"""語音別名：國語／台語音近字容錯。"""

from django.db import migrations, models


def seed_huadu_voice_aliases(apps, schema_editor):
    Customer = apps.get_model("sales", "Customer")
    Customer.objects.filter(name="華都小籠包").update(
        voice_aliases="華都, 花都, 華豆, 花豆"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("sales", "0003_order_void_and_statuses"),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="voice_aliases",
            field=models.CharField(
                blank=True,
                help_text="平常稱呼與台語音近字，逗號分隔。例：華都, 花都, 華豆",
                max_length=500,
                verbose_name="語音別名",
            ),
        ),
        migrations.RunPython(seed_huadu_voice_aliases, migrations.RunPython.noop),
    ]
