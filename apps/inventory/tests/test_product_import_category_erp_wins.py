from decimal import Decimal

from django.test import TestCase

from apps.inventory.models import Product
from apps.inventory.services.product_import import (
    ProductImportReport,
    execute_import,
    run_sync_from_rows,
)


class ProductImportCategoryErpWinsTests(TestCase):
    def _base_product(self, **kwargs):
        defaults = dict(
            product_kind=Product.ProductKind.FINISHED,
            unit=Product.Unit.PACK,
            is_active=True,
            is_for_sale=True,
            is_sellable=True,
        )
        defaults.update(kwargs)
        return defaults

    def test_execute_import_preserves_category_on_update(self):
        Product.objects.create(
            sku="FG-ERP-CAT",
            name="測試品",
            category="天然澱粉",
            **self._base_product(),
        )
        report = ProductImportReport()
        report._parsed_rows = [
            {
                "row_number": 2,
                "sku": "FG-ERP-CAT",
                "name": "測試品（Sheet 名稱）",
                "category": "有信品牌粉",
                "brand": "",
                "series": "",
                "spec": "",
                "unit_label": "包",
                "is_for_sale": True,
                "is_sellable": True,
                "can_be_raw_material": False,
                "is_active": True,
                "notes": "",
                "unit_cost": None,
                "product_kind": Product.ProductKind.FINISHED,
                "packaging": {"sales_unit": Product.SalesUnit.PACK},
            }
        ]
        execute_import(report)
        product = Product.objects.get(sku="FG-ERP-CAT")
        self.assertEqual(product.category, "天然澱粉")
        self.assertEqual(product.name, "測試品（Sheet 名稱）")

    def test_execute_import_sets_category_on_create(self):
        report = ProductImportReport()
        report._parsed_rows = [
            {
                "row_number": 2,
                "sku": "FG-NEW-CAT",
                "name": "新商品",
                "category": "糖",
                "brand": "",
                "series": "",
                "spec": "",
                "unit_label": "包",
                "is_for_sale": True,
                "is_sellable": True,
                "can_be_raw_material": False,
                "is_active": True,
                "notes": "",
                "unit_cost": None,
                "product_kind": Product.ProductKind.FINISHED,
                "packaging": {"sales_unit": Product.SalesUnit.PACK},
            }
        ]
        execute_import(report)
        self.assertEqual(Product.objects.get(sku="FG-NEW-CAT").category, "糖")

    def test_run_sync_from_rows_preserves_fg0047_category(self):
        Product.objects.create(
            sku="FG0047",
            name="忠／小粗粒粉",
            category="天然澱粉",
            standard_price=Decimal("100"),
            **self._base_product(),
        )
        rows = [
            ["產品編號", "產品名稱", "產品分類", "單位", "是否販售", "可做原料", "啟用"],
            ["FG0047", "忠／小粗粒粉", "有信品牌粉", "包", "✓", "✗", "✓"],
        ]
        run_sync_from_rows(rows)
        p = Product.objects.get(sku="FG0047")
        self.assertEqual(p.category, "天然澱粉")
        self.assertEqual(p.standard_price, Decimal("100"))