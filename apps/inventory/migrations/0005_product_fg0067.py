"""Upsert FG0067 from sheet master (醋酸澱粉F300); does not touch other SKUs."""

from decimal import Decimal

from django.db import migrations


def upsert_fg0067(apps, schema_editor):
    Product = apps.get_model("inventory", "Product")
    Product.objects.update_or_create(
        sku="FG0067",
        defaults={
            "name": "醋酸澱粉F300",
            "category": "變性澱粉",
            "brand": "佳昌",
            "series": "",
            "spec": "25kg/1包",
            "product_kind": "finished",
            "unit": "pcs",
            "sales_unit": "pack",
            "net_weight_value": Decimal("25"),
            "net_weight_unit": "kg",
            "is_for_sale": True,
            "can_be_raw_material": False,
            "is_active": True,
        },
    )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0004_product_brand_series"),
    ]

    operations = [
        migrations.RunPython(upsert_fg0067, noop_reverse),
    ]
