import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.sales.services.phase1_import import (
    DEFAULT_EXCEL_PATH,
    execute_import,
    run_preflight,
)


class Command(BaseCommand):
    help = "Phase 1：從 data/有信ERP.xlsx 匯入客戶、成品、原料（預設 dry-run）"

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
            help="Preflight 通過後執行實際匯入（會清除既有客戶/產品/訂單）",
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
            self.stdout.write(
                json.dumps(
                    {
                        "passed": report.passed,
                        "customers": report.customers,
                        "finished_products": report.finished_products,
                        "raw_materials": report.raw_materials,
                        "skipped_rows": report.skipped_rows,
                        "transformations": report.transformations,
                        "warnings": report.warnings,
                        "errors": report.errors,
                        "cleared": report.cleared,
                        "imported": report.imported,
                    },
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                )
            )
            if not options["execute"]:
                return
        else:
            self._print_report(report)

        if not report.passed:
            raise CommandError("Preflight 未通過，未執行匯入。請修正上述錯誤。")

        if not options["execute"]:
            self.stdout.write(
                self.style.WARNING(
                    "\nPreflight 通過。若要執行實際匯入，請加上 --execute"
                )
            )
            return

        execute_import(report)
        if not options["json"]:
            self.stdout.write(self.style.SUCCESS("\n=== 匯入完成 ==="))
            self.stdout.write(f"已清除：{report.cleared}")
            self.stdout.write(f"已匯入：{report.imported}")

    def _print_report(self, report):
        self.stdout.write(self.style.MIGRATE_HEADING("=== Phase 1 Preflight ==="))
        self.stdout.write(f"狀態：{'通過' if report.passed else '失敗'}")

        self.stdout.write(self.style.MIGRATE_HEADING(f"\n客戶（{len(report.customers)} 筆）"))
        for row in report.customers:
            self.stdout.write(
                f"  [{row['code']}] {row['name']} | 區域={row['region'] or '-'} | "
                f"phone={row['phone'] or '-'} | phone_2={row['phone_2'] or '-'} | phone_3={row['phone_3'] or '-'}"
            )

        self.stdout.write(self.style.MIGRATE_HEADING(f"\n成品（{len(report.finished_products)} 筆）"))
        for row in report.finished_products:
            self.stdout.write(
                f"  [{row['sku']}] {row['name']} | kind={row['product_kind']} | "
                f"unit={row['unit']} | spec={row['spec'] or '-'}"
            )

        self.stdout.write(self.style.MIGRATE_HEADING(f"\n原料（{len(report.raw_materials)} 筆）"))
        for row in report.raw_materials:
            self.stdout.write(
                f"  [{row['sku']}] {row['name']} | category={row['category'] or '-'} | "
                f"unit_cost={row['unit_cost'] or '-'}"
            )

        if report.skipped_rows:
            self.stdout.write(self.style.WARNING(f"\n略過列（{len(report.skipped_rows)}）"))
            for row in report.skipped_rows:
                self.stdout.write(f"  {row['sheet']} row {row['row']}: {row['reason']}")

        if report.transformations:
            self.stdout.write(self.style.WARNING(f"\n轉換（{len(report.transformations)}）"))
            for t in report.transformations:
                self.stdout.write(
                    f"  {t['sheet']} row {t['row']}: {t['field']} {t['from']} → {t['to']} ({t['reason']})"
                )

        if report.warnings:
            self.stdout.write(self.style.WARNING(f"\n警告（{len(report.warnings)}）"))
            for w in report.warnings:
                self.stdout.write(f"  - {w}")

        if report.errors:
            self.stdout.write(self.style.ERROR(f"\n錯誤（{len(report.errors)}）"))
            for e in report.errors:
                self.stdout.write(f"  - {e}")
