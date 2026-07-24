from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.inventory.models import Batch, Product, Warehouse
from apps.procurement.models import PurchaseOrder, PurchaseOrderItem, Supplier
from apps.production.models import ProductionOrder, Recipe, RecipeItem
from apps.sales.models import Customer, SalesOrder, SalesOrderItem


class Command(BaseCommand):
    help = "載入食品原料 ERP 示範資料"

    def handle(self, *args, **options):
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser("admin", "admin@example.com", "admin123")
            self.stdout.write("已建立管理員帳號 admin / admin123")

        wh_ambient, _ = Warehouse.objects.get_or_create(
            code="WH-A01", defaults={"name": "常溫主倉", "temperature_zone": "ambient", "location": "新北市"}
        )
        wh_chilled, _ = Warehouse.objects.get_or_create(
            code="WH-C01", defaults={"name": "冷藏倉", "temperature_zone": "chilled", "location": "新北市"}
        )
        wh_frozen, _ = Warehouse.objects.get_or_create(
            code="WH-F01", defaults={"name": "冷凍倉", "temperature_zone": "frozen", "location": "新北市"}
        )

        products_data = [
            ("RM-FL001", "高筋麵粉", "麵粉類", "kg", 365, None, None),
            ("RM-SG001", "細砂糖", "糖類", "kg", 730, None, None),
            ("RM-BT001", "無鹽奶油", "油脂", "kg", 180, 0, 4),
            ("RM-ML001", "全脂鮮乳", "乳製品", "l", 7, 0, 4),
            ("RM-EG001", "雞蛋", "蛋品", "pcs", 30, 0, 4),
            ("RM-FG001", "綜合果乾", "果乾", "kg", 365, None, None),
            ("FG-BR001", "手工麵包", "成品", "pcs", 3, None, None),
        ]
        products = {}
        for sku, name, cat, unit, shelf, tmin, tmax in products_data:
            p, _ = Product.objects.get_or_create(
                sku=sku,
                defaults={
                    "name": name,
                    "category": cat,
                    "unit": unit,
                    "shelf_life_days": shelf,
                    "storage_temp_min": tmin,
                    "storage_temp_max": tmax,
                },
            )
            products[sku] = p

        today = timezone.localdate()
        batches_data = [
            ("RM-FL001", "B20250701", wh_ambient, Decimal("500"), today + timedelta(days=200)),
            ("RM-SG001", "B20250615", wh_ambient, Decimal("300"), today + timedelta(days=500)),
            ("RM-BT001", "B20250710", wh_chilled, Decimal("50"), today + timedelta(days=120)),
            ("RM-ML001", "B20250718", wh_chilled, Decimal("200"), today + timedelta(days=5)),
            ("RM-EG001", "B20250715", wh_chilled, Decimal("1000"), today + timedelta(days=15)),
            ("RM-FG001", "B20250601", wh_ambient, Decimal("80"), today + timedelta(days=25)),
        ]
        for sku, batch_no, wh, qty, expiry in batches_data:
            Batch.objects.get_or_create(
                product=products[sku],
                batch_no=batch_no,
                warehouse=wh,
                defaults={"quantity": qty, "expiry_date": expiry, "production_date": today - timedelta(days=30)},
            )

        sup, _ = Supplier.objects.get_or_create(
            code="SUP001",
            defaults={
                "name": "優質食品原料有限公司",
                "contact_person": "王經理",
                "phone": "02-1234-5678",
                "certification": "HACCP, ISO 22000",
            },
        )

        po, created = PurchaseOrder.objects.get_or_create(
            order_no="PO-202507-001",
            defaults={
                "supplier": sup,
                "status": "pending",
                "order_date": today,
                "expected_date": today + timedelta(days=7),
            },
        )
        if created:
            PurchaseOrderItem.objects.create(
                purchase_order=po, product=products["RM-FL001"], quantity=Decimal("1000"), unit_price=Decimal("28")
            )
            PurchaseOrderItem.objects.create(
                purchase_order=po, product=products["RM-SG001"], quantity=Decimal("500"), unit_price=Decimal("35")
            )

        recipe, created = Recipe.objects.get_or_create(
            code="RCP-BR001",
            defaults={
                "name": "手工麵包標準配方",
                "output_product": products["FG-BR001"],
                "output_qty": Decimal("100"),
                "version": "1.0",
            },
        )
        if created:
            RecipeItem.objects.create(recipe=recipe, ingredient=products["RM-FL001"], quantity=Decimal("5"), loss_rate=Decimal("2"))
            RecipeItem.objects.create(recipe=recipe, ingredient=products["RM-SG001"], quantity=Decimal("0.5"))
            RecipeItem.objects.create(recipe=recipe, ingredient=products["RM-BT001"], quantity=Decimal("1"), loss_rate=Decimal("1"))
            RecipeItem.objects.create(recipe=recipe, ingredient=products["RM-ML001"], quantity=Decimal("2"))
            RecipeItem.objects.create(recipe=recipe, ingredient=products["RM-EG001"], quantity=Decimal("20"))

        ProductionOrder.objects.get_or_create(
            order_no="MO-202507-001",
            defaults={
                "recipe": recipe,
                "planned_qty": Decimal("200"),
                "status": "in_progress",
                "planned_start": today,
                "planned_end": today + timedelta(days=1),
            },
        )

        customers_data = [
            ("CUS-001", "仁武早餐店", "陳先生", "07-1234567", "高雄市仁武區仁武路100號"),
            ("CUS-002", "新興米店", "林小姐", "06-2653595", "台南市金華路二段39巷97號"),
            ("CUS-003", "阿鳳浮水魚羹", "王老板", "06-2256646", "台南市保安路59號"),
        ]
        customers = {}
        for code, name, contact, phone, address in customers_data:
            c, _ = Customer.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "contact_person": contact,
                    "phone": phone,
                    "address": address,
                },
            )
            customers[code] = c

        order, created = SalesOrder.objects.get_or_create(
            order_no="SO-20250721-001",
            defaults={
                "customer": customers["CUS-001"],
                "status": "confirmed",
                "order_date": today,
                "delivery_date": today + timedelta(days=1),
                "shipping_address": customers["CUS-001"].address,
            },
        )
        if created:
            SalesOrderItem.objects.create(
                sales_order=order,
                product=products["RM-FL001"],
                quantity=Decimal("50"),
                unit_price=Decimal("32"),
            )
            SalesOrderItem.objects.create(
                sales_order=order,
                product=products["FG-BR001"],
                quantity=Decimal("100"),
                unit_price=Decimal("45"),
            )

        self.stdout.write(self.style.SUCCESS("示範資料載入完成！"))
