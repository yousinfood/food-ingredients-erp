"""is_sellable：變性澱粉市售／自用配方分頁（依資料，非寫死品名）。"""

from django.db import migrations, models


def seed_modified_starch_sellable(apps, schema_editor):
    Product = apps.get_model("inventory", "Product")
    category = "變性澱粉"
    Product.objects.exclude(category=category).update(is_sellable=True)
    Product.objects.filter(category=category).update(is_sellable=False)
    # 既有 Sheet「是否販售」= 市售；正式匯入後以 is_sellable 為準
    Product.objects.filter(
        category=category,
        sku__in=["FG0064", "FG0065", "FG0066", "FG0067"],
    ).update(is_sellable=True)


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0005_product_fg0067"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="is_sellable",
            field=models.BooleanField(default=True, verbose_name="是否販售"),
        ),
        migrations.RunPython(seed_modified_starch_sellable, migrations.RunPython.noop),
    ]
