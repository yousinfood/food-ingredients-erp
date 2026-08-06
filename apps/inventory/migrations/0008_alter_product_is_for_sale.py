from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0007_product_standard_price_and_cost_permission"),
    ]

    operations = [
        migrations.AlterField(
            model_name="product",
            name="is_for_sale",
            field=models.BooleanField(default=False, verbose_name="可接單販售"),
        ),
    ]
