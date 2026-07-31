from django.core.management.base import BaseCommand

from apps.sales.services.google_sheet_customer_sync import (
    customer_sync_runtime,
    maybe_sync_customers_from_google_sheet,
)


class Command(BaseCommand):
    help = "從 Google「客戶資料」立即同步至 Customer（lookup=客戶編號 code，force）"

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
            result = maybe_sync_customers_from_google_sheet(force=True)

        if result.get("skipped") and result.get("reason") == "not_configured":
            self.stderr.write(
                "未設定 GOOGLE_SHEETS_SPREADSHEET_ID（或 GOOGLE_SHEETS_CUSTOMER_CSV_URL）。"
            )
            return

        self.stdout.write(str(result))

        if options.get("verbosity", 1) >= 1 and result.get("updated", 0):
            from apps.sales.models import Customer

            sample = Customer.objects.filter(code="CUS-S019").values("code", "name").first()
            if sample:
                self.stdout.write(f"CUS-S019 in DB: {sample}")
