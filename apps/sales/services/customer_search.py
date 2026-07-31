from __future__ import annotations

import re
from dataclasses import dataclass

import logging

from django.db.models import Q
from django.utils.html import escape
from django.utils.safestring import mark_safe

from apps.sales.models import Customer
from apps.sales.services.voice_search_normalize import (
    VOICE_SIMILARITY_THRESHOLD,
    normalize_voice_query,
    similarity_score,
)

# 從第一個字元即搜尋；資料庫明顯變大前不提高到 2 字。
MIN_SEARCH_QUERY_LENGTH = 1

TOUCH_SEARCH_LIMIT = 12
VOICE_SEARCH_LIMIT = 5

logger = logging.getLogger(__name__)


def _maybe_sync_customers_from_google_sheet() -> None:
    try:
        from apps.sales.services.google_sheet_customer_sync import (
            maybe_sync_customers_from_google_sheet,
        )

        result = maybe_sync_customers_from_google_sheet()
        if result.get("skipped") and result.get("reason") == "not_configured":
            logger.warning("Customer sheet sync skipped: Google Sheet 尚未設定")
        elif not result.get("ok") and not result.get("skipped"):
            logger.warning("Customer sheet sync failed: %s", result)
    except Exception as exc:
        logger.warning("Customer sheet sync raised an exception: %s", exc, exc_info=True)


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


def parse_voice_aliases(raw: str | None) -> list[str]:
    if not raw:
        return []
    text = raw.replace("，", ",")
    return [part.strip() for part in text.split(",") if part.strip()]


def _query_filter(q: str) -> Q:
    return (
        Q(name__icontains=q)
        | Q(code__icontains=q)
        | Q(contact_person__icontains=q)
        | Q(phone__icontains=q)
        | Q(phone_2__icontains=q)
        | Q(phone_3__icontains=q)
        | Q(tax_id__icontains=q)
        | Q(address__icontains=q)
        | Q(invoice_address__icontains=q)
        | Q(region__icontains=q)
        | Q(voice_aliases__icontains=q)
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


def _voice_match_score(customer: Customer, query: str) -> float:
    scores = [similarity_score(query, customer.name or "")]
    for alias in parse_voice_aliases(customer.voice_aliases):
        scores.append(similarity_score(query, alias))
    if customer.contact_person:
        scores.append(similarity_score(query, customer.contact_person))
    return max(scores) if scores else 0.0


def voice_customer_relevance_tier(customer: Customer, query: str) -> int:
    """Voice ranking: exact name → exact alias → name prefix → alias contains → fuzzy."""
    q = query.strip()
    if not q:
        return 99
    ql = q.casefold()
    name = customer.name or ""

    if name == q:
        return 1

    for alias in parse_voice_aliases(customer.voice_aliases):
        if alias == q:
            return 2

    if name.startswith(q):
        return 3

    for alias in parse_voice_aliases(customer.voice_aliases):
        if q in alias or ql in alias.casefold():
            return 4

    if ql in name.casefold():
        return 5
    if customer.contact_person and ql in customer.contact_person.casefold():
        return 5
    for field in (customer.region, customer.address, customer.invoice_address):
        if field and ql in field.casefold():
            return 5
    for alias in parse_voice_aliases(customer.voice_aliases):
        if ql in alias.casefold():
            return 5
    if _voice_match_score(customer, query) >= VOICE_SIMILARITY_THRESHOLD:
        return 5

    return 99


def _expand_voice_queries(candidates: list[str]) -> list[str]:
    seen: set[str] = set()
    expanded: list[str] = []
    for raw in candidates:
        for q in (raw.strip(), normalize_voice_query(raw.strip())):
            if q and q not in seen:
                seen.add(q)
                expanded.append(q)
    return expanded


def search_customers_voice(
    candidates: list[str],
    *,
    limit: int = VOICE_SEARCH_LIMIT,
    active_only: bool = True,
) -> RankedCustomerSearch:
    _maybe_sync_customers_from_google_sheet()
    queries = _expand_voice_queries(candidates)
    if not queries:
        return RankedCustomerSearch([], 0, limit, show_all=False)

    queryset = Customer.objects.all()
    if active_only:
        queryset = queryset.filter(is_active=True)

    best: dict[int, tuple[int, float, Customer]] = {}

    def consider(customer: Customer, q: str, *, fuzzy_score: float | None = None) -> None:
        tier = voice_customer_relevance_tier(customer, q)
        if tier >= 99:
            return
        score = fuzzy_score if fuzzy_score is not None else _voice_match_score(customer, q)
        prev = best.get(customer.pk)
        if prev is None or tier < prev[0] or (tier == prev[0] and score > prev[1]):
            best[customer.pk] = (tier, score, customer)

    for q in queries:
        for customer in queryset.filter(_query_filter(q)):
            consider(customer, q)

    for q in queries:
        norm = normalize_voice_query(q)
        for fuzzy_score, customer in _voice_fuzzy_matches(queryset, q, norm):
            consider(customer, q, fuzzy_score=fuzzy_score)

    ranked = sorted(
        best.values(),
        key=lambda item: (item[0], -item[1], (item[2].name or "").casefold()),
    )
    matches = [customer for _, _, customer in ranked]
    shown = matches[:limit]
    return RankedCustomerSearch(shown, len(matches), limit, show_all=False)


def _voice_fuzzy_matches(queryset, raw_q: str, norm_q: str) -> list[tuple[float, Customer]]:
    scored: list[tuple[float, Customer]] = []
    for customer in queryset.iterator(chunk_size=500):
        score = _voice_match_score(customer, raw_q)
        if norm_q and norm_q != raw_q:
            score = max(score, _voice_match_score(customer, norm_q))
        if score >= VOICE_SIMILARITY_THRESHOLD:
            scored.append((score, customer))
    scored.sort(key=lambda pair: (-pair[0], (pair[1].name or "").casefold()))
    return scored


def search_customers_ranked(
    query: str,
    *,
    limit: int = TOUCH_SEARCH_LIMIT,
    show_all: bool = False,
    active_only: bool = True,
    voice: bool = False,
) -> RankedCustomerSearch:
    _maybe_sync_customers_from_google_sheet()
    raw_q = query.strip()
    q = normalize_voice_query(raw_q) if voice else raw_q
    queryset = Customer.objects.all()
    if active_only:
        queryset = queryset.filter(is_active=True)
    if len(raw_q) < MIN_SEARCH_QUERY_LENGTH:
        return RankedCustomerSearch([], 0, limit, show_all)

    if voice:
        search_q = q or raw_q
        exact_ids: set[int] = set()
        matches: list[Customer] = []
        for candidate_q in (search_q, raw_q):
            if len(candidate_q) < MIN_SEARCH_QUERY_LENGTH:
                continue
            for customer in queryset.filter(_query_filter(candidate_q)):
                if customer.pk not in exact_ids:
                    exact_ids.add(customer.pk)
                    matches.append(customer)

        fuzzy_scored = _voice_fuzzy_matches(queryset, raw_q, search_q)
        fuzzy_by_id = {c.pk: (score, c) for score, c in fuzzy_scored}

        combined: dict[int, tuple[float, Customer]] = {}
        for customer in matches:
            score = fuzzy_by_id.get(customer.pk, (0.0, customer))[0]
            if score < VOICE_SIMILARITY_THRESHOLD:
                score = max(
                    similarity_score(search_q, customer.name or ""),
                    similarity_score(raw_q, customer.name or ""),
                    0.85,
                )
            combined[customer.pk] = (score, customer)
        for score, customer in fuzzy_scored:
            if customer.pk not in combined:
                combined[customer.pk] = (score, customer)

        ranked = sorted(combined.values(), key=lambda pair: (-pair[0], _sort_key(pair[1], search_q)))
        matches = [c for _, c in ranked]
    else:
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
