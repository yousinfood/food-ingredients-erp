from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.inventory.models import Product
from apps.sales.models import Customer, CustomerProductPrice, SalesOrder, SalesOrderItem


class SalesOrderTouchPricingTests(TestCase):
    def setUp(self):
        self.client = Client()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="touch-pricing", password="test")
        self.client.force_login(self.user)
        self.customer = Customer.objects.create(code="QINGYOU", name="清遊紅豆餅", is_active=True)
        self.product = Product.objects.create(
            sku="FG0029",
            name="青葉",
            is_active=True,
            is_for_sale=True,
            product_kind=Product.ProductKind.FINISHED,
            standard_price=Decimal("580"),
        )
        session = self.client.session
        session["sales_order_nonce"] = "touch-pricing-nonce"
        session.save()

    def _post_order(self, *, unit_prices=None):
        unit_prices = unit_prices if unit_prices is not None else ["580"]
        return self.client.post(
            reverse("sales:sales_order_create"),
            {
                "customer": str(self.customer.pk),
                "order_nonce": "touch-pricing-nonce",
                "order_date": "2026-08-06",
                "item_product_id": [str(self.product.pk)],
                "item_quantity": ["10"],
                "item_unit_price": unit_prices,
            },
        )

    def test_posted_zero_unit_price_resolves_to_standard_price(self):
        response = self._post_order(unit_prices=["0"])
        self.assertIn(response.status_code, (302, 303), getattr(response, "url", response.content))
        order = SalesOrder.objects.order_by("-pk").first()
        item = SalesOrderItem.objects.get(sales_order=order, product=self.product)
        self.assertEqual(item.unit_price, Decimal("580"))
        self.assertEqual(item.sale_price_snapshot, Decimal("580"))
        self.assertEqual(item.price_source, "standard")
        self.assertEqual(item.line_total, Decimal("5800"))
        self.assertEqual(order.total_amount, Decimal("5800"))

    def test_posted_missing_unit_price_resolves_to_standard_price(self):
        response = self.client.post(
            reverse("sales:sales_order_create"),
            {
                "customer": str(self.customer.pk),
                "order_nonce": "touch-pricing-nonce",
                "order_date": "2026-08-06",
                "item_product_id": [str(self.product.pk)],
                "item_quantity": ["10"],
            },
        )
        self.assertIn(response.status_code, (302, 303))
        item = SalesOrderItem.objects.get(
            sales_order=SalesOrder.objects.order_by("-pk").first(),
            product=self.product,
        )
        self.assertEqual(item.unit_price, Decimal("580"))
        self.assertEqual(item.line_total, Decimal("5800"))

    def test_posted_valid_unit_price_is_kept(self):
        response = self._post_order(unit_prices=["580"])
        self.assertIn(response.status_code, (302, 303))
        item = SalesOrderItem.objects.get(
            sales_order=SalesOrder.objects.order_by("-pk").first(),
            product=self.product,
        )
        self.assertEqual(item.unit_price, Decimal("580"))
        self.assertEqual(item.line_total, Decimal("5800"))

    def test_customer_price_overrides_standard_on_backend_fallback(self):
        CustomerProductPrice.objects.create(
            customer=self.customer,
            product=self.product,
            price=Decimal("550"),
            effective_from=timezone.localdate(),
        )
        response = self._post_order(unit_prices=["0"])
        self.assertIn(response.status_code, (302, 303))
        item = SalesOrderItem.objects.get(
            sales_order=SalesOrder.objects.order_by("-pk").first(),
            product=self.product,
        )
        self.assertEqual(item.unit_price, Decimal("550"))
        self.assertEqual(item.price_source, "customer")
        self.assertEqual(item.line_total, Decimal("5500"))
