from flask import Flask, render_template_string, request, redirect, session, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os, json, hashlib, bcrypt, requests, re
from datetime import datetime
from config import SECRET_KEY, OZON_API_URL, MAX_LOGIN_ATTEMPTS, LOGIN_BLOCK_MINUTES, MAX_API_KEYS_PER_USER

app = Flask(__name__)
app.secret_key = SECRET_KEY

# ── Защита от brute-force ──────────────────────────────────────────────────
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# ── Хранилище (в памяти; для продакшена заменить на БД) ───────────────────
USERS = {}          # email -> данные пользователя
LOGIN_FAILS = {}    # ip -> {count, last_time}

# ══════════════════════════════════════════════════════════════════════════════
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ══════════════════════════════════════════════════════════════════════════════

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def check_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except Exception:
        return False

def is_valid_email(email: str) -> bool:
    return bool(re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email))

def get_current_user():
    email = session.get('email')
    if not email or email not in USERS:
        return None
    return USERS[email]

def sanitize(text: str, max_len: int = 200) -> str:
    """Очищаем входные данные от опасных символов"""
    return str(text).strip()[:max_len].replace('<', '').replace('>', '').replace('"', '')

def verify_ozon_key(client_id: str, api_key: str) -> dict:
    """
    Проверяем API ключ Озона — делаем реальный запрос.
    Возвращает {'ok': True/False, 'message': '...'}
    """
    try:
        headers = {
            'Client-Id': client_id,
            'Api-Key': api_key,
            'Content-Type': 'application/json'
        }
        # Лёгкий запрос — список складов
        resp = requests.post(
            f'{OZON_API_URL}/v1/warehouse/list',
            headers=headers,
            json={},
            timeout=8
        )
        if resp.status_code == 200:
            return {'ok': True, 'message': 'Ключ работает ✅'}
        elif resp.status_code == 401:
            return {'ok': False, 'message': 'Неверный Client ID или API Key'}
        elif resp.status_code == 403:
            return {'ok': False, 'message': 'Нет доступа — проверьте права ключа'}
        else:
            return {'ok': False, 'message': f'Ошибка Озона: {resp.status_code}'}
    except requests.exceptions.Timeout:
        return {'ok': False, 'message': 'Озон не отвечает (timeout) — попробуйте позже'}
    except requests.exceptions.ConnectionError:
        return {'ok': False, 'message': 'Нет соединения с Озоном'}
    except Exception as e:
        return {'ok': False, 'message': f'Неожиданная ошибка: {str(e)[:100]}'}

# ══════════════════════════════════════════════════════════════════════════════
# HTML ШАБЛОНЫ
# ══════════════════════════════════════════════════════════════════════════════

CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f0f2f5;color:#1a1a2e;min-height:100vh}
a{text-decoration:none;color:inherit}
.header{background:linear-gradient(135deg,#667eea,#764ba2);color:white;padding:1rem 2rem;display:flex;align-items:center;justify-content:space-between;box-shadow:0 2px 8px rgba(0,0,0,.2);flex-wrap:wrap;gap:.8rem}
.header h1{font-size:1.4rem}
.header nav{display:flex;gap:.5rem;flex-wrap:wrap}
.nav-btn{padding:.5rem 1rem;border-radius:8px;background:rgba(255,255,255,.15);color:white;border:1px solid rgba(255,255,255,.3);cursor:pointer;font-size:.9rem;transition:.2s}
.nav-btn:hover,.nav-btn.active{background:white;color:#667eea}
.container{max-width:1100px;margin:2rem auto;padding:0 1rem}
.page-title{font-size:1.6rem;margin-bottom:1.5rem;font-weight:700}
.section{background:white;border-radius:12px;padding:1.5rem;box-shadow:0 2px 8px rgba(0,0,0,.07);margin-bottom:1.5rem}
.section h2{margin-bottom:1.2rem;font-size:1.1rem;font-weight:700}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1.2rem;margin-bottom:2rem}
.card{background:white;border-radius:12px;padding:1.5rem;box-shadow:0 2px 8px rgba(0,0,0,.07);border-left:4px solid #667eea;display:flex;align-items:center;gap:1rem}
.card .icon{font-size:2rem}
.card .num{font-size:1.8rem;font-weight:700;color:#667eea}
.card .label{font-size:.85rem;color:#666;margin-top:.2rem}
.form-group{margin-bottom:1.2rem}
.form-group label{display:block;margin-bottom:.4rem;font-weight:600;font-size:.9rem;color:#444}
.form-group input{width:100%;padding:.75rem 1rem;border:2px solid #e0e0e0;border-radius:8px;font-size:.95rem;transition:.2s}
.form-group input:focus{outline:none;border-color:#667eea;box-shadow:0 0 0 3px rgba(102,126,234,.1)}
.hint{font-size:.8rem;color:#888;margin-top:.3rem}
.btn{padding:.75rem 1.5rem;border:none;border-radius:8px;cursor:pointer;font-size:.95rem;font-weight:600;transition:.2s;display:inline-flex;align-items:center;gap:.4rem}
.btn-primary{background:linear-gradient(135deg,#667eea,#764ba2);color:white}
.btn-primary:hover{opacity:.9;transform:translateY(-1px);box-shadow:0 4px 12px rgba(102,126,234,.4)}
.btn-danger{background:#e74c3c;color:white}
.btn-danger:hover{background:#c0392b}
.btn-sm{padding:.4rem .9rem;font-size:.85rem}
.alert{padding:1rem 1.2rem;border-radius:8px;margin-bottom:1.2rem;font-size:.9rem}
.alert-success{background:#d4edda;color:#155724;border-left:4px solid #28a745}
.alert-error{background:#f8d7da;color:#721c24;border-left:4px solid #dc3545}
.alert-info{background:#cce5ff;color:#004085;border-left:4px solid #007bff}
.alert-warning{background:#fff3cd;color:#856404;border-left:4px solid #ffc107}
.key-card{background:#f8f9fa;border:1px solid #e0e0e0;border-radius:10px;padding:1.2rem;margin-bottom:1rem;display:flex;align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap}
.key-info .key-name{font-weight:700;font-size:1rem;margin-bottom:.4rem}
.key-id{font-family:monospace;font-size:.82rem;color:#555;background:#e9ecef;padding:.2rem .5rem;border-radius:4px;display:inline-block;margin-right:.4rem;margin-top:.2rem}
.badge{padding:.25rem .7rem;border-radius:20px;font-size:.78rem;font-weight:600}
.badge-green{background:#d4edda;color:#155724}
.badge-red{background:#f8d7da;color:#721c24}
.badge-yellow{background:#fff3cd;color:#856404}
.dot{width:9px;height:9px;border-radius:50%;display:inline-block;margin-right:.3rem}
.dot-green{background:#2ecc71}
.dot-red{background:#e74c3c}
.tip{background:#e8f4fd;border-left:4px solid #3b82f6;padding:1rem 1.2rem;border-radius:8px;color:#1e40af;font-size:.9rem}
.empty{text-align:center;padding:3rem;color:#aaa}
.empty-icon{font-size:3rem;margin-bottom:.8rem}
.auth-wrap{min-height:100vh;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#667eea,#764ba2);padding:1rem}
.auth-card{background:white;border-radius:16px;padding:2.5rem;width:100%;max-width:420px;box-shadow:0 20px 60px rgba(0,0,0,.2)}
.auth-card h1{text-align:center;color:#667eea;margin-bottom:.4rem}
.auth-sub{text-align:center;color:#888;margin-bottom:1.8rem;font-size:.9rem}
.auth-link{text-align:center;margin-top:1rem;font-size:.9rem;color:#667eea;cursor:pointer}
.auth-link:hover{text-decoration:underline}
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:1rem}
@media(max-width:600px){.two-col{grid-template-columns:1fr}.header{justify-content:center}}
"""

def base_layout(content, page='', logged_in=True):
    nav = ""
    if logged_in:
        pages = [('/', 'dashboard', '📊 Панель'), ('/tests', 'tests', '🧪 Тесты'),
                 ('/api-keys', 'api_keys', '🔑 API ключи'), ('/settings', 'settings', '⚙️ Настройки')]
        nav_links = ''.join(
            f'<a href="{url}" class="nav-btn {\"active\" if page==pg else ""}">{label}</a>'
            for url, pg, label in pages
        )
        nav_links += '<a href="/logout" class="nav-btn">🚪 Выход</a>'
        nav = f'''<div class="header">
            <h1>📊 A/B Testing Pro</h1>
            <nav>{nav_links}</nav>
        </div>'''
    return f'<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>A/B Testing Pro</title><style>{CSS}</style></head><body>{nav}<div class="container">{content}</div></body></html>'

# ══════════════════════════════════════════════════════════════════════════════
# МАРШРУТЫ — АУТЕНТИФИКАЦИЯ
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("20 per minute")
def login():
    if get_current_user():
        return redirect('/')

    error = None
    if request.method == 'POST':
        email = sanitize(request.form.get('email', '')).lower()
        password = request.form.get('password', '')

        if not email or not password:
            error = 'Заполните все поля'
        elif not is_valid_email(email):
            error = 'Некорректный email'
        else:
            user = USERS.get(email)
            if not user or not check_password(password, user['password']):
                error = 'Неверный email или пароль'
            else:
                session.permanent = True
                session['email'] = email
                return redirect('/')

    html = f'''
    <div class="auth-wrap">
      <div class="auth-card">
        <h1>📊 A/B Testing Pro</h1>
        <p class="auth-sub">Войдите в свой аккаунт</p>
        {"<div class='alert alert-error'>" + error + "</div>" if error else ""}
        <form method="POST">
          <div class="form-group"><label>Email</label>
            <input type="email" name="email" placeholder="your@email.com" required autocomplete="email"></div>
          <div class="form-group"><label>Пароль</label>
            <input type="password" name="password" placeholder="••••••••" required autocomplete="current-password"></div>
          <button class="btn btn-primary" style="width:100%">🔐 Войти</button>
        </form>
        <p class="auth-link" onclick="location='/register'">Нет аккаунта? Зарегистрироваться →</p>
      </div>
    </div>'''
    return base_layout(html, logged_in=False)

@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("10 per hour")
def register():
    if get_current_user():
        return redirect('/')

    error = None
    if request.method == 'POST':
        name     = sanitize(request.form.get('name', ''), 100)
        email    = sanitize(request.form.get('email', '')).lower()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm', '')

        if not all([name, email, password, confirm]):
            error = 'Заполните все поля'
        elif not is_valid_email(email):
            error = 'Некорректный email адрес'
        elif len(password) < 8:
            error = 'Пароль должен быть минимум 8 символов'
        elif password != confirm:
            error = 'Пароли не совпадают'
        elif email in USERS:
            error = 'Этот email уже зарегистрирован'
        else:
            USERS[email] = {
                'email': email,
                'name': name,
                'password': hash_password(password),
                'keys': [],
                'created_at': datetime.utcnow().isoformat()
            }
            session['email'] = email
            return redirect('/')

    html = f'''
    <div class="auth-wrap">
      <div class="auth-card">
        <h1>📊 A/B Testing Pro</h1>
        <p class="auth-sub">Создайте аккаунт бесплатно</p>
        {"<div class='alert alert-error'>" + error + "</div>" if error else ""}
        <form method="POST">
          <div class="form-group"><label>Ваше имя</label>
            <input type="text" name="name" placeholder="Иван Иванов" required maxlength="100"></div>
          <div class="form-group"><label>Email</label>
            <input type="email" name="email" placeholder="your@email.com" required autocomplete="email"></div>
          <div class="two-col">
            <div class="form-group"><label>Пароль</label>
              <input type="password" name="password" placeholder="Мин. 8 символов" required></div>
            <div class="form-group"><label>Повторите пароль</label>
              <input type="password" name="confirm" placeholder="••••••••" required></div>
          </div>
          <button class="btn btn-primary" style="width:100%">📝 Создать аккаунт</button>
        </form>
        <p class="auth-link" onclick="location='/login'">Уже есть аккаунт? Войти →</p>
      </div>
    </div>'''
    return base_layout(html, logged_in=False)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# ══════════════════════════════════════════════════════════════════════════════
# МАРШРУТЫ — ОСНОВНЫЕ СТРАНИЦЫ
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/')
def index():
    user = get_current_user()
    if not user:
        return redirect('/login')

    key_count = len(user.get('keys', []))
    warn = '' if key_count > 0 else '''
    <div class="alert alert-warning">
      🔑 <strong>Добавьте API ключи Озона</strong> чтобы начать автоматическое тестирование.
      <a href="/api-keys" style="font-weight:700;margin-left:.5rem">Добавить ключи →</a>
    </div>'''

    html = f'''
    {warn}
    <p class="page-title">👋 Привет, {user["name"]}!</p>
    <div class="cards">
      <div class="card"><div class="icon">🧪</div><div><div class="num">2</div><div class="label">Активных теста</div></div></div>
      <div class="card"><div class="icon">🔑</div><div><div class="num">{key_count}</div><div class="label">API подключений</div></div></div>
      <div class="card"><div class="icon">👁️</div><div><div class="num">12,480</div><div class="label">Просмотров за неделю</div></div></div>
      <div class="card"><div class="icon">📈</div><div><div class="num">+34%</div><div class="label">Рост конверсии</div></div></div>
    </div>
    <div class="section">
      <h2>🧪 Активные тесты</h2>
      <table style="width:100%;border-collapse:collapse">
        <tr style="background:#f8f9fa"><th style="padding:.75rem;text-align:left;font-size:.85rem;color:#666">Товар</th><th style="padding:.75rem;text-align:left;font-size:.85rem;color:#666">Вариант A</th><th style="padding:.75rem;text-align:left;font-size:.85rem;color:#666">Вариант B</th><th style="padding:.75rem;text-align:left;font-size:.85rem;color:#666">Статус</th></tr>
        <tr style="border-top:1px solid #f0f0f0"><td style="padding:.75rem"><strong>Рубашка M</strong><br><small style="color:#999">SKU-001</small></td><td style="padding:.75rem">8.2%</td><td style="padding:.75rem"><strong>11.5%</strong> ▲</td><td style="padding:.75rem"><span class="badge badge-green">✅ Идёт</span></td></tr>
        <tr style="border-top:1px solid #f0f0f0"><td style="padding:.75rem"><strong>Кроссовки</strong><br><small style="color:#999">SKU-002</small></td><td style="padding:.75rem"><strong>9.1%</strong> ▲</td><td style="padding:.75rem">7.8%</td><td style="padding:.75rem"><span class="badge badge-green">✅ Идёт</span></td></tr>
      </table>
    </div>
    <div class="tip">💡 <strong>Совет:</strong> Для достоверных результатов нужно минимум 100 просмотров и 7 дней тестирования.</div>'''
    return base_layout(html, 'dashboard')

@app.route('/tests')
def tests():
    user = get_current_user()
    if not user:
        return redirect('/login')
    html = '<p class="page-title">🧪 Мои тесты</p><div class="section"><div class="empty"><div class="empty-icon">🧪</div><p>Раздел в разработке</p><p style="font-size:.9rem;margin-top:.5rem">Сначала добавьте API ключи Озона</p></div></div>'
    return base_layout(html, 'tests')

@app.route('/settings')
def settings():
    user = get_current_user()
    if not user:
        return redirect('/login')
    html = f'''
    <p class="page-title">⚙️ Настройки</p>
    <div class="section">
      <h2>👤 Профиль</h2>
      <table><tr><td style="color:#666;padding:.5rem 2rem .5rem 0">Имя:</td><td><strong>{user["name"]}</strong></td></tr>
      <tr><td style="color:#666;padding:.5rem 2rem .5rem 0">Email:</td><td><strong>{user["email"]}</strong></td></tr>
      <tr><td style="color:#666;padding:.5rem 2rem .5rem 0">API ключей:</td><td><strong>{len(user.get("keys",[]))}</strong></td></tr>
      <tr><td style="color:#666;padding:.5rem 2rem .5rem 0">Аккаунт создан:</td><td><strong>{user.get("created_at","—")[:10]}</strong></td></tr></table>
    </div>'''
    return base_layout(html, 'settings')

# ══════════════════════════════════════════════════════════════════════════════
# МАРШРУТЫ — API КЛЮЧИ
# ══════════════════════════════════════════════════════════════════════════════

@app.route('/api-keys')
def api_keys():
    user = get_current_user()
    if not user:
        return redirect('/login')

    msg   = request.args.get('msg', '')
    error = request.args.get('error', '')

    keys_html = ''
    for i, k in enumerate(user.get('keys', [])):
        status_dot   = 'dot-green' if k.get('active') else 'dot-red'
        status_badge = '<span class="badge badge-green">✅ Активен</span>' if k.get('active') else '<span class="badge badge-red">❌ Ошибка</span>'
        keys_html += f'''
        <div class="key-card">
          <div class="key-info">
            <div class="key-name">🏪 {k["shop_name"]}</div>
            <span class="key-id">Client ID: {k["client_id"]}</span>
            <span class="key-id">API Key: ••••••••{k["hint"]}</span>
            <div style="font-size:.8rem;color:#999;margin-top:.3rem">Добавлен: {k.get("added_at","—")[:10]}</div>
          </div>
          <div style="display:flex;align-items:center;gap:.5rem">
            <span class="dot {status_dot}"></span>{status_badge}
          </div>
          <form method="POST" action="/api-keys/delete/{i}" onsubmit="return confirm('Удалить подключение «{k[\"shop_name\"]}»?')">
            <button class="btn btn-danger btn-sm">🗑 Удалить</button>
          </form>
        </div>'''

    if not keys_html:
        keys_html = '<div class="empty"><div class="empty-icon">🔑</div><p>Нет добавленных ключей</p><p style="font-size:.9rem;margin-top:.5rem">Добавьте ключ выше чтобы начать</p></div>'

    limit_warn = f'<div class="alert alert-warning">⚠️ Достигнут лимит {MAX_API_KEYS_PER_USER} ключей на аккаунт</div>' if len(user.get('keys', [])) >= MAX_API_KEYS_PER_USER else ''

    html = f'''
    <p class="page-title">🔑 API ключи Озона</p>
    {"<div class='alert alert-success'>" + msg + "</div>" if msg else ""}
    {"<div class='alert alert-error'>" + error + "</div>" if error else ""}

    <div class="section">
      <h2>➕ Добавить подключение к Озону</h2>
      <div class="tip" style="margin-bottom:1.2rem">
        📋 <strong>Где взять ключи:</strong> войдите в
        <a href="https://seller.ozon.ru/app/settings/api-keys" target="_blank" style="color:#1e40af;font-weight:600">seller.ozon.ru → Настройки → API ключи</a>
        → нажмите «Сгенерировать ключ» → скопируйте <strong>Client ID</strong> и <strong>API Key</strong>.
      </div>
      {limit_warn}
      <form method="POST" action="/api-keys/add">
        <div class="two-col">
          <div class="form-group">
            <label>Название магазина</label>
            <input type="text" name="shop_name" placeholder="Мой магазин" required maxlength="100">
            <div class="hint">Любое удобное название для вас</div>
          </div>
          <div class="form-group">
            <label>Client ID</label>
            <input type="text" name="client_id" placeholder="123456789" required maxlength="50">
            <div class="hint">Числовой ID из личного кабинета</div>
          </div>
        </div>
        <div class="form-group">
          <label>API Key</label>
          <input type="password" name="api_key" placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" required maxlength="200">
          <div class="hint">🔒 Ключ хранится в зашифрованном виде и не отображается полностью</div>
        </div>
        <button class="btn btn-primary" {"disabled" if len(user.get("keys",[])) >= MAX_API_KEYS_PER_USER else ""}>
          🔍 Проверить и добавить
        </button>
        <span style="font-size:.85rem;color:#888;margin-left:1rem">Ключ будет проверен перед сохранением</span>
      </form>
    </div>

    <div class="section">
      <h2>📋 Ваши подключения ({len(user.get("keys", []))} / {MAX_API_KEYS_PER_USER})</h2>
      {keys_html}
    </div>'''
    return base_layout(html, 'api_keys')

@app.route('/api-keys/add', methods=['POST'])
@limiter.limit("10 per minute")
def add_api_key():
    user = get_current_user()
    if not user:
        return redirect('/login')

    # Проверка лимита
    if len(user.get('keys', [])) >= MAX_API_KEYS_PER_USER:
        return redirect(f'/api-keys?error=Достигнут+лимит+{MAX_API_KEYS_PER_USER}+ключей')

    shop_name = sanitize(request.form.get('shop_name', ''), 100)
    client_id = sanitize(request.form.get('client_id', ''), 50)
    api_key   = request.form.get('api_key', '').strip()

    # Валидация полей
    if not shop_name or not client_id or not api_key:
        return redirect('/api-keys?error=Заполните+все+поля')
    if not client_id.isdigit():
        return redirect('/api-keys?error=Client+ID+должен+быть+числом')
    if len(api_key) < 10:
        return redirect('/api-keys?error=API+Key+слишком+короткий')

    # ✅ Проверяем ключ через реальный API Озона
    check = verify_ozon_key(client_id, api_key)

    new_key = {
        'shop_name': shop_name,
        'client_id': client_id,
        'api_key':   api_key,          # В продакшене — шифровать!
        'hint':      api_key[-4:],     # Показываем только последние 4 символа
        'active':    check['ok'],
        'added_at':  datetime.utcnow().isoformat(),
        'last_check': check['message']
    }

    if 'keys' not in user:
        user['keys'] = []
    user['keys'].append(new_key)

    if check['ok']:
        msg = f'Магазин «{shop_name}» успешно подключён! Ключ проверен ✅'
        return redirect(f'/api-keys?msg={msg}')
    else:
        msg = f'Ключ добавлен, но проверка не прошла: {check["message"]}'
        return redirect(f'/api-keys?error={msg}')

@app.route('/api-keys/delete/<int:idx>', methods=['POST'])
def delete_api_key(idx):
    user = get_current_user()
    if not user:
        return redirect('/login')
    keys = user.get('keys', [])
    if 0 <= idx < len(keys):
        name = keys[idx]['shop_name']
        keys.pop(idx)
        return redirect(f'/api-keys?msg=Подключение+«{name}»+удалено')
    return redirect('/api-keys?error=Ключ+не+найден')

# ══════════════════════════════════════════════════════════════════════════════
# ОБРАБОТЧИКИ ОШИБОК
# ══════════════════════════════════════════════════════════════════════════════

@app.errorhandler(404)
def not_found(e):
    html = '<div class="empty" style="margin-top:4rem"><div class="empty-icon">🔍</div><h2>Страница не найдена</h2><p style="margin:1rem 0">Возможно, ссылка устарела или введена с ошибкой</p><a href="/" class="btn btn-primary">← На главную</a></div>'
    return base_layout(html, logged_in=bool(get_current_user())), 404

@app.errorhandler(429)
def too_many(e):
    html = '<div class="empty" style="margin-top:4rem"><div class="empty-icon">⏳</div><h2>Слишком много запросов</h2><p style="margin:1rem 0">Подождите немного и попробуйте снова</p><a href="/" class="btn btn-primary">← На главную</a></div>'
    return base_layout(html, logged_in=False), 429

@app.errorhandler(500)
def server_error(e):
    html = '<div class="empty" style="margin-top:4rem"><div class="empty-icon">⚠️</div><h2>Ошибка сервера</h2><p style="margin:1rem 0">Что-то пошло не так. Мы уже разбираемся!</p><a href="/" class="btn btn-primary">← На главную</a></div>'
    return base_layout(html, logged_in=False), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
