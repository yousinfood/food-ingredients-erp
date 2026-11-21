"""FG0047/FG0048 接單分類改為有信品牌粉（僅 category，不影響料號／價格／歷史訂單）。"""

from django.db import migrations

SKUS = ("FG0047", "FG0048")
BRAND_FLOUR = "有信品牌粉"


def set_brand_flour_category(apps, schema_editor):
    Product = apps.get_model("inventory", "Product")
    Product.objects.filter(sku__in=SKUS).update(category=BRAND_FLOUR)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0011_fg0047_fg0048_natural_starch_category"),
    ]

    operations = [
        migrations.RunPython(set_brand_flour_category, noop_reverse),
    ]