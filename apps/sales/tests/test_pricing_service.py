from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.inventory.models import Product, ProductCostHistory
from apps.sales.models import Customer, CustomerProductPrice
from apps.sales.services.pricing import PricingService


class PricingServiceTests(TestCase):
    def setUp(self):
        self.service = PricingService()
        self.product = Product.objects.create(
            sku="FG-P2-01",
            name="Phase2 測試品",
            unit_cost=Decimal("40.0000"),
            standard_price=Decimal("100.00"),
        )
        self.customer = Customer.objects.create(code="CUS-P2", name="Phase2 客戶")

    def test_standard_price_and_unit_cost(self):
        result = self.service.calculate(self.product)

        self.assertEqual(result.cost, Decimal("40.0000"))
        self.assertEqual(result.sale_price, Decimal("100.00"))
        self.assertEqual(result.gross_profit, Decimal("60.00"))
        self.assertEqual(result.gross_margin, Decimal("60.0000"))

    def test_customer_price_overrides_standard_price(self):
        CustomerProductPrice.objects.create(
            customer=self.customer,
            product=self.product,
            price=Decimal("80.00"),
            effective_from=date.today(),
            is_active=True,
        )

        result = self.service.calculate(self.product, self.customer)

        self.assertEqual(result.sale_price, Decimal("80.00"))
        self.assertEqual(result.gross_profit, Decimal("40.00"))
        self.assertEqual(result.gross_margin, Decimal("50.0000"))

    def test_cost_history_overrides_product_unit_cost(self):
        ProductCostHistory.objects.create(
            product=self.product,
            unit_cost=Decimal("55.0000"),
            effective_at=timezone.now(),
        )

        result = self.service.calculate(self.product)

        self.assertEqual(result.cost, Decimal("55.0000"))
        self.assertEqual(result.gross_profit, Decimal("45.00"))
        self.assertEqual(result.gross_margin, Decimal("45.0000"))

    def test_missing_sale_price_returns_none_profit_and_margin(self):
        self.product.standard_price = None
        self.product.save(update_fields=["standard_price"])

        result = self.service.calculate(self.product)

        self.assertIsNone(result.sale_price)
        self.assertIsNone(result.gross_profit)
        self.assertIsNone(result.gross_margin)

    def test_missing_cost_returns_none_profit_and_margin(self):
        self.product.unit_cost = None
        self.product.save(update_fields=["unit_cost"])

        result = self.service.calculate(self.product)

        self.assertEqual(result.sale_price, Decimal("100.00"))
        self.assertIsNone(result.cost)
        self.assertIsNone(result.gross_profit)
        self.assertIsNone(result.gross_margin)

    def test_expired_customer_price_falls_back_to_standard_price(self):
        CustomerProductPrice.objects.create(
            customer=self.customer,
            product=self.product,
            price=Decimal("70.00"),
            effective_from=date.today() - timedelta(days=30),
            effective_to=date.today() - timedelta(days=1),
            is_active=True,
        )

        result = self.service.calculate(self.product, self.customer)

        self.assertEqual(result.sale_price, Decimal("100.00"))

    def test_zero_sale_price_returns_none_margin(self):
        self.product.standard_price = Decimal("0.00")
        self.product.save(update_fields=["standard_price"])

        result = self.service.calculate(self.product)

        self.assertEqual(result.sale_price, Decimal("0.00"))
        self.assertIsNone(result.gross_margin)

    def test_phase3_standard_sale_price_margin(self):
        product = Product.objects.create(
            sku="RM-PH3-01",
            name="Phase3 標準售價測試",
            unit_cost=Decimal("29.0000"),
            standard_price=Decimal("40.00"),
        )

        result = self.service.calculate(product)

        self.assertEqual(result.cost, Decimal("29.0000"))
        self.assertEqual(result.sale_price, Decimal("40.00"))
        self.assertEqual(result.gross_profit, Decimal("11.00"))
        self.assertEqual(result.gross_margin, Decimal("27.5000"))
