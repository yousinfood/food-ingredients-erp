from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "食品原料 ERP 管理後台"
admin.site.site_title = "食品原料 ERP"
admin.site.index_title = "系統管理"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),
    path("inventory/", include("apps.inventory.urls")),
    path("procurement/", include("apps.procurement.urls")),
    path("sales/", include("apps.sales.urls")),
    path("production/", include("apps.production.urls")),
]
