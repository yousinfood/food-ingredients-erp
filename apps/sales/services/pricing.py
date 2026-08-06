from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from apps.inventory.models import Product, ProductCostHistory
from apps.sales.models import Customer, CustomerProductPrice


@dataclass(frozen=True)
class PricingResult:
    cost: Decimal | None
    sale_price: Decimal | None
    gross_profit: Decimal | None
    gross_margin: Decimal | None


class PricingService:
    """Resolve cost and sale price, then compute gross profit and margin."""

    def calculate(
        self,
        product: Product,
        customer: Customer | None = None,
        *,
        as_of: date | None = None,
    ) -> PricingResult:
        as_of = as_of or timezone.localdate()
        cost = self._resolve_cost(product, as_of=as_of)
        sale_price = self._resolve_sale_price(product, customer, as_of=as_of)
        gross_profit = self._gross_profit(sale_price, cost)
        gross_margin = self._gross_margin(gross_profit, sale_price)
        return PricingResult(
            cost=cost,
            sale_price=sale_price,
            gross_profit=gross_profit,
            gross_margin=gross_margin,
        )

    def _resolve_cost(self, product: Product, *, as_of: date) -> Decimal | None:
        as_of_dt = timezone.make_aware(datetime.combine(as_of, time.max))
        history = ProductCostHistory.get_latest_for_product(product, as_of=as_of_dt)
        if history is not None:
            return history.unit_cost
        if product.unit_cost is not None:
            return product.unit_cost
        return None

    def _resolve_sale_price(
        self,
        product: Product,
        customer: Customer | None,
        *,
        as_of: date,
    ) -> Decimal | None:
        if customer is not None:
            customer_price = (
                CustomerProductPrice.objects.filter(
                    customer=customer,
                    product=product,
                    is_active=True,
                    effective_from__lte=as_of,
                )
                .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=as_of))
                .order_by("-effective_from", "-pk")
                .values_list("price", flat=True)
                .first()
            )
            if customer_price is not None:
                return customer_price

        if product.standard_price is not None:
            return product.standard_price
        return None

    @staticmethod
    def _gross_profit(
        sale_price: Decimal | None,
        cost: Decimal | None,
    ) -> Decimal | None:
        if sale_price is None or cost is None:
            return None
        return sale_price - cost

    @staticmethod
    def _gross_margin(
        gross_profit: Decimal | None,
        sale_price: Decimal | None,
    ) -> Decimal | None:
        if gross_profit is None or sale_price is None or sale_price == 0:
            return None
        return (gross_profit / sale_price * Decimal("100")).quantize(Decimal("0.0001"))
