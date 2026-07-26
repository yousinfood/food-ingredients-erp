from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("sw.js", views.service_worker, name="service_worker"),
    path("", views.dashboard, name="dashboard"),
    path("search/", views.customer_search, name="customer_search"),
]
