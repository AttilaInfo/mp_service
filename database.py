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
                    conversion  FLOAT DEFAULT 0.0
                )
            """)

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
