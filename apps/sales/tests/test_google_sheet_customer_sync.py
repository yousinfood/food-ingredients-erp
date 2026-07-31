from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from apps.sales.models import Customer
from apps.sales.services.customer_sheet_rows import (
    customer_to_sheet_row,
    parse_customer_sheet_rows,
)
from apps.sales.services.google_sheet_customer_sync import (
    _parse_json_body,
    maybe_sync_customers_from_google_sheet,
    push_customer_to_google_sheet,
    run_sync_from_rows,
)
from apps.sales.services.phase1_import import CUSTOMER_HEADERS


class CustomerSheetRowsTests(TestCase):
    def test_customer_to_sheet_row_maps_core_fields(self):
        customer = Customer(
            code="CUS-T01",
            name="測試店家",
            region="北區",
            phone="0912345678",
            address="台北市中正區",
        )
        row = customer_to_sheet_row(customer)
        self.assertEqual(row[0], "CUS-T01")
        self.assertEqual(row[2], "測試店家")
        self.assertEqual(row[1], "北區")
        self.assertEqual(row[4], "0912345678")
        self.assertEqual(row[7], "台北市中正區")

    def test_parse_customer_sheet_rows(self):
        rows = [
            list(CUSTOMER_HEADERS),
            [
                "CUS-T01",
                "北區",
                "測試店家",
                "王老板",
                "0912345678",
                "",
                "",
                "台北市中正區",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
            ],
        ]
        records, errors = parse_customer_sheet_rows(rows)
        self.assertEqual(errors, [])
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["code"], "CUS-T01")
        self.assertEqual(records[0]["name"], "測試店家")


class GoogleSheetCustomerSyncTests(TestCase):
    def test_parse_json_body_rejects_empty_response(self):
        with self.assertRaises(RuntimeError) as ctx:
            _parse_json_body(
                "",
                status=200,
                content_type="application/json",
                context="test",
            )
        self.assertIn("空白回應", str(ctx.exception))

    def test_parse_json_body_rejects_non_json_content_type(self):
        with self.assertRaises(RuntimeError) as ctx:
            _parse_json_body(
                "<html></html>",
                status=200,
                content_type="text/html",
                context="test",
            )
        self.assertIn("非 JSON 回應", str(ctx.exception))

    @override_settings(
        GOOGLE_SHEETS_SPREADSHEET_ID="sheet-id",
        GOOGLE_SERVICE_ACCOUNT_JSON='{"client_email":"x@y.iam.gserviceaccount.com","private_key":"x"}',
        CUSTOMER_SHEET_SYNC_INTERVAL_SECONDS=0,
    )
    @patch("apps.sales.services.google_sheet_customer_sync._fetch_customer_rows")
    def test_maybe_sync_returns_failure_on_empty_json_error(self, mock_fetch):
        mock_fetch.side_effect = RuntimeError("JSON 解析失敗; body=''")
        result = maybe_sync_customers_from_google_sheet(force=True)
        self.assertFalse(result["ok"])
        self.assertFalse(result["skipped"])
        self.assertIn("JSON 解析失敗", result["reason"])

    @override_settings(
        GOOGLE_SHEETS_SPREADSHEET_ID="sheet-id",
        GOOGLE_SERVICE_ACCOUNT_JSON='{"client_email":"x@y.iam.gserviceaccount.com","private_key":"x"}',
    )
    @patch("apps.sales.services.google_sheet_customer_sync._api_request")
    @patch("apps.sales.services.google_sheet_customer_sync._fetch_customer_rows")
    @patch("apps.sales.services.google_sheet_customer_sync._access_token")
    def test_push_updates_existing_row(self, mock_token, mock_fetch, mock_api):
        mock_token.return_value = "token"
        mock_fetch.return_value = [list(CUSTOMER_HEADERS), ["CUS-T01", "北區", "舊名稱"] + [""] * 14]
        customer = Customer.objects.create(code="CUS-T01", name="新名稱", phone="0223456789")

        result = push_customer_to_google_sheet(customer)

        self.assertTrue(result["ok"])
        self.assertEqual(result["action"], "updated")
        mock_api.assert_called_once()
        payload = mock_api.call_args.kwargs["payload"]
        self.assertEqual(payload["values"][0][2], "新名稱")
        self.assertEqual(payload["values"][0][4], "0223456789")

    def test_run_sync_from_rows_upserts_customer(self):
        rows = [
            list(CUSTOMER_HEADERS),
            [
                "CUS-T02",
                "南區",
                "Sheet 客戶",
                "",
                "0987654321",
                "",
                "",
                "高雄市",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
            ],
        ]
        report = run_sync_from_rows(rows)
        self.assertTrue(report["ok"])
        self.assertEqual(report["created"], 1)
        customer = Customer.objects.get(code="CUS-T02")
        self.assertEqual(customer.name, "Sheet 客戶")
        self.assertEqual(customer.phone, "0987654321")

        rows[1][2] = "Sheet 客戶更新"
        rows[1][4] = "0222333444"
        report = run_sync_from_rows(rows)
        customer.refresh_from_db()
        self.assertEqual(report["updated"], 1)
        self.assertEqual(customer.name, "Sheet 客戶更新")
        self.assertEqual(customer.phone, "0222333444")
