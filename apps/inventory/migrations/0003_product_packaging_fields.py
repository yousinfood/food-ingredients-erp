from decimal import Decimal

from django.db import migrations, models

from apps.inventory.packaging import parse_packaging_spec


def forwards_populate_packaging(apps, schema_editor):
    Product = apps.get_model("inventory", "Product")
    for product in Product.objects.all():
        parsed = parse_packaging_spec(product.spec)
        if parsed:
            product.net_weight_value = parsed.get("net_weight_value")
            product.net_weight_unit = parsed.get("net_weight_unit", "")
            product.sales_unit = parsed.get("sales_unit", "pack")
        elif product.unit == "kg":
            product.sales_unit = "kg"
        elif product.unit == "box":
            product.sales_unit = "pack"
        else:
            product.sales_unit = "pack"
        product.save(
            update_fields=["sales_unit", "net_weight_value", "net_weight_unit"]
        )


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0002_alter_product_options_product_can_be_raw_material_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="net_weight_unit",
            field=models.CharField(
                blank=True,
                choices=[("g", "g"), ("kg", "kg")],
                max_length=5,
                verbose_name="淨重單位",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="net_weight_value",
            field=models.DecimalField(
                blank=True,
                decimal_places=3,
                max_digits=12,
                null=True,
                verbose_name="淨重",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="sales_unit",
            field=models.CharField(
                choices=[
                    ("pack", "包"),
                    ("can", "罐"),
                    ("bag", "袋"),
                    ("box", "箱"),
                    ("kg", "kg"),
                ],
                default="pack",
                max_length=10,
                verbose_name="銷售單位",
            ),
        ),
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
                ],
                default="kg",
                max_length=10,
                verbose_name="庫存單位",
            ),
        ),
        migrations.RunPython(forwards_populate_packaging, migrations.RunPython.noop),
    ]
