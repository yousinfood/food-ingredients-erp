from django.contrib import admin

from .models import GoodsReceipt, PurchaseOrder, PurchaseOrderItem, Supplier


class PurchaseOrderItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 1


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "contact_person", "phone", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name", "contact_person")


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ("order_no", "supplier", "status", "order_date", "expected_date")
    list_filter = ("status", "order_date")
    search_fields = ("order_no", "supplier__name")
    inlines = [PurchaseOrderItemInline]
    date_hierarchy = "order_date"


@admin.register(GoodsReceipt)
class GoodsReceiptAdmin(admin.ModelAdmin):
    list_display = ("receipt_no", "purchase_order", "received_date", "received_by")
    list_filter = ("received_date",)
    search_fields = ("receipt_no", "purchase_order__order_no")
    date_hierarchy = "received_date"
