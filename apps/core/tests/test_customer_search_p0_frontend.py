"""P0 hotfix: verify fetchSearch timeout and abort behavior (no browser)."""

from django.test import SimpleTestCase


class CustomerSearchP0FrontendTests(SimpleTestCase):
    def test_fetch_search_js_has_one_second_timeout(self):
        with open("static/js/customer_search_live.js", encoding="utf-8") as f:
            src = f.read()
        self.assertIn("SEARCH_TIMEOUT_MS = 1000", src)
        self.assertIn("timedOut: true", src)
        self.assertIn("搜尋逾時，請稍後再試", src)

    def test_sse_disabled_in_live_refresh(self):
        with open("static/js/customer_search_live.js", encoding="utf-8") as f:
            src = f.read()
        self.assertIn("disable SSE", src)
        self.assertNotIn("new EventSource", src)

    def test_touch_search_ui_copy(self):
        with open("static/js/touch_customer_search.js", encoding="utf-8") as f:
            touch = f.read()
        with open("templates/core/dashboard_touch.html", encoding="utf-8") as f:
            dashboard = f.read()
        self.assertIn("搜尋中", touch)
        self.assertIn("查無客戶，請改用電話搜尋", touch)
        self.assertIn('placeholder="輸入姓名或電話"', dashboard)

    def test_hotfix_does_not_touch_pricing(self):
        import subprocess

        out = subprocess.check_output(
            ["git", "diff", "main...HEAD", "--name-only"],
            text=True,
        )
        for line in out.splitlines():
            lower = line.lower()
            self.assertNotIn("pricing", lower)
            self.assertNotIn("cost_history", lower)
