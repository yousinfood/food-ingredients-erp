from django.urls import path

from . import views

app_name = "production"

urlpatterns = [
    path("recipes/", views.recipe_list, name="recipe_list"),
    path("recipes/<int:pk>/", views.recipe_detail, name="recipe_detail"),
    path("orders/", views.production_order_list, name="production_order_list"),
    path("orders/<int:pk>/", views.production_order_detail, name="production_order_detail"),
]
