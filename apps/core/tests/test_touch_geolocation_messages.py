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
        return {"kind": "unknown"}
    code = error["code"]
    if code == 1:
        return {"kind": "denied"}
    if code == 3:
        return {"kind": "timeout"}
    if code == 2:
        if _is_location_services_disabled_message(error.get("message", "")):
            return {"kind": "disabled"}
        return {"kind": "unavailable"}
    return {"kind": "unknown"}


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
