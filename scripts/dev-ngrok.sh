#!/usr/bin/env bash
# 公開 HTTPS 隧道 → 本機 Django（iPad / 外網測試用）
# 用法：./scripts/dev-ngrok.sh [port，預設 8001]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${1:-8001}"
cd "$ROOT"

if ! command -v ngrok >/dev/null 2>&1; then
  echo "ngrok 未安裝。請擇一："
  echo "  brew install ngrok/ngrok/ngrok"
  echo "  或至 https://ngrok.com/download 安裝後加入 PATH"
  exit 1
fi

if [[ ! -f "$ROOT/.venv/bin/activate" ]]; then
  echo "找不到 .venv，請先建立虛擬環境。"
  exit 1
fi

# shellcheck source=/dev/null
source "$ROOT/.venv/bin/activate"

export USE_NGROK=1

if ! curl -sf "http://127.0.0.1:${PORT}/" >/dev/null 2>&1; then
  echo "啟動 Django（0.0.0.0:${PORT}）…"
  python manage.py runserver "0.0.0.0:${PORT}" &
  DJANGO_PID=$!
  trap 'kill "$DJANGO_PID" 2>/dev/null || true' EXIT
  sleep 2
else
  echo "偵測到 port ${PORT} 已有服務，略過啟動 runserver。"
  DJANGO_PID=""
fi

echo ""
echo "啟動 ngrok → http://127.0.0.1:${PORT}"
echo "公開網址請看下方 ngrok 輸出，或另開終端： curl -s http://127.0.0.1:4040/api/tunnels | python3 -m json.tool"
echo "（首次使用請先：ngrok config add-authtoken <你的 token>）"
echo ""

ngrok http "$PORT" --log=stdout &
NGROK_PID=$!
trap 'kill "$NGROK_PID" ${DJANGO_PID:+ "$DJANGO_PID"} 2>/dev/null || true' EXIT

for _ in $(seq 1 30); do
  sleep 1
  URL="$(curl -sf http://127.0.0.1:4040/api/tunnels 2>/dev/null | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    for t in data.get('tunnels', []):
        u = t.get('public_url', '')
        if u.startswith('https://'):
            print(u)
            break
except Exception:
    pass
" 2>/dev/null || true)"
  if [[ -n "${URL:-}" ]]; then
    echo ""
    echo "============================================"
    echo "  iPad Safari 開啟："
    echo "  $URL"
    echo "============================================"
    echo ""
    break
  fi
done

wait "$NGROK_PID"
