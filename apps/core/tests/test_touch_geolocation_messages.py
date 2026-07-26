from django.test import SimpleTestCase


def _is_location_services_disabled_message(message: str) -> bool:
    msg = (message or "").lower().replace("\u2019", "'")
    if not msg:
        return False
    if "location services" not in msg and "定位服务" not in msg:
        return False
    return (
        "turned off" in msg
        or "disabled" in msg
        or "已关闭" in msg
        or "已關閉" in msg
    )


def _message_from_geolocation_error(error) -> dict:
    if error is None or not isinstance(error, dict) or "code" not in error:
        return {"kind": "unknown", "message": "無法取得定位，仍可開啟地圖導航", "show_banner": False}
    code = error["code"]
    if code == 1:
        return {
            "kind": "denied",
            "message": "尚未允許使用定位，請在 Safari 設定中允許此網站",
            "show_banner": True,
        }
    if code == 3:
        return {"kind": "timeout", "message": "定位逾時，請再試一次", "show_banner": False}
    if code == 2:
        if _is_location_services_disabled_message(error.get("message", "")):
            return {
                "kind": "disabled",
                "message": "定位服務已關閉，請到「設定 → 隱私權與安全性 → 定位服務」開啟",
                "show_banner": True,
            }
        return {
            "kind": "unavailable",
            "message": "目前無法取得定位，仍可開啟地圖導航",
            "show_banner": False,
        }
    return {"kind": "unknown", "message": "無法取得定位，仍可開啟地圖導航", "show_banner": False}


def _coerce_mapped_error(err) -> dict:
    if isinstance(err, dict) and isinstance(err.get("kind"), str) and isinstance(err.get("message"), str):
        show = err.get("show_banner") is True or err["kind"] in ("denied", "disabled")
        return {"kind": err["kind"], "message": err["message"], "show_banner": show}
    raw = err.get("raw") if isinstance(err, dict) and "raw" in err else err
    if isinstance(raw, dict) and "code" in raw:
        return _message_from_geolocation_error(raw)
    return _message_from_geolocation_error(None)


class TouchGeolocationMessageTests(SimpleTestCase):
    def test_permission_denied_not_disabled(self):
        mapped = _message_from_geolocation_error({"code": 1})
        self.assertEqual(mapped["kind"], "denied")

    def test_timeout(self):
        self.assertEqual(_message_from_geolocation_error({"code": 3})["kind"], "timeout")

    def test_position_unavailable_only_disabled_with_browser_message(self):
        self.assertEqual(
            _message_from_geolocation_error(
                {"code": 2, "message": "Location services are turned off"}
            )["kind"],
            "disabled",
        )
        self.assertEqual(
            _message_from_geolocation_error({"code": 2, "message": "Unavailable"})["kind"],
            "unavailable",
        )
        self.assertEqual(_message_from_geolocation_error({"code": 2})["kind"], "unavailable")

    def test_code_2_without_message_is_unavailable_not_disabled(self):
        mapped = _message_from_geolocation_error({"code": 2})
        self.assertEqual(mapped["kind"], "unavailable")
        self.assertFalse(mapped["show_banner"])

    def test_raw_browser_error_never_surfaces_english_in_ui(self):
        raw = {"code": 2, "message": "Location services are turned off"}
        mapped = _coerce_mapped_error(raw)
        self.assertEqual(mapped["kind"], "disabled")
        self.assertNotIn("Location", mapped["message"])
        self.assertIn("定位服務", mapped["message"])

    def test_ipad_like_code_2_empty_message(self):
        mapped = _coerce_mapped_error({"code": 2, "message": ""})
        self.assertEqual(mapped["kind"], "unavailable")
