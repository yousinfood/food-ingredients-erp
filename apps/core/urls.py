from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("sw.js", views.service_worker, name="service_worker"),
    path("api/customers/search/", views.customer_search_api, name="customer_search_api"),
    path("api/dashboard/orders/", views.dashboard_orders_api, name="dashboard_orders_api"),
    path("", views.dashboard, name="dashboard"),
    path("search/", views.customer_search, name="customer_search"),
]
