from django.utils import timezone

from apps.sales.models import SalesOrder


def get_dashboard_stats():
    today = timezone.localdate()
    today_orders = SalesOrder.objects.filter(delivery_date=today).exclude(
        status=SalesOrder.Status.CANCELLED
    )
    deliveries_today = today_orders.filter(
        status__in=[SalesOrder.Status.SHIPPED, SalesOrder.Status.COMPLETED]
    ).count()
    undelivered_today = today_orders.filter(
        status__in=[
            SalesOrder.Status.DRAFT,
            SalesOrder.Status.CREATED,
            SalesOrder.Status.CONFIRMED,
        ]
    ).count()
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
    }
