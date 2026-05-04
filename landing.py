from flask import Blueprint, redirect
from templates import LANDING_CSS
from auth import me

landing_bp = Blueprint('landing', __name__)


@landing_bp.route('/')
def landing():
    if me():
        return redirect('/dashboard')

    html = (
        '<!DOCTYPE html><html lang="ru"><head>'
        '<meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>A/B Testing Pro &mdash; Больше продаж на Озоне</title>'
        '<style>' + LANDING_CSS + '</style>'
        '</head><body>'

        # Навигация
        '<nav class="lnav">'
        '<div class="lnav-logo">A/B Testing Pro</div>'
        '<div class="lnav-links">'
        '<a href="#how">Как работает</a>'
        '<a href="#features">Возможности</a>'
        '<a href="#pricing">Тарифы</a>'
        '<a href="/login">Войти</a>'
        '<a href="/register" class="lnav-cta">Начать бесплатно</a>'
        '</div></nav>'

        # Hero
        '<section class="hero">'
        '<div class="hero-bg"><div class="blob b1"></div><div class="blob b2"></div><div class="blob b3"></div></div>'
        '<div style="position:relative;z-index:1">'
        '<div class="hero-badge">&#128200; Увеличьте продажи без вложений в рекламу</div>'
        '<h1>Ваши конкуренты уже<br>тестируют. <span>А вы?</span></h1>'
        '<p class="hero-sub">Автоматически проверяйте какие фотографии товаров продают лучше. До 10 вариантов одновременно &mdash; без Excel, без ручной работы.</p>'
        '<div class="hero-btns">'
        '<a href="/register" class="btn-hero btn-main">Попробовать бесплатно 30 дней &rarr;</a>'
        '<a href="#how" class="btn-hero btn-ghost">Как это работает?</a>'
        '</div>'
        '<div class="hero-stat">'
        '<div class="stat-item"><div class="stat-n">+34%</div><div class="stat-l">средний рост конверсии</div></div>'
        '<div class="stat-item"><div class="stat-n">до 10</div><div class="stat-l">вариантов фото в тесте</div></div>'
        '<div class="stat-item"><div class="stat-n">30 дней</div><div class="stat-l">бесплатный период</div></div>'
        '</div></div></section>'

        # Проблема
        '<section class="problem">'
        '<div class="section-tag">Знакомо?</div>'
        '<h2 class="section-h">Почему 90% продавцов<br>теряют деньги каждый день</h2>'
        '<p class="section-sub">Большинство продавцов выбирают фото «на глазок» и никогда не узнают, сколько продаж они потеряли из-за одной неудачной картинки.</p>'
        '<div class="problem-cards">'
        '<div class="prob-card"><div class="prob-icon">&#128064;</div><h3>Выбирают фото интуитивно</h3><p>«Мне кажется это красиво» — не аргумент. Покупатели думают иначе.</p></div>'
        '<div class="prob-card"><div class="prob-icon">&#128202;</div><h3>Нет данных для решений</h3><p>Без теста невозможно знать, какое фото реально приносит больше кликов и продаж.</p></div>'
        '<div class="prob-card"><div class="prob-icon">&#9200;</div><h3>Нет времени делать вручную</h3><p>Менять фото, записывать статистику, считать конверсии — часы работы каждую неделю.</p></div>'
        '</div></section>'

        # Как работает
        '<section class="how" id="how"><div class="how-inner">'
        '<div class="how-title"><div class="section-tag">Просто и быстро</div><h2 class="section-h">Три шага до роста продаж</h2></div>'
        '<div class="steps">'
        '<div class="step"><div class="step-num">01</div><h3>Подключите магазин</h3><p>Введите API-ключ Озона. Сервис автоматически получит доступ к вашим товарам. Занимает 2 минуты.</p></div>'
        '<div class="step"><div class="step-num">02</div><h3>Загрузите варианты фото</h3><p>От 2 до 10 вариантов первого фото. Сервис начнёт показывать их покупателям по очереди.</p></div>'
        '<div class="step"><div class="step-num">03</div><h3>Получайте результаты</h3><p>Сервис определит победителя по CTR и конверсии и автоматически применит лучшее фото.</p></div>'
        '</div></div></section>'

        # Возможности
        '<section class="features" id="features">'
        '<div class="feat-title"><div class="section-tag">Возможности</div><h2 class="section-h">Всё что нужно для роста</h2></div>'
        '<div class="feat-grid">'
        '<div class="feat-card"><div class="feat-ic">&#127922;</div><h3>До 10 вариантов в одном тесте</h3><p>Мультивариантное тестирование. Тестируйте разные ракурсы, фоны, инфографику.</p></div>'
        '<div class="feat-card"><div class="feat-ic">&#128200;</div><h3>Автоматическая ротация</h3><p>Сервис сам меняет фото и выбирает лучший вариант — без ручной работы каждый день.</p></div>'
        '<div class="feat-card"><div class="feat-ic">&#128269;</div><h3>Реальная аналитика</h3><p>Просмотры, клики, CTR, продажи, конверсия по каждому варианту в одном месте.</p></div>'
        '<div class="feat-card"><div class="feat-ic">&#128737;</div><h3>Безопасно и надёжно</h3><p>Ключи хранятся в зашифрованном виде. Работаем только через официальный API Озона.</p></div>'
        '<div class="feat-card"><div class="feat-ic">&#9889;</div><h3>Быстрый старт</h3><p>Первый тест за 5 минут. Никаких сложных настроек — подключили и работаете.</p></div>'
        '<div class="feat-card"><div class="feat-ic">&#128276;</div><h3>Уведомления о результатах</h3><p>Получайте сообщения когда тест завершён и найден победитель.</p></div>'
        '</div></section>'

        # Тариф
        '<section class="pricing" id="pricing"><div class="pricing-inner">'
        '<div class="section-tag" style="display:block;text-align:center">Прозрачные условия</div>'
        '<h2 class="section-h">Начните бесплатно</h2>'
        '<div class="price-card">'
        '<div class="price-badge">&#127381; Специальное предложение</div>'
        '<div class="price-tag">500 &#8381; <span>/ 1 тест</span></div>'
        '<p class="price-sub">Платите только за результат. Без абонентской платы.</p>'
        '<ul class="price-features">'
        '<li><span class="check-ic">&#10003;</span> 1 тест = 500 токенов = 500&#8381;</li>'
        '<li><span class="check-ic">&#10003;</span> До 10 вариантов фото в одном тесте</li>'
        '<li><span class="check-ic">&#10003;</span> Автоматическая ротация и аналитика</li>'
        '<li><span class="check-ic">&#10003;</span> Токены зачисляются мгновенно после оплаты</li>'
        '<li><span class="check-ic">&#10003;</span> Поддержка 7 дней в неделю</li>'
        '</ul>'
        '<a href="/register" class="btn-hero btn-main" style="width:100%;justify-content:center;display:flex">Начать бесплатно &rarr;</a>'
        '</div></div></section>'

        # CTA
        '<section class="cta-section">'
        '<div class="cta-bg"></div>'
        '<div style="position:relative;z-index:1">'
        '<h2>Хватит терять деньги<br>на неправильных фото</h2>'
        '<p style="color:#888;font-size:1.1rem;margin:1.5rem auto 2.5rem;max-width:500px">'
        'Пока вы читаете это — ваши конкуренты уже тестируют. Начните прямо сейчас, это бесплатно.</p>'
        '<a href="/register" class="btn-hero btn-main">Попробовать бесплатно 30 дней &rarr;</a>'
        '</div></section>'

        # Футер
        '<footer class="footer">'
        '&#169; 2025 A/B Testing Pro &nbsp;&middot;&nbsp;'
        'ИП Клюева Наталья Анатольевна &nbsp;&middot;&nbsp;'
        '<a href="/login" style="color:#ff4d6d">Войти</a> &nbsp;&middot;&nbsp;'
        '<a href="/register" style="color:#ff4d6d">Регистрация</a> &nbsp;&middot;&nbsp;'
        '<a href="/terms" style="color:#ff4d6d">Оферта</a> &nbsp;&middot;&nbsp;'
        '<a href="/contacts" style="color:#ff4d6d">Контакты</a>'
        '</footer>'

        '</body></html>'
    )
    return html


# ── Оферта ────────────────────────────────────────────────────────────────

@landing_bp.route('/terms')
def terms():
    html = (
        '<!DOCTYPE html><html lang="ru"><head>'
        '<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Публичная оферта — A/B Testing Pro</title>'
        '<style>'
        'body{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;'
        'background:#f8f9fa;color:#1a1a2e;line-height:1.7}'
        '.wrap{max-width:800px;margin:0 auto;padding:2rem 1rem}'
        'h1{font-size:1.8rem;font-weight:700;margin-bottom:.5rem;color:#1a1a2e}'
        'h2{font-size:1.2rem;font-weight:700;margin:2rem 0 .75rem;color:#333}'
        'p,li{font-size:.95rem;color:#444;margin-bottom:.6rem}'
        'ul{padding-left:1.5rem;margin-bottom:1rem}'
        '.meta{font-size:.85rem;color:#888;margin-bottom:2rem}'
        '.back{display:inline-block;margin-bottom:1.5rem;color:#667eea;'
        'font-size:.9rem;text-decoration:none}'
        '</style></head><body><div class="wrap">'
        '<a href="/" class="back">&#8592; На главную</a>'
        '<h1>Публичная оферта на оказание услуг</h1>'
        '<p class="meta">Дата публикации: 1 мая 2025 г. &nbsp;·&nbsp; Редакция 1.0</p>'

        '<h2>1. Общие положения</h2>'
        '<p>Настоящий документ является публичной офертой индивидуального предпринимателя '
        'Клюевой Натальи Анатольевны (ОГРНИП 322527500044708, ИНН 360402011440) и содержит '
        'все существенные условия договора на оказание услуг сервиса A/B Testing Pro.</p>'
        '<p>Акцептом настоящей оферты является регистрация на сайте и/или оплата услуг. '
        'С момента акцепта договор считается заключённым.</p>'

        '<h2>2. Предмет договора</h2>'
        '<p>Исполнитель предоставляет Заказчику доступ к сервису A/B Testing Pro — '
        'программному обеспечению для автоматического тестирования фотографий товаров '
        'на маркетплейсе Ozon с целью увеличения конверсии.</p>'

        '<h2>3. Стоимость и порядок оплаты</h2>'
        '<ul>'
        '<li>1 токен = 1 рубль</li>'
        '<li>Минимальное пополнение: 500 рублей = 500 токенов</li>'
        '<li>Стоимость одного A/B теста: 500 токенов</li>'
        '<li>Оплата производится в безналичной форме через платёжный сервис ЮКасса</li>'
        '<li>Токены зачисляются на баланс моментально после подтверждения оплаты</li>'
        '<li>Фискальный чек направляется на email Заказчика автоматически</li>'
        '</ul>'

        '<h2>4. Порядок оказания услуг</h2>'
        '<ul>'
        '<li>Доступ к сервису предоставляется после регистрации и пополнения баланса</li>'
        '<li>Токены списываются в момент запуска теста и не возвращаются</li>'
        '<li>Текущие тесты продолжают работу до завершения даже при нулевом балансе</li>'
        '<li>Исполнитель вправе изменить стоимость услуг, уведомив пользователей за 7 дней</li>'
        '</ul>'

        '<h2>5. Возврат средств</h2>'
        '<p>Возврат неиспользованных токенов возможен по письменному запросу на email '
        'attilainfo@yandex.ru в течение 14 дней с момента пополнения при условии, '
        'что токены не были использованы для запуска тестов.</p>'

        '<h2>6. Ответственность сторон</h2>'
        '<p>Исполнитель не несёт ответственности за перебои в работе сервисов Ozon, '
        'за изменения в API Ozon, а также за результаты тестирования. '
        'Сервис предоставляется «как есть» (as is).</p>'

        '<h2>7. Конфиденциальность</h2>'
        '<p>Исполнитель обязуется не передавать данные Заказчика третьим лицам, '
        'за исключением случаев, предусмотренных законодательством РФ. '
        'API-ключи Ozon хранятся в зашифрованном виде.</p>'

        '<h2>8. Реквизиты исполнителя</h2>'
        '<p>ИП Клюева Наталья Анатольевна<br>'
        'ИНН: 360402011440<br>'
        'ОГРНИП: 322527500044708<br>'
        'Email: attilainfo@yandex.ru<br>'
        'Телефон: +7 986 755-48-93</p>'

        '</div></body></html>'
    )
    return html


# ── Контакты ───────────────────────────────────────────────────────────────

@landing_bp.route('/contacts')
def contacts():
    html = (
        '<!DOCTYPE html><html lang="ru"><head>'
        '<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Контакты — A/B Testing Pro</title>'
        '<style>'
        'body{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;'
        'background:#f8f9fa;color:#1a1a2e;line-height:1.7}'
        '.wrap{max-width:700px;margin:0 auto;padding:2rem 1rem}'
        'h1{font-size:1.8rem;font-weight:700;margin-bottom:2rem;color:#1a1a2e}'
        '.card{background:#fff;border-radius:12px;padding:1.5rem;'
        'box-shadow:0 2px 8px rgba(0,0,0,.07);margin-bottom:1rem}'
        '.row{display:flex;gap:1rem;align-items:flex-start;padding:.6rem 0;'
        'border-bottom:1px solid #f0f2f5}'
        '.row:last-child{border-bottom:none}'
        '.ic{font-size:1.3rem;min-width:2rem}'
        '.lbl{font-size:.82rem;color:#888;margin-bottom:.2rem}'
        '.val{font-size:.95rem;font-weight:600;color:#1a1a2e}'
        'a.val{color:#667eea}'
        '.back{display:inline-block;margin-bottom:1.5rem;color:#667eea;'
        'font-size:.9rem;text-decoration:none}'
        '</style></head><body><div class="wrap">'
        '<a href="/" class="back">&#8592; На главную</a>'
        '<h1>&#128222; Контакты и реквизиты</h1>'

        '<div class="card">'
        '<div class="row"><div class="ic">&#128100;</div><div>'
        '<div class="lbl">Организация</div>'
        '<div class="val">ИП Клюева Наталья Анатольевна</div>'
        '</div></div>'

        '<div class="row"><div class="ic">&#128196;</div><div>'
        '<div class="lbl">ИНН</div>'
        '<div class="val">360402011440</div>'
        '</div></div>'

        '<div class="row"><div class="ic">&#128196;</div><div>'
        '<div class="lbl">ОГРНИП</div>'
        '<div class="val">322527500044708</div>'
        '</div></div>'

        '<div class="row"><div class="ic">&#128231;</div><div>'
        '<div class="lbl">Email</div>'
        '<a href="mailto:attilainfo@yandex.ru" class="val">attilainfo@yandex.ru</a>'
        '</div></div>'

        '<div class="row"><div class="ic">&#128222;</div><div>'
        '<div class="lbl">Телефон</div>'
        '<a href="tel:+79867554893" class="val">+7 986 755-48-93</a>'
        '</div></div>'

        '<div class="row"><div class="ic">&#127760;</div><div>'
        '<div class="lbl">Сайт</div>'
        '<a href="https://mpservice-production.up.railway.app" class="val">'
        'mpservice-production.up.railway.app</a>'
        '</div></div>'
        '</div>'

        '<div class="card">'
        '<div class="row"><div class="ic">&#9203;</div><div>'
        '<div class="lbl">Время ответа</div>'
        '<div class="val">В течение 24 часов в рабочие дни</div>'
        '</div></div>'
        '<div class="row"><div class="ic">&#128230;</div><div>'
        '<div class="lbl">Для юридических вопросов и возвратов</div>'
        '<a href="mailto:attilainfo@yandex.ru" class="val">attilainfo@yandex.ru</a>'
        '</div></div>'
        '</div>'

        '<p style="font-size:.82rem;color:#aaa;margin-top:1rem">'
        '<a href="/terms" style="color:#667eea">Публичная оферта</a>'
        ' &nbsp;·&nbsp; &#169; 2025 A/B Testing Pro</p>'
        '</div></body></html>'
    )
    return html
