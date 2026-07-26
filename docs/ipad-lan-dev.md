# iPad 同 Wi‑Fi 測本機（固定區域 IP）

Mac 開發機建議固定為 **`192.168.0.165`**，iPad 永遠開同一網址：`http://192.168.0.165:8000/`。

## 1. 路由器：DHCP 保留（固定 Mac IP）

各品牌介面不同，概念相同：**把 Mac 的 Wi‑Fi MAC 位址綁定到 192.168.0.165**。

1. 查 Mac Wi‑Fi MAC（硬體位址）  
   **系統設定 → Wi‑Fi → 詳細資訊… → Wi‑Fi** → 複製 **MAC 位址**（或終端：`networksetup -getmacaddress Wi-Fi`）。
2. 登入家用路由器管理頁（常見 `192.168.0.1` 或 `192.168.1.1`，背面貼紙有帳密）。
3. 找到 **DHCP 保留 / Address Reservation / 靜態分配**（名稱依廠牌而異）。
4. 新增一筆：MAC = 上一步的位址，IP = **`192.168.0.165`**，儲存。
5. Mac：**系統設定 → Wi‑Fi → 詳細資訊… → TCP/IP** → 設為 **使用 DHCP**（保留由路由器發固定 IP，不必手動填 IP）。
6. 關閉再開 Wi‑Fi，或重開路由器；終端確認：`ipconfig getifaddr en0` 應為 `192.168.0.165`。

若你家子網不是 `192.168.0.x`，請在 `.env` 改 `DEV_LAN_IP` 為實際要固定的 IP，並在路由器保留同一個位址。

## 2. macOS 防火牆（iPad 連不上時）

**系統設定 → 網路 → 防火牆 → 選項** → 允許 **Python** 或你用的 **Terminal** 接受傳入連線。

## 3. 啟動 Django（區域網）

```bash
source .venv/bin/activate
./scripts/dev-lan.sh
```

腳本會以 `0.0.0.0:8000` 監聽，並在終端印出 iPad 網址。
