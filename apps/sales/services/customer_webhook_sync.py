"""Google Sheet → ERP：單筆客戶 webhook upsert。"""

from __future__ import annotations

import secrets
from typing import Any

from django.conf import settings
from django.db import transaction

from apps.sales.models import Customer
from apps.sales.services.customer_sheet_rows import (
    _parse_date,
    _parse_decimal,
    _parse_int,
    customer_defaults_from_record,
)
from apps.sales.signals import resume_sheet_push, skip_sheet_push


def _norm(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _first_value(data: dict, *keys: str) -> str:
    for key in keys:
        if key in data:
            text = _norm(data.get(key))
            if text:
                return text
    return ""


def _optional_bool(value: Any, *, default: bool = True) -> bool:
    if value is None or _norm(value) == "":
        return default
    if isinstance(value, bool):
        return value
    text = _norm(value).lower()
    if text in {"0", "false", "no", "n", "否"}:
        return False
    if text in {"1", "true", "yes", "y", "是"}:
        return True
    return default


def extract_webhook_token(request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    header_token = request.headers.get("X-Webhook-Token", "")
    if header_token:
        return header_token.strip()
    return _norm(request.headers.get("X-Google-Sheet-Webhook-Token"))


def verify_webhook_token(request) -> bool:
    expected = settings.GOOGLE_SHEET_WEBHOOK_TOKEN
    if not expected:
        return False
    provided = extract_webhook_token(request)
    if not provided:
        return False
    return secrets.compare_digest(provided, expected)


def parse_customer_webhook_payload(data: dict) -> tuple[str, dict]:
    if not isinstance(data, dict):
        raise ValueError("JSON 必須是物件")

    code = _first_value(data, "customer_code", "code")
    if not code:
        raise ValueError("缺少 customer_code")

    name = _first_value(data, "name", "customer_name")
    if not name:
        raise ValueError("缺少 name")

    record = {
        "code": code,
        "name": name,
        "region": _first_value(data, "region"),
        "contact_person": _first_value(data, "contact_person", "contact_name"),
        "phone": _first_value(data, "phone", "phone_1"),
        "phone_2": _first_value(data, "phone_2"),
        "phone_3": _first_value(data, "phone_3"),
        "address": _first_value(data, "address"),
        "invoice_address": _first_value(data, "invoice_address"),
        "map_location": _first_value(data, "map_location"),
        "line_id": _first_value(data, "line_id", "line"),
        "payment_method": _first_value(data, "payment_method"),
        "delivery_day": _first_value(data, "delivery_day"),
        "delivery_sequence": _parse_int(data.get("delivery_sequence")),
        "credit_limit": _parse_decimal(data.get("credit_limit")),
        "last_transaction_date": _parse_date(data.get("last_transaction_date")),
        "notes": _first_value(data, "notes"),
    }
    defaults = customer_defaults_from_record(record)
    defaults["is_active"] = _optional_bool(data.get("is_active"), default=True)

    for field in ("email", "tax_id", "voice_aliases"):
        if field in data:
            defaults[field] = _norm(data.get(field))

    return code, defaults


def upsert_customer_from_webhook(data: dict) -> dict:
    code, defaults = parse_customer_webhook_payload(data)
    skip_sheet_push()
    try:
        with transaction.atomic():
            _, created = Customer.objects.update_or_create(code=code, defaults=defaults)
    finally:
        resume_sheet_push()

    return {
        "success": True,
        "customer_code": code,
        "action": "created" if created else "updated",
    }
