import os

# Секретный ключ для сессий — задаётся через переменную окружения Railway
SECRET_KEY = os.environ.get('SECRET_KEY', 'замените-это-в-railway')

# URL API Озона
OZON_API_URL = 'https://api-seller.ozon.ru'

# Лимиты безопасности
MAX_LOGIN_ATTEMPTS = 5       # Максимум попыток входа
LOGIN_BLOCK_MINUTES = 15     # Блокировка на N минут
MAX_API_KEYS_PER_USER = 10   # Максимум ключей на пользователя
