from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0009_salesorderitem_negotiated_pricing"),
    ]

    operations = [
        migrations.AddField(
            model_name="salesorder",
            name="special_price_reason",
            field=models.CharField(
                blank=True,
                choices=[
                    ("pre_increase", "漲價前優惠"),
                    ("special_favor", "特殊優待"),
                    ("other", "其他"),
                ],
                max_length=20,
                verbose_name="特殊成交原因",
            ),
        ),
        migrations.AddField(
            model_name="salesorder",
            name="special_price_reason_note",
            field=models.CharField(blank=True, max_length=200, verbose_name="特殊成交原因說明"),
        ),
    ]
