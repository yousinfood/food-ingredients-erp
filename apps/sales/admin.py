from django.contrib import admin

from .models import Customer, SalesOrder, SalesOrderItem


class SalesOrderItemInline(admin.TabularInline):
    model = SalesOrderItem
    extra = 1


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
