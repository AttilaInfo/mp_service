import os

# Количество воркеров
workers = int(os.environ.get('GUNICORN_WORKERS', 2))

# Таймаут — увеличиваем до 120 сек для загрузки файлов до 10 МБ
timeout = 120

# Адрес и порт
bind = f"0.0.0.0:{os.environ.get('PORT', '8080')}"

# Логирование
accesslog = '-'
errorlog = '-'
loglevel = 'info'

# Размер буфера для загрузки файлов (32 МБ)
limit_request_line = 0
limit_request_fields = 200
