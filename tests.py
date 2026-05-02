"""
tests.py — управление A/B тестами: список, создание, детали, завершение.
"""
from flask import Blueprint, redirect, request
from datetime import datetime

import database as db
from templates import render, alert
from auth import me

tests_bp = Blueprint('tests', __name__)


@tests_bp.route('/tests')
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
@tests_bp.route('/tests/new')
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
        style="background:#f0f2f5;border:2px dashed #d0d0d0;border-radius:10px;padding:.6rem 1.4rem;cursor:pointer;color:#667eea;font-size:1rem;font-weight:600">
        + Добавить фото
      </button>
      <input type="file" id="file_inp" accept="image/*" multiple style="display:none" onchange="handleFiles(this.files)">
      <span id="variant_count_label" style="font-size:.95rem;font-weight:600;color:#888">Добавлено: 1 из 10</span>
      <span id="files_notice" style="font-size:.95rem;font-weight:600"></span>
    </div>
  </div>

  <!-- Стратегия -->
  <div class="fg">
    <label>Стратегия смены фото</label>
    <div style="background:#fff8e1;border:1.5px solid #ffe082;border-radius:8px;padding:.6rem .9rem;margin-bottom:.8rem;font-size:.85rem;color:#5d4037">
      &#128161; <strong>Важно:</strong> тест автоматически завершится, когда самый слабый вариант наберёт <strong>10 000 показов</strong> — это справедливо для любой стратегии. Вы также можете завершить тест самостоятельно в любое время.
    </div>

    <!-- Вариант 1: по времени -->
    <div class="strategy-option" id="s_time" onclick="selectStrategy('time')"
      style="border:2px solid #667eea;border-radius:10px;padding:1rem;margin-bottom:.6rem;cursor:pointer;background:#f5f3ff">
      <div style="display:flex;align-items:center;gap:.6rem;margin-bottom:.4rem">
        <input type="radio" name="strategy" value="time" id="r_time" checked style="accent-color:#667eea">
        <label for="r_time" style="font-weight:600;cursor:pointer;font-size:.95rem">&#9201; По времени</label>
      </div>
      <div style="font-size:.85rem;color:#666;margin-bottom:.7rem">Каждый вариант показывается заданное время, затем автоматически меняется на следующий</div>
      <div id="s_time_fields" style="display:flex;flex-direction:column;gap:.65rem">
        <!-- Быстрые пресеты -->
        <div style="display:flex;gap:.5rem;flex-wrap:wrap" onclick="event.stopPropagation()">
          <label style="display:flex;align-items:center;gap:.35rem;cursor:pointer;background:#fff;border:1.5px solid #d0d0d0;border-radius:8px;padding:.35rem .75rem;font-size:.85rem;font-weight:500;transition:border-color .15s" id="preset_label_1h">
            <input type="checkbox" id="preset_1h" onchange="applyPreset(this,'1h')" style="accent-color:#667eea;cursor:pointer"> каждый час
          </label>
          <label style="display:flex;align-items:center;gap:.35rem;cursor:pointer;background:#fff;border:1.5px solid #d0d0d0;border-radius:8px;padding:.35rem .75rem;font-size:.85rem;font-weight:500;transition:border-color .15s" id="preset_label_4h">
            <input type="checkbox" id="preset_4h" onchange="applyPreset(this,'4h')" style="accent-color:#667eea;cursor:pointer"> каждые 4 часа
          </label>
          <label style="display:flex;align-items:center;gap:.35rem;cursor:pointer;background:#fff;border:1.5px solid #d0d0d0;border-radius:8px;padding:.35rem .75rem;font-size:.85rem;font-weight:500;transition:border-color .15s" id="preset_label_1d">
            <input type="checkbox" id="preset_1d" onchange="applyPreset(this,'1d')" style="accent-color:#667eea;cursor:pointer"> раз в день
          </label>
          <label style="display:flex;align-items:center;gap:.35rem;cursor:pointer;background:#fff;border:1.5px solid #d0d0d0;border-radius:8px;padding:.35rem .75rem;font-size:.85rem;font-weight:500;transition:border-color .15s" id="preset_label_1w">
            <input type="checkbox" id="preset_1w" onchange="applyPreset(this,'1w')" style="accent-color:#667eea;cursor:pointer"> раз в неделю
          </label>
        </div>
        <!-- Поле ввода -->
        <div style="display:flex;align-items:center;gap:.5rem;flex-wrap:wrap">
          <span style="font-size:.9rem;color:#555">или введите вручную:</span>
          <input type="number" name="rotation_minutes" id="rotation_minutes" value="30" min="15" max="10080"
            class="fi" style="width:90px;padding:.4rem .6rem;font-size:.95rem"
            onclick="event.stopPropagation()" oninput="clearPresets()">
          <span style="font-size:.9rem;color:#555">минут</span>
        </div>
      </div>
    </div>

    <!-- Вариант 2: по показам -->
    <div class="strategy-option" id="s_views" onclick="selectStrategy('views')"
      style="border:2px solid #ddd;border-radius:10px;padding:1rem;margin-bottom:.6rem;cursor:pointer;background:#fafafa">
      <div style="display:flex;align-items:center;gap:.6rem;margin-bottom:.4rem">
        <input type="radio" name="strategy" value="views" id="r_views" style="accent-color:#667eea">
        <label for="r_views" style="font-weight:600;cursor:pointer;font-size:.95rem">&#128065; По количеству показов</label>
      </div>
      <div style="font-size:.85rem;color:#666;margin-bottom:.7rem">Ротация происходит при достижении карточкой нужного числа показов и продолжается до 10 000 показов на один вариант</div>
      <div id="s_views_fields" style="display:none;flex-direction:column;gap:.65rem">
        <!-- Быстрые пресеты показов -->
        <div style="display:flex;gap:.5rem;flex-wrap:wrap" onclick="event.stopPropagation()">
          <label style="display:flex;align-items:center;gap:.35rem;cursor:pointer;background:#fff;border:1.5px solid #d0d0d0;border-radius:8px;padding:.35rem .75rem;font-size:.85rem;font-weight:500" id="vpreset_label_200">
            <input type="checkbox" id="vpreset_200" onchange="applyViewsPreset(this,200)" style="accent-color:#667eea;cursor:pointer"> 200 показов
          </label>
          <label style="display:flex;align-items:center;gap:.35rem;cursor:pointer;background:#fff;border:1.5px solid #d0d0d0;border-radius:8px;padding:.35rem .75rem;font-size:.85rem;font-weight:500" id="vpreset_label_500">
            <input type="checkbox" id="vpreset_500" onchange="applyViewsPreset(this,500)" style="accent-color:#667eea;cursor:pointer"> 500 показов
          </label>
          <label style="display:flex;align-items:center;gap:.35rem;cursor:pointer;background:#fff;border:1.5px solid #d0d0d0;border-radius:8px;padding:.35rem .75rem;font-size:.85rem;font-weight:500" id="vpreset_label_1000">
            <input type="checkbox" id="vpreset_1000" onchange="applyViewsPreset(this,1000)" style="accent-color:#667eea;cursor:pointer"> 1 000 показов
          </label>
        </div>
        <div style="display:flex;align-items:center;gap:.5rem;flex-wrap:wrap">
          <span style="font-size:.9rem;color:#555">или введите вручную:</span>
          <input type="number" name="rotation_views" id="rotation_views" value="100" min="50" max="10000"
            class="fi" style="width:100px;padding:.4rem .6rem;font-size:.95rem"
            onclick="event.stopPropagation()" oninput="clearViewsPresets()">
          <span style="font-size:.9rem;color:#555">показов</span>
        </div>
      </div>
    </div>

    <!-- Вариант 3: по кликам -->
    <div class="strategy-option" id="s_clicks" onclick="selectStrategy('clicks')"
      style="border:2px solid #ddd;border-radius:10px;padding:1rem;margin-bottom:.6rem;cursor:pointer;background:#fafafa">
      <div style="display:flex;align-items:center;gap:.6rem;margin-bottom:.4rem">
        <input type="radio" name="strategy" value="clicks" id="r_clicks" style="accent-color:#667eea">
        <label for="r_clicks" style="font-weight:600;cursor:pointer;font-size:.95rem">&#128717; По количеству кликов</label>
      </div>
      <div style="font-size:.85rem;color:#666;margin-bottom:.7rem">Ротация происходит при достижении карточкой нужного числа кликов в корзину</div>
      <div id="s_clicks_fields" style="display:none;flex-direction:column;gap:.65rem">
        <div style="display:flex;gap:.5rem;flex-wrap:wrap" onclick="event.stopPropagation()">
          <label style="display:flex;align-items:center;gap:.35rem;cursor:pointer;background:#fff;border:1.5px solid #d0d0d0;border-radius:8px;padding:.35rem .75rem;font-size:.85rem;font-weight:500" id="cpreset_label_50">
            <input type="checkbox" id="cpreset_50" onchange="applyClicksPreset(this,50)" style="accent-color:#667eea;cursor:pointer"> 50 кликов
          </label>
          <label style="display:flex;align-items:center;gap:.35rem;cursor:pointer;background:#fff;border:1.5px solid #d0d0d0;border-radius:8px;padding:.35rem .75rem;font-size:.85rem;font-weight:500" id="cpreset_label_100">
            <input type="checkbox" id="cpreset_100" onchange="applyClicksPreset(this,100)" style="accent-color:#667eea;cursor:pointer"> 100 кликов
          </label>
          <label style="display:flex;align-items:center;gap:.35rem;cursor:pointer;background:#fff;border:1.5px solid #d0d0d0;border-radius:8px;padding:.35rem .75rem;font-size:.85rem;font-weight:500" id="cpreset_label_200">
            <input type="checkbox" id="cpreset_200" onchange="applyClicksPreset(this,200)" style="accent-color:#667eea;cursor:pointer"> 200 кликов
          </label>
        </div>
        <div style="display:flex;align-items:center;gap:.5rem;flex-wrap:wrap">
          <span style="font-size:.9rem;color:#555">или введите вручную:</span>
          <input type="number" name="rotation_clicks" id="rotation_clicks" value="20" min="20" max="10000"
            class="fi" style="width:100px;padding:.4rem .6rem;font-size:.95rem"
            onclick="event.stopPropagation()" oninput="clearClicksPresets()">
          <span style="font-size:.9rem;color:#555">кликов</span>
        </div>
      </div>
    </div>
  </div>

  <script>
  var PRESETS = {{ '1h': 60, '4h': 240, '1d': 1440, '1w': 10080 }};

  function applyPreset(cb, key) {{
    ['1h','4h','1d','1w'].forEach(function(k) {{
      var el = document.getElementById('preset_' + k);
      var lbl = document.getElementById('preset_label_' + k);
      if (el && k !== key) {{ el.checked = false; }}
      if (lbl) lbl.style.borderColor = (k === key && cb.checked) ? '#667eea' : '#d0d0d0';
    }});
    var inp = document.getElementById('rotation_minutes');
    if (inp) inp.value = cb.checked ? PRESETS[key] : 30;
  }}

  function applyViewsPreset(cb, val) {{
    [200,500,1000].forEach(function(v) {{
      var el = document.getElementById('vpreset_' + v);
      var lbl = document.getElementById('vpreset_label_' + v);
      if (el && v !== val) el.checked = false;
      if (lbl) lbl.style.borderColor = (v === val && cb.checked) ? '#667eea' : '#d0d0d0';
    }});
    var inp = document.getElementById('rotation_views');
    if (inp) inp.value = cb.checked ? val : 100;
  }}

  function applyClicksPreset(cb, val) {{
    [50,100,200].forEach(function(v) {{
      var el = document.getElementById('cpreset_' + v);
      var lbl = document.getElementById('cpreset_label_' + v);
      if (el && v !== val) el.checked = false;
      if (lbl) lbl.style.borderColor = (v === val && cb.checked) ? '#667eea' : '#d0d0d0';
    }});
    var inp = document.getElementById('rotation_clicks');
    if (inp) inp.value = cb.checked ? val : 20;
  }}

  function clearClicksPresets() {{
    [50,100,200].forEach(function(v) {{
      var el = document.getElementById('cpreset_' + v);
      var lbl = document.getElementById('cpreset_label_' + v);
      if (el) el.checked = false;
      if (lbl) lbl.style.borderColor = '#d0d0d0';
    }});
  }}

  function clearViewsPresets() {{
    [200,500,1000].forEach(function(v) {{
      var el = document.getElementById('vpreset_' + v);
      var lbl = document.getElementById('vpreset_label_' + v);
      if (el) el.checked = false;
      if (lbl) lbl.style.borderColor = '#d0d0d0';
    }});
  }}

  function clearPresets() {{
    ['1h','4h','1d','1w'].forEach(function(k) {{
      var el = document.getElementById('preset_' + k);
      var lbl = document.getElementById('preset_label_' + k);
      if (el) el.checked = false;
      if (lbl) lbl.style.borderColor = '#d0d0d0';
    }});
  }}

  function selectStrategy(val) {{
    ['time','views','clicks'].forEach(function(v) {{
      var opt = document.getElementById('s_' + v);
      var fields = document.getElementById('s_' + v + '_fields');
      var radio = document.getElementById('r_' + v);
      var active = (v === val);
      radio.checked = active;
      opt.style.borderColor = active ? '#667eea' : '#ddd';
      opt.style.background = active ? '#f5f3ff' : '#fafafa';
      if (fields) fields.style.display = active ? 'flex' : 'none';
    }});
  }}
  ['r_time','r_views','r_clicks'].forEach(function(id) {{
    var el = document.getElementById(id);
    if (el) el.addEventListener('click', function(e) {{
      e.stopPropagation();
      selectStrategy(this.value);
    }});
  }});
  </script>

  <button class="btn bp" style="width:100%">&#129514; Запустить тест</button>
</form>
</div>


<script src="/static/variants.js"></script>
<script src="/static/product-search.js"></script>
"""
    return render(html, 'tests')


@tests_bp.route('/tests/create', methods=['POST'])
def create_test():
    u = me()
    if not u:
        return redirect('/login')

    key_id      = request.form.get('key_id')
    product_raw = request.form.get('product', '')
    strategy    = request.form.get('strategy', 'time')

    # ── ИСПРАВЛЕНИЕ 1: собираем все непустые photo_N (без break) ──────────
    photos = []
    for i in range(1, 11):
        photo = request.form.get(f'photo_{i}', '').strip()
        if photo:
            photos.append(photo)

    if len(photos) < 2:
        return redirect('/tests/new?err=Добавьте+минимум+2+варианта+фото')

    # Параметры стратегии
    if strategy == 'time':
        try:
            rotation_val = max(15, int(request.form.get('rotation_minutes', 30)))
        except (ValueError, TypeError):
            rotation_val = 30
        strategy_str = f'time:{rotation_val}m'

    elif strategy == 'views':
        try:
            rotation_val = max(50, int(request.form.get('rotation_views', 100)))
        except (ValueError, TypeError):
            rotation_val = 100
        strategy_str = f'views:{rotation_val}'

    elif strategy == 'clicks':
        try:
            rotation_val = max(20, int(request.form.get('rotation_clicks', 20)))
        except (ValueError, TypeError):
            rotation_val = 20
        strategy_str = f'clicks:{rotation_val}'

    else:
        strategy_str = strategy

    # Парсим товар
    if '|' in product_raw:
        sku, product_name = product_raw.split('|', 1)
    else:
        sku = product_raw
        product_name = product_raw

    sku          = sku.strip()
    product_name = product_name.strip()

    if not sku or not product_name:
        return redirect('/tests/new?err=Выберите+товар')

    # Получаем ключ
    keys = db.get_keys(u['id'])
    key  = next((k for k in keys if str(k['id']) == str(key_id)), None)
    if not key:
        return redirect('/tests/new?err=Магазин+не+найден')

    # ── ИСПРАВЛЕНИЕ 2: сохраняем в БД — убрана несуществующая переменная v ─
    test_id = db.create_test(u['id'], key['shop_name'], sku, product_name, strategy_str)
    for i, photo_url in enumerate(photos, start=1):
        label = chr(64 + i)   # A, B, C, …
        db.add_variant(test_id, label, photo_url)

    return redirect(f'/tests/{test_id}')


@tests_bp.route('/tests/<int:test_id>')
def test_detail(test_id):
    u = me()
    if not u:
        return redirect('/login')

    test = db.get_test(test_id, u['id'])
    if not test:
        return redirect('/tests')

    variants = [dict(v) for v in db.get_variants(test_id)]
    is_running = test['status'] == 'running'

    # Считаем CTR для каждого варианта
    for v in variants:
        views  = v.get('views', 0) or 0
        clicks = v.get('clicks', 0) or 0
        v['ctr_calc'] = round(clicks / views * 100, 2) if views > 0 else 0.0

    # Лидер по CTR
    best_label = ''
    if variants:
        leader = max(variants, key=lambda v: v['ctr_calc'])
        if leader['ctr_calc'] > 0:
            best_label = leader['label']

    # Итоговые цифры
    total_views  = sum(v.get('views',  0) or 0 for v in variants)
    total_clicks = sum(v.get('clicks', 0) or 0 for v in variants)
    total_sales  = sum(v.get('sales',  0) or 0 for v in variants)
    overall_ctr  = round(total_clicks / total_views * 100, 2) if total_views > 0 else 0.0
    max_ctr      = max((v['ctr_calc'] for v in variants), default=0) or 1

    # Шапка
    status_badge = (
        '<span style="background:#d4edda;color:#155724;border:1.5px solid #c3e6cb;'
        'border-radius:20px;padding:.3rem .85rem;font-size:.82rem;font-weight:700;flex-shrink:0">&#9679; Активен</span>'
        if is_running else
        '<span style="background:#f8d7da;color:#721c24;border:1.5px solid #f5c6cb;'
        'border-radius:20px;padding:.3rem .85rem;font-size:.82rem;font-weight:700;flex-shrink:0">&#9209; Завершён</span>'
    )

    c = (
        '<div style="display:flex;align-items:center;gap:1rem;margin-bottom:1.5rem;flex-wrap:wrap">'
        '<a href="/tests" class="btn" style="background:#f0f2f5;border:1px solid #ddd;color:#444;flex-shrink:0">&#8592; Назад</a>'
        '<p class="ttl" style="margin:0;flex:1;min-width:0;font-size:1.1rem">' + test['product_name'] + '</p>'
        + status_badge + '</div>'
    )

    # Инфо-плашки
    info_items = [
        ('Вариантов',  str(len(variants)),              '&#127919;', '#667eea'),
        ('Показов',    f'{total_views:,}'.replace(',', ' '), '&#128065;', '#2196f3'),
        ('Кликов',     f'{total_clicks:,}'.replace(',', ' '), '&#128717;', '#27ae60'),
        ('Продаж',     str(total_sales),                '&#128200;', '#ff9800'),
        ('Общий CTR',  str(overall_ctr) + '%',          '&#128202;', '#9c27b0'),
        ('Магазин',    test['shop_name'],                '&#127978;', '#607d8b'),
        ('Стратегия',  format_strategy(test.get('strategy', '')), '&#9201;', '#455a64'),
        ('Запущен',    str(test['created_at'])[:10],    '&#128197;', '#795548'),
    ]
    c += '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:.6rem;margin-bottom:1.75rem">'
    for lbl, val, icon, clr in info_items:
        c += (
            '<div style="background:#fff;border:1.5px solid #eee;border-radius:10px;padding:.7rem .85rem">'
            '<div style="font-size:.7rem;color:#aaa;font-weight:700;text-transform:uppercase;letter-spacing:.05em;margin-bottom:.25rem">' + lbl + '</div>'
            '<div style="font-size:.95rem;font-weight:700;color:' + clr + ';white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="' + str(val) + '">'
            + icon + ' ' + str(val) + '</div>'
            '</div>'
        )
    c += '</div>'

    # Карточки вариантов
    c += '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:1rem;margin-bottom:1.5rem">'
    for v in variants:
        views      = v.get('views', 0) or 0
        clicks     = v.get('clicks', 0) or 0
        sales      = v.get('sales', 0) or 0
        conversion = v.get('conversion', 0) or 0
        ctr        = v['ctr_calc']
        is_winner  = (v['label'] == best_label and ctr > 0)
        is_current = (v['label'] == 'A')
        bar_w      = int(ctr / max_ctr * 100) if max_ctr > 0 else 0

        # Цвет акцента карточки
        if is_winner and not is_running:
            accent = '#27ae60'; border = '2.5px solid #27ae60'
            hdr_bg = 'linear-gradient(135deg,#27ae60,#2ecc71)'; hdr_clr = '#fff'
        elif is_winner:
            accent = '#667eea'; border = '2.5px solid #667eea'
            hdr_bg = 'linear-gradient(135deg,#667eea,#764ba2)'; hdr_clr = '#fff'
        elif is_current:
            accent = '#e91e8c'; border = '1.5px solid #f8bbd0'
            hdr_bg = 'linear-gradient(135deg,#f093fb,#f5576c)'; hdr_clr = '#fff'
        else:
            accent = '#667eea'; border = '1.5px solid #e8e8e8'
            hdr_bg = '#f5f5f5'; hdr_clr = '#555'

        # Фото
        photo_url = v.get('photo_url', '')
        if photo_url.startswith('/uploads/') or photo_url.startswith('http'):
            img_html = '<img src="' + photo_url + '" style="width:100%;height:100%;object-fit:cover" loading="lazy">'
        else:
            img_html = '<div style="font-size:2rem;color:#ccc">&#128247;</div>'

        # Бейджи
        badges = ''
        if is_winner and not is_running:
            badges += '<div style="position:absolute;top:.45rem;right:.45rem;background:#27ae60;color:#fff;border-radius:20px;padding:.15rem .55rem;font-size:.7rem;font-weight:700;box-shadow:0 2px 6px rgba(0,0,0,.15)">&#127942; Победитель</div>'
        elif is_winner:
            badges += '<div style="position:absolute;top:.45rem;right:.45rem;background:#667eea;color:#fff;border-radius:20px;padding:.15rem .55rem;font-size:.7rem;font-weight:700;box-shadow:0 2px 6px rgba(0,0,0,.15)">&#128200; Лидер</div>'
        if is_current:
            badges += '<div style="position:absolute;bottom:.45rem;left:50%;transform:translateX(-50%);background:rgba(0,0,0,.6);color:#fff;border-radius:20px;padding:.15rem .6rem;font-size:.68rem;font-weight:700;white-space:nowrap">Сейчас на Озоне</div>'

        # Метрики
        def mrow(icon, lbl, val):
            return (
                '<div style="background:#f8f9fa;border-radius:6px;padding:.3rem .5rem;display:flex;justify-content:space-between;align-items:center">'
                '<span style="color:#aaa;font-size:.78rem">' + icon + ' ' + lbl + '</span>'
                '<strong style="font-size:.82rem;color:#333">' + str(val) + '</strong>'
                '</div>'
            )

        c += (
            '<div style="background:#fff;border:' + border + ';border-radius:14px;overflow:hidden;'
            'box-shadow:0 2px 10px rgba(0,0,0,.05)">'

            # Заголовок
            + '<div style="background:' + hdr_bg + ';color:' + hdr_clr + ';padding:.4rem .8rem;'
            'display:flex;justify-content:space-between;align-items:center;font-size:.85rem;font-weight:700">'
            + '<span>Вариант ' + str(ord(v['label']) - 64) + '</span>'
            + ('</div>' )

            # Фото 3:4
            + '<div style="width:100%;aspect-ratio:3/4;background:#f0f0f0;overflow:hidden;'
            'display:flex;align-items:center;justify-content:center;position:relative">'
            + badges + img_html + '</div>'

            # CTR + bar
            + '<div style="padding:.65rem .8rem .55rem">'
            + '<div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:.3rem">'
            + '<span style="font-size:.7rem;color:#aaa;font-weight:700;text-transform:uppercase;letter-spacing:.05em">CTR</span>'
            + '<span style="font-size:1.45rem;font-weight:800;color:' + accent + '">' + str(ctr) + '%</span>'
            + '</div>'
            + '<div style="background:#f0f2f5;border-radius:99px;height:4px;margin-bottom:.6rem">'
            + '<div style="height:100%;border-radius:99px;background:' + accent + ';width:' + str(bar_w) + '%;transition:width .4s ease"></div>'
            + '</div>'

            # Метрики
            + '<div style="display:flex;flex-direction:column;gap:.25rem">'
            + mrow('&#128065;', 'Показы',    f'{views:,}'.replace(',', ' '))
            + mrow('&#128717;', 'Клики',     clicks)
            + mrow('&#128200;', 'Продажи',   sales)
            + mrow('&#128260;', 'Конверсия', str(round(conversion * 100, 1)) + '%')
            + '</div>'
            + '</div>'  # end padding
            + '</div>'  # end card
        )

    c += '</div>'

    # Кнопка завершения
    if is_running:
        c += (
            '<div style="background:#fff8e1;border:1.5px solid #ffe082;border-radius:12px;'
            'padding:.85rem 1.2rem;display:flex;align-items:center;justify-content:space-between;'
            'flex-wrap:wrap;gap:.75rem">'
            '<span style="font-size:.88rem;color:#5d4037">'
            '&#128161; Тест активен. Победитель — вариант с максимальным CTR.</span>'
            '<form method="POST" action="/tests/' + str(test_id) + '/stop" style="margin:0">'
            '<button class="btn" style="background:#e74c3c;color:#fff;border:none;padding:.55rem 1.3rem;'
            'font-weight:700;border-radius:8px" '
            'onclick="return confirm(\'Завершить тест и зафиксировать результаты?\')">'
            '&#9209; Завершить тест</button>'
            '</form>'
            '</div>'
        )

    return render(c, 'tests')


@tests_bp.route('/tests/<int:test_id>/stop', methods=['POST'])
def stop_test(test_id):
    u = me()
    if not u:
        return redirect('/login')
    db.finish_test(test_id, u['id'])
    return redirect(f'/tests/{test_id}')


# ── Вспомогательная функция форматирования стратегии ──────────────────────
def format_strategy(strategy_str):
    """Преобразует строку стратегии в читаемый вид."""
    if not strategy_str:
        return '—'
    if strategy_str.startswith('time:'):
        val = strategy_str[5:]
        minutes = int(val.rstrip('m')) if val.endswith('m') else int(val)
        if minutes >= 10080:
            return '⏱ Раз в неделю'
        if minutes >= 1440:
            days = minutes // 1440
            return f'⏱ Каждые {days} дн.'
        if minutes >= 60:
            hours = minutes // 60
            return f'⏱ Каждые {hours} ч.'
        return f'⏱ Каждые {minutes} мин.'
    if strategy_str.startswith('views:'):
        return f'👁 Каждые {strategy_str[6:]} показов'
    if strategy_str.startswith('clicks:'):
        return f'🛒 Каждые {strategy_str[7:]} кликов'
    return strategy_str
