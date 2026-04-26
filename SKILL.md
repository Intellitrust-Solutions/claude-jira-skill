---
name: jira
description: 分析專案 codebase → 在 Jira 建立三層結構（Epic → 模組 → 小型任務）→ 實測驗證後推進狀態。內含可重用 Python 腳本與測試樣板。
---

# Jira 專案整合與結構管理

## 何時觸發

使用者說：
- 「幫我分析專案建 Jira 結構」
- 「在 PROJECT-xxx 底下建 modules 和 tasks」
- 「依完成度更新狀態」
- 「重新整理顆粒度」
- 或透過 slash command：`/jira analyze`、`/jira build`、`/jira test-done` 等

---

## 三層結構

```
Epic（大型工作 / hierarchyLevel=1）
└── Module（中型任務 / hierarchyLevel=0）— 依模組劃分
    └── Subtask（小型任務 / hierarchyLevel=-1）— 依實際工時（~2.7h/個）劃分
```

---

## 完整流程（5 階段）

| 階段 | 文件 | 產出 |
|------|------|------|
| 1 分析 | [workflows/01-analyze-codebase.md](workflows/01-analyze-codebase.md) | 模組清單 + 預估工時 |
| 2 顆粒度 | [workflows/02-design-granularity.md](workflows/02-design-granularity.md) | Subtask 數量與範圍 |
| 3 建立 | [workflows/03-build-structure.md](workflows/03-build-structure.md) | Jira 樹狀結構 |
| 4 測試 | [workflows/04-test-and-verify.md](workflows/04-test-and-verify.md) | 測試結果報告 |
| 5 狀態 | [workflows/05-transition-states.md](workflows/05-transition-states.md) | 推進到完成 |

---

## 前置條件

1. **環境變數**（`.env` 或 shell export）：
   ```
   JIRA_BASE_URL=https://xxx.atlassian.net
   JIRA_EMAIL=you@example.com
   JIRA_API_TOKEN=xxxx
   ```
2. **Python 3.7+**（用內建 `urllib` + `json`，無需 pip 套件）
3. **Epic Key**（例如 `PROJECT-491`），或授權 skill 先詢問

---

## 核心原則 + 安全保證

| 保證 | 實作位置 |
|------|---------|
| **憑證必備**：缺 `JIRA_BASE_URL`/`JIRA_EMAIL`/`JIRA_API_TOKEN` 直接 raise | `jira_client.py:from_env()` |
| **Epic 屬主驗證**：所有 destructive 操作前 `assert_mine(epic_key)` | `delete_subtree.py` / `state_transition.py` / `structure_builder.py` |
| **預設只動自己的 issue**（assignee 或 reporter）；要動別人需明確加 `--include-others` | `delete_subtree.py` / `state_transition.py` |
| **批次操作前 mine 過濾**：跳過非本人項並回報數量 | `state_transition.py` |
| **動態查 ID**（issuetype / transition 隨專案異） | 所有 script |
| **預設 dry-run** for 刪除；要 `--yes` 才真執行 | `delete_subtree.py` |
| **Test-before-Done**：沒實測不推「完成」 | `workflows/04-test-and-verify.md` |
| **連線自檢**：`python3 jira_client.py selftest` 一秒驗證 | `jira_client.py:selftest()` |

## 自檢指令

```bash
# 1. 驗證 token + accountId 可用
python3 .claude/skills/jira/scripts/jira_client.py selftest

# 2. 確認某 issue 屬於自己
python3 .claude/skills/jira/scripts/jira_client.py check-mine PROJECT-491
```

---

## 資產索引

| 類型 | 路徑 |
|------|------|
| 共用 API client | [scripts/jira_client.py](scripts/jira_client.py) |
| 結構建立 | [scripts/structure_builder.py](scripts/structure_builder.py) |
| 狀態轉換 | [scripts/state_transition.py](scripts/state_transition.py) |
| 擁有者過濾 | [scripts/ownership_filter.py](scripts/ownership_filter.py) |
| 子樹刪除 | [scripts/delete_subtree.py](scripts/delete_subtree.py) |
| 樹狀查詢 | [scripts/query_tree.py](scripts/query_tree.py) |
| PHP 測試樣板 | [templates/module_test.php.tmpl](templates/module_test.php.tmpl) |
| 顆粒度規則 | [references/granularity-rules.md](references/granularity-rules.md) |
| 狀態機 | [references/workflow-states.md](references/workflow-states.md) |
| 模組識別 | [references/module-heuristics.md](references/module-heuristics.md) |
