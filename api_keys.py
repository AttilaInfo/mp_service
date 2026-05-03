from flask import Blueprint, request, redirect, session
from flask_limiter import Limiter

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

    msg       = request.args.get('msg', '')
    err       = request.args.get('err', '')
    saved_shop = request.args.get('shop', '')
    saved_cid  = request.args.get('cid', '')
    keys = db.get_keys(u['id'])
    cnt  = len(keys)

    c = '<p class="ttl">API ключи Озона</p>'
    c += alert(msg, 'ok')
    c += alert(err, 'er')

    # ── Форма добавления ───────────────────────────────────────────────────
    c += '<div class="box"><h2>Добавить подключение</h2>'
    c += (
        '<div class="tip" style="margin-bottom:1rem">'
        '&#128273; <strong>Где взять ключи:</strong> '
        '<a href="https://seller.ozon.ru/app/settings/api-keys" target="_blank" '
        'style="color:#1e40af;font-weight:600">seller.ozon.ru</a>'
        ' &rarr; Учётная запись (&#128100; в правом верхнем углу) &rarr; Настройки &rarr; Seller API &rarr; нажмите «Сгенерировать ключ»'
        '</div>'
        '<div style="background:#fff8e1;border:1px solid #ffe082;border-radius:10px;padding:1.2rem;margin-bottom:1.2rem">'
        '<p style="font-weight:700;margin-bottom:.8rem;color:#856404">&#9888; Какие права выбрать:</p>'
        '<div style="display:flex;flex-direction:column;gap:.5rem">'
        '<div style="display:flex;gap:.5rem;font-size:.9rem"><span style="color:#27ae60;font-weight:700">&#10003;</span><div><strong>Product read-only</strong> &mdash; чтение данных о товарах</div></div>'
        '<div style="display:flex;gap:.5rem;font-size:.9rem"><span style="color:#27ae60;font-weight:700">&#10003;</span><div><strong>Warehouse</strong> &mdash; для проверки подключения</div></div>'
        '<div style="display:flex;gap:.5rem;font-size:.9rem"><span style="color:#27ae60;font-weight:700">&#10003;</span><div><strong>Report</strong> &mdash; отчёты и статистика</div></div>'
        '<div style="display:flex;gap:.5rem;font-size:.9rem"><span style="color:#27ae60;font-weight:700">&#10003;</span><div><strong>Product</strong> &mdash; управление товарами и фото</div></div>'
        '</div></div>'
    )

    if cnt < MAX_API_KEYS:
        c += (
            '<form method="POST" action="/api-keys/add">'
            '<div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem">'
            '<div class="fg"><label>Название магазина</label>'
            '<input type="text" name="shop" class="fi" placeholder="Мой магазин" required maxlength="100" value="' + saved_shop + '">'
            '<div class="hn">Любое удобное название</div></div>'
            '<div class="fg"><label>Client ID</label>'
            '<input type="text" name="cid" class="fi" placeholder="123456789" required maxlength="50" value="' + saved_cid + '">'
            '<div class="hn">Числовой ID из личного кабинета</div></div>'
            '</div>'
            '<div class="fg">'
            '<label style="display:flex;justify-content:space-between">'
            '<span>API Key</span>'
            '<span onclick="togglePw(\'akey_field\', this)" '
            'style="font-size:.78rem;color:#aaa;cursor:pointer;user-select:none">показать</span>'
            '</label>'
            '<input type="password" id="akey_field" name="akey" class="fi" '
            'placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" required maxlength="200">'
            '<div class="hn">Хранится безопасно. Показываются только последние 4 символа</div>'
            '</div>'
            '<button class="btn bp">Проверить и сохранить</button>'
            '<span style="font-size:.85rem;color:#888;margin-left:1rem">Ключ будет проверен через API Озона</span>'
            '</form>'
        )
    else:
        c += alert(f'Достигнут лимит {MAX_API_KEYS} ключей на аккаунт', 'wn')

    c += '</div>'

    # ── Performance API ────────────────────────────────────────────────────
    perf = db.get_perf_key(u['id'])
    c += '<div class="box"><h2>&#128640; Performance API (для точного CTR)</h2>'
    c += (
        '<div class="tip" style="margin-bottom:1rem">'
        'Performance API даёт точный CTR по каждому рекламному объявлению. '
        'Нужен для тестирования фото с подключённой рекламной кампанией.<br>'
        '<a href="https://seller.ozon.ru/app/settings/performance-api" target="_blank" '
        'style="color:#1e40af;font-weight:600">seller.ozon.ru → Учётная запись → Настройки → Performance API → Создать аккаунт → Добавить ключ</a>'
        '</div>'
    )
    if perf:
        perf_cid   = perf['client_id'][:50] + '...'
        perf_added = str(perf['added_at'])[:10]
        c += '<div style="background:#d4edda;border-radius:10px;padding:1rem;margin-bottom:1rem">'
        c += '<div style="font-weight:700;color:#155724">&#10003; Performance API подключён</div>'
        c += '<div style="font-size:.85rem;color:#444;margin-top:.3rem">Client ID: ' + perf_cid + '</div>'
        c += '<div style="font-size:.8rem;color:#999">Добавлен: ' + perf_added + '</div>'
        c += '<form method="POST" action="/api-keys/perf/del" style="margin-top:.8rem">'
        c += '<button class="btn bd bs" onclick="return confirm(&apos;Удалить Performance API ключ?&apos;)">Удалить</button>'
        c += '</form></div>'
    else:
        c += (
            '<form method="POST" action="/api-keys/perf/add">'
            '<div class="fg"><label>Client ID</label>'
            '<input type="text" name="perf_client_id" class="fi" '
            'placeholder="94436566-...@advertising.performance.ozon.ru" required maxlength="200">'
            '<div class="hn">Формат: 12345-...@advertising.performance.ozon.ru</div></div>'
            '<div class="fg"><label>Client Secret</label>'
            '<input type="password" name="perf_client_secret" class="fi" '
            'placeholder="Ваш Client Secret" required maxlength="300">'
            '<div class="hn">Хранится безопасно</div></div>'
            '<button class="btn bp">Сохранить Performance API ключ</button>'
            '</form>'
        )
    c += '</div>'

    # ── Единая таблица подключений ────────────────────────────────────────
    perf = db.get_perf_key(u['id'])

    c += f'<div class="box"><h2>Ваши подключения</h2>'

    if keys or perf:
        for k in keys:
            dot   = 'dg' if k['active'] else 'dr'
            badge = '<span class="bg g" style="font-size:.75rem">Активен</span>' if k['active'] else '<span class="bg r" style="font-size:.75rem">Ошибка</span>'
            added = str(k['added_at'])[:10] if k.get('added_at') else '-'
            c += '<div style="border:1px solid #e8e8e8;border-radius:12px;margin-bottom:1rem;overflow:hidden">'
            c += '<div style="background:#f5f3ff;padding:.75rem 1rem;border-bottom:1px solid #e8e8e8;display:flex;justify-content:space-between;align-items:center">'
            c += '<div style="font-weight:700;font-size:1rem">&#127978; ' + k['shop_name'] + '</div>'
            c += badge + '</div>'
            c += '<div style="padding:.75rem 1rem;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #f0f0f0">'
            c += '<div>'
            c += '<div style="font-size:.85rem;font-weight:600;color:#444">&#128273; Seller API</div>'
            c += '<div style="font-size:.8rem;color:#888">Client ID: ' + k['client_id'] + ' &nbsp;&middot;&nbsp; Key: ....' + k['hint'] + ' &nbsp;&middot;&nbsp; Добавлен: ' + added + '</div>'
            if k.get('check_msg'):
                c += '<div style="font-size:.78rem;color:#666">' + k['check_msg'] + '</div>'
            c += '</div>'
            c += '<div style="display:flex;gap:.4rem">'
            c += '<form method="POST" action="/api-keys/recheck/' + str(k['id']) + '"><button class="btn bs" style="font-size:.8rem;padding:.3rem .7rem;background:#e8f4fd;color:#1e40af;border:1px solid #bfdbfe" title="Перепроверить">&#128260;</button></form>'
            c += '<form method="POST" action="/api-keys/del/' + str(k['id']) + '"><button class="btn bd bs" style="font-size:.8rem;padding:.3rem .7rem" onclick="return confirm(&apos;Удалить?&apos;)" title="Удалить">&#10005;</button></form>'
            c += '</div></div>'
            c += '<div style="padding:.75rem 1rem;display:flex;justify-content:space-between;align-items:center;background:#fafafa">'
            c += '<div>'
            c += '<div style="font-size:.85rem;font-weight:600;color:#444">&#128640; Performance API</div>'
            if perf:
                perf_added = str(perf['added_at'])[:10]
                c += '<div style="font-size:.8rem;color:#888">Client ID: ' + perf['client_id'][:35] + '... &nbsp;&middot;&nbsp; Добавлен: ' + perf_added + '</div>'
            else:
                c += '<div style="font-size:.8rem;color:#e74c3c">Не подключён — нужен для точного CTR</div>'
            c += '</div>'
            if perf:
                c += '<form method="POST" action="/api-keys/perf/del"><button class="btn bd bs" style="font-size:.8rem;padding:.3rem .7rem" onclick="return confirm(&apos;Удалить Performance API?&apos;)" title="Удалить">&#10005;</button></form>'
            else:
                c += '<a href="#perf_form" class="btn bp" style="font-size:.8rem;padding:.3rem .7rem;white-space:nowrap">Подключить</a>'
            c += '</div>'
            c += '</div>'
    else:
        c += '<div class="empty"><p style="font-size:2rem">&#128273;</p><p style="margin-top:1rem">Нет добавленных ключей</p></div>'

    c += '</div>'

    if not perf:
        c += '<div class="box" id="perf_form"><h2>&#128640; Подключить Performance API</h2>'
        c += (
            '<div class="tip" style="margin-bottom:1rem">'
            'Performance API даёт точный CTR по каждому рекламному объявлению. '
            'Нужен для тестирования фото с подключённой рекламной кампанией.<br>'
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
            '<button class="btn bp">Сохранить Performance API ключ</button>'
            '</form>'
        )
        c += '</div>'
    return render(c, 'keys')
