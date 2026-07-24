from django.urls import path

from . import views

app_name = "procurement"

urlpatterns = [
    path("suppliers/", views.supplier_list, name="supplier_list"),
    path("orders/", views.purchase_order_list, name="purchase_order_list"),
    path("orders/<int:pk>/", views.purchase_order_detail, name="purchase_order_detail"),
]
