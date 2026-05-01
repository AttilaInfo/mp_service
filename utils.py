import re
import bcrypt
import requests
from config import OZON_API_URL


# ── Безопасность ───────────────────────────────────────────────────────────

def hash_pw(pw):
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def check_pw(pw, hashed):
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except Exception:
        return False


def valid_email(e):
    return bool(re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', e))


def clean(text, max_len=200):
    """Очистить строку от опасных символов."""
    return str(text).strip()[:max_len].replace('<', '').replace('>', '').replace('"', '')


# ── Озон API ───────────────────────────────────────────────────────────────

def verify_ozon(client_id, api_key):
    """
    Проверить API ключ через реальный запрос к Озону.
    Возвращает (ok: bool, message: str)
    """
    try:
        headers = {
            'Client-Id': client_id,
            'Api-Key': api_key,
            'Content-Type': 'application/json'
        }
        # Пробуем warehouse/list, если 400 — пробуем product/list
        r = requests.post(
            f'{OZON_API_URL}/v1/warehouse/list',
            headers=headers, json={}, timeout=8
        )
        if r.status_code == 200:
            return True, 'Ключ работает'
        if r.status_code == 401:
            return False, 'Неверный Client ID или API Key'
        if r.status_code == 403:
            return False, 'Нет прав — выберите нужные роли'
        # Если 400 — пробуем другой эндпоинт
        if r.status_code == 400:
            r2 = requests.post(
                f'{OZON_API_URL}/v2/product/list',
                headers=headers,
                json={'filter': {}, 'last_id': '', 'limit': 1},
                timeout=8
            )
            if r2.status_code in (200, 400):
                return True, 'Ключ работает'
            if r2.status_code == 401:
                return False, 'Неверный Client ID или API Key'
            if r2.status_code == 403:
                return False, 'Нет прав — выберите нужные роли'
        return False, f'Ошибка Озона: {r.status_code}'
    except requests.exceptions.Timeout:
        return False, 'Озон не отвечает (timeout)'
    except requests.exceptions.ConnectionError:
        return False, 'Нет соединения с Озоном'
    except Exception as ex:
        return False, f'Ошибка: {str(ex)[:80]}'
