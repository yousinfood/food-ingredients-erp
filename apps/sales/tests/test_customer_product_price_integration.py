from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.inventory.models import Product
from apps.sales.models import Customer, CustomerProductPrice
from apps.sales.services.customer_product_price import (
    build_price_map,
    enrich_product_pricing,
    resolve_sale_price_detail,
)
from apps.sales.services.product_search import product_to_dict


class CustomerProductPriceIntegrationTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(code="CPP-001", name="售價測試客戶", is_active=True)
        self.product = Product.objects.create(
            sku="CPP-P1",
            name="售價測試商品",
            is_active=True,
            is_for_sale=True,
            product_kind=Product.ProductKind.FINISHED,
            standard_price=Decimal("100.00"),
        )

    def test_standard_price_when_no_customer_price(self):
        price, source, version = resolve_sale_price_detail(self.product, self.customer)
        self.assertEqual(price, Decimal("100.00"))
        self.assertEqual(source, "standard")
        self.assertIsNone(version)

    def test_customer_price_overrides_standard(self):
        CustomerProductPrice.objects.create(
            customer=self.customer,
            product=self.product,
            price=Decimal("88.00"),
            effective_from=timezone.localdate(),
        )
        price, source, version = resolve_sale_price_detail(self.product, self.customer)
        self.assertEqual(price, Decimal("88.00"))
        self.assertEqual(source, "customer")
        self.assertIsNotNone(version)

    def test_build_price_map_and_enrich(self):
        CustomerProductPrice.objects.create(
            customer=self.customer,
            product=self.product,
            price=Decimal("77.00"),
            effective_from=timezone.localdate(),
        )
        price_map = build_price_map(self.customer, [self.product.pk])
        self.assertEqual(price_map[str(self.product.pk)], "77.00")
        item = enrich_product_pricing(product_to_dict(self.product), self.customer, self.product)
        self.assertEqual(item["resolved_unit_price"], "77.00")
        self.assertEqual(item["price_source"], "customer")

    def test_enrich_marks_price_unset_when_no_price(self):
        product = Product.objects.create(
            sku="CPP-NO-PRICE",
            name="無售價商品",
            is_active=True,
            is_for_sale=True,
            product_kind=Product.ProductKind.FINISHED,
            standard_price=None,
        )
        item = enrich_product_pricing(product_to_dict(product), self.customer, product)
        self.assertTrue(item["price_unset"])
        self.assertNotIn("resolved_unit_price", item)

    def test_acceptance_fg0029_standard_price_for_yizhong_customer(self):
        customer = Customer.objects.create(code="ACC-YIZHONG", name="一中街紅豆餅", is_active=True)
        product = Product.objects.create(
            sku="FG0029",
            name="青葉",
            is_active=True,
            is_for_sale=True,
            product_kind=Product.ProductKind.FINISHED,
            standard_price=Decimal("580"),
        )
        price, source, version = resolve_sale_price_detail(product, customer)
        self.assertEqual(price, Decimal("580"))
        self.assertEqual(source, "standard")
        self.assertEqual(build_price_map(customer, [product.pk])[str(product.pk)], "580.00")

        qty = Decimal("10")
        self.assertEqual(qty * price, Decimal("5800"))

    def test_pricing_resolve_api_returns_standard_price(self):
        customer = Customer.objects.create(code="ACC-API", name="一中街紅豆餅", is_active=True)
        product = Product.objects.create(
            sku="FG0029",
            name="青葉",
            is_active=True,
            is_for_sale=True,
            product_kind=Product.ProductKind.FINISHED,
            standard_price=Decimal("580"),
        )
        url = reverse("sales:pricing_resolve_api")
        response = self.client.get(
            url,
            {"customer": customer.pk, "product_id": product.pk},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["unit_price"], "580.00")
        self.assertEqual(data["price_source"], "standard")
        self.assertFalse(data["price_unset"])

    def test_product_search_api_enriches_price_for_customer(self):
        product = Product.objects.create(
            sku="FG0029",
            name="青葉",
            category="天然澱粉",
            is_active=True,
            is_for_sale=True,
            product_kind=Product.ProductKind.FINISHED,
            standard_price=Decimal("580"),
        )
        url = reverse("sales:product_search_api")
        response = self.client.get(
            url,
            {"q": "FG0029", "customer": self.customer.pk},
        )
        self.assertEqual(response.status_code, 200)
        results = response.json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["resolved_unit_price"], "580.00")
        self.assertEqual(results[0]["price_source"], "standard")
        self.assertEqual(results[0]["id"], product.pk)
