import re
from decimal import Decimal, InvalidOperation

SPEC_PATTERN = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>g|kg)\s*/?\s*(?:1\s*)?(?P<sales>包|罐|袋|箱)?",
    re.IGNORECASE,
)

SALES_UNIT_FROM_LABEL = {
    "包": "pack",
    "罐": "can",
    "袋": "bag",
    "箱": "box",
}


def parse_packaging_spec(spec: str | None) -> dict:
    """Parse legacy spec text such as '20kg/1包' into structured packaging."""
    text = (spec or "").strip()
    if not text:
        return {}

    match = SPEC_PATTERN.search(text.replace("／", "/"))
    if not match:
        return {}

    result = {
        "net_weight_value": Decimal(match.group("value")),
        "net_weight_unit": match.group("unit").lower(),
    }
    sales_label = match.group("sales")
    if sales_label:
        result["sales_unit"] = SALES_UNIT_FROM_LABEL.get(sales_label, "pack")
    return result


def format_net_weight(value, unit: str) -> str:
    if value is None or not unit:
        return ""
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return ""
    if number == number.to_integral_value():
        number = int(number)
    return f"{number}{unit}"


def format_packaging(*, net_weight_value, net_weight_unit, sales_unit_label: str) -> str:
    weight = format_net_weight(net_weight_value, net_weight_unit)
    if weight and sales_unit_label:
        return f"{weight}／{sales_unit_label}"
    return sales_unit_label or ""
