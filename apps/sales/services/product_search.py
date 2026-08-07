from django.db.models import Q

from apps.inventory.models import Product


def saleable_products_queryset():
    return Product.objects.filter(
        is_active=True,
        is_for_sale=True,
        product_kind__in=[Product.ProductKind.FINISHED, Product.ProductKind.DUAL],
    ).order_by("sku")


def get_saleable_categories():
    preferred = ["有信品牌粉", "麵粉", "天然澱粉", "變性澱粉", "糖"]
    found = set(
        saleable_products_queryset()
        .exclude(category="")
        .values_list("category", flat=True)
        .distinct()
    )
    ordered = [c for c in preferred if c in found]
    ordered.extend(sorted(found - set(ordered)))
    return ordered


FLOUR_SERIES = ["低筋", "中筋", "高筋", "油條"]


def search_saleable_products(*, query="", category="", series="", limit=20):
    qs = saleable_products_queryset()
    category = category.strip()
    if category:
        qs = qs.filter(category=category)
    series = series.strip()
    if series:
        qs = qs.filter(series=series)
    q = query.strip()
    if q:
        qs = qs.filter(Q(sku__icontains=q) | Q(name__icontains=q) | Q(category__icontains=q))
    return list(qs[:limit])


def product_to_dict(product):
    return {
        "id": product.pk,
        "sku": product.sku,
        "name": product.name,
        "category": product.category or "",
        "series": product.series or "",
        "unit": product.sales_unit,
        "unit_label": product.packaging_display or product.get_sales_unit_display(),
        "sales_unit_label": product.get_sales_unit_display(),
        "packaging_label": product.packaging_display,
        "spec": product.spec or "",
        "is_sellable": product.is_sellable,
    }
