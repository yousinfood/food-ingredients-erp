from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from apps.excel_schema.db_counts import compare_table_counts
from apps.excel_schema.import_excel import DEFAULT_EXCEL_PATH, run_import


class Command(BaseCommand):
    help = "在 PostgreSQL（Supabase）執行 migrate、Excel 匯入，並與 SQLite 筆數比對"

    def add_arguments(self, parser):
        parser.add_argument(
            "file_path",
            nargs="?",
            default=str(DEFAULT_EXCEL_PATH),
            help=f"Excel 檔案路徑（預設：{DEFAULT_EXCEL_PATH}）",
        )
        parser.add_argument(
            "--sqlite-path",
            default=str(settings.BASE_DIR / "db.sqlite3"),
            help="作為基準的 SQLite 檔案路徑",
        )
        parser.add_argument(
            "--skip-import",
            action="store_true",
            help="只執行 migrate 與筆數比對，不重新匯入 Excel",
        )
        parser.add_argument(
            "--fake-initial",
            action="store_true",
            help="資料表已由 Supabase MCP 建立時，略過重複 CREATE TABLE（migrate --fake-initial）",
        )

    def handle(self, *args, **options):
        engine = settings.DATABASES["default"]["ENGINE"]
        if engine != "django.db.backends.postgresql":
            raise CommandError(
                "目前未使用 PostgreSQL。請在 .env 設定 Supabase 的 DATABASE_URL 後再執行。"
            )

        sqlite_path = Path(options["sqlite_path"])
        if not sqlite_path.exists():
            raise CommandError(f"找不到 SQLite 基準檔案：{sqlite_path}")

        migrate_kwargs = {"verbosity": 1}
        if options["fake_initial"]:
            migrate_kwargs["fake_initial"] = True
            self.stdout.write(
                "=== 執行 PostgreSQL migration（--fake-initial：略過已存在資料表）==="
            )
        else:
            self.stdout.write("=== 執行 PostgreSQL migration ===")
        call_command("migrate", **migrate_kwargs)

        if not options["skip_import"]:
            self.stdout.write("\n=== 匯入 Excel 至 PostgreSQL ===")
            run_import(options["file_path"])

        self.stdout.write("\n=== 資料表筆數比對（SQLite vs PostgreSQL）===")
        rows = compare_table_counts(sqlite_path)
        all_match = True
        for row in rows:
            sqlite_count = row["sqlite"]
            current_count = row["current"]
            if sqlite_count is None:
                status = "SQLite 無此表"
                all_match = False
            elif row["match"]:
                status = "一致"
            else:
                status = "不一致"
                all_match = False
            self.stdout.write(
                f"{row['table']}: SQLite={sqlite_count} | PostgreSQL={current_count} | {status}"
            )

        if all_match:
            self.stdout.write(self.style.SUCCESS("\n所有 excel_schema 資料表筆數與 SQLite 一致。"))
        else:
            raise CommandError("部分資料表筆數與 SQLite 不一致，請檢查上方輸出。")
