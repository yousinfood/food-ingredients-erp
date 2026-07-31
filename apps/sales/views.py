from datetime import date
from decimal import Decimal, InvalidOperation
import json
import secrets

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.db.models import ProtectedError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.core.services.dashboard_order_filters import (
    DASHBOARD_FILTER_LABELS,
    queryset_for_dashboard_filter,
)
from .services.customer_sheet_push_ui import (
    delete_customer_sheet_or_warn,
    push_customer_sheet_or_warn,
)
from apps.sales.signals import resume_sheet_push, skip_sheet_push
from .forms import CustomerForm
from .models import Customer, SalesOrder, SalesOrderItem
from .services.customer_center import (
    build_customer_center,
    compute_accounts_receivable,
    get_order_history,
    get_price_history,
)
from .services.customer_search import filter_customers, get_customer_regions, search_customers_ranked
from .services.customer_order_context import build_order_page_context
from .services.nearby_recommendations import build_recommendation_row, get_recommended_nearby_customers
from .services.order_actions import (
    can_permanently_delete,
    order_lines_for_copy,
    permanently_delete_order,
    void_order,
)
from .services.order_numbers import next_order_no
from .services.product_search import product_to_dict, search_saleable_products


def customer_search(request):
    query = request.GET.get("q", "").strip()
    show_all = request.GET.get("more") == "1"
    searched = bool(query)
    search = (
        search_customers_ranked(query, show_all=show_all)
        if searched
        else None
    )
    results = search.customers if search else []
    return render(
        request,
        "sales/customer_search.html",
        {
            "query": query,
            "searched": searched,
            "results": results,
            "search_total": search.total_count if search else 0,
            "search_has_more": search.has_more if search else False,
            "search_remaining": search.remaining_count if search else 0,
            "search_show_all": show_all,
        },
    )


def customer_center(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    center = build_customer_center(customer)
    back_query = request.GET.get("q", "").strip()
    return render(
        request,
        "sales/customer_center.html",
        {"customer": customer, "center": center, "back_query": back_query},
    )


def customer_detail(request, pk):
    return customer_center(request, pk)


def order_history(request, pk):
    customer = get_object_or_404(Customer, pk=pk, is_active=True)
    orders = get_order_history(customer)
    return render(
        request,
        "sales/order_history.html",
        {"customer": customer, "orders": orders},
    )


def price_history(request, pk):
    customer = get_object_or_404(Customer, pk=pk, is_active=True)
    prices = get_price_history(customer)
    return render(
        request,
        "sales/price_history.html",
        {"customer": customer, "prices": prices},
    )


def receive_payment(request, pk):
    customer = get_object_or_404(Customer, pk=pk, is_active=True)
    balance = compute_accounts_receivable(customer)
    credit = customer.credit_limit
    return render(
        request,
        "sales/receive_payment.html",
        {
            "customer": customer,
            "current_balance": f"${balance:,.0f}" if balance else "—",
            "credit_limit": f"${credit:,.0f}" if credit else "—",
        },
    )


def customer_list(request):
    query = request.GET.get("q", "").strip()
    region = request.GET.get("region", "").strip()
    show_inactive = request.GET.get("inactive") == "1"
    customers = filter_customers(query=query, region=region, show_inactive=show_inactive)
    return render(
        request,
        "sales/customer_list.html",
        {
            "customers": customers,
            "query": query,
            "region": region,
            "regions": get_customer_regions(),
            "show_inactive": show_inactive,
        },
    )


def customer_create(request):
    form = CustomerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        skip_sheet_push()
        try:
            customer = form.save()
        finally:
            resume_sheet_push()
        push_customer_sheet_or_warn(request, customer)
        messages.success(request, f"已新增客戶 {customer.name}")
        return redirect("sales:customer_center", pk=customer.pk)
    return render(request, "sales/customer_form.html", {"form": form, "title": "新增客戶"})


def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    form = CustomerForm(request.POST or None, instance=customer)
    if request.method == "POST" and form.is_valid():
        skip_sheet_push()
        try:
            customer = form.save()
        finally:
            resume_sheet_push()
        push_customer_sheet_or_warn(request, customer)
        messages.success(request, f"已更新客戶 {customer.name}")
        return redirect("sales:customer_center", pk=customer.pk)
    return render(
        request,
        "sales/customer_form.html",
        {"form": form, "title": "編輯客戶", "customer": customer},
    )


def customer_delete(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    order_count = customer.sales_orders.count()

    if request.method == "POST":
        confirm_name = request.POST.get("confirm_name", "").strip()
        if confirm_name != customer.name:
            messages.error(request, "客戶名稱不符，無法刪除。")
            return render(
                request,
                "sales/customer_confirm_delete.html",
                {"customer": customer, "order_count": order_count},
            )
        try:
            name = customer.name
            code = customer.code
            skip_sheet_push()
            try:
                customer.delete()
            finally:
                resume_sheet_push()
            delete_customer_sheet_or_warn(request, code)
        except ProtectedError:
            messages.error(request, "此客戶有關聯訂單，無法刪除。請改為停用。")
            return redirect("sales:customer_center", pk=pk)
        messages.success(request, f"已刪除客戶 {name}")
        return redirect("sales:customer_list")

    return render(
        request,
        "sales/customer_confirm_delete.html",
        {"customer": customer, "order_count": order_count},
    )


def sales_order_list(request):
    orders = SalesOrder.objects.select_related("customer").prefetch_related("items")
    dashboard_filter = request.GET.get("dashboard", "").strip()
    dashboard_label = None
    if dashboard_filter:
        filtered = queryset_for_dashboard_filter(dashboard_filter)
        if filtered is not None:
            orders = filtered.select_related("customer").prefetch_related("items")
            dashboard_label = DASHBOARD_FILTER_LABELS.get(dashboard_filter)
    status = request.GET.get("status")
    if status and not dashboard_filter:
        orders = orders.filter(status=status)
    return render(
        request,
        "sales/sales_order_list.html",
        {
            "orders": orders,
            "status_filter": status,
            "dashboard_filter": dashboard_filter or None,
            "dashboard_label": dashboard_label,
        },
    )


def sales_order_detail(request, pk):
    order = get_object_or_404(
        SalesOrder.objects.select_related(
            "customer",
            "created_by",
            "cancelled_by",
        ).prefetch_related("items__product"),
        pk=pk,
    )
    delete_allowed, delete_reason = can_permanently_delete(order)
    return render(
        request,
        "sales/sales_order_detail.html",
        {
            "order": order,
            "debug_mode": settings.DEBUG,
            "can_permanently_delete": delete_allowed,
            "permanent_delete_reason": delete_reason,
        },
    )


@require_POST
def sales_order_void(request, pk):
    order = get_object_or_404(SalesOrder, pk=pk)
    if not order.can_void:
        messages.error(request, "此訂單狀態不可作廢")
        return redirect("sales:sales_order_detail", pk=pk)
    try:
        void_order(order, user=request.user)
        messages.success(request, f"已作廢訂單 {order.order_no}")
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect("sales:sales_order_detail", pk=pk)


@require_POST
def sales_order_permanent_delete(request, pk):
    order = get_object_or_404(SalesOrder, pk=pk)
    customer_pk = order.customer_id
    try:
        permanently_delete_order(order)
        messages.success(request, f"已永久刪除訂單（測試模式）")
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("sales:sales_order_detail", pk=pk)
    return redirect("sales:order_history", pk=customer_pk)


def sales_order_reorder(request, pk):
    order = get_object_or_404(SalesOrder.objects.select_related("customer"), pk=pk)
    url = reverse("sales:sales_order_create") + f"?customer={order.customer_id}&copy_from={order.pk}"
    return redirect(url)


def sales_order_copy(request, pk):
    return sales_order_reorder(request, pk)


def _customer_price_map(customer):
    from apps.sales.services.customer_order_context import _latest_prices_by_product

    items = (
        SalesOrderItem.objects.filter(sales_order__customer=customer)
        .exclude(sales_order__status=SalesOrder.Status.CANCELLED)
        .values_list("product_id", flat=True)
        .distinct()
    )
    product_ids = list(items)
    if not product_ids:
        return {}
    prices = _latest_prices_by_product(customer, product_ids)
    return {str(pid): str(prices.get(pid, Decimal("0"))) for pid in product_ids}


@require_GET
def product_search_api(request):
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    series = request.GET.get("series", "").strip()
    customer_id = request.GET.get("customer", "").strip()
    limit = 80 if category else 25
    products = search_saleable_products(query=query, category=category, series=series, limit=limit)
    price_map = {}
    if customer_id:
        customer = Customer.objects.filter(pk=customer_id, is_active=True).first()
        if customer:
            price_map = _customer_price_map(customer)
    results = []
    for p in products:
        item = product_to_dict(p)
        if str(p.pk) in price_map:
            item["last_unit_price"] = price_map[str(p.pk)]
        results.append(item)
    return JsonResponse({"results": results})


def _parse_decimal(value, default=Decimal("0")):
    if value is None or value == "":
        return default
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return default


def _parse_order_lines(request):
    product_ids = request.POST.getlist("item_product_id")
    quantities = request.POST.getlist("item_quantity")
    unit_prices = request.POST.getlist("item_unit_price")

    lines = []
    errors = []
    seen_products = set()

    for i, product_id in enumerate(product_ids):
        if not product_id:
            continue
        qty = _parse_decimal(quantities[i] if i < len(quantities) else "", default=Decimal("0"))
        price = _parse_decimal(unit_prices[i] if i < len(unit_prices) else "", default=Decimal("0"))
        if qty <= 0:
            continue
        try:
            pid = int(product_id)
        except (TypeError, ValueError):
            errors.append(f"第 {i + 1} 項產品無效")
            continue
        if pid in seen_products:
            errors.append("同一產品請合併數量，勿重複加入")
            continue
        seen_products.add(pid)
        lines.append({"product_id": pid, "quantity": qty, "unit_price": price})

    if not lines and not errors:
        errors.append("請至少加入一項產品並填寫數量")
    return lines, errors


def _initial_lines_from_post(request):
    from apps.inventory.models import Product

    product_ids = request.POST.getlist("item_product_id")
    quantities = request.POST.getlist("item_quantity")
    unit_prices = request.POST.getlist("item_unit_price")
    lines = []
    for i, product_id in enumerate(product_ids):
        if not product_id:
            continue
        try:
            pid = int(product_id)
        except (TypeError, ValueError):
            continue
        product = Product.objects.filter(pk=pid).first()
        if not product:
            continue
        item = product_to_dict(product)
        item["quantity"] = quantities[i] if i < len(quantities) else "1"
        item["unit_price"] = unit_prices[i] if i < len(unit_prices) else "0"
        lines.append(item)
    return lines


def _order_form_context(customer, request=None, **overrides):
    from apps.sales.services.customer_order_context import suggest_delivery_date
    from apps.sales.services.product_search import product_to_dict, search_saleable_products

    today = timezone.localdate().isoformat()
    initial_lines = overrides.get("initial_lines")
    ctx = {
        "customer": customer,
        "order_date": overrides.get("order_date", today),
        "delivery_date": overrides.get("delivery_date", suggest_delivery_date(customer).isoformat()),
        "shipping_address": overrides.get("shipping_address", customer.address or ""),
        "notes": overrides.get("notes", ""),
        "payment_method": customer.payment_method or "",
        "special_instructions": overrides.get("special_instructions", ""),
        "copy_source_order": overrides.get("copy_source_order"),
        **build_order_page_context(customer),
    }
    categories = ctx.get("product_categories") or []
    default_category = categories[0] if categories else "有信品牌粉"
    default_products = [
        product_to_dict(p)
        for p in search_saleable_products(category=default_category, limit=80)
    ]
    ctx["default_category"] = default_category
    ctx["last_order_json"] = json.dumps(ctx["last_order"], ensure_ascii=False)
    ctx["frequent_products_json"] = json.dumps(ctx["frequent_products"], ensure_ascii=False)
    ctx["initial_lines_json"] = json.dumps(initial_lines or [], ensure_ascii=False)
    ctx["default_category_products_json"] = json.dumps(default_products, ensure_ascii=False)
    saved_order = overrides.get("saved_order")
    ctx["saved_order"] = saved_order
    if saved_order:
        ctx["saved_order_json"] = json.dumps(
            {"pk": saved_order.pk, "order_no": saved_order.order_no},
            ensure_ascii=False,
        )
    else:
        ctx["saved_order_json"] = "null"
    price_map = _customer_price_map(customer)
    ctx["customer_price_map_json"] = json.dumps(price_map, ensure_ascii=False)
    saved = overrides.get("saved_order")
    if request is not None and not saved:
        nonce = request.session.get("sales_order_nonce")
        if not nonce:
            nonce = secrets.token_urlsafe(16)
            request.session["sales_order_nonce"] = nonce
        ctx["order_nonce"] = nonce
    else:
        ctx["order_nonce"] = ""
    return ctx


def _copy_lines_from_order(source_order):
    return order_lines_for_copy(source_order)


@transaction.atomic
def sales_order_create(request):
    customer = None
    customer_id = request.GET.get("customer") or request.POST.get("customer")
    if customer_id:
        customer = Customer.objects.filter(pk=customer_id, is_active=True).first()

    if request.method == "POST":
        if not customer:
            messages.error(request, "請先選擇客戶")
            return redirect("dashboard")

        session_nonce = request.session.get("sales_order_nonce")
        posted_nonce = (request.POST.get("order_nonce") or "").strip()
        if not session_nonce or posted_nonce != session_nonce:
            last_pk = request.session.get("sales_order_last_created_pk")
            last_customer = request.session.get("sales_order_last_created_customer")
            if last_pk and str(last_customer) == str(customer.pk):
                return redirect(
                    f"{reverse('sales:sales_order_create')}?customer={customer.pk}&saved={last_pk}",
                    code=303,
                )
            messages.error(request, "請勿重複送出，請重新接單")
            return redirect(
                f"{reverse('sales:sales_order_create')}?customer={customer.pk}",
                code=303,
            )

        lines, line_errors = _parse_order_lines(request)
        order_date_str = request.POST.get("order_date") or timezone.localdate().isoformat()
        delivery_date_str = request.POST.get("delivery_date", "").strip()
        if line_errors:
            for err in line_errors:
                messages.error(request, err)
            return render(
                request,
                "sales/sales_order_touch_form.html",
                _order_form_context(
                    customer,
                    request,
                    order_date=order_date_str,
                    delivery_date=delivery_date_str,
                    shipping_address=request.POST.get("shipping_address", customer.address or ""),
                    notes=request.POST.get("notes", ""),
                    special_instructions=request.POST.get("special_instructions", ""),
                    initial_lines=_initial_lines_from_post(request),
                ),
            )

        try:
            order_date = date.fromisoformat(order_date_str)
        except ValueError:
            order_date = timezone.localdate()

        delivery_date = None
        if delivery_date_str:
            try:
                delivery_date = date.fromisoformat(delivery_date_str)
            except ValueError:
                delivery_date = None

        special_instructions = request.POST.get("special_instructions", "").strip()
        notes = request.POST.get("notes", "").strip()
        if special_instructions:
            notes = f"{special_instructions}\n{notes}".strip() if notes else special_instructions

        order = SalesOrder(
            order_no=next_order_no(),
            customer=customer,
            status=SalesOrder.Status.CREATED,
            order_date=order_date,
            delivery_date=delivery_date,
            shipping_address=request.POST.get("shipping_address", customer.address or "").strip(),
            notes=notes,
        )
        if request.user.is_authenticated:
            order.created_by = request.user
        order.save()

        from apps.inventory.models import Product

        saleable_ids = set(
            Product.objects.filter(
                is_active=True,
                is_for_sale=True,
                product_kind__in=[Product.ProductKind.FINISHED, Product.ProductKind.DUAL],
            ).values_list("pk", flat=True)
        )
        for line in lines:
            if line["product_id"] not in saleable_ids:
                messages.error(request, "包含不可販售的產品，請重新選擇")
                return render(
                    request,
                    "sales/sales_order_touch_form.html",
                    _order_form_context(
                        customer,
                        request,
                        order_date=order_date_str,
                        delivery_date=delivery_date_str,
                        shipping_address=request.POST.get("shipping_address", ""),
                        notes=request.POST.get("notes", ""),
                        special_instructions=request.POST.get("special_instructions", ""),
                        initial_lines=_initial_lines_from_post(request),
                    ),
                )
            SalesOrderItem.objects.create(
                sales_order=order,
                product_id=line["product_id"],
                quantity=line["quantity"],
                unit_price=line["unit_price"],
            )

        customer.last_transaction_date = order_date
        customer.save(update_fields=["last_transaction_date"])

        request.session.pop("sales_order_nonce", None)
        request.session["sales_order_last_created_pk"] = order.pk
        request.session["sales_order_last_created_customer"] = customer.pk

        return redirect(
            f"{reverse('sales:sales_order_create')}?customer={customer.pk}&saved={order.pk}",
            code=303,
        )

    if not customer:
        messages.error(request, "請從客戶中心開始接單")
        return redirect("dashboard")

    initial_lines = []
    copy_source_order = None
    saved_order = None
    saved_id = request.GET.get("saved")
    if saved_id:
        saved_order = SalesOrder.objects.filter(pk=saved_id, customer=customer).first()

    copy_from_id = request.GET.get("copy_from")
    if copy_from_id:
        source = (
            SalesOrder.objects.filter(pk=copy_from_id, customer=customer)
            .prefetch_related("items__product")
            .first()
        )
        if source:
            initial_lines = _copy_lines_from_order(source)
            copy_source_order = source

    return render(
        request,
        "sales/sales_order_touch_form.html",
        _order_form_context(
            customer,
            request,
            initial_lines=initial_lines,
            copy_source_order=copy_source_order,
            saved_order=saved_order,
        ),
    )


def sales_order_success(request, pk):
    order = get_object_or_404(
        SalesOrder.objects.select_related("customer").prefetch_related("items__product"),
        pk=pk,
    )
    customer = order.customer
    nearby = [
        build_recommendation_row(c)
        for c in get_recommended_nearby_customers(customer, limit=8)
    ]
    return render(
        request,
        "sales/sales_order_success.html",
        {
            "order": order,
            "customer": customer,
            "nearby_recommendations": nearby,
        },
    )
