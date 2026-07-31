"""Google Sheet「客戶資料」列格式 ↔ sales.Customer。"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from apps.sales.models import Customer
from apps.sales.services.phase1_import import CUSTOMER_HEADERS, CUSTOMER_SHEET

COLUMN_COUNT = len(CUSTOMER_HEADERS)

FIELD_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "code": ("客戶編號", "客戶代碼", "code"),
    "region": ("區域", "district", "region"),
    "name": ("客戶名稱", "公司名稱", "name"),
    "contact_person": ("聯絡人", "contact_name", "contact_person"),
    "address": ("配送地址", "地址", "address"),
    "invoice_address": ("發票地址", "invoice_address"),
    "map_location": ("📍", "地圖", "map_location"),
    "line_id": ("🟩line", "line", "line_id"),
    "payment_method": ("付款方式", "payment_method"),
    "delivery_day": ("固定配送日", "delivery_day"),
    "delivery_sequence": ("配送順序", "delivery_sequence"),
    "credit_limit": ("信用額度", "credit_limit"),
    "last_transaction_date": ("最後交易日", "last_transaction_date"),
    "notes": ("備註", "notes"),
}


def _norm(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_header(value) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _parse_decimal(value) -> Decimal | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


def _parse_int(value) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return None


def _parse_date(value) -> date | None:
    if value is None or str(value).strip() == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip().replace("-", "/")
    for fmt in ("%Y/%m/%d", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _format_date(value: date | None) -> str:
    if not value:
        return ""
    return value.strftime("%Y/%m/%d")


def _format_decimal(value: Decimal | None) -> str:
    if value is None:
        return ""
    return format(value, "f")


def _cell_value(row: list, index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    return _norm(row[index]) or ""


def build_customer_column_map(headers: list) -> tuple[dict[str, int], list[int], list[str]]:
    normalized = [_normalize_header(header) for header in headers]
    column_map: dict[str, int] = {}
    errors: list[str] = []

    for field_name, aliases in FIELD_COLUMN_ALIASES.items():
        for alias in aliases:
            alias_key = alias.strip().lower()
            if alias_key in normalized:
                column_map[field_name] = normalized.index(alias_key)
                break

    phone_columns: list[int] = []
    for index, header in enumerate(normalized):
        if header in {"📞", "電話", "phone", "tel", "mobile"}:
            phone_columns.append(index)

    if "code" not in column_map:
        errors.append(f"「{CUSTOMER_SHEET}」缺少欄位：客戶編號")
    if "name" not in column_map:
        errors.append(f"「{CUSTOMER_SHEET}」缺少欄位：客戶名稱")

    return column_map, phone_columns, errors


def customer_to_sheet_row(customer: Customer) -> list:
    return [
        customer.code,
        customer.region or "",
        customer.name,
        customer.contact_person or "",
        customer.phone or "",
        customer.phone_2 or "",
        customer.phone_3 or "",
        customer.address or "",
        customer.invoice_address or "",
        customer.map_location or "",
        customer.line_id or "",
        customer.payment_method or "",
        customer.delivery_day or "",
        customer.delivery_sequence if customer.delivery_sequence is not None else "",
        _format_decimal(customer.credit_limit),
        _format_date(customer.last_transaction_date),
        customer.notes or "",
    ]


def parse_customer_sheet_rows(rows: list[list]) -> tuple[list[dict], list[str]]:
    if not rows:
        return [], [f"「{CUSTOMER_SHEET}」工作表為空"]

    headers = list(rows[0])
    column_map, phone_columns, errors = build_customer_column_map(headers)
    if "code" not in column_map or "name" not in column_map:
        return [], errors

    records: list[dict] = []
    seen_codes: set[str] = set()

    for row_number, raw_row in enumerate(rows[1:], start=2):
        cells = list(raw_row)
        code = _cell_value(cells, column_map.get("code"))
        name = _cell_value(cells, column_map.get("name"))
        if not code and not name:
            continue
        if not code:
            errors.append(f"第 {row_number} 列：缺少客戶編號")
            continue
        if not name:
            errors.append(f"第 {row_number} 列：缺少客戶名稱")
            continue
        if code in seen_codes:
            errors.append(f"第 {row_number} 列：客戶編號 {code} 重複")
            continue
        seen_codes.add(code)

        phones = [_cell_value(cells, index) for index in phone_columns]
        phones = [phone for phone in phones if phone]

        records.append(
            {
                "code": code,
                "name": name,
                "region": _cell_value(cells, column_map.get("region")),
                "contact_person": _cell_value(cells, column_map.get("contact_person")),
                "phone": phones[0] if len(phones) > 0 else "",
                "phone_2": phones[1] if len(phones) > 1 else "",
                "phone_3": phones[2] if len(phones) > 2 else "",
                "address": _cell_value(cells, column_map.get("address")),
                "invoice_address": _cell_value(cells, column_map.get("invoice_address")),
                "map_location": _cell_value(cells, column_map.get("map_location")),
                "line_id": _cell_value(cells, column_map.get("line_id")),
                "payment_method": _cell_value(cells, column_map.get("payment_method")),
                "delivery_day": _cell_value(cells, column_map.get("delivery_day")),
                "delivery_sequence": _parse_int(
                    cells[column_map["delivery_sequence"]]
                    if "delivery_sequence" in column_map and column_map["delivery_sequence"] < len(cells)
                    else None
                ),
                "credit_limit": _parse_decimal(
                    cells[column_map["credit_limit"]]
                    if "credit_limit" in column_map and column_map["credit_limit"] < len(cells)
                    else None
                ),
                "last_transaction_date": _parse_date(
                    cells[column_map["last_transaction_date"]]
                    if "last_transaction_date" in column_map
                    and column_map["last_transaction_date"] < len(cells)
                    else None
                ),
                "notes": _cell_value(cells, column_map.get("notes")),
            }
        )

    return records, errors


def customer_defaults_from_record(record: dict) -> dict:
    return {
        "name": record["name"],
        "region": record["region"],
        "contact_person": record["contact_person"],
        "phone": record["phone"],
        "phone_2": record["phone_2"],
        "phone_3": record["phone_3"],
        "address": record["address"],
        "invoice_address": record["invoice_address"],
        "map_location": record["map_location"],
        "line_id": record["line_id"],
        "payment_method": record["payment_method"],
        "delivery_day": record["delivery_day"],
        "delivery_sequence": record["delivery_sequence"],
        "credit_limit": record["credit_limit"],
        "last_transaction_date": record["last_transaction_date"],
        "notes": record["notes"],
        "is_active": True,
    }
