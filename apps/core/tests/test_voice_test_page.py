from django.test import Client, TestCase


class VoiceTestPageTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_voice_test_page_loads(self):
        response = self.client.get("/voice-test/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "語音錄製測試 v3")
        self.assertContains(response, "開始錄音")
        self.assertContains(response, "voice_search_v3.js")
        self.assertContains(response, "送出辨識")
