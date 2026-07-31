import logging

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.sales.models import Customer
from apps.sales.services.google_sheet_customer_sync import (
    delete_customer_from_google_sheet,
    push_customer_to_google_sheet,
)

logger = logging.getLogger(__name__)

_skip_sheet_push = False


def skip_sheet_push() -> None:
    global _skip_sheet_push
    _skip_sheet_push = True


def resume_sheet_push() -> None:
    global _skip_sheet_push
    _skip_sheet_push = False


def _schedule_push(customer_id: int) -> None:
    def _push() -> None:
        customer = Customer.objects.filter(pk=customer_id).first()
        if not customer:
            return
        result = push_customer_to_google_sheet(customer)
        if not result.get("ok") and not result.get("skipped"):
            logger.error("Customer sheet push failed for %s: %s", customer.code, result)

    transaction.on_commit(_push)


def _schedule_delete(code: str) -> None:
    def _delete() -> None:
        result = delete_customer_from_google_sheet(code)
        if not result.get("ok") and not result.get("skipped"):
            logger.error("Customer sheet delete failed for %s: %s", code, result)

    transaction.on_commit(_delete)


@receiver(post_save, sender=Customer)
def customer_saved_sync_sheet(sender, instance, **kwargs):
    if _skip_sheet_push:
        return
    _schedule_push(instance.pk)


@receiver(post_delete, sender=Customer)
def customer_deleted_sync_sheet(sender, instance, **kwargs):
    if _skip_sheet_push:
        return
    _schedule_delete(instance.code)
