from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.deliveries.models import DeliveryTrip, DeliveryTripOrder
from apps.deliveries.services import (
    TripCreationError,
    create_delivery_trip,
    orders_for_delivery_date,
)
from apps.inventory.models import Product
from apps.sales.models import Customer, SalesOrder, SalesOrderItem


class DeliveryFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="driver", password="test-pass-123")
        self.today = timezone.localdate()
        self.customer_a = Customer.objects.create(
            code="D001",
            name="華都小籠包",
            region="南區",
            address="台南市民權路二段28號",
            phone="06-1234567",
        )
        self.customer_b = Customer.objects.create(
            code="D002",
            name="老陳炸雞",
            region="中西區",
            address="台南市中西區民權路1號",
        )
        self.product = Product.objects.create(
            sku="FG0009",
            name="紅有信2",
            is_sellable=True,
        )
        self.product_b = Product.objects.create(
            sku="ST001",
            name="太白粉",
            is_sellable=True,
        )

    def _order(self, customer, suffix="1", status=SalesOrder.Status.CREATED):
        order = SalesOrder.objects.create(
            order_no=f"SO-TEST-{suffix}",
            customer=customer,
            status=status,
            order_date=self.today,
            delivery_date=self.today,
            shipping_address=customer.address,
        )
        SalesOrderItem.objects.create(
            sales_order=order,
            product=self.product,
            quantity=Decimal("5"),
            unit_price=Decimal("100"),
        )
        return order

    def test_unassigned_orders_appear_on_delivery_list(self):
        order = self._order(self.customer_a)
        qs = orders_for_delivery_date(self.today)
        self.assertIn(order, qs)

    def test_assigned_orders_hidden_from_delivery_list(self):
        order = self._order(self.customer_a)
        create_delivery_trip([order.pk], trip_date=self.today)
        qs = orders_for_delivery_date(self.today)
        self.assertNotIn(order, qs)

    def test_cancelled_orders_do_not_appear(self):
        order = self._order(self.customer_a, status=SalesOrder.Status.CANCELLED)
        qs = orders_for_delivery_date(self.today)
        self.assertNotIn(order, qs)

    def test_create_first_trip_number_is_one(self):
        order = self._order(self.customer_a)
        trip = create_delivery_trip([order.pk], trip_date=self.today)
        self.assertEqual(trip.trip_number, 1)
        self.assertEqual(trip.trip_code, f"TRIP-{self.today.strftime('%Y%m%d')}-01")
        self.assertEqual(trip.status, DeliveryTrip.Status.PREPARING)

    def test_second_trip_same_day_gets_next_number(self):
        order1 = self._order(self.customer_a, suffix="A")
        order2 = self._order(self.customer_b, suffix="B")
        create_delivery_trip([order1.pk], trip_date=self.today)
        trip2 = create_delivery_trip([order2.pk], trip_date=self.today)
        self.assertEqual(trip2.trip_number, 2)
        self.assertTrue(trip2.trip_code.endswith("-02"))

    def test_same_order_cannot_be_assigned_twice(self):
        order = self._order(self.customer_a)
        create_delivery_trip([order.pk], trip_date=self.today)
        with self.assertRaises(TripCreationError):
            create_delivery_trip([order.pk], trip_date=self.today)

    def test_empty_selection_cannot_create_trip(self):
        with self.assertRaises(TripCreationError):
            create_delivery_trip([], trip_date=self.today)

    def test_failed_creation_leaves_no_trip_data(self):
        order = self._order(self.customer_a)
        create_delivery_trip([order.pk], trip_date=self.today)
        before_trips = DeliveryTrip.objects.count()
        before_links = DeliveryTripOrder.objects.count()
        with self.assertRaises(TripCreationError):
            create_delivery_trip([order.pk], trip_date=self.today)
        self.assertEqual(DeliveryTrip.objects.count(), before_trips)
        self.assertEqual(DeliveryTripOrder.objects.count(), before_links)

    def test_trip_orders_keep_sequence(self):
        order1 = self._order(self.customer_a, suffix="A")
        order2 = self._order(self.customer_b, suffix="B")
        trip = create_delivery_trip([order2.pk, order1.pk], trip_date=self.today)
        sequences = list(
            trip.trip_orders.order_by("sequence").values_list("sales_order_id", flat=True)
        )
        self.assertEqual(sequences, [order2.pk, order1.pk])

    def test_anonymous_can_view_delivery_list(self):
        order = self._order(self.customer_a)
        url = reverse("deliveries:delivery_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, order.customer.name)
        self.assertContains(response, order.order_no)

    def test_create_trip_via_post_redirects_to_detail(self):
        self.client.login(username="driver", password="test-pass-123")
        order1 = self._order(self.customer_a, suffix="P1")
        order2 = self._order(self.customer_b, suffix="P2")
        response = self.client.post(
            reverse("deliveries:create_trip"),
            {
                "trip_date": self.today.isoformat(),
                "order_ids": [str(order1.pk), str(order2.pk)],
            },
        )
        self.assertEqual(response.status_code, 302)
        trip = DeliveryTrip.objects.get()
        self.assertEqual(response.url, reverse("deliveries:trip_detail", args=[trip.pk]))
        self.assertEqual(trip.trip_orders.count(), 2)

    def test_create_trip_post_without_orders_shows_error(self):
        self.client.login(username="driver", password="test-pass-123")
        response = self.client.post(
            reverse("deliveries:create_trip"),
            {"trip_date": self.today.isoformat()},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(DeliveryTrip.objects.count(), 0)

    def test_trip_detail_shows_customer_and_items(self):
        self.client.login(username="driver", password="test-pass-123")
        order = self._order(self.customer_a)
        trip = create_delivery_trip([order.pk], trip_date=self.today)
        response = self.client.get(reverse("deliveries:trip_detail", args=[trip.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "華都小籠包")
        self.assertContains(response, "紅有信2")
        self.assertContains(response, "準備中")
