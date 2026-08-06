from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("sw.js", views.service_worker, name="service_worker"),
    path("api/customers/search/", views.customer_search_api, name="customer_search_api"),
    path("api/customers/revision/", views.customer_search_revision_api, name="customer_search_revision_api"),
    path("api/customers/events/", views.customer_search_events_api, name="customer_search_events_api"),
    path("api/voice/transcribe/", views.voice_transcribe_api, name="voice_transcribe_api"),
    path("api/voice/ts-log/", views.voice_ts_log_api, name="voice_ts_log_api"),
    path("api/debug/audio/", views.debug_audio_api, name="debug_audio_api"),
    path("api/dashboard/orders/", views.dashboard_orders_api, name="dashboard_orders_api"),
    path("voice-test/", views.voice_test, name="voice_test"),
    path("", views.dashboard, name="dashboard"),
    path("search/", views.customer_search, name="customer_search"),
]
