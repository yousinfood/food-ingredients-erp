"""Helpers for delivery list display and trip creation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Max, Prefetch, Q, QuerySet
from django.utils import timezone

from apps.deliveries.models import DeliveryTrip, DeliveryTripOrder
from apps.sales.models import SalesOrder, SalesOrderItem

DELIVERABLE_STATUSES = (
    SalesOrder.Status.CREATED,
    SalesOrder.Status.CONFIRMED,
)

ACTIVE_TRIP_STATUSES = (
    DeliveryTrip.Status.PREPARING,
    DeliveryTrip.Status.DEPARTED,
)


class TripCreationError(Exception):
    """Raised when a delivery trip cannot be created."""


@dataclass
class OrderSummaryLine:
    text: str


def orders_for_delivery_date(delivery_date: date) -> QuerySet[SalesOrder]:
    """Orders due on a date that are not yet assigned to any delivery trip."""
    assigned_ids = DeliveryTripOrder.objects.values_list("sales_order_id", flat=True)

    return (
        SalesOrder.objects.filter(
            status__in=DELIVERABLE_STATUSES,
            delivery_date=delivery_date,
        )
        .exclude(pk__in=assigned_ids)
        .select_related("customer")
        .prefetch_related(
            Prefetch(
                "items",
                queryset=SalesOrderItem.objects.select_related("product").order_by("pk"),
            )
        )
        .order_by("customer__region", "customer__name", "order_no")
    )


def parse_delivery_date(raw: str | None) -> date:
    if not raw:
        return timezone.localdate()
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return timezone.localdate()


def shift_delivery_date(current: date, delta_days: int) -> date:
    return current + timedelta(days=delta_days)


def format_quantity(qty: Decimal) -> str:
    normalized = qty.normalize()
    text = format(normalized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def build_order_summary(order: SalesOrder, max_items: int = 3) -> list[str]:
    items = list(order.items.all())
    lines: list[str] = []
    for item in items[:max_items]:
        name = item.product.name if item.product_id else "商品"
        lines.append(f"{name} × {format_quantity(item.quantity)}")
    extra = len(items) - max_items
    if extra > 0:
        lines.append(f"另有 {extra} 項商品")
    return lines


def total_item_quantity(order: SalesOrder) -> Decimal:
    total = Decimal("0")
    for item in order.items.all():
        total += item.quantity
    return total


def make_trip_code(trip_date: date, trip_number: int) -> str:
    return f"TRIP-{trip_date.strftime('%Y%m%d')}-{trip_number:02d}"


def next_trip_number(trip_date: date) -> int:
    last = (
        DeliveryTrip.objects.filter(trip_date=trip_date)
        .aggregate(max_num=Max("trip_number"))
        .get("max_num")
    )
    return (last or 0) + 1


@transaction.atomic
def create_delivery_trip(order_ids: list[int], trip_date: date | None = None) -> DeliveryTrip:
    """
    Create a delivery trip with the given orders in list order.
    Rolls back entirely if any order is invalid or already assigned.
    """
    if not order_ids:
        raise TripCreationError("請至少選擇一張訂單")

    trip_date = trip_date or timezone.localdate()

    locked_orders = list(
        SalesOrder.objects.select_for_update()
        .filter(pk__in=order_ids)
        .select_related("customer")
    )

    if len(locked_orders) != len(set(order_ids)):
        raise TripCreationError("部分訂單不存在，請重新整理後再試")

    order_map = {order.pk: order for order in locked_orders}
    ordered_orders = [order_map[pk] for pk in order_ids if pk in order_map]

    assigned = set(
        DeliveryTripOrder.objects.select_for_update()
        .filter(
            sales_order_id__in=order_ids,
            delivery_trip__status__in=ACTIVE_TRIP_STATUSES,
        )
        .values_list("sales_order_id", flat=True)
    )
    if assigned:
        raise TripCreationError("部分訂單已被安排出車，請重新整理後再試")

    for order in ordered_orders:
        if order.status not in DELIVERABLE_STATUSES:
            raise TripCreationError(f"訂單 {order.order_no} 目前無法安排出車")
        if order.status == SalesOrder.Status.CANCELLED:
            raise TripCreationError(f"訂單 {order.order_no} 已作廢")

    trip_number = next_trip_number(trip_date)
    trip = DeliveryTrip.objects.create(
        trip_date=trip_date,
        trip_number=trip_number,
        trip_code=make_trip_code(trip_date, trip_number),
        status=DeliveryTrip.Status.PREPARING,
    )

    for index, order in enumerate(ordered_orders, start=1):
        DeliveryTripOrder.objects.create(
            delivery_trip=trip,
            sales_order=order,
            sequence=index,
            status=DeliveryTripOrder.Status.PENDING,
        )

    return trip


def trip_detail_context(trip: DeliveryTrip) -> dict:
    trip_orders = (
        trip.trip_orders.select_related("sales_order", "sales_order__customer")
        .prefetch_related(
            Prefetch(
                "sales_order__items",
                queryset=SalesOrderItem.objects.select_related("product").order_by("pk"),
            )
        )
        .order_by("sequence")
    )
    customer_ids = {to.sales_order.customer_id for to in trip_orders}
    return {
        "trip": trip,
        "trip_orders": trip_orders,
        "order_count": trip_orders.count(),
        "customer_count": len(customer_ids),
    }
