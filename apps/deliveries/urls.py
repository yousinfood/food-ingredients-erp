from django.urls import path

from apps.deliveries import views

app_name = "deliveries"

urlpatterns = [
    path("", views.delivery_list, name="delivery_list"),
    path("trips/create/", views.create_trip, name="create_trip"),
    path("trips/<int:trip_id>/", views.trip_detail, name="trip_detail"),
]
