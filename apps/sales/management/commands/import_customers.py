from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.sales.services.customer_import import CUSTOMER_SHEET_NAME, DEFAULT_EXCEL_PATH, import_customers


class Command(BaseCommand):
    help = f"從 Excel「{CUSTOMER_SHEET_NAME}」工作表匯入客戶資料到 Customer 資料表"

    def add_arguments(self, parser):
        parser.add_argument(
            "file_path",
            nargs="?",
            default=str(DEFAULT_EXCEL_PATH),
            help=f"Excel 檔案路徑（預設：{DEFAULT_EXCEL_PATH}）",
        )

    def handle(self, *args, **options):
        file_path = Path(options["file_path"])

        if not file_path.exists():
            raise CommandError(f"找不到 Excel 檔案：{file_path}")

        self.stdout.write(f"讀取 Excel：{file_path}")

        try:
            result = import_customers(file_path)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"匯入完成：新增 {result.created} 筆、更新 {result.updated} 筆、略過 {result.skipped} 筆"
            )
        )

        for error in result.errors:
            self.stdout.write(self.style.WARNING(error))
