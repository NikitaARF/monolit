from decimal import Decimal, ROUND_HALF_UP

import pytest

from engine import Catalog, calculate, money


@pytest.fixture(scope="module")
def catalog():
    return Catalog()


def parsed(items, *, method="самовывоз", settlement=None, pickup_branch="Пермь", letter_id="99"):
    return {
        "letter_id": letter_id,
        "client": {"name": "Тест", "company": None, "email": None, "phone": None},
        "delivery_method": method,
        "settlement": settlement,
        "pickup_branch": pickup_branch,
        "items": items,
        "clarify": [],
        "notes": [],
    }


def test_volume_conversion_and_sales_multiple(catalog):
    item = catalog.make_item("12001", 5, "м³")
    # 5 / 0.036 = 138.89 -> 139; then rounded up to a multiple of 40.
    assert item["qty"] == 160
    assert item["unit"] == "шт"
    assert item["amount"] == 40800.00


def test_area_conversion_and_reserve_before_conversion(catalog):
    item = catalog.make_item("14015", 96, "м²", reserve_pct=10)
    # 96 m² + 10% = 105.6 m²; a roll covers 70 m².
    assert item["qty"] == 2
    assert item["amount"] == 5900.00


def test_sales_multiple_rounds_up(catalog):
    item = catalog.make_item("12001", 41, "шт")
    assert item["qty"] == 80


def test_discount_tier_counts_promo_but_discount_excludes_it(catalog):
    data = calculate(parsed([
        {"request": "Ротбанд", "sku": "11005", "quantity": 160, "unit": "меш"},
        {"request": "Цемент М500", "sku": "11002", "quantity": 100, "unit": "меш"},
    ]), catalog)
    assert data["goods_total"] == 158900.00
    assert data["discount_percent"] == 3
    assert data["discount_base"] == 56500.00
    assert data["discount_amount"] == 1695.00
    assert data["goods_after_discount"] == 157205.00


def test_manipulator_and_trip_count(catalog):
    data = calculate(parsed([
        {"request": "Доска длинномер", "sku": "16005", "quantity": 500, "unit": "шт"}
    ], method="доставка", settlement="Оверята"), catalog)
    assert data["weight_kg"] == 11250.00
    assert data["delivery"]["vehicle"] == "Манипулятор"
    assert data["delivery"]["trips"] == 2
    assert data["delivery"]["cost"] == 10800.00


def test_free_delivery_condition(catalog):
    data = calculate(parsed([
        {"request": "Теплица 3×8", "sku": "20003", "quantity": 5, "unit": "шт"}
    ], method="доставка", settlement="Пермь"), catalog)
    assert data["discount_percent"] == 3
    assert data["goods_after_discount"] == 154715.00
    assert data["delivery"]["zone"] == 1
    assert data["delivery"]["free"] is True
    assert data["delivery"]["cost"] == 0.00
    assert data["total"] == data["goods_after_discount"]
    assert any("Бесплатная доставка" in n for n in data["notes"])


def test_unknown_or_far_settlement_is_not_charged(catalog):
    data = calculate(parsed([
        {"request": "Цемент", "sku": "11002", "quantity": 10, "unit": "меш"}
    ], method="доставка", settlement="Неизвестный город"), catalog)
    assert data["delivery"]["status"] == "уточнить"
    assert data["delivery"]["cost"] == 0.00
    assert data["total"] == data["goods_after_discount"]
    assert "стоимость доставки по согласованию" in data["notes"]


def test_vat_is_extracted_from_gross_total(catalog):
    data = calculate(parsed([
        {"request": "Цемент М500", "sku": "11002", "quantity": 1, "unit": "меш"}
    ]), catalog)
    expected = (Decimal(str(data["total"])) * Decimal("22") / Decimal("122")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    assert Decimal(str(data["vat"])) == expected


def test_on_order_item_is_kept_and_noted(catalog):
    data = calculate(parsed([
        {"request": "Брус клееный", "sku": "16012", "quantity": 1, "unit": "шт"}
    ]), catalog)
    assert data["items"][0]["on_order_days"] == 10
    assert any("под заказ, срок поставки 10 дн." in n for n in data["notes"])


def test_zero_quantity_is_rejected(catalog):
    with pytest.raises(ValueError, match="больше нуля"):
        catalog.make_item("11002", 0, "меш")


def test_money_rounding():
    assert money("1.005") == Decimal("1.01")


def test_malformed_items_are_moved_to_clarify_instead_of_crashing(catalog):
    data = calculate(parsed([
        "not-an-object",
        {"request": "Цемент без количества", "sku": "11002", "quantity": "много", "unit": "меш"},
    ]), catalog)
    assert data["items"] == []
    assert len(data["clarify"]) == 2


def test_unknown_delivery_method_is_not_priced(catalog):
    data = calculate({
        "letter_id": "98",
        "client": {},
        "delivery_method": "не знаю",
        "settlement": "Пермь",
        "items": [{"request": "Цемент", "sku": "11002", "quantity": 1, "unit": "меш"}],
    }, catalog)
    assert data["delivery_method"] == "доставка"
    assert data["delivery"]["status"] == "уточнить"
    assert data["delivery"]["cost"] == 0.00
    assert any(c["request"] == "Способ получения заказа" for c in data["clarify"])


def test_five_percent_discount_tier_and_promo_exclusion(catalog):
    data = calculate(parsed([
        {"request": "Теплица 3×8", "sku": "20003", "quantity": 10, "unit": "шт"},
        {"request": "Ротбанд по акции", "sku": "11005", "quantity": 160, "unit": "меш"},
    ]), catalog)
    assert data["goods_total"] == 421400.00
    assert data["discount_percent"] == 5
    assert data["discount_base"] == 319000.00
    assert data["discount_amount"] == 15950.00


def test_delivery_over_sixty_km_requires_agreement(catalog):
    data = calculate(parsed([
        {"request": "Цемент М500", "sku": "11002", "quantity": 10, "unit": "меш"}
    ], method="доставка", settlement="Добрянка"), catalog)
    assert data["delivery"]["status"] == "уточнить"
    assert data["delivery"]["distance_km"] == 72
    assert data["delivery"]["cost"] == 0.00
    assert "стоимость доставки по согласованию" in data["notes"]
