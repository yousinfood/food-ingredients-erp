from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0008_alter_product_is_for_sale"),
        migrations.swappable_dependency("auth.user"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="minimum_margin_rate",
            field=models.DecimalField(
                decimal_places=4,
                default=Decimal("0.0500"),
                max_digits=5,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("0")),
                    django.core.validators.MaxValueValidator(Decimal("1")),
                ],
                verbose_name="最低毛利率",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="target_margin_rate",
            field=models.DecimalField(
                decimal_places=4,
                default=Decimal("0.2500"),
                help_text="例：0.25 = 25%",
                max_digits=5,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("0")),
                    django.core.validators.MaxValueValidator(Decimal("1")),
                ],
                verbose_name="目標毛利率",
            ),
        ),
        migrations.AddField(
            model_name="product",
            name="warning_margin_rate",
            field=models.DecimalField(
                decimal_places=4,
                default=Decimal("0.1500"),
                max_digits=5,
                validators=[
                    django.core.validators.MinValueValidator(Decimal("0")),
                    django.core.validators.MaxValueValidator(Decimal("1")),
                ],
                verbose_name="預警毛利率",
            ),
        ),
        migrations.CreateModel(
            name="ProductCostHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "unit_cost",
                    models.DecimalField(
                        decimal_places=4,
                        max_digits=12,
                        validators=[django.core.validators.MinValueValidator(Decimal("0"))],
                        verbose_name="單位成本",
                    ),
                ),
                ("effective_at", models.DateTimeField(verbose_name="生效時間")),
                (
                    "previous_cost",
                    models.DecimalField(
                        blank=True, decimal_places=4, max_digits=12, null=True, verbose_name="前次成本"
                    ),
                ),
                (
                    "change_amount",
                    models.DecimalField(
                        blank=True, decimal_places=4, max_digits=12, null=True, verbose_name="成本變動"
                    ),
                ),
                (
                    "change_percent",
                    models.DecimalField(
                        blank=True, decimal_places=4, max_digits=8, null=True, verbose_name="成本漲幅"
                    ),
                ),
                (
                    "source",
                    models.CharField(
                        choices=[
                            ("manual", "手動"),
                            ("import", "匯入"),
                            ("purchase", "採購"),
                            ("sync", "同步"),
                        ],
                        default="manual",
                        max_length=20,
                        verbose_name="來源",
                    ),
                ),
                ("note", models.TextField(blank=True, verbose_name="備註")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="建立時間")),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="product_cost_history_created",
                        to="auth.user",
                        verbose_name="建立人",
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="cost_history",
                        to="inventory.product",
                        verbose_name="產品",
                    ),
                ),
            ],
            options={
                "verbose_name": "產品成本歷史",
                "verbose_name_plural": "產品成本歷史",
                "ordering": ["-effective_at", "-pk"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("product", "effective_at"),
                        name="inventory_unique_product_cost_effective_at",
                    ),
                ],
            },
        ),
    ]
