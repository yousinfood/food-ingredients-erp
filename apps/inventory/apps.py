from decimal import Decimal

from django.apps import AppConfig
from django.db.utils import OperationalError, ProgrammingError


class InventoryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.inventory"
    verbose_name = "庫存管理"

    def ready(self):
        self._ensure_fg0067_from_sheet_master()

    @staticmethod
    def _ensure_fg0067_from_sheet_master():
        """Sheet 已登 FG0067；Production DB 缺列時補上（不動其他 SKU）。"""
        from apps.inventory.models import Product

        try:
            if Product.objects.filter(sku="FG0067").exists():
                return
        except (OperationalError, ProgrammingError):
            return

        Product.objects.update_or_create(
            sku="FG0067",
            defaults={
                "name": "醋酸澱粉F300",
                "category": "變性澱粉",
                "brand": "佳昌",
                "series": "",
                "spec": "25kg/1包",
                "product_kind": Product.ProductKind.FINISHED,
                "unit": Product.Unit.PCS,
                "sales_unit": Product.SalesUnit.PACK,
                "net_weight_value": Decimal("25"),
                "net_weight_unit": Product.NetWeightUnit.KG,
                "is_for_sale": True,
                "is_sellable": True,
                "can_be_raw_material": False,
                "is_active": True,
            },
        )
