from __future__ import annotations

import logging
from urllib.parse import quote

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from apps.sales.services.customer_search import search_customers_ranked, search_customers_voice
from apps.sales.services.voice_search_normalize import normalize_voice_query

from .services.dashboard import get_dashboard_stats
from .services.dashboard_order_filters import (
    DASHBOARD_FILTER_LABELS,
    queryset_for_dashboard_filter,
)
from .services.voice_transcribe import (
    VOICE_UNCLEAR_MESSAGE,
    VoiceTranscribeError,
    transcribe_audio_upload,
)


logger = logging.getLogger(__name__)


def health(request):
    return HttpResponse("ok", content_type="text/plain")


def service_worker(request):
    sw_path = settings.BASE_DIR / "static" / "pwa" / "service-worker.js"
    response = HttpResponse(sw_path.read_text(encoding="utf-8"), content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache"
    return response


def _customer_search_context(
    query: str,
    show_all: bool,
    *,
    voice: bool = False,
    voice_alts: list[str] | None = None,
):
    searched = bool(query or (voice and voice_alts))
    search = None
    if searched:
        if voice:
            candidates = [query] + [alt for alt in (voice_alts or []) if alt]
            search = search_customers_voice(candidates)
        else:
            search = search_customers_ranked(query, show_all=show_all, voice=False)
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
    home = request.GET.get("home") == "1"
    voice = request.GET.get("voice") == "1"
    voice_alts = [alt.strip() for alt in request.GET.getlist("alt") if alt.strip()]
    ctx = _customer_search_context(query, show_all, voice=voice, voice_alts=voice_alts)
    search = ctx.get("search")
    if (
        not home
        and ctx["searched"]
        and search
        and search.total_count == 1
    ):
        customer = ctx["results"][0]
        return JsonResponse(
            {
                "ok": True,
                "total": 1,
                "redirect": f"/sales/customers/{customer.pk}/?q={quote(query)}",
            }
        )
    template_name = (
        "core/_customer_search_results_home.html"
        if home
        else "core/_customer_search_results.html"
    )
    html = render_to_string(
        template_name,
        ctx,
        request=request,
    )
    return JsonResponse(
        {
            "ok": True,
            "total": ctx["search_total"],
            "html": html,
            "normalized_q": normalize_voice_query(query) if voice else "",
        }
    )


@require_POST
def voice_transcribe_api(request):
    user_agent = request.META.get("HTTP_USER_AGENT", "")
    uploaded = request.FILES.get("audio")
    if not uploaded:
        logger.warning("voice_transcribe missing_audio user_agent=%r", user_agent)
        return JsonResponse({"ok": False, "error": "沒有收到語音", "text": ""}, status=400)

    mime_type = getattr(uploaded, "content_type", "") or ""
    file_size = uploaded.size
    logger.info(
        "voice_transcribe request user_agent=%r mime_type=%r audio_file_size=%s",
        user_agent,
        mime_type,
        file_size,
    )

    try:
        text = transcribe_audio_upload(uploaded, user_agent=user_agent)
    except VoiceTranscribeError as exc:
        message = str(exc)
        logger.warning(
            "voice_transcribe failed user_agent=%r mime_type=%r audio_file_size=%s error=%r",
            user_agent,
            mime_type,
            file_size,
            message,
        )
        if message == VOICE_UNCLEAR_MESSAGE:
            return JsonResponse({"ok": False, "error": message, "text": ""})
        return JsonResponse({"ok": False, "error": message, "text": ""}, status=400)
    except Exception as exc:
        logger.warning(
            "voice_transcribe unexpected_error user_agent=%r mime_type=%r audio_file_size=%s error=%s",
            user_agent,
            mime_type,
            file_size,
            exc,
            exc_info=True,
        )
        return JsonResponse(
            {"ok": False, "error": "語音辨識暫時無法使用", "text": ""},
            status=500,
        )
    return JsonResponse({"ok": True, "text": text})


@require_GET
def dashboard_orders_api(request):
    filter_key = request.GET.get("dashboard", "").strip()
    qs = queryset_for_dashboard_filter(filter_key)
    if qs is None:
        return JsonResponse({"ok": False, "error": "無效的篩選"}, status=400)
    orders = qs.select_related("customer").order_by("-order_date", "-created_at")[:200]
    total = qs.count()
    html = render_to_string(
        "core/_dashboard_order_list.html",
        {"orders": orders, "dashboard_filter": filter_key},
        request=request,
    )
    return JsonResponse(
        {
            "ok": True,
            "total": total,
            "label": DASHBOARD_FILTER_LABELS.get(filter_key, ""),
            "html": html,
        }
    )


@ensure_csrf_cookie
def voice_test(request):
    return render(request, "core/voice_test.html")


@ensure_csrf_cookie
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
