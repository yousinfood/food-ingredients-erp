from apps.sales.models import SalesOrder

from .dashboard_order_filters import (
    DASHBOARD_STAT_FILTER_KEYS,
    TODAY_DELIVERED,
    TODAY_UNDELIVERED,
    dashboard_stat_links,
    queryset_for_dashboard_filter,
)


def get_dashboard_stats():
    deliveries_today = queryset_for_dashboard_filter(TODAY_DELIVERED).count()
    undelivered_today = queryset_for_dashboard_filter(TODAY_UNDELIVERED).count()
    recent_orders = (
        SalesOrder.objects.select_related("customer")
        .exclude(status=SalesOrder.Status.CANCELLED)
        .order_by("-order_date", "-created_at")[:8]
    )
    return {
        "deliveries_today": deliveries_today,
        "undelivered_today": undelivered_today,
        "pending_collection_today": "—",
        "overdue_today": "—",
        "recent_orders": recent_orders,
        "stat_links": dashboard_stat_links(),
        "stat_filter_keys": DASHBOARD_STAT_FILTER_KEYS,
    }
