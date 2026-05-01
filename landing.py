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
        '<div class="price-tag">0 &#8381; <span>/ первые 30 дней</span></div>'
        '<p class="price-sub">Полный доступ ко всем функциям. Без ввода карты.</p>'
        '<ul class="price-features">'
        '<li><span class="check-ic">&#10003;</span> Неограниченное количество товаров</li>'
        '<li><span class="check-ic">&#10003;</span> До 10 вариантов фото в одном тесте</li>'
        '<li><span class="check-ic">&#10003;</span> Автоматическая ротация и аналитика</li>'
        '<li><span class="check-ic">&#10003;</span> Подключение нескольких магазинов</li>'
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
        '&#169; 2024 A/B Testing Pro &nbsp;&middot;&nbsp;'
        '<a href="/login" style="color:#ff4d6d"> Войти</a> &nbsp;&middot;&nbsp;'
        '<a href="/register" style="color:#ff4d6d">Регистрация</a>'
        '</footer>'

        '</body></html>'
    )
    return html
