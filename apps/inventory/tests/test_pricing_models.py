from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.inventory.models import Product, ProductCostHistory


class ProductPricingModelTests(TestCase):
    def test_negative_standard_price_fails(self):
        product = Product(
            sku="M-001",
            name="測試",
            standard_price=Decimal("-1.00"),
        )
        with self.assertRaises(ValidationError):
            product.full_clean()

    def test_margin_rate_above_one_fails(self):
        product = Product(
            sku="M-002",
            name="測試",
            target_margin_rate=Decimal("1.5000"),
        )
        with self.assertRaises(ValidationError):
            product.full_clean()

    def test_margin_rate_order_validation(self):
        product = Product(
            sku="M-003",
            name="測試",
            minimum_margin_rate=Decimal("0.2000"),
            warning_margin_rate=Decimal("0.1500"),
            target_margin_rate=Decimal("0.2500"),
        )
        with self.assertRaises(ValidationError):
            product.full_clean()

    def test_margin_rate_equal_one_fails(self):
        product = Product(
            sku="M-005",
            name="測試",
            minimum_margin_rate=Decimal("0.0500"),
            warning_margin_rate=Decimal("0.1500"),
            target_margin_rate=Decimal("1.0000"),
        )
        with self.assertRaises(ValidationError):
            product.full_clean()

    def test_valid_margin_rate_order_passes(self):
        product = Product(
            sku="M-004",
            name="測試",
            minimum_margin_rate=Decimal("0.0500"),
            warning_margin_rate=Decimal("0.1500"),
            target_margin_rate=Decimal("0.2500"),
        )
        product.full_clean()
        product.save()
        self.assertTrue(Product.objects.filter(sku="M-004").exists())


class ProductCostHistoryModelTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(sku="C-001", name="成本測試")

    def test_negative_unit_cost_fails(self):
        row = ProductCostHistory(
            product=self.product,
            unit_cost=Decimal("-1.0000"),
            effective_at=timezone.now(),
        )
        with self.assertRaises(ValidationError):
            row.full_clean()

    def test_cost_history_cannot_be_updated_via_save(self):
        row = ProductCostHistory.objects.create(
            product=self.product,
            unit_cost=Decimal("10.0000"),
            effective_at=timezone.now(),
        )
        row.unit_cost = Decimal("12.0000")
        with self.assertRaises(ValidationError):
            row.save()

    def test_cost_history_note_can_be_updated(self):
        row = ProductCostHistory.objects.create(
            product=self.product,
            unit_cost=Decimal("10.0000"),
            effective_at=timezone.now(),
            note="原始備註",
        )
        row.note = "更新備註"
        row.save()
        row.refresh_from_db()
        self.assertEqual(row.note, "更新備註")
        self.assertEqual(row.unit_cost, Decimal("10.0000"))

    def test_duplicate_effective_at_for_same_product_fails(self):
        effective_at = timezone.now()
        ProductCostHistory.objects.create(
            product=self.product,
            unit_cost=Decimal("10.0000"),
            effective_at=effective_at,
        )
        duplicate = ProductCostHistory(
            product=self.product,
            unit_cost=Decimal("11.0000"),
            effective_at=effective_at,
        )
        with self.assertRaises(ValidationError):
            duplicate.save()

    def test_cost_history_cannot_be_updated_via_queryset(self):
        ProductCostHistory.objects.create(
            product=self.product,
            unit_cost=Decimal("10.0000"),
            effective_at=timezone.now(),
        )
        with self.assertRaises(ValidationError):
            ProductCostHistory.objects.filter(product=self.product).update(
                unit_cost=Decimal("99.0000")
            )

    def test_cost_history_cannot_be_deleted_via_instance(self):
        row = ProductCostHistory.objects.create(
            product=self.product,
            unit_cost=Decimal("10.0000"),
            effective_at=timezone.now(),
        )
        with self.assertRaises(ValidationError):
            row.delete()

    def test_cost_history_cannot_be_deleted_via_queryset(self):
        ProductCostHistory.objects.create(
            product=self.product,
            unit_cost=Decimal("10.0000"),
            effective_at=timezone.now(),
        )
        with self.assertRaises(ValidationError):
            ProductCostHistory.objects.filter(product=self.product).delete()

    def test_cost_history_computes_change_fields_on_create(self):
        base = timezone.now()
        ProductCostHistory.objects.create(
            product=self.product,
            unit_cost=Decimal("10.0000"),
            effective_at=base - timedelta(days=2),
        )
        newer = ProductCostHistory.objects.create(
            product=self.product,
            unit_cost=Decimal("12.0000"),
            effective_at=base - timedelta(days=1),
        )
        self.assertEqual(newer.previous_cost, Decimal("10.0000"))
        self.assertEqual(newer.change_amount, Decimal("2.0000"))
        self.assertEqual(newer.change_percent, Decimal("0.2000"))

    def test_get_latest_for_product_by_effective_at(self):
        base = timezone.now()
        older = ProductCostHistory.objects.create(
            product=self.product,
            unit_cost=Decimal("10.0000"),
            effective_at=base - timedelta(days=2),
        )
        newer = ProductCostHistory.objects.create(
            product=self.product,
            unit_cost=Decimal("12.0000"),
            effective_at=base - timedelta(days=1),
        )
        latest = ProductCostHistory.get_latest_for_product(self.product, as_of=base)
        self.assertEqual(latest.pk, newer.pk)
        self.assertNotEqual(latest.pk, older.pk)

        as_of_past = base - timedelta(days=1, hours=12)
        past_latest = ProductCostHistory.get_latest_for_product(self.product, as_of=as_of_past)
        self.assertEqual(past_latest.pk, older.pk)

    def test_get_latest_for_product_returns_none_when_empty(self):
        self.assertIsNone(
            ProductCostHistory.get_latest_for_product(self.product, as_of=timezone.now())
        )
