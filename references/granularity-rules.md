# 顆粒度規則（Lv2 嚴格版）

## 核心數字

| 指標 | 值 |
|------|---|
| 每日有效工時 | 8 h |
| 每日 subtask 數 | 3 |
| **每 subtask 目標工時** | **2.67 h** |
| **subtask 允許值** | **{1.5, 2, 2.5, 3}**（半小時錨點） |
| **subtask 軟區間** | **2.0 – 3.0 h**（落在此區間最理想） |

> Lv2 原則：消除「2.3 vs 2.4 是不是同一件事」的爭議 — `hours` 只能是 0.5h 的倍數，且只能是 1.5 / 2 / 2.5 / 3 這 4 個值。其他都是估算幻覺，必擋。

## 三道閘門（pre-flight 自動執行）

### 硬閘門（不可 `--force`）

| 條件 | 處置 |
|------|------|
| `subtask.hours` ∉ {1.5, 2, 2.5, 3} | 報錯。半小時錨點，禁止任意小數 |
| 實際工作 < 1.5h | 不開 subtask，**併入 module description** |
| 單一 subtask > 3h | 報錯。**拆成 2 個**（拆完每個都要 ≥ 1.5h） |
| `sum(module.subtasks.hours) > 22` | 報錯。**拆成兩個 module** |

### 軟警告（可 `--force` 但會列報告）

| 條件 | 警告 |
|------|------|
| `subtask.hours = 1.5`（< 軟下限 2.0） | 偏細，確認不該合併 |
| 模組總工時與 subtask 數量不對齊下表 | 數量與工時不對齊 |

## 選擇 subtask 數的順序

判斷一個模組要切幾個 subtask，**永遠依此順序**：

1. 先看「每個 subtask ∈ {1.5, 2, 2.5, 3}」 → 不滿足必擋
2. 再看「模組總工時 ≤ 22h」 → 超過就**拆模組**（不是增加 subtask 數）
3. 都過了才查下表決定數量

## 模組工時 → Subtask 數 速查

| 模組總工時 | Subtask 數 | 平均 | 工作天 | 排程節奏 |
|----------|-----------|-----|-------|---------|
| **< 1.5 h** | **0（併入 module description）** | — | — | — |
| 1.5 – 3 h | 1 | 1.5 – 3 | 0.5 | 半天 |
| 3 – 6 h | 2 | 1.5 – 3 | 1 | 1 天 |
| 6 – 9 h | 3 | 2 – 3 | 1 | **1 天飽滿**（=3 個/天） |
| 9 – 12 h | 4 | 2.25 – 3 | 1.5 | 1.5 天 |
| 12 – 15 h | 5 | 2.4 – 3 | 2 | 2 天 |
| 15 – 18 h | 6 | 2.5 – 3 | 2.5 | 2.5 天 |
| 18 – 21 h | 7 | 2.6 – 3 | 3 | 3 天 |
| 21 – 22 h | 8 | 2.6 – 2.75 | 3 | 3 天 |
| **> 22 h** | **拆成兩個 module** | — | — | — |

> 工作天 = ceil(工時 / 8h)。Due date 由 `structure_builder.py` 自動推算（跳週末），詳見 [workflows/02-design-granularity.md](../workflows/02-design-granularity.md)。

## 為什麼上限是 3h、不是 3.5h？

3.5h 體感接近半天，跟「一天 3 個」的節奏對不上 — 一個 3.5h 的 subtask 會讓當天只能塞 2 個，破壞排程模型。3h 是「飽滿但不溢出」的甜蜜點。

## 為什麼下限是 1.5h、不是 1h？

`< 1.5h` 的工作通常是「實作細節」（一個 config、一個 helper、一個簡單 method），不該佔 Jira 一個 ticket 的視覺空間。併到 module description 反而更清楚地呈現「這個模組順便也會處理這些瑣事」。

## 判斷「太細」的紅旗

- Subtask 內容只描述單一 class / method / file
- 預估工時 < 1.5 h（→ 硬閘門擋下）
- `hours` 是 0.3 / 0.7 / 1.2 這類非半小時粒度（→ 硬閘門擋下）
- 同一 feature 被拆成 5 個以上 subtask
- Subtask 標題裡只有檔名

## 判斷「太粗」的紅旗

- Subtask 預估工時 > 3 h（→ 硬閘門擋下）
- Subtask 描述涵蓋多個 feature（用「以及」、「與」、「+」連接無關功能）
- 看 subtask 標題看不出要做什麼

## 合併示範

### 太細 — 半小時錨點 + 併入 description（5 個 → 0 個 subtask）
```
❌ composer.json 依賴定義        (0.3h)   ← hours 不是半小時錨點
❌ artisan 專案建置              (0.4h)
❌ Inertia Server + Client 橋接  (0.5h)   ← < 1.5h
❌ Vite 打包設定                 (0.4h)
❌ .env 範本                     (0.4h)
↓ 合計 2h，全部觸發硬閘門
✅ Module: Laravel + Inertia + Vite 專案腳手架建置
   description 包含：composer.json 依賴 / artisan / Inertia 橋接 /
                    Vite 打包 / .env 範本
   subtasks: 1 個 — 「Laravel 腳手架建置與驗證」(2h)
```

### 太細 — 鎖定錨點後合併（6 個 → 1 個）
```
❌ AppointmentCancelledMail 類別  (0.5h each, 6 個合計 3h)
❌ AppointmentCompletedMail 類別
❌ BookingReceivedMail 類別
❌ BookingStatusMail 類別
❌ FollowUpReminderMail 類別
❌ NewBookingAlertMail 類別
↓ 每項 < 1.5h → 硬閘門擋下
✅ Email 通知信件組（6 封 Mailable） (3h, 1 個 subtask)
```

### 太粗 — 單一 subtask > 3h（1 個 → 2 個）
```
❌ 2FA 完整實作（後端 API + 前端 UI + 登入驗證 + 回復碼 + 設定頁）(6h)
↓ 單一 subtask > 3h → 硬閘門擋下
✅ 2FA TOTP 後端 API（QR / 金鑰 / 回復碼 Controller）(3h)
✅ 2FA TOTP 前端設定 UI + 回復碼元件                  (3h)
```

### 太粗 — 模組 > 22h（單模組 → 兩模組）
```
❌ 認證系統（登入/註冊/2FA/密碼/角色/Session）(28h, 10 subtasks)
↓ 模組總工時 > 22h → 硬閘門擋下
✅ 認證 — 帳號與 Session（登入/註冊/密碼/角色） (15h, 5 subtasks)
✅ 認證 — 2FA 與安全控管                       (13h, 5 subtasks)
```

## 使用時的對話原則

當使用者說「顆粒度太細/太粗」時：
1. 檢查每個 subtask 的 `hours` 是否 ∈ {1.5, 2, 2.5, 3}（**第一道**）
2. 計算當前 subtask 平均工時，與 2.67h 比對
3. 若全部都是 1.5h → 警告偏細，考慮合併
4. 若有 > 3h 或 < 1.5h 或非半小時錨點 → **硬閘門必擋**
5. 出示前後差異清單讓使用者確認再動 Jira
