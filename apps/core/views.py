from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET
from urllib.parse import quote

from apps.sales.services.customer_search import search_customers_ranked

from .services.dashboard import get_dashboard_stats


def health(request):
    return HttpResponse("ok", content_type="text/plain")


def service_worker(request):
    sw_path = settings.BASE_DIR / "static" / "pwa" / "service-worker.js"
    response = HttpResponse(sw_path.read_text(encoding="utf-8"), content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache"
    return response


def _customer_search_context(query: str, show_all: bool):
    searched = bool(query)
    search = (
        search_customers_ranked(query, show_all=show_all)
        if searched
        else None
    )
    results = search.customers if search else []
    return {
        "query": query,
        "searched": searched,
        "results": results,
        "search_total": search.total_count if search else 0,
        "search_has_more": search.has_more if search else False,
        "search_remaining": search.remaining_count if search else 0,
        "search_show_all": show_all,
        "search": search,
    }


@require_GET
def customer_search_api(request):
    query = request.GET.get("q", "").strip()
    show_all = request.GET.get("more") == "1"
    ctx = _customer_search_context(query, show_all)
    search = ctx.get("search")
    if ctx["searched"] and search and search.total_count == 1:
        customer = ctx["results"][0]
        return JsonResponse(
            {
                "ok": True,
                "total": 1,
                "redirect": f"/sales/customers/{customer.pk}/?q={quote(query)}",
            }
        )
    html = render_to_string(
        "core/_customer_search_results.html",
        ctx,
        request=request,
    )
    return JsonResponse(
        {
            "ok": True,
            "total": ctx["search_total"],
            "html": html,
        }
    )


def dashboard(request):
    query = request.GET.get("q", "").strip()
    show_all = request.GET.get("more") == "1"
    ctx = _customer_search_context(query, show_all)
    search = ctx.get("search")

    if ctx["searched"] and search and search.total_count == 1:
        return redirect(f"/sales/customers/{ctx['results'][0].pk}/?q={query}")

    stats = get_dashboard_stats()

    return render(
        request,
        "core/dashboard_touch.html",
        {
            **ctx,
            **stats,
        },
    )


def customer_search(request):
    query = request.GET.get("q", "").strip()
    if not query:
        return redirect("dashboard")
    return redirect(f"/?q={query}")
