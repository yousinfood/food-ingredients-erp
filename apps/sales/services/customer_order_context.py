from decimal import Decimal
from datetime import date, timedelta

from django.db.models import Count, Q
from django.utils import timezone

from apps.inventory.models import Product
from apps.sales.models import SalesOrder, SalesOrderItem

from .product_search import product_to_dict

_WEEKDAY_ALIASES = {
    "mon": 0, "monday": 0, "一": 0, "週一": 0, "星期一": 0, "周一": 0,
    "tue": 1, "tuesday": 1, "二": 1, "週二": 1, "星期二": 1, "周二": 1,
    "wed": 2, "wednesday": 2, "三": 2, "週三": 2, "星期三": 2, "周三": 2,
    "thu": 3, "thursday": 3, "四": 3, "週四": 3, "星期四": 3, "周四": 3,
    "fri": 4, "friday": 4, "五": 4, "週五": 4, "星期五": 4, "周五": 4,
    "sat": 5, "saturday": 5, "六": 5, "週六": 5, "星期六": 5, "周六": 5,
    "sun": 6, "sunday": 6, "日": 6, "週日": 6, "星期日": 6, "周日": 6, "天": 6,
}


def _weekday_from_delivery_day(value: str) -> int | None:
    normalized = (value or "").strip().lower()
    if not normalized:
        return None
    if normalized in _WEEKDAY_ALIASES:
        return _WEEKDAY_ALIASES[normalized]
    for token, weekday in _WEEKDAY_ALIASES.items():
        if token in normalized:
            return weekday
    return None


def suggest_delivery_date(customer, *, today: date | None = None) -> date:
    """Default delivery date from customer delivery day, else today."""
    today = today or timezone.localdate()
    weekday = _weekday_from_delivery_day(customer.delivery_day)
    if weekday is None:
        return today
    days_ahead = (weekday - today.weekday()) % 7
    return today + timedelta(days=days_ahead)


def _line_dict(*, product, quantity, unit_price):
    base = product_to_dict(product)
    base["quantity"] = str(quantity)
    base["unit_price"] = str(unit_price)
    return base


def get_last_order_context(customer):
    """Most recent non-cancelled order with line items for copy-last-order."""
    last_order = (
        customer.sales_orders.exclude(status=SalesOrder.Status.CANCELLED)
        .prefetch_related("items__product")
        .order_by("-order_date", "-created_at")
        .first()
    )
    if not last_order:
        return None

    items = []
    for item in last_order.items.select_related("product").all():
        if not item.product.is_active:
            continue
        items.append(
            _line_dict(
                product=item.product,
                quantity=item.quantity,
                unit_price=item.unit_price,
            )
        )

    if not items:
        return None

    return {
        "order_no": last_order.order_no,
        "order_date": last_order.order_date.isoformat(),
        "item_count": len(items),
        "total_amount": str(last_order.total_amount),
        "items": items,
    }


def get_frequent_products(customer, limit=12):
    """Rank saleable products by recent purchase frequency for this customer."""
    today = timezone.localdate()
    since_30 = today - timedelta(days=30)
    since_90 = today - timedelta(days=90)
    rows = (
        SalesOrderItem.objects.filter(
            sales_order__customer=customer,
            sales_order__status__in=[
                SalesOrder.Status.DRAFT,
                SalesOrder.Status.CREATED,
                SalesOrder.Status.CONFIRMED,
                SalesOrder.Status.SHIPPED,
                SalesOrder.Status.COMPLETED,
            ],
            product__is_active=True,
            product__is_for_sale=True,
        )
        .values("product_id")
        .annotate(
            order_count=Count("sales_order_id", distinct=True),
            order_count_30=Count(
                "sales_order_id",
                filter=Q(sales_order__order_date__gte=since_30),
                distinct=True,
            ),
            order_count_90=Count(
                "sales_order_id",
                filter=Q(sales_order__order_date__gte=since_90),
                distinct=True,
            ),
        )
        .order_by("-order_count_30", "-order_count_90", "-order_count", "product_id")[: limit * 2]
    )

    if not rows:
        return []

    product_ids = [row["product_id"] for row in rows]
    products = {
        p.pk: p
        for p in Product.objects.filter(
            pk__in=product_ids,
            is_active=True,
            is_for_sale=True,
            product_kind__in=[Product.ProductKind.FINISHED, Product.ProductKind.DUAL],
        )
    }

    last_prices = _latest_prices_by_product(customer, product_ids)
    last_qtys = _latest_quantities_by_product(customer, product_ids)

    results = []
    for row in rows:
        product = products.get(row["product_id"])
        if not product:
            continue
        item = product_to_dict(product)
        item["order_count"] = row["order_count"]
        item["order_count_30"] = row["order_count_30"]
        item["order_count_90"] = row["order_count_90"]
        item["last_unit_price"] = str(last_prices.get(product.pk, Decimal("0")))
        item["last_quantity"] = str(last_qtys.get(product.pk, Decimal("1")))
        results.append(item)
        if len(results) >= limit:
            break
    return results


def _latest_prices_by_product(customer, product_ids):
    items = (
        SalesOrderItem.objects.filter(
            sales_order__customer=customer,
            product_id__in=product_ids,
        )
        .exclude(sales_order__status=SalesOrder.Status.CANCELLED)
        .select_related("sales_order")
        .order_by("-sales_order__order_date", "-sales_order__created_at")
    )
    prices = {}
    for item in items:
        if item.product_id not in prices:
            prices[item.product_id] = item.unit_price
    return prices


def _latest_quantities_by_product(customer, product_ids):
    items = (
        SalesOrderItem.objects.filter(
            sales_order__customer=customer,
            product_id__in=product_ids,
        )
        .exclude(sales_order__status=SalesOrder.Status.CANCELLED)
        .select_related("sales_order")
        .order_by("-sales_order__order_date", "-sales_order__created_at")
    )
    qtys = {}
    for item in items:
        if item.product_id not in qtys:
            qtys[item.product_id] = item.quantity
    return qtys


def build_order_page_context(customer):
    from apps.sales.services.product_search import get_saleable_categories

    return {
        "last_order": get_last_order_context(customer),
        "frequent_products": get_frequent_products(customer),
        "product_categories": get_saleable_categories(),
    }
