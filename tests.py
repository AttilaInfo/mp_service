"""
tests.py — управление A/B тестами: список, создание, детали, завершение.
"""
import threading
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
    if active_key and db.get_perf_key(u['id']):
        c += '<a href="/tests/new" class="btn bp">&#43; Создать тест</a>'
    elif active_key:
        c += '<a href="/api-keys" class="btn" style="background:#fff3cd;border:1px solid #ffc107;color:#856404">&#128640; Подключить Performance API</a>'
    c += '</div>'

    perf_key = db.get_perf_key(u['id'])
    has_seller_api = bool(active_key)
    has_perf_api   = bool(perf_key)

    if not has_seller_api or not has_perf_api:
        c += ('<div style="background:#fff8e1;border:1px solid #ffe082;border-radius:14px;padding:1.5rem;margin-bottom:1.5rem">'
               '<p style="font-weight:700;color:#856404;font-size:1.05rem;margin-bottom:1rem">'
               '&#9888; Для создания A/B тестов нужно подключить два API</p>'
               '<div style="display:flex;flex-direction:column;gap:.75rem">'
               '<div style="display:flex;align-items:center;gap:.75rem;background:' + ('#d4edda' if has_seller_api else '#f8d7da') + ';border-radius:10px;padding:.75rem 1rem">'
               '<span style="font-size:1.3rem">' + ('&#10003;' if has_seller_api else '&#10005;') + '</span>'
               '<div style="flex:1">'
               '<div style="font-weight:600">Seller API Озона</div>'
               '<div style="font-size:.85rem;color:#555">Нужен для управления фото товаров</div>'
               '</div>'
               '</div>'
               '<div style="display:flex;align-items:center;gap:.75rem;background:' + ('#d4edda' if has_perf_api else '#f8d7da') + ';border-radius:10px;padding:.75rem 1rem">'
               '<span style="font-size:1.3rem">' + ('&#10003;' if has_perf_api else '&#10005;') + '</span>'
               '<div style="flex:1">'
               '<div style="font-weight:600">Performance API Озона &#128640;</div>'
               '<div style="font-size:.85rem;color:#555">Нужен для точного CTR через рекламные кампании</div>'
               '</div>'
               '</div>'
               '</div>'
               + ('<div style="margin-top:1rem;text-align:right"><a href="/api-keys" class="btn bp">Подключить API ключи →</a></div>' if not (has_seller_api and has_perf_api) else '') +
               '</div>')

    if user_tests:
        c += '<div class="box"><table>'
        c += '<tr><th>Товар</th><th>Магазин</th><th>Вариантов</th><th>Статус</th><th>Создан</th><th></th></tr>'
        for t in user_tests:
            status_badge = '<span class="bg g">Активен</span>' if t['status'] == 'running' else '<span class="bg r">Завершён</span>'
            tid = str(t['id'])
            c += (
                '<tr onclick="location.href=\'/tests/' + tid + '\'" '
                'style="cursor:pointer;transition:background .15s" '
                'onmouseover="this.style.background=\'#f5f3ff\'" '
                'onmouseout="this.style.background=\'\'">' 
                '<td><strong>' + t['product_name'] + '</strong><br><small style="color:#999">SKU: ' + t['sku'] + '</small></td>'
                '<td>' + t['shop_name'] + '</td>'
                '<td style="text-align:center">' + str(t.get('variant_count', 0)) + '</td>'
                '<td>' + status_badge + '</td>'
                '<td>' + str(t['created_at'])[:10] + '</td>'
                '<td style="display:flex;gap:.4rem;flex-wrap:wrap" onclick="event.stopPropagation()">'
                + (('<a href="/tests/' + tid + '/edit" class="btn" style="padding:.4rem .9rem;font-size:.82rem;background:#fff3cd;border:1px solid #ffc107;color:#856404">Изменить</a>') if t['status'] == 'running' else '') +
                (('<form method="POST" action="/tests/' + tid + '/delete" style="margin:0"><button class="btn bd" style="padding:.4rem .9rem;font-size:.82rem" onclick="return confirm(&apos;Удалить тест и все данные?&apos;)">&#128465; Удалить</button></form>') if t['status'] != 'running' else '') +
                '</td>'
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
        return redirect('/tests?err=Сначала+добавьте+API+ключ+Озона')

    # Проверка Performance API — показываем предупреждение на странице тестов
    perf_key = db.get_perf_key(u['id'])

    err = request.args.get('err', '')
    shops_opts = ''.join(
        f'<option value="{k["id"]}">{k["shop_name"]} (ID: {k["client_id"]})</option>'
        for k in active_keys
    )
    # Баланс токенов и стоимость теста
    balance   = db.get_balance(u['id'])
    service   = db.get_service('ab_test')
    test_cost = service['token_cost'] if service else 500
    enough    = balance >= test_cost
    # err_html вычисляем ПОСЛЕ проверки баланса — при нехватке токенов скрываем дубль
    err_html = '' if not enough else (f'<div class="al er">{err}</div>' if err else '')
    if enough:
        balance_html = (
            '<div style="background:#d4edda;border:1.5px solid #c3e6cb;border-radius:10px;'
            'padding:.65rem 1rem;font-size:.88rem;margin-bottom:.75rem;'
            'display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.5rem">'
            f'<span>&#128176; Баланс: <strong>{balance} токенов</strong></span>'
            f'<span style="color:#666">Стоимость теста: <strong>{test_cost} токенов</strong></span>'
            '</div>'
        )
    else:
        balance_html = (
            '<div class="al er" style="margin-bottom:.75rem">'
            f'&#9888; Недостаточно токенов. Баланс: <strong>{balance}</strong>, нужно: <strong>{test_cost}</strong>. '
            '<a href="/billing" style="color:#721c24;font-weight:700;text-decoration:underline">Пополнить баланс →</a>'
            '</div>'
        )

    html = (
        f'''<div style="display:flex;align-items:center;gap:1rem;margin-bottom:1.5rem">'''
        '''<a href="/tests" class="btn" style="background:#f0f2f5;border:1px solid #ddd;color:#444">&#8592; Назад</a>'''
        '''<p class="ttl" style="margin:0">+ Новый A/B тест</p></div>'''
        + err_html
        + balance_html
        + '''<div class="box">'''
    )
    html += f"""

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

  <!-- Шаг 3: Рекламная кампания -->
  <!-- Шаг 3: Рекламная кампания -->
  <div class="fg" id="camp_section" style="border:2px solid #667eea;border-radius:12px;padding:1.2rem;background:#f5f3ff">
    <label style="font-weight:700;font-size:1rem;color:#4c1d95;display:flex;align-items:center;gap:.5rem">
      &#128640; Рекламная кампания <span style="font-weight:400;font-size:.82rem;color:#888">(обязательно для точного CTR)</span>
    </label>
    <p style="font-size:.85rem;color:#666;margin:.6rem 0 1rem">
      <span id="camp_desc_text"></span>
    </p>
    <div id="camp_status" style="margin-bottom:.8rem">
      <span style="color:#aaa;font-size:.9rem">&#128269; Выберите товар выше — список кампаний загрузится автоматически</span>
    </div>
    <input type="hidden" name="campaign_ids" id="camp_ids_field" value="">
    <div style="display:flex;gap:.5rem;align-items:center;margin-top:.5rem">
      <button type="button" onclick="loadCampaigns()" class="btn" style="background:#e8f4fd;border:1px solid #bfdbfe;color:#1e40af;font-size:.85rem;padding:.4rem .9rem">
        &#128260; Обновить список кампаний
      </button>
      <span id="camp_hint" style="font-size:.8rem;color:#999"></span>
    </div>
  </div>

  <div id="no_perf_warning" style="display:none;background:#fff3cd;border:1px solid #ffe082;border-radius:10px;padding:1rem;margin-bottom:1rem">
    <p style="font-size:.9rem">&#9888; Для точного CTR нужен <strong>Performance API</strong>.
    <a href="/api-keys" style="color:#1e40af;font-weight:600">Подключите его в разделе API ключи</a> и вернитесь.</p>
  </div>

<script>
var _selectedCamps = [];

function loadCampaigns() {{
  var prodEl = document.getElementById('product_val');
  var sku = prodEl && prodEl.value ? prodEl.value.split('|')[0].trim() : '';
  if (!sku) {{
    document.getElementById('camp_status').innerHTML = '<span style="color:#aaa;font-size:.9rem">&#128269; Выберите товар выше — список кампаний загрузится автоматически</span>';
    return;
  }}
  document.getElementById('camp_status').innerHTML = '<span style="color:#aaa;font-size:.9rem">&#9203; Загрузка кампаний...</span>';

  var controller = new AbortController();
  var timer = setTimeout(function(){{ controller.abort(); }}, 20000);

  fetch('/api/perf-campaigns?sku=' + encodeURIComponent(sku), {{signal: controller.signal}})
    .then(function(r){{ clearTimeout(timer); return r.json(); }})
    .then(function(data) {{
      var el = document.getElementById('camp_status');
      if (data.error === 'no_perf_key') {{
        document.getElementById('no_perf_warning').style.display = '';
        document.getElementById('variants_section').style.display = '';
        document.getElementById('camp_section').style.borderColor = '#ffc107';
        el.innerHTML = '';
        return;
      }}
      document.getElementById('no_perf_warning').style.display = 'none';

      var camps = data.campaigns || [];
      if (!camps.length) {{
        el.innerHTML = '<div style="background:#fff8e1;border:1.5px solid #ffc107;border-radius:10px;padding:1rem 1.1rem;line-height:1.6">'
          + '<p style="font-weight:700;color:#856404;margin:0 0 .5rem;font-size:.95rem">&#9888; Рекламная кампания не найдена</p>'
          + '<p style="color:#555;font-size:.88rem;margin:0 0 .4rem">Для A/B тестирования необходима работающая рекламная кампания на этот товар — без неё мы не сможем отслеживать CTR.</p>'
          + '<p style="color:#888;font-size:.82rem;margin:0 0 .7rem">&#128161; Рекомендуем: 1 рекламная кампания — 1 товар. Так статистика будет точнее.</p>'
          + '<a href="https://seller.ozon.ru/app/advertisement/product/cpc" target="_blank" rel="noopener" '
          + 'style="display:inline-flex;align-items:center;gap:.45rem;background:#667eea;color:#fff;border-radius:8px;padding:.5rem 1.1rem;font-weight:600;text-decoration:none;font-size:.88rem">'
          + '&#128640; Создать рекламную кампанию в Озоне &#8594;</a>'
          + '<p style="margin:.7rem 0 0;font-size:.8rem;color:#999">Озон &#8594; Продвижение &#8594; Оплата за клик &#8594; Создать кампанию. После создания нажмите «Обновить список кампаний».</p>'
          + '</div>';
        var sbtn = document.getElementById('submit_btn');
        var shint = document.getElementById('submit_hint');
        if (sbtn) sbtn.disabled = true;
        if (shint) {{ shint.textContent = 'Создайте рекламную кампанию и обновите список'; shint.style.display = ''; }}
        document.getElementById('camp_section').style.borderColor = '#ffc107';
        return;
      }}

      var html = '';
      camps.forEach(function(c) {{
        html += '<label style="display:flex;align-items:center;gap:.6rem;margin-bottom:.5rem;cursor:pointer;font-size:.9rem">'
          + '<input type="checkbox" value="' + c.id + '" onchange="updateCampSel()" style="accent-color:#667eea"> '
          + c.name
          + ' <span style="color:#aaa;font-size:.78rem">(ID: ' + c.id + ')</span></label>';
      }});
      el.innerHTML = '<p style="font-size:.82rem;color:#555;margin:0 0 .6rem">&#9745; Отметьте галочкой кампанию чтобы продолжить — после этого откроется загрузка фотографий:</p>' + html;
      document.getElementById('camp_section').style.borderColor = '#27ae60';
      var vs = document.getElementById('variants_section');
      // variants_section появится после выбора кампании (в updateCampSel)
    }})
    .catch(function(e) {{
      clearTimeout(timer);
      var msg = (e.name === 'AbortError') ? 'Превышено время ожидания (20 сек).' : 'Ошибка соединения.';
      document.getElementById('camp_status').innerHTML = '<div style="background:#f8d7da;border-radius:8px;padding:.8rem;font-size:.88rem;color:#721c24">'
        + '&#10060; ' + msg + ' '
        + '<button type="button" onclick="loadCampaigns()" style="background:none;border:none;color:#1e40af;cursor:pointer;font-weight:600;font-size:.88rem;text-decoration:underline;padding:0">Попробовать ещё раз</button></div>';
    }});
}}

function updateCampSel() {{
  var ids = [];
  document.querySelectorAll('#camp_status input:checked').forEach(function(x){{ ids.push(x.value); }});
  _selectedCamps = ids;
  document.getElementById('camp_ids_field').value = ids.join(',');
  var btn  = document.getElementById('submit_btn');
  var hint = document.getElementById('submit_hint');
  if (ids.length > 0) {{
    if (btn)  btn.disabled = false;
    if (hint) hint.style.display = 'none';
    document.getElementById('camp_section').style.borderColor = '#27ae60';
    // Показываем блок загрузки фото
    var vs = document.getElementById('variants_section');
    if (vs) vs.style.display = '';
  }} else {{
    if (btn)  btn.disabled = true;
    if (hint) {{ hint.style.display = ''; }}
    document.getElementById('camp_section').style.borderColor = '#e74c3c';
  }}
}}

// Загружаем кампании автоматически когда выбран товар
document.addEventListener('DOMContentLoaded', function() {{
  var _lastProdVal = '';
  setInterval(function() {{
    var prodField = document.getElementById('product_val');
    var val = prodField ? prodField.value : '';
    if (val && val !== _lastProdVal) {{
      _lastProdVal = val;
      loadCampaigns();
    }}
  }}, 500);
  var prodField = document.getElementById('product_val');
  if (prodField && prodField.value) loadCampaigns();
}});
</script>

  <!-- Варианты фото (показываются после выбора кампании) -->
  <div id="variants_section" style="display:none">
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

  </div>
  <!-- Стратегия -->
  <div class="fg">
    <label>Стратегия смены фото</label>
    <div style="background:#fff8e1;border:1.5px solid #ffe082;border-radius:8px;padding:.6rem .9rem;margin-bottom:.8rem;font-size:.85rem;color:#5d4037">
      &#128161; <strong>Важно:</strong> Вы можете завершить тест самостоятельно в любое время. Тест автоматически завершится через <strong>14 дней</strong> или когда все варианты наберут по <strong>10 000 показов</strong> — это справедливо для любой стратегии.
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

  <!-- Кнопка запуска -->
  <div style="margin-top:1.5rem">
    <p id="submit_hint" style="display:none;color:#e74c3c;font-size:.88rem;margin-bottom:.5rem;text-align:center"></p>
    <button type="submit" id="submit_btn" class="btn bp"
      style="width:100%;padding:.85rem;font-size:1rem;font-weight:700;border-radius:12px">
      &#128640; Запустить тест
    </button>
  </div>

</form>

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

</div>


<script src="/static/variants.js"></script>
<script src="/static/product-search.js"></script>
"""
    return render(html, 'tests')


def _init_variant_baseline(user_id, test_id, campaign_ids_str):
    """Фоновая задача: записывает baseline Performance API для варианта A при создании теста."""
    import time as _t, psycopg2, psycopg2.extras, requests as _req, io, csv as _csv, logging
    log = logging.getLogger('baseline_init')
    try:
        _t.sleep(2)  # Даём время на создание вариантов в БД

        # Получаем perf_key пользователя
        conn = db.get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT * FROM perf_keys WHERE user_id=%s LIMIT 1', (user_id,))
            perf = cur.fetchone()
            cur.execute('SELECT id FROM test_variants WHERE test_id=%s ORDER BY label LIMIT 1', (test_id,))
            variant_a = cur.fetchone()
        conn.close()

        if not perf or not variant_a:
            log.warning(f'baseline_init: нет perf_key или вариантов для теста #{test_id}')
            return

        # Получаем токен
        r = _req.post('https://api-performance.ozon.ru/api/client/token',
            json={'client_id': perf['client_id'], 'client_secret': perf['client_secret'],
                  'grant_type': 'client_credentials'}, timeout=10)
        if r.status_code != 200:
            log.warning(f'baseline_init: ошибка токена {r.status_code}')
            return
        token = r.json().get('access_token')
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

        today = _t.strftime('%Y-%m-%d')
        campaign_ids = [c.strip() for c in campaign_ids_str.split(',') if c.strip()]
        total_views = total_clicks = total_tocart = 0

        for cid in campaign_ids:
            # Запрашиваем статистику (async)
            r2 = _req.post('https://api-performance.ozon.ru/api/client/statistics',
                headers=headers,
                json={'campaigns': [str(cid)], 'dateFrom': today, 'dateTo': today, 'groupBy': 'HOUR'},
                timeout=15)
            if r2.status_code != 200:
                continue
            uuid = r2.json().get('UUID')
            if not uuid:
                continue
            # Ждём готовности
            link = None
            for _ in range(10):
                _t.sleep(3)
                r3 = _req.get(f'https://api-performance.ozon.ru/api/client/statistics/{uuid}',
                    headers=headers, timeout=15)
                if r3.json().get('state') == 'OK':
                    link = r3.json().get('link')
                    break
            if not link:
                continue
            # Скачиваем CSV
            r4 = _req.get(f'https://api-performance.ozon.ru{link}', headers=headers, timeout=15)
            if r4.status_code != 200:
                continue
            # Парсим строку Всего
            reader = _csv.reader(io.StringIO(r4.text), delimiter=';')
            headers_row = None
            for row in reader:
                if not row:
                    continue
                if headers_row is None:
                    headers_row = [h.strip() for h in row]
                    continue
                if row[0].startswith('Всего') or row[0].startswith('итого'):
                    try:
                        idx_v = next((i for i,h in enumerate(headers_row) if 'показ' in h.lower()), 3)
                        idx_c = next((i for i,h in enumerate(headers_row) if 'клик' in h.lower()), 4)
                        idx_t = next((i for i,h in enumerate(headers_row) if 'корзин' in h.lower()), 6)
                        def _si(r, i):
                            try: return int(float(r[i].replace(',','.').replace(' ','') or 0))
                            except: return 0
                        total_views  += _si(row, idx_v)
                        total_clicks += _si(row, idx_c)
                        total_tocart += _si(row, idx_t)
                    except Exception as e:
                        log.warning(f'baseline_init CSV parse: {e}')
                    break

        # Записываем baseline для варианта A
        conn = db.get_conn()
        with conn.cursor() as cur:
            cur.execute(
                'UPDATE test_variants SET perf_baseline_views=%s, perf_baseline_clicks=%s WHERE id=%s',
                (total_views, total_clicks, variant_a['id'])
            )
        conn.commit()
        conn.close()
        log.info(f'baseline_init: тест #{test_id} вариант A — baseline: показы={total_views} клики={total_clicks} корзина={total_tocart}')

    except Exception as e:
        log.error(f'baseline_init error: {e}')


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

    # ── Проверка баланса токенов ──────────────────────────────────────────
    service   = db.get_service('ab_test')
    test_cost = service['token_cost'] if service else 500
    balance   = db.get_balance(u['id'])
    if balance < test_cost:
        return redirect(
            f'/tests/new?err=Недостаточно+токенов.+Баланс:+{balance},+нужно:+{test_cost}.+'
            f'Пополните+баланс'
        )

    # ── Создаём тест и списываем токены ───────────────────────────────────
    test_id = db.create_test(u['id'], key['shop_name'], sku, product_name, strategy_str)
    db.spend_tokens(u['id'], test_cost, f'Запуск A/B теста #{test_id} ({sku})')
    campaign_ids = request.form.get('campaign_ids', '').strip()
    if campaign_ids:
        db.update_test_campaigns(test_id, u['id'], campaign_ids)
    for i, photo_url in enumerate(photos, start=1):
        label = chr(64 + i)   # A, B, C, …
        db.add_variant(test_id, label, photo_url)

    # Запускаем baseline в фоне — не блокируем пользователя
    if campaign_ids:
        t = threading.Thread(
            target=_init_variant_baseline,
            args=(u['id'], test_id, campaign_ids),
            daemon=True
        )
        t.start()

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
    campaign_ids_str = test.get('campaign_ids') or ''
    camp_short = ('ID: ' + campaign_ids_str[:20]) if campaign_ids_str else 'Не выбрана'
    info_items = [
        ('Вариантов',  str(len(variants)),              '&#127919;', '#667eea'),
        ('Показов',    f'{total_views:,}'.replace(',', ' '), '&#128065;', '#2196f3'),
        ('Кликов',     f'{total_clicks:,}'.replace(',', ' '), '&#128717;', '#27ae60'),
        ('В корзину',  str(sum(v.get('tocart',0) or 0 for v in variants)), '&#128722;', '#ff9800'),
        ('Общий CTR',  str(overall_ctr) + '%',          '&#128202;', '#9c27b0'),
        ('Магазин',    test['shop_name'],                '&#127978;', '#607d8b'),
        ('Стратегия',  format_strategy(test.get('strategy', '')), '&#9201;', '#455a64'),
        ('Запущен',    str(test['created_at'])[:10],    '&#128197;', '#795548'),
        ('Реклама',    camp_short,                      '&#128640;', '#e91e8c'),
    ]
    c += '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:.6rem;margin-bottom:1.75rem">'
    for lbl, val, icon, clr in info_items:
        c += (
            '<div style="background:#fff;border:1.5px solid #eee;border-radius:10px;padding:.7rem .85rem">'
            '<div style="font-size:.7rem;color:#aaa;font-weight:700;text-transform:uppercase;letter-spacing:.05em;margin-bottom:.25rem">' + lbl + '</div>'
            '<div style="font-size:.95rem;font-weight:700;color:' + clr + ';word-break:break-word;line-height:1.3">'
            + icon + ' ' + str(val) + '</div>'
            '</div>'
        )
    c += '</div>'

    # Карточки вариантов
    c += '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:1rem;margin-bottom:1.5rem">'
    for v in variants:
        views      = v.get('views', 0) or 0
        clicks     = v.get('clicks', 0) or 0
        tocart     = v.get('tocart', 0) or 0
        ctr        = v['ctr_calc']
        is_winner  = (v['label'] == best_label and ctr > 0)
        is_current = (v['label'] == (test.get('current_variant') or 'A'))
        bar_w      = int(ctr / max_ctr * 100) if max_ctr > 0 else 0

        # Цвет акцента карточки
        is_paused  = bool(v.get('paused'))
        if is_paused:
            accent = '#aaa'; border = '1.5px solid #ddd'
            hdr_bg = '#e0e0e0'; hdr_clr = '#888'
        elif is_winner and not is_running:
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
        if is_paused:
            badges += '<div style="position:absolute;top:.45rem;right:.45rem;background:rgba(0,0,0,.5);color:#fff;border-radius:20px;padding:.15rem .55rem;font-size:.7rem;font-weight:700">&#9208; Пауза</div>'
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
            'display:flex;align-items:center;justify-content:center;position:relative'
            + (';opacity:.45;filter:grayscale(60%)' if is_paused else '') + '">'
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
            + mrow('&#128722;', 'В корзину',  tocart)
            + mrow('&#128200;', 'CTR',        str(ctr) + '%')
            + '</div>'
            # Кнопка паузы — только для активного теста
            + ((
                '<form method="POST" action="/tests/' + str(test_id) + '/variant/' + str(v['id']) + '/pause" style="margin:0">'
                + ('<button class="btn" style="width:100%;margin-top:.4rem;background:#fff3cd;border:1px solid #ffc107;color:#856404;padding:.35rem;font-size:.78rem;font-weight:600">&#9208; На паузу</button>'
                   if not v.get('paused') else
                   '<button class="btn" style="width:100%;margin-top:.4rem;background:#d4edda;border:1px solid #c3e6cb;color:#155724;padding:.35rem;font-size:.78rem;font-weight:600">&#9654; Возобновить</button>')
                + '</form>'
            ) if is_running else '')
            + '</div>'  # end padding
            + '</div>'  # end card
        )

    c += '</div>'

    # -- Рекламные кампании
    perf_key = db.get_perf_key(u['id'])
    campaign_ids = test.get('campaign_ids') or ''
    selected_campaigns = [x.strip() for x in campaign_ids.split(',') if x.strip()]
    if is_running:
        if perf_key:
            camp_sku = test['sku']
            sel_json = str(selected_campaigns).replace("'", '"')
            c += (
                '<div class="box" style="margin-top:1.5rem">'
                '<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.5rem;margin-bottom:.75rem">'
                '<h3 style="margin:0">&#128640; Рекламные кампании для точного CTR</h3>'
                '<button type="button" onclick="var s=document.getElementById(\'camp_edit\');s.style.display=s.style.display===\'none\'?\'block\':\'none\'" '
                'style="background:#f0f2f5;border:1px solid #ddd;border-radius:8px;padding:.3rem .8rem;cursor:pointer;font-size:.82rem;color:#444">Изменить</button>'
                '</div>'
            )
            if selected_campaigns:
                c += ('<div style="background:#d4edda;border-radius:8px;padding:.65rem .9rem;font-size:.88rem;margin-bottom:.5rem">'
                      '&#10003; Подключено: <strong>' + ', '.join(selected_campaigns) + '</strong></div>')
            else:
                c += '<div style="background:#fff3cd;border-radius:8px;padding:.65rem .9rem;font-size:.88rem;margin-bottom:.5rem">&#9888; Кампания не выбрана — CTR считается приближённо</div>'

            c += (
                '<div id="camp_edit" style="display:none;margin-top:.75rem;border-top:1px solid #eee;padding-top:.75rem">'
                '<p style="font-size:.82rem;color:#666;margin-bottom:.6rem">Отметьте кампанию и нажмите «Сохранить изменения» — CTR будет считаться из неё.</p>'
                '<div id="camp_list2"><span style="color:#aaa;font-size:.88rem">&#9203; Загрузка кампаний...</span></div>'
                '<form method="POST" action="/tests/' + str(test_id) + '/campaigns" style="margin-top:.7rem">'
                '<input type="hidden" id="camp_ids_input" name="campaign_ids" value="' + campaign_ids + '">'
                '<button class="btn bp" style="font-size:.85rem;padding:.4rem .9rem">&#10003; Сохранить изменения</button>'
                '</form>'
                '</div>'
            )
            c += '''<script>
fetch("/api/perf-campaigns?sku=''' + camp_sku + '''")
.then(function(r){return r.json();})
.then(function(data){
  var el=document.getElementById("camp_list2");
  var sel=''' + sel_json + ''';
  if(!data.campaigns||!data.campaigns.length){
    el.innerHTML='<div style="background:#fff3cd;border-radius:8px;padding:.7rem;font-size:.88rem">&#9888; Кампаний с этим товаром не найдено. <a href="https://seller.ozon.ru/app/advertisement/product/cpc" target="_blank" style="color:#1e40af;font-weight:600">Создать кампанию</a></div>';
    return;
  }
  var html="";
  data.campaigns.forEach(function(camp){
    var chk=sel.indexOf(camp.id)>=0?"checked":"";
    html+='<label style="display:flex;align-items:center;gap:.6rem;margin-bottom:.5rem;cursor:pointer;font-size:.88rem"><input type="checkbox" value="'+camp.id+'" '+chk+' onchange="updC()" style="accent-color:#667eea"> '+camp.name+' <span style="color:#aaa;font-size:.78rem">(ID: '+camp.id+')</span></label>';
  });
  el.innerHTML=html;
})
.catch(function(){document.getElementById("camp_list2").innerHTML='<span style="color:#e74c3c;font-size:.88rem">Ошибка загрузки</span>';});
function updC(){
  var ids=[];
  document.querySelectorAll("#camp_list2 input:checked").forEach(function(x){ids.push(x.value);});
  document.getElementById("camp_ids_input").value=ids.join(",");
}
</script>
</div>'''
        else:
            c += ('<div class="box" style="margin-top:1.5rem;background:#fff8e1;border:1px solid #ffe082">'
                  '<p style="font-size:.9rem">&#128640; <strong>Хотите точный CTR?</strong> '
                  '<a href="/api-keys" style="color:#1e40af;font-weight:600">Подключите Performance API</a> '
                  'и выберите рекламную кампанию для этого теста.</p></div>')


    # Кнопка завершения
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




@tests_bp.route('/tests/<int:test_id>/variant/<int:variant_id>/pause', methods=['POST'])
def pause_variant(test_id, variant_id):
    u = me()
    if not u:
        return redirect('/login')
    ok, msg = db.toggle_variant_pause(variant_id, test_id, u['id'])
    if not ok:
        # Показываем ошибку через параметр (например «нельзя — осталось 2»)
        from flask import flash
        pass  # просто редиректим, toast не нужен
    return redirect(f'/tests/{test_id}')


@tests_bp.route('/tests/<int:test_id>/edit')
def edit_test(test_id):
    u = me()
    if not u:
        return redirect('/login')
    test = db.get_test(test_id, u['id'])
    if not test or test['status'] != 'running':
        return redirect('/tests')

    strategy = test.get('strategy') or 'time:30m'
    if strategy.startswith('time:'):
        cur_type, cur_val = 'time', strategy[5:].rstrip('m')
    elif strategy.startswith('views:'):
        cur_type, cur_val = 'views', strategy[6:]
    elif strategy.startswith('clicks:'):
        cur_type, cur_val = 'clicks', strategy[7:]
    else:
        cur_type, cur_val = 'time', '30'

    variants = db.get_variants(test_id)

    c = f'''
<div style="display:flex;align-items:center;gap:1rem;margin-bottom:1.5rem">
  <a href="/tests/{test_id}" class="btn" style="background:#f0f2f5;border:1px solid #ddd;color:#444">&#8592; Назад</a>
  <p class="ttl" style="margin:0">&#9998; Редактирование теста</p>
</div>
<div class="box">
  <p style="color:#666;margin-bottom:1.5rem">
    <strong>{test["product_name"]}</strong><br>
    <small style="color:#999">SKU: {test["sku"]} &middot; {test["shop_name"]}</small>
  </p>
  <form method="POST" action="/tests/{test_id}/edit">
    <div class="fg">
      <label>Стратегия ротации</label>

      <div id="s_time" onclick="selS('time')" style="border:2px solid {("#667eea" if cur_type=="time" else "#ddd")};border-radius:10px;padding:.85rem 1rem;margin-bottom:.6rem;cursor:pointer;background:{("#f5f3ff" if cur_type=="time" else "#fafafa")}">
        <div style="display:flex;align-items:center;gap:.6rem;margin-bottom:.3rem">
          <input type="radio" name="strategy" value="time" id="r_time" {"checked" if cur_type=="time" else ""} style="accent-color:#667eea">
          <label for="r_time" style="font-weight:600;cursor:pointer">&#9201; По времени</label>
        </div>
        <div id="s_time_f" style="display:{"flex" if cur_type=="time" else "none"};align-items:center;gap:.5rem;margin-top:.4rem">
          <span style="font-size:.9rem;color:#555">каждые</span>
          <input type="number" name="rotation_minutes" value="{cur_val if cur_type=="time" else "30"}" min="15" max="10080" class="fi" style="width:90px;padding:.4rem .6rem" onclick="event.stopPropagation()">
          <span style="font-size:.9rem;color:#555">минут</span>
        </div>
      </div>

      <div id="s_views" onclick="selS('views')" style="border:2px solid {("#667eea" if cur_type=="views" else "#ddd")};border-radius:10px;padding:.85rem 1rem;margin-bottom:.6rem;cursor:pointer;background:{("#f5f3ff" if cur_type=="views" else "#fafafa")}">
        <div style="display:flex;align-items:center;gap:.6rem;margin-bottom:.3rem">
          <input type="radio" name="strategy" value="views" id="r_views" {"checked" if cur_type=="views" else ""} style="accent-color:#667eea">
          <label for="r_views" style="font-weight:600;cursor:pointer">&#128065; По показам</label>
        </div>
        <div id="s_views_f" style="display:{"flex" if cur_type=="views" else "none"};align-items:center;gap:.5rem;margin-top:.4rem">
          <span style="font-size:.9rem;color:#555">каждые</span>
          <input type="number" name="rotation_views" value="{cur_val if cur_type=="views" else "100"}" min="50" max="10000" class="fi" style="width:100px;padding:.4rem .6rem" onclick="event.stopPropagation()">
          <span style="font-size:.9rem;color:#555">показов</span>
        </div>
      </div>

      <div id="s_clicks" onclick="selS('clicks')" style="border:2px solid {("#667eea" if cur_type=="clicks" else "#ddd")};border-radius:10px;padding:.85rem 1rem;margin-bottom:.6rem;cursor:pointer;background:{("#f5f3ff" if cur_type=="clicks" else "#fafafa")}">
        <div style="display:flex;align-items:center;gap:.6rem;margin-bottom:.3rem">
          <input type="radio" name="strategy" value="clicks" id="r_clicks" {"checked" if cur_type=="clicks" else ""} style="accent-color:#667eea">
          <label for="r_clicks" style="font-weight:600;cursor:pointer">&#128717; По кликам</label>
        </div>
        <div id="s_clicks_f" style="display:{"flex" if cur_type=="clicks" else "none"};align-items:center;gap:.5rem;margin-top:.4rem">
          <span style="font-size:.9rem;color:#555">каждые</span>
          <input type="number" name="rotation_clicks" value="{cur_val if cur_type=="clicks" else "20"}" min="20" max="10000" class="fi" style="width:100px;padding:.4rem .6rem" onclick="event.stopPropagation()">
          <span style="font-size:.9rem;color:#555">кликов</span>
        </div>
      </div>
    </div>
    <script>
    function selS(v){{['time','views','clicks'].forEach(function(x){{var b=document.getElementById('s_'+x),f=document.getElementById('s_'+x+'_f'),r=document.getElementById('r_'+x),on=x===v;r.checked=on;b.style.borderColor=on?'#667eea':'#ddd';b.style.background=on?'#f5f3ff':'#fafafa';if(f)f.style.display=on?'flex':'none';}});}}
    ['r_time','r_views','r_clicks'].forEach(function(id){{var el=document.getElementById(id);if(el)el.addEventListener('click',function(e){{e.stopPropagation();selS(this.value);}});}});
    </script>
    <div style="display:flex;gap:.75rem;margin-top:1rem">
      <button class="btn bp" style="flex:1">&#10003; Сохранить</button>
      <a href="/tests/{test_id}" class="btn" style="background:#f0f2f5;border:1px solid #ddd;color:#444;padding:.6rem 1.2rem">Отмена</a>
    </div>
  </form>
</div>
'''
    return render(c, 'tests')


@tests_bp.route('/tests/<int:test_id>/edit', methods=['POST'])
def save_test(test_id):
    u = me()
    if not u:
        return redirect('/login')
    test = db.get_test(test_id, u['id'])
    if not test or test['status'] != 'running':
        return redirect('/tests')
    strategy = request.form.get('strategy', 'time')
    if strategy == 'time':
        try: val = max(15, int(request.form.get('rotation_minutes', 30)))
        except: val = 30
        strategy_str = f'time:{val}m'
    elif strategy == 'views':
        try: val = max(50, int(request.form.get('rotation_views', 100)))
        except: val = 100
        strategy_str = f'views:{val}'
    elif strategy == 'clicks':
        try: val = max(20, int(request.form.get('rotation_clicks', 20)))
        except: val = 20
        strategy_str = f'clicks:{val}'
    else:
        strategy_str = 'time:30m'
    db.update_test_strategy(test_id, u['id'], strategy_str)
    return redirect(f'/tests/{test_id}')


@tests_bp.route('/tests/<int:test_id>/delete', methods=['POST'])
def delete_test(test_id):
    u = me()
    if not u:
        return redirect('/login')
    test = db.get_test(test_id, u['id'])
    if not test or test['status'] == 'running':
        return redirect('/tests')
    db.delete_test(test_id, u['id'])
    return redirect('/tests')



@tests_bp.route('/api/perf-campaigns')
def api_perf_campaigns():
    """Возвращает список активных рекламных кампаний для выбранного SKU."""
    u = me()
    if not u:
        return {'error': 'auth'}, 401

    sku = request.args.get('sku', '').strip()
    perf = db.get_perf_key(u['id'])
    if not perf:
        return {'campaigns': [], 'error': 'no_perf_key'}

    import requests as req
    try:
        # Получаем токен
        r = req.post(
            'https://api-performance.ozon.ru/api/client/token',
            json={
                'client_id':     perf['client_id'],
                'client_secret': perf['client_secret'],
                'grant_type':    'client_credentials'
            },
            timeout=10
        )
        if r.status_code != 200:
            return {'campaigns': [], 'error': f'token: {r.status_code}'}

        token = r.json().get('access_token')
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

        # Список активных кампаний
        r2 = req.get(
            'https://api-performance.ozon.ru/api/client/campaign',
            headers=headers,
            params={'state': 'CAMPAIGN_STATE_RUNNING'},
            timeout=10
        )
        if r2.status_code != 200:
            return {'campaigns': [], 'error': f'campaigns: {r2.status_code} {r2.text[:100]}'}

        campaigns = r2.json().get('list', [])

        if not sku:
            return {'campaigns': [
                {'id': str(c.get('id','')), 'name': c.get('title','') or c.get('name','')}
                for c in campaigns
            ]}

        # Шаг 1: получаем ВСЕ числовые product_id для этого offer_id через Seller API
        ozon_product_id = None
        all_product_ids = set()
        import logging
        log = logging.getLogger('perf_campaigns')
        try:
            seller_keys = db.get_keys(u['id'])
            active_key  = next((k for k in seller_keys if k['active']), None)
            if active_key:
                seller_hdrs = {
                    'Client-Id':    active_key['client_id'],
                    'Api-Key':      active_key['api_key'],
                    'Content-Type': 'application/json',
                }
                # v3/product/info/list — возвращает id, fbo_sku, fbs_sku
                rp = req.post(
                    'https://api-seller.ozon.ru/v3/product/info/list',
                    headers=seller_hdrs,
                    json={'offer_id': [sku]},
                    timeout=10
                )
                log.info(f'info/list {rp.status_code}: {rp.text[:600]}')
                if rp.status_code == 200:
                    rj = rp.json()
                    items = []
                    if 'result' in rj:
                        items = rj['result'].get('items') or []
                    elif 'items' in rj:
                        items = rj['items']
                    for item in items:
                        log.info(f'item keys: {list(item.keys())} values: {item}')
                        for key in ('id', 'product_id', 'fbo_sku', 'fbs_sku', 'sku'):
                            v = item.get(key)
                            if v: all_product_ids.add(str(v))

                if all_product_ids:
                    ozon_product_id = next(iter(all_product_ids))
                log.info(f'all_product_ids={all_product_ids}')
        except Exception as e:
            log.warning(f'product_id lookup failed: {e}')

        # Шаг 2: фильтруем кампании по /objects
        # Логика: fail-open — если /objects не работает, показываем кампанию.
        # Исключаем только если /objects вернул 200 и товара там точно нет.
        result = []
        debug_info = {'ozon_product_id': ozon_product_id, 'all_ids': list(all_product_ids), 'camps': {}}
        for camp in campaigns:
            camp_id   = str(camp.get('id', ''))
            camp_name = camp.get('title', '') or camp.get('name', '')
            include   = True   # по умолчанию включаем
            try:
                r3 = req.get(
                    f'https://api-performance.ozon.ru/api/client/campaign/{camp_id}/objects',
                    headers=headers,
                    timeout=8
                )
                log.info(f'  camp {camp_id} /objects status={r3.status_code} body={r3.text[:300]}')
                if r3.status_code == 200:
                    data3   = r3.json()
                    objects = (data3.get('list') or data3.get('items') or
                               (data3.get('result') or {}).get('items') or [])
                    if len(debug_info['camps']) < 3:
                        debug_info['camps'][camp_id] = {'status': 200, 'count': len(objects), 'sample': objects[:2]}
                    if objects:
                        # Объекты получены — фильтруем по совпадению
                        found = False
                        for obj in objects:
                            obj_id    = str(obj.get('id', ''))
                            obj_offer = str(obj.get('offer_id', ''))
                            obj_sku   = str(obj.get('sku', ''))
                            obj_name  = str(obj.get('name', ''))
                            # Сначала сравниваем по offer_id/sku/name
                            match = bool(sku) and sku in (obj_offer, obj_sku, obj_name)
                            # Если не совпало — сравниваем по числовому product_id (все варианты FBO/FBS)
                            if not match and obj_id:
                                match = obj_id in all_product_ids
                            log.info(f'    obj_id={obj_id} obj_offer={obj_offer} ozon_pid={ozon_product_id} match={match}')
                            if match:
                                found = True
                                break
                        include = found
                    else:
                        # Пустой /objects = кампания-автотаргетинг без конкретных товаров
                        # ("Продвижение в поиске — все товары") — исключаем
                        include = False
                    # /objects не вернул 200 — не можем проверить, включаем
                    if len(debug_info['camps']) < 3:
                        debug_info['camps'][camp_id] = {'status': r3.status_code, 'body': r3.text[:100]}
            except Exception as e:
                log.warning(f'  camp {camp_id} objects error: {e}')
                if len(debug_info['camps']) < 3:
                    debug_info['camps'][camp_id] = {'error': str(e)[:80]}
                # Ошибка — не можем проверить, включаем
            if include:
                result.append({'id': camp_id, 'name': camp_name})

        log.info(f'result campaigns: {[r["name"] for r in result]}')
        return {'campaigns': result, '_debug': debug_info}

    except Exception as e:
        return {'campaigns': [], 'error': str(e)[:100]}



@tests_bp.route('/tests/<int:test_id>/campaigns', methods=['POST'])
def save_campaigns(test_id):
    u = me()
    if not u:
        return redirect('/login')
    campaign_ids = request.form.get('campaign_ids', '').strip()
    db.update_test_campaigns(test_id, u['id'], campaign_ids)
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
