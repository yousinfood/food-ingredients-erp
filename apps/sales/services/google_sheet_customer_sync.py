"""
Google Sheet「客戶資料」↔ sales.Customer 同步。

Source of Truth：Google Sheet「客戶資料」工作表。
- Sheet → ERP：搜尋客戶前節流拉取
- ERP → Sheet：Customer 新增／修改／刪除後立即寫回
"""

from __future__ import annotations

import csv
import io
import json
import logging
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager

from django.conf import settings
from django.core.cache import cache
from django.db import transaction

from apps.sales.models import Customer
from apps.sales.services.customer_sheet_rows import (
    CUSTOMER_SHEET,
    COLUMN_COUNT,
    customer_defaults_from_record,
    customer_to_sheet_row,
    parse_customer_sheet_rows,
)
from apps.sales.services.phase1_import import CUSTOMER_HEADERS

logger = logging.getLogger(__name__)

CACHE_KEY_LAST = "sales:google_customer_sheet_sync_at"
CACHE_KEY_LOCK = "sales:google_customer_sheet_sync_lock"
CACHE_KEY_SHEET_GID = "sales:google_customer_sheet_gid"
USER_AGENT = "YousinERP-CustomerSync/1.0"

READ_SCOPE = "https://www.googleapis.com/auth/spreadsheets.readonly"
WRITE_SCOPE = "https://www.googleapis.com/auth/spreadsheets"

_syncing_from_sheet = threading.local()
_runtime_overrides: dict[str, str] = {}


def _sync_configured() -> bool:
    if _runtime_overrides.get("csv_url") or settings.GOOGLE_SHEETS_CUSTOMER_CSV_URL.strip():
        return True
    if _runtime_overrides.get("spreadsheet_id") or settings.GOOGLE_SHEETS_SPREADSHEET_ID.strip():
        return True
    return False


def _spreadsheet_id() -> str:
    sheet_id = (_runtime_overrides.get("spreadsheet_id") or settings.GOOGLE_SHEETS_SPREADSHEET_ID).strip()
    if not sheet_id:
        raise RuntimeError("未設定 GOOGLE_SHEETS_SPREADSHEET_ID")
    return sheet_id


def _customer_csv_url() -> str:
    return (_runtime_overrides.get("csv_url") or settings.GOOGLE_SHEETS_CUSTOMER_CSV_URL).strip()


@contextmanager
def customer_sync_runtime(*, spreadsheet_id: str = "", csv_url: str = ""):
    previous = dict(_runtime_overrides)
    if spreadsheet_id:
        _runtime_overrides["spreadsheet_id"] = spreadsheet_id.strip()
    if csv_url:
        _runtime_overrides["csv_url"] = csv_url.strip()
    try:
        yield
    finally:
        _runtime_overrides.clear()
        _runtime_overrides.update(previous)


def clear_customer_search_cache() -> None:
    cache.delete(CACHE_KEY_LAST)
    cache.delete(CACHE_KEY_LOCK)
    cache.delete(CACHE_KEY_SHEET_GID)


def _is_pulling_from_sheet() -> bool:
    return bool(getattr(_syncing_from_sheet, "active", False))


def _set_pulling_from_sheet(active: bool) -> None:
    _syncing_from_sheet.active = active


def _response_meta(resp) -> tuple[int, str, bytes]:
    status = int(getattr(resp, "status", 200))
    headers = getattr(resp, "headers", {}) or {}
    content_type = headers.get("Content-Type") or headers.get("content-type") or ""
    if isinstance(content_type, str):
        content_type = content_type.split(";")[0].strip().lower()
    else:
        content_type = ""
    return status, content_type, resp.read()


def _decode_body(body: bytes) -> str:
    if not body:
        return ""
    return body.decode("utf-8-sig", errors="replace")


def _parse_json_body(
    body_text: str,
    *,
    status: int,
    content_type: str,
    context: str,
) -> dict:
    if status >= 400:
        snippet = (body_text or "")[:200]
        raise RuntimeError(
            f"{context}: HTTP {status} "
            f"(content-type={content_type or 'unknown'}, body={snippet!r})"
        )
    if not body_text or not body_text.strip():
        raise RuntimeError(
            f"{context}: 空白回應 (HTTP {status}, content-type={content_type or 'unknown'})"
        )
    if content_type and "json" not in content_type and "javascript" not in content_type:
        snippet = body_text[:200]
        raise RuntimeError(
            f"{context}: 非 JSON 回應 (content-type={content_type}, body={snippet!r})"
        )
    try:
        parsed = json.loads(body_text)
    except json.JSONDecodeError as exc:
        snippet = body_text[:200]
        raise RuntimeError(
            f"{context}: JSON 解析失敗 ({exc}); "
            f"content-type={content_type or 'unknown'}, body={snippet!r}"
        ) from exc
    if not isinstance(parsed, dict):
        raise RuntimeError(f"{context}: 預期 JSON 物件，收到 {type(parsed).__name__}")
    return parsed


def _service_account_info() -> dict:
    raw = settings.GOOGLE_SERVICE_ACCOUNT_JSON.strip()
    if not raw:
        raise RuntimeError("未設定 GOOGLE_SERVICE_ACCOUNT_JSON")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"GOOGLE_SERVICE_ACCOUNT_JSON 不是有效 JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON 必須是 JSON 物件")
    return parsed


def _access_token(*, write: bool = False) -> str:
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account

    scopes = [WRITE_SCOPE if write else READ_SCOPE]
    creds = service_account.Credentials.from_service_account_info(
        _service_account_info(),
        scopes=scopes,
    )
    creds.refresh(Request())
    return creds.token


def _http_get_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=90) as resp:
        status, content_type, body = _response_meta(resp)
        text = _decode_body(body)
        if status >= 400:
            snippet = text[:200]
            raise RuntimeError(
                f"HTTP GET {url}: HTTP {status} "
                f"(content-type={content_type or 'unknown'}, body={snippet!r})"
            )
        if not text.strip():
            raise RuntimeError(
                f"HTTP GET {url}: 空白回應 (HTTP {status}, content-type={content_type or 'unknown'})"
            )
        return text


def _rows_from_csv_text(text: str) -> list[list]:
    reader = csv.reader(io.StringIO(text))
    return [list(row) for row in reader]


def _public_csv_export_url() -> str:
    sheet_param = urllib.parse.quote(CUSTOMER_SHEET)
    return (
        f"https://docs.google.com/spreadsheets/d/{_spreadsheet_id()}/gviz/tq"
        f"?tqx=out:csv&sheet={sheet_param}"
    )


def _fetch_rows_via_csv_url(url: str) -> list[list]:
    return _rows_from_csv_text(_http_get_text(url))


def _fetch_rows_via_sheets_api() -> list[list]:
    token = _access_token(write=False)
    encoded_range = urllib.parse.quote(f"{CUSTOMER_SHEET}!A:Q", safe="")
    url = f"https://sheets.googleapis.com/v4/spreadsheets/{_spreadsheet_id()}/values/{encoded_range}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=90) as resp:
        status, content_type, body = _response_meta(resp)
        data = _parse_json_body(
            _decode_body(body),
            status=status,
            content_type=content_type,
            context="Google Sheets values API",
        )
    return data.get("values") or []


def _fetch_customer_rows(*, write_token: str | None = None) -> list[list]:
    csv_url = _customer_csv_url()
    if csv_url:
        return _fetch_rows_via_csv_url(csv_url)

    if write_token:
        encoded_range = urllib.parse.quote(f"{CUSTOMER_SHEET}!A:Q", safe="")
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{_spreadsheet_id()}/values/{encoded_range}"
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {write_token}", "User-Agent": USER_AGENT},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            status, content_type, body = _response_meta(resp)
            data = _parse_json_body(
                _decode_body(body),
                status=status,
                content_type=content_type,
                context="Google Sheets values API",
            )
        return data.get("values") or []

    if settings.GOOGLE_SERVICE_ACCOUNT_JSON.strip():
        return _fetch_rows_via_sheets_api()

    return _fetch_rows_via_csv_url(_public_csv_export_url())


def _api_request(method: str, url: str, *, token: str, payload: dict | None = None) -> dict:
    data = None
    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": USER_AGENT,
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=90) as resp:
        status, content_type, raw = _response_meta(resp)
        body_text = _decode_body(raw)
        if not body_text.strip():
            return {}
        return _parse_json_body(
            body_text,
            status=status,
            content_type=content_type,
            context=f"Google Sheets API {method}",
        )


def _customer_range(start_row: int | None = None, end_row: int | None = None) -> str:
    last_col = chr(ord("A") + COLUMN_COUNT - 1)
    if start_row and end_row:
        return f"{CUSTOMER_SHEET}!A{start_row}:{last_col}{end_row}"
    return f"{CUSTOMER_SHEET}!A:{last_col}"


def _find_customer_row_number(rows: list[list], code: str) -> int | None:
    for row_number, row in enumerate(rows[1:], start=2):
        if row and str(row[0]).strip() == code:
            return row_number
    return None


def _customer_sheet_gid(*, token: str) -> int:
    cached = cache.get(CACHE_KEY_SHEET_GID)
    if cached is not None:
        return int(cached)

    url = (
        f"https://sheets.googleapis.com/v4/spreadsheets/{_spreadsheet_id()}"
        "?fields=sheets.properties(sheetId,title)"
    )
    data = _api_request("GET", url, token=token)
    for sheet in data.get("sheets") or []:
        props = sheet.get("properties") or {}
        if props.get("title") == CUSTOMER_SHEET:
            gid = int(props["sheetId"])
            cache.set(CACHE_KEY_SHEET_GID, gid, timeout=3600)
            return gid
    raise RuntimeError(f"找不到工作表：{CUSTOMER_SHEET}")


def run_sync_from_rows(rows: list[list]) -> dict:
    records, errors = parse_customer_sheet_rows(rows)
    if not records:
        return {"ok": False, "created": 0, "updated": 0, "errors": errors or ["沒有可同步的客戶列"]}

    created = 0
    updated = 0
    _set_pulling_from_sheet(True)
    try:
        with transaction.atomic():
            for record in records:
                defaults = customer_defaults_from_record(record)
                _, was_created = Customer.objects.update_or_create(
                    code=record["code"],
                    defaults=defaults,
                )
                if was_created:
                    created += 1
                else:
                    updated += 1
    finally:
        _set_pulling_from_sheet(False)

    clear_customer_search_cache()
    return {
        "ok": not errors,
        "created": created,
        "updated": updated,
        "errors": errors,
    }


def maybe_sync_customers_from_google_sheet(*, force: bool = False) -> dict:
    """Sheet → ERP：拉取「客戶資料」並 upsert Customer（lookup=code）。"""
    if not _sync_configured():
        return {"ok": False, "skipped": True, "reason": "not_configured"}

    interval = settings.CUSTOMER_SHEET_SYNC_INTERVAL_SECONDS
    now = time.time()
    last = cache.get(CACHE_KEY_LAST)
    if not force and last is not None and (now - float(last)) < interval:
        return {"ok": True, "skipped": True, "reason": "throttled"}

    if not cache.add(CACHE_KEY_LOCK, "1", timeout=180):
        return {"ok": True, "skipped": True, "reason": "in_progress"}

    try:
        rows = _fetch_customer_rows()
        if not rows:
            return {"ok": False, "skipped": False, "reason": "empty_sheet"}

        report = run_sync_from_rows(rows)
        cache.set(CACHE_KEY_LAST, now, timeout=max(interval * 4, 120))
        if report.get("errors"):
            logger.warning("Customer sheet pull finished with issues: %s", report["errors"])
        logger.info(
            "Customer sheet pull: created=%s updated=%s ok=%s",
            report.get("created"),
            report.get("updated"),
            report.get("ok"),
        )
        return {"ok": report.get("ok", False), "skipped": False, **report}
    except urllib.error.HTTPError as exc:
        body_text = ""
        try:
            body_text = _decode_body(exc.read())
        except Exception:
            body_text = ""
        logger.warning(
            "Google Sheet customer pull HTTP error: %s (body=%r)",
            exc.code,
            body_text[:200],
        )
        if exc.code in (401, 403):
            return {"ok": False, "skipped": False, "reason": "sheet_access_denied"}
        return {"ok": False, "skipped": False, "reason": f"http_{exc.code}"}
    except Exception as exc:
        logger.warning("Google Sheet customer pull failed: %s", exc, exc_info=True)
        return {"ok": False, "skipped": False, "reason": str(exc)}
    finally:
        cache.delete(CACHE_KEY_LOCK)


def push_customer_to_google_sheet(customer: Customer) -> dict:
    """ERP → Sheet：新增或更新一列客戶資料。"""
    if _is_pulling_from_sheet():
        return {"ok": True, "skipped": True, "reason": "pull_in_progress"}

    if not _sync_configured():
        return {"ok": False, "skipped": True, "reason": "not_configured"}

    if not settings.GOOGLE_SERVICE_ACCOUNT_JSON.strip():
        return {"ok": False, "skipped": True, "reason": "write_requires_service_account"}

    if not customer.code:
        return {"ok": False, "skipped": False, "reason": "missing_customer_code"}

    try:
        token = _access_token(write=True)
        rows = _fetch_customer_rows(write_token=token)
        row_values = customer_to_sheet_row(customer)
        row_number = _find_customer_row_number(rows, customer.code)

        if not rows:
            encoded_range = urllib.parse.quote(f"{CUSTOMER_SHEET}!A1", safe="")
            url = (
                f"https://sheets.googleapis.com/v4/spreadsheets/{_spreadsheet_id()}/values/"
                f"{encoded_range}?valueInputOption=USER_ENTERED"
            )
            _api_request(
                "PUT",
                url,
                token=token,
                payload={"values": [list(CUSTOMER_HEADERS), row_values]},
            )
            action = "initialized"
        elif row_number:
            encoded_range = urllib.parse.quote(_customer_range(row_number, row_number), safe="")
            url = (
                f"https://sheets.googleapis.com/v4/spreadsheets/{_spreadsheet_id()}/values/"
                f"{encoded_range}?valueInputOption=USER_ENTERED"
            )
            _api_request("PUT", url, token=token, payload={"values": [row_values]})
            action = "updated"
        else:
            encoded_range = urllib.parse.quote(f"{CUSTOMER_SHEET}!A:Q", safe="")
            url = (
                f"https://sheets.googleapis.com/v4/spreadsheets/{_spreadsheet_id()}/values/"
                f"{encoded_range}:append?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS"
            )
            _api_request("POST", url, token=token, payload={"values": [row_values]})
            action = "appended"

        clear_customer_search_cache()
        logger.info("Customer %s synced to Google Sheet (%s)", customer.code, action)
        return {"ok": True, "skipped": False, "action": action, "code": customer.code}
    except urllib.error.HTTPError as exc:
        logger.exception("Google Sheet customer push HTTP error: %s", exc.code)
        if exc.code in (401, 403):
            return {"ok": False, "skipped": False, "reason": "sheet_write_denied"}
        return {"ok": False, "skipped": False, "reason": f"http_{exc.code}"}
    except Exception as exc:
        logger.exception("Google Sheet customer push failed for %s", customer.code)
        return {"ok": False, "skipped": False, "reason": str(exc)}


def delete_customer_from_google_sheet(code: str) -> dict:
    """ERP → Sheet：刪除客戶列。"""
    if _is_pulling_from_sheet():
        return {"ok": True, "skipped": True, "reason": "pull_in_progress"}

    if not _sync_configured() or not settings.GOOGLE_SERVICE_ACCOUNT_JSON.strip():
        return {"ok": False, "skipped": True, "reason": "write_requires_service_account"}

    code = (code or "").strip()
    if not code:
        return {"ok": False, "skipped": False, "reason": "missing_customer_code"}

    try:
        token = _access_token(write=True)
        rows = _fetch_customer_rows(write_token=token)
        row_number = _find_customer_row_number(rows, code)
        if not row_number:
            return {"ok": True, "skipped": True, "reason": "row_not_found", "code": code}

        sheet_gid = _customer_sheet_gid(token=token)
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{_spreadsheet_id()}:batchUpdate"
        payload = {
            "requests": [
                {
                    "deleteDimension": {
                        "range": {
                            "sheetId": sheet_gid,
                            "dimension": "ROWS",
                            "startIndex": row_number - 1,
                            "endIndex": row_number,
                        }
                    }
                }
            ]
        }
        _api_request("POST", url, token=token, payload=payload)
        clear_customer_search_cache()
        logger.info("Customer %s deleted from Google Sheet (row %s)", code, row_number)
        return {"ok": True, "skipped": False, "action": "deleted", "code": code}
    except urllib.error.HTTPError as exc:
        logger.exception("Google Sheet customer delete HTTP error: %s", exc.code)
        if exc.code in (401, 403):
            return {"ok": False, "skipped": False, "reason": "sheet_write_denied"}
        return {"ok": False, "skipped": False, "reason": f"http_{exc.code}"}
    except Exception as exc:
        logger.exception("Google Sheet customer delete failed for %s", code)
        return {"ok": False, "skipped": False, "reason": str(exc)}
