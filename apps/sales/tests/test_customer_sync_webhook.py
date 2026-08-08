import json

from django.test import Client, TestCase, override_settings

from apps.sales.models import Customer


@override_settings(GOOGLE_SHEET_WEBHOOK_TOKEN="test-webhook-token")
class CustomerSyncWebhookTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = "/api/sync/customer/"
        self.headers = {"HTTP_AUTHORIZATION": "Bearer test-webhook-token"}

    def _post(self, payload, **extra_headers):
        headers = dict(self.headers)
        headers.update(extra_headers)
        return self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
            **headers,
        )

    def test_create_with_valid_token(self):
        response = self._post(
            {
                "customer_code": "CUS-W01",
                "name": "Webhook 測試客戶",
                "region": "北區",
                "phone": "0912345678",
            }
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["customer_code"], "CUS-W01")
        self.assertEqual(data["action"], "created")

        customer = Customer.objects.get(code="CUS-W01")
        self.assertEqual(customer.name, "Webhook 測試客戶")
        self.assertEqual(customer.region, "北區")
        self.assertEqual(customer.phone, "0912345678")

    def test_update_with_valid_token(self):
        Customer.objects.create(code="CUS-W02", name="舊名稱", phone="0222222222")

        response = self._post(
            {
                "customer_code": "CUS-W02",
                "name": "新名稱",
                "phone": "0333333333",
            }
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["customer_code"], "CUS-W02")
        self.assertEqual(data["action"], "updated")

        customer = Customer.objects.get(code="CUS-W02")
        self.assertEqual(customer.name, "新名稱")
        self.assertEqual(customer.phone, "0333333333")
        self.assertEqual(Customer.objects.filter(code="CUS-W02").count(), 1)

    def test_invalid_token_returns_403(self):
        response = self.client.post(
            self.url,
            data=json.dumps({"customer_code": "CUS-W03", "name": "不該建立"}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer wrong-token",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.json()["success"])
        self.assertFalse(Customer.objects.filter(code="CUS-W03").exists())

    def test_duplicate_post_does_not_create_duplicate(self):
        payload = {"customer_code": "CUS-W04", "name": "重複測試"}

        first = self._post(payload)
        second = self._post({**payload, "name": "重複測試更新"})

        self.assertEqual(first.json()["action"], "created")
        self.assertEqual(second.json()["action"], "updated")
        self.assertEqual(Customer.objects.filter(code="CUS-W04").count(), 1)
        self.assertEqual(Customer.objects.get(code="CUS-W04").name, "重複測試更新")
