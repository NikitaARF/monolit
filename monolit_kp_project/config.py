from decimal import Decimal
VAT_RATE = Decimal("22")
DISCOUNT_TIERS = [(Decimal("300000"), Decimal("5")), (Decimal("100000"), Decimal("3")), (Decimal("0"), Decimal("0"))]
FREE_DELIVERY_ZONE = 1
FREE_DELIVERY_MIN_GOODS_AFTER_DISCOUNT = Decimal("150000")
ZONE_LIMITS = [(10, 1), (30, 2), (60, 3)]
DEFAULT_MANAGER = "Не назначен"
LLM_PROVIDER = "openrouter"
