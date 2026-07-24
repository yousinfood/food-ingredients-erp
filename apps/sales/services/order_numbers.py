from django.utils import timezone

from ..models import SalesOrder


def next_order_no():
    today = timezone.localdate()
    prefix = f"SO-{today.strftime('%Y%m%d')}-"
    last = (
        SalesOrder.objects.filter(order_no__startswith=prefix)
        .order_by("-order_no")
        .values_list("order_no", flat=True)
        .first()
    )
    if last:
        seq = int(last.rsplit("-", 1)[-1]) + 1
    else:
        seq = 1
    return f"{prefix}{seq:03d}"
