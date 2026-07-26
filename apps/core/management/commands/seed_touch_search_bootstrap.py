"""Idempotent minimal customers for touch search on empty production DB."""

from django.core.management.base import BaseCommand

from apps.sales.models import Customer

# Real shop names used in iPad search QA (see scripts/migration_sql/data/客戶資料.sql).
BOOTSTRAP = (
    {
        "code": "CUS-W007",
        "name": "成功彩虹日本料理",
        "region": "中西區",
        "phone": "2263162",
        "phone_2": "2263163",
        "address": "台南市成功路249號",
    },
    {
        "code": "CUS-N003",
        "name": "和緯彩虹日本料理",
        "region": "北區",
        "phone": "2803819",
        "phone_2": "2803057",
        "address": "台南市和緯路三段332號",
    },
)


class Command(BaseCommand):
    help = "Ensure touch-search demo customers exist (safe to run on every deploy)."

    def handle(self, *args, **options):
        created = 0
        for row in BOOTSTRAP:
            _, was_created = Customer.objects.get_or_create(
                code=row["code"],
                defaults={k: v for k, v in row.items() if k != "code"},
            )
            if was_created:
                created += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"touch search bootstrap: {created} created, {len(BOOTSTRAP) - created} already present"
            )
        )
