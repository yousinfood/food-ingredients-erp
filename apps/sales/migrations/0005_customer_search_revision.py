from django.db import migrations, models


def seed_revision(apps, schema_editor):
    CustomerSearchRevision = apps.get_model("sales", "CustomerSearchRevision")
    CustomerSearchRevision.objects.get_or_create(pk=1, defaults={"version": 0})


class Migration(migrations.Migration):
    dependencies = [
        ("sales", "0004_customer_voice_aliases"),
    ]

    operations = [
        migrations.CreateModel(
            name="CustomerSearchRevision",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("version", models.PositiveBigIntegerField(default=0, verbose_name="版本")),
            ],
            options={
                "verbose_name": "客戶搜尋版本",
                "verbose_name_plural": "客戶搜尋版本",
            },
        ),
        migrations.RunPython(seed_revision, migrations.RunPython.noop),
    ]
