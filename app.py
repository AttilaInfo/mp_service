import os
from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from config import SECRET_KEY, DATABASE_URL
import database as db

from landing   import landing_bp
from auth      import auth_bp
from dashboard import dashboard_bp
from api_keys  import api_keys_bp

app = Flask(__name__)
app.secret_key = SECRET_KEY

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=['200 per day', '50 per hour'],
    storage_uri='memory://'
)

app.register_blueprint(landing_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(api_keys_bp)

# Создаём таблицы при старте
if DATABASE_URL:
    try:
        db.init_db()
        print('БД инициализирована')
    except Exception as e:
        print(f'Ошибка инициализации БД: {e}')
else:
    print('ВНИМАНИЕ: DATABASE_URL не задан!')

@app.errorhandler(404)
def e404(e):
    return '<div style="font-family:sans-serif;text-align:center;padding:4rem"><h2>404 — Страница не найдена</h2><br><a href="/">На главную</a></div>', 404

@app.errorhandler(429)
def e429(e):
    return '<div style="font-family:sans-serif;text-align:center;padding:4rem"><h2>Слишком много запросов</h2><p>Подождите немного</p></div>', 429

@app.errorhandler(500)
def e500(e):
    return '<div style="font-family:sans-serif;text-align:center;padding:4rem"><h2>Ошибка сервера</h2><br><a href="/">На главную</a></div>', 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
