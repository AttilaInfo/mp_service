from flask import Blueprint, request, redirect, session
from flask_limiter import Limiter

import database as db
from utils import clean, verify_ozon
from templates import render, alert
from config import MAX_API_KEYS
from auth import me

api_keys_bp = Blueprint('api_keys', __name__)


@api_keys_bp.route('/api-keys')
def api_keys():
    u = me()
    if not u:
        return redirect('/login')

    msg       = request.args.get('msg', '')
    err       = request.args.get('err', '')
    saved_shop = request.args.get('shop', '')
    saved_cid  = request.args.get('cid', '')
    keys = db.get_keys(u['id'])
    cnt  = len(keys)

    c = '<p class="ttl">API ключи Озона</p>'
    c += alert(msg, 'ok')
    c += alert(err, 'er')

    # ── Форма добавления ───────────────────────────────────────────────────
    c += '<div class="box"><h2>Добавить подключение</h2>'
    c += (
        '<div class="tip" style="margin-bottom:1rem">'
        '&#128273; <strong>Где взять ключи:</strong> '
        '<a href="https://seller.ozon.ru/app/settings/api-keys" target="_blank" '
        'style="color:#1e40af;font-weight:600">seller.ozon.ru &rarr; Настройки &rarr; API ключи</a>'
        ' &rarr; нажмите «Сгенерировать ключ»'
        '</div>'
        '<div style="background:#fff8e1;border:1px solid #ffe082;border-radius:10px;padding:1.2rem;margin-bottom:1.2rem">'
        '<p style="font-weight:700;margin-bottom:.8rem;color:#856404">&#9888; Какие права выбрать:</p>'
        '<div style="display:flex;flex-direction:column;gap:.5rem">'
        '<div style="display:flex;gap:.5rem;font-size:.9rem"><span style="color:#27ae60;font-weight:700">&#10003;</span><div><strong>Product read-only</strong> &mdash; чтение данных о товарах</div></div>'
        '<div style="display:flex;gap:.5rem;font-size:.9rem"><span style="color:#27ae60;font-weight:700">&#10003;</span><div><strong>Warehouse</strong> &mdash; для проверки подключения</div></div>'
        '<div style="display:flex;gap:.5rem;font-size:.9rem"><span style="color:#27ae60;font-weight:700">&#10003;</span><div><strong>Report</strong> &mdash; отчёты и статистика</div></div>'
        '<div style="display:flex;gap:.5rem;font-size:.9rem"><span style="color:#27ae60;font-weight:700">&#10003;</span><div><strong>Product</strong> &mdash; управление товарами и фото</div></div>'
        '</div></div>'
    )

    if cnt < MAX_API_KEYS:
        c += (
            '<form method="POST" action="/api-keys/add">'
            '<div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem">'
            '<div class="fg"><label>Название магазина</label>'
            '<input type="text" name="shop" class="fi" placeholder="Мой магазин" required maxlength="100" value="' + saved_shop + '">'
            '<div class="hn">Любое удобное название</div></div>'
            '<div class="fg"><label>Client ID</label>'
            '<input type="text" name="cid" class="fi" placeholder="123456789" required maxlength="50" value="' + saved_cid + '">'
            '<div class="hn">Числовой ID из личного кабинета</div></div>'
            '</div>'
            '<div class="fg">'
            '<label style="display:flex;justify-content:space-between">'
            '<span>API Key</span>'
            '<span onclick="togglePw(\'akey_field\', this)" '
            'style="font-size:.78rem;color:#aaa;cursor:pointer;user-select:none">показать</span>'
            '</label>'
            '<input type="password" id="akey_field" name="akey" class="fi" '
            'placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" required maxlength="200">'
            '<div class="hn">Хранится безопасно. Показываются только последние 4 символа</div>'
            '</div>'
            '<button class="btn bp">Проверить и сохранить</button>'
            '<span style="font-size:.85rem;color:#888;margin-left:1rem">Ключ будет проверен через API Озона</span>'
            '</form>'
        )
    else:
        c += alert(f'Достигнут лимит {MAX_API_KEYS} ключей на аккаунт', 'wn')

    c += '</div>'

    # ── Список ключей ──────────────────────────────────────────────────────
    c += f'<div class="box"><h2>Ваши подключения ({cnt} / {MAX_API_KEYS})</h2>'

    if keys:
        for k in keys:
            dot   = 'dg' if k['active'] else 'dr'
            badge = '<span class="bg g">Активен</span>' if k['active'] else '<span class="bg r">Ошибка</span>'
            c += (
                '<div class="kc"><div style="flex:1">'
                '<div class="kn">' + k['shop_name'] + '</div>'
                '<span class="ki">Client ID: ' + k['client_id'] + '</span>'
                '<span class="ki">API Key: ....' + k['hint'] + '</span>'
            )
            if k.get('check_msg'):
                c += '<div style="font-size:.8rem;color:#666;margin-top:.3rem">' + k['check_msg'] + '</div>'
            added = str(k['added_at'])[:10] if k.get('added_at') else '-'
            c += (
                '<div style="font-size:.8rem;color:#999;margin-top:.2rem">Добавлен: ' + added + '</div>'
                '</div>'
                '<div style="display:flex;align-items:center;gap:.5rem">'
                '<span class="dot ' + dot + '"></span>' + badge +
                '</div>'
                '<div style="display:flex;gap:.5rem">'
                '<a href="/api-keys/test/' + str(k['id']) + '" class="btn bs" style="background:#f0fdf4;color:#166534;border:1px solid #bbf7d0">&#128270; Проверить данные</a>'
                '<form method="POST" action="/api-keys/recheck/' + str(k['id']) + '">'
                '<button class="btn bs" style="background:#e8f4fd;color:#1e40af;border:1px solid #bfdbfe">&#128260; Перепроверить</button>'
                '</form>'
                '<form method="POST" action="/api-keys/del/' + str(k['id']) + '">'
                '<button class="btn bd bs" onclick="return confirm(\'Удалить?\')">Удалить</button>'
                '</form></div></div>'
            )
    else:
        c += '<div class="empty"><p style="font-size:2rem">&#128273;</p><p style="margin-top:1rem">Нет добавленных ключей</p></div>'

    c += '</div>'
    return render(c, 'keys')


@api_keys_bp.route('/api-keys/add', methods=['POST'])
def add_key():
    u = me()
    if not u:
        return redirect('/login')

    if db.count_keys(u['id']) >= MAX_API_KEYS:
        return redirect('/api-keys?err=Достигнут+лимит+ключей')

    shop = clean(request.form.get('shop', ''), 100)
    cid  = clean(request.form.get('cid',  ''), 50)
    akey = request.form.get('akey', '').strip()

    if not shop or not cid or not akey:
        return redirect(f'/api-keys?err=Заполните+все+поля&shop={shop}&cid={cid}')
    if not cid.isdigit():
        return redirect(f'/api-keys?err=Client+ID+должен+быть+числом&shop={shop}&cid={cid}')
    if len(akey) < 10:
        return redirect(f'/api-keys?err=API+Key+слишком+короткий&shop={shop}&cid={cid}')

    ok, msg = verify_ozon(cid, akey)
    db.add_key(u['id'], shop, cid, akey, akey[-4:], ok, msg)

    if ok:
        return redirect('/api-keys?msg=Магазин+' + shop + '+успешно+подключён')
    return redirect('/api-keys?err=Ключ+добавлен+но+проверка:+' + msg.replace(' ', '+'))


@api_keys_bp.route('/api-keys/recheck/<int:key_id>', methods=['POST'])
def recheck_key(key_id):
    u = me()
    if not u:
        return redirect('/login')
    keys = db.get_keys(u['id'])
    key = next((k for k in keys if k['id'] == key_id), None)
    if not key:
        return redirect('/api-keys?err=Ключ+не+найден')
    ok, msg = verify_ozon(key['client_id'], key['api_key'])
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                'UPDATE api_keys SET active=%s, check_msg=%s WHERE id=%s AND user_id=%s',
                (ok, msg, key_id, u['id'])
            )
        conn.commit()
    if ok:
        return redirect('/api-keys?msg=Ключ+успешно+проверен')
    return redirect('/api-keys?err=Проверка+не+прошла:+' + msg.replace(' ', '+'))


@api_keys_bp.route('/api-keys/test/<int:key_id>')
def test_key(key_id):
    u = me()
    if not u:
        return redirect('/login')

    keys = db.get_keys(u['id'])
    key = next((k for k in keys if k['id'] == key_id), None)
    if not key:
        return redirect('/api-keys?err=Ключ+не+найден')

    import requests as req
    from config import OZON_API_URL
    headers = {
        'Client-Id': key['client_id'],
        'Api-Key':   key['api_key'],
        'Content-Type': 'application/json'
    }

    results = []

    # 1. Список товаров
    try:
        r = req.post(f'{OZON_API_URL}/v2/product/list',
            headers=headers,
            json={'filter': {}, 'last_id': '', 'limit': 5},
            timeout=8)
        if r.status_code == 200:
            data = r.json()
            items = data.get('result', {}).get('items', [])
            results.append(('✅ Товары', f'Найдено товаров в выборке: {len(items)}. ID: ' + ', '.join(str(x.get("product_id","?")) for x in items[:5])))
        else:
            results.append(('⚠️ Товары', f'Статус {r.status_code}: {r.text[:200]}'))
    except Exception as e:
        results.append(('❌ Товары', str(e)[:200]))

    # 2. Информация о складах
    try:
        r = req.post(f'{OZON_API_URL}/v1/warehouse/list',
            headers=headers, json={}, timeout=8)
        if r.status_code == 200:
            wh = r.json().get('result', [])
            results.append(('✅ Склады', f'Найдено складов: {len(wh)}. ' + ', '.join(w.get("name","?") for w in wh[:3])))
        else:
            results.append(('⚠️ Склады', f'Статус {r.status_code}: {r.text[:200]}'))
    except Exception as e:
        results.append(('❌ Склады', str(e)[:200]))

    # 3. Аналитика (Report)
    try:
        from datetime import datetime, timedelta
        date_to = datetime.now().strftime('%Y-%m-%d')
        date_from = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        r = req.post(f'{OZON_API_URL}/v1/analytics/data',
            headers=headers,
            json={'date_from': date_from, 'date_to': date_to,
                  'metrics': ['revenue', 'ordered_units'],
                  'dimension': ['day'], 'limit': 7},
            timeout=8)
        if r.status_code == 200:
            rows = r.json().get('result', {}).get('data', [])
            results.append(('✅ Аналитика', f'Получено строк за 7 дней: {len(rows)}'))
        else:
            results.append(('⚠️ Аналитика', f'Статус {r.status_code}: {r.text[:200]}'))
    except Exception as e:
        results.append(('❌ Аналитика', str(e)[:200]))

    # Рендерим результаты
    rows_html = ''
    for icon_title, detail in results:
        color = '#d4edda' if '✅' in icon_title else '#fff3cd' if '⚠️' in icon_title else '#f8d7da'
        rows_html += (
            f'<div style="background:{color};border-radius:10px;padding:1rem;margin-bottom:.8rem">'
            f'<strong>{icon_title}</strong><br>'
            f'<span style="font-size:.9rem;color:#444;margin-top:.3rem;display:block">{detail}</span>'
            f'</div>'
        )

    from templates import render
    c = (
        f'<p class="ttl">&#128270; Тест подключения — {key["shop_name"]}</p>'
        '<div class="box">'
        f'<p style="margin-bottom:1.2rem;color:#666">Client ID: <strong>{key["client_id"]}</strong></p>'
        + rows_html +
        '<div style="margin-top:1.5rem">'
        '<a href="/api-keys" class="btn bp">&#8592; Назад к ключам</a>'
        '</div></div>'
    )
    return render(c, 'keys')


@api_keys_bp.route('/api-keys/del/<int:key_id>', methods=['POST'])
def delete_key(key_id):
    u = me()
    if not u:
        return redirect('/login')

    db.delete_key(key_id, u['id'])
    return redirect('/api-keys?msg=Подключение+удалено')
