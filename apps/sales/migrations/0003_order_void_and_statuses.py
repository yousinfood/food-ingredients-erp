from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def migrate_legacy_statuses(apps, schema_editor):
    SalesOrder = apps.get_model("sales", "SalesOrder")
    SalesOrder.objects.filter(status="picking").update(status="confirmed")
    SalesOrder.objects.filter(status="delivered").update(status="completed")


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("sales", "0002_customer_credit_limit_customer_delivery_day_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="salesorder",
            name="cancelled_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="作廢時間"),
        ),
        migrations.AddField(
            model_name="salesorder",
            name="cancelled_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="sales_orders_cancelled",
                to=settings.AUTH_USER_MODEL,
                verbose_name="作廢人",
            ),
        ),
        migrations.AlterField(
            model_name="salesorder",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="sales_orders_created",
                to=settings.AUTH_USER_MODEL,
                verbose_name="建立人",
            ),
        ),
        migrations.AlterField(
            model_name="salesorder",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "草稿"),
                    ("created", "已建立"),
                    ("confirmed", "已確認"),
                    ("shipped", "已出貨"),
                    ("completed", "已完成"),
                    ("cancelled", "已作廢"),
                ],
                default="draft",
                max_length=20,
                verbose_name="狀態",
            ),
        ),
        migrations.RunPython(migrate_legacy_statuses, migrations.RunPython.noop),
    ]
