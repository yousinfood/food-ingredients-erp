import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.inventory.services.product_import import (
    DEFAULT_EXCEL_PATH,
    execute_import,
    run_preflight,
)


class Command(BaseCommand):
    help = "從 Google Sheet 匯出的 Excel「產品資料」工作表匯入 Product（預設 dry-run）"

    def add_arguments(self, parser):
        parser.add_argument(
            "file_path",
            nargs="?",
            default=str(DEFAULT_EXCEL_PATH),
            help=f"Excel 檔案路徑（預設：{DEFAULT_EXCEL_PATH}）",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Preflight 通過後實際寫入 ERP",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="以 JSON 輸出完整報告",
        )

    def handle(self, *args, **options):
        path = Path(options["file_path"])
        report = run_preflight(path)

        if options["json"]:
            payload = {
                "passed": report.passed,
                "total_rows": report.total_rows,
                "success_count": report.success_count,
                "failed_count": report.failed_count,
                "duplicate_skus": report.duplicate_skus,
                "failures": report.failures,
                "successes": report.successes,
                "errors": report.errors,
            }
            if options["execute"] and report.passed:
                execute_import(report)
                payload["success_count"] = report.success_count
                payload["failed_count"] = report.failed_count
                payload["failures"] = report.failures
                payload["successes"] = report.successes
            self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
            return

        self._print_report(report, executed=False)

        if not report.passed:
            raise CommandError("Preflight 未通過，未執行匯入。")

        if not options["execute"]:
            self.stdout.write(
                self.style.WARNING(
                    "\nPreflight 通過。若要實際匯入，請加上 --execute"
                )
            )
            return

        execute_import(report)
        self.stdout.write(self.style.SUCCESS("\n=== 產品匯入完成 ==="))
        self._print_summary(report)

    def _print_report(self, report, *, executed: bool):
        self.stdout.write(self.style.MIGRATE_HEADING("=== 產品資料 Preflight ==="))
        self.stdout.write(f"狀態：{'通過' if report.passed else '失敗'}")
        self.stdout.write(f"工作表列數：{report.total_rows}")

        parsed_rows = getattr(report, "_parsed_rows", [])
        self.stdout.write(self.style.MIGRATE_HEADING(f"\n待匯入（{len(parsed_rows)} 筆）"))
        for row in parsed_rows:
            self.stdout.write(
                f"  [{row['sku']}] {row['name']} | 分類={row['category'] or '-'} | "
                f"品牌={row['brand'] or '-'} | 系列={row['series'] or '-'} | "
                f"規格={row['spec'] or '-'} | 單位={row['unit_label']}"
            )

        if report.duplicate_skus:
            self.stdout.write(self.style.ERROR(f"\n重複產品編號（{len(report.duplicate_skus)}）"))
            for sku in report.duplicate_skus:
                self.stdout.write(f"  - {sku}")

        if report.failures:
            self.stdout.write(self.style.ERROR(f"\n失敗列（{len(report.failures)}）"))
            for item in report.failures:
                self.stdout.write(f"  row {item['row']} [{item.get('sku', '')}]: {item['reason']}")

        if report.errors:
            self.stdout.write(self.style.ERROR(f"\n錯誤（{len(report.errors)}）"))
            for err in report.errors:
                self.stdout.write(f"  - {err}")

    def _print_summary(self, report):
        self.stdout.write(f"共處理：{report.total_rows} 筆")
        self.stdout.write(self.style.SUCCESS(f"成功：{report.success_count} 筆"))
        self.stdout.write(f"失敗：{report.failed_count} 筆")
        if report.duplicate_skus:
            self.stdout.write(f"重複編號：{', '.join(report.duplicate_skus)}")
        if report.failures:
            self.stdout.write("\n失敗原因：")
            for item in report.failures:
                self.stdout.write(f"  row {item['row']} [{item.get('sku', '')}]: {item['reason']}")
