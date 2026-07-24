from decimal import Decimal

from django.db.models import Sum

from apps.sales.models import SalesOrder, SalesOrderItem


def _fmt_money(value) -> str:
    if value is None:
        return "—"
    return f"${value:,.0f}"


def _fmt_date(value) -> str:
    if not value:
        return "—"
    return value.strftime("%Y/%m/%d")


def compute_accounts_receivable(customer) -> Decimal:
    """Sum non-cancelled order totals (payments module not yet implemented)."""
    orders = customer.sales_orders.exclude(status=SalesOrder.Status.CANCELLED)
    total = Decimal("0")
    for order in orders:
        total += order.total_amount
    return total


def get_recent_orders(customer, limit=5):
    return list(
        customer.sales_orders.select_related("customer")
        .prefetch_related("items__product")
        .order_by("-order_date", "-created_at")[:limit]
    )


def get_order_history(customer, limit=50):
    return list(
        customer.sales_orders.select_related("customer")
        .prefetch_related("items__product")
        .order_by("-order_date", "-created_at")[:limit]
    )


def get_recent_selling_prices(customer, limit=5):
    """Latest unit price per product from this customer's orders."""
    items = (
        SalesOrderItem.objects.filter(sales_order__customer=customer)
        .exclude(sales_order__status=SalesOrder.Status.CANCELLED)
        .select_related("product", "sales_order")
        .order_by("-sales_order__order_date", "-sales_order__created_at")
    )
    seen = set()
    results = []
    for item in items:
        if item.product_id in seen:
            continue
        seen.add(item.product_id)
        results.append(
            {
                "product_sku": item.product.sku,
                "product_name": item.product.name,
                "unit_price": item.unit_price,
                "order_date": item.sales_order.order_date,
                "order_no": item.sales_order.order_no,
            }
        )
        if len(results) >= limit:
            break
    return results


def get_price_history(customer):
    """All line-item prices grouped by product (most recent first)."""
    items = (
        SalesOrderItem.objects.filter(sales_order__customer=customer)
        .exclude(sales_order__status=SalesOrder.Status.CANCELLED)
        .select_related("product", "sales_order")
        .order_by("-sales_order__order_date", "-id")
    )
    return [
        {
            "product_sku": item.product.sku,
            "product_name": item.product.name,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "order_date": item.sales_order.order_date,
            "order_no": item.sales_order.order_no,
        }
        for item in items
    ]


from apps.sales.services.customer_links import (
    delivery_address,
    maps_navigation_urls,
    phone_tel_href,
    primary_phone_href,
)


def build_customer_center(customer):
    recent_orders = get_recent_orders(customer, limit=3)
    recent_prices = get_recent_selling_prices(customer, limit=5)
    balance = compute_accounts_receivable(customer)

    last_order = customer.sales_orders.order_by("-order_date", "-created_at").first()
    latest_tx = customer.last_transaction_date or (last_order.order_date if last_order else None)

    credit_limit = customer.credit_limit
    credit_used_pct = None
    if credit_limit and credit_limit > 0:
        credit_used_pct = min(int((balance / credit_limit) * 100), 100)

    phone = customer.phone or "—"
    phone_2 = customer.phone_2 or "—"
    phone_3 = customer.phone_3 or "—"
    address = customer.address or "—"
    delivery = delivery_address(customer)
    maps_urls = maps_navigation_urls(delivery) if delivery else None
    call_href = primary_phone_href(customer)

    return {
        "customer": customer,
        "name": customer.name,
        "code": customer.code,
        "region": customer.region or "—",
        "address": address,
        "invoice_address": customer.invoice_address or "—",
        "phone": phone,
        "phone_2": phone_2,
        "phone_3": phone_3,
        "phone_href": phone_tel_href(customer.phone),
        "phone_2_href": phone_tel_href(customer.phone_2),
        "phone_3_href": phone_tel_href(customer.phone_3),
        "call_href": call_href,
        "can_navigate": bool(delivery),
        "can_call": bool(call_href),
        "maps_apple_href": maps_urls["apple"] if maps_urls else "",
        "maps_google_href": maps_urls["google"] if maps_urls else "",
        "line_id": customer.line_id or "—",
        "contact_person": customer.contact_person or "—",
        "tax_id": customer.tax_id or "—",
        "notes": customer.notes or "—",
        "is_active": customer.is_active,
        "payment_method": customer.payment_method or "—",
        "delivery_day": customer.delivery_day or "—",
        "delivery_sequence": customer.delivery_sequence if customer.delivery_sequence is not None else "—",
        "credit_limit": _fmt_money(credit_limit),
        "credit_limit_raw": credit_limit,
        "current_balance": _fmt_money(balance),
        "current_balance_raw": balance,
        "credit_used_pct": credit_used_pct,
        "latest_transaction_date": _fmt_date(latest_tx),
        "recent_orders": recent_orders,
        "order_count": customer.sales_orders.count(),
        "recent_prices": recent_prices,
    }
