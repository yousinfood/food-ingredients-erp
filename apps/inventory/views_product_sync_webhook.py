import json
import logging

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.inventory.services.product_webhook_sync import (
    upsert_product_from_webhook,
    verify_webhook_token,
)

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def product_sync_webhook_api(request):
    if not verify_webhook_token(request):
        logger.warning("Product webhook rejected: invalid token")
        return JsonResponse({"success": False, "error": "forbidden"}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        logger.warning("Product webhook rejected: invalid JSON")
        return JsonResponse({"success": False, "error": "invalid_json"}, status=400)

    logger.info(
        "Product webhook received: product_code=%r sku=%r name=%r",
        payload.get("product_code"),
        payload.get("sku"),
        payload.get("name"),
    )

    try:
        result = upsert_product_from_webhook(payload)
    except ValueError as exc:
        logger.warning("Product webhook rejected: %s", exc)
        return JsonResponse({"success": False, "error": str(exc)}, status=400)
    except Exception:
        logger.exception(
            "Product webhook failed: product_code=%r",
            payload.get("product_code") or payload.get("sku"),
        )
        raise

    logger.info(
        "Product webhook response: product_code=%r action=%s product_id=%s",
        result.get("product_code"),
        result.get("action"),
        result.get("product_id"),
    )
    return JsonResponse(result)
