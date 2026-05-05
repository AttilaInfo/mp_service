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
ROTATION_THRESHOLD_DAYS  = 14       # дней максимум → завершаем тест

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
            cur.execute("ALTER TABLE test_variants ADD COLUMN IF NOT EXISTS perf_baseline_views INTEGER DEFAULT -1")
            cur.execute("ALTER TABLE test_variants ADD COLUMN IF NOT EXISTS perf_baseline_clicks INTEGER DEFAULT -1")
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


# ── Performance API ───────────────────────────────────────────────────────────

def get_perf_token(user_id):
    """Получить access_token Performance API для пользователя."""
    try:
        conn = get_conn()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT * FROM perf_keys WHERE user_id=%s LIMIT 1', (user_id,))
            perf = cur.fetchone()
        conn.close()
        if not perf:
            return None
        r = requests.post(
            'https://api-performance.ozon.ru/api/client/token',
            json={
                'client_id':     perf['client_id'],
                'client_secret': perf['client_secret'],
                'grant_type':    'client_credentials'
            },
            timeout=10
        )
        if r.status_code == 200:
            return r.json().get('access_token')
        log.warning(f'  perf token: {r.status_code} {r.text[:100]}')
    except Exception as e:
        log.error(f'  get_perf_token: {e}')
    return None


def get_perf_totals_now(token, campaign_ids, date_from):
    """Получить суммарную статистику кампаний от date_from до сегодня.
    Используется для дельта-метода: baseline при активации варианта.
    Возвращает dict {views, clicks, tocart} или None.
    """
    date_to = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    total_views  = 0
    total_clicks = 0
    total_tocart = 0
    for campaign_id in campaign_ids:
        stats = get_perf_variant_stats(token, campaign_id, date_from, date_to)
        if stats:
            total_views  += stats['views']
            total_clicks += stats['clicks']
            total_tocart += stats.get('tocart', 0)
    return {'views': total_views, 'clicks': total_clicks, 'tocart': total_tocart}


def get_perf_variant_stats(token, campaign_id, date_from, date_to):
    """Получить статистику кампании за период из Performance API.
    Возвращает dict {views, clicks} или None.
    Flow: POST statistics → UUID → GET statistics/{UUID} → link → GET CSV
    """
    try:
        import io, csv as csv_mod, time as time_mod
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

        # 1. Создаём задание
        r = requests.post(
            'https://api-performance.ozon.ru/api/client/statistics',
            headers=headers,
            json={
                'campaigns': [str(campaign_id)],
                'dateFrom':  date_from,
                'dateTo':    date_to,
                'groupBy':   'HOUR'
            },
            timeout=15
        )
        log.info(f'  perf stats status={r.status_code} camp={campaign_id} {date_from}→{date_to}')
        if r.status_code != 200:
            log.warning(f'  perf stats error: {r.status_code} {r.text[:200]}')
            return None

        uuid = r.json().get('UUID')
        if not uuid:
            return None

        # 2. Ждём готовности (state=OK)
        link = None
        for _ in range(10):
            time_mod.sleep(3)
            r2 = requests.get(
                f'https://api-performance.ozon.ru/api/client/statistics/{uuid}',
                headers=headers, timeout=15
            )
            data = r2.json()
            if data.get('state') == 'OK':
                link = data.get('link')
                break

        if not link:
            log.warning(f'  perf: задание не готово за 30 сек')
            return None

        # 3. Скачиваем CSV
        r3 = requests.get(
            f'https://api-performance.ozon.ru{link}',
            headers=headers, timeout=15
        )
        if r3.status_code != 200:
            log.warning(f'  perf CSV error: {r3.status_code}')
            return None

        # 4. Парсим CSV — строка "Всего" содержит суммарные данные
        # Формат: День;sku;Название;Цена;Показы;Клики;CTR...
        views = 0
        clicks = 0
        text = r3.text
        reader = csv_mod.reader(io.StringIO(text), delimiter=';')
        headers_row = None
        for row in reader:
            if not row:
                continue
            if headers_row is None:
                headers_row = [h.strip() for h in row]
                continue
            if not row[0] or row[0].startswith('Всего') or row[0].startswith('итого'):
                # Строка итогов — берём показы и клики
                try:
                    idx_views  = next((i for i, h in enumerate(headers_row) if 'показ' in h.lower()), 3)
                    idx_clicks = next((i for i, h in enumerate(headers_row) if 'клик' in h.lower()), 4)
                    idx_tocart = next((i for i, h in enumerate(headers_row) if 'корзин' in h.lower()), 6)
                    # HOUR groupBy: Всего row may have 2 empty leading cells
                    # Auto-detect offset by finding first numeric value after index 0
                    offset = 0
                    for ci in range(1, min(5, len(row))):
                        if row[ci] and row[ci].strip() not in ('', ' '):
                            try:
                                float(row[ci].replace(',', '.'))
                                offset = ci - idx_views
                                if offset < 0:
                                    offset = 0
                                break
                            except ValueError:
                                continue
                    def _safe_int(r, idx):
                        try:
                            v = r[idx + offset] if idx + offset < len(r) else ''
                            return int(float(v.replace(',', '.').replace(' ', '') or 0))
                        except Exception:
                            return 0
                    views  = _safe_int(row, idx_views)
                    clicks = _safe_int(row, idx_clicks)
                    tocart = _safe_int(row, idx_tocart)
                except Exception as pe:
                    log.warning(f'  perf CSV parse итого: {pe}')
                break

        log.info(f'  [PERF API] показы={views} клики={clicks} корзина={tocart}')
        return {'views': views, 'clicks': clicks, 'tocart': tocart}

    except Exception as e:
        log.error(f'  get_perf_variant_stats: {e}')
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



def _collect_variant_stats(conn, test, key, variant, all_variants, product_id=None, accumulate=False):
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

    log.info(f'  Сбор статистики {variant["label"]}: {date_from} → {date_to} SKU={test["sku"]} activated_at={variant.get("activated_at")} created_at={test.get("created_at")}')

    # Точный CTR через Performance API — дельта-метод
    campaign_ids_str = test.get('campaign_ids', '') or ''
    campaign_ids = [c.strip() for c in campaign_ids_str.split(',') if c.strip()]
    if campaign_ids:
        token = get_perf_token(test.get('user_id'))
        if token:
            totals_now = get_perf_totals_now(token, campaign_ids, date_from)
            if totals_now:
                baseline_views  = variant.get('perf_baseline_views')
                baseline_clicks = variant.get('perf_baseline_clicks')

                # Если baseline не инициализирован (-1 или None) — инициализируем сейчас
                if baseline_views is None or baseline_views == -1:
                    with conn.cursor() as cur:
                        cur.execute(
                            'UPDATE test_variants SET perf_baseline_views=%s, perf_baseline_clicks=%s WHERE id=%s',
                            (totals_now['views'], totals_now['clicks'], variant['id'])
                        )
                    conn.commit()
                    log.info(f'  [PERF INIT] {variant["label"]}: baseline установлен: показы={totals_now["views"]} клики={totals_now["clicks"]}')
                    return True  # Первый прогон — инициализация, статистика 0

                # Дельта = текущий итог минус значение на момент активации варианта
                delta_views  = max(0, totals_now['views']  - baseline_views)
                delta_clicks = max(0, totals_now['clicks'] - baseline_clicks)
                delta_tocart = max(0, totals_now.get('tocart', 0) - (variant.get('perf_baseline_tocart') or 0))
                # CTR = расчётный: суммарные клики / суммарные показы
                if accumulate:
                    total_views  = (variant.get('views')  or 0) + delta_views
                    total_clicks = (variant.get('clicks') or 0) + delta_clicks
                else:
                    total_views  = delta_views
                    total_clicks = delta_clicks
                ctr = round(total_clicks / total_views * 100, 2) if total_views > 0 else 0.0
                sql_acc = (
                    "UPDATE test_variants SET "
                    "views=COALESCE(views,0)+%s, clicks=COALESCE(clicks,0)+%s, "
                    "tocart=COALESCE(tocart,0)+%s, ctr=%s WHERE id=%s"
                )
                sql_set = "UPDATE test_variants SET views=%s, clicks=%s, tocart=%s, ctr=%s WHERE id=%s"
                with conn.cursor() as cur:
                    if accumulate:
                        cur.execute(sql_acc, (delta_views, delta_clicks, delta_tocart, ctr, variant['id']))
                    else:
                        cur.execute(sql_set, (delta_views, delta_clicks, delta_tocart, ctr, variant['id']))
                conn.commit()
                log.info(f'  [PERF DELTA{"ACC" if accumulate else ""}] {variant["label"]}: показы={delta_views} клики={delta_clicks} корзина={delta_tocart} CTR={ctr}%')
                return

    # Fallback: Seller API
    try:
        r = requests.post(
            f'{OZON_API_URL}/v1/analytics/data',
            headers=ozon_headers(key),
            json={
                'date_from': date_from,
                'date_to':   date_to,
                'metrics':   ['hits_view_pdp', 'hits_tocart', 'revenue', 'ordered_units'],
                'dimension': ['day'],
                'limit':     1000,
            },
            timeout=20
        )
        log.info(f'  analytics status={r.status_code} body={r.text[:400]}')
        if r.status_code == 200:
            rows = r.json().get('result', {}).get('data', [])
            if rows:
                # Суммируем по всем дням (данные по магазину за период)
                views  = sum(int(row.get('metrics',[0])[0])   for row in rows if row.get('metrics'))
                tocart = sum(int(row.get('metrics',[0,0])[1]) for row in rows if len(row.get('metrics',[]))>1)
                clicks = tocart
                # Делим на количество вариантов — приближение на период активности
                n = max(1, len([v for v in all_variants if not v.get('paused')]))
                views  = views  // n
                tocart = tocart // n
                clicks = clicks // n
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

    # 3. Проверяем условие автозавершения
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # 3а. Проверка по времени — 14 дней
    created_at = test.get('created_at')
    if isinstance(created_at, str):
        try:
            created_at = datetime.fromisoformat(created_at.replace('Z', ''))
        except Exception:
            created_at = None
    if created_at:
        days_elapsed = (now - created_at.replace(tzinfo=None)).days
        if days_elapsed >= ROTATION_THRESHOLD_DAYS:
            winner = max(variants, key=lambda v: v.get('ctr') or 0.0)
            log.info(f'  ЗАВЕРШАЕМ тест: прошло {days_elapsed} дней (лимит {ROTATION_THRESHOLD_DAYS}), победитель {winner["label"]} CTR={winner.get("ctr")}%')
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE tests SET status='completed', winner=%s WHERE id=%s",
                    (winner['label'], test_id)
                )
            conn.commit()
            _apply_photo(test, key, winner, variants)
            return

    # 3б. Проверка по показам — слабейший набрал 10 000
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
    _prod_info = get_product_info(key, test['sku'])
    _prod_id   = (_prod_info.get('id') or _prod_info.get('product_id')) if _prod_info else None
    _just_initialized = _collect_variant_stats(conn, test, key, cur_variant, variants, product_id=_prod_id)

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
        # Собираем финальную статистику деактивируемого варианта (накопительно)
        # Если только что произошёл INIT — пропускаем (delta = 0, нечего накапливать)
        if not _just_initialized:
            _collect_variant_stats(conn, test, key, cur_variant, variants, product_id=_prod_id, accumulate=True)
        # Записываем время активации нового варианта
        try:
            import database as db_local
            db_local.activate_variant(test_id, nxt['label'])
        except Exception as e:
            log.warning(f'  activate_variant error: {e}')
        # Записываем baseline для нового варианта (дельта-метод)
        campaign_ids_str = test.get('campaign_ids', '') or ''
        campaign_ids_list = [c.strip() for c in campaign_ids_str.split(',') if c.strip()]
        if campaign_ids_list:
            try:
                perf_token = get_perf_token(test.get('user_id'))
                if perf_token:
                    test_date = (test.get('created_at') or datetime.now()).strftime('%Y-%m-%d') if not isinstance(test.get('created_at'), str) else test['created_at'][:10]
                    baseline = get_perf_totals_now(perf_token, campaign_ids_list, test_date)
                    if baseline:
                        with conn.cursor() as cur:
                            cur.execute(
                                'UPDATE test_variants SET perf_baseline_views=%s, perf_baseline_clicks=%s WHERE id=%s',
                                (baseline['views'], baseline['clicks'], nxt['id'])
                            )
                        conn.commit()
                        log.info(f'  Baseline для {nxt["label"]}: показы={baseline["views"]} клики={baseline["clicks"]}')
            except Exception as e:
                log.warning(f'  baseline error: {e}')


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
