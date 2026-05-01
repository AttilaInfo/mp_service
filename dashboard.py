from flask import Blueprint, redirect, request
from datetime import datetime, timedelta
import requests as req

import database as db
from templates import render, alert
from auth import me
from config import OZON_API_URL

dashboard_bp = Blueprint('dashboard', __name__)


def get_analytics(client_id, api_key, date_from, date_to):
    """Получить аналитику с Озона за период."""
    try:
        r = req.post(
            f'{OZON_API_URL}/v1/analytics/data',
            headers={
                'Client-Id': client_id,
                'Api-Key': api_key,
                'Content-Type': 'application/json'
            },
            json={
                'date_from': date_from,
                'date_to': date_to,
                'metrics': ['hits_view_pdp', 'hits_tocart', 'revenue', 'ordered_units'],
                'dimension': ['day'],
                'limit': 100
            },
            timeout=10
        )
        if r.status_code == 200:
            return r.json().get('result', {}).get('data', [])
        return []
    except Exception:
        return []


def sum_metrics(rows):
    """Суммировать метрики по списку строк."""
    views = clicks = revenue = orders = 0
    for row in rows:
        m = row.get('metrics', [])
        if len(m) >= 4:
            views   += m[0] or 0
            clicks  += m[1] or 0
            revenue += m[2] or 0
            orders  += m[3] or 0
    conv = round((orders / views * 100), 2) if views > 0 else 0
    return {
        'views':   int(views),
        'clicks':  int(clicks),
        'revenue': round(revenue, 0),
        'orders':  int(orders),
        'conv':    conv
    }


def fmt_num(n):
    """Форматировать число с пробелами: 12345 → 12 345"""
    return f'{int(n):,}'.replace(',', ' ')


def week_ranges(weeks=4):
    """Вернуть список (label, date_from, date_to) за последние N недель."""
    today = datetime.now().date()
    result = []
    for i in range(weeks - 1, -1, -1):
        end   = today - timedelta(days=i * 7)
        start = end - timedelta(days=6)
        label = f'{start.strftime("%d.%m")} – {end.strftime("%d.%m")}'
        result.append((label, str(start), str(end)))
    return result


# ── Дашборд ────────────────────────────────────────────────────────────────
@dashboard_bp.route('/dashboard')
def dashboard():
    u = me()
    if not u:
        return redirect('/login')

    kc   = db.count_keys(u['id'])
    keys = db.get_keys(u['id'])

    # Если нет ключей — показываем приветственный экран
    if kc == 0:
        c = (
            alert('Добавьте API ключи Озона чтобы начать. <a href="/api-keys" style="font-weight:700">Добавить</a>', 'wn') +
            '<p class="ttl">Привет, ' + u['name'] + '!</p>'
            '<div class="box" style="text-align:center;padding:3rem">'
            '<p style="font-size:3rem">&#128200;</p>'
            '<h2 style="margin:1rem 0">Подключите магазин чтобы видеть статистику</h2>'
            '<p style="color:#888;margin-bottom:1.5rem">После добавления API ключа здесь появятся реальные данные с Озона</p>'
            '<a href="/api-keys" class="btn bp">Добавить API ключ</a>'
            '</div>'
        )
        return render(c, 'dash')

    # Берём первый активный ключ
    active_key = next((k for k in keys if k['active']), keys[0])

    # Данные за 4 недели
    weeks = week_ranges(4)
    today = datetime.now().date()
    date_from_all = str(today - timedelta(days=27))
    date_to_all   = str(today)

    all_rows = get_analytics(active_key['client_id'], active_key['api_key'], date_from_all, date_to_all)

    # Суммарные метрики за 4 недели
    total = sum_metrics(all_rows)

    # Метрики по неделям
    weekly = []
    for label, wfrom, wto in weeks:
        wrows = [r for r in all_rows if wfrom <= r.get('dimensions', [{}])[0].get('id', '')[:10] <= wto]
        weekly.append({'label': label, **sum_metrics(wrows)})

    # ── Карточки метрик ────────────────────────────────────────────────────
    c = '<p class="ttl">Привет, ' + u['name'] + '! <span style="font-size:1rem;color:#888;font-weight:400">Статистика за 4 недели</span></p>'

    c += '<div class="cards">'
    c += '<div class="card"><div class="ic">&#128065;</div><div><div class="n">' + fmt_num(total['views']) + '</div><div class="lb">Просмотров</div></div></div>'
    c += '<div class="card"><div class="ic">&#128717;</div><div><div class="n">' + fmt_num(total['clicks']) + '</div><div class="lb">Кликов в корзину</div></div></div>'
    c += '<div class="card"><div class="ic">&#128176;</div><div><div class="n">' + fmt_num(total['revenue']) + ' ₽</div><div class="lb">Выручка</div></div></div>'
    c += '<div class="card"><div class="ic">&#128200;</div><div><div class="n">' + str(total['conv']) + '%</div><div class="lb">Конверсия</div></div></div>'
    c += '</div>'

    # ── Таблица по неделям ─────────────────────────────────────────────────
    c += '<div class="box"><h2>&#128197; Статистика по неделям</h2>'
    c += '<div style="overflow-x:auto"><table>'
    c += '<tr><th>Неделя</th><th>Просмотры</th><th>Клики в корзину</th><th>Выручка</th><th>Заказы</th><th>Конверсия</th></tr>'

    prev = None
    for w in weekly:
        # Стрелки изменений относительно предыдущей недели
        def arrow(curr, p, key):
            if p is None: return ''
            diff = curr[key] - p[key]
            if diff > 0: return ' <span style="color:#27ae60;font-size:.8rem">▲</span>'
            if diff < 0: return ' <span style="color:#e74c3c;font-size:.8rem">▼</span>'
            return ''

        c += (
            '<tr>'
            '<td style="font-weight:600">' + w['label'] + '</td>'
            '<td>' + fmt_num(w['views'])   + arrow(w, prev, 'views')   + '</td>'
            '<td>' + fmt_num(w['clicks'])  + arrow(w, prev, 'clicks')  + '</td>'
            '<td>' + fmt_num(w['revenue']) + ' ₽' + arrow(w, prev, 'revenue') + '</td>'
            '<td>' + fmt_num(w['orders'])  + arrow(w, prev, 'orders')  + '</td>'
            '<td>' + str(w['conv']) + '%'  + arrow(w, prev, 'conv')    + '</td>'
            '</tr>'
        )
        prev = w

    c += '</table></div></div>'

    # ── Магазин ────────────────────────────────────────────────────────────
    c += (
        '<div class="box"><h2>&#128273; Активное подключение</h2>'
        '<div style="display:flex;align-items:center;gap:1rem;flex-wrap:wrap">'
        '<div><strong>' + active_key['shop_name'] + '</strong>'
        '<div style="font-size:.85rem;color:#888;margin-top:.3rem">Client ID: ' + active_key['client_id'] + '</div></div>'
        '<span class="bg g" style="margin-left:auto">&#9679; Активен</span>'
        '<a href="/api-keys" class="btn bp" style="padding:.5rem 1rem;font-size:.85rem">Управление</a>'
        '</div></div>'
    )

    c += '<div class="tip">&#128161; <strong>Совет:</strong> Для достоверных A/B тестов нужно минимум 100 просмотров и 7 дней на каждый вариант.</div>'

    return render(c, 'dash')


# ── Тесты ──────────────────────────────────────────────────────────────────
@dashboard_bp.route('/tests')
def tests():
    u = me()
    if not u:
        return redirect('/login')

    keys = db.get_keys(u['id'])
    active_key = next((k for k in keys if k['active']), None)

    # Список тестов из БД
    user_tests = db.get_tests(u['id'])

    c = '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1.5rem">'
    c += '<p class="ttl" style="margin:0">&#129514; Мои тесты</p>'
    if active_key:
        c += '<a href="/tests/new" class="btn bp">&#43; Создать тест</a>'
    c += '</div>'

    if not active_key:
        c += alert('Сначала добавьте API ключ Озона чтобы создавать тесты. <a href="/api-keys" style="font-weight:700">Добавить</a>', 'wn')

    if user_tests:
        c += '<div class="box"><table>'
        c += '<tr><th>Товар</th><th>Магазин</th><th>Вариантов</th><th>Статус</th><th>Создан</th><th></th></tr>'
        for t in user_tests:
            status_badge = '<span class="bg g">Активен</span>' if t['status'] == 'running' else '<span class="bg r">Завершён</span>'
            c += (
                '<tr>'
                '<td><strong>' + t['product_name'] + '</strong><br><small style="color:#999">SKU: ' + t['sku'] + '</small></td>'
                '<td>' + t['shop_name'] + '</td>'
                '<td style="text-align:center">' + str(t.get('variant_count', 0)) + '</td>'
                '<td>' + status_badge + '</td>'
                '<td>' + str(t['created_at'])[:10] + '</td>'
                '<td><a href="/tests/' + str(t['id']) + '" class="btn bp" style="padding:.4rem .9rem;font-size:.82rem">Подробнее</a></td>'
                '</tr>'
            )
        c += '</table></div>'
    else:
        c += (
            '<div class="box"><div class="empty">'
            '<p style="font-size:2rem">&#129514;</p>'
            '<p style="margin-top:1rem;font-weight:600">Тестов пока нет</p>'
            '<p style="font-size:.9rem;margin-top:.5rem;color:#aaa">Создайте первый тест чтобы начать оптимизацию фото</p>'
            + ('<a href="/tests/new" class="btn bp" style="margin-top:1.5rem">Создать первый тест</a>' if active_key else '') +
            '</div></div>'
        )

    return render(c, 'tests')


# ── Создание теста ─────────────────────────────────────────────────────────
@dashboard_bp.route('/tests/new')
def new_test():
    u = me()
    if not u:
        return redirect('/login')

    keys = db.get_keys(u['id'])
    active_keys = [k for k in keys if k['active']]
    if not active_keys:
        return redirect('/tests')

    err = request.args.get('err', '')

    # Загружаем товары с Озона для первого активного ключа
    key = active_keys[0]
    products = []
    try:
        r = req.post(
            f'{OZON_API_URL}/v3/product/list',
            headers={'Client-Id': key['client_id'], 'Api-Key': key['api_key'], 'Content-Type': 'application/json'},
            json={'filter': {}, 'last_id': '', 'limit': 100},
            timeout=10
        )
        if r.status_code == 200:
            items = r.json().get('result', {}).get('items', [])
            if items:
                # Получаем детали товаров
                ids = [str(x['product_id']) for x in items[:50]]
                r2 = req.post(
                    f'{OZON_API_URL}/v2/product/info/list',
                    headers={'Client-Id': key['client_id'], 'Api-Key': key['api_key'], 'Content-Type': 'application/json'},
                    json={'product_id': [int(x) for x in ids]},
                    timeout=10
                )
                if r2.status_code == 200:
                    products = r2.json().get('result', {}).get('items', [])
    except Exception:
        pass

    # Строим список магазинов
    shops_opts = ''.join(
        f'<option value="{k["id"]}">{k["shop_name"]} (ID: {k["client_id"]})</option>'
        for k in active_keys
    )

    # Строим список товаров
    if products:
        prod_opts = ''.join(
            '<option value="{sku}|{name}">{name} (SKU: {sku})</option>'.format(
                sku=p.get('offer_id', ''),
                name=p.get('name', 'Без названия')[:60]
            )
            for p in products
        )
        prod_select = f'<select name="product" class="fi" required>{prod_opts}</select>'
        prod_hint   = f'Загружено {len(products)} товаров из Озона'
    else:
        prod_select = '<input type="text" name="product" class="fi" placeholder="SKU|Название товара" required>'
        prod_hint   = 'Не удалось загрузить товары — введите вручную в формате SKU|Название'

    c = (
        '<div style="display:flex;align-items:center;gap:1rem;margin-bottom:1.5rem">'
        '<a href="/tests" class="btn" style="background:#f0f2f5;border:1px solid #ddd;color:#444">&#8592; Назад</a>'
        '<p class="ttl" style="margin:0">&#43; Новый A/B тест</p>'
        '</div>'
        + (alert(err, 'er') if err else '') +
        '<div class="box">'
        '<form method="POST" action="/tests/create" enctype="multipart/form-data">'

        '<div class="fg"><label>Магазин</label>'
        f'<select name="key_id" class="fi" required>{shops_opts}</select></div>'

        '<div class="fg"><label>Товар</label>'
        + prod_select +
        f'<div class="hn">{prod_hint}</div></div>'

        '<div class="fg"><label>Количество вариантов фото <span style="color:#667eea">(от 2 до 10)</span></label>'
        '<select name="variant_count" class="fi" id="vc_select">'
        + ''.join(f'<option value="{i}">{i} варианта</option>' if i <= 4 else f'<option value="{i}">{i} вариантов</option>' for i in range(2, 11)) +
        '</select></div>'

        '<div id="variants_wrap"></div>'

        '<div class="fg"><label>Стратегия ротации</label>'
        '<select name="strategy" class="fi">'
        '<option value="round_robin">По очереди (Round Robin) — равномерно</option>'
        '<option value="random">Случайная</option>'
        '<option value="best_ctr">Лучший CTR — больше показов победителю</option>'
        '</select>'
        '<div class="hn">Round Robin рекомендуется для новых тестов</div></div>'

        '<button class="btn bp" style="width:100%">&#129514; Запустить тест</button>'
        '</form></div>'

        '<script>'
        'function updateVariants() {'
        '  var n = parseInt(document.getElementById("vc_select").value);'
        '  var wrap = document.getElementById("variants_wrap");'
        '  var html = "";'
        '  for (var i = 1; i <= n; i++) {'
        '    html += "<div class=\\"fg\\"><label>Вариант " + String.fromCharCode(64+i) + " — URL фото</label>"'
        '         + "<input type=\\"url\\" name=\\"photo_" + i + "\\" class=\\"fi\\" placeholder=\\"https://...\\" required>"'
        '         + "<div class=\\"hn\\">Ссылка на фото (JPEG/PNG)</div></div>";'
        '  }'
        '  wrap.innerHTML = html;'
        '}'
        'document.getElementById("vc_select").addEventListener("change", updateVariants);'
        'updateVariants();'
        '</script>'
    )
    return render(c, 'tests')


@dashboard_bp.route('/tests/create', methods=['POST'])
def create_test():
    u = me()
    if not u:
        return redirect('/login')

    key_id        = request.form.get('key_id')
    product_raw   = request.form.get('product', '')
    strategy      = request.form.get('strategy', 'round_robin')
    variant_count = int(request.form.get('variant_count', 2))

    # Парсим товар
    if '|' in product_raw:
        sku, product_name = product_raw.split('|', 1)
    else:
        sku = product_raw
        product_name = product_raw

    if not sku or not product_name:
        return redirect('/tests/new?err=Выберите+товар')

    # Получаем ключ
    keys = db.get_keys(u['id'])
    key = next((k for k in keys if str(k['id']) == str(key_id)), None)
    if not key:
        return redirect('/tests/new?err=Магазин+не+найден')

    # Собираем варианты
    variants = []
    for i in range(1, variant_count + 1):
        photo = request.form.get(f'photo_{i}', '').strip()
        if not photo:
            return redirect(f'/tests/new?err=Заполните+URL+фото+для+варианта+{chr(64+i)}')
        variants.append({'label': chr(64 + i), 'photo_url': photo})

    # Сохраняем в БД
    test_id = db.create_test(u['id'], key['shop_name'], sku, product_name, strategy)
    for v in variants:
        db.add_variant(test_id, v['label'], v['photo_url'])

    return redirect(f'/tests/{test_id}')


@dashboard_bp.route('/tests/<int:test_id>')
def test_detail(test_id):
    u = me()
    if not u:
        return redirect('/login')

    test = db.get_test(test_id, u['id'])
    if not test:
        return redirect('/tests')

    variants = db.get_variants(test_id)

    status_badge = '<span class="bg g">&#9679; Активен</span>' if test['status'] == 'running' else '<span class="bg r">Завершён</span>'

    c = (
        '<div style="display:flex;align-items:center;gap:1rem;margin-bottom:1.5rem">'
        '<a href="/tests" class="btn" style="background:#f0f2f5;border:1px solid #ddd;color:#444">&#8592; Назад</a>'
        '<p class="ttl" style="margin:0">' + test['product_name'] + '</p>'
        + status_badge +
        '</div>'
    )

    c += (
        '<div class="box">'
        '<table style="width:auto;margin-bottom:1rem">'
        '<tr><td style="color:#666;padding:.4rem 2rem .4rem 0">SKU:</td><td><strong>' + test['sku'] + '</strong></td></tr>'
        '<tr><td style="color:#666;padding:.4rem 2rem .4rem 0">Магазин:</td><td><strong>' + test['shop_name'] + '</strong></td></tr>'
        '<tr><td style="color:#666;padding:.4rem 2rem .4rem 0">Стратегия:</td><td><strong>' + test['strategy'] + '</strong></td></tr>'
        '<tr><td style="color:#666;padding:.4rem 2rem .4rem 0">Создан:</td><td><strong>' + str(test['created_at'])[:10] + '</strong></td></tr>'
        '</table>'

        '<h2 style="margin-bottom:1rem">Варианты фото (' + str(len(variants)) + ')</h2>'
        '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:1rem">'
    )

    for v in variants:
        winner_style = 'border:3px solid #27ae60;' if test.get('winner') == v['label'] else ''
        c += (
            '<div style="background:#f8f9fa;border-radius:12px;padding:1rem;text-align:center;' + winner_style + '">'
            '<div style="font-size:2rem;font-weight:700;color:#667eea">&#127919; ' + v['label'] + '</div>'
            '<div style="font-size:.8rem;color:#888;margin:.5rem 0;word-break:break-all">' + v['photo_url'][:50] + '...</div>'
            '<div style="display:grid;grid-template-columns:1fr 1fr;gap:.3rem;font-size:.82rem;margin-top:.5rem">'
            '<div style="background:#e8f4fd;padding:.3rem;border-radius:4px">&#128065; ' + str(v['views']) + '</div>'
            '<div style="background:#d4edda;padding:.3rem;border-radius:4px">&#128717; ' + str(v['clicks']) + '</div>'
            '</div>'
            + ('<div style="margin-top:.5rem;color:#27ae60;font-weight:700">&#127942; Победитель!</div>' if test.get('winner') == v['label'] else '') +
            '</div>'
        )

    c += '</div></div>'

    if test['status'] == 'running':
        c += (
            '<form method="POST" action="/tests/' + str(test_id) + '/stop">'
            '<button class="btn bd" onclick="return confirm(\'Завершить тест?\')">&#9209; Завершить тест</button>'
            '</form>'
        )

    return render(c, 'tests')


@dashboard_bp.route('/tests/<int:test_id>/stop', methods=['POST'])
def stop_test(test_id):
    u = me()
    if not u:
        return redirect('/login')
    db.finish_test(test_id, u['id'])
    return redirect(f'/tests/{test_id}')


@dashboard_bp.route('/settings')
def settings():
    u = me()
    if not u:
        return redirect('/login')
    kc = db.count_keys(u['id'])
    c = (
        '<p class="ttl">&#9881; Настройки</p>'
        '<div class="box"><h2>&#128100; Профиль</h2>'
        '<table style="width:auto">'
        '<tr><td style="color:#666;padding:.5rem 2rem .5rem 0">Имя:</td><td><strong>' + u['name'] + '</strong></td></tr>'
        '<tr><td style="color:#666;padding:.5rem 2rem .5rem 0">Email:</td><td><strong>' + u['email'] + '</strong></td></tr>'
        '<tr><td style="color:#666;padding:.5rem 2rem .5rem 0">API ключей:</td><td><strong>' + str(kc) + '</strong></td></tr>'
        '<tr><td style="color:#666;padding:.5rem 2rem .5rem 0">Аккаунт создан:</td><td><strong>' + str(u['created_at'])[:10] + '</strong></td></tr>'
        '</table></div>'
    )
    return render(c, 'cfg')
