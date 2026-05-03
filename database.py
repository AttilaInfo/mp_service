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
            # Performance API ключи
            cur.execute("""
                CREATE TABLE IF NOT EXISTS perf_keys (
                    id          SERIAL PRIMARY KEY,
                    user_id     INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    client_id   TEXT NOT NULL,
                    client_secret TEXT NOT NULL,
                    added_at    TIMESTAMP DEFAULT NOW()
                )
            """)
            # campaign_ids для тестов
            cur.execute("ALTER TABLE tests ADD COLUMN IF NOT EXISTS campaign_ids TEXT DEFAULT ''")

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
    """Получить Performance API ключ пользователя."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM perf_keys WHERE user_id=%s ORDER BY added_at DESC LIMIT 1",
                (user_id,)
            )
            return cur.fetchone()


def save_perf_key(user_id, client_id, client_secret):
    """Сохранить (или обновить) Performance API ключ."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM perf_keys WHERE user_id=%s", (user_id,))
            cur.execute(
                "INSERT INTO perf_keys (user_id, client_id, client_secret) VALUES (%s,%s,%s)",
                (user_id, client_id, client_secret)
            )
        conn.commit()


def delete_perf_key(user_id):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM perf_keys WHERE user_id=%s", (user_id,))
        conn.commit()


def update_test_campaigns(test_id, user_id, campaign_ids):
    """Сохраняет список ID рекламных кампаний для теста (через запятую)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE tests SET campaign_ids=%s WHERE id=%s AND user_id=%s",
                (campaign_ids, test_id, user_id)
            )
        conn.commit()
