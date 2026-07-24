from django.contrib import admin

from .models import ProductionOrder, Recipe, RecipeItem


class RecipeItemInline(admin.TabularInline):
    model = RecipeItem
    extra = 2


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "output_product", "output_qty", "version", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")
    inlines = [RecipeItemInline]


@admin.register(ProductionOrder)
class ProductionOrderAdmin(admin.ModelAdmin):
    list_display = ("order_no", "recipe", "planned_qty", "actual_qty", "status", "planned_start")
    list_filter = ("status", "planned_start")
    search_fields = ("order_no", "batch_no", "recipe__name")
    date_hierarchy = "planned_start"
