from __future__ import annotations

import re
from dataclasses import dataclass

from django.db.models import Q
from django.utils.html import escape
from django.utils.safestring import mark_safe

from apps.sales.models import Customer

# 從第一個字元即搜尋；資料庫明顯變大前不提高到 2 字。
MIN_SEARCH_QUERY_LENGTH = 1

TOUCH_SEARCH_LIMIT = 12


@dataclass(frozen=True)
class RankedCustomerSearch:
    customers: list[Customer]
    total_count: int
    limit: int
    show_all: bool

    @property
    def has_more(self) -> bool:
        return not self.show_all and self.total_count > len(self.customers)

    @property
    def remaining_count(self) -> int:
        return max(0, self.total_count - len(self.customers))


def _query_filter(q: str) -> Q:
    return (
        Q(name__icontains=q)
        | Q(code__icontains=q)
        | Q(phone__icontains=q)
        | Q(phone_2__icontains=q)
        | Q(phone_3__icontains=q)
        | Q(tax_id__icontains=q)
        | Q(address__icontains=q)
        | Q(invoice_address__icontains=q)
        | Q(region__icontains=q)
    )


def _phone_digits(value: str | None) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def customer_relevance_tier(customer: Customer, query: str) -> int:
    """Lower = higher priority: name start → name contains → phone → address → code."""
    q = query.strip()
    if not q:
        return 99
    ql = q.casefold()
    q_digits = _phone_digits(q)

    name = (customer.name or "").casefold()
    if name.startswith(ql):
        return 1
    if ql in name:
        return 2

    for phone in (customer.phone, customer.phone_2, customer.phone_3):
        if not phone:
            continue
        pl = phone.casefold()
        pd = _phone_digits(phone)
        if q_digits and pd:
            if pd.startswith(q_digits):
                return 3
            if q_digits in pd:
                return 4
        if ql in pl:
            return 4

    for addr in (customer.address, customer.invoice_address, customer.region):
        if addr and ql in addr.casefold():
            return 5

    code = (customer.code or "").casefold()
    if ql in code:
        return 6
    if customer.tax_id and ql in customer.tax_id.casefold():
        return 6

    return 99


def _sort_key(customer: Customer, query: str) -> tuple:
    tier = customer_relevance_tier(customer, query)
    name = customer.name or ""
    return (tier, name.casefold(), name)


def search_customers_ranked(
    query: str,
    *,
    limit: int = TOUCH_SEARCH_LIMIT,
    show_all: bool = False,
    active_only: bool = True,
) -> RankedCustomerSearch:
    q = query.strip()
    queryset = Customer.objects.all()
    if active_only:
        queryset = queryset.filter(is_active=True)
    if len(q) < MIN_SEARCH_QUERY_LENGTH:
        return RankedCustomerSearch([], 0, limit, show_all)

    matches = list(queryset.filter(_query_filter(q)))
    matches.sort(key=lambda c: _sort_key(c, q))
    total = len(matches)
    if show_all:
        shown = matches
    else:
        shown = matches[: max(1, limit)]
    return RankedCustomerSearch(shown, total, limit, show_all)


def search_customers(*, query="", name="", phone="", code="", tax_id="", address="", active_only=True):
    queryset = Customer.objects.all()
    if active_only:
        queryset = queryset.filter(is_active=True)

    q = query.strip()
    if q:
        ranked = search_customers_ranked(q, show_all=True, active_only=active_only)
        return ranked.customers

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
        customers = customers.filter(_query_filter(query))
        matches = list(customers)
        matches.sort(key=lambda c: _sort_key(c, query))
        return matches
    return customers.order_by("code")


def get_customer_regions():
    return (
        Customer.objects.exclude(region="")
        .values_list("region", flat=True)
        .distinct()
        .order_by("region")
    )


def highlight_match(text: str | None, query: str) -> str:
    if text is None:
        return ""
    raw = str(text)
    q = query.strip()
    if not q:
        return escape(raw)
    escaped = escape(raw)
    try:
        pattern = re.compile(re.escape(q), re.IGNORECASE)
    except re.error:
        return escaped
    return mark_safe(pattern.sub(r'<mark class="touch-search-mark">\g<0></mark>', escaped))


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
