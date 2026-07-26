# 食品原料 ERP

食品原料公司的企業資源規劃（ERP）系統，涵蓋庫存、採購、銷售、生產四大核心模組，界面為繁體中文。

## 功能模組

| 模組 | 功能 |
|------|------|
| **庫存管理** | 原料主檔、批次追蹤、保質期管理、溫區倉庫、庫存異動 |
| **採購管理** | 供應商管理、採購單、入庫驗收 |
| **銷售管理** | 客戶管理、銷售訂單、出貨追蹤 |
| **生產管理** | 配方/BOM、生產工單、領料計算 |

## 環境需求

- Python 3.10+
- macOS：需先安裝 Xcode Command Line Tools（`xcode-select --install`）

## 快速開始

```bash
cd ~/Projects/food-ingredients-erp

# 建立虛擬環境
python3 -m venv .venv
source .venv/bin/activate

# 安裝依賴
pip install -r requirements.txt

# 初始化資料庫
python manage.py migrate

# 載入示範資料（含管理員帳號）
python manage.py seed_data

# 啟動開發伺服器
python manage.py runserver
```

開啟瀏覽器：

- **前台 ERP**：http://127.0.0.1:8000/
- **管理後台**：http://127.0.0.1:8000/admin/

預設帳號：`admin` / `admin123`

## iPad 測本機（同一 Wi‑Fi，建議）

Mac 與 iPad 連**同一個 Wi‑Fi** 時，不必用隧道。開發機 IP 建議固定為 **`192.168.0.165`**（路由器 DHCP 保留步驟見 [docs/ipad-lan-dev.md](docs/ipad-lan-dev.md)）。

```bash
source .venv/bin/activate
./scripts/dev-lan.sh
```

終端以 `0.0.0.0:8000` 啟動 Django；iPad 開 **`http://192.168.0.165:8000/`**。  
若 iPad 連不上，腳本會提示檢查 macOS 防火牆（允許 Python 傳入連線）。

## iPad 遠端測本機（Cloudflare Quick Tunnel）

**不需 Cloudflare 域名、不需 Dashboard。** 從 iPad / 4G 用 HTTPS 連到你 Mac 上的 Django；改程式後在 iPad **重新整理** 即可。

```bash
source .venv/bin/activate
./scripts/dev-ipad.sh
```

終端會印出 **https://….trycloudflare.com**（每次重啟 cloudflared 網址會變，屬正常）。  
客戶搜尋：`https://….trycloudflare.com/search/`

本機仍用 **SQLite**（`.env` 預設 `USE_POSTGRES=0`）。

## iPad 遠端測本機（ngrok，選用）

從**任何網路**用 Safari 開本機 Django（HTTPS）。專案已允許 `*.ngrok-free.app` 的 Host / CSRF（僅 `DEBUG=True`）。

1. 安裝 ngrok：<https://ngrok.com/download> 或 `brew install ngrok/ngrok/ngrok`
2. 註冊後取得 authtoken：<https://dashboard.ngrok.com/get-started/your-authtoken>  
   `ngrok config add-authtoken <TOKEN>`
3. 在專案目錄：

```bash
source .venv/bin/activate
./scripts/dev-ngrok.sh 8001
```

終端會印出 **https://….ngrok-free.app**（每次重啟可能變動；付費可固定網域）。  
若 ngrok 已在跑：`./scripts/print-ngrok-url.sh`

或手動兩個終端：

```bash
export USE_NGROK=1
python manage.py runserver 0.0.0.0:8001
# 另一終端
ngrok http 8001
```

iPad 開啟：`https://xxxx.ngrok-free.app/search/`（首次可能需點 ngrok 警告頁「Visit Site」）。

## Railway 部署（固定 HTTPS，GitHub 自動部署）

**資料庫：** 請在 Railway 加 **PostgreSQL**（會自動注入 `DATABASE_URL`）。容器內 SQLite 重部署會清空，不適合 staging。

1. 將專案推到 GitHub（本 repo 需先 `git init` / 建立 remote）。
2. [Railway](https://railway.com) → New Project → **Deploy from GitHub repo** → 選此 repo。
3. 在 Railway 專案：**Add service → PostgreSQL**，並把 Postgres 的 `DATABASE_URL` 連到 Web service（Variables 參考 / 連結）。
4. Web service **Variables**（見 `railway.env.example`）：
   - `DEBUG` = `False`
   - `SECRET_KEY` = 隨機長字串（必填）
5. 每次 push `main` 會自動 build（`collectstatic`）+ `migrate` + 啟動 gunicorn。
6. **Settings → Networking → Generate Domain** → 得到 `https://xxx.up.railway.app`。
7. 首次部署後在 Railway Shell 或本地連線執行：`python manage.py seed_data`（示範資料 + admin）。

iPad 測試：`https://<你的網域>.up.railway.app/search/`

CLI（選用）：`npm i -g @railway/cli` → `railway login` → `railway link` → `railway up`

## 專案結構

```
food-ingredients-erp/
├── config/              # Django 設定
├── apps/
│   ├── core/            # 儀表板、共用功能
│   ├── inventory/       # 庫存管理
│   ├── procurement/     # 採購管理
│   ├── sales/           # 銷售管理
│   └── production/      # 生產管理
├── templates/           # 繁中 UI 模板
├── static/              # CSS 樣式
└── manage.py
```

## 後續擴充建議

- 質檢與合規追溯（HACCP 記錄）
- 財務模組（應收應付、發票）
- 條碼/QR Code 掃描入出庫
- 報表與數據分析
- PostgreSQL 生產環境部署

## 技術棧

- **後端**：Django 5
- **資料庫**：SQLite（開發）/ PostgreSQL（生產）
- **前端**：Django Templates + 自訂 CSS
