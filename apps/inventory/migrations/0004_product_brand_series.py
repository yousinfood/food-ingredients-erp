from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0003_product_packaging_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="brand",
            field=models.CharField(blank=True, max_length=100, verbose_name="品牌"),
        ),
        migrations.AddField(
            model_name="product",
            name="series",
            field=models.CharField(blank=True, max_length=100, verbose_name="系列"),
        ),
    ]
