"""
analytics.py — дашборд и аналитика Озон.
"""
from flask import Blueprint, redirect
from datetime import datetime, timedelta
import requests as req

import database as db
from templates import render, alert
from auth import me
from config import OZON_API_URL

analytics_bp = Blueprint('analytics', __name__)


def get_analytics(client_id, api_key, date_from, date_to):
    """Два раздельных запроса: трафик и продажи. Пауза между ними."""
    import time as _t
    h = {'Client-Id': client_id, 'Api-Key': api_key, 'Content-Type': 'application/json'}
    base = {'date_from': date_from, 'date_to': date_to, 'dimension': ['day'], 'limit': 1000}

    def fetch(metrics, retries=2):
        for attempt in range(retries):
            try:
                r = req.post(f'{OZON_API_URL}/v1/analytics/data', headers=h,
                    json={**base, 'metrics': metrics}, timeout=15)
                if r.status_code == 200:
                    return r.json().get('result', {}).get('data', [])
                if r.status_code == 429:
                    _t.sleep(3)
            except Exception:
                pass
        return []

    # Запрос 1: просмотры и клики
    rows_v = fetch(['hits_view_pdp', 'hits_tocart'])
    _t.sleep(1)  # обязательная пауза
    # Запрос 2: выручка и заказы
    rows_s = fetch(['revenue', 'ordered_units'])

    # Индексируем продажи по дате
    sales = {}
    for row in rows_s:
        d = (row.get('dimensions') or [{}])[0].get('id', '')[:10]
        m = row.get('metrics', [])
        sales[d] = {
            'revenue': float((m[0] or 0) if len(m) > 0 else 0),
            'orders':  int((m[1] or 0) if len(m) > 1 else 0),
        }

    # Собираем итоговые строки
    result = []
    if rows_v:
        for row in rows_v:
            d = (row.get('dimensions') or [{}])[0].get('id', '')[:10]
            m = row.get('metrics', [])
            s = sales.get(d, {'revenue': 0.0, 'orders': 0})
            result.append({
                'date':    d,
                'views':   int((m[0] or 0) if len(m) > 0 else 0),
                'clicks':  int((m[1] or 0) if len(m) > 1 else 0),
                'revenue': s['revenue'],
                'orders':  s['orders'],
            })
    elif rows_s:
        # Только продажи (трафик недоступен)
        for row in rows_s:
            d = (row.get('dimensions') or [{}])[0].get('id', '')[:10]
            m = row.get('metrics', [])
            result.append({
                'date': d, 'views': 0, 'clicks': 0,
                'revenue': float((m[0] or 0) if len(m) > 0 else 0),
                'orders':  int((m[1] or 0) if len(m) > 1 else 0),
            })
    return result

    # Объединяем по дате
    sales_by_date = {}
    for row in rows_sales:
        date = (row.get('dimensions') or [{}])[0].get('id', '')[:10]
        m = row.get('metrics', [])
        sales_by_date[date] = {
            'revenue': (m[0] or 0) if len(m) > 0 else 0,
            'orders':  (m[1] or 0) if len(m) > 1 else 0,
        }

    # Строим объединённые строки
    combined = []
    for row in rows_traffic:
        date = (row.get('dimensions') or [{}])[0].get('id', '')[:10]
        m = row.get('metrics', [])
        s = sales_by_date.get(date, {'revenue': 0, 'orders': 0})
        combined.append({
            'date': date,
            'views':   int((m[0] or 0) if len(m) > 0 else 0),
            'clicks':  int((m[1] or 0) if len(m) > 1 else 0),
            'revenue': float(s['revenue']),
            'orders':  int(s['orders']),
        })

    # Если трафика нет — берём только продажи
    if not combined and rows_sales:
        for row in rows_sales:
            date = (row.get('dimensions') or [{}])[0].get('id', '')[:10]
            m = row.get('metrics', [])
            combined.append({
                'date': date,
                'views': 0, 'clicks': 0,
                'revenue': float((m[0] or 0) if len(m) > 0 else 0),
                'orders':  int((m[1] or 0) if len(m) > 1 else 0),
            })

    return combined


def sum_metrics(rows, metric_count=4):
    """Суммировать метрики по списку строк (новый формат — dict)."""
    views = clicks = revenue = orders = 0
    for row in rows:
        views   += row.get('views',   0) or 0
        clicks  += row.get('clicks',  0) or 0
        revenue += row.get('revenue', 0) or 0
        orders  += row.get('orders',  0) or 0
    conv = round((orders / views * 100), 2) if views > 0 else 0
    return {
        'views':   int(views),
        'clicks':  int(clicks),
        'revenue': round(revenue, 0),
        'orders':  int(orders),
        'conv':    conv
    }


def format_strategy(s):
    """Человекочитаемое название стратегии из строки вида time:30m, views:100, clicks:20"""
    if not s:
        return 'По времени (30 мин)'
    if s.startswith('time:'):
        mins = s.split(':')[1].replace('m','')
        try:
            m = int(mins)
            if m < 60:   return f'По времени — каждые {m} мин'
            if m < 1440: return f'По времени — каждые {m//60} ч {m%60} мин'.replace(' 0 мин','')
            return f'По времени — каждые {m//1440} дн'
        except:
            return f'По времени ({mins} мин)'
    if s.startswith('views:'):
        return f'По показам — {s.split(":")[1]} показов'
    if s.startswith('clicks:'):
        return f'По кликам — {s.split(":")[1]} кликов'
    # Старые значения
    if s == 'round_robin': return 'Round Robin (равномерно)'
    if s == 'random':      return 'Случайная'
    if s == 'best_ctr':    return 'Лучший CTR'
    return s


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


# ── Отладочный маршрут ────────────────────────────────────────────────────
@analytics_bp.route('/debug-analytics')
def debug_analytics():
    u = me()
    if not u:
        return redirect('/login')
    keys = db.get_keys(u['id'])
    active_key = next((k for k in keys if k['active']), None)
    if not active_key:
        return 'Нет активных ключей'

    from datetime import datetime, timedelta
    today = datetime.now().date()
    date_from = str(today - timedelta(days=27))
    date_to   = str(today)

    import requests as req
    headers = {
        'Client-Id': active_key['client_id'],
        'Api-Key':   active_key['api_key'],
        'Content-Type': 'application/json'
    }

    results = []

    # Пробуем разные варианты метрик
    test_cases = [
        ['hits_view_pdp', 'hits_tocart', 'revenue', 'ordered_units'],
        ['hits_view', 'hits_tocart', 'revenue', 'ordered_units'],
        ['revenue', 'ordered_units'],
    ]

    for metrics in test_cases:
        r = req.post(
            f'{OZON_API_URL}/v1/analytics/data',
            headers=headers,
            json={
                'date_from': date_from,
                'date_to': date_to,
                'metrics': metrics,
                'dimension': ['day'],
                'limit': 7
            },
            timeout=10
        )
        data = r.json()
        rows = data.get('result', {}).get('data', [])
        # Суммируем первую метрику
        total = sum(row.get('metrics', [0])[0] or 0 for row in rows)
        results.append(f'Метрики {metrics}: статус={r.status_code}, строк={len(rows)}, сумма[0]={total}')

    # Проверяем новый формат get_analytics
    combined = get_analytics(active_key['client_id'], active_key['api_key'],
        str(today - timedelta(days=7)), str(today))
    results.append(f'get_analytics новый: строк={len(combined)}')
    if combined:
        results.append(f'Первая строка combined: {combined[0]}')
        total = sum_metrics(combined)
        results.append(f'Итого: views={total["views"]}, revenue={total["revenue"]}, orders={total["orders"]}')

    # Также проверим период
    r2 = req.post(
        f'{OZON_API_URL}/v1/analytics/data',
        headers=headers,
        json={
            'date_from': str(today - timedelta(days=7)),
            'date_to': str(today),
            'metrics': ['revenue', 'ordered_units'],
            'dimension': ['day'],
            'limit': 7
        },
        timeout=10
    )
    d2 = r2.json()
    rows2 = d2.get('result', {}).get('data', [])
    results.append(f'Последние 7 дней: статус={r2.status_code}, строк={len(rows2)}')
    if rows2:
        results.append(f'Первая строка: {rows2[0]}')

    return '<br>'.join(results)


# ── Дашборд ────────────────────────────────────────────────────────────────
@analytics_bp.route('/dashboard')
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
        wrows = [r for r in all_rows if wfrom <= r.get('date', '')[:10] <= wto]
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