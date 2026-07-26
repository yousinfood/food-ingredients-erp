from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect, render

from apps.sales.services.customer_search import search_customers

from .services.dashboard import get_dashboard_stats


def health(request):
    return HttpResponse("ok", content_type="text/plain")


def service_worker(request):
    sw_path = settings.BASE_DIR / "static" / "pwa" / "service-worker.js"
    response = HttpResponse(sw_path.read_text(encoding="utf-8"), content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache"
    return response


def dashboard(request):
    query = request.GET.get("q", "").strip()
    searched = bool(query)
    results = list(search_customers(query=query)) if searched else []
    stats = get_dashboard_stats()

    if searched and len(results) == 1:
        return redirect(f"/sales/customers/{results[0].pk}/?q={query}")

    return render(
        request,
        "core/dashboard_touch.html",
        {
            "query": query,
            "searched": searched,
            "results": results,
            **stats,
        },
    )


def customer_search(request):
    query = request.GET.get("q", "").strip()
    if not query:
        return redirect("dashboard")
    return redirect(f"/?q={query}")
