from unittest.mock import patch

from django.test import Client, TestCase

from apps.sales.models import Customer, CustomerSearchRevision
from apps.sales.services.customer_realtime import get_customer_search_revision
from apps.sales.services.customer_search import (
    search_customers_live,
    search_customers_ranked,
    search_customers_voice,
)


class CustomerSearchLiveRefactorTests(TestCase):
    def setUp(self):
        CustomerSearchRevision.objects.get_or_create(pk=1, defaults={"version": 0})

    def test_new_customer_visible_immediately_in_text_search(self):
        Customer.objects.create(code="LIVE-001", name="即時測試店", is_active=True)
        result = search_customers_ranked("即時測試", show_all=True)
        names = [customer.name for customer in result.customers]
        self.assertIn("即時測試店", names)

    def test_new_customer_visible_immediately_in_voice_search(self):
        Customer.objects.create(
            code="LIVE-002",
            name="王小明",
            voice_aliases="小王",
            is_active=True,
        )
        result = search_customers_voice(["王小明"])
        names = [customer.name for customer in result.customers]
        self.assertIn("王小明", names)

    @patch("apps.sales.services.google_sheet_customer_sync.maybe_sync_customers_from_google_sheet")
    def test_search_does_not_pull_google_sheet(self, mock_sync):
        Customer.objects.create(code="LIVE-003", name="不走Sheet", is_active=True)
        search_customers_ranked("不走Sheet", show_all=True)
        search_customers_voice(["不走Sheet"])
        mock_sync.assert_not_called()

    def test_search_api_returns_no_store_headers(self):
        Customer.objects.create(code="LIVE-004", name="NoStore店", is_active=True)
        response = Client().get(
            "/api/customers/search/",
            {"q": "NoStore", "home": "1"},
            HTTP_ACCEPT="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("NoStore店", response.json()["html"])

    def test_search_customers_live_text_and_voice_share_entry(self):
        Customer.objects.create(code="LIVE-T1", name="共享入口店", is_active=True)
        text = search_customers_live("共享入口", voice=False)
        self.assertIn("共享入口店", [c.name for c in text.customers])

        Customer.objects.create(
            code="LIVE-T2",
            name="語音共享店",
            voice_aliases="語音店",
            is_active=True,
        )
        voice = search_customers_live("語音店", voice=True)
        self.assertIn("語音共享店", [c.name for c in voice.customers])

    def test_customer_save_bumps_revision(self):
        before = get_customer_search_revision()
        with self.captureOnCommitCallbacks(execute=True):
            Customer.objects.create(code="REV-001", name="版本測試", is_active=True)
        after = get_customer_search_revision()
        self.assertGreater(after, before)

    def test_updated_name_visible_immediately(self):
        customer = Customer.objects.create(code="REV-002", name="舊店名", is_active=True)
        customer.name = "新店名"
        customer.save(update_fields=["name"])
        result = search_customers_live("新店名", voice=False)
        self.assertEqual([c.name for c in result.customers], ["新店名"])

    def test_updated_address_visible_immediately(self):
        customer = Customer.objects.create(
            code="REV-003",
            name="地址測試店",
            address="舊地址路1號",
            is_active=True,
        )
        customer.address = "新地址路99號"
        customer.save(update_fields=["address"])
        result = search_customers_live("新地址路99", voice=False)
        self.assertIn("地址測試店", [c.name for c in result.customers])

    def test_deleted_customer_removed_immediately(self):
        customer = Customer.objects.create(code="REV-004", name="刪除測試店", is_active=True)
        customer.delete()
        result = search_customers_live("刪除測試", voice=False)
        self.assertEqual(result.customers, [])

    def test_revision_api_returns_no_store(self):
        response = Client().get(
            "/api/customers/revision/",
            HTTP_ACCEPT="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertTrue(response.json()["ok"])

    def test_events_api_streams_revision(self):
        response = Client().get("/api/customers/events/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/event-stream")
        first = next(response.streaming_content).decode("utf-8")
        self.assertIn("event: revision", first)
        response.close()

    @patch("apps.sales.services.customer_search._live_customer_queryset")
    def test_search_api_db_error_returns_friendly_message(self, mock_qs):
        from django.db import OperationalError

        mock_qs.side_effect = OperationalError("connection failed")
        response = Client().get(
            "/api/customers/search/",
            {"q": "測試", "home": "1"},
            HTTP_ACCEPT="application/json",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertFalse(payload["ok"])
        self.assertIn("目前無法取得最新客戶資料", payload["error"])
