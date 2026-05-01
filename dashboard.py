from flask import Blueprint, redirect
import database as db
from templates import render, alert
from auth import me

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/dashboard')
def dashboard():
    u = me()
    if not u:
        return redirect('/login')

    kc = db.count_keys(u['id'])
    warn = alert(
        'Добавьте API ключи Озона чтобы начать. <a href="/api-keys" style="font-weight:700">Добавить</a>',
        'wn'
    ) if kc == 0 else ''

    c = warn + '<p class="ttl">Привет, ' + u['name'] + '!</p>'

    c += '<div class="cards">'
    c += '<div class="card"><div class="ic">&#129514;</div><div><div class="n">0</div><div class="lb">Активных тестов</div></div></div>'
    c += '<div class="card"><div class="ic">&#128273;</div><div><div class="n">' + str(kc) + '</div><div class="lb">API подключений</div></div></div>'
    c += '<div class="card"><div class="ic">&#128065;</div><div><div class="n">0</div><div class="lb">Просмотров</div></div></div>'
    c += '<div class="card"><div class="ic">&#128200;</div><div><div class="n">0%</div><div class="lb">Рост конверсии</div></div></div>'
    c += '</div>'

    c += (
        '<div class="box"><h2>&#129514; Активные тесты</h2>'
        '<div class="empty">'
        '<p style="font-size:2rem">&#129514;</p>'
        '<p style="margin-top:1rem">Тестов пока нет</p>'
        '<p style="font-size:.9rem;margin-top:.5rem;color:#aaa">Перейдите в раздел «Тесты» чтобы создать первый</p>'
        '<a href="/tests" class="btn bp" style="margin-top:1.5rem">Создать тест</a>'
        '</div></div>'
    )

    c += '<div class="tip">&#128161; <strong>Совет:</strong> Для достоверных результатов нужно минимум 100 просмотров и 7 дней тестирования.</div>'
    return render(c, 'dash')


@dashboard_bp.route('/tests')
def tests():
    u = me()
    if not u:
        return redirect('/login')
    c = (
        '<p class="ttl">Мои тесты</p>'
        '<div class="box"><div class="empty">'
        '<p style="font-size:2rem">&#129514;</p>'
        '<p style="margin-top:1rem">Раздел в разработке</p>'
        '<p style="font-size:.9rem;margin-top:.5rem;color:#aaa">Скоро здесь появится возможность создавать тесты с 2–10 вариантами фото</p>'
        '</div></div>'
    )
    return render(c, 'tests')


@dashboard_bp.route('/settings')
def settings():
    u = me()
    if not u:
        return redirect('/login')

    kc = db.count_keys(u['id'])
    c = (
        '<p class="ttl">Настройки</p>'
        '<div class="box"><h2>&#128100; Профиль</h2>'
        '<table style="width:auto">'
        '<tr><td style="color:#666;padding:.5rem 2rem .5rem 0">Имя:</td><td><strong>' + u['name'] + '</strong></td></tr>'
        '<tr><td style="color:#666;padding:.5rem 2rem .5rem 0">Email:</td><td><strong>' + u['email'] + '</strong></td></tr>'
        '<tr><td style="color:#666;padding:.5rem 2rem .5rem 0">API ключей:</td><td><strong>' + str(kc) + '</strong></td></tr>'
        '<tr><td style="color:#666;padding:.5rem 2rem .5rem 0">Аккаунт создан:</td><td><strong>' + str(u['created_at'])[:10] + '</strong></td></tr>'
        '</table></div>'
    )
    return render(c, 'cfg')
