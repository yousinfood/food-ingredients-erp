# 雲端 Staging 部署（Railway）

固定網址（HTTPS，任何網路皆可開，含 iPad 4G／Wi‑Fi）：

**https://web-production-dfc69.up.railway.app/**

| 用途 | 路徑 |
|------|------|
| 客戶搜尋 | 首頁 `/` 或 `/search/?q=關鍵字` |
| 健康檢查 | `/health/` → `200` 與文字 `ok` |
| 接單 | `/sales/orders/new/?customer=<id>` |

**iPad 日常操作：** 不必連公司 Wi‑Fi。Safari 開上方網址即可；建議「加入主畫面」當接單 App（見下方）。

本機開發仍用 **SQLite**（`.env` 設 `USE_POSTGRES=0`，`db.sqlite3` 勿刪）。Staging／Production 雲端用 **Railway PostgreSQL**。

---

## Railway 專案

| 項目 | 值 |
|------|-----|
| 儀表板 | [Railway → yousin-food-erp](https://railway.com/project/140aaf06-65b8-4921-b1d7-3b425efb118c) |
| 專案 | `yousin-food-erp` |
| 服務 | `web`（Django + Gunicorn + WhiteNoise） |
| 資料庫 | `Postgres`（持久化） |
| 公開網域 | `web-production-dfc69.up.railway.app` |

### 環境變數（Railway → web → Variables）

勿把密鑰提交到 Git。參考 `railway.env.example`。

| 變數 | 值 |
|------|-----|
| `DEBUG` | `False` |
| `SECRET_KEY` | Railway 內隨機字串 |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` |
| `RAILWAY_PUBLIC_DOMAIN` | `web-production-dfc69.up.railway.app` |
| `SECURE_SSL_REDIRECT` | `False`（Railway 邊界已 HTTPS） |

`config/settings.py` 會依 `RAILWAY_PUBLIC_DOMAIN` 設定 `ALLOWED_HOSTS`、`CSRF_TRUSTED_ORIGINS`、`SECURE_PROXY_SSL_HEADER`，以及 production 的 secure cookie。

### 靜態與媒體

- **CSS／JS：** build 時 `collectstatic`，執行時由 **WhiteNoise** 提供（`/static/...`）。
- **上傳檔（媒體）：** 目前 ERP 接單流程幾乎不用上傳。若日後需要持久化，在 Railway **web** 掛 **Volume**（例如 `/data/media`），並設 `MEDIA_ROOT=/data/media`。未掛 volume 時容器內 `media/` 會在重部署後清空；大量檔案可改 S3／R2（另案設定）。

---

## 部署流程

### 自動（推薦）：GitHub → Railway

1. 將本 repo push 到 GitHub（見下一節）。
2. Railway → **yousin-food-erp** → **web** → **Settings** → **Connect Repo** → 選 repo、分支 `main`。
3. 之後每次 `git push origin main` 自動 build／deploy。

### 手動（CLI）

```bash
export PATH="$HOME/.railway/bin:$PATH"
cd /path/to/food-ingredients-erp
railway login    # 帳號 yousinfood@gmail.com
railway link     # 選 yousin-food-erp → web
railway up
```

### Build／Deploy 步驟（`railway.toml`）

- **build：** `pip install -r requirements.txt` → `collectstatic --noinput`
- **release：** `migrate --noinput`
- **start：** `migrate` → `seed_data`（可重複）→ **Gunicorn**
- **healthcheck：** `GET /health/`（逾時 180s）

---

## GitHub repo 與第一次 push

本機若尚無 `origin`：

```bash
cd /path/to/food-ingredients-erp
# GitHub 網站：New repository → 例如 food-ingredients-erp（Private 可）
git remote add origin https://github.com/<帳號>/food-ingredients-erp.git
git push -u origin main
```

若 `git push` 要求登入：瀏覽器用 GitHub 帳號授權，或設定 [Personal Access Token](https://github.com/settings/tokens)（HTTPS），或改用 SSH remote。

連好 remote 並在 Railway **Connect Repo** 後，部署狀態可在 Railway → **web** → **Deployments** 查看。

---

## iPad：加入主畫面（像 App，免額外設定）

1. iPad 用 **Safari** 開啟：**https://web-production-dfc69.up.railway.app/**
2. 點網址列旁的 **分享**（方框＋箭頭）。
3. 選 **加入主畫面**。
4. 名稱可保留「有信接單」，按 **加入**。
5. 之後從主畫面圖示開啟：全螢幕、大按鈕；斷線時會顯示「目前沒有網路…」，恢復連線後會自動重新整理。

現場人員**不需要**改 Safari 設定、不需要 VPN、不需要記 IP。

---

## 回滾

1. Railway → **web** → **Deployments**
2. 選上一個 **SUCCESS** → **Redeploy**

Postgres 資料不會因程式回滾而還原；危險 migration 請用 Postgres **Backups**。

---

## 資料

- **尚未**從本機 SQLite 匯入 staging；確認網站正常後再另做匯入（不覆寫本機 `db.sqlite3`）。
- Staging 目前靠 `seed_data` 建立示範客戶／商品。

---

## 驗收清單

- [ ] `https://web-production-dfc69.up.railway.app/health/` → 200、`ok`
- [ ] 首頁搜尋可開
- [ ] `/static/css/touch.css` → 200
- [ ] 接單、儲存訂單；redeploy 後訂單仍在 Postgres
- [ ] iPad 主畫面圖示可全螢幕開啟

---

## 本機 LAN

本機 iPad 同 Wi‑Fi 測試見 `docs/ipad-lan-dev.md`。**Staging 驗收請只用上方 HTTPS 網址**，不要用 LAN IP 當正式環境。
