"""Google Sheet → ERP：單筆產品 webhook upsert。"""

from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.inventory.models import Product
from apps.inventory.services.product_import import (
    PRODUCT_SHEET,
    _bool_from_sheet,
    _map_inventory_unit,
    _packaging_from_row,
    _parse_decimal,
)
from apps.sales.services.customer_webhook_sync import verify_webhook_token

__all__ = ["upsert_product_from_webhook", "verify_webhook_token"]


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


def _value_or_none(data: dict, *keys: str):
    for key in keys:
        if key in data:
            value = data.get(key)
            if value is None:
                continue
            if _norm(value) == "":
                continue
            return value
    return None


def parse_product_webhook_payload(data: dict) -> tuple[str, dict, str]:
    if not isinstance(data, dict):
        raise ValueError("JSON 必須是物件")

    sku = _first_value(data, "product_code", "sku", "code")
    if not sku:
        raise ValueError("缺少 product_code")

    name = _first_value(data, "name", "product_name")
    if not name:
        raise ValueError("缺少 name")

    spec = _first_value(data, "spec")
    unit_label = _first_value(data, "unit") or "包"
    can_be_raw = _bool_from_sheet(
        _value_or_none(data, "can_be_raw_material"),
        default=False,
    )
    packaging = _packaging_from_row(spec=spec, unit_label=unit_label)

    defaults = {
        "name": name,
        "category": _first_value(data, "category"),
        "brand": _first_value(data, "brand"),
        "series": _first_value(data, "series"),
        "spec": spec,
        "product_kind": Product.ProductKind.DUAL if can_be_raw else Product.ProductKind.FINISHED,
        "is_for_sale": _bool_from_sheet(
            _value_or_none(data, "is_for_sale"),
            default=True,
        ),
        "is_sellable": _bool_from_sheet(
            _value_or_none(data, "is_sellable"),
            default=True,
        ),
        "can_be_raw_material": can_be_raw,
        "is_active": _bool_from_sheet(
            _value_or_none(data, "is_active"),
            default=True,
        ),
        "description": _first_value(data, "notes"),
        "sales_unit": packaging["sales_unit"],
        "net_weight_value": packaging.get("net_weight_value"),
        "net_weight_unit": packaging.get("net_weight_unit", ""),
        "unit_cost": _parse_decimal(_value_or_none(data, "unit_cost")),
    }
    return sku, defaults, unit_label


def upsert_product_from_webhook(data: dict) -> dict:
    sku, defaults, unit_label = parse_product_webhook_payload(data)

    with transaction.atomic():
        existing = Product.objects.filter(sku=sku).first()
        if existing is None:
            defaults["unit"] = _map_inventory_unit(unit_label)
        _, created = Product.objects.update_or_create(sku=sku, defaults=defaults)

    return {
        "success": True,
        "product_code": sku,
        "action": "created" if created else "updated",
    }
