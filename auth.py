from flask import Blueprint, request, redirect, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

import database as db
from utils import hash_pw, check_pw, valid_email, clean
from templates import render_auth, alert, pw_input

auth_bp = Blueprint('auth', __name__)


def me():
    """Вернуть текущего пользователя из БД или None."""
    user_id = session.get('user_id')
    if not user_id:
        return None
    return db.get_user_by_id(user_id)


# ── Вход ───────────────────────────────────────────────────────────────────

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if me():
        return redirect('/dashboard')

    err = ''
    if request.method == 'POST':
        email = clean(request.form.get('email', '')).lower()
        pw    = request.form.get('password', '')

        if not email or not pw:
            err = 'Заполните все поля'
        elif not valid_email(email):
            err = 'Некорректный email'
        else:
            user = db.get_user_by_email(email)
            if not user or not check_pw(pw, user['password']):
                err = 'Неверный email или пароль'
            else:
                session['user_id'] = user['id']
                return redirect('/dashboard')

    body = (
        '<div class="aw"><div class="ac">'
        '<h1>A/B Testing Pro</h1>'
        '<p class="sub">Войдите в аккаунт</p>'
        + alert(err, 'er') +
        '<form method="POST">'
        '<div class="fg"><label>Email</label>'
        '<input type="email" name="email" class="fi" placeholder="your@email.com" required autocomplete="email"></div>'
        + pw_input('password', 'pw_login', 'Ваш пароль', 'Пароль') +
        '<button class="btn bp" style="width:100%">Войти</button>'
        '</form>'
        '<p class="al2" onclick="location=\'/register\'">Нет аккаунта? Зарегистрироваться</p>'
        '<p style="text-align:center;margin-top:.8rem;font-size:.85rem;color:#aaa">'
        '<a href="/" style="color:#667eea">&#8592; На главную</a></p>'
        '</div></div>'
    )
    return render_auth(body)


# ── Регистрация ────────────────────────────────────────────────────────────

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if me():
        return redirect('/dashboard')

    err = ''
    saved_name  = ''
    saved_email = ''

    if request.method == 'POST':
        saved_name  = clean(request.form.get('name', ''), 100)
        saved_email = clean(request.form.get('email', '')).lower()
        pw          = request.form.get('password', '')
        pw2         = request.form.get('confirm', '')

        agree = request.form.get('agree', '')
        if not all([saved_name, saved_email, pw, pw2]):
            err = 'Заполните все поля'
        elif not agree:
            err = 'Необходимо согласиться с офертой и политикой обработки данных'
        elif not valid_email(saved_email):
            err = 'Некорректный email'
        elif len(pw) < 8:
            err = 'Пароль минимум 8 символов'
        elif pw != pw2:
            err = 'Пароли не совпадают'
        elif db.get_user_by_email(saved_email):
            err = 'Email уже зарегистрирован'
        else:
            user_id = db.create_user(saved_email, saved_name, hash_pw(pw))
            session['user_id'] = user_id
            # Приветственный бонус — 1000 токенов = 2 теста бесплатно
            db.add_tokens(user_id, 1000, 'promo', 'Приветственный бонус: 2 теста бесплатно')
            # Реферальная программа — если пришёл по реф-ссылке
            ref_code = session.pop('ref_code', None)
            if ref_code:
                referrer = db.get_user_by_ref_code(ref_code)
                if referrer and referrer['id'] != user_id:
                    db.create_referral(referrer['id'], user_id, percent=10)
            return redirect('/dashboard')

    name_val  = ' value="' + saved_name  + '"' if saved_name  else ''
    email_val = ' value="' + saved_email + '"' if saved_email else ''

    body = (
        '<div class="aw"><div class="ac">'
        '<h1>A/B Testing Pro</h1>'
        '<p class="sub">30 дней бесплатно — без карты</p>'
        + alert(err, 'er') +
        '<form method="POST">'
        '<div class="fg"><label>Имя</label>'
        '<input type="text" name="name" class="fi" placeholder="Иван Иванов" required maxlength="100"' + name_val + '></div>'
        '<div class="fg"><label>Email</label>'
        '<input type="email" name="email" class="fi" placeholder="your@email.com" required autocomplete="email"' + email_val + '></div>'
        + pw_input('password', 'pw_r1', 'Мин. 8 символов', 'Пароль')
        + pw_input('confirm',  'pw_r2', 'Повторите пароль', 'Повторите пароль')
        + '<div id="pw_match_hint" style="font-size:.82rem;margin-top:-.6rem;margin-bottom:1rem;min-height:1.1em"></div>'
        + '<div style="margin-bottom:1rem">'
        '<label style="display:flex;align-items:flex-start;gap:.6rem;cursor:pointer;font-size:.85rem;color:#555;line-height:1.4">'
        '<input type="checkbox" name="agree" style="margin-top:.2rem;accent-color:#667eea;flex-shrink:0" required> '
        '<span>Я принимаю условия '
        '<a href="/terms" target="_blank" style="color:#667eea;font-weight:600">публичной оферты</a>'
        ' и даю согласие на '
        '<a href="/privacy" target="_blank" style="color:#667eea;font-weight:600">обработку персональных данных</a>'
        '</span></label></div>'
        + '<button class="btn bp" style="width:100%">Создать аккаунт бесплатно</button>'
        '</form>'
        '<p class="al2" onclick="location=\'/login\'">Есть аккаунт? Войти</p>'
        '<p style="text-align:center;margin-top:.8rem;font-size:.85rem;color:#aaa">'
        '<a href="/" style="color:#667eea">&#8592; На главную</a></p>'
        '</div></div>'
    )
    return render_auth(body)


# ── Выход ──────────────────────────────────────────────────────────────────

@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect('/')
