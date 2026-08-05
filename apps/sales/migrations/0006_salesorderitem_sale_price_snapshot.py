# Generated manually for pricing cost isolation

import django.core.validators
from decimal import Decimal
from django.db import migrations, models


def backfill_sale_price_snapshot(apps, schema_editor):
    SalesOrderItem = apps.get_model("sales", "SalesOrderItem")
    for item in SalesOrderItem.objects.all().iterator():
        item.sale_price_snapshot = item.unit_price
        item.save(update_fields=["sale_price_snapshot"])


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0005_customer_search_revision"),
    ]

    operations = [
        migrations.AddField(
            model_name="salesorderitem",
            name="sale_price_snapshot",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0"),
                max_digits=12,
                validators=[django.core.validators.MinValueValidator(Decimal("0"))],
                verbose_name="成交售價快照",
                help_text="訂單成立當下由後端寫入，不受日後售價調整影響",
            ),
            preserve_default=False,
        ),
        migrations.RunPython(backfill_sale_price_snapshot, migrations.RunPython.noop),
    ]
