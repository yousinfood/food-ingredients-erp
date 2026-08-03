from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from apps.sales.models import Customer
from apps.sales.services.customer_search import search_customers_ranked
from apps.sales.services.voice_search_normalize import (
    VOICE_SIMILARITY_THRESHOLD,
    normalize_voice_query,
    similarity_score,
)


class VoiceQueryNormalizeTests(SimpleTestCase):
    def test_examples_normalize_to_bubu(self):
        cases = (
            "去洗澡機",
            "布布炸雞",
            "ㄅㄨㄅㄨ炸雞",
            "不不炸雞",
            "哺哺炸雞",
        )
        for raw in cases:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_voice_query(raw), "布布炸雞")

    def test_fried_suffix_variants(self):
        self.assertEqual(normalize_voice_query("布布炸機"), "布布炸雞")
        self.assertEqual(normalize_voice_query("布布炸机"), "布布炸雞")


class VoiceSimilarityTests(SimpleTestCase):
    def test_bubu_queries_meet_threshold_against_canonical(self):
        canonical = "布布炸雞"
        for q in ("ㄅㄨㄅㄨ炸雞", "布布炸機", "去洗澡機", "不不炸雞"):
            with self.subTest(q=q):
                score = similarity_score(q, canonical)
                self.assertGreaterEqual(score, VOICE_SIMILARITY_THRESHOLD)


class VoiceCustomerSearchIntegrationTests(TestCase):
    def setUp(self):
        Customer.objects.create(code="V-BUBU", name="布布炸雞", is_active=True)
        Customer.objects.create(code="V-OTHER", name="華姐黑輪", is_active=True)
        Customer.objects.create(
            code="V-HUADU",
            name="華都小籠包",
            voice_aliases="華都, 花都, 華豆, 花豆",
            is_active=True,
        )
        Customer.objects.create(
            code="V-CHEN",
            name="老陳炸雞",
            contact_person="老陳",
            voice_aliases="老陳, 老沈, 陳仔, 炸雞陳",
            is_active=True,
        )

    def _voice_search(self, q: str, alts=None):
        from apps.sales.services.customer_search import search_customers_voice

        candidates = [q] + list(alts or [])
        return search_customers_voice(candidates)

    def test_voice_finds_bubu_from_mishears(self):
        for q in ("ㄅㄨㄅㄨ炸雞", "布布炸機", "去洗澡機", "不不炸雞"):
            with self.subTest(q=q):
                result = self._voice_search(q)
                names = [c.name for c in result.customers]
                self.assertIn("布布炸雞", names)

    def test_voice_results_sorted_by_similarity(self):
        result = self._voice_search("去洗澡機")
        self.assertGreaterEqual(result.total_count, 1)
        self.assertEqual(result.customers[0].name, "布布炸雞")

    def test_huadu_alias_finds_xiaolongbao(self):
        for q in ("華都", "花都", "華豆", "花豆"):
            with self.subTest(q=q):
                result = self._voice_search(q)
                names = [c.name for c in result.customers]
                self.assertIn("華都小籠包", names)

    def test_huadu_voice_limits_to_five(self):
        result = self._voice_search("華")
        self.assertLessEqual(len(result.customers), 5)

    def test_voice_uses_multiple_candidates(self):
        result = self._voice_search("花都", alts=["華豆", "不存在"])
        names = [c.name for c in result.customers]
        self.assertIn("華都小籠包", names)

    def test_laochen_alias(self):
        result = self._voice_search("老沈")
        names = [c.name for c in result.customers]
        self.assertIn("老陳炸雞", names)

    @patch("apps.sales.services.google_sheet_customer_sync.maybe_sync_customers_from_google_sheet")
    def test_voice_search_reads_postgres_without_sheet_sync(self, mock_sync):
        result = self._voice_search("布布")
        names = [c.name for c in result.customers]
        self.assertIn("布布炸雞", names)
        mock_sync.assert_not_called()
