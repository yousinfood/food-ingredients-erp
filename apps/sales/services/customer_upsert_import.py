import json
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.db import transaction

from apps.sales.models import Customer

DEFAULT_JSON_PATH = settings.BASE_DIR / "staging_customers.json"

SAFE_UPDATE_FIELDS = ("name", "phone", "phone_2", "phone_3", "address", "is_active")

CREATE_FIELD_NAMES = (
    "code",
    "name",
    "region",
    "contact_person",
    "phone",
    "phone_2",
    "phone_3",
    "email",
    "address",
    "invoice_address",
    "map_location",
    "line_id",
    "payment_method",
    "delivery_day",
    "delivery_sequence",
    "credit_limit",
    "last_transaction_date",
    "tax_id",
    "is_active",
    "notes",
)


@dataclass
class UpsertResult:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


def _parse_date(value):
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        return None


def _parse_decimal(value):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _coerce_field(name, value):
    if name == "is_active":
        return bool(value)
    if name == "delivery_sequence":
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    if name == "credit_limit":
        return _parse_decimal(value)
    if name == "last_transaction_date":
        return _parse_date(value)
    if value is None:
        return ""
    return value


def _build_create_kwargs(fields):
    kwargs = {}
    for name in CREATE_FIELD_NAMES:
        if name not in fields:
            continue
        kwargs[name] = _coerce_field(name, fields[name])
    return kwargs


def _safe_update_values(fields):
    return {name: _coerce_field(name, fields.get(name)) for name in SAFE_UPDATE_FIELDS}


def load_customer_records(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ValueError("JSON 根節點必須是陣列（Django dumpdata 格式）")
    return payload


def upsert_customers_from_json(path: Path, *, dry_run: bool = False) -> UpsertResult:
    records = load_customer_records(path)
    result = UpsertResult()

    with transaction.atomic():
        for index, record in enumerate(records, start=1):
            if record.get("model") != "sales.customer":
                result.skipped += 1
                continue

            fields = record.get("fields") or {}
            code = str(fields.get("code") or "").strip()
            if not code:
                result.errors.append(f"第 {index} 筆缺少客戶代碼，已略過")
                result.skipped += 1
                continue

            existing = Customer.objects.filter(code=code).first()
            if existing:
                new_values = _safe_update_values(fields)
                changed_fields = []
                for name, new_value in new_values.items():
                    if getattr(existing, name) != new_value:
                        changed_fields.append(name)
                        if not dry_run:
                            setattr(existing, name, new_value)
                if changed_fields:
                    if not dry_run:
                        existing.save(update_fields=changed_fields)
                    result.updated += 1
                else:
                    result.unchanged += 1
                continue

            create_kwargs = _build_create_kwargs(fields)
            create_kwargs["code"] = code
            if not create_kwargs.get("name"):
                result.errors.append(f"{code} 缺少客戶名稱，已略過")
                result.skipped += 1
                continue

            if not dry_run:
                Customer.objects.create(**create_kwargs)
            result.created += 1

        if dry_run:
            transaction.set_rollback(True)

    return result
