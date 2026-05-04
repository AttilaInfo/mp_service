"""
admin.py — панель администратора.

Доступ только для email из переменной окружения ADMIN_EMAIL.

Маршруты:
  GET  /admin                          — дашборд
  GET  /admin/users                    — список пользователей
  GET  /admin/user/<id>                — детали пользователя
  POST /admin/user/<id>/tokens         — скорректировать токены
  GET  /admin/promocodes               — список промокодов
  POST /admin/promocodes/create        — создать промокод
  POST /admin/promocodes/<code>/deactivate — отключить промокод
  GET  /admin/services                 — услуги с ценами
  POST /admin/services/<slug>/price    — изменить цену
  GET  /admin/payments                 — история платежей
"""

import os
import uuid
from datetime import datetime

from flask import Blueprint, request, redirect
from auth import me
from templates import render
import database as db

admin_bp = Blueprint('admin', __name__)


# ── Доступ ─────────────────────────────────────────────────────────────────

def _is_admin():
    u = me()
    if not u:
        return False
    admin_email = os.environ.get('ADMIN_EMAIL', '')
    return admin_email and u['email'].lower() == admin_email.lower()


def _admin_or_redirect():
    if not _is_admin():
        return redirect('/dashboard')
    return None


# ── Общие стили для таблиц ─────────────────────────────────────────────────

TABLE_STYLE = (
    'width:100%;border-collapse:collapse;font-size:.88rem'
)
TH_STYLE = (
    'padding:.6rem .75rem;text-align:left;font-size:.8rem;'
    'color:#888;font-weight:600;border-bottom:2px solid #f0f2f5;white-space:nowrap'
)
TD_STYLE = (
    'padding:.6rem .75rem;border-bottom:1px solid #f8f9fa;vertical-align:middle'
)


def _badge(text, color):
    return (
        f'<span style="background:{color}20;color:{color};border-radius:6px;'
        f'padding:.15rem .55rem;font-size:.78rem;font-weight:600">{text}</span>'
    )


# ── Дашборд ────────────────────────────────────────────────────────────────

@admin_bp.route('/admin')
def admin_dashboard():
    r = _admin_or_redirect()
    if r: return r

    stats = db.get_admin_stats()

    cards = (
        '<div class="cards">'
        f'<div class="card"><div class="ic">👥</div><div>'
        f'<div class="n">{stats["total_users"]}</div>'
        f'<div class="lb">Пользователей</div></div></div>'

        f'<div class="card"><div class="ic">🚀</div><div>'
        f'<div class="n">{stats["active_tests"]}</div>'
        f'<div class="lb">Активных тестов</div></div></div>'

        f'<div class="card"><div class="ic">💰</div><div>'
        f'<div class="n">{stats["total_revenue"]}₽</div>'
        f'<div class="lb">Доходы всего</div></div></div>'

        f'<div class="card"><div class="ic">💳</div><div>'
        f'<div class="n">{stats["total_payments"]}</div>'
        f'<div class="lb">Успешных платежей</div></div></div>'
        '</div>'
    )

    nav = (
        '<div style="display:flex;gap:.75rem;flex-wrap:wrap;margin-bottom:1.5rem">'
        '<a href="/admin/users" class="btn bp">👥 Пользователи</a>'
        '<a href="/admin/promocodes" class="btn bp">🎁 Промокоды</a>'
        '<a href="/admin/services" class="btn bp">⚙️ Услуги и цены</a>'
        '<a href="/admin/payments" class="btn bp">💳 Платежи</a>'
        '</div>'
    )

    c = '<p class="ttl">🔧 Панель администратора</p>' + nav + cards
    return render(c, 'admin')


# ── Пользователи ───────────────────────────────────────────────────────────

@admin_bp.route('/admin/users')
def admin_users():
    r = _admin_or_redirect()
    if r: return r

    users = db.get_all_users_with_balance()

    rows = ''
    for u in users:
        rows += (
            f'<tr>'
            f'<td style="{TD_STYLE}">{u["id"]}</td>'
            f'<td style="{TD_STYLE}"><a href="/admin/user/{u["id"]}" style="color:#667eea;font-weight:600">{u["email"]}</a></td>'
            f'<td style="{TD_STYLE}">{u["name"]}</td>'
            f'<td style="{TD_STYLE}"><strong>{u["balance"]}</strong></td>'
            f'<td style="{TD_STYLE}">{str(u["created_at"])[:10]}</td>'
            f'</tr>'
        )

    table = (
        f'<table style="{TABLE_STYLE}">'
        f'<thead><tr>'
        f'<th style="{TH_STYLE}">ID</th>'
        f'<th style="{TH_STYLE}">Email</th>'
        f'<th style="{TH_STYLE}">Имя</th>'
        f'<th style="{TH_STYLE}">Токены</th>'
        f'<th style="{TH_STYLE}">Дата регистрации</th>'
        f'</tr></thead>'
        f'<tbody>{rows}</tbody>'
        f'</table>'
    )

    c = (
        '<div style="display:flex;align-items:center;gap:1rem;margin-bottom:1.5rem">'
        '<a href="/admin" class="btn" style="background:#f0f2f5;border:1px solid #ddd;color:#444">← Назад</a>'
        f'<p class="ttl" style="margin:0">👥 Пользователи ({len(users)})</p>'
        '</div>'
        '<div class="box"><div style="overflow-x:auto">' + table + '</div></div>'
    )
    return render(c, 'admin')


# ── Детали пользователя ────────────────────────────────────────────────────

@admin_bp.route('/admin/user/<int:user_id>')
def admin_user(user_id):
    r = _admin_or_redirect()
    if r: return r

    u = db.get_user_by_id(user_id)
    if not u:
        return redirect('/admin/users')

    balance = db.get_balance(user_id)
    txs     = db.get_transactions(user_id, limit=30)
    ref     = db.get_referral_earnings(user_id)

    # Форма корректировки токенов
    msg = request.args.get('msg', '')
    msg_html = ''
    if msg:
        color = '#d4edda' if 'успешно' in msg.lower() else '#f8d7da'
        msg_html = f'<div style="background:{color};border-radius:8px;padding:.65rem 1rem;font-size:.88rem;margin-bottom:1rem">{msg}</div>'

    token_form = (
        '<div class="box">'
        '<h2>⚙️ Скорректировать токены</h2>'
        + msg_html +
        f'<form method="POST" action="/admin/user/{user_id}/tokens" '
        'style="display:flex;gap:.75rem;flex-wrap:wrap;align-items:flex-end">'
        '<div class="fg" style="margin:0;flex:1;min-width:140px">'
        '<label>Сумма (+ добавить, − снять)</label>'
        '<input type="number" name="amount" class="fi" placeholder="например: 500 или -500" required></div>'
        '<div class="fg" style="margin:0;flex:2;min-width:200px">'
        '<label>Комментарий</label>'
        '<input type="text" name="description" class="fi" placeholder="Причина корректировки"></div>'
        '<button type="submit" class="btn bp">Применить</button>'
        '</form>'
        '</div>'
    )

    # История транзакций
    tx_rows = ''
    for tx in txs:
        amount = tx['amount']
        color  = '#27ae60' if amount > 0 else '#e74c3c'
        tx_rows += (
            f'<tr>'
            f'<td style="{TD_STYLE};font-size:.82rem;color:#888">{str(tx["created_at"])[:16]}</td>'
            f'<td style="{TD_STYLE}">{tx["type"]}</td>'
            f'<td style="{TD_STYLE};color:#555">{tx.get("description","")}</td>'
            f'<td style="{TD_STYLE};font-weight:700;color:{color};text-align:right">'
            f'{("+" if amount > 0 else "")}{amount}</td>'
            f'</tr>'
        )

    tx_table = (
        f'<table style="{TABLE_STYLE}">'
        f'<thead><tr>'
        f'<th style="{TH_STYLE}">Дата</th>'
        f'<th style="{TH_STYLE}">Тип</th>'
        f'<th style="{TH_STYLE}">Описание</th>'
        f'<th style="{TH_STYLE}" align="right">Токены</th>'
        f'</tr></thead>'
        f'<tbody>{tx_rows if tx_rows else "<tr><td colspan=4 style=padding:.75rem;color:#aaa;text-align:center>Нет транзакций</td></tr>"}</tbody>'
        f'</table>'
    )

    c = (
        '<div style="display:flex;align-items:center;gap:1rem;margin-bottom:1.5rem">'
        '<a href="/admin/users" class="btn" style="background:#f0f2f5;border:1px solid #ddd;color:#444">← Назад</a>'
        f'<p class="ttl" style="margin:0">👤 {u["name"]}</p>'
        '</div>'

        '<div class="cards">'
        f'<div class="card"><div class="ic">🪙</div><div><div class="n">{balance}</div><div class="lb">Токенов</div></div></div>'
        f'<div class="card"><div class="ic">📧</div><div><div class="n" style="font-size:1rem">{u["email"]}</div><div class="lb">Email</div></div></div>'
        f'<div class="card"><div class="ic">🤝</div><div><div class="n">{ref["count"]}</div><div class="lb">Рефералов</div></div></div>'
        f'<div class="card"><div class="ic">📅</div><div><div class="n" style="font-size:1rem">{str(u["created_at"])[:10]}</div><div class="lb">Регистрация</div></div></div>'
        '</div>'

        + token_form +

        '<div class="box">'
        '<h2>📋 История транзакций</h2>'
        '<div style="overflow-x:auto">' + tx_table + '</div>'
        '</div>'
    )
    return render(c, 'admin')


@admin_bp.route('/admin/user/<int:user_id>/tokens', methods=['POST'])
def admin_adjust_tokens(user_id):
    r = _admin_or_redirect()
    if r: return r

    try:
        amount      = int(request.form.get('amount', 0))
        description = request.form.get('description', '').strip() or 'Корректировка администратором'
    except ValueError:
        return redirect(f'/admin/user/{user_id}?msg=Неверная+сумма')

    if amount == 0:
        return redirect(f'/admin/user/{user_id}?msg=Сумма+не+может+быть+0')

    db.admin_adjust_tokens(user_id, amount, description)
    action = 'начислено' if amount > 0 else 'списано'
    return redirect(f'/admin/user/{user_id}?msg=Успешно:+{action}+{abs(amount)}+токенов')


# ── Промокоды ──────────────────────────────────────────────────────────────

@admin_bp.route('/admin/promocodes')
def admin_promocodes():
    r = _admin_or_redirect()
    if r: return r

    promos = db.get_all_promocodes()
    msg    = request.args.get('msg', '')

    msg_html = ''
    if msg:
        color = '#d4edda' if 'успешно' in msg.lower() or 'создан' in msg.lower() else '#f8d7da'
        msg_html = f'<div style="background:{color};border-radius:8px;padding:.65rem 1rem;font-size:.88rem;margin-bottom:1rem">{msg}</div>'

    # Форма создания промокода
    create_form = (
        '<div class="box">'
        '<h2>➕ Создать промокод</h2>'
        + msg_html +
        '<form method="POST" action="/admin/promocodes/create">'
        '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:.75rem;margin-bottom:.75rem">'

        '<div class="fg" style="margin:0">'
        '<label>Код</label>'
        '<input type="text" name="code" class="fi" placeholder="LAUNCH2025" '
        'style="text-transform:uppercase" required></div>'

        '<div class="fg" style="margin:0">'
        '<label>Токены</label>'
        '<input type="number" name="tokens" class="fi" value="1000" min="1" required></div>'

        '<div class="fg" style="margin:0">'
        '<label>Тип</label>'
        '<select name="type" class="fi">'
        '<option value="public">Публичный (многоразовый)</option>'
        '<option value="personal">Личный (одноразовый)</option>'
        '</select></div>'

        '<div class="fg" style="margin:0">'
        '<label>Макс. использований</label>'
        '<input type="number" name="max_uses" class="fi" placeholder="пусто = безлимит"></div>'

        '<div class="fg" style="margin:0">'
        '<label>Действует до</label>'
        '<input type="date" name="expires_at" class="fi"></div>'

        '<div class="fg" style="margin:0">'
        '<label>UTM-метка</label>'
        '<input type="text" name="utm_source" class="fi" placeholder="vk_ads"></div>'

        '</div>'
        '<button type="submit" class="btn bp">Создать промокод</button>'
        '</form>'
        '</div>'
    )

    # Таблица промокодов
    rows = ''
    for p in promos:
        active_badge = _badge('Активен', '#27ae60') if p['active'] else _badge('Отключён', '#e74c3c')
        type_badge   = _badge('Публичный', '#2196f3') if p['type'] == 'public' else _badge('Личный', '#9c27b0')
        expires      = str(p['expires_at'])[:10] if p['expires_at'] else '—'
        max_uses     = str(p['max_uses']) if p['max_uses'] else '∞'
        deact_btn    = ''
        if p['active']:
            deact_btn = (
                f'<form method="POST" action="/admin/promocodes/{p["code"]}/deactivate" style="margin:0">'
                f'<button class="btn" style="padding:.3rem .7rem;font-size:.78rem;background:#f8d7da;'
                f'border:1px solid #f5c6cb;color:#721c24">Отключить</button></form>'
            )
        rows += (
            f'<tr>'
            f'<td style="{TD_STYLE}"><strong style="font-family:monospace">{p["code"]}</strong></td>'
            f'<td style="{TD_STYLE}">{type_badge}</td>'
            f'<td style="{TD_STYLE}"><strong>{p["tokens"]}</strong></td>'
            f'<td style="{TD_STYLE}">{p["used_count"]} / {max_uses}</td>'
            f'<td style="{TD_STYLE}">{expires}</td>'
            f'<td style="{TD_STYLE}">{p.get("utm_source","") or "—"}</td>'
            f'<td style="{TD_STYLE}">{active_badge}</td>'
            f'<td style="{TD_STYLE}">{deact_btn}</td>'
            f'</tr>'
        )

    table = (
        f'<table style="{TABLE_STYLE}">'
        '<thead><tr>'
        f'<th style="{TH_STYLE}">Код</th>'
        f'<th style="{TH_STYLE}">Тип</th>'
        f'<th style="{TH_STYLE}">Токены</th>'
        f'<th style="{TH_STYLE}">Использован</th>'
        f'<th style="{TH_STYLE}">Действует до</th>'
        f'<th style="{TH_STYLE}">UTM</th>'
        f'<th style="{TH_STYLE}">Статус</th>'
        f'<th style="{TH_STYLE}"></th>'
        '</tr></thead>'
        f'<tbody>{rows if rows else "<tr><td colspan=8 style=padding:.75rem;color:#aaa;text-align:center>Промокодов пока нет</td></tr>"}</tbody>'
        '</table>'
    )

    c = (
        '<div style="display:flex;align-items:center;gap:1rem;margin-bottom:1.5rem">'
        '<a href="/admin" class="btn" style="background:#f0f2f5;border:1px solid #ddd;color:#444">← Назад</a>'
        '<p class="ttl" style="margin:0">🎁 Промокоды</p>'
        '</div>'
        + create_form +
        '<div class="box"><div style="overflow-x:auto">' + table + '</div></div>'
    )
    return render(c, 'admin')


@admin_bp.route('/admin/promocodes/create', methods=['POST'])
def admin_create_promo():
    r = _admin_or_redirect()
    if r: return r

    code       = request.form.get('code', '').strip().upper()
    tokens     = int(request.form.get('tokens', 1000))
    promo_type = request.form.get('type', 'public')
    utm        = request.form.get('utm_source', '').strip()

    max_uses_raw = request.form.get('max_uses', '').strip()
    max_uses     = int(max_uses_raw) if max_uses_raw else None

    expires_raw = request.form.get('expires_at', '').strip()
    expires_at  = datetime.strptime(expires_raw, '%Y-%m-%d') if expires_raw else None

    if not code:
        return redirect('/admin/promocodes?msg=Введите+код')

    try:
        db.create_promocode(code, tokens, promo_type, None, max_uses, expires_at, utm)
        return redirect(f'/admin/promocodes?msg=Промокод+{code}+успешно+создан')
    except Exception as e:
        if 'unique' in str(e).lower():
            return redirect(f'/admin/promocodes?msg=Промокод+{code}+уже+существует')
        return redirect(f'/admin/promocodes?msg=Ошибка:+{str(e)[:60]}')


@admin_bp.route('/admin/promocodes/<code>/deactivate', methods=['POST'])
def admin_deactivate_promo(code):
    r = _admin_or_redirect()
    if r: return r

    db.deactivate_promocode(code)
    return redirect(f'/admin/promocodes?msg=Промокод+{code}+отключён')


# ── Услуги и цены ──────────────────────────────────────────────────────────

@admin_bp.route('/admin/services')
def admin_services():
    r = _admin_or_redirect()
    if r: return r

    services = db.get_all_services()
    msg      = request.args.get('msg', '')

    msg_html = ''
    if msg:
        color = '#d4edda' if 'успешно' in msg.lower() else '#f8d7da'
        msg_html = f'<div style="background:{color};border-radius:8px;padding:.65rem 1rem;font-size:.88rem;margin-bottom:1rem">{msg}</div>'

    rows = ''
    for s in services:
        active_badge = _badge('Активна', '#27ae60') if s['active'] else _badge('Отключена', '#e74c3c')
        rows += (
            f'<tr>'
            f'<td style="{TD_STYLE}">{s["id"]}</td>'
            f'<td style="{TD_STYLE}"><strong>{s["name"]}</strong></td>'
            f'<td style="{TD_STYLE};font-family:monospace">{s["slug"]}</td>'
            f'<td style="{TD_STYLE}">'
            f'<form method="POST" action="/admin/services/{s["slug"]}/price" '
            f'style="display:flex;gap:.5rem;align-items:center">'
            f'<input type="number" name="token_cost" value="{s["token_cost"]}" '
            f'class="fi" style="max-width:100px;padding:.4rem .6rem" min="1" required>'
            f'<button type="submit" class="btn bp" style="padding:.4rem .8rem;font-size:.82rem">Сохранить</button>'
            f'</form>'
            f'</td>'
            f'<td style="{TD_STYLE}">{active_badge}</td>'
            f'</tr>'
        )

    table = (
        f'<table style="{TABLE_STYLE}">'
        '<thead><tr>'
        f'<th style="{TH_STYLE}">ID</th>'
        f'<th style="{TH_STYLE}">Название</th>'
        f'<th style="{TH_STYLE}">Slug</th>'
        f'<th style="{TH_STYLE}">Стоимость (токенов)</th>'
        f'<th style="{TH_STYLE}">Статус</th>'
        '</tr></thead>'
        f'<tbody>{rows}</tbody>'
        '</table>'
    )

    c = (
        '<div style="display:flex;align-items:center;gap:1rem;margin-bottom:1.5rem">'
        '<a href="/admin" class="btn" style="background:#f0f2f5;border:1px solid #ddd;color:#444">← Назад</a>'
        '<p class="ttl" style="margin:0">⚙️ Услуги и цены</p>'
        '</div>'
        + msg_html +
        '<div class="box"><div style="overflow-x:auto">' + table + '</div></div>'
        '<div class="box" style="background:#fff8e1;border:1.5px solid #ffe082">'
        '<p style="font-size:.88rem;color:#856404">💡 Изменение цены вступает в силу немедленно для всех новых тестов. '
        'Текущие активные тесты не затрагиваются.</p>'
        '</div>'
    )
    return render(c, 'admin')


@admin_bp.route('/admin/services/<slug>/price', methods=['POST'])
def admin_update_price(slug):
    r = _admin_or_redirect()
    if r: return r

    try:
        token_cost = int(request.form.get('token_cost', 500))
        db.update_service_cost(slug, token_cost)
        return redirect(f'/admin/services?msg=Цена+успешно+обновлена:+{token_cost}+токенов')
    except Exception as e:
        return redirect(f'/admin/services?msg=Ошибка:+{str(e)[:60]}')


# ── Платежи ────────────────────────────────────────────────────────────────

@admin_bp.route('/admin/payments')
def admin_payments():
    r = _admin_or_redirect()
    if r: return r

    with db.get_conn() as conn:
        import psycopg2.extras
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT p.*, u.email, u.name
                FROM payments p
                JOIN users u ON u.id = p.user_id
                ORDER BY p.created_at DESC
                LIMIT 100
            """)
            payments = cur.fetchall()

    status_colors = {
        'succeeded': '#27ae60',
        'pending':   '#ff9800',
        'canceled':  '#e74c3c',
    }

    rows = ''
    for p in payments:
        color = status_colors.get(p['status'], '#888')
        rows += (
            f'<tr>'
            f'<td style="{TD_STYLE};font-size:.82rem;color:#888">{str(p["created_at"])[:16]}</td>'
            f'<td style="{TD_STYLE}">'
            f'<a href="/admin/user/{p["user_id"]}" style="color:#667eea">{p["email"]}</a></td>'
            f'<td style="{TD_STYLE}"><strong>{p["amount_rub"]}₽</strong></td>'
            f'<td style="{TD_STYLE}">{p["tokens"]}</td>'
            f'<td style="{TD_STYLE}">{_badge(p["status"], color)}</td>'
            f'<td style="{TD_STYLE};font-size:.78rem;color:#aaa;font-family:monospace">'
            f'{p["yookassa_id"][:16]}...</td>'
            f'</tr>'
        )

    table = (
        f'<table style="{TABLE_STYLE}">'
        '<thead><tr>'
        f'<th style="{TH_STYLE}">Дата</th>'
        f'<th style="{TH_STYLE}">Пользователь</th>'
        f'<th style="{TH_STYLE}">Сумма</th>'
        f'<th style="{TH_STYLE}">Токены</th>'
        f'<th style="{TH_STYLE}">Статус</th>'
        f'<th style="{TH_STYLE}">ID платежа</th>'
        '</tr></thead>'
        f'<tbody>{rows if rows else "<tr><td colspan=6 style=padding:.75rem;color:#aaa;text-align:center>Платежей пока нет</td></tr>"}</tbody>'
        '</table>'
    )

    total = sum(p['amount_rub'] for p in payments if p['status'] == 'succeeded')

    c = (
        '<div style="display:flex;align-items:center;gap:1rem;margin-bottom:1.5rem">'
        '<a href="/admin" class="btn" style="background:#f0f2f5;border:1px solid #ddd;color:#444">← Назад</a>'
        f'<p class="ttl" style="margin:0">💳 Платежи (последние 100)</p>'
        '</div>'
        f'<div class="box" style="background:#d4edda;border:1.5px solid #c3e6cb;margin-bottom:1rem">'
        f'<p style="font-size:.9rem;margin:0">💰 Итого успешных платежей в этом списке: <strong>{total}₽</strong></p>'
        '</div>'
        '<div class="box"><div style="overflow-x:auto">' + table + '</div></div>'
    )
    return render(c, 'admin')
