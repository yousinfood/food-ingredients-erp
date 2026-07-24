from urllib.parse import quote


def phone_tel_href(number: str | None) -> str | None:
    if not number or number.strip() in ("—", "-"):
        return None
    digits = "".join(ch for ch in number if ch.isdigit() or ch == "+")
    return f"tel:{digits}" if digits else None


def primary_phone_href(customer) -> str | None:
    for number in (customer.phone, customer.phone_2, customer.phone_3):
        href = phone_tel_href(number)
        if href:
            return href
    return None


def delivery_address(customer) -> str | None:
    address = (customer.address or "").strip()
    if not address or address in ("—", "-"):
        return None
    return address


def maps_navigation_urls(address: str) -> dict:
    encoded = quote(address)
    return {
        "apple": f"https://maps.apple.com/?daddr={encoded}",
        "google": f"https://www.google.com/maps/search/?api=1&query={encoded}",
    }
