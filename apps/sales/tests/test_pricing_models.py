from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.inventory.models import Product
from apps.sales.models import Customer, CustomerProductPrice


class CustomerProductPriceModelTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(code="M-C01", name="模型測試客戶")
        self.product = Product.objects.create(sku="M-P01", name="模型測試產品", is_for_sale=True)

    def _price(self, **kwargs):
        defaults = {
            "customer": self.customer,
            "product": self.product,
            "price": Decimal("100.00"),
            "effective_from": date(2026, 1, 1),
            "is_active": True,
        }
        defaults.update(kwargs)
        return CustomerProductPrice(**defaults)

    def test_negative_price_fails(self):
        row = self._price(price=Decimal("-5.00"))
        with self.assertRaises(ValidationError):
            row.full_clean()

    def test_effective_to_before_from_fails(self):
        row = self._price(
            effective_from=date(2026, 6, 1),
            effective_to=date(2026, 1, 1),
        )
        with self.assertRaises(ValidationError):
            row.full_clean()

    def test_overlapping_active_periods_fail_on_full_clean(self):
        self._price(
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 12, 31),
        ).save()

        overlap = self._price(
            effective_from=date(2026, 3, 1),
            effective_to=date(2026, 8, 1),
        )
        with self.assertRaises(ValidationError):
            overlap.full_clean()

    def test_open_ended_overlap_fails_on_full_clean(self):
        self._price(effective_from=date(2026, 1, 1)).save()
        overlap = self._price(effective_from=date(2026, 3, 1))
        with self.assertRaises(ValidationError):
            overlap.full_clean()

    def test_same_effective_from_active_prices_fail(self):
        self._price(effective_from=date(2026, 6, 1)).save()
        duplicate = self._price(
            effective_from=date(2026, 6, 1),
            price=Decimal("110.00"),
        )
        with self.assertRaises(ValidationError):
            duplicate.save()

    def test_new_price_auto_closes_prior_active_price(self):
        old = self._price(effective_from=date(2026, 1, 1))
        old.save()
        self.assertIsNone(old.effective_to)

        new_row = self._price(
            effective_from=date(2026, 6, 1),
            price=Decimal("110.00"),
        )
        new_row.save()

        old.refresh_from_db()
        new_row.refresh_from_db()
        self.assertEqual(old.effective_to, date(2026, 5, 31))
        self.assertEqual(new_row.effective_from, date(2026, 6, 1))

    def test_new_price_auto_closes_open_ended_prior_without_manual_step(self):
        self._price(effective_from=date(2026, 1, 1)).save()
        self._price(
            effective_from=date(2026, 6, 1),
            price=Decimal("110.00"),
        ).save()

        rows = CustomerProductPrice.objects.filter(
            customer=self.customer,
            product=self.product,
            is_active=True,
        ).order_by("effective_from")
        self.assertEqual(rows.count(), 2)
        self.assertEqual(rows[0].effective_to, date(2026, 5, 31))
        self.assertIsNone(rows[1].effective_to)

    def test_new_price_cannot_start_before_existing_active_price(self):
        self._price(effective_from=date(2026, 6, 1)).save()
        backdated = self._price(effective_from=date(2026, 1, 1))
        with self.assertRaises(ValidationError):
            backdated.save()

    def test_non_overlapping_periods_pass(self):
        self._price(
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 5, 31),
        ).save()

        row = self._price(
            effective_from=date(2026, 6, 1),
            effective_to=date(2026, 12, 31),
        )
        row.save()
        self.assertEqual(CustomerProductPrice.objects.filter(customer=self.customer).count(), 2)

    def test_inactive_customer_cannot_have_active_price(self):
        self.customer.is_active = False
        self.customer.save(update_fields=["is_active"])
        row = self._price()
        with self.assertRaises(ValidationError):
            row.save()

    def test_inactive_product_cannot_have_active_price(self):
        self.product.is_active = False
        self.product.save(update_fields=["is_active"])
        row = self._price()
        with self.assertRaises(ValidationError):
            row.save()

    def test_historical_price_core_fields_are_immutable(self):
        row = self._price()
        row.save()
        row.price = Decimal("120.00")
        with self.assertRaises(ValidationError):
            row.save()

    def test_adjacent_periods_after_auto_close_do_not_overlap(self):
        self._price(effective_from=date(2026, 1, 1)).save()
        self._price(effective_from=date(2026, 6, 1), price=Decimal("110.00")).save()
        self._price(effective_from=date(2026, 12, 1), price=Decimal("120.00")).save()

        for row in CustomerProductPrice.objects.filter(
            customer=self.customer, product=self.product, is_active=True
        ).order_by("effective_from"):
            row.full_clean()
