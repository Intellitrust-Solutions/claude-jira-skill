# 階段 2：Subtask 顆粒度設計

## 核心原則

**每個 subtask ≈ 2.67 小時工時**（3 個/天 × 8 小時）

## 推導方式

1. 取得模組的預估總工時（階段 1 產出）
2. 除以 2.67 → 得到 subtask 建議數量
3. 用 **功能塊（feature block）** 切分，不用檔案切分

## 切分範例

### ✅ 好的顆粒度（功能塊級）
- 「Customer Model + 遷移 + CRUD Controller」（3h）
- 「顧客列表（關鍵字搜尋 + 膚質分類篩選 + 分頁）」（3h）
- 「5 維評分引擎（pores / hydration / oil 含加權）」（3h）

### ❌ 太細（檔案級 / method 級）
- 「Customer model 關聯設定」（15 min）
- 「composer.json 依賴定義」（10 min）
- 「CSP header 設定」（15 min）
- 「TwoFactorQrCodeController」（30 min）
- 「AppointmentCancelledMail 單封」（20 min）

### ❌ 太粗（超過一天）
- 「全部認證功能」（>20h，涵蓋登入/註冊/2FA/密碼/角色）
- 「整個庫存模組」（>20h）

## 合併策略

把以下**實作細節**併回功能塊：
- 同一個 service class 的各 private method → 1 個 subtask
- 同一個 CRUD 的各 Controller method → 1 個 subtask
- 一組有關聯的 Mailable / Notification → 1 個 subtask
- Migration + Model + Factory → 1 個 subtask（若邏輯簡單）

## 拆分策略

當一個「功能塊」>4h 時才拆：
- 後端 Service + 前端 UI → 2 個 subtask
- 多步驟流程 → 每 2–3 步 1 個 subtask
- 資料密集 feature（例如 5 維分數）→ 依維度群組分 2–3 個

## 數字速查表

| 模組預估工時 | Subtask 數 | 工作天 | 從起算日 +N 個工作日 |
|------------|-----------|-------|------------------|
| ≤ 3h | 1 | 1 | +0（當天） |
| 4–6h | 2 | 1 | +0 |
| 7–10h | 3 | 2 | +1 |
| 11–15h | 4–5 | 2 | +1 |
| 16–22h | 6–8 | 3 | +2 |
| > 22h | 考慮拆成兩個模組 | — | — |

> 工作天 = ceil(工時 / 8h)；自動跳過週末。
>
> Subtask 共用所屬 module 的 due（不每個 subtask 一個日期）。
>
> 模組依排序序列推進：模組 N+1 起算日 = 模組 N due + 1 工作日。

## Due date 推算（自動）

`structure_builder.py` 會自動推算 due date，**不需手填**：

```bash
# 從今天起算
python3 ~/.claude/skills/jira/scripts/structure_builder.py --plan plan.json

# 從指定日期起算（例如下週一開工）
python3 ~/.claude/skills/jira/scripts/structure_builder.py --plan plan.json --start-date 2026-05-04
```

優先序：
1. plan.json 中該 module 有 `"due": "YYYY-MM-DD"` → 用它
2. 沒給 → 依該 module 的 subtask 工時加總自動推算
3. 起算日：`--start-date` > plan.json 內 `start_date` > 今天

## 工作日設定

預設週一到週五。要改成「週二到週六」或其他組合，在 `~/.claude/skills/jira/.env` 加：

```
# 0=週一, 1=週二, 2=週三, 3=週四, 4=週五, 5=週六, 6=週日
JIRA_WORKING_DAYS=1,2,3,4,5    # 週二到週六
JIRA_WORKING_DAYS=0,1,2,3,4    # 週一到週五（預設）
JIRA_WORKING_DAYS=0,1,2,3,4,5  # 週一到週六（含小週末）
```

`structure_builder.py` 跑起來會印一行 `⚙ 工作日: ...` 確認當前設定。

## 範例：SleepingBeauty 案例（實作參考）

> 此為**實作案例**，數字僅供顆粒度感覺。你的專案模組數與工時必定不同 —— 由 Claude 依當前 codebase 估。

10 模組 → 54 subtasks，每 subtask 平均 ~2.7h，全部通過模組級測試。

| 模組 | 工時 | Subtasks |
|------|------|---------|
| 基礎建設與安全防護 | ~24h | 9 |
| 使用者認證與 2FA | ~16h | 6 |
| 個人設定 | ~11h | 5 |
| 顧客管理 | ~14h | 5 |
| 膚況分析與評分 | ~22h | 8 |
| 預約排程 | ~10h | 4 |
| 線上預約與顧客回饋 | ~9h | 3 |
| 庫存管理 | ~17h | 6 |
| Dashboard 與統計報表 | ~13h | 5 |
| 系統日誌與 Email 通知 | ~8h | 3 |

## 下一步

確認 subtask 清單 → [03-build-structure.md](03-build-structure.md)
