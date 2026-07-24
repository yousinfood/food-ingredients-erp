from decimal import Decimal

from django.db.models import Q

from apps.sales.models import Customer


def search_customers(*, query="", name="", phone="", code="", tax_id="", address="", active_only=True):
    queryset = Customer.objects.all()
    if active_only:
        queryset = queryset.filter(is_active=True)

    q = query.strip()
    if q:
        return queryset.filter(
            Q(name__icontains=q)
            | Q(code__icontains=q)
            | Q(phone__icontains=q)
            | Q(phone_2__icontains=q)
            | Q(phone_3__icontains=q)
            | Q(tax_id__icontains=q)
            | Q(address__icontains=q)
            | Q(invoice_address__icontains=q)
            | Q(region__icontains=q)
        ).order_by("code")

    filters = Q()
    if name:
        filters |= Q(name__icontains=name)
    if phone:
        filters |= (
            Q(phone__icontains=phone)
            | Q(phone_2__icontains=phone)
            | Q(phone_3__icontains=phone)
        )
    if code:
        filters |= Q(code__icontains=code)
    if tax_id:
        filters |= Q(tax_id__icontains=tax_id)
    if address:
        filters |= Q(address__icontains=address) | Q(invoice_address__icontains=address)

    if not filters:
        return queryset.none()

    return queryset.filter(filters).order_by("code")


def filter_customers(*, query="", region="", show_inactive=False):
    customers = Customer.objects.all()
    if not show_inactive:
        customers = customers.filter(is_active=True)
    if region:
        customers = customers.filter(region=region)
    if query:
        customers = customers.filter(
            Q(name__icontains=query)
            | Q(code__icontains=query)
            | Q(phone__icontains=query)
            | Q(phone_2__icontains=query)
            | Q(phone_3__icontains=query)
            | Q(tax_id__icontains=query)
            | Q(contact_person__icontains=query)
            | Q(region__icontains=query)
        )
    return customers.order_by("code")


def get_customer_regions():
    return (
        Customer.objects.exclude(region="")
        .values_list("region", flat=True)
        .distinct()
        .order_by("region")
    )


def _format_decimal(value):
    if value is None:
        return "—"
    return f"{value:,.0f}"


def _format_date(value):
    return value.isoformat() if value else "—"


def build_customer_profile(customer):
    last_order = customer.sales_orders.order_by("-order_date", "-created_at").first()
    last_products = "—"
    last_price = "—"
    last_order_date = "—"
    if last_order:
        last_order_date = last_order.order_date.isoformat()
        items = list(last_order.items.select_related("product")[:5])
        if items:
            last_products = "、".join(item.product.name for item in items)
            last_price = _format_decimal(items[0].unit_price)

    return {
        "id": customer.pk,
        "code": customer.code,
        "name": customer.name,
        "region": customer.region or "—",
        "phone": customer.phone or "—",
        "phone_2": customer.phone_2 or "—",
        "phone_3": customer.phone_3 or "—",
        "address": customer.address or "—",
        "invoice_address": customer.invoice_address or "—",
        "map_location": customer.map_location or "—",
        "line_id": customer.line_id or "—",
        "tax_id": customer.tax_id or "—",
        "contact_person": customer.contact_person or "—",
        "email": customer.email or "—",
        "payment_method": customer.payment_method or "—",
        "delivery_day": customer.delivery_day or "—",
        "delivery_sequence": customer.delivery_sequence if customer.delivery_sequence is not None else "—",
        "notes": customer.notes or "—",
        "accounts_receivable": "—",
        "credit_limit": _format_decimal(customer.credit_limit),
        "last_payment_date": _format_date(customer.last_transaction_date),
        "last_price": last_price,
        "last_order_date": last_order_date,
        "last_products": last_products,
    }
