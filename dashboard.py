from flask import Blueprint, redirect, request
from datetime import datetime, timedelta
import requests as req

import database as db
from templates import render, alert
from auth import me
from config import OZON_API_URL

dashboard_bp = Blueprint('dashboard', __name__)


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
@dashboard_bp.route('/debug-analytics')
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
@dashboard_bp.route('/static/variants.js')
def variants_js():
    from flask import Response
    return Response(r"""
var variantCount = 0;
var MAX_VARIANTS = 10;
var currentFiles = [];

function patchSelectProduct() {
  if (typeof window.selectProduct !== 'function') {
    setTimeout(patchSelectProduct, 100);
    return;
  }
  var orig = window.selectProduct;
  window.selectProduct = function(sku, name, img) {
    orig(sku, name, img);
    var imgField = document.getElementById('product_img');
    if (imgField) imgField.value = img || '';
    if (variantCount === 0) {
      addVariantWithUrl(img || '', 'текущее фото', true);
    } else {
      var prev = document.getElementById('preview_1');
      if (prev && img) prev.innerHTML = '<img src="' + img + '" style="width:100%;height:100%;object-fit:cover">';
      var inp = document.querySelector('input[name="photo_1"]');
      if (inp) inp.value = img || '';
    }
  };
}
patchSelectProduct();

function triggerFileInput() {
  if (variantCount >= MAX_VARIANTS) return;
  var fi = document.getElementById('file_inp');
  if (fi) { fi.value = ''; fi.click(); }
}

function addVariantWithUrl(url, hint, isFirst) {
  if (variantCount >= MAX_VARIANTS) return;
  variantCount++;
  var label = String(variantCount);
  var grid = document.getElementById('variants_grid');
  if (!grid) return;
  var card = document.createElement('div');
  card.id = 'variant_card_' + variantCount;
  card.setAttribute('data-num', variantCount);
  card.style.cssText = 'border-radius:10px;overflow:hidden;background:#fff;position:relative';
  var headerBg = isFirst ? '#27ae60' : '#667eea';
  var delBtn = variantCount > 1
    ? '<button type="button" onclick="removeVariant(this)" style="background:none;border:none;color:rgba(255,255,255,.8);cursor:pointer;font-size:1.2rem;padding:0;line-height:1">&times;</button>'
    : '';
  var previewHtml = url
    ? '<img src="' + url + '" style="width:100%;height:100%;object-fit:cover" onerror="this.parentElement.innerHTML=String.fromCodePoint(128247)">'
    : '<span style="font-size:2.5rem">&#128247;</span>';
  card.innerHTML =
    '<div style="background:' + headerBg + ';color:#fff;padding:.35rem .7rem;font-size:.82rem;font-weight:700;display:flex;justify-content:space-between;align-items:center">'
    + '<span>' + label + (isFirst ? ' — текущее' : '') + '</span>' + delBtn + '</div>'
    + '<div id="preview_' + variantCount + '" style="width:100%;aspect-ratio:3/4;background:#f0f2f5;overflow:hidden;display:flex;align-items:center;justify-content:center">'
    + previewHtml + '</div>'
    + '<input type="url" name="photo_' + variantCount + '" value="' + (url || '') + '" class="fi" placeholder="https://..." required style="display:none">';
  grid.appendChild(card);
  updateCountLabel();
}

function removeVariant(btn) {
  var card = btn.closest('[data-num]');
  if (card) { card.remove(); updateCountLabel(); }
}

function updateCountLabel() {
  var grid = document.getElementById('variants_grid');
  var cards = grid.children;
  var n = cards.length;
  variantCount = n;

  for (var i = 0; i < cards.length; i++) {
    var card = cards[i];
    var isFirst = (i === 0);
    var num = i + 1;
    card.setAttribute('data-num', num);
    var header = card.querySelector('div[style*="background:"]');
    if (header) {
      var delBtn = isFirst ? '' : '<button type="button" onclick="removeVariant(this)" style="background:none;border:none;color:rgba(255,255,255,.8);cursor:pointer;font-size:1.2rem;padding:0;line-height:1">×</button>';
      header.style.background = isFirst ? '#27ae60' : '#667eea';
      header.innerHTML = '<span>' + num + (isFirst ? ' — текущее' : '') + '</span>' + delBtn;
    }
    var inp = card.querySelector('input[type="url"]');
    if (inp) inp.name = 'photo_' + num;
  }

  var lbl = document.getElementById('variant_count_label');
  if (lbl) lbl.textContent = 'Добавлено: ' + n + ' из ' + MAX_VARIANTS;
  var b = document.getElementById('add_variant_btn');
  if (b) b.style.opacity = n >= MAX_VARIANTS ? '.4' : '1';
  var notice = document.getElementById('files_notice');
  if (notice) notice.textContent = '';
}

function handleFiles(files) {
  if (!files || !files.length) return;
  var available = MAX_VARIANTS - variantCount;
  if (available <= 0) return;
  var toAdd = Math.min(files.length, available);
  var skipped = files.length - toAdd;
  var notice = document.getElementById('files_notice');

  if (skipped > 0 && notice) {
    notice.innerHTML = '<span style="color:#e67e22">⚠️ Добавлено ' + toAdd + ' из ' + files.length + ' фото (лимит 10 вариантов)</span>';
  }

  for (var i = 0; i < toAdd; i++) {
    (function(file) {
      var reader = new FileReader();
      reader.onload = function(e) {
        addVariantWithUrl(e.target.result, '', false);
      };
      reader.readAsDataURL(file);
    })(files[i]);
  }
}

function handleDrop(e) {
  e.preventDefault();
  handleFiles(e.dataTransfer.files);
}

    """, mimetype='application/javascript')


@dashboard_bp.route('/static/product-search.js')
def product_search_js():
    from flask import Response
    js = r"""
var ALL_PRODUCTS = [];
var LOADED = false;

function loadProducts(callback) {
  if (LOADED) {
    if (callback) callback();
    return;
  }
  var loading = document.getElementById('prod_loading');
  if (loading) loading.style.display = 'block';
  var srch = document.getElementById('prod_search');
  if (srch) srch.placeholder = 'Загружаем товары...';
  fetch('/api/products')
    .then(function(r){ return r.json(); })
    .then(function(data){
      ALL_PRODUCTS = Array.isArray(data) ? data : [];
      LOADED = true;
      if (loading) loading.style.display = 'none';
      if (srch) srch.placeholder = 'Начните вводить название или артикул...';
      var hint = document.getElementById('prod_hint_text');
      if (hint) hint.textContent = 'Загружено ' + ALL_PRODUCTS.length + ' товаров с остатками';
      if (callback) callback();
      else renderDropdown(srch ? srch.value : '');
    }).catch(function(){
      if (loading) loading.style.display = 'none';
      if (srch) srch.placeholder = 'Ошибка загрузки. Введите артикул и нажмите Найти';
    });
}

function renderDropdown(q) {
  var dd = document.getElementById('prod_dropdown');
  if (!dd) return;
  var list = ALL_PRODUCTS;
  if (q) {
    var ql = q.toLowerCase();
    list = list.filter(function(p){
      return (p.sku  && p.sku.toLowerCase().indexOf(ql)     >= 0)
          || (p.ozon_id && p.ozon_id.indexOf(ql)            >= 0)
          || (p.name && p.name.toLowerCase().indexOf(ql)    >= 0);
    });
  }
  if (!list.length) {
    dd.innerHTML = '<div style="padding:1rem;color:#888;text-align:center">Ничего не найдено. Введите артикул и нажмите «Найти».</div>';
    dd.style.display = 'block';
    return;
  }
  var show = list.slice(0, 30);
  dd.innerHTML = show.map(function(p){
    var img_html = p.img
      ? '<img src="' + p.img + '" style="width:52px;height:52px;object-fit:cover;border-radius:6px;flex-shrink:0">'
      : '<div style="width:52px;height:52px;background:#f0f2f5;border-radius:6px;display:flex;align-items:center;justify-content:center;flex-shrink:0;color:#ccc;font-size:1.2rem">&#128247;</div>';
    var safe_name = p.name.replace(/\\/g,'\\\\').replace(/'/g,"\\'");
    var safe_img  = (p.img||'').replace(/'/g,"\\'");
    return '<div onclick="selectProduct(\'' + p.sku + '\',\'' + safe_name + '\',\'' + safe_img + '\')"'
      + ' style="display:flex;align-items:center;gap:.85rem;padding:.75rem 1rem;cursor:pointer;border-bottom:1px solid #f5f5f5"'
      + ' onmouseover="this.style.background=\'#f8f9fa\'" onmouseout="this.style.background=\'\'">'
      + img_html
      + '<div style="min-width:0">'
      + '<div style="font-size:.9rem;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:360px">' + p.name + '</div>'
      + '<div style="font-size:.78rem;color:#888;margin-top:.15rem">'
      + (p.sku ? 'Арт: ' + p.sku : '')
      + (p.ozon_id ? ' &nbsp;·&nbsp; ID: ' + p.ozon_id : '')
      + '</div>'
      + '</div></div>';
  }).join('')
  + (list.length > 30 ? '<div style="padding:.7rem;color:#888;text-align:center;font-size:.85rem">...ещё ' + (list.length-30) + ' товаров. Уточните запрос.</div>' : '');
  dd.style.display = 'block';
}

function selectProduct(sku, name, img) {
  document.getElementById('product_val').value = sku + '|' + name;
  document.getElementById('prod_search').value = '';
  document.getElementById('prod_dropdown').style.display = 'none';
  var img_tag = img ? '<img src="' + img + '" style="width:52px;height:52px;object-fit:cover;border-radius:6px">' : '';
  var sel = document.getElementById('prod_selected');
  sel.innerHTML = img_tag
    + '<div><div style="font-weight:600;font-size:.95rem">' + name + '</div>'
    + '<div style="font-size:.82rem;color:#666;margin-top:.2rem">Артикул: ' + sku + '</div>'
    + '<div style="font-size:.78rem;color:#27ae60;margin-top:.2rem">&#10003; Выбран для теста</div></div>'
    + '<button type="button" onclick="clearProduct()" style="margin-left:auto;background:none;border:none;color:#aaa;cursor:pointer;font-size:1.4rem">&times;</button>';
  sel.style.display = 'flex';
  document.getElementById('sku_result').innerHTML = '';
}

function toggleSkuSearch() {
  var wrap = document.getElementById('sku_search_wrap');
  if (!wrap) return;
  wrap.style.display = wrap.style.display === 'none' || wrap.style.display === '' ? 'block' : 'none';
  if (wrap.style.display === 'block') {
    var inp = document.getElementById('sku_manual');
    if (inp) inp.focus();
  }
}
function clearSearch() {
  var srch = document.getElementById('prod_search');
  srch.value = '';
  document.getElementById('prod_clear').style.display = 'none';
  document.getElementById('prod_dropdown').style.display = 'none';
  srch.focus();
}
function clearProduct() {
  document.getElementById('product_val').value = '';
  document.getElementById('prod_selected').style.display = 'none';
  document.getElementById('prod_search').focus();
}

function checkBySku() {
  var manualInp = document.getElementById('sku_manual');
  var sku = (manualInp ? manualInp.value : document.getElementById('prod_search').value).trim();
  if (!sku) return;
  var res = document.getElementById('sku_result');
  res.innerHTML = '&#128269; Проверяем...';
  fetch('/api/check-sku?sku=' + encodeURIComponent(sku))
    .then(function(r){ return r.json(); })
    .then(function(d){
      if (d.found && d.has_stock) {
        selectProduct(d.sku, d.name, '');
        res.innerHTML = '<span style="color:#27ae60">&#10003; Товар найден и выбран</span>';
      } else if (d.found && !d.has_stock) {
        res.innerHTML = '<span style="color:#e67e22">&#9888; Товар найден, но нет остатков. Пополните остатки на FBS — тогда он появится в списке.</span>';
      } else {
        res.innerHTML = '<span style="color:#e74c3c">&#10007; Товар с таким артикулом не найден</span>';
      }
    }).catch(function(){ res.innerHTML = 'Ошибка проверки'; });
}

document.addEventListener('DOMContentLoaded', function(){
  var srch = document.getElementById('prod_search');
  if (!srch) return;
  srch.addEventListener('focus', function(){
    var self = this;
    loadProducts(function(){ renderDropdown(self.value); });
  });
  srch.addEventListener('input', function(){
    var clr = document.getElementById('prod_clear');
    if (clr) clr.style.display = this.value ? 'block' : 'none';
    renderDropdown(this.value);
  });
  document.addEventListener('click', function(e){
    var dd = document.getElementById('prod_dropdown');
    if (dd && !srch.contains(e.target) && !dd.contains(e.target)) {
      dd.style.display = 'none';
    }
  });
});

    """
    return Response(js, mimetype='application/javascript')


@dashboard_bp.route('/api/products')
def api_products():
    """Загрузка товаров с остатками для формы создания теста."""
    from flask import jsonify
    u = me()
    if not u:
        return jsonify([])
    keys = db.get_keys(u['id'])
    key  = next((k for k in keys if k['active']), None)
    if not key:
        return jsonify([])

    hk = {'Client-Id': key['client_id'], 'Api-Key': key['api_key'], 'Content-Type': 'application/json'}
    all_items = []
    last_id = ''
    import time as _t
    try:
        # Шаг 1: получаем ID товаров в продаже
        while len(all_items) < 2000:
            r = req.post(f'{OZON_API_URL}/v3/product/list', headers=hk,
                json={'filter': {'visibility': 'IN_SALE'}, 'last_id': last_id, 'limit': 1000},
                timeout=15)
            if r.status_code != 200:
                break
            result = r.json().get('result', {})
            items  = result.get('items', [])
            all_items.extend(items)
            last_id = result.get('last_id', '')
            if not last_id or len(items) < 1000:
                break
            _t.sleep(0.3)

        if not all_items:
            return jsonify([])

        # Шаг 2: получаем детали пачками по 100
        products = []
        for i in range(0, min(len(all_items), 2000), 100):
            batch = all_items[i:i+100]
            r2 = req.post(f'{OZON_API_URL}/v3/product/info/list', headers=hk,
                json={'product_id': [int(x['product_id']) for x in batch]}, timeout=15)
            if r2.status_code == 200:
                resp   = r2.json()
                items2 = (resp.get('result') or {}).get('items') or resp.get('items') or []
                for p in items2:
                    sku     = p.get('offer_id', '')
                    ozon_id = str(p.get('id') or p.get('product_id', ''))
                    name    = p.get('name', '')[:80]
                    if not name:
                        continue
                    # primary_image — массив с главным фото
                    img = ''
                    primary = p.get('primary_image', [])
                    if isinstance(primary, list) and primary:
                        img = primary[0]
                    elif isinstance(primary, str) and primary.startswith('http'):
                        img = primary
                    # Если primary_image пустой — берём первое из images
                    if not img:
                        imgs = p.get('images', [])
                        if isinstance(imgs, list) and imgs:
                            img = imgs[0] if isinstance(imgs[0], str) else ''
                    products.append({'sku': sku, 'ozon_id': ozon_id, 'name': name, 'img': img})
            _t.sleep(0.2)

        return jsonify(products)
    except Exception as e:
        return jsonify([])

@dashboard_bp.route('/api/debug-product')
def debug_product():
    from flask import jsonify
    u = me()
    if not u:
        return jsonify({})
    keys = db.get_keys(u['id'])
    key = next((k for k in keys if k['active']), None)
    if not key:
        return jsonify({})
    hk = {'Client-Id': key['client_id'], 'Api-Key': key['api_key'], 'Content-Type': 'application/json'}
    # Берём первый товар
    r = req.post(f'{OZON_API_URL}/v3/product/list', headers=hk,
        json={'filter': {'visibility': 'IN_SALE'}, 'last_id': '', 'limit': 1}, timeout=10)
    if r.status_code != 200:
        return jsonify({'error': r.status_code})
    items = r.json().get('result', {}).get('items', [])
    if not items:
        return jsonify({'error': 'no items'})
    pid = items[0]['product_id']
    r2 = req.post(f'{OZON_API_URL}/v3/product/info/list', headers=hk,
        json={'product_id': [pid]}, timeout=10)
    if r2.status_code != 200:
        return jsonify({'error': r2.status_code})
    resp = r2.json()
    p = ((resp.get('result') or {}).get('items') or resp.get('items') or [{}])[0]
    # Возвращаем все поля связанные с картинками
    return jsonify({
        'primary_image':  p.get('primary_image'),
        'images':         p.get('images'),
        'images360':      p.get('images360'),
        'color_image':    p.get('color_image'),
        'all_keys':       [k for k in p.keys() if 'image' in k.lower() or 'photo' in k.lower() or 'pic' in k.lower()],
    })


@dashboard_bp.route('/api/check-sku')
def check_sku():
    """Проверяет артикул через API Озона — есть ли товар и есть ли остатки."""
    from flask import jsonify
    u = me()
    if not u:
        return jsonify({'found': False})
    sku = request.args.get('sku', '').strip()
    if not sku:
        return jsonify({'found': False})
    keys = db.get_keys(u['id'])
    key  = next((k for k in keys if k['active']), None)
    if not key:
        return jsonify({'found': False})

    hk = {'Client-Id': key['client_id'], 'Api-Key': key['api_key'], 'Content-Type': 'application/json'}
    items = []
    try:
        # Ищем по offer_id (артикул продавца: подарок_роза, AL_SKB_44 и т.д.)
        r = req.post(f'{OZON_API_URL}/v3/product/info/list', headers=hk,
            json={'offer_id': [sku]}, timeout=10)
        if r.status_code == 200:
            resp  = r.json()
            items = (resp.get('result') or {}).get('items') or resp.get('items') or []

        # Если не нашли по offer_id — пробуем как числовой product_id
        if not items and sku.isdigit():
            r2 = req.post(f'{OZON_API_URL}/v3/product/info/list', headers=hk,
                json={'product_id': [int(sku)]}, timeout=10)
            if r2.status_code == 200:
                resp2 = r2.json()
                items = (resp2.get('result') or {}).get('items') or resp2.get('items') or []

        if items:
            p        = items[0]
            name     = p.get('name', sku)[:80]
            offer_id = p.get('offer_id', sku)
            pid      = p.get('id') or p.get('product_id', 0)

            # Проверяем остатки
            has_stock = False
            stock_val = 0
            if pid:
                r3 = req.post(f'{OZON_API_URL}/v2/product/info', headers=hk,
                    json={'product_id': int(pid)}, timeout=10)
                if r3.status_code == 200:
                    stocks    = r3.json().get('result', {}).get('stocks', {})
                    stock_val = (stocks.get('present') or 0) + (stocks.get('coming') or 0)
                    has_stock = stock_val > 0

            return jsonify({
                'found':     True,
                'has_stock': has_stock,
                'name':      name,
                'sku':       offer_id,
                'stock':     stock_val
            })
    except Exception:
        pass
    return jsonify({'found': False})

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
    shops_opts = ''.join(
        f'<option value="{k["id"]}">{k["shop_name"]} (ID: {k["client_id"]})</option>'
        for k in active_keys
    )
    err_html = f'<div class="al er">{err}</div>' if err else ''

    html = f"""
<div style="display:flex;align-items:center;gap:1rem;margin-bottom:1.5rem">
  <a href="/tests" class="btn" style="background:#f0f2f5;border:1px solid #ddd;color:#444">&#8592; Назад</a>
  <p class="ttl" style="margin:0">+ Новый A/B тест</p>
</div>
{err_html}
<div class="box">
<form method="POST" action="/tests/create" id="test_form">
  <div class="fg"><label>Магазин</label>
    <select name="key_id" class="fi" required>{shops_opts}</select>
  </div>

  <!-- Товар -->
  <div class="fg" style="position:relative">
    <label>Товар <span style="color:#27ae60;font-size:.85rem">(с остатками)</span></label>
    <input type="hidden" name="product" id="product_val">
    <input type="hidden" id="product_img" value="">
    <div style="position:relative">
      <input type="text" id="prod_search" class="fi" autocomplete="off" placeholder="Выберите карточку..." style="padding-right:2rem">
      <button type="button" id="prod_clear" onclick="clearSearch()" style="display:none;position:absolute;right:.5rem;top:50%;transform:translateY(-50%);background:none;border:none;color:#aaa;cursor:pointer;font-size:1.2rem;padding:0;line-height:1">&times;</button>
    </div>
    <div id="prod_dropdown" style="display:none;position:absolute;z-index:200;background:#fff;border:1px solid #ddd;border-radius:10px;box-shadow:0 8px 24px rgba(0,0,0,.12);max-height:350px;overflow-y:auto;left:0;right:0;margin-top:2px"></div>
    <div id="prod_selected" style="display:none;background:#f0fdf4;border:2px solid #86efac;border-radius:10px;padding:.85rem 1rem;margin-top:.6rem;align-items:center;gap:.85rem"></div>
    <div id="prod_loading" style="display:none;color:#888;font-size:.85rem;margin-top:.4rem">&#128269; Загружаем список товаров...</div>
    <div id="sku_result" style="font-size:.85rem;margin-top:.4rem"></div>
    <div style="margin-top:.3rem">
      <span onclick="toggleSkuSearch()" style="font-size:.82rem;color:#667eea;cursor:pointer;text-decoration:underline">Не нашли товар? Найти по артикулу</span>
    </div>
    <div id="sku_search_wrap" style="display:none;margin-top:.5rem">
      <div style="display:flex;gap:.5rem">
        <input type="text" id="sku_manual" class="fi" placeholder="Введите артикул продавца или SKU Озона">
        <button type="button" onclick="checkBySku()" style="background:#667eea;color:#fff;border:none;border-radius:8px;padding:.75rem 1.2rem;cursor:pointer;font-size:.9rem;font-weight:600;white-space:nowrap">Найти</button>
      </div>
    </div>
    <div class="hn" id="prod_hint_text">Нажмите на поле — появится список товаров с остатками</div>
  </div>

  <!-- Варианты фото -->
  <div class="fg">
    <label>Варианты фото <span style="color:#667eea;font-size:.85rem">(от 2 до 10)</span></label>
    <style>
      #variants_grid {{ display:grid; grid-template-columns:repeat(5,1fr); gap:.5rem; margin-top:.5rem }}
      @media(max-width:600px){{ #variants_grid {{ grid-template-columns:repeat(2,1fr) !important }} }}
    </style>
    <div id="variants_grid"></div>
    <div style="display:flex;gap:.75rem;align-items:center;margin-top:.75rem;flex-wrap:wrap">
      <button type="button" onclick="triggerFileInput()" id="add_variant_btn"
        style="background:#f0f2f5;border:2px dashed #d0d0d0;border-radius:10px;padding:.6rem 1.2rem;cursor:pointer;color:#667eea;font-size:.9rem;font-weight:600">
        + Добавить фото
      </button>
      <input type="file" id="file_inp" accept="image/*" multiple style="display:none" onchange="handleFiles(this.files)">
      <span id="variant_count_label" style="font-size:.82rem;color:#888">Добавлено: 1 из 10</span>
      <span id="files_notice" style="font-size:.82rem"></span>
    </div>
  </div>

  <!-- Стратегия -->
  <div class="fg"><label>Стратегия ротации</label>
    <select name="strategy" class="fi">
      <option value="round_robin">По очереди (Round Robin) — равномерно</option>
      <option value="random">Случайная</option>
      <option value="best_ctr">Лучший CTR — больше показов победителю</option>
    </select>
    <div class="hn">Round Robin рекомендуется для новых тестов</div>
  </div>
  <button class="btn bp" style="width:100%">&#129514; Запустить тест</button>
</form>
</div>


<script src="/static/variants.js"></script>
<script src="/static/product-search.js"></script>
"""
    return render(html, 'tests')


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
