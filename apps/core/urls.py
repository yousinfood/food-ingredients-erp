from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("search/", views.customer_search, name="customer_search"),
]
