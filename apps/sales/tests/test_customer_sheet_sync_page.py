from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.sales.models import CustomerSheetSyncLog


class CustomerSheetSyncPageTests(TestCase):
    def test_sync_page_loads(self):
        client = Client()
        response = client.get(reverse("sales:customer_sheet_sync"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "同步 Google Sheet 客戶資料")

    @override_settings(GOOGLE_SHEETS_SPREADSHEET_ID="")
    @override_settings(GOOGLE_SHEETS_CUSTOMER_CSV_URL="")
    def test_sync_post_not_configured_shows_error(self):
        client = Client()
        response = client.post(reverse("sales:customer_sheet_sync"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CustomerSheetSyncLog.objects.filter(triggered_by="admin").count(), 1)
