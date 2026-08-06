from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator

NON_NEGATIVE_PRICE_VALIDATORS = [MinValueValidator(Decimal("0"))]
MARGIN_RATE_VALIDATORS = [
    MinValueValidator(Decimal("0")),
    MaxValueValidator(Decimal("1")),
]
