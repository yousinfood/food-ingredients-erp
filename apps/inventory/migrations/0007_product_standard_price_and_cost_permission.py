from decimal import Decimal

import django.core.validators
from django.db import migrations, models


def add_pricing_cost_view_permission(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Permission = apps.get_model("auth", "Permission")
    content_type = ContentType.objects.filter(app_label="inventory", model="product").first()
    if content_type is None:
        return
    Permission.objects.get_or_create(
        codename="pricing_cost_view",
        content_type=content_type,
        defaults={"name": "Can view product unit cost"},
    )


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0006_product_is_sellable"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="standard_price",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="無客戶專屬價時的預設售價（銷售單位）",
                max_digits=12,
                null=True,
                validators=[django.core.validators.MinValueValidator(Decimal("0"))],
                verbose_name="標準售價",
            ),
        ),
        migrations.RunPython(add_pricing_cost_view_permission, migrations.RunPython.noop),
    ]
