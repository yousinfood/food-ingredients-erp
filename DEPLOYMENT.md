# 雲端 Staging 部署（Railway）

固定網址（HTTPS）：

**https://web-production-dfc69.up.railway.app/**

- 客戶搜尋：`/search/` 或首頁 `/?q=關鍵字`
- 健康檢查：`/health/` → `200` 與文字 `ok`
- 接單：`/sales/orders/new/?customer=<id>`

本機開發仍用 **SQLite**（`db.sqlite3`），不要刪。Staging 使用 **Railway PostgreSQL**。

---

## 日常流程

1. 在本機改程式、用 SQLite 測試。
2. `git push` 到 GitHub（連好 Railway 後每次 push 自動部署）。
3. 用 iPad / Mac 開啟上方 **同一個 HTTPS 網址** 驗收。

若尚未連 GitHub，可手動部署：

```bash
cd /path/to/food-ingredients-erp
railway login
railway link   # 選 yousin-food-erp → web
railway up
```

---

## Railway 專案

| 項目 | 值 |
|------|-----|
| 專案 | `yousin-food-erp` |
| 服務 | `web`（Django + Gunicorn） |
| 資料庫 | `Postgres`（持久化） |
| 網域 | `web-production-dfc69.up.railway.app` |

### 必要環境變數（在 Railway → web → Variables）

已在雲端設定，**勿提交到 Git**：

- `DEBUG` = `False`
- `SECRET_KEY` =（Railway 內隨機產生）
- `DATABASE_URL` = `${{Postgres.DATABASE_URL}}`
- `RAILWAY_PUBLIC_DOMAIN` = `web-production-dfc69.up.railway.app`
- `SECURE_SSL_REDIRECT` = `False`（Railway 邊界已終止 HTTPS；也可依 `settings.py` 預設）

---

## 部署時自動執行

`railway.toml`：

- **build：** `collectstatic`（WhiteNoise 提供 CSS/JS）
- **start：** `migrate` → `seed_data`（示範資料，可重複執行）→ **Gunicorn**
- **healthcheck：** `GET /health/`

---

## 回滾（保留上一版）

1. Railway → 專案 → **web** → **Deployments**
2. 選上一個 **SUCCESS** 的部署 → **Redeploy**

資料庫不會因回滾程式而還原；若做過危險 migration，用 Postgres **備份還原**（Railway → Postgres → Backups）。

---

## 資料

- **尚未**從本機 SQLite 匯入 staging；確認網站正常後再另做匯入（不覆寫本機 `db.sqlite3`）。
- Staging 目前靠 `seed_data` 建立示範客戶／商品；正式資料匯入前請先備份 Postgres。

---

## 驗收清單

- [x] `https://web-production-dfc69.up.railway.app/health/` → 200
- [ ] 首頁與搜尋可開
- [ ] `/static/css/touch.css` → 200
- [ ] 接單、儲存訂單後 redeploy，訂單仍在

---

## 連接 GitHub（自動部署）

**現況：** 雲端已由 CLI／手動部署上線；GitHub remote 需在本機建立並 push 後，才能連自動部署。

### 1. 建立 GitHub repo 並 push（本機一次）

```bash
cd /path/to/food-ingredients-erp
# 在 GitHub 網站 New repository（建議名稱 food-ingredients-erp，Private 亦可）
git remote add origin https://github.com/<你的帳號>/food-ingredients-erp.git
git push -u origin main
```

若未安裝 GitHub CLI，可用瀏覽器建立空 repo 後再 `git push`。需登入 GitHub（HTTPS token 或 SSH key）。

### 2. Railway 連 repo

**Dashboard：** **yousin-food-erp** → **web** → **Settings** → **Connect Repo** → 選 repo → 分支 `main`。

**CLI（已 login）：**

```bash
export PATH="$HOME/.railway/bin:$PATH"
cd /path/to/food-ingredients-erp
railway link   # yousin-food-erp → web
railway service source connect --repo <帳號>/food-ingredients-erp --branch main --service web
```

之後每次 `git push origin main` 會自動 build／deploy。

### 環境變數名稱（Railway → web → Variables）

勿把值寫進 Git；清單見 `railway.env.example`：

- `DEBUG`
- `SECRET_KEY`
- `DATABASE_URL`
- `RAILWAY_PUBLIC_DOMAIN`
- `SECURE_SSL_REDIRECT`（選用）

---

## 本機 LAN / 隧道

Staging 驗收 **只用** 上方 HTTPS 網址，不要用 `127.0.0.1`、LAN IP 或 Quick Tunnel 當 staging。
