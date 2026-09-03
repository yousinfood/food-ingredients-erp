from django.db import migrations, models


def ensure_walk_in_customer(apps, schema_editor):
    Customer = apps.get_model("sales", "Customer")
    Customer.objects.get_or_create(
        code="WALK-IN",
        defaults={
            "name": "現場客",
            "is_active": True,
            "notes": "系統共用現場客；每筆訂單以 SalesOrder.is_walk_in 標記，勿刪除。",
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0011_special_price_audit_log"),
    ]

    operations = [
        migrations.AddField(
            model_name="salesorder",
            name="is_walk_in",
            field=models.BooleanField(default=False, verbose_name="現場客訂單"),
        ),
        migrations.AddField(
            model_name="salesorder",
            name="walk_in_contact_label",
            field=models.CharField(
                blank=True,
                help_text="選填：姓名或店名（未來歸戶用）",
                max_length=200,
                verbose_name="現場客稱呼",
            ),
        ),
        migrations.AddField(
            model_name="salesorder",
            name="walk_in_phone",
            field=models.CharField(
                blank=True,
                help_text="選填：電話（未來歸戶用）",
                max_length=30,
                verbose_name="現場客電話",
            ),
        ),
        migrations.RunPython(ensure_walk_in_customer, migrations.RunPython.noop),
    ]
