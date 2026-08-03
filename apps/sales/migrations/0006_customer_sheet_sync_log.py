from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("sales", "0005_customer_search_revision"),
    ]

    operations = [
        migrations.CreateModel(
            name="CustomerSheetSyncLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("synced_at", models.DateTimeField(auto_now_add=True, verbose_name="同步時間")),
                (
                    "triggered_by",
                    models.CharField(
                        choices=[("command", "指令"), ("admin", "管理頁"), ("webhook", "Webhook")],
                        default="command",
                        max_length=20,
                        verbose_name="觸發來源",
                    ),
                ),
                ("ok", models.BooleanField(default=False, verbose_name="成功")),
                ("created_count", models.PositiveIntegerField(default=0, verbose_name="新增")),
                ("updated_count", models.PositiveIntegerField(default=0, verbose_name="更新")),
                ("skipped_count", models.PositiveIntegerField(default=0, verbose_name="略過")),
                ("error_count", models.PositiveIntegerField(default=0, verbose_name="錯誤")),
                ("error_details", models.JSONField(blank=True, default=list, verbose_name="錯誤明細")),
                ("message", models.CharField(blank=True, max_length=500, verbose_name="摘要")),
            ],
            options={
                "verbose_name": "客戶 Sheet 同步紀錄",
                "verbose_name_plural": "客戶 Sheet 同步紀錄",
                "ordering": ["-synced_at"],
            },
        ),
    ]
