var ALL_PRODUCTS = [];
var LOADED = false;

function loadProducts() {
  if (LOADED) return;
  var loading = document.getElementById('prod_loading');
  if (loading) loading.style.display = 'block';
  fetch('/api/products')
    .then(function(r){ return r.json(); })
    .then(function(data){
      ALL_PRODUCTS = data;
      LOADED = true;
      if (loading) loading.style.display = 'none';
      var hint = document.getElementById('prod_hint_text');
      if (hint) hint.textContent = 'Загружено ' + data.length + ' товаров с остатками';
      renderDropdown('');
    }).catch(function(){
      if (loading) loading.style.display = 'none';
    });
}

function renderDropdown(q) {
  var dd = document.getElementById('prod_dropdown');
  if (!dd) return;
  var list = ALL_PRODUCTS;
  if (q) {
    var ql = q.toLowerCase();
    list = list.filter(function(p){
      return p.sku.toLowerCase().indexOf(ql) >= 0 || p.name.toLowerCase().indexOf(ql) >= 0;
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
      + '<div style="font-size:.78rem;color:#888;margin-top:.15rem">Артикул: ' + p.sku + '</div>'
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

function clearProduct() {
  document.getElementById('product_val').value = '';
  document.getElementById('prod_selected').style.display = 'none';
  document.getElementById('prod_search').focus();
}

function checkBySku() {
  var sku = document.getElementById('prod_search').value.trim();
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
    loadProducts();
    setTimeout(function(){ renderDropdown(srch.value); }, 200);
  });
  srch.addEventListener('input', function(){ renderDropdown(this.value); });
  document.addEventListener('click', function(e){
    var dd = document.getElementById('prod_dropdown');
    if (dd && !srch.contains(e.target) && !dd.contains(e.target)) {
      dd.style.display = 'none';
    }
  });
});
