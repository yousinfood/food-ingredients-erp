from django.core.management.base import BaseCommand

from apps.core.services.db_connectivity import verify_database_connection


class Command(BaseCommand):
    help = "Verify PostgreSQL / DATABASE_URL connectivity before sync or deploy"

    def handle(self, *args, **options):
        from django.conf import settings
        from django.db import connection

        db = settings.DATABASES["default"]
        engine = db.get("ENGINE", "")
        host = db.get("HOST") or "(sqlite)"
        name = db.get("NAME") or ""

        self.stdout.write(f"Engine: {engine}")
        self.stdout.write(f"Host: {host}")
        self.stdout.write(f"Database: {name}")

        verify_database_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT version()")
            version = cursor.fetchone()[0]
        self.stdout.write(self.style.SUCCESS(f"OK — {version[:80]}"))
