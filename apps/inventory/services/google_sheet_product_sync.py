"""Google「產品資料」→ inventory.Product 自動同步（接單讀取前觸發）。"""

from __future__ import annotations

import csv
import io
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.cache import cache

from apps.inventory.services.product_import import PRODUCT_SHEET, run_sync_from_rows

logger = logging.getLogger(__name__)

CACHE_KEY_LAST = "inventory:google_product_sheet_sync_at"
CACHE_KEY_LOCK = "inventory:google_product_sheet_sync_lock"
USER_AGENT = "YousinERP-ProductSync/1.0"


def _sync_configured() -> bool:
    if settings.GOOGLE_SHEETS_PRODUCT_CSV_URL:
        return True
    return bool(settings.GOOGLE_SHEETS_SPREADSHEET_ID.strip())


def _public_csv_export_url() -> str:
    sheet_id = settings.GOOGLE_SHEETS_SPREADSHEET_ID.strip()
    sheet_param = urllib.parse.quote(PRODUCT_SHEET)
    return (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq"
        f"?tqx=out:csv&sheet={sheet_param}"
    )


def _http_get_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return resp.read().decode("utf-8-sig")


def _rows_from_csv_text(text: str) -> list[list]:
    reader = csv.reader(io.StringIO(text))
    return [list(row) for row in reader]


def _fetch_rows_via_csv_url(url: str) -> list[list]:
    return _rows_from_csv_text(_http_get_text(url))


def _fetch_rows_via_sheets_api() -> list[list]:
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account

    raw = settings.GOOGLE_SERVICE_ACCOUNT_JSON.strip()
    if not raw:
        raise RuntimeError("未設定 GOOGLE_SERVICE_ACCOUNT_JSON")
    info = json.loads(raw)
    creds = service_account.Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    creds.refresh(Request())

    sheet_id = settings.GOOGLE_SHEETS_SPREADSHEET_ID.strip()
    range_name = f"{PRODUCT_SHEET}!A:Z"
    encoded_range = urllib.parse.quote(range_name, safe="")
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{encoded_range}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {creds.token}"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read().decode())
    return data.get("values") or []


def _fetch_product_rows() -> list[list]:
    csv_url = settings.GOOGLE_SHEETS_PRODUCT_CSV_URL.strip()
    if csv_url:
        return _fetch_rows_via_csv_url(csv_url)

    if settings.GOOGLE_SERVICE_ACCOUNT_JSON.strip():
        return _fetch_rows_via_sheets_api()

    return _fetch_rows_via_csv_url(_public_csv_export_url())


def maybe_sync_products_from_google_sheet(*, force: bool = False) -> dict:
    """
    從 Google Sheet 拉「產品資料」並 upsert Product。
    接單／搜尋商品前呼叫；節流避免每次請求都打 Google。
    """
    if not _sync_configured():
        return {"ok": False, "skipped": True, "reason": "not_configured"}

    interval = settings.PRODUCT_SHEET_SYNC_INTERVAL_SECONDS
    now = time.time()
    last = cache.get(CACHE_KEY_LAST)
    if not force and last is not None and (now - float(last)) < interval:
        return {"ok": True, "skipped": True, "reason": "throttled"}

    if not cache.add(CACHE_KEY_LOCK, "1", timeout=180):
        return {"ok": True, "skipped": True, "reason": "in_progress"}

    try:
        rows = _fetch_product_rows()
        report = run_sync_from_rows(rows)
        cache.set(CACHE_KEY_LAST, now, timeout=max(interval * 4, 120))
        ok = report.passed and report.errors == []
        if not ok or report.failed_count:
            logger.warning(
                "Product sheet sync finished with issues: errors=%s failed=%s",
                report.errors,
                report.failed_count,
            )
        return {
            "ok": ok and report.failed_count == 0,
            "skipped": False,
            "success_count": report.success_count,
            "failed_count": report.failed_count,
            "errors": list(report.errors),
        }
    except urllib.error.HTTPError as exc:
        logger.exception("Google Sheet product sync HTTP error: %s", exc.code)
        if exc.code in (401, 403):
            return {
                "ok": False,
                "skipped": False,
                "reason": "sheet_access_denied",
            }
        return {"ok": False, "skipped": False, "reason": f"http_{exc.code}"}
    except Exception as exc:
        logger.exception("Google Sheet product sync failed")
        return {"ok": False, "skipped": False, "reason": str(exc)}
    finally:
        cache.delete(CACHE_KEY_LOCK)
