from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0012_salesorder_walk_in"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="customerproductprice",
            constraint=models.UniqueConstraint(
                fields=("customer", "product"),
                condition=Q(is_active=True, effective_to__isnull=True),
                name="sales_cpp_unique_open_active_customer_product",
            ),
        ),
    ]
