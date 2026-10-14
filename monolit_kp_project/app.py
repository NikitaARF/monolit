import os, json
from flask import Flask, request, render_template_string, send_file, flash, redirect, url_for
from dotenv import load_dotenv
from engine import Catalog, calculate, parse_with_llm
from documents import render_docx
from pathlib import Path
import tempfile

ROOT=Path(__file__).resolve().parent
load_dotenv(ROOT/".env")
app=Flask(__name__); app.secret_key=os.getenv("FLASK_SECRET_KEY","local-development-only")
HTML=r"""
<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>КП по письму клиента — Монолит Р</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f2f5f8;color:#1d2939;font:15px Arial,sans-serif}
header{background:#173e63;color:white;padding:22px max(20px,calc((100% - 1100px)/2))}header h1{margin:0 0 6px;font-size:25px}header p{margin:0;color:#d6e4f0}
main{max-width:1100px;margin:24px auto;padding:0 18px}.panel{background:white;border:1px solid #dce3eb;border-radius:12px;padding:20px;margin-bottom:18px;box-shadow:0 2px 8px #172b4d0a}
textarea{width:100%;min-height:230px;border:1px solid #b8c4d2;border-radius:8px;padding:12px;font:14px/1.5 Consolas,monospace}
button,.download{display:inline-block;background:#1d5d91;color:white;border:0;border-radius:7px;padding:11px 16px;font-weight:bold;cursor:pointer;text-decoration:none;margin-top:10px}
table{width:100%;border-collapse:collapse;margin:12px 0;font-size:13px}th,td{border:1px solid #d9e0e8;padding:8px;text-align:left}th{background:#edf3f8}td.num{text-align:right;white-space:nowrap}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}.stat{padding:13px;background:#f4f7fa;border-radius:8px}.stat small{display:block;color:#667085;margin-bottom:6px}.stat b{font-size:20px}.warn{background:#fff5e8;border:1px solid #ffd9a8;padding:12px;border-radius:8px}.muted{color:#667085;font-size:13px}.error{color:#9d2222}.pill{background:#e6f5eb;color:#17643b;border-radius:20px;padding:4px 9px;font-size:12px}
</style></head><body><header><h1>«Монолит Р» — КП по письму клиента</h1><p>ИИ разбирает письмо, расчёты выполняются детерминированным кодом по прайсу и регламенту.</p></header><main>
<section class="panel"><h2>1. Вставьте письмо клиента</h2>
<form method="post"><textarea name="letter" placeholder="Вставьте полный текст письма, включая запрос и контактные данные..." required>{{ letter or "" }}</textarea><br><button type="submit">Сформировать черновик КП</button></form>
<p class="muted">Для разбора письма нужен API-ключ в .env. Если ключ не настроен, можно использовать режим расчёта из готового JSON-разбора командой batch.py --no-llm.</p></section>
{% if error %}<section class="panel warn error"><b>Не удалось обработать письмо</b><p>{{ error }}</p></section>{% endif %}
{% if result %}<section class="panel"><h2>2. Результат расчёта <span class="pill">Черновик</span></h2>
<div class="grid">
<div class="stat"><small>Сумма товаров</small><b>{{ money(result.goods_total) }} ₽</b></div>
<div class="stat"><small>Скидка {{ result.discount_percent }}%</small><b>{{ money(result.discount_amount) }} ₽</b></div>
<div class="stat"><small>Доставка</small><b>{{ money(result.delivery.cost) }} ₽</b></div>
<div class="stat"><small>Итого к оплате</small><b>{{ money(result.total) }} ₽</b></div></div>
<p><b>Клиент:</b> {{ result.client.name or "не определён" }} · {{ result.client.phone or "телефон не указан" }}</p>
<p><b>Получение:</b> {{ result.delivery_method }}{% if result.settlement %}, {{ result.settlement }}{% endif %} · <b>Филиал:</b> {{ result.branch or "не определён" }}</p>
<h3>Позиции</h3><table><tr><th>Артикул</th><th>Наименование</th><th>Кол-во</th><th>Цена</th><th>Сумма</th></tr>
{% for i in result["items"] %}<tr><td>{{ i.sku }}</td><td>{{ i.name }}{% if i.promo %} <span class="pill">акция</span>{% endif %}{% if i.on_order_days %} (под заказ {{ i.on_order_days }} дн.){% endif %}</td><td>{{ i.qty }} {{ i.unit }}</td><td class="num">{{ money(i.price) }}</td><td class="num">{{ money(i.amount) }}</td></tr>{% endfor %}</table>
{% if result.clarify %}<div class="warn"><h3>Требует уточнения — в сумму не включено</h3>{% for c in result.clarify %}<p><b>{{ c.request }}</b> — {{ c.reason }}</p>{% endfor %}</div>{% endif %}
{% if result.notes %}<h3>Примечания менеджеру</h3><ul>{% for n in result.notes %}<li>{{ n }}</li>{% endfor %}</ul>{% endif %}
<p><b>Вес заказа:</b> {{ money(result.weight_kg) }} кг · <b>НДС 22% в итоге:</b> {{ money(result.vat) }} ₽</p>
<form method="post" action="/download"><input type="hidden" name="payload" value="{{ payload|e }}"><button type="submit">Скачать КП в DOCX</button></form>
</section>{% endif %}
</main></body></html>
"""
def money(v): return f"{float(v):,.2f}".replace(","," ").replace(".",",")
@app.route("/",methods=["GET","POST"])
def index():
    letter=request.form.get("letter",""); result=None; error=None; payload=""
    if request.method=="POST":
      try:
        parsed=parse_with_llm(letter)
        parsed["letter_id"]="00"
        result=calculate(parsed,Catalog())
        payload=json.dumps(result,ensure_ascii=False)
      except Exception as e: error=str(e)
    return render_template_string(HTML,letter=letter,result=result,error=error,payload=payload,money=money)
@app.route("/download",methods=["POST"])
def download():
    try:
      data=json.loads(request.form["payload"])
      with tempfile.NamedTemporaryFile(suffix=".docx",delete=False) as f: path=Path(f.name)
      render_docx(data,path,ROOT/"templates"/"Шаблон_КП.docx")
      return send_file(path,as_attachment=True,download_name="kommercheskoe_predlozhenie.docx")
    except Exception as e:
      return f"Ошибка создания документа: {e}",400
if __name__=="__main__": app.run(host="127.0.0.1",port=int(os.getenv("PORT","5000")),debug=False)
