"""Dashboard stat cards → filtered sales order list (shared with list view)."""

from django.urls import reverse
from django.utils import timezone

from apps.sales.models import SalesOrder

TODAY_DELIVERED = "today_delivered"
TODAY_UNDELIVERED = "today_undelivered"
TODAY_PENDING_COLLECTION = "today_pending_collection"
TODAY_OVERDUE = "today_overdue"

DASHBOARD_FILTER_LABELS = {
    TODAY_DELIVERED: "今日配送",
    TODAY_UNDELIVERED: "今日未送",
    TODAY_PENDING_COLLECTION: "今日待收款",
    TODAY_OVERDUE: "今日欠款",
}

_DELIVERED_STATUSES = (SalesOrder.Status.SHIPPED, SalesOrder.Status.COMPLETED)
_UNDELIVERED_STATUSES = (
    SalesOrder.Status.DRAFT,
    SalesOrder.Status.CREATED,
    SalesOrder.Status.CONFIRMED,
)


def _orders_due_today():
    today = timezone.localdate()
    return SalesOrder.objects.filter(delivery_date=today).exclude(
        status=SalesOrder.Status.CANCELLED
    )


def queryset_for_dashboard_filter(filter_key: str):
    """Return queryset for a dashboard filter key, or None if unknown."""
    if filter_key == TODAY_DELIVERED:
        return _orders_due_today().filter(status__in=_DELIVERED_STATUSES)
    if filter_key == TODAY_UNDELIVERED:
        return _orders_due_today().filter(status__in=_UNDELIVERED_STATUSES)
    if filter_key in (TODAY_PENDING_COLLECTION, TODAY_OVERDUE):
        return SalesOrder.objects.none()
    return None


def dashboard_order_list_url(filter_key: str) -> str:
    base = reverse("sales:sales_order_list")
    return f"{base}?dashboard={filter_key}"


def dashboard_stat_links() -> dict[str, str]:
    return {
        "deliveries_today": dashboard_order_list_url(TODAY_DELIVERED),
        "undelivered_today": dashboard_order_list_url(TODAY_UNDELIVERED),
        "pending_collection_today": dashboard_order_list_url(TODAY_PENDING_COLLECTION),
        "overdue_today": dashboard_order_list_url(TODAY_OVERDUE),
    }
