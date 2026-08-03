"""從 Google Sheet「客戶資料」同步至 PostgreSQL（upsert by code）。"""

from django.core.management.base import BaseCommand

from apps.sales.models import CustomerSheetSyncLog
from apps.sales.services.google_sheet_customer_sync import (
    customer_sync_runtime,
    sync_customers_from_google_sheet,
)


class Command(BaseCommand):
    help = "從 Google Sheet「客戶資料」同步至 Customer（唯一鍵=客戶編號 code）"

    def add_arguments(self, parser):
        parser.add_argument(
            "--spreadsheet-id",
            default="",
            help="覆寫 GOOGLE_SHEETS_SPREADSHEET_ID（一次性同步用）",
        )
        parser.add_argument(
            "--csv-url",
            default="",
            help="覆寫 GOOGLE_SHEETS_CUSTOMER_CSV_URL（一次性同步用）",
        )

    def handle(self, *args, **options):
        with customer_sync_runtime(
            spreadsheet_id=options.get("spreadsheet_id") or "",
            csv_url=options.get("csv_url") or "",
        ):
            report = sync_customers_from_google_sheet(
                force=True,
                triggered_by=CustomerSheetSyncLog.Trigger.COMMAND,
            )

        if report.skipped and report.reason == "not_configured":
            self.stderr.write(
                "未設定 GOOGLE_SHEETS_SPREADSHEET_ID（或 GOOGLE_SHEETS_CUSTOMER_CSV_URL）。"
            )
            return

        if report.skipped:
            self.stdout.write(f"略過同步：{report.reason}")
            return

        self.stdout.write(
            f"同步完成：新增 {report.created}、更新 {report.updated}、"
            f"略過 {report.skipped_rows}、錯誤 {len(report.errors)}"
        )
        if report.synced_at:
            self.stdout.write(f"時間：{report.synced_at}")
        if report.errors:
            self.stderr.write("錯誤明細：")
            for err in report.errors:
                self.stderr.write(f"  - {err}")
        if not report.ok:
            self.stderr.write("同步未完全成功。")
