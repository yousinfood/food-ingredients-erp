import logging

from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.sales.models import Customer
from apps.sales.services.customer_realtime import bump_customer_search_revision
from apps.sales.services.customer_sheet_sync_flags import (
    revision_bump_skipped,
    sheet_push_skipped,
    skip_revision_bump,
    skip_sheet_push,
)
from apps.sales.services.google_sheet_customer_sync import (
    customer_sheet_push_enabled,
    delete_customer_from_google_sheet,
    push_customer_to_google_sheet,
)

logger = logging.getLogger(__name__)


def resume_sheet_push() -> None:
    from apps.sales.services.customer_sheet_sync_flags import resume_sheet_push as _resume

    _resume()


def resume_revision_bump() -> None:
    from apps.sales.services.customer_sheet_sync_flags import resume_revision_bump as _resume

    _resume()


def _schedule_push(customer_id: int) -> None:
    if not customer_sheet_push_enabled():
        return

    def _push() -> None:
        customer = Customer.objects.filter(pk=customer_id).first()
        if not customer:
            return
        result = push_customer_to_google_sheet(customer)
        if not result.get("ok") and not result.get("skipped"):
            logger.error("Customer sheet push failed for %s: %s", customer.code, result)

    transaction.on_commit(_push)


def _schedule_delete(code: str) -> None:
    if not customer_sheet_push_enabled():
        return

    def _delete() -> None:
        result = delete_customer_from_google_sheet(code)
        if not result.get("ok") and not result.get("skipped"):
            logger.error("Customer sheet delete failed for %s: %s", code, result)

    transaction.on_commit(_delete)


@receiver(post_save, sender=Customer)
def customer_saved_sync_sheet(sender, instance, **kwargs):
    if not revision_bump_skipped():
        bump_customer_search_revision()
    if sheet_push_skipped() or not customer_sheet_push_enabled():
        return
    _schedule_push(instance.pk)


@receiver(post_delete, sender=Customer)
def customer_deleted_sync_sheet(sender, instance, **kwargs):
    if not revision_bump_skipped():
        bump_customer_search_revision()
    if sheet_push_skipped() or not customer_sheet_push_enabled():
        return
    _schedule_delete(instance.code)
