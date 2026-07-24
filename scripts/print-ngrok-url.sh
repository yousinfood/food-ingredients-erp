#!/usr/bin/env bash
# ngrok 已在跑時，印出目前 HTTPS 公開網址
curl -sf http://127.0.0.1:4040/api/tunnels | python3 -c "
import json, sys
data = json.load(sys.stdin)
for t in data.get('tunnels', []):
    u = t.get('public_url', '')
    if u.startswith('https://'):
        print(u)
        break
else:
    print('找不到 https 隧道。請先執行 ./scripts/dev-ngrok.sh', file=sys.stderr)
    sys.exit(1)
"
