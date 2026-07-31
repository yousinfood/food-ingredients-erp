import json
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.db import transaction

from apps.inventory.models import Product

DEFAULT_JSON_PATH = settings.BASE_DIR / "staging_products.json"

SAFE_UPDATE_FIELDS = (
    "name",
    "product_kind",
    "category",
    "brand",
    "series",
    "spec",
    "unit",
    "sales_unit",
    "net_weight_value",
    "net_weight_unit",
    "is_for_sale",
    "is_sellable",
    "can_be_raw_material",
    "unit_cost",
    "shelf_life_days",
    "storage_temp_min",
    "storage_temp_max",
    "description",
    "is_active",
)

CREATE_FIELD_NAMES = SAFE_UPDATE_FIELDS + ("sku",)


@dataclass
class UpsertResult:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


def _parse_decimal(value):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _coerce_field(name, value):
    if name in ("is_for_sale", "is_sellable", "can_be_raw_material", "is_active"):
        return bool(value)
    if name == "shelf_life_days":
        if value in (None, ""):
            return 365
        try:
            return int(value)
        except (TypeError, ValueError):
            return 365
    if name in (
        "net_weight_value",
        "unit_cost",
        "storage_temp_min",
        "storage_temp_max",
    ):
        return _parse_decimal(value)
    if value is None:
        if name in ("category", "brand", "series", "spec", "description", "net_weight_unit"):
            return ""
        return value
    return value


def _build_create_kwargs(fields, *, sku: str):
    kwargs = {"sku": sku}
    for name in CREATE_FIELD_NAMES:
        if name == "sku":
            continue
        if name not in fields:
            continue
        kwargs[name] = _coerce_field(name, fields[name])
    if "name" not in kwargs or not str(kwargs.get("name") or "").strip():
        kwargs["name"] = sku
    return kwargs


def _safe_update_values(fields):
    return {name: _coerce_field(name, fields.get(name)) for name in SAFE_UPDATE_FIELDS}


def load_product_records(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ValueError("JSON 根節點必須是陣列（Django dumpdata 格式）")
    return payload


def upsert_products_from_json(path: Path, *, dry_run: bool = False) -> UpsertResult:
    records = load_product_records(path)
    result = UpsertResult()

    with transaction.atomic():
        for index, record in enumerate(records, start=1):
            if record.get("model") != "inventory.product":
                result.skipped += 1
                continue

            fields = record.get("fields") or {}
            sku = str(fields.get("sku") or "").strip()
            if not sku:
                result.errors.append(f"第 {index} 筆缺少料號 (sku)，已略過")
                result.skipped += 1
                continue

            existing = Product.objects.filter(sku=sku).first()
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
                        existing.save(update_fields=changed_fields + ["updated_at"])
                    result.updated += 1
                else:
                    result.unchanged += 1
                continue

            create_kwargs = _build_create_kwargs(fields, sku=sku)
            if not dry_run:
                Product.objects.create(**create_kwargs)
            result.created += 1

        if dry_run:
            transaction.set_rollback(True)

    return result
