"""
uploads.py — загрузка фото через Telegraph (telegra.ph).

Фото загружаются на telegra.ph и возвращают публичный https:// URL
который принимает API Озона для смены фото на карточке товара.

Локальная копия также сохраняется в /data/uploads для отображения
на сайте (быстрее чем внешний запрос).
"""

import os
import re
import uuid

from flask import Blueprint, request, jsonify, abort, make_response
from flask import send_from_directory
from auth import me

uploads_bp = Blueprint('uploads', __name__)

# ── Константы ──────────────────────────────────────────────────────────────
UPLOAD_DIR    = '/data/uploads'
MAX_FILE_SIZE = 10 * 1024 * 1024   # 10 МБ

MAGIC = {
    b'\xff\xd8\xff':       ('jpg',  'image/jpeg'),
    b'\x89PNG\r\n\x1a\n': ('png',  'image/png'),
    b'RIFF':               ('webp', 'image/webp'),
    b'GIF87a':             ('gif',  'image/gif'),
    b'GIF89a':             ('gif',  'image/gif'),
}


def _detect_image_type(data: bytes):
    for magic, info in MAGIC.items():
        if data[:len(magic)] == magic:
            if magic == b'RIFF':
                if len(data) >= 12 and data[8:12] == b'WEBP':
                    return info
                return None, None
            return info
    return None, None


def _safe_user_dir(user_id: int) -> str:
    uid = re.sub(r'\D', '', str(user_id))
    if not uid:
        raise ValueError('Invalid user_id')
    path = os.path.join(UPLOAD_DIR, uid)
    os.makedirs(path, exist_ok=True)
    return path


# Базовый URL сервиса — фото отдаются публично по HTTPS
# Озон скачает фото по этому URL при ротации
SERVICE_BASE_URL = os.environ.get('SERVICE_URL', 'https://mpservice-production.up.railway.app')


# ── Загрузка ───────────────────────────────────────────────────────────────
@uploads_bp.route('/api/upload-photo', methods=['POST'])
def upload_photo():
    u = me()
    if not u:
        return jsonify({'error': 'Необходима авторизация'}), 401

    f = request.files.get('photo')
    if not f:
        return jsonify({'error': 'Файл не передан'}), 400

    header = f.read(16)
    if len(header) < 4:
        return jsonify({'error': 'Файл слишком мал'}), 400

    ext, mime = _detect_image_type(header)
    if not ext:
        return jsonify({'error': 'Допустимы только JPEG, PNG, WebP, GIF'}), 415

    f.seek(0)
    data = f.read(MAX_FILE_SIZE + 1)
    if len(data) > MAX_FILE_SIZE:
        return jsonify({'error': 'Файл слишком большой (макс 10 МБ)'}), 413

    # 1. Сохраняем локально (для отображения на сайте)
    try:
        user_dir = _safe_user_dir(u['id'])
    except ValueError:
        return jsonify({'error': 'Ошибка пользователя'}), 400

    filename = f'{uuid.uuid4().hex}.{ext}'
    filepath = os.path.join(user_dir, filename)
    with open(filepath, 'wb') as out:
        out.write(data)

    # 2. Загружаем на Telegraph (для Озона — нужен публичный URL)
    # Формируем публичный URL — наш сайт доступен по HTTPS, Озон может скачать фото
    local_path = f'/uploads/{u["id"]}/{filename}'
    public_url = f'{SERVICE_BASE_URL}{local_path}' 

    return jsonify({
        'url':       public_url,
        'local_url': local_path,
    })


# ── Отдача локальных файлов ────────────────────────────────────────────────
@uploads_bp.route('/uploads/<int:user_id>/<path:filename>')
def serve_upload(user_id, filename):
    if not re.fullmatch(r'[a-f0-9]{32}\.(jpg|png|webp|gif)', filename):
        abort(404)

    user_dir = os.path.join(UPLOAD_DIR, str(user_id))
    filepath = os.path.join(user_dir, filename)

    if not os.path.isfile(filepath):
        abort(404)

    with open(filepath, 'rb') as fh:
        header = fh.read(16)
    _, mime = _detect_image_type(header)
    if not mime:
        abort(415)

    resp = make_response(send_from_directory(user_dir, filename, mimetype=mime))
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    resp.headers['Cache-Control']          = 'public, max-age=86400'
    return resp
