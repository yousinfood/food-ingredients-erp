#!/usr/bin/env bash
# 本機驗證 production 設定（collectstatic + gunicorn）
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate
pip install -q -r requirements.txt
export DEBUG=False
export SECRET_KEY="${SECRET_KEY:-local-prod-test-key-change-me}"
export PORT=8000
python manage.py collectstatic --noinput
python manage.py migrate --noinput
echo "OK: collectstatic + migrate. Run: gunicorn config.wsgi:application --bind 0.0.0.0:8000"
