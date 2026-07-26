from django.test import SimpleTestCase

from apps.sales.models import Customer
from apps.sales.services.customer_search import customer_relevance_tier, search_customers_ranked


class CustomerSearchRankingTests(SimpleTestCase):
    def _customer(self, **kwargs):
        return Customer(**kwargs)

    def test_single_character_name_start(self):
        a = self._customer(name="華姐", code="A")
        b = self._customer(name="國華", code="B")
        self.assertEqual(customer_relevance_tier(a, "華"), 1)
        self.assertEqual(customer_relevance_tier(b, "華"), 2)

        a = self._customer(name="華姐黑輪", code="A")
        b = self._customer(name="國華街蚵仔煎", code="B")
        self.assertLess(customer_relevance_tier(a, "華"), customer_relevance_tier(b, "華"))

    def test_sort_order_example(self):
        customers = [
            self._customer(name="國華街蚵仔煎", code="C3"),
            self._customer(name="華姐黑輪", code="C1"),
            self._customer(name="華都小籠包", code="C2"),
        ]
        customers.sort(key=lambda c: (customer_relevance_tier(c, "華"), c.name))
        self.assertEqual([c.name for c in customers], ["華姐黑輪", "華都小籠包", "國華街蚵仔煎"])
