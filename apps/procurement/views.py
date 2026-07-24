from django.shortcuts import get_object_or_404, render

from .models import PurchaseOrder, Supplier


def supplier_list(request):
    suppliers = Supplier.objects.filter(is_active=True)
    return render(request, "procurement/supplier_list.html", {"suppliers": suppliers})


def purchase_order_list(request):
    orders = PurchaseOrder.objects.select_related("supplier").prefetch_related("items")
    status = request.GET.get("status")
    if status:
        orders = orders.filter(status=status)
    return render(
        request,
        "procurement/purchase_order_list.html",
        {"orders": orders, "status_filter": status},
    )


def purchase_order_detail(request, pk):
    order = get_object_or_404(
        PurchaseOrder.objects.select_related("supplier").prefetch_related("items__product"),
        pk=pk,
    )
    return render(request, "procurement/purchase_order_detail.html", {"order": order})
