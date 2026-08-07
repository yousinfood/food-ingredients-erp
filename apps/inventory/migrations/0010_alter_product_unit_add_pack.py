from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0009_product_pricing_and_cost_history"),
    ]

    operations = [
        migrations.AlterField(
            model_name="product",
            name="unit",
            field=models.CharField(
                choices=[
                    ("kg", "公斤"),
                    ("g", "公克"),
                    ("l", "公升"),
                    ("ml", "毫升"),
                    ("pcs", "件"),
                    ("box", "箱"),
                    ("pack", "包"),
                ],
                default="kg",
                max_length=10,
                verbose_name="庫存單位",
            ),
        ),
    ]
