from django.core.management.base import BaseCommand

from apps.inventory.services.google_sheet_product_sync import maybe_sync_products_from_google_sheet


class Command(BaseCommand):
    help = "從 Google「產品資料」立即同步至 Product（略過節流，供部署後驗證）"

    def handle(self, *args, **options):
        result = maybe_sync_products_from_google_sheet(force=True)
        if result.get("skipped") and result.get("reason") == "not_configured":
            self.stderr.write(
                "未設定 GOOGLE_SHEETS_SPREADSHEET_ID（或 GOOGLE_SHEETS_PRODUCT_CSV_URL）。"
            )
            return
        self.stdout.write(str(result))
