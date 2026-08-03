from django.contrib import admin

from .models import Customer, CustomerSheetSyncLog, SalesOrder, SalesOrderItem


class SalesOrderItemInline(admin.TabularInline):
    model = SalesOrderItem
    extra = 1


@admin.register(CustomerSheetSyncLog)
class CustomerSheetSyncLogAdmin(admin.ModelAdmin):
    list_display = (
        "synced_at",
        "triggered_by",
        "ok",
        "created_count",
        "updated_count",
        "skipped_count",
        "error_count",
    )
    list_filter = ("ok", "triggered_by")
    readonly_fields = (
        "synced_at",
        "triggered_by",
        "ok",
        "created_count",
        "updated_count",
        "skipped_count",
        "error_count",
        "error_details",
        "message",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "contact_person", "phone", "tax_id", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name", "contact_person", "tax_id")


@admin.register(SalesOrder)
class SalesOrderAdmin(admin.ModelAdmin):
    list_display = ("order_no", "customer", "status", "order_date", "delivery_date")
    list_filter = ("status", "order_date")
    search_fields = ("order_no", "customer__name")
    inlines = [SalesOrderItemInline]
    date_hierarchy = "order_date"
