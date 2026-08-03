"""Live customer search revision — PostgreSQL source of truth + SSE refresh hook.

Future: swap SSE polling for Supabase Realtime / WebSocket by implementing
the same ``bump_customer_search_revision`` / ``get_customer_search_revision`` contract.
"""

from __future__ import annotations

import json
import time

from django.db import close_old_connections, transaction
from django.db.models import F

from apps.sales.models import CustomerSearchRevision

REVISION_PK = 1
SSE_POLL_SECONDS = 1.0


def get_customer_search_revision() -> int:
    close_old_connections()
    version = (
        CustomerSearchRevision.objects.filter(pk=REVISION_PK)
        .values_list("version", flat=True)
        .first()
    )
    return int(version or 0)


def bump_customer_search_revision() -> None:
    def _do_bump() -> None:
        close_old_connections()
        CustomerSearchRevision.objects.get_or_create(pk=REVISION_PK, defaults={"version": 0})
        CustomerSearchRevision.objects.filter(pk=REVISION_PK).update(version=F("version") + 1)

    transaction.on_commit(_do_bump)


def customer_revision_event_payload() -> str:
    return json.dumps({"version": get_customer_search_revision()}, ensure_ascii=False)


def iter_customer_revision_events(*, poll_seconds: float = SSE_POLL_SECONDS):
    """SSE generator — notifies clients when customer data revision changes."""
    last_version = get_customer_search_revision()
    yield f"event: revision\ndata: {json.dumps({'version': last_version}, ensure_ascii=False)}\n\n"

    try:
        while True:
            time.sleep(poll_seconds)
            current = get_customer_search_revision()
            if current != last_version:
                last_version = current
                yield f"event: revision\ndata: {json.dumps({'version': current}, ensure_ascii=False)}\n\n"
    except GeneratorExit:
        return
