# 階段 2：Subtask 顆粒度設計（Lv2 嚴格版）

## 核心原則

每個 subtask 的 `hours` **只能是** `1.5 / 2 / 2.5 / 3`（半小時錨點），目標 ≈ 2.67h、軟區間 2.0–3.0h。

> 完整規則與例外處置見 [references/granularity-rules.md](../references/granularity-rules.md)。

## 推導方式

1. 取得模組的預估總工時（階段 1 產出）
2. 套用「選擇順序」（見 granularity-rules.md）
3. 用 **功能塊（feature block）** 切分，不用檔案切分
4. 每個 subtask 從 {1.5, 2, 2.5, 3} 中選一個合理值，不可填 2.3 / 2.7 等

## 切分範例

### ✅ 好的顆粒度（功能塊級 + 錨點數值）
- 「Customer Model + 遷移 + CRUD Controller」 (3h)
- 「顧客列表（關鍵字搜尋 + 膚質分類篩選 + 分頁）」 (3h)
- 「5 維評分引擎（pores / hydration / oil 含加權）」 (3h)
- 「Email 通知信件組（6 封 Mailable）」 (3h)

### ❌ 太細（< 1.5h，併入 module description）
- 「Customer model 關聯設定」 (0.25h)
- 「composer.json 依賴定義」 (0.3h)
- 「CSP header 設定」 (0.25h)
- 「TwoFactorQrCodeController」 (0.5h)
- 「AppointmentCancelledMail 單封」 (0.5h)

### ❌ 數字違規（非半小時錨點）
- subtask hours = 2.3 → 改 2 或 2.5
- subtask hours = 0.8 → 併入 description
- subtask hours = 3.5 → 拆成兩個

### ❌ 太粗（單一 subtask > 3h）
- 「全部認證功能」(>20h，涵蓋登入/註冊/2FA/密碼/角色) → 拆成兩個 module
- 「整個庫存模組」(>20h) → 拆成兩個 module

## 合併策略

當以下情況出現 → 併回 module description（不開 subtask）：
- 同一個 service class 的各 private method
- 同一個 CRUD 的各 Controller method
- 一組有關聯的 Mailable / Notification
- 簡單的 Migration + Model + Factory（< 1.5h）

> module description 是塞「實作細節清單」的地方，讓 < 1.5h 的瑣事有歸宿。

## 拆分策略

當一個「功能塊」> 3h 時必須拆（硬閘門擋下）：
- 後端 Service + 前端 UI → 2 個 subtask
- 多步驟流程 → 每 2–3 步 1 個 subtask
- 資料密集 feature（例如 5 維分數）→ 依維度群組分 2–3 個

## 數字速查表

| 模組總工時 | Subtask 數 | 平均 | 工作天 | 從起算日 +N |
|----------|-----------|-----|-------|------------|
| < 1.5h | 0（併 desc） | — | — | — |
| 1.5–3h | 1 | 1.5–3 | 0.5 | +0 |
| 3–6h | 2 | 1.5–3 | 1 | +0 |
| 6–9h | 3 | 2–3 | 1 | +0 |
| 9–12h | 4 | 2.25–3 | 1.5 | +1 |
| 12–15h | 5 | 2.4–3 | 2 | +1 |
| 15–18h | 6 | 2.5–3 | 2.5 | +2 |
| 18–21h | 7 | 2.6–3 | 3 | +2 |
| 21–22h | 8 | 2.6–2.75 | 3 | +2 |
| > 22h | 拆模組 | — | — | — |

> 工作天 = ceil(工時 / 8h)；自動跳過週末。
>
> Subtask 共用所屬 module 的 due（不每個 subtask 一個日期）。
>
> 模組依排序序列推進：模組 N+1 起算日 = 模組 N due + 1 工作日。

## Pre-flight 自動驗證（**進入階段 3 前必跑**）

plan.json 草稿產出後，**強制**先跑 `--check-only`，通過才進入階段 3 真正上傳：

```bash
# 純驗證（不連 Jira、不上傳）— 階段 2 結尾必跑
python3 scripts/structure_builder.py --plan plan.json --check-only

# 正常上傳（同樣會跑 pre-flight，硬閘門擋下會 exit）
python3 scripts/structure_builder.py --plan plan.json

# 軟警告也擋下（最嚴）
python3 scripts/structure_builder.py --plan plan.json --strict

# 略過軟警告（硬閘門仍擋）— 注意：dry-run 也適用
python3 scripts/structure_builder.py --plan plan.json --force
```

擋下的條件見 [references/granularity-rules.md](../references/granularity-rules.md#三道閘門pre-flight-自動執行)。

## Due date 推算（自動）

`structure_builder.py` 會自動推算 due date，**不需手填**：

```bash
# 從今天起算
python3 ~/.claude/skills/jira/scripts/structure_builder.py --plan plan.json

# 從指定日期起算
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

> 注意：上表「基礎建設」=24h 已超出 Lv2 的 22h 上限，新案例應拆成兩個 module。
> SleepingBeauty 案例建於 Lv2 規則之前，僅作顆粒度感覺參考。

## 下一步

確認 subtask 清單 → [03-build-structure.md](03-build-structure.md)
