import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.inventory.services.product_webhook_sync import (
    upsert_product_from_webhook,
    verify_webhook_token,
)


@csrf_exempt
@require_POST
def product_sync_webhook_api(request):
    if not verify_webhook_token(request):
        return JsonResponse({"success": False, "error": "forbidden"}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"success": False, "error": "invalid_json"}, status=400)

    try:
        result = upsert_product_from_webhook(payload)
    except ValueError as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)

    return JsonResponse(result)
