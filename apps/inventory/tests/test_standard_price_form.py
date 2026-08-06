from decimal import Decimal

from django.test import TestCase

from apps.inventory.forms import ProductForm
from apps.inventory.models import Product


class ProductStandardPriceFormTests(TestCase):
    def test_product_form_includes_standard_price(self):
        product = Product.objects.create(sku="RM-FORM-01", name="表單測試")

        form = ProductForm(
            {
                "sku": product.sku,
                "name": product.name,
                "category": "",
                "brand": "",
                "series": "",
                "sales_unit": product.sales_unit,
                "net_weight_value": "",
                "net_weight_unit": "",
                "unit": product.unit,
                "shelf_life_days": product.shelf_life_days,
                "storage_temp_min": "",
                "storage_temp_max": "",
                "description": "",
                "standard_price": "40.00",
                "is_active": "on",
            },
            instance=product,
        )

        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        saved.refresh_from_db()
        self.assertEqual(saved.standard_price, Decimal("40.00"))
