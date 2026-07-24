from django.contrib import messages
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import ProductForm
from .models import Batch, Product, Warehouse


def product_list(request):
    products = Product.objects.all().annotate(total_qty=Sum("batches__quantity"))
    query = request.GET.get("q", "").strip()
    if query:
        products = products.filter(Q(name__icontains=query) | Q(sku__icontains=query))
    show_inactive = request.GET.get("inactive") == "1"
    if not show_inactive:
        products = products.filter(is_active=True)
    return render(
        request,
        "inventory/product_list.html",
        {"products": products, "query": query, "show_inactive": show_inactive},
    )


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    batches = product.batches.select_related("warehouse").order_by("expiry_date")
    return render(request, "inventory/product_detail.html", {"product": product, "batches": batches})


def product_create(request):
    form = ProductForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        product = form.save()
        messages.success(request, f"已新增產品 {product.name}")
        return redirect("inventory:product_detail", pk=product.pk)
    return render(request, "inventory/product_form.html", {"form": form, "title": "新增產品"})


def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    form = ProductForm(request.POST or None, instance=product)
    if request.method == "POST" and form.is_valid():
        product = form.save()
        messages.success(request, f"已更新產品 {product.name}")
        return redirect("inventory:product_detail", pk=product.pk)
    return render(
        request,
        "inventory/product_form.html",
        {"form": form, "title": "編輯產品", "product": product},
    )


def batch_list(request):
    today = timezone.localdate()
    batches = Batch.objects.select_related("product", "warehouse").filter(quantity__gt=0)

    status_filter = request.GET.get("status")
    if status_filter == "expiring":
        batches = batches.filter(
            expiry_date__gte=today,
            expiry_date__lte=today + timezone.timedelta(days=30),
        )
    elif status_filter == "expired":
        batches = batches.filter(expiry_date__lt=today)

    return render(request, "inventory/batch_list.html", {"batches": batches, "status_filter": status_filter})


def warehouse_list(request):
    warehouses = Warehouse.objects.filter(is_active=True).annotate(
        batch_count=Sum("batches__quantity")
    )
    return render(request, "inventory/warehouse_list.html", {"warehouses": warehouses})
