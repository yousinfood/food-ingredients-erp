from django.urls import path

from . import views

app_name = "sales"

urlpatterns = [
    path("customers/", views.customer_list, name="customer_list"),
    path("customers/new/", views.customer_create, name="customer_create"),
    path("customers/<int:pk>/", views.customer_center, name="customer_center"),
    path("customers/<int:pk>/detail/", views.customer_detail, name="customer_detail"),
    path("customers/<int:pk>/edit/", views.customer_edit, name="customer_edit"),
    path("customers/<int:pk>/delete/", views.customer_delete, name="customer_delete"),
    path("customers/<int:pk>/orders/", views.order_history, name="order_history"),
    path("customers/<int:pk>/prices/", views.price_history, name="price_history"),
    path("customers/<int:pk>/payment/", views.receive_payment, name="receive_payment"),
    path("orders/", views.sales_order_list, name="sales_order_list"),
    path("orders/new/", views.sales_order_create, name="sales_order_create"),
    path("orders/<int:pk>/", views.sales_order_detail, name="sales_order_detail"),
    path("orders/<int:pk>/void/", views.sales_order_void, name="sales_order_void"),
    path("orders/<int:pk>/delete/", views.sales_order_permanent_delete, name="sales_order_permanent_delete"),
    path("orders/<int:pk>/reorder/", views.sales_order_reorder, name="sales_order_reorder"),
    path("orders/<int:pk>/copy/", views.sales_order_copy, name="sales_order_copy"),
    path("orders/<int:pk>/success/", views.sales_order_success, name="sales_order_success"),
    path("products/search/", views.product_search_api, name="product_search_api"),
    path("api/pricing/resolve/", views.pricing_resolve_api, name="pricing_resolve_api"),
    path("pricing/", views.customer_product_price_list, name="customer_product_price_list"),
    path("pricing/new/", views.customer_product_price_create, name="customer_product_price_create"),
    path("pricing/<int:pk>/deactivate/", views.customer_product_price_deactivate, name="customer_product_price_deactivate"),
]
