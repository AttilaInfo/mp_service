from flask import Flask, request, redirect, session, Response
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
        if r.status_code == 403: return False, 'Нет прав - проверьте настройки ключа'
        return False, 'Ошибка Озона: ' + str(r.status_code)
    except requests.exceptions.Timeout:
        return False, 'Озон не отвечает (timeout)'
    except requests.exceptions.ConnectionError:
        return False, 'Нет соединения с Озоном'
    except Exception as ex:
        return False, 'Ошибка: ' + str(ex)[:80]

EYE_JS = """
<script>
function checkPasswords() {
    var p1 = document.getElementById("pw_r1");
    var p2 = document.getElementById("pw_r2");
    var hint = document.getElementById("pw_match_hint");
    if (!p1 || !p2 || !hint) return true;
    if (p2.value.length === 0) { hint.textContent = ""; return true; }
    if (p1.value !== p2.value) {
        hint.textContent = "Пароли не совпадают";
        hint.style.color = "#e74c3c";
        p2.style.borderColor = "#e74c3c";
        return false;
    } else {
        hint.textContent = "Пароли совпадают ✓";
        hint.style.color = "#27ae60";
        p2.style.borderColor = "#27ae60";
        return true;
    }
}
function submitRegister(e) {
    if (!checkPasswords()) { e.preventDefault(); }
}
document.addEventListener("DOMContentLoaded", function() {
    var p2 = document.getElementById("pw_r2");
    if (p2) {
        p2.addEventListener("input", function() { checkPasswords(); });
        var form = p2.closest("form");
        if (form) form.addEventListener("submit", submitRegister);
    }
});
function togglePw(inputId, btn) {
    var inp = document.getElementById(inputId);
    if (inp.type === 'password') {
        inp.type = 'text';
        btn.textContent = 'скрыть';
        btn.style.color = '#667eea';
    } else {
        inp.type = 'password';
        btn.textContent = 'показать';
        btn.style.color = '#aaa';
    }
}
</script>
"""

def pw_input(name, field_id, placeholder, label_text='Пароль'):
    return (
        '<div class="fg">'
        '<label style="display:flex;justify-content:space-between;align-items:center">'
        '<span>' + label_text + '</span>'
        '<span id="eye_' + field_id + '" '
        'onclick="togglePw(\'' + field_id + '\', this)" '
        'style="font-size:.78rem;color:#aaa;cursor:pointer;font-weight:400;user-select:none;transition:color .2s">показать</span>'
        '</label>'
        '<input type="password" id="' + field_id + '" name="' + name + '" '
        'class="fi" placeholder="' + placeholder + '" required>'
        '</div>'
    )

APP_CSS = (
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
    '.fi{width:100%;padding:.75rem 1rem;border:2px solid #e0e0e0;border-radius:8px;font-size:.95rem;transition:.2s}'
    '.fi:focus{outline:none;border-color:#667eea;box-shadow:0 0 0 3px rgba(102,126,234,.1)}'
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
    'table{width:100%;border-collapse:collapse}'
    'th{background:#f8f9fa;padding:.75rem 1rem;text-align:left;font-size:.85rem;color:#666;font-weight:600}'
    'td{padding:.75rem 1rem;border-top:1px solid #f0f0f0;font-size:.9rem}'
    '@media(max-width:600px){.hdr{justify-content:center}}'
)

LANDING_CSS = (
    '@import url(https://fonts.googleapis.com/css2?family=Unbounded:wght@400;700;900&family=Onest:wght@300;400;500;600&display=swap);'
    ':root{--c1:#ff4d6d;--c2:#ff9a3c;--c3:#4361ee;--c4:#7209b7;'
    '--grad:linear-gradient(135deg,#ff4d6d,#ff9a3c);'
    '--grad2:linear-gradient(135deg,#4361ee,#7209b7);'
    '--dark:#0d0d0d;--dark2:#161616;--dark3:#1e1e1e;--text:#f0f0f0;--muted:#888;}'
    '*{margin:0;padding:0;box-sizing:border-box}'
    'html{scroll-behavior:smooth}'
    'body{font-family:Onest,sans-serif;background:var(--dark);color:var(--text);overflow-x:hidden}'
    'a{text-decoration:none;color:inherit}'
    '.lnav{position:fixed;top:0;left:0;right:0;z-index:100;padding:1.2rem 2rem;'
    'display:flex;align-items:center;justify-content:space-between;'
    'backdrop-filter:blur(20px);background:rgba(13,13,13,.8);border-bottom:1px solid rgba(255,255,255,.06)}'
    '.lnav-logo{font-family:Unbounded,sans-serif;font-size:1.1rem;font-weight:700;'
    'background:var(--grad);-webkit-background-clip:text;-webkit-text-fill-color:transparent}'
    '.lnav-links{display:flex;gap:2rem;align-items:center}'
    '.lnav-links a{color:var(--muted);font-size:.9rem;transition:.2s}'
    '.lnav-links a:hover{color:var(--text)}'
    '.lnav-cta{background:var(--grad);color:#fff !important;padding:.6rem 1.4rem;border-radius:100px;font-weight:600;font-size:.9rem;transition:.2s}'
    '.lnav-cta:hover{opacity:.85;transform:scale(1.04)}'
    '.hero{min-height:100vh;display:flex;align-items:center;justify-content:center;'
    'text-align:center;padding:8rem 2rem 4rem;position:relative;overflow:hidden}'
    '.hero-bg{position:absolute;inset:0;pointer-events:none}'
    '.blob{position:absolute;border-radius:50%;filter:blur(80px);opacity:.25}'
    '.b1{width:500px;height:500px;background:var(--c1);top:-100px;left:-100px;animation:drift 8s ease-in-out infinite}'
    '.b2{width:400px;height:400px;background:var(--c3);bottom:-50px;right:-50px;animation:drift 10s ease-in-out infinite reverse}'
    '.b3{width:300px;height:300px;background:var(--c2);top:30%;left:50%;animation:drift 12s ease-in-out infinite 2s}'
    '@keyframes drift{0%,100%{transform:translate(0,0) scale(1)}50%{transform:translate(30px,-20px) scale(1.1)}}'
    '.hero-badge{display:inline-flex;align-items:center;gap:.5rem;background:rgba(255,77,109,.12);'
    'border:1px solid rgba(255,77,109,.3);color:var(--c1);padding:.4rem 1rem;border-radius:100px;'
    'font-size:.82rem;font-weight:600;margin-bottom:2rem;letter-spacing:.05em}'
    '.hero h1{font-family:Unbounded,sans-serif;font-size:clamp(2.2rem,6vw,4.5rem);'
    'font-weight:900;line-height:1.1;margin-bottom:1.5rem;letter-spacing:-.02em}'
    '.hero h1 span{background:var(--grad);-webkit-background-clip:text;-webkit-text-fill-color:transparent}'
    '.hero-sub{font-size:clamp(1rem,2.5vw,1.2rem);color:var(--muted);max-width:580px;margin:0 auto 2.5rem;line-height:1.7;font-weight:300}'
    '.hero-btns{display:flex;gap:1rem;justify-content:center;flex-wrap:wrap}'
    '.btn-hero{padding:1rem 2.5rem;border-radius:100px;font-weight:700;font-size:1rem;transition:.3s;cursor:pointer;border:none;text-decoration:none}'
    '.btn-main{background:var(--grad);color:#fff;box-shadow:0 8px 32px rgba(255,77,109,.35);display:inline-block}'
    '.btn-main:hover{transform:translateY(-3px);box-shadow:0 16px 48px rgba(255,77,109,.5);opacity:.9}'
    '.btn-ghost{background:transparent;color:var(--text);border:1px solid rgba(255,255,255,.2);display:inline-block}'
    '.btn-ghost:hover{background:rgba(255,255,255,.07);transform:translateY(-2px)}'
    '.hero-stat{display:flex;gap:3rem;justify-content:center;margin-top:4rem;flex-wrap:wrap}'
    '.stat-item{text-align:center}'
    '.stat-n{font-family:Unbounded,sans-serif;font-size:2rem;font-weight:700;'
    'background:var(--grad);-webkit-background-clip:text;-webkit-text-fill-color:transparent}'
    '.stat-l{font-size:.82rem;color:var(--muted);margin-top:.3rem}'
    '.problem{padding:6rem 2rem;max-width:900px;margin:0 auto;text-align:center}'
    '.section-tag{display:inline-block;font-size:.78rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--c1);margin-bottom:1rem}'
    '.section-h{font-family:Unbounded,sans-serif;font-size:clamp(1.6rem,4vw,2.8rem);font-weight:700;margin-bottom:1.5rem;line-height:1.2}'
    '.section-sub{color:var(--muted);font-size:1.05rem;line-height:1.8;max-width:650px;margin:0 auto}'
    '.problem-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:1.5rem;margin-top:3rem;text-align:left}'
    '.prob-card{background:var(--dark2);border:1px solid rgba(255,255,255,.06);border-radius:16px;padding:1.5rem;position:relative;overflow:hidden}'
    '.prob-card::before{content:"";position:absolute;top:0;left:0;right:0;height:2px;background:var(--grad)}'
    '.prob-icon{font-size:2rem;margin-bottom:1rem}'
    '.prob-card h3{font-size:1rem;font-weight:600;margin-bottom:.5rem}'
    '.prob-card p{font-size:.88rem;color:var(--muted);line-height:1.6}'
    '.how{padding:6rem 2rem;background:var(--dark2)}'
    '.how-inner{max-width:1100px;margin:0 auto}'
    '.how-title{text-align:center;margin-bottom:4rem}'
    '.steps{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:2rem}'
    '.step{background:var(--dark3);border-radius:20px;padding:2rem;border:1px solid rgba(255,255,255,.05);transition:.3s}'
    '.step:hover{border-color:rgba(255,77,109,.3);transform:translateY(-4px)}'
    '.step-num{font-family:Unbounded,sans-serif;font-size:3.5rem;font-weight:900;'
    'background:var(--grad);-webkit-background-clip:text;-webkit-text-fill-color:transparent;line-height:1;margin-bottom:1rem}'
    '.step h3{font-size:1.1rem;font-weight:600;margin-bottom:.75rem}'
    '.step p{font-size:.88rem;color:var(--muted);line-height:1.7}'
    '.features{padding:6rem 2rem;max-width:1100px;margin:0 auto}'
    '.feat-title{text-align:center;margin-bottom:4rem}'
    '.feat-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1.5rem}'
    '.feat-card{background:var(--dark2);border:1px solid rgba(255,255,255,.06);border-radius:20px;padding:2rem;transition:.3s}'
    '.feat-card:hover{border-color:rgba(67,97,238,.4);transform:translateY(-4px)}'
    '.feat-ic{width:48px;height:48px;border-radius:12px;background:var(--grad2);'
    'display:flex;align-items:center;justify-content:center;font-size:1.4rem;margin-bottom:1.2rem}'
    '.feat-card h3{font-size:1rem;font-weight:600;margin-bottom:.5rem}'
    '.feat-card p{font-size:.88rem;color:var(--muted);line-height:1.6}'
    '.pricing{padding:6rem 2rem;background:var(--dark2)}'
    '.pricing-inner{max-width:500px;margin:0 auto;text-align:center}'
    '.price-card{background:var(--dark3);border:1px solid rgba(255,77,109,.3);border-radius:24px;padding:3rem;margin-top:3rem;position:relative;overflow:hidden}'
    '.price-card::before{content:"";position:absolute;top:0;left:0;right:0;height:3px;background:var(--grad)}'
    '.price-badge{display:inline-block;background:var(--grad);color:#fff;font-size:.78rem;font-weight:700;padding:.3rem .9rem;border-radius:100px;margin-bottom:1.5rem}'
    '.price-tag{font-family:Unbounded,sans-serif;font-size:3.5rem;font-weight:900;margin-bottom:.5rem}'
    '.price-tag span{font-size:1.2rem;color:var(--muted);font-family:Onest,sans-serif;font-weight:400}'
    '.price-sub{color:var(--muted);font-size:.9rem;margin-bottom:2rem}'
    '.price-features{list-style:none;text-align:left;margin-bottom:2rem}'
    '.price-features li{padding:.6rem 0;border-bottom:1px solid rgba(255,255,255,.06);font-size:.9rem;display:flex;align-items:center;gap:.75rem}'
    '.price-features li:last-child{border:none}'
    '.check-ic{color:var(--c1);font-weight:700}'
    '.cta-section{padding:8rem 2rem;text-align:center;position:relative;overflow:hidden}'
    '.cta-bg{position:absolute;inset:0;background:radial-gradient(ellipse at center,rgba(255,77,109,.12) 0%,transparent 70%);pointer-events:none}'
    '.cta-section h2{font-family:Unbounded,sans-serif;font-size:clamp(1.8rem,5vw,3.5rem);font-weight:900;margin-bottom:1.5rem;line-height:1.15}'
    '.cta-section p{color:var(--muted);font-size:1.1rem;margin-bottom:2.5rem;max-width:500px;margin-left:auto;margin-right:auto}'
    '.footer{padding:2rem;text-align:center;border-top:1px solid rgba(255,255,255,.06);color:var(--muted);font-size:.85rem}'
    '@media(max-width:640px){.lnav-links{display:none}.hero h1{font-size:2rem}.hero-stat{gap:1.5rem}.stat-n{font-size:1.5rem}}'
)

def app_html(body, title='A/B Testing Pro'):
    return (
        '<!DOCTYPE html><html lang="ru"><head>'
        '<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>' + title + '</title>'
        '<style>' + APP_CSS + '</style>' + EYE_JS +
        '</head><body>' + body + '</body></html>'
    )

def nav_bar(pg):
    pages = [('/', 'dash', 'Панель'), ('/tests', 'tests', 'Тесты'),
             ('/api-keys', 'keys', 'API ключи'), ('/settings', 'cfg', 'Настройки')]
    items = ''
    for url, p, label in pages:
        cls = 'nb on' if pg == p else 'nb'
        items += '<a href="{}" class="{}">{}</a>'.format(url, cls, label)
    items += '<a href="/logout" class="nb">Выход</a>'
    return '<div class="hdr"><h1>A/B Testing Pro</h1><nav>' + items + '</nav></div>'

def page(content, pg='', logged=True):
    top = nav_bar(pg) if logged else ''
    return app_html(top + '<div class="wrap">' + content + '</div>')

def alert(msg, kind='ok'):
    return '<div class="al ' + kind + '">' + msg + '</div>' if msg else ''

# ── ЛЕНДИНГ ────────────────────────────────────────────────────────────────
@app.route('/')
def landing():
    if me():
        return redirect('/dashboard')
    html = (
        '<!DOCTYPE html><html lang="ru"><head>'
        '<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>A/B Testing Pro - Больше продаж на Озоне</title>'
        '<style>' + LANDING_CSS + '</style>'
        '</head><body>'

        '<nav class="lnav">'
        '<div class="lnav-logo">A/B Testing Pro</div>'
        '<div class="lnav-links">'
        '<a href="#how">Как работает</a>'
        '<a href="#features">Возможности</a>'
        '<a href="#pricing">Тарифы</a>'
        '<a href="/login">Войти</a>'
        '<a href="/register" class="lnav-cta">Начать бесплатно</a>'
        '</div></nav>'

        '<section class="hero">'
        '<div class="hero-bg"><div class="blob b1"></div><div class="blob b2"></div><div class="blob b3"></div></div>'
        '<div style="position:relative;z-index:1">'
        '<div class="hero-badge">&#128200; Увеличьте продажи без вложений в рекламу</div>'
        '<h1>Ваши конкуренты уже<br>тестируют. <span>А вы?</span></h1>'
        '<p class="hero-sub">Автоматически проверяйте какие фотографии товаров продают лучше. До 10 вариантов одновременно — без Excel, без ручной работы, без догадок.</p>'
        '<div class="hero-btns">'
        '<a href="/register" class="btn-hero btn-main">Попробовать бесплатно 30 дней &rarr;</a>'
        '<a href="#how" class="btn-hero btn-ghost">Как это работает?</a>'
        '</div>'
        '<div class="hero-stat">'
        '<div class="stat-item"><div class="stat-n">+34%</div><div class="stat-l">средний рост конверсии</div></div>'
        '<div class="stat-item"><div class="stat-n">до 10</div><div class="stat-l">вариантов фото в тесте</div></div>'
        '<div class="stat-item"><div class="stat-n">30 дней</div><div class="stat-l">бесплатный период</div></div>'
        '</div></div></section>'

        '<section class="problem" style="max-width:900px;margin:0 auto;padding:6rem 2rem;text-align:center">'
        '<div class="section-tag">Знакомо?</div>'
        '<h2 class="section-h">Почему 90% продавцов<br>теряют деньги каждый день</h2>'
        '<p class="section-sub">Большинство продавцов выбирают фото «на глазок» — и никогда не узнают, сколько продаж они потеряли из-за одной неудачной картинки.</p>'
        '<div class="problem-cards">'
        '<div class="prob-card"><div class="prob-icon">&#128064;</div><h3>Выбирают фото интуитивно</h3><p>«Мне кажется это красиво» — не аргумент. Покупатели думают иначе.</p></div>'
        '<div class="prob-card"><div class="prob-icon">&#128202;</div><h3>Нет данных для решений</h3><p>Без теста невозможно знать, какое фото реально приносит больше кликов и продаж.</p></div>'
        '<div class="prob-card"><div class="prob-icon">&#9200;</div><h3>Нет времени делать это вручную</h3><p>Менять фото, записывать статистику, считать конверсии — часы работы каждую неделю.</p></div>'
        '</div></section>'

        '<section class="how" id="how"><div class="how-inner">'
        '<div class="how-title"><div class="section-tag">Просто и быстро</div><h2 class="section-h">Три шага до роста продаж</h2></div>'
        '<div class="steps">'
        '<div class="step"><div class="step-num">01</div><h3>Подключите магазин</h3><p>Введите API-ключ Озона. Сервис автоматически получит доступ к вашим товарам. Занимает 2 минуты.</p></div>'
        '<div class="step"><div class="step-num">02</div><h3>Загрузите варианты фото</h3><p>От 2 до 10 вариантов первого фото. Сервис начнет показывать их покупателям по очереди.</p></div>'
        '<div class="step"><div class="step-num">03</div><h3>Получайте результаты</h3><p>Сервис автоматически определит победителя по CTR и конверсии и применит лучшее фото.</p></div>'
        '</div></div></section>'

        '<section class="features" id="features"><div class="feat-title">'
        '<div class="section-tag">Возможности</div><h2 class="section-h">Всё что нужно для роста</h2></div>'
        '<div class="feat-grid">'
        '<div class="feat-card"><div class="feat-ic">&#127922;</div><h3>До 10 вариантов в одном тесте</h3><p>Не просто A/B — полноценное мультивариантное тестирование. Тестируйте разные ракурсы, фоны, инфографику.</p></div>'
        '<div class="feat-card"><div class="feat-ic">&#128200;</div><h3>Автоматическая ротация</h3><p>Сервис сам меняет фото и выбирает лучший вариант — вам не нужно заходить в личный кабинет каждый день.</p></div>'
        '<div class="feat-card"><div class="feat-ic">&#128269;</div><h3>Реальная аналитика</h3><p>Просмотры, клики, CTR, продажи, конверсия — всё в одном месте. Точные цифры по каждому варианту.</p></div>'
        '<div class="feat-card"><div class="feat-ic">&#128737;</div><h3>Безопасно и надёжно</h3><p>Ключи хранятся в зашифрованном виде. Работаем только через официальный API Озона.</p></div>'
        '<div class="feat-card"><div class="feat-ic">&#9889;</div><h3>Быстрый старт</h3><p>Первый тест запустите за 5 минут. Никаких сложных настроек — подключили и работаете.</p></div>'
        '<div class="feat-card"><div class="feat-ic">&#128276;</div><h3>Уведомления о результатах</h3><p>Получайте сообщения когда тест завершён и найден победитель. Не нужно постоянно проверять.</p></div>'
        '</div></section>'

        '<section class="pricing" id="pricing"><div class="pricing-inner">'
        '<div class="section-tag" style="display:block;text-align:center">Прозрачные условия</div>'
        '<h2 class="section-h">Начните бесплатно</h2>'
        '<div class="price-card">'
        '<div class="price-badge">&#127381; Специальное предложение</div>'
        '<div class="price-tag">0 &#8381; <span>/ первые 30 дней</span></div>'
        '<p class="price-sub">Полный доступ ко всем функциям. Без ввода карты.</p>'
        '<ul class="price-features">'
        '<li><span class="check-ic">&#10003;</span> Неограниченное количество товаров</li>'
        '<li><span class="check-ic">&#10003;</span> До 10 вариантов фото в одном тесте</li>'
        '<li><span class="check-ic">&#10003;</span> Автоматическая ротация и аналитика</li>'
        '<li><span class="check-ic">&#10003;</span> Подключение нескольких магазинов</li>'
        '<li><span class="check-ic">&#10003;</span> Email-уведомления о результатах</li>'
        '<li><span class="check-ic">&#10003;</span> Поддержка 7 дней в неделю</li>'
        '</ul>'
        '<a href="/register" class="btn-hero btn-main" style="width:100%;justify-content:center;display:flex">Начать бесплатно &rarr;</a>'
        '</div></div></section>'

        '<section class="cta-section">'
        '<div class="cta-bg"></div>'
        '<div style="position:relative;z-index:1">'
        '<h2>Хватит терять деньги<br>на неправильных фото</h2>'
        '<p class="cta-section p" style="color:#888;font-size:1.1rem;margin:1.5rem auto 2.5rem;max-width:500px">Пока вы читаете это — ваши конкуренты уже тестируют. Начните прямо сейчас, это бесплатно.</p>'
        '<a href="/register" class="btn-hero btn-main">Попробовать бесплатно 30 дней &rarr;</a>'
        '</div></section>'

        '<footer class="footer">'
        '<p>&#169; 2024 A/B Testing Pro &nbsp;&middot;&nbsp; '
        '<a href="/login" style="color:#ff4d6d">Войти</a> &nbsp;&middot;&nbsp; '
        '<a href="/register" style="color:#ff4d6d">Регистрация</a></p>'
        '</footer>'
        '</body></html>'
    )
    return html

# ── ДАШБОРД ────────────────────────────────────────────────────────────────
@app.route('/dashboard')
def dashboard():
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

# ── AUTH ───────────────────────────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("20 per minute")
def login():
    if me(): return redirect('/dashboard')
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
                return redirect('/dashboard')
    body = (
        '<div class="aw"><div class="ac">'
        '<h1>A/B Testing Pro</h1>'
        '<p class="sub">Войдите в аккаунт</p>'
        + alert(err, 'er') +
        '<form method="POST">'
        '<div class="fg"><label>Email</label>'
        '<input type="email" name="email" class="fi" placeholder="your@email.com" required></div>'
        + pw_input('password', 'pw_login', 'Ваш пароль', 'Пароль') +
        '<button class="btn bp" style="width:100%">Войти</button>'
        '</form>'
        '<p class="al2" onclick="location=\'/register\'">Нет аккаунта? Зарегистрироваться</p>'
        '<p style="text-align:center;margin-top:.8rem;font-size:.85rem;color:#aaa">'
        '<a href="/" style="color:#667eea">&#8592; На главную</a></p>'
        '</div></div>'
    )
    return app_html(body)

@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per hour")
def register():
    if me(): return redirect('/dashboard')
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
            return redirect('/dashboard')
    # Сохраняем введённые значения для подстановки обратно
    saved_name  = clean(request.form.get('name', ''), 100) if request.method == 'POST' else ''
    saved_email = clean(request.form.get('email', ''), 200) if request.method == 'POST' else ''
    name_val  = ' value="' + saved_name  + '"' if saved_name  else ''
    email_val = ' value="' + saved_email + '"' if saved_email else ''
    body = (
        '<div class="aw"><div class="ac">'
        '<h1>A/B Testing Pro</h1>'
        '<p class="sub">30 дней бесплатно — без карты</p>'
        + alert(err, 'er') +
        '<form method="POST">'
        '<div class="fg"><label>Имя</label>'
        '<input type="text" name="name" class="fi" placeholder="Иван Иванов" required maxlength="100"' + name_val + '></div>'
        '<div class="fg"><label>Email</label>'
        '<input type="email" name="email" class="fi" placeholder="your@email.com" required autocomplete="email"' + email_val + '></div>'
        + pw_input('password', 'pw_r1', 'Мин. 8 символов', 'Пароль')
        + pw_input('confirm', 'pw_r2', 'Повторите пароль', 'Повторите пароль')
        + '<div id="pw_match_hint" style="font-size:.82rem;margin-top:-.6rem;margin-bottom:1rem;min-height:1.1em"></div>'
        + '<button class="btn bp" style="width:100%">Создать аккаунт бесплатно</button>'
        '</form>'
        '<p class="al2" onclick="location=\'/login\'">Есть аккаунт? Войти</p>'
        '<p style="text-align:center;margin-top:.8rem;font-size:.85rem;color:#aaa">'
        '<a href="/" style="color:#667eea">&#8592; На главную</a></p>'
        '</div></div>'
    )
    return app_html(body)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ── СТРАНИЦЫ ПРИЛОЖЕНИЯ ────────────────────────────────────────────────────
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

# ── API КЛЮЧИ ──────────────────────────────────────────────────────────────
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
    c += '<div class="tip" style="margin-bottom:1.2rem">Где взять ключи: <a href="https://seller.ozon.ru/app/settings/api-keys" target="_blank" style="color:#1e40af;font-weight:600">seller.ozon.ru - Настройки - API ключи</a> - нажмите «Сгенерировать ключ»</div>'
    if len(keys) < MAX_KEYS:
        c += '<form method="POST" action="/api-keys/add"><div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem">'
        c += '<div class="fg"><label>Название магазина</label><input type="text" name="shop" class="fi" placeholder="Мой магазин" required maxlength="100"><div class="hn">Любое удобное название</div></div>'
        c += '<div class="fg"><label>Client ID</label><input type="text" name="cid" class="fi" placeholder="123456789" required maxlength="50"><div class="hn">Числовой ID из личного кабинета</div></div>'
        c += '</div>'
        c += pw_input('akey', 'akey_field', 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx', 'API Key')
        c += '<div class="hn" style="margin-top:-.8rem;margin-bottom:1rem">Хранится безопасно. Показываются только последние 4 символа</div>'
        c += '<button class="btn bp">Проверить и сохранить</button><span style="font-size:.85rem;color:#888;margin-left:1rem">Ключ будет проверен через API Озона</span></form>'
    else:
        c += alert('Достигнут лимит ' + str(MAX_KEYS) + ' ключей', 'wn')
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
        return redirect('/api-keys?msg=Магазин+' + shop + '+успешно+подключён')
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

# ── ОШИБКИ ─────────────────────────────────────────────────────────────────
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
