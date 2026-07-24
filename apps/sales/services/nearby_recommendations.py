from apps.sales.models import Customer
from apps.sales.services.customer_links import phone_tel_href


def get_recommended_nearby_customers(anchor: Customer, limit=8):
    """Same delivery area first, then nearby delivery sequence. No geo/AI."""
    if not anchor.region:
        return []

    candidates = list(
        Customer.objects.filter(is_active=True, region=anchor.region).exclude(pk=anchor.pk)
    )
    if not candidates:
        return []

    anchor_seq = anchor.delivery_sequence

    def sort_key(customer):
        if anchor_seq is None or customer.delivery_sequence is None:
            return (1, customer.code)
        return (0, abs(customer.delivery_sequence - anchor_seq), customer.code)

    candidates.sort(key=sort_key)
    return candidates[:limit]


def build_recommendation_row(customer):
    phones = [p for p in (customer.phone, customer.phone_2, customer.phone_3) if p]
    phone_href = phone_tel_href(phones[0]) if phones else None

    return {
        "customer": customer,
        "code": customer.code,
        "name": customer.name,
        "region": customer.region or "—",
        "delivery_sequence": customer.delivery_sequence if customer.delivery_sequence is not None else "—",
        "phones": phones,
        "phone_display": " / ".join(phones) if phones else "—",
        "phone_href": phone_href,
        "address": customer.address or "—",
        "last_transaction_date": customer.last_transaction_date or "—",
    }
