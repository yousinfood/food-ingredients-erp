import importlib

from django.apps import apps as django_apps
from django.test import TestCase

from apps.inventory.models import Product
from apps.inventory.services.product_import import category_from_sheet_row
from apps.sales.services.product_search import search_saleable_products


class Fg0047GranuleCategoryTests(TestCase):
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
            category="有信品牌粉",
            **base,
        )
        Product.objects.create(
            sku="FG0048",
            name="忠／中粗粒粉",
            category="",
            **base,
        )

    def test_migration_sets_natural_starch_category(self):
        mig = importlib.import_module(
            "apps.inventory.migrations.0011_fg0047_fg0048_natural_starch_category"
        )
        mig.set_natural_starch_category(django_apps, None)
        self.assertEqual(Product.objects.get(sku="FG0047").category, "天然澱粉")
        self.assertEqual(Product.objects.get(sku="FG0048").category, "天然澱粉")

    def test_sheet_sync_category_lock_for_granule_skus(self):
        self.assertEqual(
            category_from_sheet_row("FG0047", "有信品牌粉"),
            "天然澱粉",
        )
        self.assertEqual(category_from_sheet_row("FG9999", "有信品牌粉"), "有信品牌粉")

    def test_natural_starch_api_includes_fg0047_fg0048(self):
        Product.objects.filter(sku__in=("FG0047", "FG0048")).update(category="天然澱粉")
        rows = search_saleable_products(category="天然澱粉", limit=80)
        skus = {p.sku for p in rows}
        self.assertIn("FG0047", skus)
        self.assertIn("FG0048", skus)