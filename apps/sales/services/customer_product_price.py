"""Resolve customer-specific sale prices for order flow and admin."""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from apps.inventory.models import Product
from apps.sales.models import Customer, CustomerProductPrice
from apps.sales.services.pricing import PricingService


def _active_customer_price_row(
    customer: Customer,
    product: Product,
    *,
    as_of=None,
) -> CustomerProductPrice | None:
    as_of = as_of or timezone.localdate()
    return (
        CustomerProductPrice.objects.filter(
            customer=customer,
            product=product,
            is_active=True,
            effective_from__lte=as_of,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=as_of))
        .order_by("-effective_from", "-pk")
        .first()
    )


def resolve_sale_price_detail(
    product: Product,
    customer: Customer | None,
    *,
    as_of=None,
) -> tuple[Decimal | None, str, int | None]:
    """Return (price, price_source, price_version). source: customer | standard | \"\"."""
    as_of = as_of or timezone.localdate()
    if customer is not None:
        row = _active_customer_price_row(customer, product, as_of=as_of)
        if row is not None:
            return row.price, "customer", row.pk
    if product.standard_price is not None:
        return product.standard_price, "standard", None
    return None, "", None


def resolve_sale_price(product: Product, customer: Customer | None, *, as_of=None) -> Decimal | None:
    return PricingService().calculate(product, customer, as_of=as_of).sale_price


def build_price_map(customer: Customer, product_ids: list[int]) -> dict[str, str]:
    if not product_ids:
        return {}
    products = Product.objects.filter(pk__in=product_ids)
    service = PricingService()
    as_of = timezone.localdate()
    out: dict[str, str] = {}
    for product in products:
        price = service.calculate(product, customer, as_of=as_of).sale_price
        if price is not None:
            out[str(product.pk)] = str(price)
    return out


def enrich_product_pricing(item: dict, customer: Customer | None, product: Product) -> dict:
    price, source, version = resolve_sale_price_detail(product, customer)
    if price is not None:
        item["resolved_unit_price"] = str(price)
        item["last_unit_price"] = str(price)
        item["price_unset"] = False
    else:
        item["price_unset"] = True
    item["price_source"] = source
    if version is not None:
        item["price_version"] = version
    return item
