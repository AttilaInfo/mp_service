"""
dashboard.py — настройки пользователя и Blueprint-хаб.
"""
from flask import Blueprint, redirect

import database as db
from templates import render
from auth import me

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/settings')
def settings():
    u = me()
    if not u:
        return redirect('/login')
    kc = db.count_keys(u['id'])
    c = (
        '<p class="ttl">&#9881; Настройки</p>'
        '<div class="box"><h2>&#128100; Профиль</h2>'
        '<table style="width:auto">'
        '<tr><td style="color:#666;padding:.5rem 2rem .5rem 0">Имя:</td><td><strong>' + u['name'] + '</strong></td></tr>'
        '<tr><td style="color:#666;padding:.5rem 2rem .5rem 0">Email:</td><td><strong>' + u['email'] + '</strong></td></tr>'
        '<tr><td style="color:#666;padding:.5rem 2rem .5rem 0">API ключей:</td><td><strong>' + str(kc) + '</strong></td></tr>'
        '<tr><td style="color:#666;padding:.5rem 2rem .5rem 0">Аккаунт создан:</td><td><strong>' + str(u['created_at'])[:10] + '</strong></td></tr>'
        '</table></div>'
    )
    return render(c, 'cfg')
