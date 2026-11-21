"""Ensure 忠粒粉 SKUs appear under 接單「天然澱粉」API（僅更新 category，不新增商品）。"""

from django.db import migrations

GRANULE_SKUS = ("FG0047", "FG0048")
NATURAL_STARCH = "天然澱粉"


def set_natural_starch_category(apps, schema_editor):
    Product = apps.get_model("inventory", "Product")
    Product.objects.filter(sku__in=GRANULE_SKUS).exclude(category=NATURAL_STARCH).update(
        category=NATURAL_STARCH
    )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0010_alter_product_unit_add_pack"),
    ]

    operations = [
        migrations.RunPython(set_natural_starch_category, noop_reverse),
    ]