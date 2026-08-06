from django.contrib import admin

from .models import Batch, Product, StockMovement, Warehouse


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "temperature_zone", "is_active")
    list_filter = ("temperature_zone", "is_active")
    search_fields = ("code", "name")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("sku", "name", "standard_price", "unit_cost", "category", "unit", "is_active")
    list_filter = ("category", "unit", "is_active")
    search_fields = ("sku", "name")
    fieldsets = (
        (None, {"fields": ("sku", "name", "product_kind", "category", "brand", "series", "spec")}),
        (
            "定價",
            {
                "fields": (
                    "standard_price",
                    "unit_cost",
                    "target_margin_rate",
                    "warning_margin_rate",
                    "minimum_margin_rate",
                ),
            },
        ),
        (
            "銷售與庫存",
            {
                "fields": (
                    "unit",
                    "sales_unit",
                    "net_weight_value",
                    "net_weight_unit",
                    "is_for_sale",
                    "is_sellable",
                    "can_be_raw_material",
                ),
            },
        ),
        ("其他", {"fields": ("shelf_life_days", "storage_temp_min", "storage_temp_max", "description", "is_active")}),
    )


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ("batch_no", "product", "warehouse", "quantity", "expiry_date", "status")
    list_filter = ("status", "warehouse", "expiry_date")
    search_fields = ("batch_no", "product__sku", "product__name")
    date_hierarchy = "expiry_date"


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("created_at", "batch", "movement_type", "quantity", "reference", "created_by")
    list_filter = ("movement_type", "created_at")
    search_fields = ("reference", "batch__batch_no")
    date_hierarchy = "created_at"
