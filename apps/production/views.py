from django.shortcuts import get_object_or_404, render

from .models import ProductionOrder, Recipe


def recipe_list(request):
    recipes = Recipe.objects.filter(is_active=True).select_related("output_product").prefetch_related("items")
    return render(request, "production/recipe_list.html", {"recipes": recipes})


def recipe_detail(request, pk):
    recipe = get_object_or_404(
        Recipe.objects.select_related("output_product").prefetch_related("items__ingredient"),
        pk=pk,
    )
    return render(request, "production/recipe_detail.html", {"recipe": recipe})


def production_order_list(request):
    orders = ProductionOrder.objects.select_related("recipe").prefetch_related("recipe__output_product")
    status = request.GET.get("status")
    if status:
        orders = orders.filter(status=status)
    return render(
        request,
        "production/production_order_list.html",
        {"orders": orders, "status_filter": status},
    )


def production_order_detail(request, pk):
    order = get_object_or_404(
        ProductionOrder.objects.select_related("recipe__output_product").prefetch_related(
            "recipe__items__ingredient"
        ),
        pk=pk,
    )
    return render(request, "production/production_order_detail.html", {"order": order})
