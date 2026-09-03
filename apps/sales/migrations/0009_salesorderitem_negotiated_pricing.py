from decimal import Decimal

import django.core.validators
from django.db import migrations, models


def backfill_negotiated_pricing(apps, schema_editor):
    SalesOrderItem = apps.get_model("sales", "SalesOrderItem")
    for item in SalesOrderItem.objects.all().iterator():
        original = item.sale_price_snapshot if item.sale_price_snapshot else item.unit_price
        discount = max(Decimal("0"), (original - item.unit_price) * item.quantity)
        item.original_unit_price = original
        item.discount_amount = discount
        item.save(update_fields=["original_unit_price", "discount_amount"])


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0008_customer_product_price"),
    ]

    operations = [
        migrations.AddField(
            model_name="salesorderitem",
            name="original_unit_price",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0"),
                help_text="接單當下依客戶／標準售價解析的單價",
                max_digits=12,
                validators=[django.core.validators.MinValueValidator(Decimal("0"))],
                verbose_name="原始單價",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="salesorderitem",
            name="discount_amount",
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal("0"),
                max_digits=12,
                validators=[django.core.validators.MinValueValidator(Decimal("0"))],
                verbose_name="折讓金額",
            ),
        ),
        migrations.RunPython(backfill_negotiated_pricing, migrations.RunPython.noop),
    ]
