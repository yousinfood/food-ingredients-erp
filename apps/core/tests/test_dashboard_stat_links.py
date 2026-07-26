from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.services.dashboard import get_dashboard_stats
from apps.core.services.dashboard_order_filters import (
    TODAY_DELIVERED,
    TODAY_UNDELIVERED,
    dashboard_order_list_url,
    dashboard_stat_links,
    queryset_for_dashboard_filter,
)
from apps.sales.models import Customer, SalesOrder


class DashboardStatLinksTests(TestCase):
    def test_stat_links_use_sales_order_list_dashboard_query(self):
        links = dashboard_stat_links()
        self.assertIn("dashboard=today_delivered", links["deliveries_today"])
        self.assertIn("dashboard=today_undelivered", links["undelivered_today"])
        self.assertIn("dashboard=today_pending_collection", links["pending_collection_today"])
        self.assertIn("dashboard=today_overdue", links["overdue_today"])
        for url in links.values():
            self.assertTrue(url.startswith(reverse("sales:sales_order_list")))

    def test_dashboard_order_list_url_reverses(self):
        url = dashboard_order_list_url(TODAY_UNDELIVERED)
        self.assertEqual(url, f"{reverse('sales:sales_order_list')}?dashboard=today_undelivered")


class DashboardOrderFilterTests(TestCase):
    def setUp(self):
        self.customer = Customer.objects.create(code="C001", name="測試店")
        self.today = timezone.localdate()

    def _order(self, status, delivery_date=None):
        return SalesOrder.objects.create(
            order_no=f"SO-TEST-{SalesOrder.objects.count() + 1}",
            customer=self.customer,
            status=status,
            order_date=self.today,
            delivery_date=delivery_date or self.today,
        )

    def test_undelivered_today_includes_created_not_shipped(self):
        self._order(SalesOrder.Status.CREATED)
        self._order(SalesOrder.Status.SHIPPED)
        qs = queryset_for_dashboard_filter(TODAY_UNDELIVERED)
        self.assertEqual(qs.count(), 1)

    def test_delivered_today_includes_shipped_and_completed(self):
        self._order(SalesOrder.Status.CREATED)
        self._order(SalesOrder.Status.SHIPPED)
        self._order(SalesOrder.Status.COMPLETED)
        qs = queryset_for_dashboard_filter(TODAY_DELIVERED)
        self.assertEqual(qs.count(), 2)

    def test_excludes_cancelled_and_other_delivery_dates(self):
        self._order(SalesOrder.Status.CREATED)
        self._order(SalesOrder.Status.CANCELLED)
        self._order(SalesOrder.Status.CREATED, delivery_date=self.today + timedelta(days=1))
        stats = get_dashboard_stats()
        self.assertEqual(stats["undelivered_today"], 1)

    def test_sales_order_list_view_applies_dashboard_filter(self):
        self._order(SalesOrder.Status.CREATED)
        self._order(SalesOrder.Status.SHIPPED)
        url = dashboard_order_list_url(TODAY_UNDELIVERED)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "今日未送")
        order_nos = [o.order_no for o in response.context["orders"]]
        self.assertEqual(len(order_nos), 1)
