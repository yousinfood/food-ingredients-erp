from django.conf import settings
from django.utils import timezone

from apps.inventory.models import StockMovement
from apps.sales.models import SalesOrder
from apps.sales.services.product_search import product_to_dict


def void_order(order: SalesOrder, *, user=None) -> None:
    if not order.can_void:
        raise ValueError("此訂單狀態不可作廢")
    order.status = SalesOrder.Status.CANCELLED
    order.cancelled_at = timezone.now()
    order.cancelled_by = user if user and user.is_authenticated else None
    order.save(update_fields=["status", "cancelled_at", "cancelled_by", "updated_at"])


def can_permanently_delete(order: SalesOrder) -> tuple[bool, str]:
    if not settings.DEBUG:
        return False, "正式模式不可永久刪除"

    if order.status in (SalesOrder.Status.SHIPPED, SalesOrder.Status.COMPLETED):
        return False, "已出貨或已完成的訂單不可刪除"

    if order.items.filter(shipped_qty__gt=0).exists():
        return False, "已有出貨數量，不可刪除"

    if StockMovement.objects.filter(reference=order.order_no).exists():
        return False, "已有庫存異動紀錄，不可刪除"

    return True, ""


def permanently_delete_order(order: SalesOrder) -> None:
    allowed, reason = can_permanently_delete(order)
    if not allowed:
        raise ValueError(reason)
    order.delete()


def order_lines_for_copy(order: SalesOrder) -> list[dict]:
    lines = []
    for item in order.items.select_related("product").all():
        if not item.product.is_active:
            continue
        product = product_to_dict(item.product)
        product["quantity"] = str(item.quantity)
        product["unit_price"] = str(item.unit_price)
        lines.append(product)
    return lines
