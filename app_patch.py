# ═══════════════════════════════════════════════════════════════════
# ПАТЧ ДЛЯ app.py
# Замените блок с импортами и register_blueprint на этот код:
# ═══════════════════════════════════════════════════════════════════

# --- БЫЛО (примерно) ---
# from dashboard import dashboard_bp
# app.register_blueprint(dashboard_bp)

# --- СТАЛО ---
from flask import Flask
from config import SECRET_KEY
from database import init_db

from landing import landing_bp
from auth import auth_bp
from api_keys import api_keys_bp
from analytics import analytics_bp    # ← НОВЫЙ (бывший dashboard: аналитика)
from api import api_bp                # ← НОВЫЙ (JS-файлы + /api/products, /api/check-sku)
from tests import tests_bp            # ← НОВЫЙ (список/создание/детали тестов)
from dashboard import dashboard_bp    # ← ТОЛЬКО /settings теперь
from uploads import uploads_bp        # ← НОВЫЙ (безопасная загрузка фото)

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 МБ — лимит Ozon и Wildberries

app.register_blueprint(landing_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(api_keys_bp)
app.register_blueprint(analytics_bp)
app.register_blueprint(api_bp)
app.register_blueprint(tests_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(uploads_bp)

with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(debug=False)
