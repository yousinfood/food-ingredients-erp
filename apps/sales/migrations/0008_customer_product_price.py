from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0009_product_pricing_and_cost_history"),
        ("sales", "0007_salesorderitem_price_source_version"),
    ]

    operations = [
        migrations.CreateModel(
            name="CustomerProductPrice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "price",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=12,
                        validators=[django.core.validators.MinValueValidator(Decimal("0"))],
                        verbose_name="售價",
                    ),
                ),
                ("effective_from", models.DateField(verbose_name="生效日")),
                ("effective_to", models.DateField(blank=True, null=True, verbose_name="失效日")),
                ("is_active", models.BooleanField(default=True, verbose_name="啟用")),
                ("note", models.TextField(blank=True, verbose_name="備註")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="建立時間")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="更新時間")),
                (
                    "customer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="product_prices",
                        to="sales.customer",
                        verbose_name="客戶",
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="customer_prices",
                        to="inventory.product",
                        verbose_name="產品",
                    ),
                ),
            ],
            options={
                "verbose_name": "客戶專屬售價",
                "verbose_name_plural": "客戶專屬售價",
                "ordering": ["-effective_from", "-pk"],
            },
        ),
        migrations.AddIndex(
            model_name="customerproductprice",
            index=models.Index(
                fields=["customer", "product", "is_active", "effective_from"],
                name="sales_custo_custome_6a8b0d_idx",
            ),
        ),
    ]
