from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.excel_schema.db_counts import compare_table_counts, get_current_table_counts


class Command(BaseCommand):
    help = "輸出 excel_schema 各資料表筆數，並可與 SQLite 基準比對"

    def add_arguments(self, parser):
        parser.add_argument(
            "--sqlite-path",
            default=str(settings.BASE_DIR / "db.sqlite3"),
            help="要比對的 SQLite 檔案路徑",
        )
        parser.add_argument(
            "--no-compare",
            action="store_true",
            help="只輸出目前資料庫筆數，不與 SQLite 比對",
        )

    def handle(self, *args, **options):
        self.stdout.write("=== 目前資料庫 excel_schema 筆數 ===")
        for table, count in get_current_table_counts().items():
            self.stdout.write(f"{table}: {count} 筆")

        if options["no_compare"]:
            return

        sqlite_path = Path(options["sqlite_path"])
        if not sqlite_path.exists():
            raise CommandError(f"找不到 SQLite 檔案：{sqlite_path}")

        self.stdout.write("\n=== 與 SQLite 比對 ===")
        all_match = True
        for row in compare_table_counts(sqlite_path):
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
                f"{row['table']}: SQLite={sqlite_count} | 目前={current_count} | {status}"
            )

        if all_match:
            self.stdout.write(self.style.SUCCESS("\n所有資料表筆數一致。"))
        else:
            raise CommandError("部分資料表筆數不一致。")
