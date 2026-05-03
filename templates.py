# ── CSS для приложения ────────────────────────────────────────────────────
APP_CSS = (
    '*{margin:0;padding:0;box-sizing:border-box}'
    'body{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;background:#f0f2f5;color:#1a1a2e;min-height:100vh}'
    'a{text-decoration:none;color:inherit}'
    '.hdr{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;padding:1rem 2rem;'
    'display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.8rem;box-shadow:0 2px 8px rgba(0,0,0,.2)}'
    '.hdr h1{font-size:1.4rem;font-weight:700}'
    '.hdr h1 a{color:#fff;text-decoration:none}'
    '.hdr h1 a:hover{opacity:.85}'
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

# ── CSS для лендинга ───────────────────────────────────────────────────────
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
    '.btn-hero{padding:1rem 2.5rem;border-radius:100px;font-weight:700;font-size:1rem;transition:.3s;cursor:pointer;border:none;text-decoration:none;display:inline-block}'
    '.btn-main{background:var(--grad);color:#fff;box-shadow:0 8px 32px rgba(255,77,109,.35)}'
    '.btn-main:hover{transform:translateY(-3px);box-shadow:0 16px 48px rgba(255,77,109,.5);opacity:.9}'
    '.btn-ghost{background:transparent;color:var(--text);border:1px solid rgba(255,255,255,.2)}'
    '.btn-ghost:hover{background:rgba(255,255,255,.07);transform:translateY(-2px)}'
    '.hero-stat{display:flex;gap:3rem;justify-content:center;margin-top:4rem;flex-wrap:wrap}'
    '.stat-item{text-align:center}'
    '.stat-n{font-family:Unbounded,sans-serif;font-size:2rem;font-weight:700;'
    'background:var(--grad);-webkit-background-clip:text;-webkit-text-fill-color:transparent}'
    '.stat-l{font-size:.82rem;color:var(--muted);margin-top:.3rem}'
    '.section-tag{display:inline-block;font-size:.78rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--c1);margin-bottom:1rem}'
    '.section-h{font-family:Unbounded,sans-serif;font-size:clamp(1.6rem,4vw,2.8rem);font-weight:700;margin-bottom:1.5rem;line-height:1.2}'
    '.section-sub{color:var(--muted);font-size:1.05rem;line-height:1.8;max-width:650px;margin:0 auto}'
    '.problem{padding:6rem 2rem;max-width:900px;margin:0 auto;text-align:center}'
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
    '.feat-ic{width:48px;height:48px;border-radius:12px;background:var(--grad2);display:flex;align-items:center;justify-content:center;font-size:1.4rem;margin-bottom:1.2rem}'
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
    '.footer{padding:2rem;text-align:center;border-top:1px solid rgba(255,255,255,.06);color:var(--muted);font-size:.85rem}'
    '@media(max-width:640px){.lnav-links{display:none}.hero h1{font-size:2rem}.hero-stat{gap:1.5rem}.stat-n{font-size:1.5rem}}'
)

# ── JavaScript ─────────────────────────────────────────────────────────────
EYE_JS = """
<script>
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
function checkPasswords() {
    var p1 = document.getElementById('pw_r1');
    var p2 = document.getElementById('pw_r2');
    var hint = document.getElementById('pw_match_hint');
    if (!p1 || !p2 || !hint) return true;
    if (p2.value.length === 0) { hint.textContent = ''; return true; }
    if (p1.value !== p2.value) {
        hint.textContent = 'Пароли не совпадают';
        hint.style.color = '#e74c3c';
        p2.style.borderColor = '#e74c3c';
        return false;
    } else {
        hint.textContent = 'Пароли совпадают \u2713';
        hint.style.color = '#27ae60';
        p2.style.borderColor = '#27ae60';
        return true;
    }
}
document.addEventListener('DOMContentLoaded', function() {
    var p2 = document.getElementById('pw_r2');
    if (p2) {
        p2.addEventListener('input', function() { checkPasswords(); });
        var form = p2.closest('form');
        if (form) form.addEventListener('submit', function(e) {
            if (!checkPasswords()) e.preventDefault();
        });
    }
});
</script>
"""


# ── Компоненты ─────────────────────────────────────────────────────────────

def pw_input(name, field_id, placeholder, label_text='Пароль'):
    return (
        '<div class="fg">'
        '<label style="display:flex;justify-content:space-between;align-items:center">'
        '<span>' + label_text + '</span>'
        '<span onclick="togglePw(\'' + field_id + '\', this)" '
        'style="font-size:.78rem;color:#aaa;cursor:pointer;font-weight:400;user-select:none">показать</span>'
        '</label>'
        '<input type="password" id="' + field_id + '" name="' + name + '" class="fi" placeholder="' + placeholder + '" required>'
        '</div>'
    )


def alert(msg, kind='ok'):
    return '<div class="al ' + kind + '">' + msg + '</div>' if msg else ''


def nav_bar(active_page):
    pages = [
        ('/dashboard', 'dash',    'Дашборд'),
        ('/tests',     'tests',   'Тесты'),
        ('/api-keys',  'keys',    'API ключи'),
        ('/settings',  'cfg',     'Настройки'),
    ]
    items = ''
    for url, pg, label in pages:
        cls = 'nb on' if active_page == pg else 'nb'
        items += '<a href="{}" class="{}">{}</a>'.format(url, cls, label)
    items += '<a href="/logout" class="nb">Выход</a>'
    return '<div class="hdr"><h1><a href="/dashboard">A/B Testing Pro</a></h1><nav>' + items + '</nav></div>'


def render(content, page='', logged=True):
    """Обернуть контент в полноценную HTML страницу."""
    top = nav_bar(page) if logged else ''
    return (
        '<!DOCTYPE html><html lang="ru"><head>'
        '<meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>A/B Testing Pro</title>'
        '<style>' + APP_CSS + '</style>' + EYE_JS +
        '</head><body>' + top + '<div class="wrap">' + content + '</div></body></html>'
    )


def render_auth(content):
    """Страница без навигации (вход/регистрация)."""
    return (
        '<!DOCTYPE html><html lang="ru"><head>'
        '<meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>A/B Testing Pro</title>'
        '<style>' + APP_CSS + '</style>' + EYE_JS +
        '</head><body>' + content + '</body></html>'
    )
