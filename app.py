from flask import Flask, request, redirect, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os, bcrypt, requests, re
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-me-in-production')

limiter = Limiter(app=app, key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"], storage_uri="memory://")

USERS = {}
MAX_KEYS = 10

# ── helpers ────────────────────────────────────────────────────────────────
def hash_pw(pw):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def check_pw(pw, hashed):
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False

def valid_email(e):
    return bool(re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', e))

def clean(t, n=200):
    return str(t).strip()[:n].replace('<','').replace('>','').replace('"','')

def me():
    e = session.get('email')
    return USERS.get(e) if e else None

def verify_ozon(cid, akey):
    try:
        r = requests.post(
            'https://api-seller.ozon.ru/v1/warehouse/list',
            headers={'Client-Id': cid, 'Api-Key': akey, 'Content-Type': 'application/json'},
            json={}, timeout=8)
        if r.status_code == 200: return True, 'Ключ работает'
        if r.status_code == 401: return False, 'Неверный Client ID или API Key'
        if r.status_code == 403: return False, 'Нет прав — проверьте настройки ключа'
        return False, 'Ошибка Озона: ' + str(r.status_code)
    except requests.exceptions.Timeout:
        return False, 'Озон не отвечает (timeout)'
    except requests.exceptions.ConnectionError:
        return False, 'Нет соединения с Озоном'
    except Exception as ex:
        return False, 'Ошибка: ' + str(ex)[:80]

# ── HTML builder ───────────────────────────────────────────────────────────
CSS = (
    '*{margin:0;padding:0;box-sizing:border-box}'
    'body{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;background:#f0f2f5;color:#1a1a2e;min-height:100vh}'
    'a{text-decoration:none;color:inherit}'
    '.hdr{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;padding:1rem 2rem;'
    'display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.8rem;box-shadow:0 2px 8px rgba(0,0,0,.2)}'
    '.hdr h1{font-size:1.4rem}'
    '.hdr nav{display:flex;gap:.5rem;flex-wrap:wrap}'
    '.nb{padding:.5rem 1rem;border-radius:8px;background:rgba(255,255,255,.15);color:#fff;'
    'border:1px solid rgba(255,255,255,.3);font-size:.9rem;transition:.2s;text-decoration:none}'
    '.nb:hover,.nb.on{background:#fff;color:#667eea}'
    '.wrap{max-width:1100px;margin:2rem auto;padding:0 1rem}'
    '.ttl{font-size:1.6rem;font-weight:700;margin-bottom:1.5rem}'
    '.box{background:#fff;border-radius:12px;padding:1.5rem;box-shadow:0 2px 8px rgba(0,0,0,.07);margin-bottom:1.5rem}'
    '.box h2{font-size:1.1rem;font-weight:700;margin-bottom:1.2rem}'
    '.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1.2rem;margin-bottom:2rem}'
    '.card{background:#fff;border-radius:12px;padding:1.5rem;box-shadow:0 2px 8px rgba(0,0,0,.07);'
    'border-left:4px solid #667eea;display:flex;align-items:center;gap:1rem}'
    '.card .ic{font-size:2rem}'
    '.card .n{font-size:1.8rem;font-weight:700;color:#667eea}'
    '.card .lb{font-size:.85rem;color:#666;margin-top:.2rem}'
    '.fg{margin-bottom:1.2rem}'
    '.fg label{display:block;margin-bottom:.4rem;font-weight:600;font-size:.9rem;color:#444}'
    '.fg input{width:100%;padding:.75rem 1rem;border:2px solid #e0e0e0;border-radius:8px;font-size:.95rem;transition:.2s}'
    '.fg input:focus{outline:none;border-color:#667eea;box-shadow:0 0 0 3px rgba(102,126,234,.1)}'
    '.hn{font-size:.8rem;color:#888;margin-top:.3rem}'
    '.btn{padding:.75rem 1.5rem;border:none;border-radius:8px;cursor:pointer;font-size:.95rem;'
    'font-weight:600;transition:.2s;display:inline-flex;align-items:center;gap:.4rem}'
    '.bp{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff}'
    '.bp:hover{opacity:.9;transform:translateY(-1px);box-shadow:0 4px 12px rgba(102,126,234,.4)}'
    '.bd{background:#e74c3c;color:#fff}'
    '.bd:hover{background:#c0392b}'
    '.bs{padding:.4rem .9rem;font-size:.85rem}'
    '.al{padding:1rem 1.2rem;border-radius:8px;margin-bottom:1.2rem;font-size:.9rem}'
    '.ok{background:#d4edda;color:#155724;border-left:4px solid #28a745}'
    '.er{background:#f8d7da;color:#721c24;border-left:4px solid #dc3545}'
    '.wn{background:#fff3cd;color:#856404;border-left:4px solid #ffc107}'
    '.kc{background:#f8f9fa;border:1px solid #e0e0e0;border-radius:10px;padding:1.2rem;'
    'margin-bottom:1rem;display:flex;align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap}'
    '.kn{font-weight:700;margin-bottom:.4rem}'
    '.ki{font-family:monospace;font-size:.82rem;color:#555;background:#e9ecef;'
    'padding:.2rem .5rem;border-radius:4px;display:inline-block;margin:.2rem .3rem 0 0}'
    '.bg{padding:.25rem .7rem;border-radius:20px;font-size:.78rem;font-weight:600}'
    '.g{background:#d4edda;color:#155724}'
    '.r{background:#f8d7da;color:#721c24}'
    '.dot{width:9px;height:9px;border-radius:50%;display:inline-block;margin-right:.3rem}'
    '.dg{background:#2ecc71}.dr{background:#e74c3c}'
    '.tip{background:#e8f4fd;border-left:4px solid #3b82f6;padding:1rem 1.2rem;border-radius:8px;color:#1e40af;font-size:.9rem}'
    '.empty{text-align:center;padding:3rem;color:#aaa}'
    '.aw{min-height:100vh;display:flex;align-items:center;justify-content:center;'
    'background:linear-gradient(135deg,#667eea,#764ba2);padding:1rem}'
    '.ac{background:#fff;border-radius:16px;padding:2.5rem;width:100%;max-width:420px;box-shadow:0 20px 60px rgba(0,0,0,.2)}'
    '.ac h1{text-align:center;color:#667eea;margin-bottom:.4rem}'
    '.sub{text-align:center;color:#888;margin-bottom:1.8rem;font-size:.9rem}'
    '.al2{text-align:center;margin-top:1rem;font-size:.9rem;color:#667eea;cursor:pointer}'
    '.al2:hover{text-decoration:underline}'
    '.tc{display:grid;grid-template-columns:1fr 1fr;gap:1rem}'
    'table{width:100%;border-collapse:collapse}'
    'th{background:#f8f9fa;padding:.75rem 1rem;text-align:left;font-size:.85rem;color:#666;font-weight:600}'
    'td{padding:.75rem 1rem;border-top:1px solid #f0f0f0;font-size:.9rem}'
    '@media(max-width:600px){.tc{grid-template-columns:1fr}.hdr{justify-content:center}}'
)

def html(body, title='A/B Testing Pro'):
    return (
        '<!DOCTYPE html><html lang="ru"><head>'
        '<meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>' + title + '</title>'
        '<style>' + CSS + '</style>'
        '</head><body>' + body + '</body></html>'
    )

def nav_bar(pg):
    pages = [('/', 'dash', '&#128202; Панель'),
             ('/tests', 'tests', '&#129514; Тесты'),
             ('/api-keys', 'keys', '&#128273; API ключи'),
             ('/settings', 'cfg', '&#9881; Настройки')]
    items = ''
    for url, p, label in pages:
        cls = 'nb on' if pg == p else 'nb'
        items += '<a href="{}" class="{}">{}</a>'.format(url, cls, label)
    items += '<a href="/logout" class="nb">&#128682; Выход</a>'
    return '<div class="hdr"><h1>&#128202; A/B Testing Pro</h1><nav>' + items + '</nav></div>'

def page(content, pg='', logged=True):
    top = nav_bar(pg) if logged else ''
    return html(top + '<div class="wrap">' + content + '</div>')

def alert(msg, kind='ok'):
    return '<div class="al ' + kind + '">' + msg + '</div>' if msg else ''

# ── auth routes ────────────────────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("20 per minute")
def login():
    if me(): return redirect('/')
    err = ''
    if request.method == 'POST':
        email = clean(request.form.get('email', '')).lower()
        pw = request.form.get('password', '')
        if not email or not pw:
            err = 'Заполните все поля'
        elif not valid_email(email):
            err = 'Некорректный email'
        else:
            u = USERS.get(email)
            if not u or not check_pw(pw, u['pw']):
                err = 'Неверный email или пароль'
            else:
                session['email'] = email
                return redirect('/')
    body = (
        '<div class="aw"><div class="ac">'
        '<h1>A/B Testing Pro</h1>'
        '<p class="sub">Войдите в аккаунт</p>'
        + alert(err, 'er') +
        '<form method="POST">'
        '<div class="fg"><label>Email</label>'
        '<input type="email" name="email" placeholder="your@email.com" required></div>'
        '<div class="fg"><label>Пароль</label>'
        '<input type="password" name="password" placeholder="&#8226;&#8226;&#8226;&#8226;&#8226;&#8226;&#8226;&#8226;" required></div>'
        '<button class="btn bp" style="width:100%">Войти</button>'
        '</form>'
        '<p class="al2" onclick="location=\'/register\'">Нет аккаунта? Зарегистрироваться</p>'
        '</div></div>'
    )
    return html(body)

@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per hour")
def register():
    if me(): return redirect('/')
    err = ''
    if request.method == 'POST':
        name  = clean(request.form.get('name', ''), 100)
        email = clean(request.form.get('email', '')).lower()
        pw    = request.form.get('password', '')
        pw2   = request.form.get('confirm', '')
        if not all([name, email, pw, pw2]):
            err = 'Заполните все поля'
        elif not valid_email(email):
            err = 'Некорректный email'
        elif len(pw) < 8:
            err = 'Пароль минимум 8 символов'
        elif pw != pw2:
            err = 'Пароли не совпадают'
        elif email in USERS:
            err = 'Email уже зарегистрирован'
        else:
            USERS[email] = {
                'email': email, 'name': name,
                'pw': hash_pw(pw), 'keys': [],
                'created': datetime.utcnow().strftime('%Y-%m-%d')
            }
            session['email'] = email
            return redirect('/')
    body = (
        '<div class="aw"><div class="ac">'
        '<h1>A/B Testing Pro</h1>'
        '<p class="sub">Создайте аккаунт бесплатно</p>'
        + alert(err, 'er') +
        '<form method="POST">'
        '<div class="fg"><label>Имя</label>'
        '<input type="text" name="name" placeholder="Иван Иванов" required maxlength="100"></div>'
        '<div class="fg"><label>Email</label>'
        '<input type="email" name="email" placeholder="your@email.com" required></div>'
        '<div class="tc">'
        '<div class="fg"><label>Пароль</label>'
        '<input type="password" name="password" placeholder="Мин. 8 символов" required></div>'
        '<div class="fg"><label>Повторите</label>'
        '<input type="password" name="confirm" placeholder="Повторите пароль" required></div>'
        '</div>'
        '<button class="btn bp" style="width:100%">Создать аккаунт</button>'
        '</form>'
        '<p class="al2" onclick="location=\'/login\'">Есть аккаунт? Войти</p>'
        '</div></div>'
    )
    return html(body)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# ── main pages ─────────────────────────────────────────────────────────────
@app.route('/')
def index():
    u = me()
    if not u: return redirect('/login')
    kc = len(u.get('keys', []))
    warn = alert('Добавьте API ключи Озона чтобы начать. <a href="/api-keys" style="font-weight:700">Добавить</a>', 'wn') if kc == 0 else ''
    c = warn + '<p class="ttl">Привет, ' + u['name'] + '!</p>'
    c += '<div class="cards">'
    c += '<div class="card"><div class="ic">&#129514;</div><div><div class="n">2</div><div class="lb">Активных теста</div></div></div>'
    c += '<div class="card"><div class="ic">&#128273;</div><div><div class="n">' + str(kc) + '</div><div class="lb">API подключений</div></div></div>'
    c += '<div class="card"><div class="ic">&#128065;</div><div><div class="n">12 480</div><div class="lb">Просмотров</div></div></div>'
    c += '<div class="card"><div class="ic">&#128200;</div><div><div class="n">+34%</div><div class="lb">Рост конверсии</div></div></div>'
    c += '</div>'
    c += '<div class="box"><h2>Активные тесты</h2><table>'
    c += '<tr><th>Товар</th><th>Вариант A</th><th>Вариант B</th><th>Статус</th></tr>'
    c += '<tr><td><strong>Рубашка M</strong><br><small style="color:#999">SKU-001</small></td><td>8.2%</td><td><strong>11.5%</strong></td><td><span class="bg g">Идет</span></td></tr>'
    c += '<tr><td><strong>Кроссовки</strong><br><small style="color:#999">SKU-002</small></td><td><strong>9.1%</strong></td><td>7.8%</td><td><span class="bg g">Идет</span></td></tr>'
    c += '</table></div>'
    c += '<div class="tip">Совет: для достоверных результатов нужно минимум 100 просмотров и 7 дней тестирования.</div>'
    return page(c, 'dash')

@app.route('/tests')
def tests():
    if not me(): return redirect('/login')
    c = '<p class="ttl">Мои тесты</p><div class="box"><div class="empty"><p style="font-size:2rem">&#129514;</p><p style="margin-top:1rem">Раздел в разработке</p></div></div>'
    return page(c, 'tests')

@app.route('/settings')
def settings():
    u = me()
    if not u: return redirect('/login')
    c = '<p class="ttl">Настройки</p><div class="box"><h2>Профиль</h2><table style="width:auto">'
    c += '<tr><td style="color:#666;padding:.5rem 2rem .5rem 0">Имя:</td><td><strong>' + u['name'] + '</strong></td></tr>'
    c += '<tr><td style="color:#666;padding:.5rem 2rem .5rem 0">Email:</td><td><strong>' + u['email'] + '</strong></td></tr>'
    c += '<tr><td style="color:#666;padding:.5rem 2rem .5rem 0">Ключей:</td><td><strong>' + str(len(u.get('keys', []))) + '</strong></td></tr>'
    c += '<tr><td style="color:#666;padding:.5rem 2rem .5rem 0">Создан:</td><td><strong>' + u.get('created', '-') + '</strong></td></tr>'
    c += '</table></div>'
    return page(c, 'cfg')

# ── api keys ───────────────────────────────────────────────────────────────
@app.route('/api-keys')
def api_keys():
    u = me()
    if not u: return redirect('/login')
    msg  = request.args.get('msg', '')
    err  = request.args.get('err', '')
    keys = u.get('keys', [])
    c = '<p class="ttl">API ключи Озона</p>'
    c += alert(msg, 'ok')
    c += alert(err, 'er')
    c += '<div class="box"><h2>Добавить подключение</h2>'
    c += '<div class="tip" style="margin-bottom:1.2rem">Где взять ключи: войдите в <a href="https://seller.ozon.ru/app/settings/api-keys" target="_blank" style="color:#1e40af;font-weight:600">seller.ozon.ru - Настройки - API ключи</a> - нажмите «Сгенерировать ключ»</div>'
    if len(keys) < MAX_KEYS:
        c += '<form method="POST" action="/api-keys/add"><div class="tc">'
        c += '<div class="fg"><label>Название магазина</label><input type="text" name="shop" placeholder="Мой магазин" required maxlength="100"><div class="hn">Любое удобное название</div></div>'
        c += '<div class="fg"><label>Client ID</label><input type="text" name="cid" placeholder="123456789" required maxlength="50"><div class="hn">Числовой ID из личного кабинета</div></div>'
        c += '</div><div class="fg"><label>API Key</label><input type="password" name="akey" placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" required maxlength="200"><div class="hn">Хранится безопасно. Показываются только последние 4 символа</div></div>'
        c += '<button class="btn bp">Проверить и сохранить</button><span style="font-size:.85rem;color:#888;margin-left:1rem">Ключ будет проверен через API Озона</span></form>'
    else:
        c += alert('Достигнут лимит ' + str(MAX_KEYS) + ' ключей на аккаунт', 'wn')
    c += '</div>'
    c += '<div class="box"><h2>Ваши подключения (' + str(len(keys)) + ' / ' + str(MAX_KEYS) + ')</h2>'
    if keys:
        for i, k in enumerate(keys):
            dot   = 'dg' if k.get('active') else 'dr'
            badge = '<span class="bg g">Активен</span>' if k.get('active') else '<span class="bg r">Ошибка</span>'
            c += '<div class="kc"><div style="flex:1"><div class="kn">' + k['shop'] + '</div>'
            c += '<span class="ki">Client ID: ' + k['cid'] + '</span>'
            c += '<span class="ki">API Key: ....' + k['hint'] + '</span>'
            if k.get('check_msg'):
                c += '<div style="font-size:.8rem;color:#666;margin-top:.3rem">' + k['check_msg'] + '</div>'
            c += '<div style="font-size:.8rem;color:#999;margin-top:.2rem">Добавлен: ' + k.get('added', '-') + '</div>'
            c += '</div>'
            c += '<div style="display:flex;align-items:center;gap:.5rem"><span class="dot ' + dot + '"></span>' + badge + '</div>'
            c += '<form method="POST" action="/api-keys/del/' + str(i) + '"><button class="btn bd bs" onclick="return confirm(\'Удалить?\')">Удалить</button></form>'
            c += '</div>'
    else:
        c += '<div class="empty"><p style="font-size:2rem">&#128273;</p><p style="margin-top:1rem">Нет добавленных ключей</p></div>'
    c += '</div>'
    return page(c, 'keys')

@app.route('/api-keys/add', methods=['POST'])
@limiter.limit("10 per minute")
def add_key():
    u = me()
    if not u: return redirect('/login')
    if len(u.get('keys', [])) >= MAX_KEYS:
        return redirect('/api-keys?err=Достигнут+лимит+ключей')
    shop = clean(request.form.get('shop', ''), 100)
    cid  = clean(request.form.get('cid', ''), 50)
    akey = request.form.get('akey', '').strip()
    if not shop or not cid or not akey:
        return redirect('/api-keys?err=Заполните+все+поля')
    if not cid.isdigit():
        return redirect('/api-keys?err=Client+ID+должен+быть+числом')
    if len(akey) < 10:
        return redirect('/api-keys?err=API+Key+слишком+короткий')
    ok, msg = verify_ozon(cid, akey)
    u.setdefault('keys', []).append({
        'shop': shop, 'cid': cid, 'akey': akey,
        'hint': akey[-4:], 'active': ok,
        'check_msg': msg,
        'added': datetime.utcnow().strftime('%Y-%m-%d')
    })
    if ok:
        return redirect('/api-keys?msg=Магазин+' + shop + '+подключён')
    return redirect('/api-keys?err=Ключ+добавлен+но+проверка:+' + msg.replace(' ', '+'))

@app.route('/api-keys/del/<int:i>', methods=['POST'])
def del_key(i):
    u = me()
    if not u: return redirect('/login')
    keys = u.get('keys', [])
    if 0 <= i < len(keys):
        name = keys.pop(i)['shop']
        return redirect('/api-keys?msg=' + name + '+удалён')
    return redirect('/api-keys?err=Ключ+не+найден')

# ── error handlers ─────────────────────────────────────────────────────────
@app.errorhandler(404)
def e404(e):
    c = '<div style="text-align:center;padding:4rem"><p style="font-size:3rem">&#128269;</p><h2 style="margin:1rem 0">Страница не найдена</h2><a href="/" class="btn bp" style="margin-top:1rem">На главную</a></div>'
    return page(c, logged=bool(me())), 404

@app.errorhandler(429)
def e429(e):
    c = '<div style="text-align:center;padding:4rem"><p style="font-size:3rem">&#9203;</p><h2 style="margin:1rem 0">Слишком много запросов</h2><p>Подождите и попробуйте снова</p></div>'
    return page(c, logged=False), 429

@app.errorhandler(500)
def e500(e):
    c = '<div style="text-align:center;padding:4rem"><p style="font-size:3rem">&#9888;</p><h2 style="margin:1rem 0">Ошибка сервера</h2><a href="/" class="btn bp" style="margin-top:1rem">На главную</a></div>'
    return page(c, logged=False), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
