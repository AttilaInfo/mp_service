import psycopg2
import psycopg2.extras
from config import DATABASE_URL


def get_conn():
    """Получить соединение с БД."""
    return psycopg2.connect(DATABASE_URL)


def init_db():
    """
    Создать все таблицы при первом запуске.
    Безопасно вызывать повторно — IF NOT EXISTS.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:

            # Пользователи
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id          SERIAL PRIMARY KEY,
                    email       TEXT UNIQUE NOT NULL,
                    name        TEXT NOT NULL,
                    password    TEXT NOT NULL,
                    created_at  TIMESTAMP DEFAULT NOW()
                )
            """)

            # API ключи Озона
            cur.execute("""
                CREATE TABLE IF NOT EXISTS api_keys (
                    id          SERIAL PRIMARY KEY,
                    user_id     INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    shop_name   TEXT NOT NULL,
                    client_id   TEXT NOT NULL,
                    api_key     TEXT NOT NULL,
                    hint        TEXT NOT NULL,
                    active      BOOLEAN DEFAULT FALSE,
                    check_msg   TEXT DEFAULT '',
                    added_at    TIMESTAMP DEFAULT NOW()
                )
            """)

            # Тесты
            cur.execute("""
                CREATE TABLE IF NOT EXISTS tests (
                    id          SERIAL PRIMARY KEY,
                    user_id     INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    shop_name   TEXT NOT NULL,
                    sku         TEXT NOT NULL,
                    product_name TEXT NOT NULL,
                    status      TEXT DEFAULT 'running',
                    winner      TEXT DEFAULT '',
                    created_at  TIMESTAMP DEFAULT NOW()
                )
            """)

            # Варианты фото в тесте (от 2 до 10)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS test_variants (
                    id          SERIAL PRIMARY KEY,
                    test_id     INTEGER REFERENCES tests(id) ON DELETE CASCADE,
                    label       TEXT NOT NULL,
                    photo_url   TEXT NOT NULL,
                    views       INTEGER DEFAULT 0,
                    clicks      INTEGER DEFAULT 0,
                    sales       INTEGER DEFAULT 0,
                    ctr         FLOAT DEFAULT 0.0,
                    conversion  FLOAT DEFAULT 0.0,
                    paused      BOOLEAN DEFAULT FALSE
                )
            """)
            # Добавляем колонки если их ещё нет (для существующих БД)
            cur.execute("ALTER TABLE test_variants ADD COLUMN IF NOT EXISTS paused BOOLEAN DEFAULT FALSE")
            cur.execute("ALTER TABLE tests ADD COLUMN IF NOT EXISTS strategy TEXT DEFAULT 'time:30m'")
            cur.execute("ALTER TABLE test_variants ADD COLUMN IF NOT EXISTS activated_at TIMESTAMP DEFAULT NOW()")
            cur.execute("ALTER TABLE test_variants ADD COLUMN IF NOT EXISTS deactivated_at TIMESTAMP DEFAULT NULL")
            cur.execute("ALTER TABLE test_variants ADD COLUMN IF NOT EXISTS views INTEGER DEFAULT 0")
            cur.execute("ALTER TABLE test_variants ADD COLUMN IF NOT EXISTS clicks INTEGER DEFAULT 0")
            cur.execute("ALTER TABLE test_variants ADD COLUMN IF NOT EXISTS tocart INTEGER DEFAULT 0")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS perf_keys (
                    id            SERIAL PRIMARY KEY,
                    user_id       INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    client_id     TEXT NOT NULL,
                    client_secret TEXT NOT NULL,
                    added_at      TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("ALTER TABLE tests ADD COLUMN IF NOT EXISTS campaign_ids TEXT DEFAULT ''")

            # ── Биллинг ────────────────────────────────────────────────────

            # Справочник услуг
            cur.execute("""
                CREATE TABLE IF NOT EXISTS services (
                    id          SERIAL PRIMARY KEY,
                    name        TEXT NOT NULL,
                    slug        TEXT UNIQUE NOT NULL,
                    token_cost  INTEGER NOT NULL DEFAULT 500,
                    active      BOOLEAN DEFAULT TRUE,
                    created_at  TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("""
                INSERT INTO services (name, slug, token_cost, active)
                VALUES ('A/B тест фото', 'ab_test', 500, TRUE)
                ON CONFLICT (slug) DO NOTHING
            """)

            # Баланс токенов пользователя
            cur.execute("""
                CREATE TABLE IF NOT EXISTS token_balances (
                    user_id     INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                    balance     INTEGER NOT NULL DEFAULT 0,
                    updated_at  TIMESTAMP DEFAULT NOW()
                )
            """)

            # История движения токенов
            cur.execute("""
                CREATE TABLE IF NOT EXISTS token_transactions (
                    id          SERIAL PRIMARY KEY,
                    user_id     INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    amount      INTEGER NOT NULL,
                    type        TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    created_at  TIMESTAMP DEFAULT NOW()
                )
            """)

            # Платежи через ЮКассу
            cur.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    id           SERIAL PRIMARY KEY,
                    user_id      INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    yookassa_id  TEXT UNIQUE NOT NULL,
                    amount_rub   INTEGER NOT NULL,
                    tokens       INTEGER NOT NULL,
                    status       TEXT DEFAULT 'pending',
                    created_at   TIMESTAMP DEFAULT NOW()
                )
            """)

            # Промокоды
            cur.execute("""
                CREATE TABLE IF NOT EXISTS promocodes (
                    id          SERIAL PRIMARY KEY,
                    code        TEXT UNIQUE NOT NULL,
                    type        TEXT NOT NULL DEFAULT 'public',
                    tokens      INTEGER NOT NULL,
                    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    max_uses    INTEGER DEFAULT NULL,
                    used_count  INTEGER DEFAULT 0,
                    expires_at  TIMESTAMP DEFAULT NULL,
                    active      BOOLEAN DEFAULT TRUE,
                    utm_source  TEXT DEFAULT '',
                    created_at  TIMESTAMP DEFAULT NOW()
                )
            """)

            # Использования промокодов
            cur.execute("""
                CREATE TABLE IF NOT EXISTS promo_uses (
                    id           SERIAL PRIMARY KEY,
                    promocode_id INTEGER REFERENCES promocodes(id) ON DELETE CASCADE,
                    user_id      INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    created_at   TIMESTAMP DEFAULT NOW(),
                    UNIQUE(promocode_id, user_id)
                )
            """)

            # Рефералы
            cur.execute("""
                CREATE TABLE IF NOT EXISTS referrals (
                    id          SERIAL PRIMARY KEY,
                    referrer_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    referred_id INTEGER UNIQUE REFERENCES users(id) ON DELETE CASCADE,
                    percent     INTEGER NOT NULL DEFAULT 10,
                    created_at  TIMESTAMP DEFAULT NOW()
                )
            """)
            cur.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS ref_code TEXT DEFAULT NULL")
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_ref_code_idx ON users(ref_code) WHERE ref_code IS NOT NULL")

        conn.commit()
    print('БД инициализирована успешно')


# ── Пользователи ───────────────────────────────────────────────────────────

def create_user(email, name, password_hash):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (email, name, password) VALUES (%s, %s, %s) RETURNING id",
                (email, name, password_hash)
            )
            user_id = cur.fetchone()[0]
        conn.commit()
    return user_id


def get_user_by_email(email):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            return cur.fetchone()


def get_user_by_id(user_id):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            return cur.fetchone()


# ── API ключи ──────────────────────────────────────────────────────────────

def get_keys(user_id):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM api_keys WHERE user_id = %s ORDER BY added_at DESC",
                (user_id,)
            )
            return cur.fetchall()


def add_key(user_id, shop_name, client_id, api_key, hint, active, check_msg):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO api_keys
                   (user_id, shop_name, client_id, api_key, hint, active, check_msg)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (user_id, shop_name, client_id, api_key, hint, active, check_msg)
            )
        conn.commit()


def delete_key(key_id, user_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM api_keys WHERE id = %s AND user_id = %s",
                (key_id, user_id)
            )
        conn.commit()


def count_keys(user_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM api_keys WHERE user_id = %s",
                (user_id,)
            )
            return cur.fetchone()[0]


# ── Тесты ──────────────────────────────────────────────────────────────────

def get_tests(user_id):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT t.*, COUNT(v.id) as variant_count
                FROM tests t
                LEFT JOIN test_variants v ON v.test_id = t.id
                WHERE t.user_id = %s
                GROUP BY t.id
                ORDER BY t.created_at DESC
            """, (user_id,))
            return cur.fetchall()


def get_test(test_id, user_id):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM tests WHERE id=%s AND user_id=%s", (test_id, user_id))
            return cur.fetchone()


def create_test(user_id, shop_name, sku, product_name, strategy):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tests (user_id, shop_name, sku, product_name, status) VALUES (%s,%s,%s,%s,'running') RETURNING id",
                (user_id, shop_name, sku, product_name)
            )
            test_id = cur.fetchone()[0]
            # Сохраняем стратегию если колонка есть
            try:
                cur.execute("ALTER TABLE tests ADD COLUMN IF NOT EXISTS strategy TEXT DEFAULT 'round_robin'")
                cur.execute("UPDATE tests SET strategy=%s WHERE id=%s", (strategy, test_id))
            except Exception:
                pass
        conn.commit()
    return test_id


def add_variant(test_id, label, photo_url):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO test_variants (test_id, label, photo_url) VALUES (%s,%s,%s)",
                (test_id, label, photo_url)
            )
        conn.commit()


def get_variants(test_id):
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM test_variants WHERE test_id=%s ORDER BY label", (test_id,))
            return cur.fetchall()


def finish_test(test_id, user_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE tests SET status='completed' WHERE id=%s AND user_id=%s",
                (test_id, user_id)
            )
        conn.commit()


def toggle_variant_pause(variant_id, test_id, user_id):
    """Переключает паузу варианта. Нельзя поставить на паузу если активных < 2."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Проверяем что тест принадлежит пользователю и активен
            cur.execute(
                "SELECT id FROM tests WHERE id=%s AND user_id=%s AND status='running'",
                (test_id, user_id)
            )
            if not cur.fetchone():
                return False, 'Тест не найден или завершён'

            # Получаем текущий статус варианта
            cur.execute(
                "SELECT paused FROM test_variants WHERE id=%s AND test_id=%s",
                (variant_id, test_id)
            )
            row = cur.fetchone()
            if not row:
                return False, 'Вариант не найден'

            currently_paused = row['paused']

            # Если хотим поставить на паузу — проверяем что останется минимум 2 активных
            if not currently_paused:
                cur.execute(
                    "SELECT COUNT(*) as cnt FROM test_variants WHERE test_id=%s AND paused=FALSE",
                    (test_id,)
                )
                active_count = cur.fetchone()['cnt']
                if active_count <= 2:
                    return False, 'Нельзя — должно остаться минимум 2 активных варианта'

            # Переключаем
            cur.execute(
                "UPDATE test_variants SET paused=%s WHERE id=%s AND test_id=%s",
                (not currently_paused, variant_id, test_id)
            )
        conn.commit()
    return True, 'paused' if not currently_paused else 'resumed'


def delete_test(test_id, user_id):
    """Удаляет завершённый тест (каскадно удаляет варианты)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM tests WHERE id=%s AND user_id=%s AND status='completed'",
                (test_id, user_id)
            )
        conn.commit()


def update_test_strategy(test_id, user_id, strategy):
    """Обновляет стратегию активного теста."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE tests SET strategy=%s WHERE id=%s AND user_id=%s AND status='running'",
                (strategy, test_id, user_id)
            )
        conn.commit()


def activate_variant(test_id, label):
    """Отмечает вариант как активный (сохраняет время активации)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            # Деактивируем предыдущий активный вариант
            cur.execute("""
                UPDATE test_variants
                SET deactivated_at = NOW()
                WHERE test_id = %s AND deactivated_at IS NULL AND label != %s
            """, (test_id, label))
            # Активируем новый
            cur.execute("""
                UPDATE test_variants
                SET activated_at = NOW(), deactivated_at = NULL
                WHERE test_id = %s AND label = %s
            """, (test_id, label))
        conn.commit()


def update_variant_stats(variant_id, views, clicks, tocart):
    """Обновляет накопленную статистику варианта."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            ctr = round(clicks / views * 100, 2) if views > 0 else 0.0
            cur.execute("""
                UPDATE test_variants
                SET views = views + %s,
                    clicks = clicks + %s,
                    tocart = tocart + %s,
                    ctr = %s
                WHERE id = %s
            """, (views, clicks, tocart, ctr, variant_id))
        conn.commit()


# ── Performance API ────────────────────────────────────────────────────────

def get_perf_key(user_id):
    """Получить первый Performance API ключ (обратная совместимость)."""
    keys = get_perf_keys(user_id)
    return keys[0] if keys else None


def get_perf_keys(user_id):
    """Получить все Performance API ключи пользователя."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM perf_keys WHERE user_id=%s ORDER BY added_at DESC", (user_id,))
            return cur.fetchall()


def save_perf_key(user_id, client_id, client_secret):
    """Добавить Performance API ключ."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO perf_keys (user_id, client_id, client_secret) VALUES (%s,%s,%s)",
                        (user_id, client_id, client_secret))
        conn.commit()


def delete_perf_key(user_id):
    """Удалить все Performance API ключи пользователя."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM perf_keys WHERE user_id=%s", (user_id,))
        conn.commit()


def delete_perf_key_by_id(perf_id, user_id):
    """Удалить конкретный Performance API ключ."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM perf_keys WHERE id=%s AND user_id=%s", (perf_id, user_id))
        conn.commit()


def update_test_campaigns(test_id, user_id, campaign_ids):
    """Сохраняет список ID рекламных кампаний для теста."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE tests SET campaign_ids=%s WHERE id=%s AND user_id=%s",
                        (campaign_ids, test_id, user_id))
        conn.commit()


# ── Токены и баланс ────────────────────────────────────────────────────────

def get_balance(user_id):
    """Получить текущий баланс токенов пользователя."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT balance FROM token_balances WHERE user_id=%s", (user_id,))
            row = cur.fetchone()
            return row[0] if row else 0


def add_tokens(user_id, amount, tx_type, description=''):
    """Пополнить баланс токенов и записать транзакцию."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO token_balances (user_id, balance, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (user_id) DO UPDATE
                SET balance = token_balances.balance + %s, updated_at = NOW()
            """, (user_id, amount, amount))
            cur.execute("""
                INSERT INTO token_transactions (user_id, amount, type, description)
                VALUES (%s, %s, %s, %s)
            """, (user_id, amount, tx_type, description))
        conn.commit()


def spend_tokens(user_id, amount, description=''):
    """
    Списать токены. Возвращает (True, '') или (False, сообщение об ошибке).
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT balance FROM token_balances WHERE user_id=%s FOR UPDATE", (user_id,))
            row = cur.fetchone()
            balance = row[0] if row else 0
            if balance < amount:
                return False, f'Недостаточно токенов. Баланс: {balance}, нужно: {amount}'
            cur.execute("""
                UPDATE token_balances SET balance = balance - %s, updated_at = NOW()
                WHERE user_id = %s
            """, (amount, user_id))
            cur.execute("""
                INSERT INTO token_transactions (user_id, amount, type, description)
                VALUES (%s, %s, 'spend', %s)
            """, (user_id, -amount, description))
        conn.commit()
    return True, ''


def get_transactions(user_id, limit=50):
    """История транзакций токенов пользователя."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM token_transactions
                WHERE user_id = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (user_id, limit))
            return cur.fetchall()


# ── Платежи ────────────────────────────────────────────────────────────────

def create_payment(user_id, yookassa_id, amount_rub, tokens):
    """Создать запись о платеже со статусом pending."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO payments (user_id, yookassa_id, amount_rub, tokens, status)
                VALUES (%s, %s, %s, %s, 'pending')
                RETURNING id
            """, (user_id, yookassa_id, amount_rub, tokens))
            payment_id = cur.fetchone()[0]
        conn.commit()
    return payment_id


def update_payment_status(yookassa_id, status):
    """Обновить статус платежа. Возвращает данные платежа или None."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                UPDATE payments SET status = %s
                WHERE yookassa_id = %s AND status = 'pending'
                RETURNING *
            """, (status, yookassa_id))
            row = cur.fetchone()
        conn.commit()
    return row


def get_payments(user_id, limit=20):
    """История платежей пользователя."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM payments WHERE user_id = %s
                ORDER BY created_at DESC LIMIT %s
            """, (user_id, limit))
            return cur.fetchall()


# ── Услуги ─────────────────────────────────────────────────────────────────

def get_service(slug):
    """Получить услугу по slug."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM services WHERE slug=%s AND active=TRUE", (slug,))
            return cur.fetchone()


def get_services():
    """Все активные услуги."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM services WHERE active=TRUE ORDER BY id")
            return cur.fetchall()


def get_all_services():
    """Все услуги включая неактивные (для админки)."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM services ORDER BY id")
            return cur.fetchall()


def update_service_cost(slug, token_cost):
    """Изменить стоимость услуги (для админки)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE services SET token_cost=%s WHERE slug=%s",
                (token_cost, slug)
            )
        conn.commit()


# ── Промокоды ──────────────────────────────────────────────────────────────

def create_promocode(code, tokens, promo_type='public', user_id=None,
                     max_uses=None, expires_at=None, utm_source=''):
    """Создать промокод."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO promocodes
                (code, type, tokens, user_id, max_uses, expires_at, utm_source)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (code.upper(), promo_type, tokens, user_id, max_uses, expires_at, utm_source))
            promo_id = cur.fetchone()[0]
        conn.commit()
    return promo_id


def get_promocode(code):
    """Получить промокод по коду."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM promocodes WHERE code=%s", (code.upper(),))
            return cur.fetchone()


def use_promocode(code, user_id):
    """
    Применить промокод. Проверяет:
    - активность, срок действия, лимит использований
    - не использован ли уже этим пользователем
    Возвращает (tokens: int, '') или (0, сообщение_об_ошибке).
    """
    from datetime import datetime
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM promocodes WHERE code=%s FOR UPDATE", (code.upper(),))
            promo = cur.fetchone()
            if not promo:
                return 0, 'Промокод не найден'
            if not promo['active']:
                return 0, 'Промокод недействителен'
            if promo['expires_at'] and promo['expires_at'] < datetime.now():
                return 0, 'Срок действия промокода истёк'
            if promo['max_uses'] and promo['used_count'] >= promo['max_uses']:
                return 0, 'Промокод исчерпан'
            if promo['type'] == 'personal' and promo['user_id'] != user_id:
                return 0, 'Этот промокод предназначен для другого пользователя'
            # Проверяем не использовал ли уже
            cur.execute(
                "SELECT id FROM promo_uses WHERE promocode_id=%s AND user_id=%s",
                (promo['id'], user_id)
            )
            if cur.fetchone():
                return 0, 'Вы уже использовали этот промокод'
            # Применяем
            cur.execute(
                "UPDATE promocodes SET used_count = used_count + 1 WHERE id=%s",
                (promo['id'],)
            )
            cur.execute(
                "INSERT INTO promo_uses (promocode_id, user_id) VALUES (%s, %s)",
                (promo['id'], user_id)
            )
        conn.commit()
    # Начисляем токены
    add_tokens(user_id, promo['tokens'], 'promo', f'Промокод {code.upper()}')
    return promo['tokens'], ''


def deactivate_promocode(code):
    """Отключить промокод."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE promocodes SET active=FALSE WHERE code=%s", (code.upper(),))
        conn.commit()


def get_promo_stats(code):
    """Статистика использования промокода."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT p.*, COUNT(pu.id) as uses_count
                FROM promocodes p
                LEFT JOIN promo_uses pu ON pu.promocode_id = p.id
                WHERE p.code = %s
                GROUP BY p.id
            """, (code.upper(),))
            return cur.fetchone()


def get_all_promocodes():
    """Все промокоды (для админки)."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT p.*, COUNT(pu.id) as uses_count
                FROM promocodes p
                LEFT JOIN promo_uses pu ON pu.promocode_id = p.id
                GROUP BY p.id
                ORDER BY p.created_at DESC
            """)
            return cur.fetchall()


# ── Реферальная программа ──────────────────────────────────────────────────

def create_referral(referrer_id, referred_id, percent=10):
    """Записать реферальную связь."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO referrals (referrer_id, referred_id, percent)
                VALUES (%s, %s, %s)
                ON CONFLICT (referred_id) DO NOTHING
            """, (referrer_id, referred_id, percent))
        conn.commit()


def get_referral_info(user_id):
    """Получить реферала для этого пользователя (кто его пригласил)."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM referrals WHERE referred_id=%s", (user_id,))
            return cur.fetchone()


def get_referral_earnings(user_id):
    """
    Статистика реферальной программы для пользователя:
    количество рефералов и сколько токенов заработано.
    """
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT COUNT(*) as count FROM referrals WHERE referrer_id=%s", (user_id,))
            referral_count = cur.fetchone()['count']
            cur.execute("""
                SELECT COALESCE(SUM(ABS(amount)), 0) as earned
                FROM token_transactions
                WHERE user_id=%s AND type='referral'
            """, (user_id,))
            earned = cur.fetchone()['earned']
    return {'count': referral_count, 'earned': earned}


def pay_referral_bonus(referred_id, payment_amount_rub):
    """
    Начислить реферальный бонус рефереру при пополнении реферала.
    Вызывается из webhook ЮКассы после успешной оплаты.
    """
    referral = get_referral_info(referred_id)
    if not referral:
        return
    bonus_tokens = int(payment_amount_rub * referral['percent'] / 100)
    if bonus_tokens > 0:
        add_tokens(
            referral['referrer_id'],
            bonus_tokens,
            'referral',
            f'Реферальный бонус {referral["percent"]}% от пополнения реферала'
        )


def get_user_by_ref_code(ref_code):
    """Найти пользователя по реферальному коду."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE ref_code=%s", (ref_code,))
            return cur.fetchone()


def set_ref_code(user_id, ref_code):
    """Установить реферальный код пользователю."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET ref_code=%s WHERE id=%s",
                (ref_code, user_id)
            )
        conn.commit()


# ── Админка ────────────────────────────────────────────────────────────────

def get_all_users_with_balance():
    """Все пользователи с балансами (для админки)."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT u.id, u.email, u.name, u.created_at, u.ref_code,
                       COALESCE(tb.balance, 0) as balance
                FROM users u
                LEFT JOIN token_balances tb ON tb.user_id = u.id
                ORDER BY u.created_at DESC
            """)
            return cur.fetchall()


def get_admin_stats():
    """Общая статистика для дашборда администратора."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT COUNT(*) as total FROM users")
            total_users = cur.fetchone()['total']
            cur.execute("SELECT COUNT(*) as total FROM tests WHERE status='running'")
            active_tests = cur.fetchone()['total']
            cur.execute("""
                SELECT COALESCE(SUM(amount_rub), 0) as total
                FROM payments WHERE status='succeeded'
            """)
            total_revenue = cur.fetchone()['total']
            cur.execute("SELECT COUNT(*) as total FROM payments WHERE status='succeeded'")
            total_payments = cur.fetchone()['total']
    return {
        'total_users': total_users,
        'active_tests': active_tests,
        'total_revenue': total_revenue,
        'total_payments': total_payments,
    }


def admin_adjust_tokens(user_id, amount, description='Ручная корректировка администратором'):
    """Вручную добавить или снять токены (для админки). amount может быть отрицательным."""
    if amount >= 0:
        add_tokens(user_id, amount, 'admin', description)
    else:
        spend_tokens(user_id, abs(amount), description)
