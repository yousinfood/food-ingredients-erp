#!/usr/bin/env bash
# 同一 Wi‑Fi：iPad 用 Mac 區域網路 IP 連本機 Django（免隧道）
# 用法：./scripts/dev-lan.sh [port，預設 8000]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${1:-8000}"
DEV_LAN_IP="${DEV_LAN_IP:-192.168.0.165}"
cd "$ROOT"

detect_lan_ip() {
  local ip iface
  for iface in en0 en1 en2 bridge0; do
    ip="$(ipconfig getifaddr "$iface" 2>/dev/null || true)"
    if [[ -n "$ip" && "$ip" != 127.* ]]; then
      echo "$ip"
      return 0
    fi
  done
  ip="$(python3 - <<'PY'
import socket
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    print(s.getsockname()[0])
    s.close()
except OSError:
    pass
PY
)"
  if [[ -n "$ip" && "$ip" != 127.* ]]; then
    echo "$ip"
    return 0
  fi
  return 1
}

LAN_IP="$(detect_lan_ip || true)"
if [[ -z "${LAN_IP:-}" ]]; then
  echo "找不到區域網路 IP。請確認 Mac 已連上 Wi‑Fi（與 iPad 同一網路）。"
  exit 1
fi

if [[ "$LAN_IP" != "$DEV_LAN_IP" ]]; then
  echo "提示：目前 Wi‑Fi IP 為 ${LAN_IP}，預期固定為 ${DEV_LAN_IP}。"
  echo "      iPad 請用 http://${DEV_LAN_IP}:${PORT}/；若連不上，請依 docs/ipad-lan-dev.md 設定 DHCP 保留。"
  echo ""
fi

if [[ ! -f "$ROOT/.venv/bin/activate" ]]; then
  echo "找不到 .venv，請先建立虛擬環境。"
  exit 1
fi

# shellcheck source=/dev/null
set -a
source "$ROOT/.venv/bin/activate"
source "$ROOT/.env" 2>/dev/null || true
set +a

export USE_LAN_DEV=1
export USE_POSTGRES="${USE_POSTGRES:-0}"
export DEV_LAN_IP="${DEV_LAN_IP}"
export DJANGO_DEV_PORT="${PORT}"
export DJANGO_ALLOWED_HOSTS_EXTRA="${DEV_LAN_IP},${LAN_IP}"
export CSRF_TRUSTED_ORIGINS_EXTRA="http://${DEV_LAN_IP}:${PORT},http://${LAN_IP}:${PORT}"

stop_runserver_on_port() {
  local pids
  pids="$(lsof -ti tcp:"${PORT}" -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    echo "停止 port ${PORT} 上的既有程序…"
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null || true
    sleep 1
  fi
}

check_firewall_hint() {
  if ! command -v /usr/libexec/ApplicationFirewall/socketfilterfw >/dev/null 2>&1; then
    return 0
  fi
  local state
  state="$(/usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate 2>/dev/null | tail -1 || true)"
  if [[ "$state" == *"enabled"* ]]; then
    echo ""
    echo "提示：macOS 防火牆已開啟。若 iPad 連不上，請在「系統設定 → 網路 → 防火牆 → 選項」"
    echo "      允許 Python／Terminal 接受傳入連線，或暫時關閉防火牆測試。"
    echo ""
  fi
}

stop_runserver_on_port

echo "啟動 Django → 0.0.0.0:${PORT}（ALLOWED_HOSTS 含 ${DEV_LAN_IP}）"
python manage.py runserver "0.0.0.0:${PORT}" &
DJANGO_PID=$!

cleanup() {
  kill "$DJANGO_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

for _ in $(seq 1 40); do
  if curl -sf "http://127.0.0.1:${PORT}/" >/dev/null 2>&1; then
    break
  fi
  sleep 0.25
done

if ! curl -sf "http://127.0.0.1:${PORT}/" >/dev/null 2>&1; then
  echo "Django 無法在本機回應，請看上方錯誤訊息。"
  exit 1
fi

LAN_OK=0
if curl -sf --connect-timeout 3 "http://${LAN_IP}:${PORT}/" >/dev/null 2>&1; then
  LAN_OK=1
else
  check_firewall_hint
  echo "警告：本機用 ${LAN_IP} 測試失敗（127.0.0.1 正常）。iPad 可能仍連不上，請檢查防火牆或 Wi‑Fi 隔離。"
fi

BASE="http://${DEV_LAN_IP}:${PORT}"

echo ""
echo "============================================"
echo "  iPad Safari（與 Mac 同一 Wi‑Fi）開啟："
echo "  ${BASE}/"
echo "  客戶搜尋：${BASE}/search/"
echo "  接單範例：${BASE}/sales/orders/new/?customer=68"
echo "============================================"
if curl -sf --connect-timeout 3 "http://${DEV_LAN_IP}:${PORT}/" >/dev/null 2>&1; then
  echo "  本機已用 ${DEV_LAN_IP} 驗證通過。"
elif [[ "$LAN_OK" -eq 1 ]]; then
  echo "  本機已用 ${LAN_IP} 驗證通過（固定 IP ${DEV_LAN_IP} 尚未就緒，請設 DHCP 保留）。"
else
  echo "  請在 iPad 試開上方網址；若不行再查防火牆或 docs/ipad-lan-dev.md。"
fi
echo "  按 Ctrl+C 停止伺服器"
echo "============================================"
echo ""

wait "$DJANGO_PID"
