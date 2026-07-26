import subprocess
import sys
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.inventory.services.product_upsert_import import (
    DEFAULT_JSON_PATH,
    upsert_products_from_json,
)


class Command(BaseCommand):
    help = "依料號 (sku) idempotent upsert 產品主檔（Django dumpdata JSON；不刪除、不改 pk）"

    def add_arguments(self, parser):
        parser.add_argument(
            "json_path",
            nargs="?",
            default=str(DEFAULT_JSON_PATH),
            help=f"產品 JSON 路徑（預設：{DEFAULT_JSON_PATH}）",
        )
        parser.add_argument(
            "--from-sqlite",
            action="store_true",
            help="從本機 SQLite 以 dumpdata 產生 JSON（唯讀），再 upsert",
        )
        parser.add_argument(
            "--sqlite-path",
            default=str(settings.BASE_DIR / "db.sqlite3"),
            help="--from-sqlite 使用的 SQLite 路徑",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="只統計將新增／更新筆數，不寫入資料庫",
        )

    def handle(self, *args, **options):
        json_path = Path(options["json_path"])

        if options["from_sqlite"]:
            sqlite_path = Path(options["sqlite_path"])
            if not sqlite_path.exists():
                raise CommandError(f"找不到 SQLite：{sqlite_path}")
            json_path = self._dump_sqlite_products(sqlite_path)

        if not json_path.exists():
            raise CommandError(f"找不到 JSON：{json_path}")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("dry-run：不會寫入資料庫"))

        self.stdout.write(f"讀取：{json_path}")

        try:
            result = upsert_products_from_json(json_path, dry_run=options["dry_run"])
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                "完成："
                f"新增 {result.created}、更新 {result.updated}、"
                f"未變更 {result.unchanged}、略過 {result.skipped}"
            )
        )
        for error in result.errors:
            self.stdout.write(self.style.WARNING(error))

    def _dump_sqlite_products(self, sqlite_path: Path) -> Path:
        import os

        env = os.environ.copy()
        env["USE_POSTGRES"] = "0"
        env.pop("DATABASE_URL", None)
        env.pop("DATABASE_PUBLIC_URL", None)
        env.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as tmp:
            out_path = Path(tmp.name)

        cmd = [
            sys.executable,
            "manage.py",
            "dumpdata",
            "inventory.Product",
            "--indent",
            "2",
            "--database",
            "default",
        ]
        self.stdout.write(f"從 SQLite 匯出產品：{sqlite_path} → {out_path}")
        completed = subprocess.run(
            cmd,
            cwd=settings.BASE_DIR,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            out_path.unlink(missing_ok=True)
            raise CommandError(completed.stderr.strip() or "dumpdata 失敗")

        out_path.write_text(completed.stdout, encoding="utf-8")
        return out_path
