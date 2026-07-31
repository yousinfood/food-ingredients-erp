from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from apps.deliveries.models import DeliveryTrip
from apps.deliveries.services import (
    TripCreationError,
    build_order_summary,
    create_delivery_trip,
    orders_for_delivery_date,
    parse_delivery_date,
    shift_delivery_date,
    total_item_quantity,
    trip_detail_context,
)


@require_GET
def delivery_list(request):
    selected_date = parse_delivery_date(request.GET.get("date"))
    orders = list(orders_for_delivery_date(selected_date))
    for order in orders:
        order.summary_lines = build_order_summary(order)
        order.total_qty = total_item_quantity(order)
        order.display_address = order.shipping_address or order.customer.address

    return render(
        request,
        "deliveries/delivery_list.html",
        {
            "selected_date": selected_date,
            "prev_date": shift_delivery_date(selected_date, -1),
            "next_date": shift_delivery_date(selected_date, 1),
            "orders": orders,
        },
    )


@require_http_methods(["GET", "POST"])
def create_trip(request):
    if request.method == "GET":
        return redirect("deliveries:delivery_list")

    selected_date = parse_delivery_date(request.POST.get("trip_date"))
    raw_ids = request.POST.getlist("order_ids")
    try:
        order_ids = [int(pk) for pk in raw_ids]
    except (TypeError, ValueError):
        messages.error(request, "訂單選擇無效，請重新操作")
        return redirect("deliveries:delivery_list")

    if not order_ids:
        messages.error(request, "請至少選擇一張訂單")
        return redirect(f"{reverse('deliveries:delivery_list')}?date={selected_date.isoformat()}")

    page_orders = orders_for_delivery_date(selected_date)
    page_order_ids = {order.pk for order in page_orders}
    selected_set = set(order_ids)
    if not selected_set.issubset(page_order_ids):
        messages.error(request, "部分訂單已不在清單中，請重新整理後再試")
        return redirect(f"{reverse('deliveries:delivery_list')}?date={selected_date.isoformat()}")

    ordered_ids = [order.pk for order in page_orders if order.pk in selected_set]

    try:
        trip = create_delivery_trip(ordered_ids, trip_date=selected_date)
    except TripCreationError as exc:
        messages.error(request, str(exc))
        return redirect(f"{reverse('deliveries:delivery_list')}?date={selected_date.isoformat()}")

    return redirect("deliveries:trip_detail", trip_id=trip.pk)


@require_GET
def trip_detail(request, trip_id):
    trip = get_object_or_404(DeliveryTrip, pk=trip_id)
    ctx = trip_detail_context(trip)
    for trip_order in ctx["trip_orders"]:
        order = trip_order.sales_order
        trip_order.summary_lines = build_order_summary(order)
        trip_order.display_address = order.shipping_address or order.customer.address

    return render(request, "deliveries/trip_detail.html", ctx)
