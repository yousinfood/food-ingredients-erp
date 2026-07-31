from django.contrib import messages

from apps.sales.services.google_sheet_customer_sync import (
    delete_customer_from_google_sheet,
    push_customer_to_google_sheet,
)


def push_customer_sheet_or_warn(request, customer) -> dict:
    result = push_customer_to_google_sheet(customer)
    if result.get("ok") or result.get("skipped"):
        return result

    reason = result.get("reason", "unknown")
    if reason == "sheet_write_denied":
        text = "客戶已儲存，但 Google Sheet 寫入失敗（服務帳號需編輯權限）"
    elif reason == "not_configured":
        text = "客戶已儲存，但 Google Sheet 尚未設定"
    else:
        text = f"客戶已儲存，但 Google Sheet 同步失敗：{reason}"
    messages.warning(request, text)
    return result


def delete_customer_sheet_or_warn(request, code: str) -> dict:
    result = delete_customer_from_google_sheet(code)
    if result.get("ok") or result.get("skipped"):
        return result

    reason = result.get("reason", "unknown")
    if reason == "sheet_write_denied":
        text = "客戶已刪除，但 Google Sheet 更新失敗（服務帳號需編輯權限）"
    elif reason == "not_configured":
        text = "客戶已刪除，但 Google Sheet 尚未設定"
    else:
        text = f"客戶已刪除，但 Google Sheet 同步失敗：{reason}"
    messages.warning(request, text)
    return result
