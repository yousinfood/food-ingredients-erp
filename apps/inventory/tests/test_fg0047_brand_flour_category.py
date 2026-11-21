import importlib

from django.apps import apps as django_apps
from django.test import TestCase

from apps.inventory.models import Product
from apps.inventory.services.product_import import run_sync_from_rows
from apps.sales.services.product_search import search_saleable_products


class Fg0047BrandFlourCategoryTests(TestCase):
    def setUp(self):
        base = dict(
            product_kind=Product.ProductKind.FINISHED,
            unit=Product.Unit.PACK,
            is_active=True,
            is_for_sale=True,
            is_sellable=True,
        )
        Product.objects.create(
            sku="FG0047",
            name="忠／小粗粒粉",
            category="天然澱粉",
            **base,
        )
        Product.objects.create(
            sku="FG0048",
            name="忠／中粗粒粉",
            category="天然澱粉",
            **base,
        )

    def test_migration_sets_brand_flour_category(self):
        mig = importlib.import_module(
            "apps.inventory.migrations.0012_fg0047_fg0048_brand_flour_category"
        )
        mig.set_brand_flour_category(django_apps, None)
        self.assertEqual(Product.objects.get(sku="FG0047").category, "有信品牌粉")
        self.assertEqual(Product.objects.get(sku="FG0048").category, "有信品牌粉")

    def test_sheet_sync_does_not_overwrite_category(self):
        Product.objects.filter(sku__in=("FG0047", "FG0048")).update(category="有信品牌粉")
        rows = [
            ["產品編號", "產品名稱", "產品分類", "單位", "是否販售", "可做原料", "啟用"],
            ["FG0047", "忠／小粗粒粉", "天然澱粉", "包", "✓", "✗", "✓"],
            ["FG0048", "忠／中粗粒粉", "天然澱粉", "包", "✓", "✗", "✓"],
        ]
        run_sync_from_rows(rows)
        self.assertEqual(Product.objects.get(sku="FG0047").category, "有信品牌粉")
        self.assertEqual(Product.objects.get(sku="FG0048").category, "有信品牌粉")

    def test_brand_flour_api_includes_fg0047_fg0048(self):
        Product.objects.filter(sku__in=("FG0047", "FG0048")).update(category="有信品牌粉")
        rows = search_saleable_products(category="有信品牌粉", limit=80)
        skus = {p.sku for p in rows}
        self.assertIn("FG0047", skus)
        self.assertIn("FG0048", skus)