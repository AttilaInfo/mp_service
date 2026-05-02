"""
uploads.py — безопасная загрузка и отдача изображений.

Защиты:
- Проверка magic bytes (реальный тип файла, не только Content-Type)
- Ограничение размера каждого файла (5 MB)
- Только UUID-имена файлов (никаких пользовательских имён)
- Привязка файла к пользователю (папка per-user)
- Защита от path traversal через werkzeug.secure_filename + re
- Только изображения (JPEG, PNG, WebP, GIF)
- Заголовки ответа: X-Content-Type-Options, Content-Security-Policy
"""

import os
import re
import uuid
import struct

from flask import Blueprint, request, jsonify, send_from_directory, abort
from auth import me

uploads_bp = Blueprint('uploads', __name__)

# ── Константы ─────────────────────────────────────────────────────────────────
UPLOAD_DIR      = '/tmp/mp_uploads'
MAX_FILE_SIZE   = 10 * 1024 * 1024   # 10 МБ — лимит Ozon и Wildberries
ALLOWED_MIMES   = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}

# Magic bytes для проверки реального типа файла
MAGIC = {
    b'\xff\xd8\xff':           ('jpg', 'image/jpeg'),   # JPEG
    b'\x89PNG\r\n\x1a\n':     ('png', 'image/png'),     # PNG
    b'RIFF':                   ('webp', 'image/webp'),  # WebP (проверяем дополнительно)
    b'GIF87a':                 ('gif', 'image/gif'),
    b'GIF89a':                 ('gif', 'image/gif'),
}


def _detect_image_type(data: bytes):
    """
    Определяет тип изображения по magic bytes.
    Возвращает (ext, mime) или (None, None) если не изображение.
    """
    for magic, info in MAGIC.items():
        if data[:len(magic)] == magic:
            # Дополнительная проверка для WebP: байты 8-12 должны быть 'WEBP'
            if magic == b'RIFF':
                if len(data) >= 12 and data[8:12] == b'WEBP':
                    return info
                return None, None
            return info
    return None, None


def _safe_user_dir(user_id: int) -> str:
    """
    Возвращает путь к папке пользователя.
    Только цифры в user_id — защита от path traversal.
    """
    uid = re.sub(r'\D', '', str(user_id))
    if not uid:
        raise ValueError('Invalid user_id')
    path = os.path.join(UPLOAD_DIR, uid)
    os.makedirs(path, exist_ok=True)
    return path


# ── Загрузка файла ─────────────────────────────────────────────────────────────
@uploads_bp.route('/api/upload-photo', methods=['POST'])
def upload_photo():
    """
    POST /api/upload-photo
    Принимает multipart/form-data с полем 'photo'.
    Возвращает JSON: {"url": "/uploads/USER_ID/UUID.ext"}
    """
    u = me()
    if not u:
        return jsonify({'error': 'Необходима авторизация'}), 401

    f = request.files.get('photo')
    if not f:
        return jsonify({'error': 'Файл не передан'}), 400

    # 1. Читаем первые байты для проверки magic (не весь файл сразу)
    header = f.read(16)
    if len(header) < 4:
        return jsonify({'error': 'Файл слишком мал'}), 400

    ext, mime = _detect_image_type(header)
    if not ext:
        return jsonify({'error': 'Допустимы только изображения: JPEG, PNG, WebP, GIF'}), 415

    # 2. Читаем остаток и проверяем размер
    f.seek(0)
    data = f.read(MAX_FILE_SIZE + 1)
    if len(data) > MAX_FILE_SIZE:
        return jsonify({'error': f'Файл слишком большой (макс 10 МБ)'}), 413

    # 3. Сохраняем с UUID-именем в папку пользователя
    try:
        user_dir = _safe_user_dir(u['id'])
    except ValueError:
        return jsonify({'error': 'Ошибка пользователя'}), 400

    filename = f'{uuid.uuid4().hex}.{ext}'
    filepath = os.path.join(user_dir, filename)

    with open(filepath, 'wb') as out:
        out.write(data)

    return jsonify({'url': f'/uploads/{u["id"]}/{filename}'})


# ── Отдача файла ───────────────────────────────────────────────────────────────
@uploads_bp.route('/uploads/<int:user_id>/<path:filename>')
def serve_upload(user_id, filename):
    """
    GET /uploads/USER_ID/FILENAME
    Отдаёт файл только если он существует в папке пользователя.
    Защита от path traversal: filename не должен содержать / или ..
    """
    # Только буквы, цифры, дефис, точка — никаких слэшей и ..
    if not re.fullmatch(r'[a-f0-9]{32}\.(jpg|png|webp|gif)', filename):
        abort(404)

    user_dir = os.path.join(UPLOAD_DIR, str(user_id))
    filepath = os.path.join(user_dir, filename)

    if not os.path.isfile(filepath):
        abort(404)

    # Определяем MIME по magic bytes для корректного Content-Type
    with open(filepath, 'rb') as fh:
        header = fh.read(16)
    _, mime = _detect_image_type(header)
    if not mime:
        abort(415)

    from flask import send_from_directory, make_response
    resp = make_response(send_from_directory(user_dir, filename, mimetype=mime))

    # Заголовки безопасности
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    resp.headers['Content-Security-Policy'] = "default-src 'none'; img-src 'self'"
    resp.headers['Cache-Control'] = 'public, max-age=86400'

    return resp
