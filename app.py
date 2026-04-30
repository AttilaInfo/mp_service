from flask import Flask, render_template_string
import json, os

app = Flask(__name__)

HTML = '''<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>A/B Testing — Озон</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family: -apple-system, sans-serif; background:#f0f2f5; color:#1a1a2e; }
  .header { background:linear-gradient(135deg,#667eea,#764ba2); color:white; padding:2rem; text-align:center; }
  .header h1 { font-size:2rem; margin-bottom:.5rem; }
  .header p { opacity:.9; }
  .container { max-width:1200px; margin:2rem auto; padding:0 1rem; }
  .cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:1.5rem; margin-bottom:2rem; }
  .card { background:white; border-radius:12px; padding:1.5rem; box-shadow:0 2px 8px rgba(0,0,0,.08); border-left:4px solid #667eea; }
  .card .icon { font-size:2rem; margin-bottom:.5rem; }
  .card .num { font-size:2rem; font-weight:700; color:#667eea; }
  .card .label { color:#666; font-size:.9rem; margin-top:.25rem; }
  .section { background:white; border-radius:12px; padding:1.5rem; box-shadow:0 2px 8px rgba(0,0,0,.08); margin-bottom:1.5rem; }
  .section h2 { margin-bottom:1rem; font-size:1.2rem; }
  table { width:100%; border-collapse:collapse; }
  th { background:#f8f9fa; padding:.75rem 1rem; text-align:left; font-size:.85rem; color:#666; }
  td { padding:.75rem 1rem; border-top:1px solid #f0f0f0; }
  .badge { padding:.25rem .75rem; border-radius:20px; font-size:.8rem; font-weight:600; }
  .badge-green { background:#d4edda; color:#155724; }
  .badge-blue  { background:#cce5ff; color:#004085; }
  .badge-gold  { background:#fff3cd; color:#856404; }
  .bar-wrap { background:#f0f0f0; border-radius:4px; height:8px; width:100%; }
  .bar { height:8px; border-radius:4px; background:linear-gradient(90deg,#667eea,#764ba2); }
  .ab { display:flex; gap:1rem; }
  .ab-box { flex:1; background:#f8f9fa; border-radius:8px; padding:1rem; text-align:center; }
  .ab-box .letter { font-size:2rem; font-weight:700; }
  .ab-box.winner { background:linear-gradient(135deg,#d4edda,#c3e6cb); }
  .a-letter { color:#667eea; }
  .b-letter { color:#764ba2; }
  .tip { background:linear-gradient(135deg,#e8f4fd,#dbeafe); border-left:4px solid #3b82f6; padding:1rem 1.25rem; border-radius:8px; color:#1e40af; }
  @media(max-width:600px){ .ab{flex-direction:column} }
</style>
</head>
<body>

<div class="header">
  <h1>📊 A/B Testing Pro</h1>
  <p>Оптимизируйте фотографии товаров на Озоне</p>
</div>

<div class="container">

  <div class="cards">
    <div class="card">
      <div class="icon">🧪</div>
      <div class="num">3</div>
      <div class="label">Активных теста</div>
    </div>
    <div class="card">
      <div class="icon">👁️</div>
      <div class="num">12,480</div>
      <div class="label">Просмотров за неделю</div>
    </div>
    <div class="card">
      <div class="icon">🛒</div>
      <div class="num">+34%</div>
      <div class="label">Рост конверсии</div>
    </div>
    <div class="card">
      <div class="icon">🏆</div>
      <div class="num">5</div>
      <div class="label">Завершённых тестов</div>
    </div>
  </div>

  <div class="section">
    <h2>🧪 Активные тесты</h2>
    <table>
      <tr>
        <th>Товар (SKU)</th>
        <th>Вариант A</th>
        <th>Вариант B</th>
        <th>CTR A vs B</th>
        <th>Статус</th>
      </tr>
      <tr>
        <td><strong>Рубашка M</strong><br><small>SKU-001</small></td>
        <td>8.2%</td>
        <td><strong>11.5%</strong></td>
        <td>
          <div class="bar-wrap"><div class="bar" style="width:70%"></div></div>
          <small>B лучше на 40%</small>
        </td>
        <td><span class="badge badge-green">✅ Идёт</span></td>
      </tr>
      <tr>
        <td><strong>Кроссовки Nike</strong><br><small>SKU-002</small></td>
        <td><strong>9.1%</strong></td>
        <td>7.8%</td>
        <td>
          <div class="bar-wrap"><div class="bar" style="width:45%"></div></div>
          <small>A лучше на 16%</small>
        </td>
        <td><span class="badge badge-green">✅ Идёт</span></td>
      </tr>
      <tr>
        <td><strong>Наушники BT</strong><br><small>SKU-003</small></td>
        <td>5.4%</td>
        <td>5.6%</td>
        <td>
          <div class="bar-wrap"><div class="bar" style="width:50%"></div></div>
          <small>Почти одинаково</small>
        </td>
        <td><span class="badge badge-blue">⏳ Копим данные</span></td>
      </tr>
    </table>
  </div>

  <div class="section">
    <h2>🏆 Последний завершённый тест — SKU-004 Куртка зимняя</h2>
    <div class="ab">
      <div class="ab-box">
        <div class="letter a-letter">A</div>
        <div style="font-size:1.5rem;font-weight:700;margin:.5rem 0">6.3%</div>
        <div style="color:#666;font-size:.9rem">CTR</div>
        <div style="margin-top:.5rem;color:#666;font-size:.85rem">1240 просмотров<br>78 кликов</div>
      </div>
      <div class="ab-box winner">
        <div class="letter b-letter">B 🏆</div>
        <div style="font-size:1.5rem;font-weight:700;margin:.5rem 0">9.8%</div>
        <div style="color:#666;font-size:.9rem">CTR</div>
        <div style="margin-top:.5rem;color:#666;font-size:.85rem">1180 просмотров<br>116 кликов</div>
      </div>
    </div>
    <p style="margin-top:1rem;color:#155724;font-weight:600">
      ✅ Победитель: Вариант B — CTR выше на 55%! Применено к товару.
    </p>
  </div>

  <div class="tip">
    💡 <strong>Совет:</strong> Для достоверных результатов нужно минимум 100 просмотров на каждый вариант и не менее 7 дней тестирования.
  </div>

</div>
</body>
</html>'''

@app.route('/')
def index():
    return render_template_string(HTML)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
