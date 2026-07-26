from django.test import TestCase

from apps.sales.models import Customer
from apps.sales.services.customer_search import search_customers_ranked


class CustomerSearchUnicodeTests(TestCase):
    def setUp(self):
        Customer.objects.create(
            code="CUS-W007",
            name="成功彩虹日本料理",
            region="中西區",
            phone="2263162",
            address="台南市成功路249號",
        )
        Customer.objects.create(
            code="CUS-N003",
            name="和緯彩虹日本料理",
            region="北區",
            phone="2803819",
            address="台南市和緯路三段332號",
        )

    def test_substring_query_rainbow_japan(self):
        result = search_customers_ranked("彩虹日本")
        self.assertEqual(result.total_count, 2)
        names = {c.name for c in result.customers}
        self.assertIn("成功彩虹日本料理", names)
        self.assertIn("和緯彩虹日本料理", names)

    def test_single_character_still_matches(self):
        result = search_customers_ranked("彩")
        self.assertEqual(result.total_count, 2)
