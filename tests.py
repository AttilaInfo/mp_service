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
    // Снимаем остальные галочки
    ['1h','4h','1d','1w'].forEach(function(k) {{
      var el = document.getElementById('preset_' + k);
      var lbl = document.getElementById('preset_label_' + k);
      if (el && k !== key) {{ el.checked = false; }}
      if (lbl) lbl.style.borderColor = (k === key && cb.checked) ? '#667eea' : '#d0d0d0';
    }});
    // Вставляем значение
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
  // Клик по радио не должен срабатывать дважды
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

    key_id        = request.form.get('key_id')
    product_raw   = request.form.get('product', '')
    strategy      = request.form.get('strategy', 'time')
    # Считаем варианты по переданным photo_N полям
    variant_count = 0
    for i in range(1, 11):
        if request.form.get(f'photo_{i}', '').strip():
            variant_count = i
        else:
            break
    if variant_count < 2:
        return redirect('/tests/new?err=Добавьте+минимум+2+варианта+фото')

    # Параметры стратегии
    rotation_minutes = None
    rotation_views   = None
    rotation_clicks  = None
    if strategy == 'time':
        try: rotation_minutes = max(15, int(request.form.get('rotation_minutes', 30)))
        except: rotation_minutes = 30
    elif strategy == 'views':
        try: rotation_views = max(10, int(request.form.get('rotation_views', 100)))
        except: rotation_views = 100
    elif strategy == 'clicks':
        try: rotation_clicks = max(20, int(request.form.get('rotation_clicks', 20)))
        except: rotation_clicks = 20

    # Формируем строку стратегии с параметром для хранения
    if strategy == 'time':
        strategy_str = f'time:{rotation_minutes}m'
    elif strategy == 'views':
        strategy_str = f'views:{rotation_views}'
    elif strategy == 'clicks':
        strategy_str = f'clicks:{rotation_clicks}'
    else:
        strategy_str = strategy

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
            continue  # пропускаем пустые (не должно быть, но на всякий)
        variants.append({'label': chr(64 + i), 'photo_url': photo})

    # Сохраняем в БД
    test_id = db.create_test(u['id'], key['shop_name'], sku, product_name, strategy_str)
    for v in variants:
        db.add_variant(test_id, v['label'], v['photo_url'])

    return redirect(f'/tests/{test_id}')


@tests_bp.route('/tests/<int:test_id>')
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
        '<tr><td style="color:#666;padding:.4rem 2rem .4rem 0">Стратегия:</td><td><strong>' + format_strategy(test['strategy']) + '</strong></td></tr>'
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


@tests_bp.route('/tests/<int:test_id>/stop', methods=['POST'])
def stop_test(test_id):
    u = me()
    if not u:
        return redirect('/login')
    db.finish_test(test_id, u['id'])
    return redirect(f'/tests/{test_id}')

