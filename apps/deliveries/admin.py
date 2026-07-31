from django.contrib import admin

from apps.deliveries.models import DeliveryTrip, DeliveryTripOrder


class DeliveryTripOrderInline(admin.TabularInline):
    model = DeliveryTripOrder
    extra = 0
    readonly_fields = ("sales_order", "sequence", "status", "created_at")


@admin.register(DeliveryTrip)
class DeliveryTripAdmin(admin.ModelAdmin):
    list_display = ("trip_code", "trip_date", "trip_number", "status", "created_at")
    list_filter = ("status", "trip_date")
    search_fields = ("trip_code",)
    inlines = [DeliveryTripOrderInline]


@admin.register(DeliveryTripOrder)
class DeliveryTripOrderAdmin(admin.ModelAdmin):
    list_display = ("delivery_trip", "sales_order", "sequence", "status")
    list_filter = ("status",)
