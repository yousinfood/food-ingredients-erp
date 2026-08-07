from django.conf import settings

ERP_NAV = [
    {"label": "儀表板", "url_name": "dashboard", "icon": "📊"},
    {"label": "客戶管理", "url_name": "sales:customer_list", "icon": "👥"},
    {"label": "客戶售價", "url_name": "sales:customer_product_price_list", "icon": "💲"},
    {"label": "產品管理", "url_name": "inventory:product_list", "icon": "📦"},
    {"label": "銷售訂單", "url_name": "sales:sales_order_list", "icon": "🧾"},
]


def erp_nav(request):
    return {
        "erp_nav": ERP_NAV,
        "customer_search_timeout_ms": settings.CUSTOMER_SEARCH_TIMEOUT_MS,
    }
