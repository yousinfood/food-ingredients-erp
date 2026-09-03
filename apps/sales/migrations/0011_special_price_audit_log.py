from decimal import Decimal

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.core.validators import MinValueValidator


def backfill_special_price_audits(apps, schema_editor):
    SalesOrder = apps.get_model("sales", "SalesOrder")
    SalesOrderItem = apps.get_model("sales", "SalesOrderItem")
    SpecialPriceAuditLog = apps.get_model("sales", "SpecialPriceAuditLog")
    User = apps.get_model("auth", "User")

    fallback_user = User.objects.order_by("pk").first()
    logs = []
    for item in SalesOrderItem.objects.select_related("sales_order", "sales_order__customer", "product"):
        if item.unit_price == item.original_unit_price and item.discount_amount <= 0:
            continue
        order = item.sales_order
        user = order.created_by or fallback_user
        if user is None:
            continue
        unit_delta = item.unit_price - item.original_unit_price
        total_delta = unit_delta * item.quantity
        reason_code = order.special_price_reason or "other"
        reason_note = order.special_price_reason_note or ""
        if not order.special_price_reason and item.discount_amount > 0:
            reason_code = "other"
            reason_note = reason_note or "歷史資料補登"
        logs.append(
            SpecialPriceAuditLog(
                sales_order_id=order.pk,
                sales_order_item_id=item.pk,
                customer_id=order.customer_id,
                product_id=item.product_id,
                order_no=order.order_no,
                order_date=order.order_date,
                original_unit_price=item.original_unit_price,
                deal_unit_price=item.unit_price,
                unit_price_delta=unit_delta,
                quantity=item.quantity,
                total_delta=total_delta,
                reason_code=reason_code,
                reason_note=reason_note,
                changed_by_id=user.pk,
                changed_at=order.created_at,
            )
        )
    if logs:
        SpecialPriceAuditLog.objects.bulk_create(logs, batch_size=500)


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("inventory", "0010_alter_product_unit_add_pack"),
        ("sales", "0010_salesorder_special_price_reason"),
    ]

    operations = [
        migrations.AlterField(
            model_name="salesorder",
            name="special_price_reason",
            field=models.CharField(
                blank=True,
                choices=[
                    ("pre_increase", "漲價前優惠"),
                    ("bulk_purchase", "大量採購優惠"),
                    ("long_term_customer", "長期客戶優惠"),
                    ("special_favor", "特殊優待"),
                    ("compensation", "補償客戶"),
                    ("price_commitment", "報價承諾"),
                    ("other", "其他"),
                ],
                max_length=30,
                verbose_name="特殊成交原因",
            ),
        ),
        migrations.CreateModel(
            name="SpecialPriceAuditLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("order_no", models.CharField(max_length=30, verbose_name="訂單編號")),
                ("order_date", models.DateField(verbose_name="訂單日期")),
                (
                    "original_unit_price",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=12,
                        validators=[MinValueValidator(Decimal("0"))],
                        verbose_name="原售價",
                    ),
                ),
                (
                    "deal_unit_price",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=12,
                        validators=[MinValueValidator(Decimal("0"))],
                        verbose_name="成交價",
                    ),
                ),
                ("unit_price_delta", models.DecimalField(decimal_places=2, max_digits=12, verbose_name="單價價差")),
                (
                    "quantity",
                    models.DecimalField(
                        decimal_places=3,
                        max_digits=12,
                        validators=[MinValueValidator(Decimal("0.001"))],
                        verbose_name="數量",
                    ),
                ),
                ("total_delta", models.DecimalField(decimal_places=2, max_digits=14, verbose_name="總價差")),
                (
                    "reason_code",
                    models.CharField(
                        choices=[
                            ("pre_increase", "漲價前優惠"),
                            ("bulk_purchase", "大量採購優惠"),
                            ("long_term_customer", "長期客戶優惠"),
                            ("special_favor", "特殊優待"),
                            ("compensation", "補償客戶"),
                            ("price_commitment", "報價承諾"),
                            ("other", "其他"),
                        ],
                        max_length=30,
                        verbose_name="修改原因",
                    ),
                ),
                ("reason_note", models.CharField(blank=True, max_length=200, verbose_name="原因說明")),
                ("changed_at", models.DateTimeField(auto_now_add=True, verbose_name="修改時間")),
                (
                    "changed_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="special_price_audits",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="操作人員",
                    ),
                ),
                (
                    "customer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="special_price_audits",
                        to="sales.customer",
                        verbose_name="客戶",
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="special_price_audits",
                        to="inventory.product",
                        verbose_name="商品",
                    ),
                ),
                (
                    "sales_order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="special_price_audits",
                        to="sales.salesorder",
                        verbose_name="銷售訂單",
                    ),
                ),
                (
                    "sales_order_item",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="special_price_audits",
                        to="sales.salesorderitem",
                        verbose_name="銷售明細",
                    ),
                ),
            ],
            options={
                "verbose_name": "特殊成交價紀錄",
                "verbose_name_plural": "特殊成交價紀錄",
                "ordering": ["-changed_at", "-pk"],
                "indexes": [
                    models.Index(fields=["order_date", "customer"], name="sales_sp_audit_date_cust"),
                    models.Index(fields=["changed_by", "changed_at"], name="sales_sp_audit_user_time"),
                    models.Index(fields=["reason_code", "order_date"], name="sales_sp_audit_reason_date"),
                ],
            },
        ),
        migrations.RunPython(backfill_special_price_audits, migrations.RunPython.noop),
    ]
