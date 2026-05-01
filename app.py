from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import SECRET_KEY
import database as db

# ── Импорт всех Blueprint'ов ───────────────────────────────────────────────
from landing   import landing_bp
from auth      import auth_bp
from dashboard import dashboard_bp
from api_keys  import api_keys_bp

# ── Создание приложения ────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = SECRET_KEY

# ── Rate limiting (защита от brute-force) ─────────────────────────────────
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=['200 per day', '50 per hour'],
    storage_uri='memory://'
)

# Применяем лимиты к auth маршрутам
limiter.limit('20 per minute')(auth_bp.view_functions['login'])
limiter.limit('5 per hour')(auth_bp.view_functions['register'])
limiter.limit('10 per minute')(api_keys_bp.view_functions['add_key'])

# ── Регистрация Blueprint'ов ───────────────────────────────────────────────
app.register_blueprint(landing_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(api_keys_bp)

# ── Обработчики ошибок ─────────────────────────────────────────────────────
@app.errorhandler(404)
def e404(e):
    return '<div style="text-align:center;padding:4rem"><h2>404 — Страница не найдена</h2><a href="/">На главную</a></div>', 404

@app.errorhandler(429)
def e429(e):
    return '<div style="text-align:center;padding:4rem"><h2>Слишком много запросов</h2><p>Подождите немного</p></div>', 429

@app.errorhandler(500)
def e500(e):
    return '<div style="text-align:center;padding:4rem"><h2>Ошибка сервера</h2><a href="/">На главную</a></div>', 500

# ── Запуск ─────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import os
    db.init_db()  # создаём таблицы при первом запуске
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
