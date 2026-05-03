"""
rotation.py — воркер ротации фото для A/B тестов.

Запускается по cron каждые 15 минут (Railway Cron Service).
Для каждого активного теста:
  1. Проверяет не пора ли менять фото (по стратегии: time / views / clicks)
  2. Получает свежую статистику из Озона и обновляет БД
  3. Меняет главное фото товара через API Озона
  4. Завершает тест если слабейший вариант набрал 10 000 показов
"""

import os
import sys
import time
import logging
from datetime import datetime, timedelta, timezone

import requests
import psycopg2
import psycopg2.extras

# ── Конфиг ────────────────────────────────────────────────────────────────────
DATABASE_URL = os.environ.get('DATABASE_URL', '')
OZON_API_URL = 'https://api-seller.ozon.ru'
ROTATION_THRESHOLD_VIEWS = 10_000   # показов у слабейшего → завершаем тест

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [rotation] %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
log = logging.getLogger('rotation')


# ── БД ────────────────────────────────────────────────────────────────────────

def get_conn():
    return psycopg2.connect(DATABASE_URL)


def init_rotation_columns():
    """Добавляем колонки если их ещё нет."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                ALTER TABLE tests
                    ADD COLUMN IF NOT EXISTS strategy        TEXT    DEFAULT 'time:30m',
                    ADD COLUMN IF NOT EXISTS current_variant TEXT    DEFAULT 'A',
                    ADD COLUMN IF NOT EXISTS last_rotated_at TIMESTAMP DEFAULT NOW(),
                    ADD COLUMN IF NOT EXISTS rotation_count  INTEGER DEFAULT 0
            """)
            cur.execute("ALTER TABLE test_variants ADD COLUMN IF NOT EXISTS views_at_rotation INTEGER DEFAULT 0")
            cur.execute("ALTER TABLE test_variants ADD COLUMN IF NOT EXISTS activated_at TIMESTAMP DEFAULT NOW()")
            cur.execute("ALTER TABLE test_variants ADD COLUMN IF NOT EXISTS tocart INTEGER DEFAULT 0")
        conn.commit()
    log.info('Колонки ротации готовы')


# ── Парсинг стратегии ─────────────────────────────────────────────────────────

def parse_strategy(strategy_str):
    """
    Возвращает dict с типом и порогом.
    'time:30m'   → {'type': 'time',   'minutes': 30}
    'views:200'  → {'type': 'views',  'count': 200}
    'clicks:50'  → {'type': 'clicks', 'count': 50}
    """
    if not strategy_str:
        return {'type': 'time', 'minutes': 30}
    if strategy_str.startswith('time:'):
        val = strategy_str[5:].rstrip('m')
        try:
            return {'type': 'time', 'minutes': max(5, int(val))}
        except ValueError:
            return {'type': 'time', 'minutes': 30}
    if strategy_str.startswith('views:'):
        try:
            return {'type': 'views', 'count': max(50, int(strategy_str[6:]))}
        except ValueError:
            return {'type': 'views', 'count': 100}
    if strategy_str.startswith('clicks:'):
        try:
            return {'type': 'clicks', 'count': max(20, int(strategy_str[7:]))}
        except ValueError:
            return {'type': 'clicks', 'count': 20}
    return {'type': 'time', 'minutes': 30}


def should_rotate(test, variant, strategy):
    """
    Проверяет нужно ли делать ротацию прямо сейчас.
    Возвращает True / False.
    """
    s = strategy
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    if s['type'] == 'time':
        # Если ротаций ещё не было — первая ротация сразу
        if not (test.get('rotation_count') or 0):
            return True
        last = test.get('last_rotated_at')
        if not last:
            return True
        if isinstance(last, str):
            last = datetime.fromisoformat(last)
        elapsed_minutes = (now - last).total_seconds() / 60
        return elapsed_minutes >= s['minutes']

    if s['type'] == 'views':
        # Ротируем когда текущий вариант набрал нужное число показов
        # сверх того что было при последней ротации
        current_views = (variant.get('views') or 0)
        views_at_rotation = (variant.get('views_at_rotation') or 0)
        return (current_views - views_at_rotation) >= s['count']

    if s['type'] == 'clicks':
        current_clicks = (variant.get('clicks') or 0)
        return current_clicks >= s['count']

    return False


# ── Озон API ──────────────────────────────────────────────────────────────────

def ozon_headers(key):
    return {
        'Client-Id':    key['client_id'],
        'Api-Key':      key['api_key'],
        'Content-Type': 'application/json',
    }


def get_product_info(key, offer_id):
    """Получить текущую информацию о товаре."""
    try:
        r = requests.post(
            f'{OZON_API_URL}/v3/product/info/list',
            headers=ozon_headers(key),
            json={'offer_id': [offer_id]},
            timeout=15
        )
        log.info(f'  product/info/list status={r.status_code} body={r.text[:300]}')
        if r.status_code == 200:
            data  = r.json()
            items = (data.get('result') or {}).get('items') or data.get('items') or []
            if items:
                return items[0]
            # Если по offer_id не нашли — пробуем без фильтра (первый товар)
            log.warning(f'  Товар {offer_id} не найден по offer_id, пробуем product/list')
            r2 = requests.post(
                f'{OZON_API_URL}/v3/product/list',
                headers=ozon_headers(key),
                json={'filter': {'offer_id': [offer_id]}, 'limit': 1},
                timeout=15
            )
            log.info(f'  product/list status={r2.status_code} body={r2.text[:300]}')
            if r2.status_code == 200:
                pids = [x['product_id'] for x in r2.json().get('result', {}).get('items', [])]
                if pids:
                    r3 = requests.post(
                        f'{OZON_API_URL}/v3/product/info/list',
                        headers=ozon_headers(key),
                        json={'product_id': pids},
                        timeout=15
                    )
                    if r3.status_code == 200:
                        items3 = (r3.json().get('result') or {}).get('items') or []
                        return items3[0] if items3 else None
        log.warning(f'  product/info/list {r.status_code}: {r.text[:200]}')
    except Exception as e:
        log.error(f'get_product_info error: {e}')
    return None


def set_main_photo(key, offer_id, product_id, photo_url, rest_images):
    """
    Меняет главное фото товара через /v1/product/pictures/import.
    photo_url — новое главное фото (первое).
    rest_images — остальные фото в нужном порядке (оригиналы Озона → варианты).
    """
    # Первое фото = тестовый вариант, остальные — в переданном порядке
    images = [photo_url] + [
        img for img in rest_images
        if isinstance(img, str) and img.startswith('http') and img != photo_url
    ]

    payload = {
        'product_id':  product_id,
        'images':      images[:15],  # Озон принимает до 15 фото
        'color_image': ''
    }
    try:
        r = requests.post(
            f'{OZON_API_URL}/v1/product/pictures/import',
            headers=ozon_headers(key),
            json=payload,
            timeout=20
        )
        log.info(f'  pictures/import status={r.status_code} body={r.text[:300]}')
        if r.status_code == 200:
            result = r.json()
            # Озон возвращает task_id — фото применяется асинхронно
            task_id = result.get('task_id') or result.get('result', {}).get('task_id')
            log.info(f'  Фото отправлено в Озон: {offer_id} → {photo_url[:60]} task_id={task_id}')
            return True
        log.warning(f'  pictures/import {r.status_code}: {r.text[:300]}')
    except Exception as e:
        log.error(f'  set_main_photo error: {e}')
    return False


def get_analytics(key, offer_id, date_from, date_to):
    """
    Получить статистику товара из Озона за период.
    Возвращает dict {views, clicks, orders} или None.
    """
    try:
        r = requests.post(
            f'{OZON_API_URL}/v1/analytics/data',
            headers=ozon_headers(key),
            json={
                'date_from':  date_from,
                'date_to':    date_to,
                'metrics':    ['hits_view', 'hits_tocart', 'orders_count'],
                'dimension':  ['offer_id'],
                'filters': [{
                    'key':       'offer_id',
                    'op':        'EQ',
                    'value':     offer_id,
                }],
                'limit': 1,
            },
            timeout=15
        )
        if r.status_code == 200:
            rows = r.json().get('result', {}).get('data', [])
            if rows:
                m = rows[0].get('metrics', [0, 0, 0])
                return {
                    'views':   int(m[0]) if len(m) > 0 else 0,
                    'clicks':  int(m[1]) if len(m) > 1 else 0,
                    'orders':  int(m[2]) if len(m) > 2 else 0,
                }
        elif r.status_code == 429:
            log.warning('  Озон: rate limit (429), пауза 2 сек')
            time.sleep(2)
    except Exception as e:
        log.error(f'  get_analytics error: {e}')
    return None


# ── Обновление статистики вариантов ──────────────────────────────────────────

def update_variant_stats(conn, test, variants, key):
    """
    Запрашивает аналитику из Озона за всё время теста
    и обновляет views/clicks/sales/ctr в test_variants.
    """
    created_at = test.get('created_at') or datetime.now(timezone.utc).replace(tzinfo=None)
    if isinstance(created_at, str):
        created_at = datetime.fromisoformat(created_at)
    date_from = created_at.strftime('%Y-%m-%d')
    date_to   = datetime.now(timezone.utc).replace(tzinfo=None).strftime('%Y-%m-%d')

    stats = get_analytics(key, test['sku'], date_from, date_to)
    if not stats:
        return

    # Распределяем общую статистику пропорционально времени показа каждого варианта.
    # Точная атрибуция будет когда Озон откроет аналитику по фото — пока так.
    total_variants = len(variants)
    rotation_count = test.get('rotation_count') or 0
    total_slots    = max(rotation_count + 1, total_variants)

    with conn.cursor() as cur:
        for i, v in enumerate(variants):
            # Каждому варианту — доля пропорционально числу его «слотов»
            slots = max(1, total_slots // total_variants)
            views  = int(stats['views']  * slots / total_slots)
            clicks = int(stats['clicks'] * slots / total_slots)
            sales  = int(stats['orders'] * slots / total_slots)
            ctr    = round(clicks / views * 100, 2) if views > 0 else 0.0
            conv   = round(sales  / views,        4) if views > 0 else 0.0

            cur.execute("""
                UPDATE test_variants
                SET views=%s, clicks=%s, sales=%s, ctr=%s, conversion=%s
                WHERE id=%s
            """, (views, clicks, sales, ctr, conv, v['id']))
    conn.commit()
    log.info(f'  Статистика обновлена: {stats}')


# ── Следующий вариант ─────────────────────────────────────────────────────────

def next_variant(variants, current_label):
    """Round-robin: следующий вариант после current_label."""
    labels = [v['label'] for v in variants]
    if not labels:
        return None
    try:
        idx = labels.index(current_label)
        return variants[(idx + 1) % len(variants)]
    except ValueError:
        return variants[0]


def weakest_variant(variants):
    """Вариант с наименьшим числом показов."""
    return min(variants, key=lambda v: v.get('views') or 0)



def _collect_variant_stats(conn, test, key, variant, all_variants):
    """Запрашивает статистику из Озона за период активности варианта."""
    activated_at = variant.get('activated_at')
    # Если activated_at пустой — используем дату создания теста как запасной вариант
    if not activated_at:
        activated_at = test.get('created_at')
    if not activated_at:
        return
    if isinstance(activated_at, str):
        try:
            activated_at = datetime.fromisoformat(activated_at.replace('Z', ''))
        except Exception:
            return

    date_from = activated_at.strftime('%Y-%m-%d')
    date_to   = datetime.now(timezone.utc).replace(tzinfo=None).strftime('%Y-%m-%d')
    if date_from > date_to:
        return

    log.info(f'  Сбор статистики {variant["label"]}: {date_from} → {date_to} SKU={test["sku"]}')
    try:
        r = requests.post(
            f'{OZON_API_URL}/v1/analytics/data',
            headers=ozon_headers(key),
            json={
                'date_from': date_from,
                'date_to':   date_to,
                'metrics':   ['hits_view_pdp', 'hits_tocart', 'revenue', 'ordered_units'],
                'dimension': ['offer_id'],
                'limit':     1000,
            },
            timeout=20
        )
        log.info(f'  analytics status={r.status_code} body={r.text[:400]}')
        if r.status_code == 200:
            rows = r.json().get('result', {}).get('data', [])
            if rows:
                # Ищем строку с нашим SKU (dimension=offer_id)
                sku = test['sku']
                row = next(
                    (r for r in rows
                     if (r.get('dimensions') or [{}])[0].get('id') == sku),
                    None
                )
                if not row:
                    log.warning(f'  SKU {sku} не найден в аналитике, примеры: {[(r.get("dimensions") or [{}])[0].get("id") for r in rows[:3]]}')
                    return
                m      = row.get('metrics', [0, 0])
                views  = int(m[0]) if len(m) > 0 else 0
                tocart = int(m[1]) if len(m) > 1 else 0
                clicks = tocart
                n      = max(1, len([v for v in all_variants if not v.get('paused')]))
                views_v  = views  // n
                tocart_v = tocart // n
                clicks_v = clicks // n
                ctr = round(clicks_v / views_v * 100, 2) if views_v > 0 else 0.0
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE test_variants SET views=%s, clicks=%s, tocart=%s, ctr=%s WHERE id=%s",
                        (views_v, tocart_v, tocart_v, ctr, variant['id'])
                    )
                conn.commit()
                log.info(f'  Статистика {variant["label"]}: показы={views_v} клики={clicks_v} корзина={tocart_v}')
            else:
                log.warning(f'  analytics: пустой ответ (нет данных за период)')
        elif r.status_code == 429:
            log.warning('  analytics rate limit')
    except Exception as e:
        log.error(f'  _collect_variant_stats: {e}')


# ── Основная логика ───────────────────────────────────────────────────────────

def process_test(conn, test, key):
    """Обрабатывает один активный тест."""
    test_id  = test['id']
    sku      = test['sku']
    strategy = parse_strategy(test.get('strategy') or 'time:30m')
    cur_lbl  = test.get('current_variant') or 'A'

    log.info(f'Тест #{test_id} «{test["product_name"][:40]}» SKU={sku} стратегия={test.get("strategy")}')

    # 1. Получаем варианты
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute('SELECT * FROM test_variants WHERE test_id=%s ORDER BY label', (test_id,))
        variants = [dict(r) for r in cur.fetchall()]

    if len(variants) < 2:
        log.warning(f'  Пропускаем: меньше 2 вариантов')
        return

    # 2. Обновляем статистику из Озона (с паузой чтобы не превысить rate limit)
    time.sleep(1)
    update_variant_stats(conn, dict(test), variants, key)

    # Перечитываем варианты с обновлёнными данными
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute('SELECT * FROM test_variants WHERE test_id=%s ORDER BY label', (test_id,))
        variants = [dict(r) for r in cur.fetchall()]

    # 3. Проверяем условие завершения (слабейший набрал 10 000 показов)
    weak = weakest_variant(variants)
    if (weak.get('views') or 0) >= ROTATION_THRESHOLD_VIEWS:
        # Определяем победителя по CTR
        winner = max(variants, key=lambda v: v.get('ctr') or 0.0)
        log.info(f'  ЗАВЕРШАЕМ тест: победитель {winner["label"]} CTR={winner.get("ctr")}%')
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE tests SET status='completed', winner=%s WHERE id=%s",
                (winner['label'], test_id)
            )
        conn.commit()
        # Ставим фото победителя
        _apply_photo(test, key, winner, variants)
        return

    # 4. Находим текущий вариант
    cur_variant = next((v for v in variants if v['label'] == cur_lbl), variants[0])

    # 4.5. Всегда обновляем статистику текущего варианта
    time.sleep(1)
    _collect_variant_stats(conn, test, key, cur_variant, variants)

    # 5. Проверяем нужна ли ротация
    if not should_rotate(dict(test), cur_variant, strategy):
        log.info(f'  Ротация не нужна (текущий: {cur_lbl})')
        return

    # 6. Ротируем — переходим к следующему варианту
    nxt = next_variant(variants, cur_lbl)
    if not nxt or nxt['label'] == cur_lbl:
        log.info(f'  Некуда ротировать')
        return

    log.info(f'  Ротация: {cur_lbl} → {nxt["label"]}')
    success = _apply_photo(test, key, nxt, variants)

    if success:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE tests
                SET current_variant=%s,
                    last_rotated_at=NOW(),
                    rotation_count=COALESCE(rotation_count,0)+1
                WHERE id=%s
            """, (nxt['label'], test_id))
            cur.execute("""
                UPDATE test_variants
                SET views_at_rotation=views
                WHERE id=%s
            """, (nxt['id'],))
        conn.commit()
        log.info(f'  Ротация применена: {cur_lbl} → {nxt["label"]}')
        # Собираем статистику деактивируемого варианта
        _collect_variant_stats(conn, test, key, cur_variant, variants)
        # Записываем время активации нового варианта
        try:
            import database as db_local
            db_local.activate_variant(test_id, nxt['label'])
        except Exception as e:
            log.warning(f'  activate_variant error: {e}')


def _apply_photo(test, key, variant, all_variants):
    """Применяет фото варианта к товару на Озоне."""
    photo_url = variant.get('photo_url', '')

    # Локальные фото (/uploads/...) нельзя отправить в Озон — нужен публичный URL
    if photo_url.startswith('/uploads/'):
        log.warning(f'  Фото локальное — невозможно применить без CDN: {photo_url[:60]}')
        return False

    # Получаем информацию о товаре (нужен product_id)
    product = get_product_info(key, test['sku'])
    if not product:
        log.warning(f'  Не удалось получить информацию о товаре {test["sku"]}')
        return False

    product_id = product.get('id') or product.get('product_id')
    if not product_id:
        log.warning(f'  Не удалось получить product_id для {test["sku"]}')
        return False

    # Оригинальные фото товара с Озона (сохраняем их порядок)
    ozon_images = []
    imgs = product.get('images', [])
    if isinstance(imgs, list):
        for img in imgs:
            if isinstance(img, str) and img.startswith('http'):
                ozon_images.append(img)

    # URL всех тестовых вариантов (для добавления в конец)
    variant_urls = []
    for v in all_variants:
        url = v.get('photo_url', '')
        if url.startswith('http') and url not in variant_urls:
            variant_urls.append(url)

    # Строим итоговый список:
    # 1. Тестовое фото — главное (первое место)
    # 2. Оригинальные фото Озона — в своём порядке (продающая последовательность)
    # 3. Остальные тестовые варианты — в конце (не мешают)
    final_images = [photo_url]
    for img in ozon_images:
        if img != photo_url and img not in final_images:
            final_images.append(img)
    for url in variant_urls:
        if url != photo_url and url not in final_images:
            final_images.append(url)

    log.info(f'  Порядок фото: тест[1] + озон[{len(ozon_images)}] + варианты[{len(variant_urls)}]')
    return set_main_photo(key, test['sku'], product_id, photo_url, final_images[1:])


# ── Точка входа ───────────────────────────────────────────────────────────────

def run():
    if not DATABASE_URL:
        log.error('DATABASE_URL не задан — выходим')
        sys.exit(1)

    log.info('=== Запуск ротации ===')

    # Инициализируем колонки
    try:
        init_rotation_columns()
    except Exception as e:
        log.error(f'init_rotation_columns: {e}')

    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Все активные тесты с API ключами
            cur.execute("""
                SELECT t.*, k.client_id, k.api_key
                FROM tests t
                JOIN api_keys k ON k.user_id = t.user_id AND k.active = TRUE
                WHERE t.status = 'running'
                ORDER BY t.id
            """)
            tests = cur.fetchall()

        log.info(f'Активных тестов: {len(tests)}')

        for test in tests:
            try:
                key = {'client_id': test['client_id'], 'api_key': test['api_key']}
                process_test(conn, dict(test), key)
            except Exception as e:
                log.error(f'Ошибка теста #{test["id"]}: {e}')
            time.sleep(0.5)   # пауза между тестами

    finally:
        conn.close()

    log.info('=== Ротация завершена ===')


if __name__ == '__main__':
    run()
