#!/usr/bin/env python3
"""Configure Google Sheet customer sync (.env + connectivity test).

Usage:
  python scripts/setup_google_sheet_sync.py --spreadsheet-url 'https://docs.google.com/spreadsheets/d/XXXX/edit'
  python scripts/setup_google_sheet_sync.py --spreadsheet-id XXXX --service-account-json /path/to/key.json
  python scripts/setup_google_sheet_sync.py --csv-url 'http://127.0.0.1:8765/customers.csv'  # local test only
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"

try:
    from dotenv import load_dotenv

    load_dotenv(ENV_PATH, override=False)
except ImportError:
    pass

SPREADSHEET_ID_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9-_]+)")


def parse_spreadsheet_id(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    match = SPREADSHEET_ID_RE.search(value)
    if match:
        return match.group(1)
    if re.fullmatch(r"[a-zA-Z0-9-_]{20,}", value):
        return value
    raise SystemExit(f"無法解析 Spreadsheet ID：{value!r}")


def load_service_account_json(path: str) -> str:
    p = Path(path).expanduser()
    if not p.is_file():
        raise SystemExit(f"找不到 Service Account JSON：{p}")
    raw = p.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict) or "client_email" not in data:
        raise SystemExit("Service Account JSON 格式不正確（缺少 client_email）")
    return json.dumps(data, ensure_ascii=False)


def upsert_env_lines(lines: dict[str, str]) -> None:
    existing: list[str] = []
    if ENV_PATH.is_file():
        existing = ENV_PATH.read_text(encoding="utf-8").splitlines()

    keys = set(lines)
    out: list[str] = []
    seen: set[str] = set()
    for line in existing:
        if not line or line.lstrip().startswith("#"):
            out.append(line)
            continue
        if "=" not in line:
            out.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key in keys:
            out.append(f"{key}={lines[key]}")
            seen.add(key)
        else:
            out.append(line)

    missing = [k for k in lines if k not in seen]
    if missing:
        if out and out[-1].strip():
            out.append("")
        out.append("# Google Sheet → PostgreSQL 客戶同步（scripts/setup_google_sheet_sync.py）")
        for key in missing:
            out.append(f"{key}={lines[key]}")

    ENV_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="設定 Google Sheet 客戶同步環境變數")
    parser.add_argument("--spreadsheet-url", default="", help="Google 試算表完整網址")
    parser.add_argument("--spreadsheet-id", default="", help="Spreadsheet ID")
    parser.add_argument("--service-account-json", default="", help="Service Account JSON 檔案路徑")
    parser.add_argument("--csv-url", default="", help="公開 CSV URL（本機測試用）")
    parser.add_argument("--skip-test", action="store_true", help="只寫 .env，不跑連線測試")
    args = parser.parse_args()

    env_updates: dict[str, str] = {
        "CUSTOMER_SHEET_ONE_WAY_SYNC": "1",
        "CUSTOMER_SHEET_SYNC_INTERVAL_SECONDS": "15",
    }

    spreadsheet_id = ""
    if args.spreadsheet_id:
        spreadsheet_id = parse_spreadsheet_id(args.spreadsheet_id)
    elif args.spreadsheet_url:
        spreadsheet_id = parse_spreadsheet_id(args.spreadsheet_url)

    if spreadsheet_id:
        env_updates["GOOGLE_SHEETS_SPREADSHEET_ID"] = spreadsheet_id
        env_updates["GOOGLE_SHEETS_CUSTOMER_CSV_URL"] = ""

    if args.csv_url:
        env_updates["GOOGLE_SHEETS_CUSTOMER_CSV_URL"] = args.csv_url.strip()

    if args.service_account_json:
        sa_json = load_service_account_json(args.service_account_json)
        env_updates["GOOGLE_SERVICE_ACCOUNT_JSON"] = sa_json
        email = json.loads(sa_json)["client_email"]
        print(f"Service Account Email（請分享試算表「編輯者」）：{email}")
    elif spreadsheet_id and not args.csv_url:
        print("提示：未提供 Service Account JSON。私人試算表需 Service Account 或公開 CSV。")

    if not spreadsheet_id and not args.csv_url:
        raise SystemExit(
            "請提供 --spreadsheet-url / --spreadsheet-id，或 --csv-url（本機測試）。"
        )

    upsert_env_lines(env_updates)
    print(f"已更新 {ENV_PATH}")

    if args.skip_test:
        return 0

    os.chdir(ROOT)
    os.environ.update(env_updates)
    sys.path.insert(0, str(ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    import django

    django.setup()

    from apps.sales.models import CustomerSheetSyncLog
    from apps.sales.services.google_sheet_customer_sync import sync_customers_from_google_sheet

    report = sync_customers_from_google_sheet(force=True)
    print(
        "同步結果:",
        f"ok={report.ok}",
        f"created={report.created}",
        f"updated={report.updated}",
        f"skipped={report.skipped_rows}",
        f"errors={report.errors}",
    )
    if report.log_id:
        log = CustomerSheetSyncLog.objects.get(pk=report.log_id)
        print(f"SyncLog #{log.pk} triggered_by={log.triggered_by} message={log.message}")

    return 0 if report.ok and not report.skipped else 1


if __name__ == "__main__":
    raise SystemExit(main())
