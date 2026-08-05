from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.inventory.models import Product
from apps.sales.models import Customer, SalesOrderItem


class SalesOrderItemSnapshotRegressionTests(TestCase):
    def setUp(self):
        self.client = Client()
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="snapshot-tester", password="test")
        self.client.force_login(self.user)
        self.customer = Customer.objects.create(code="SNAP-001", name="快照測試客戶", is_active=True)
        self.product = Product.objects.create(
            sku="SNAP-P1",
            name="快照測試商品",
            is_active=True,
            is_for_sale=True,
            product_kind=Product.ProductKind.FINISHED,
        )
        session = self.client.session
        session["sales_order_nonce"] = "test-nonce-snapshot"
        session.save()

    def _post_order(self, unit_price: str = "88.00"):
        return self.client.post(
            reverse("sales:sales_order_create"),
            {
                "customer": str(self.customer.pk),
                "order_nonce": "test-nonce-snapshot",
                "order_date": "2026-08-05",
                "item_product_id": [str(self.product.pk)],
                "item_quantity": ["2"],
                "item_unit_price": [unit_price],
            },
        )

    @patch("apps.sales.views.SalesOrderItem.objects.create")
    def test_create_order_item_passes_sale_price_snapshot_equal_to_unit_price(self, mock_create):
        mock_create.return_value = MagicMock()
        response = self._post_order("88.00")
        self.assertIn(response.status_code, (302, 303), response.url)
        self.assertIn("saved=", response.url)
        mock_create.assert_called_once()
        kwargs = mock_create.call_args.kwargs
        self.assertEqual(kwargs["unit_price"], Decimal("88.00"))
        self.assertIsNotNone(kwargs["sale_price_snapshot"])
        self.assertEqual(kwargs["sale_price_snapshot"], kwargs["unit_price"])

    @patch("apps.sales.views.SalesOrderItem.objects.create")
    def test_create_order_item_passes_snapshot_when_unit_price_is_zero(self, mock_create):
        mock_create.return_value = MagicMock()
        response = self._post_order("0")
        self.assertIn(response.status_code, (302, 303), response.url)
        self.assertIn("saved=", response.url)
        mock_create.assert_called_once()
        kwargs = mock_create.call_args.kwargs
        self.assertIsNotNone(kwargs["sale_price_snapshot"])
        self.assertEqual(kwargs["sale_price_snapshot"], Decimal("0"))
        self.assertEqual(kwargs["sale_price_snapshot"], kwargs["unit_price"])
