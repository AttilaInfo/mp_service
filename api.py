"""
api.py — JS-файлы и API-эндпоинты (товары, поиск по SKU).
"""
from flask import Blueprint, redirect, request
import requests as req

import database as db
from auth import me
from config import OZON_API_URL

api_bp = Blueprint('api', __name__)


@api_bp.route('/static/variants.js')
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
    + '<input type="hidden" name="photo_' + variantCount + '" value="' + (url || '') + '">';
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
    var inp = card.querySelector('input[type="hidden"][name^="photo_"]');
    if (inp) inp.name = 'photo_' + num;
  }

  var lbl = document.getElementById('variant_count_label');
  if (lbl) lbl.textContent = 'Добавлено: ' + n + ' из ' + MAX_VARIANTS;
  var b = document.getElementById('add_variant_btn');
  if (b) b.style.opacity = n >= MAX_VARIANTS ? '.4' : '1';
  var notice = document.getElementById('files_notice');
  // не сбрасываем предупреждение здесь
}

// ── Прогресс-бар загрузки ─────────────────────────────────────────────────
function setProgress(done, total, errors) {
  var notice = document.getElementById('files_notice');
  if (!notice) return;
  if (total === 0) { notice.innerHTML = ''; return; }
  var pct = Math.round((done / total) * 100);
  var color = errors > 0 ? '#e74c3c' : '#667eea';
  var statusText = done < total
    ? 'Загружаем ' + done + ' из ' + total + '...'
    : (errors > 0
        ? '&#9888; ' + errors + ' фото не загрузились'
        : '&#10003; Все фото загружены');
  var statusColor = done < total ? '#555' : (errors > 0 ? '#e74c3c' : '#27ae60');
  notice.innerHTML =
    '<div style="width:100%">'
    + '<div style="display:flex;justify-content:space-between;margin-bottom:.3rem;font-size:.85rem;font-weight:600">'
    + '<span style="color:' + statusColor + '">' + statusText + '</span>'
    + '<span style="color:#888">' + pct + '%</span>'
    + '</div>'
    + '<div style="background:#e9ecef;border-radius:99px;height:6px;overflow:hidden">'
    + '<div style="height:100%;border-radius:99px;background:' + color + ';width:' + pct + '%;transition:width .25s ease"></div>'
    + '</div>'
    + '</div>';
}

// ── Сжатие одного файла → Blob (Promise) ──────────────────────────────────
function compressFile(file) {
  return new Promise(function(resolve, reject) {
    var reader = new FileReader();
    reader.onerror = reject;
    reader.onload = function(e) {
      var img = new Image();
      img.onerror = reject;
      img.onload = function() {
        var MAX = 1600;
        var w = img.width, h = img.height;
        if (w > MAX || h > MAX) {
          var ratio = Math.min(MAX / w, MAX / h);
          w = Math.round(w * ratio);
          h = Math.round(h * ratio);
        }
        var canvas = document.createElement('canvas');
        canvas.width = w; canvas.height = h;
        canvas.getContext('2d').drawImage(img, 0, 0, w, h);
        canvas.toBlob(function(blob) {
          resolve({ blob: blob, preview: e.target.result });
        }, 'image/jpeg', 0.85);
      };
      img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  });
}

// ── Параллельная загрузка всех фото сразу ─────────────────────────────────
function handleFiles(files) {
  if (!files || !files.length) return;
  var notice = document.getElementById('files_notice');
  if (notice) notice.innerHTML = '';

  var available = MAX_VARIANTS - variantCount;
  if (available <= 0) {
    showToast('Достигнут лимит 10 вариантов', 'error');
    return;
  }
  var toAdd   = Math.min(files.length, available);
  var skipped = files.length - toAdd;
  if (skipped > 0) {
    showToast('Добавлено ' + toAdd + ' из ' + files.length + ' — лимит 10 вариантов', 'warning');
  }

  var done = 0, errors = 0;
  setProgress(0, toAdd, 0);

  // Шаг 1: сразу добавляем все карточки с превью и запоминаем номера
  var tasks = [];
  for (var i = 0; i < toAdd; i++) {
    // Добавляем карточку-заглушку (превью появится после сжатия)
    addVariantWithUrl('', '', false);
    tasks.push({ cardNum: variantCount, file: files[i] });
  }

  // Шаг 2: параллельно сжимаем + загружаем все файлы
  tasks.forEach(function(task) {
    compressFile(task.file)
      .then(function(result) {
        // Ставим превью в карточку
        var prev = document.getElementById('preview_' + task.cardNum);
        if (prev) prev.innerHTML = '<img src="' + result.preview + '" style="width:100%;height:100%;object-fit:cover">';

        // Загружаем на сервер
        var fd = new FormData();
        fd.append('photo', result.blob, 'photo.jpg');
        return fetch('/api/upload-photo', { method: 'POST', body: fd }).then(function(r) { return r.json(); });
      })
      .then(function(data) {
        done++;
        if (data.url) {
          var inp = document.querySelector('input[name="photo_' + task.cardNum + '"]');
          if (inp) inp.value = data.url;
        } else {
          errors++;
        }
        setProgress(done, toAdd, errors);
      })
      .catch(function() {
        done++; errors++;
        setProgress(done, toAdd, errors);
      });
  });
}

function handleDrop(e) {
  e.preventDefault();
  handleFiles(e.dataTransfer.files);
}

// ── Toast-уведомления (вместо alert) ──────────────────────────────────────
function showToast(msg, type) {
  var existing = document.getElementById('form_toast');
  if (existing) existing.remove();
  var colors = {
    error:   { bg: '#fff0f0', border: '#ffb3b3', icon: '&#9888;', text: '#c0392b' },
    warning: { bg: '#fff8e1', border: '#ffe082', icon: '&#9201;', text: '#7d5a00' },
    success: { bg: '#f0fdf4', border: '#86efac', icon: '&#10003;', text: '#166534' }
  };
  var c = colors[type] || colors.error;
  var toast = document.createElement('div');
  toast.id = 'form_toast';
  toast.style.cssText = [
    'position:fixed', 'bottom:2rem', 'left:50%', 'transform:translateX(-50%)',
    'background:' + c.bg, 'border:1.5px solid ' + c.border,
    'color:' + c.text, 'font-weight:600', 'font-size:.95rem',
    'padding:.85rem 1.4rem', 'border-radius:12px',
    'box-shadow:0 4px 24px rgba(0,0,0,.13)',
    'z-index:9999', 'display:flex', 'align-items:center', 'gap:.6rem',
    'max-width:90vw', 'animation:toastIn .2s ease'
  ].join(';');
  toast.innerHTML = '<span style="font-size:1.15rem">' + c.icon + '</span><span>' + msg + '</span>';
  if (!document.getElementById('toast_style')) {
    var s = document.createElement('style');
    s.id = 'toast_style';
    s.textContent = '@keyframes toastIn{from{opacity:0;transform:translateX(-50%) translateY(12px)}to{opacity:1;transform:translateX(-50%) translateY(0)}}';
    document.head.appendChild(s);
  }
  document.body.appendChild(toast);
  clearTimeout(window._toastTimer);
  window._toastTimer = setTimeout(function(){ if(toast.parentNode) toast.remove(); }, 4000);
}

// ── Валидация формы перед отправкой ───────────────────────────────────────
document.addEventListener('DOMContentLoaded', function() {
  var form = document.getElementById('test_form');
  if (!form) return;
  form.addEventListener('submit', function(e) {

    // 1. Проверяем товар
    var product = document.getElementById('product_val');
    if (!product || !product.value.trim()) {
      e.preventDefault();
      showToast('Выберите товар для теста', 'error');
      var ps = document.getElementById('prod_search');
      if (ps) ps.focus();
      return;
    }

    // 2. Берём только карточки реально в гриде
    var grid = document.getElementById('variants_grid');
    var cards = grid ? Array.from(grid.children) : [];
    var filled = 0, uploading = 0;
    cards.forEach(function(card) {
      var inp = card.querySelector('input[type="hidden"][name^="photo_"]');
      if (!inp) return;
      if (inp.value.trim()) { filled++; }
      else { uploading++; }
    });

    if (filled < 2) {
      e.preventDefault();
      showToast('Добавьте минимум 2 варианта фото', 'error');
      return;
    }
    if (uploading > 0) {
      e.preventDefault();
      showToast('Фото ещё загружаются — подождите пару секунд ⏳', 'warning');
      return;
    }

    // 3. Всё ок — индикатор загрузки на кнопке
    var btn = form.querySelector('button.btn.bp');
    if (btn) {
      btn.disabled = true;
      btn.style.opacity = '.7';
      btn.innerHTML = '⏳ Создаём тест...';
    }
  });
});

    """, mimetype='application/javascript')


@api_bp.route('/static/product-search.js')
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



@api_bp.route('/api/products')
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

@api_bp.route('/api/debug-product')
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


@api_bp.route('/api/check-sku')
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
