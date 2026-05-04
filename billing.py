"""
billing.py — страница биллинга: баланс токенов, пополнение, промокоды, рефералы.

Маршруты:
  GET  /billing          — страница баланса
  POST /billing/promo    — применить промокод
  POST /billing/webhook  — webhook от ЮКассы (заготовка)
  GET  /billing/ref/<code> — реферальная ссылка
"""

import os
import hmac
import hashlib
import json
import uuid

from flask import Blueprint, request, redirect, session, jsonify

import database as db
from templates import render
from auth import me

billing_bp = Blueprint('billing', __name__)


# ── Вспомогательные ───────────────────────────────────────────────────────

def _gen_ref_code():
    """Генерация уникального реферального кода."""
    return uuid.uuid4().hex[:8].upper()


def _ensure_ref_code(user_id):
    """Убедиться что у пользователя есть реф-код, создать если нет."""
    user = db.get_user_by_id(user_id)
    if not user.get('ref_code'):
        code = _gen_ref_code()
        db.set_ref_code(user_id, code)
        return code
    return user['ref_code']


def _tx_type_label(tx_type):
    labels = {
        'purchase':  ('💳 Пополнение',  '#27ae60'),
        'spend':     ('🚀 Запуск теста', '#e74c3c'),
        'promo':     ('🎁 Промокод',     '#9b59b6'),
        'referral':  ('🤝 Реферал',      '#2980b9'),
        'admin':     ('⚙️ Администратор','#7f8c8d'),
    }
    return labels.get(tx_type, (tx_type, '#888'))


# ── Главная страница биллинга ─────────────────────────────────────────────

@billing_bp.route('/billing')
def billing():
    u = me()
    if not u:
        return redirect('/login')

    balance      = db.get_balance(u['id'])
    transactions = db.get_transactions(u['id'], limit=20)
    ref_code     = _ensure_ref_code(u['id'])
    ref_stats    = db.get_referral_earnings(u['id'])
    service      = db.get_service('ab_test')
    test_cost    = service['token_cost'] if service else 500

    base_url = os.environ.get('SERVICE_URL', 'https://mpservice-production.up.railway.app')
    ref_url  = f'{base_url}/billing/ref/{ref_code}'

    # ── Карточки статистики ──────────────────────────────────────────────
    cards = (
        '<div class="cards">'
        f'<div class="card"><div class="ic">🪙</div><div><div class="n">{balance}</div>'
        f'<div class="lb">Токенов на балансе</div></div></div>'
        f'<div class="card"><div class="ic">🚀</div><div><div class="n">{test_cost}</div>'
        f'<div class="lb">Токенов за 1 тест</div></div></div>'
        f'<div class="card"><div class="ic">🤝</div><div><div class="n">{ref_stats["count"]}</div>'
        f'<div class="lb">Рефералов</div></div></div>'
        f'<div class="card"><div class="ic">💰</div><div><div class="n">{ref_stats["earned"]}</div>'
        f'<div class="lb">Заработано токенов</div></div></div>'
        '</div>'
    )

    # ── Пополнение баланса ───────────────────────────────────────────────
    yookassa_ready = bool(os.environ.get('YOOKASSA_SHOP_ID'))
    if yookassa_ready:
        pay_block = (
            '<div class="box">'
            '<h2>💳 Пополнить баланс</h2>'
            '<p style="font-size:.9rem;color:#666;margin-bottom:1rem">'
            f'Минимальное пополнение: <strong>{test_cost}₽ = {test_cost} токенов</strong></p>'
            '<form method="POST" action="/billing/pay" style="display:flex;gap:.75rem;flex-wrap:wrap;align-items:flex-end">'
            '<div class="fg" style="margin:0;flex:1;min-width:140px">'
            '<label>Сумма (₽)</label>'
            f'<input type="number" name="amount" class="fi" value="{test_cost}" '
            f'min="{test_cost}" step="{test_cost}" required style="max-width:180px">'
            '</div>'
            '<button type="submit" class="btn bp">Оплатить через ЮКассу →</button>'
            '</form>'
            '</div>'
        )
    else:
        pay_block = (
            '<div class="box" style="background:#fff8e1;border:1.5px solid #ffe082">'
            '<h2>💳 Пополнить баланс</h2>'
            '<p style="font-size:.9rem;color:#666;margin-bottom:.5rem">'
            'Оплата через ЮКассу подключается. Пока вы можете получить токены по промокоду.</p>'
            '<p style="font-size:.82rem;color:#aaa">Если вы администратор — подключите ЮКассу в переменных окружения Railway.</p>'
            '</div>'
        )

    # ── Промокод ────────────────────────────────────────────────────────
    promo_msg = request.args.get('promo_msg', '')
    promo_ok  = request.args.get('promo_ok', '')
    promo_feedback = ''
    if promo_msg:
        color = '#d4edda' if promo_ok else '#f8d7da'
        border = '#c3e6cb' if promo_ok else '#f5c6cb'
        promo_feedback = (
            f'<div style="background:{color};border:1px solid {border};'
            f'border-radius:8px;padding:.75rem 1rem;font-size:.9rem;margin-bottom:.75rem">'
            f'{promo_msg}</div>'
        )

    promo_block = (
        '<div class="box">'
        '<h2>🎁 Промокод</h2>'
        + promo_feedback +
        '<form method="POST" action="/billing/promo" '
        'style="display:flex;gap:.75rem;flex-wrap:wrap;align-items:flex-end">'
        '<div class="fg" style="margin:0;flex:1;min-width:180px">'
        '<label>Введите промокод</label>'
        '<input type="text" name="code" class="fi" placeholder="НАПРИМЕР: LAUNCH2024" '
        'style="text-transform:uppercase;letter-spacing:.05em" required>'
        '</div>'
        '<button type="submit" class="btn bp">Применить</button>'
        '</form>'
        '</div>'
    )

    # ── Реферальная программа ────────────────────────────────────────────
    ref_block = (
        '<div class="box">'
        '<h2>🤝 Реферальная программа</h2>'
        '<p style="font-size:.9rem;color:#666;margin-bottom:1rem">'
        'Приглашайте друзей — получайте <strong>10% токенов</strong> от каждого их пополнения.</p>'
        '<div style="background:#f0f2f5;border-radius:8px;padding:.75rem 1rem;'
        'display:flex;align-items:center;gap:.75rem;flex-wrap:wrap;margin-bottom:.75rem">'
        f'<span style="font-family:monospace;font-size:.95rem;word-break:break-all">{ref_url}</span>'
        f'<button type="button" onclick="navigator.clipboard.writeText(\'{ref_url}\');this.textContent=\'✓ Скопировано\'" '
        'style="background:#667eea;color:#fff;border:none;border-radius:8px;'
        'padding:.4rem .9rem;cursor:pointer;font-size:.82rem;white-space:nowrap">Скопировать</button>'
        '</div>'
        f'<p style="font-size:.82rem;color:#888">Рефералов: <strong>{ref_stats["count"]}</strong> · '
        f'Заработано: <strong>{ref_stats["earned"]} токенов</strong></p>'
        '</div>'
    )

    # ── История транзакций ───────────────────────────────────────────────
    if transactions:
        rows = ''
        for tx in transactions:
            label, color = _tx_type_label(tx['type'])
            amount = tx['amount']
            amount_str = (f'+{amount}' if amount > 0 else str(amount))
            amount_color = '#27ae60' if amount > 0 else '#e74c3c'
            date_str = str(tx['created_at'])[:16]
            rows += (
                f'<tr>'
                f'<td style="padding:.6rem .75rem;font-size:.85rem;color:#666">{date_str}</td>'
                f'<td style="padding:.6rem .75rem">'
                f'<span style="background:{color}20;color:{color};border-radius:6px;'
                f'padding:.2rem .6rem;font-size:.8rem;font-weight:600">{label}</span></td>'
                f'<td style="padding:.6rem .75rem;font-size:.85rem;color:#555">'
                f'{tx.get("description","")}</td>'
                f'<td style="padding:.6rem .75rem;font-weight:700;color:{amount_color};'
                f'text-align:right">{amount_str}</td>'
                f'</tr>'
            )
        tx_block = (
            '<div class="box">'
            '<h2>📋 История операций</h2>'
            '<div style="overflow-x:auto">'
            '<table style="width:100%;border-collapse:collapse">'
            '<thead><tr style="border-bottom:2px solid #f0f2f5">'
            '<th style="padding:.5rem .75rem;text-align:left;font-size:.82rem;color:#888;font-weight:600">Дата</th>'
            '<th style="padding:.5rem .75rem;text-align:left;font-size:.82rem;color:#888;font-weight:600">Тип</th>'
            '<th style="padding:.5rem .75rem;text-align:left;font-size:.82rem;color:#888;font-weight:600">Описание</th>'
            '<th style="padding:.5rem .75rem;text-align:right;font-size:.82rem;color:#888;font-weight:600">Токены</th>'
            '</tr></thead>'
            f'<tbody>{rows}</tbody>'
            '</table></div></div>'
        )
    else:
        tx_block = (
            '<div class="box">'
            '<h2>📋 История операций</h2>'
            '<p style="color:#aaa;font-size:.9rem">Операций пока нет.</p>'
            '</div>'
        )

    c = (
        '<p class="ttl">🪙 Баланс и оплата</p>'
        + cards
        + pay_block
        + promo_block
        + ref_block
        + tx_block
    )
    return render(c, 'billing')


# ── Применить промокод ────────────────────────────────────────────────────

@billing_bp.route('/billing/promo', methods=['POST'])
def apply_promo():
    u = me()
    if not u:
        return redirect('/login')

    code = request.form.get('code', '').strip().upper()
    if not code:
        return redirect('/billing?promo_msg=Введите+промокод')

    tokens, err = db.use_promocode(code, u['id'])
    if err:
        return redirect(f'/billing?promo_msg={err.replace(" ", "+")}')

    return redirect(f'/billing?promo_ok=1&promo_msg=✓+Промокод+применён!+Начислено+{tokens}+токенов')


# ── Реферальная ссылка ────────────────────────────────────────────────────

@billing_bp.route('/billing/ref/<code>')
def ref_landing(code):
    """Записываем реферальный код в сессию и редиректим на регистрацию."""
    session['ref_code'] = code
    return redirect('/register')


# ── Webhook ЮКассы ────────────────────────────────────────────────────────

@billing_bp.route('/billing/webhook', methods=['POST'])
def yookassa_webhook():
    """
    Webhook от ЮКассы — уведомление об успешной оплате.
    Документация: https://yookassa.ru/developers/using-api/webhooks
    """
    try:
        data = request.get_json(force=True)
        if not data:
            return jsonify({'error': 'no data'}), 400

        event  = data.get('event', '')
        obj    = data.get('object', {})
        status = obj.get('status', '')

        if event == 'payment.succeeded' and status == 'succeeded':
            yookassa_id = obj.get('id')
            if not yookassa_id:
                return jsonify({'error': 'no payment id'}), 400

            # Обновляем статус платежа и начисляем токены
            payment = db.update_payment_status(yookassa_id, 'succeeded')
            if payment:
                db.add_tokens(
                    payment['user_id'],
                    payment['tokens'],
                    'purchase',
                    f'Пополнение на {payment["amount_rub"]}₽'
                )
                # Начисляем реферальный бонус если есть
                db.pay_referral_bonus(payment['user_id'], payment['amount_rub'])

        elif event == 'payment.canceled':
            yookassa_id = obj.get('id')
            if yookassa_id:
                db.update_payment_status(yookassa_id, 'canceled')

        return jsonify({'status': 'ok'}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Создать платёж через ЮКассу ───────────────────────────────────────────

@billing_bp.route('/billing/pay', methods=['POST'])
def pay():
    u = me()
    if not u:
        return redirect('/login')

    try:
        amount = int(request.form.get('amount', 0))
    except (ValueError, TypeError):
        return redirect('/billing?promo_msg=Неверная+сумма')

    service   = db.get_service('ab_test')
    min_amount = service['token_cost'] if service else 500

    if amount < min_amount:
        return redirect(f'/billing?promo_msg=Минимальная+сумма+{min_amount}₽')

    shop_id    = os.environ.get('YOOKASSA_SHOP_ID')
    secret_key = os.environ.get('YOOKASSA_SECRET_KEY')

    if not shop_id or not secret_key:
        return redirect('/billing?promo_msg=Оплата+временно+недоступна.+Попробуйте+позже.')

    try:
        import requests as req
        idempotency_key = uuid.uuid4().hex
        base_url = os.environ.get('SERVICE_URL', 'https://mpservice-production.up.railway.app')

        payload = {
            'amount': {'value': f'{amount}.00', 'currency': 'RUB'},
            'confirmation': {
                'type': 'redirect',
                'return_url': f'{base_url}/billing?promo_ok=1&promo_msg=Оплата+прошла+успешно'
            },
            'capture': True,
            'description': f'Пополнение баланса A/B Testing Pro на {amount}₽',
            'metadata': {'user_id': u['id'], 'tokens': amount},
        }

        r = req.post(
            'https://api.yookassa.ru/v3/payments',
            json=payload,
            auth=(shop_id, secret_key),
            headers={'Idempotence-Key': idempotency_key},
            timeout=15
        )

        if r.status_code != 200:
            return redirect(f'/billing?promo_msg=Ошибка+ЮКассы:+{r.status_code}')

        payment_data = r.json()
        yookassa_id  = payment_data['id']
        confirm_url  = payment_data['confirmation']['confirmation_url']

        # Сохраняем платёж со статусом pending
        db.create_payment(u['id'], yookassa_id, amount, amount)

        return redirect(confirm_url)

    except Exception as e:
        return redirect(f'/billing?promo_msg=Ошибка:+{str(e)[:60]}')
