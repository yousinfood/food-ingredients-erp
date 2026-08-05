# Generated manually for pricing API snapshot fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0006_salesorderitem_sale_price_snapshot"),
    ]

    operations = [
        migrations.AddField(
            model_name="salesorderitem",
            name="price_source",
            field=models.CharField(
                blank=True,
                default="",
                help_text="customer=客戶專屬售價，standard=標準售價",
                max_length=20,
                verbose_name="售價來源",
            ),
        ),
        migrations.AddField(
            model_name="salesorderitem",
            name="price_version",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="CustomerProductPrice 主鍵（客戶售價時）",
                null=True,
                verbose_name="售價版本",
            ),
        ),
    ]
