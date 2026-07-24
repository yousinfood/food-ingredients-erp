from django.core.management.base import BaseCommand, CommandError

from apps.excel_schema.import_excel import DEFAULT_EXCEL_PATH, run_import


class Command(BaseCommand):
    help = "從有信ERP.xlsx 依工作表順序匯入 excel_schema 資料表"

    def add_arguments(self, parser):
        parser.add_argument(
            "file_path",
            nargs="?",
            default=str(DEFAULT_EXCEL_PATH),
            help=f"Excel 檔案路徑（預設：{DEFAULT_EXCEL_PATH}）",
        )

    def handle(self, *args, **options):
        file_path = options["file_path"]
        try:
            run_import(file_path)
        except FileNotFoundError as exc:
            raise CommandError(str(exc)) from exc
