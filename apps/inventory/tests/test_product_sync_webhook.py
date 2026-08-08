import json

from django.test import Client, TestCase, override_settings

from apps.inventory.models import Product


@override_settings(GOOGLE_SHEET_WEBHOOK_TOKEN="test-webhook-token")
class ProductSyncWebhookTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = "/api/sync/product/"
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
                "product_code": "FG-W01",
                "name": "Webhook 測試產品",
                "category": "有信品牌粉",
                "brand": "有信",
                "series": "品牌粉",
                "spec": "20kg/1包",
                "unit": "包",
                "is_sellable": "✓",
                "can_be_raw_material": "✗",
                "is_active": "✓",
            }
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["product_code"], "FG-W01")
        self.assertEqual(data["action"], "created")

        product = Product.objects.get(sku="FG-W01")
        self.assertEqual(product.name, "Webhook 測試產品")
        self.assertEqual(product.category, "有信品牌粉")
        self.assertTrue(product.is_sellable)
        self.assertFalse(product.can_be_raw_material)
        self.assertEqual(product.product_kind, Product.ProductKind.FINISHED)

    def test_update_with_valid_token(self):
        Product.objects.create(
            sku="FG-W02",
            name="舊品名",
            product_kind=Product.ProductKind.FINISHED,
            unit=Product.Unit.PACK,
        )

        response = self._post(
            {
                "product_code": "FG-W02",
                "name": "新品名",
                "spec": "10kg/1包",
                "unit": "包",
            }
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["product_code"], "FG-W02")
        self.assertEqual(data["action"], "updated")

        product = Product.objects.get(sku="FG-W02")
        self.assertEqual(product.name, "新品名")
        self.assertEqual(product.spec, "10kg/1包")
        self.assertEqual(Product.objects.filter(sku="FG-W02").count(), 1)

    def test_invalid_token_returns_403(self):
        response = self.client.post(
            self.url,
            data=json.dumps({"product_code": "FG-W03", "name": "不該建立"}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer wrong-token",
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.json()["success"])
        self.assertFalse(Product.objects.filter(sku="FG-W03").exists())

    def test_duplicate_post_does_not_create_duplicate(self):
        payload = {
            "product_code": "FG-W04",
            "name": "重複測試",
            "unit": "包",
        }

        first = self._post(payload)
        second = self._post({**payload, "name": "重複測試更新"})

        self.assertEqual(first.json()["action"], "created")
        self.assertEqual(second.json()["action"], "updated")
        self.assertEqual(Product.objects.filter(sku="FG-W04").count(), 1)
        self.assertEqual(Product.objects.get(sku="FG-W04").name, "重複測試更新")
