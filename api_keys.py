from flask import Blueprint, request, redirect
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

    msg        = request.args.get('msg', '')
    err        = request.args.get('err', '')
    saved_shop = request.args.get('shop', '')
    saved_cid  = request.args.get('cid', '')
    keys       = db.get_keys(u['id'])
    perf_keys  = db.get_perf_keys(u['id'])
    cnt        = len(keys)

    c  = '<p class="ttl">API ключи Озона</p>'
    c += alert(msg, 'ok')
    c += alert(err, 'er')

    # ── Единая таблица подключений ─────────────────────────────────────────
    c += '<div class="box">'
    '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem">'
    '<h2 style="margin:0">Ваши подключения</h2>'
    '<div style="display:flex;gap:.5rem">'
    '<a href="#seller_form" class="btn" style="font-size:.82rem;padding:.35rem .8rem;background:#f5f3ff;border:1px solid #667eea;color:#667eea">+ Seller API</a>'
    '<a href="#perf_form" class="btn" style="font-size:.82rem;padding:.35rem .8rem;background:#d4edda;border:1px solid #27ae60;color:#155724">+ Performance API</a>'
    '</div></div>'
    if keys or perf_keys:
        # Seller API строки
        for k in keys:
            badge  = '<span class="bg g" style="font-size:.75rem">Активен</span>' if k['active'] else '<span class="bg r" style="font-size:.75rem">Ошибка</span>'
            added  = str(k['added_at'])[:10] if k.get('added_at') else '-'
            c += '<div style="border:1px solid #e8e8e8;border-radius:12px;margin-bottom:1rem;overflow:hidden">'
            # Заголовок магазина
            c += ('<div style="background:#f5f3ff;padding:.75rem 1rem;border-bottom:1px solid #e8e8e8;'
                  'display:flex;justify-content:space-between;align-items:center">'
                  '<div style="font-weight:700;font-size:1rem">&#127978; ' + k['shop_name'] + '</div>'
                  + badge + '</div>')
            # Seller API
            c += ('<div style="padding:.75rem 1rem;display:flex;justify-content:space-between;'
                  'align-items:center;border-bottom:1px solid #f0f0f0">'
                  '<div>'
                  '<div style="font-size:.85rem;font-weight:600;color:#444">&#128273; Seller API</div>'
                  '<div style="font-size:.8rem;color:#888">Client ID: ' + k['client_id'] +
                  ' &nbsp;&middot;&nbsp; Key: ....' + k['hint'] +
                  ' &nbsp;&middot;&nbsp; Добавлен: ' + added + '</div>')
            if k.get('check_msg'):
                c += '<div style="font-size:.78rem;color:#666">' + k['check_msg'] + '</div>'
            c += ('</div>'
                  '<div style="display:flex;gap:.4rem">'
                  '<form method="POST" action="/api-keys/recheck/' + str(k['id']) + '">'
                  '<button class="btn bs" style="font-size:.8rem;padding:.3rem .7rem;background:#e8f4fd;color:#1e40af;border:1px solid #bfdbfe" title="Перепроверить">&#128260;</button>'
                  '</form>'
                  '<form method="POST" action="/api-keys/del/' + str(k['id']) + '">'
                  '<button class="btn bd bs" style="font-size:.8rem;padding:.3rem .7rem" onclick="showConfirm(this.closest(&apos;form&apos;),&apos;Удалить подключение?&apos;,&apos;Это действие нельзя отменить.&apos;);return false;" title="Удалить">&#10005;</button>'
                  '</form>'
                  '</div></div>')
            c += '</div>'

        # Performance API строки
        if perf_keys:
            for pk in perf_keys:
                pk_added = str(pk['added_at'])[:10]
                c += ('<div style="border:1px solid #c3e6cb;border-radius:12px;margin-bottom:1rem;overflow:hidden">'
                      '<div style="background:#d4edda;padding:.75rem 1rem;border-bottom:1px solid #c3e6cb;'
                      'display:flex;justify-content:space-between;align-items:center">'
                      '<div style="font-weight:700;font-size:1rem">&#128640; Performance API</div>'
                      '<span class="bg g" style="font-size:.75rem">Подключён</span></div>'
                      '<div style="padding:.75rem 1rem;display:flex;justify-content:space-between;align-items:center">'
                      '<div>'
                      '<div style="font-size:.8rem;color:#888">Client ID: ' + pk['client_id'][:50] + '...</div>'
                      '<div style="font-size:.8rem;color:#888">Добавлен: ' + pk_added + '</div>'
                      '</div>'
                      '<form method="POST" action="/api-keys/perf/del/' + str(pk['id']) + '">'
                      '<button class="btn bd bs" style="font-size:.8rem;padding:.3rem .7rem" '
                      'onclick="showConfirm(this.closest(&apos;form&apos;),&apos;Удалить Performance API?&apos;,&apos;CTR по рекламным кампаниям перестанет собираться.&apos;);return false;" title="Удалить">&#10005;</button>'
                      '</form>'
                      '</div></div>')
        else:
            c += ('<div style="border:1px dashed #ffc107;border-radius:12px;padding:1rem;margin-bottom:1rem;'
                  'background:#fff8e1;display:flex;justify-content:space-between;align-items:center">'
                  '<div>'
                  '<div style="font-weight:600;color:#856404">&#128640; Performance API не подключён</div>'
                  '<div style="font-size:.85rem;color:#666">Нужен для точного CTR через рекламные кампании</div>'
                  '</div>'
                  '<a href="#perf_form" class="btn bp" style="white-space:nowrap">Подключить</a>'
                  '</div>')
    else:
        c += '<div class="empty"><p style="font-size:2rem">&#128273;</p><p style="margin-top:1rem">Нет добавленных ключей</p></div>'
    c += '</div>'

    # ── Форма добавления Seller API ────────────────────────────────────────
    c += '<div class="box" id="seller_form"><h2>Добавить Seller API</h2>'
    c += (
        '<div class="tip" style="margin-bottom:1rem">'
        '&#128273; <strong>Где взять:</strong> '
        '<a href="https://seller.ozon.ru/app/settings/api-keys" target="_blank" '
        'style="color:#1e40af;font-weight:600">seller.ozon.ru</a>'
        ' &rarr; Учётная запись (&#128100; в правом верхнем углу) &rarr; Настройки &rarr; Seller API &rarr; «Сгенерировать ключ»'
        '</div>'
        '<div style="background:#fff8e1;border:1px solid #ffe082;border-radius:10px;padding:1rem;margin-bottom:1rem">'
        '<p style="font-weight:700;margin-bottom:.6rem;color:#856404;font-size:.9rem">&#9888; Выберите права:</p>'
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:.3rem;font-size:.85rem">'
        '<div><span style="color:#27ae60;font-weight:700">&#10003;</span> <strong>Product read-only</strong></div>'
        '<div><span style="color:#27ae60;font-weight:700">&#10003;</span> <strong>Warehouse</strong></div>'
        '<div><span style="color:#27ae60;font-weight:700">&#10003;</span> <strong>Report</strong></div>'
        '<div><span style="color:#27ae60;font-weight:700">&#10003;</span> <strong>Product</strong></div>'
        '</div></div>'
    )
    if cnt < MAX_API_KEYS:
        c += (
            '<form method="POST" action="/api-keys/add">'
            '<div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem">'
            '<div class="fg"><label>Название магазина</label>'
            '<input type="text" name="shop" class="fi" placeholder="Мой магазин" required maxlength="100" value="' + saved_shop + '">'
            '</div>'
            '<div class="fg"><label>Client ID</label>'
            '<input type="text" name="cid" class="fi" placeholder="123456789" required maxlength="50" value="' + saved_cid + '">'
            '</div></div>'
            '<div class="fg"><label style="display:flex;justify-content:space-between">'
            '<span>API Key</span>'
            '<span onclick="togglePw(\'akey_field\',this)" style="font-size:.78rem;color:#aaa;cursor:pointer;user-select:none">показать</span>'
            '</label>'
            '<input type="password" id="akey_field" name="akey" class="fi" '
            'placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" required maxlength="200">'
            '</div>'
            '<button class="btn bp" onclick="this.disabled=true;this.innerHTML=\'&#9203; Проверка...\';">Проверить и сохранить</button>'
            '</form>'
        )
    else:
        c += alert(f'Достигнут лимит {MAX_API_KEYS} ключей', 'wn')
    c += '</div>'

    # ── Форма добавления Performance API ──────────────────────────────────
    c += '<div class="box" id="perf_form"><h2>&#128640; Добавить Performance API</h2>'
    c += (
        '<div class="tip" style="margin-bottom:1rem">'
        'Performance API даёт точный CTR по каждому рекламному объявлению.<br>'
        '<a href="https://seller.ozon.ru/app/settings/performance-api" target="_blank" '
        'style="color:#1e40af;font-weight:600">'
        'seller.ozon.ru → Учётная запись → Настройки → Performance API → Создать аккаунт → Добавить ключ'
        '</a>'
        '</div>'
        '<form method="POST" action="/api-keys/perf/add">'
        '<div class="fg"><label>Client ID</label>'
        '<input type="text" name="perf_client_id" class="fi" '
        'placeholder="94436566-...@advertising.performance.ozon.ru" required maxlength="200">'
        '<div class="hn">Формат: 12345-...@advertising.performance.ozon.ru</div></div>'
        '<div class="fg"><label>Client Secret</label>'
        '<input type="password" name="perf_client_secret" class="fi" '
        'placeholder="Ваш Client Secret" required maxlength="300">'
        '<div class="hn">Хранится безопасно</div></div>'
        '<button class="btn bp" onclick="this.disabled=true;this.innerHTML=\'&#9203; Подключение...\';">Сохранить Performance API ключ</button>'
        '</form>'
    )
    c += '</div>'
    c += ('<div id="cm" style="display:none;position:fixed;inset:0;z-index:9999;background:rgba(15,15,30,.6);backdrop-filter:blur(4px);align-items:center;justify-content:center;padding:1rem">'
           '<div style="background:#fff;border-radius:20px;padding:2rem 2rem 1.5rem;width:360px;max-width:100%;box-shadow:0 24px 80px rgba(0,0,0,.3);position:relative">'
           '<div style="position:absolute;top:0;left:0;right:0;height:4px;background:linear-gradient(90deg,#e53e3e,#fc8181);border-radius:20px 20px 0 0"></div>'
           '<div style="width:52px;height:52px;border-radius:50%;background:#fff5f5;display:flex;align-items:center;justify-content:center;margin-bottom:1rem">'
           '<span style="font-size:1.4rem">&#128465;</span></div>'
           '<p style="font-weight:700;font-size:1.1rem;color:#1a1a2e;margin:0 0 .4rem" id="cm_t"></p>'
           '<p style="font-size:.9rem;color:#888;margin:0 0 1.75rem;line-height:1.5" id="cm_s"></p>'
           '<div style="display:flex;gap:.75rem">'
           '<button onclick="closeCM()" style="flex:1;background:#f7f8fa;border:1.5px solid #e2e8f0;color:#555;border-radius:10px;padding:.6rem 1rem;cursor:pointer;font-size:.9rem;font-weight:500">Отмена</button>'
           '<button id="cm_ok" style="flex:1;background:linear-gradient(135deg,#e53e3e,#c53030);color:#fff;border:none;border-radius:10px;padding:.6rem 1rem;font-weight:600;cursor:pointer;font-size:.9rem;box-shadow:0 4px 12px rgba(229,62,62,.35)">Удалить</button>'
           '</div></div></div>'
           '<style>#cm>div{animation:cmIn .2s cubic-bezier(.34,1.56,.64,1)}@keyframes cmIn{from{opacity:0;transform:scale(.88)}to{opacity:1;transform:scale(1)}}</style>'
           '<script>'
           'var _cmf=null;'
           'function showConfirm(f,t,s){'
           'var m=document.getElementById("cm");'
           'document.getElementById("cm_t").textContent=t;'
           'document.getElementById("cm_s").textContent=s;'
           '_cmf=f;m.style.display="flex";}'
           'function closeCM(){document.getElementById("cm").style.display="none";_cmf=null;}'
           'document.addEventListener("DOMContentLoaded",function(){'
           'var ok=document.getElementById("cm_ok");'
           'var cm=document.getElementById("cm");'
           'if(ok)ok.addEventListener("click",function(){if(_cmf){var f=_cmf;closeCM();f.submit();}});'
           'if(cm)cm.addEventListener("click",function(e){if(e.target===this)closeCM();});'
           '});'
           'document.addEventListener("keydown",function(e){if(e.key==="Escape")closeCM();});'
           '</script>')
    return render(c, 'keys')


# ── Seller API роуты ───────────────────────────────────────────────────────

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
    existing = db.get_keys(u['id'])
    if any(k['client_id'] == cid for k in existing):
        return redirect(f'/api-keys?err=Магазин+с+таким+Client+ID+уже+добавлен&shop={shop}&cid={cid}')
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
    key  = next((k for k in keys if k['id'] == key_id), None)
    if not key:
        return redirect('/api-keys?err=Ключ+не+найден')
    ok, msg = verify_ozon(key['client_id'], key['api_key'])
    with db.get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute('UPDATE api_keys SET active=%s, check_msg=%s WHERE id=%s AND user_id=%s',
                        (ok, msg, key_id, u['id']))
        conn.commit()
    if ok:
        return redirect('/api-keys?msg=Ключ+успешно+проверен')
    return redirect('/api-keys?err=Проверка+не+прошла:+' + msg.replace(' ', '+'))


@api_keys_bp.route('/api-keys/del/<int:key_id>', methods=['POST'])
def delete_key(key_id):
    u = me()
    if not u:
        return redirect('/login')
    db.delete_key(key_id, u['id'])
    return redirect('/api-keys?msg=Подключение+удалено')


# ── Performance API роуты ──────────────────────────────────────────────────

@api_keys_bp.route('/api-keys/perf/add', methods=['POST'])
def add_perf_key():
    u = me()
    if not u:
        return redirect('/login')
    client_id     = request.form.get('perf_client_id', '').strip()
    client_secret = request.form.get('perf_client_secret', '').strip()
    if not client_id or not client_secret:
        return redirect('/api-keys?err=Заполните+оба+поля+Performance+API')
    import requests as req
    try:
        r = req.post(
            'https://api-performance.ozon.ru/api/client/token',
            json={'client_id': client_id, 'client_secret': client_secret,
                  'grant_type': 'client_credentials'},
            timeout=10
        )
        if r.status_code == 200 and r.json().get('access_token'):
            db.save_perf_key(u['id'], client_id, client_secret)
            return redirect('/api-keys?msg=Performance+API+успешно+подключён')
        else:
            return redirect('/api-keys?err=Ошибка+Performance+API:+' + r.text[:80].replace(' ', '+'))
    except Exception as e:
        return redirect('/api-keys?err=Ошибка+подключения:+' + str(e)[:80].replace(' ', '+'))


@api_keys_bp.route('/api-keys/perf/del/<int:perf_id>', methods=['POST'])
def del_perf_key(perf_id):
    u = me()
    if not u:
        return redirect('/login')
    db.delete_perf_key_by_id(perf_id, u['id'])
    return redirect('/api-keys?msg=Performance+API+ключ+удалён')
