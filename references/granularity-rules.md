# 顆粒度規則

## 核心數字

| 指標 | 值 |
|------|---|
| 每日有效工時 | 8 h |
| 每日 subtask 數 | 3 |
| **每 subtask 工時** | **2.67 h** |

## 模組工時 → Subtask 數 / 工作天速查

| 模組工時 | Subtask 數 | 工作天 | 節奏 |
|---------|-----------|-------|------|
| ≤ 3 h | 1 | 1 | 一個早上或下午 |
| 4–6 h | 2 | 1 | 一天內 |
| 7–10 h | 3 | 2 | 一天工作量 |
| 11–15 h | 4–5 | 2 | 1.5 天 |
| 16–22 h | 6–8 | 3 | 2–3 天 |
| > 22 h | **考慮拆成兩個模組** | — | — |

> 工作天 = ceil(工時 / 8h)。Due date 由 `structure_builder.py` 自動推算（跳週末），詳見 [workflows/02-design-granularity.md](../workflows/02-design-granularity.md)。

## 判斷「太細」的紅旗

- Subtask 內容只描述單一 class / method / file
- 預估工時 < 1 h
- 同一 feature 被拆成 5 個以上 subtask
- Subtask 標題裡只有檔名

## 判斷「太粗」的紅旗

- Subtask 預估工時 > 1 天
- Subtask 描述涵蓋多個 feature（用「以及」、「與」、「+」連接無關功能）
- 看 subtask 標題看不出要做什麼

## 合併示範

### 太細（5 個 → 1 個）
```
❌ composer.json 依賴定義
❌ artisan 專案建置
❌ Inertia Server + Client 橋接
❌ Vite 打包設定
❌ .env 範本
↓
✅ Laravel + Inertia + Vite 專案腳手架建置
```

### 太細（6 個 → 1 個）
```
❌ AppointmentCancelledMail 類別
❌ AppointmentCompletedMail 類別
❌ BookingReceivedMail 類別
❌ BookingStatusMail 類別
❌ FollowUpReminderMail 類別
❌ NewBookingAlertMail 類別
↓
✅ Email 通知信件組（6 封 Mailable）
```

### 太粗（1 個 → 2 個）
```
❌ 2FA 完整實作（後端 API + 前端 UI + 登入驗證 + 回復碼 + 設定頁）
↓
✅ 2FA TOTP 後端 API（QR / 金鑰 / 回復碼 Controller）
✅ 2FA TOTP 前端設定 UI + 回復碼元件
```

## 使用時的對話原則

當使用者說「顆粒度太細/太粗」時：
1. 計算當前 subtask 平均工時
2. 與 2.67 h 比對
3. 若 <1.5 h → 合併；若 >4 h → 拆分
4. 出示前後差異清單讓使用者確認再動 Jira
