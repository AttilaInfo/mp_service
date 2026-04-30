from flask import Flask, render_template_string, request, redirect, session
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

def hash_pw(pw):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def check_pw(pw, hashed):
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False

def valid_email(e):
    return bool(re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', e))

def clean(text, n=200):
    return str(text).strip()[:n].replace('<','').replace('>','').replace('"','')

def current_user():
    e = session.get('email')
    return USERS.get(e) if e else None

def verify_ozon(client_id, api_key):
    try:
        r = requests.post(
            'https://api-seller.ozon.ru/v1/warehouse/list',
            headers={'Client-Id': client_id, 'Api-Key': api_key, 'Content-Type': 'application/json'},
            json={}, timeout=8)
        if r.status_code == 200:
            return True, 'Ключ работает'
        if r.status_code == 401:
            return False, 'Неверный Client ID или API Key'
        if r.status_code == 403:
            return False, 'Нет прав — проверьте настройки ключа'
        return False, 'Ошибка Озона: ' + str(r.status_code)
    except requests.exceptions.Timeout:
        return False, 'Озон не отвечает (timeout)'
    except requests.exceptions.ConnectionError:
        return False, 'Нет соединения с Озоном'
    except Exception as ex:
        return False, 'Ошибка: ' + str(ex)[:80]

CSS = """
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f0f2f5;color:#1a1a2e;min-height:100vh}
a{text-decoration:none;color:inherit}
.hdr{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;padding:1rem 2rem;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.8rem;box-shadow:0 2px 8px rgba(0,0,0,.2)}
.hdr h1{font-size:1.4rem}
.hdr nav{display:flex;gap:.5rem;flex-wrap:wrap}
.nb{padding:.5rem 1rem;border-radius:8px;background:rgba(255,255,255,.15);color:#fff;border:1px solid rgba(255,255,255,.3);cursor:pointer;font-size:.9rem;transition:.2s;text-decoration:none}
.nb:hover,.nb.on{background:#fff;color:#667eea}
.wrap{max-width:1100px;margin:2rem auto;padding:0 1rem}
.ttl{font-size:1.6rem;font-weight:700;margin-bottom:1.5rem}
.box{background:#fff;border-radius:12px;padding:1.5rem;box-shadow:0 2px 8px rgba(0,0,0,.07);margin-bottom:1.5rem}
.box h2{font-size:1.1rem;font-weight:700;margin-bottom:1.2rem}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1.2rem;margin-bottom:2rem}
.card{background:#fff;border-radius:12px;padding:1.5rem;box-shadow:0 2px 8px rgba(0,0,0,.07);border-left:4px solid #667eea;display:flex;align-items:center;gap:1rem}
.card .ic{font-size:2rem}
.card .n{font-size:1.8rem;font-weight:700;color:#667eea}
.card .lb{font-size:.85rem;color:#666;margin-top:.2rem}
.fg{margin-bottom:1.2rem}
.fg label{display:block;margin-bottom:.4rem;font-weight:600;font-size:.9rem;color:#444}
.fg input{width:100%;padding:.75rem 1rem;border:2px solid #e0e0e0;border-radius:8px;font-size:.95rem;transition:.2s}
.fg input:focus{outline:none;border-color:#667eea;box-shadow:0 0 0 3px rgba(102,126,234,.1)}
.hn{font-size:.8rem;color:#888;margin-top:.3rem}
.btn{padding:.75rem 1.5rem;border:none;border-radius:8px;cursor:pointer;font-size:.95rem;font-weight:600;transition:.2s;display:inline-flex;align-items:center;gap:.4rem}
.bp{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff}
.bp:hover{opacity:.9;transform:translateY(-1px);box-shadow:0 4px 12px rgba(102,126,234,.4)}
.bd{background:#e74c3c;color:#fff}
.bd:hover{background:#c0392b}
.bs{padding:.4rem .9rem;font-size:.85rem}
.al{padding:1rem 1.2rem;border-radius:8px;margin-bottom:1.2rem;font-size:.9rem}
.ok{background:#d4edda;color:#155724;bo
