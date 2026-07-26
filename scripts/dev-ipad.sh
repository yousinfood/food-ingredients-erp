#!/usr/bin/env bash
# 一鍵啟動：本機 Django（SQLite）+ Cloudflare Quick Tunnel（免域名、免 Dashboard）
# 用法：./scripts/dev-ipad.sh [port，預設 8000]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${1:-8000}"
CF="${CLOUDFLARED_BIN:-$HOME/.local/bin/cloudflared}"
LOG="${ROOT}/.cloudflared-quick.log"

cd "$ROOT"

install_cloudflared() {
  if [[ -x "$CF" ]]; then
    return 0
  fi
  echo "安裝 cloudflared…"
  mkdir -p "$HOME/.local/bin"
  ARCH="$(uname -m)"
  case "$ARCH" in
    arm64) TGT="cloudflared-darwin-arm64.tgz" ;;
    x86_64) TGT="cloudflared-darwin-amd64.tgz" ;;
    *) echo "不支援的 macOS 架構: $ARCH"; exit 1 ;;
  esac
  curl -fsSL "https://github.com/cloudflare/cloudflared/releases/latest/download/$TGT" -o "/tmp/$TGT"
  tar -xzf "/tmp/$TGT" -C "$HOME/.local/bin" cloudflared
  chmod +x "$HOME/.local/bin/cloudflared"
}

install_cloudflared

pkill -f 'cloudflared tunnel login' 2>/dev/null || true
pkill -f 'cloudflared tunnel --config' 2>/dev/null || true
pkill -f 'cloudflared tunnel run' 2>/dev/null || true

# shellcheck source=/dev/null
set -a
source "$ROOT/.venv/bin/activate"
source "$ROOT/.env" 2>/dev/null || true
set +a

export USE_CLOUDFLARE_TUNNEL=1
export USE_POSTGRES="${USE_POSTGRES:-0}"

DJANGO_PID=""
if ! curl -sf "http://127.0.0.1:${PORT}/" >/dev/null 2>&1; then
  echo "啟動 Django → 127.0.0.1:${PORT}（SQLite）"
  python manage.py runserver "127.0.0.1:${PORT}" &
  DJANGO_PID=$!
  for _ in $(seq 1 30); do
    if curl -sf "http://127.0.0.1:${PORT}/" >/dev/null 2>&1; then
      break
    fi
    sleep 0.5
  done
else
  echo "Django 已在 port ${PORT} 運行"
fi

pkill -f "cloudflared tunnel --url http://127.0.0.1:${PORT}" 2>/dev/null || true
: > "$LOG"

echo "啟動 Cloudflare Quick Tunnel → http://127.0.0.1:${PORT}"
"$CF" tunnel --url "http://127.0.0.1:${PORT}" --logfile "$LOG" --loglevel info &
CF_PID=$!

cleanup() {
  kill "$CF_PID" 2>/dev/null || true
  if [[ -n "${DJANGO_PID:-}" ]]; then
    kill "$DJANGO_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

URL=""
for _ in $(seq 1 45); do
  sleep 1
  URL="$(grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" 2>/dev/null | head -1 || true)"
  if [[ -n "${URL:-}" ]]; then
    break
  fi
done

if [[ -z "${URL:-}" ]]; then
  echo "無法取得公開網址，請看 $LOG"
  exit 1
fi

echo ""
echo "============================================"
echo "  iPad Safari（重新整理即看到本機變更）："
echo "  $URL"
echo "  客戶搜尋：${URL}/search/"
echo "  （重啟後網址會變；不需 Cloudflare 域名）"
echo "============================================"
echo ""

wait "$CF_PID"
