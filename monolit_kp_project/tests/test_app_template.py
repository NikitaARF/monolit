import ast
import json
from pathlib import Path

from jinja2 import Template

ROOT = Path(__file__).resolve().parents[1]


def load_html_template():
    module = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    for node in module.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "HTML" for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError("HTML-шаблон не найден в app.py")


def money(value):
    return f"{float(value):,.2f}".replace(",", " ").replace(".", ",")


def test_result_page_renders_items_and_clarification_without_flask():
    data = json.loads((ROOT / "results" / "kp_04.json").read_text(encoding="utf-8"))
    letter = (ROOT / "letters" / "Письмо_04.txt").read_text(encoding="utf-8")
    html = Template(load_html_template()).render(
        letter=letter,
        result=data,
        error=None,
        payload=json.dumps(data, ensure_ascii=False),
        money=money,
    )
    assert "Пароизоляция Изоспан B" in html
    assert "Требует уточнения — в сумму не включено" in html
    assert "Ольга Ракитина" in html
    assert "Скачать КП в DOCX" in html
