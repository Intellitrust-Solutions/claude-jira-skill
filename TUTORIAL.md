# 教學：在專案中使用 claude-jira-skill

從 0 開始走完一輪：安裝 → 設定 → 在專案中觸發 → 推進狀態。

---

## Step 1：安裝 skill（全域，一次就好）

```bash
curl -sL https://raw.githubusercontent.com/Intellitrust-Solutions/claude-jira-skill/main/install.sh | bash
```

裝完會建立：
```
~/.claude/skills/jira/
├── .env          ← 從 .env.example 複製，待你填
├── SKILL.md
├── scripts/
└── ...
```

---

## Step 2：填個人憑證（全域，一次就好）

編輯 `~/.claude/skills/jira/.env`：

```bash
JIRA_BASE_URL=https://你的工作區.atlassian.net
JIRA_EMAIL=you@example.com
JIRA_API_TOKEN=從 https://id.atlassian.com/manage-profile/security/api-tokens 申請
```

驗證憑證能用：

```bash
python3 ~/.claude/skills/jira/scripts/jira_client.py selftest
```

預期輸出：
```json
{
  "base_url": "https://...",
  "account_id": "...",
  "display_name": "你的名字",
  "status": "OK"
}
```

---

## Step 3：在你的測試專案設定 Epic Key（每個專案一次）

到你想測試的專案根目錄（例如 `/var/www/your-project/`），編輯或新建 `CLAUDE.md`：

```markdown
# 你的專案名稱

本專案 Jira Epic: PROJECT-XXX
```

> Epic Key 寫在專案 CLAUDE.md 而非全域 .env 的原因：同個 Jira 帳號可能管多個專案，每個專案的 Epic 不同。

確認你是這個 Epic 的 assignee 或 reporter（skill 會擋非自己的）：

```bash
python3 ~/.claude/skills/jira/scripts/jira_client.py check-mine PROJECT-XXX
```

---

## Step 4：在 Claude Code 中觸發 skill

進入你的測試專案，啟動 Claude Code，試以下任一指令：

### 場景 A：分析 codebase 並建立 Jira 結構

> 「幫我分析這個專案的 codebase，在 PROJECT-XXX 底下建立 module 和 subtask」

Claude 會：
1. 讀 [workflows/01-analyze-codebase.md](workflows/01-analyze-codebase.md) → 掃描你的 codebase 識別模組
2. 讀 [workflows/02-design-granularity.md](workflows/02-design-granularity.md) → 估工時、切 subtask（~2.7h/個）
3. 給你一份模組 + subtask 計畫，**等你確認**才動手
4. 確認後執行 [scripts/structure_builder.py](scripts/structure_builder.py) 建立樹狀結構

### 場景 B：查當前結構

> 「查 PROJECT-XXX 底下的結構」

Claude 會跑 `python3 ~/.claude/skills/jira/scripts/query_tree.py PROJECT-XXX`。

### 場景 C：依完成度推進狀態

實作完某個模組、跑過測試後：

> 「模組 A 的測試都過了，幫我推進狀態」

Claude 會：
1. 讀 [workflows/04-test-and-verify.md](workflows/04-test-and-verify.md) → 確認**真的有測試結果**（沒測試不推完成）
2. 讀 [workflows/05-transition-states.md](workflows/05-transition-states.md) → 找對應 transition id
3. 跑 [scripts/state_transition.py](scripts/state_transition.py) → 推進該模組 + 所有 subtask

---

## Step 5：清理（可選）

如果想砍掉 Epic 底下整棵測試結構重來：

```bash
# 先 dry-run 看會刪什麼
python3 ~/.claude/skills/jira/scripts/delete_subtree.py PROJECT-XXX

# 確認無誤再加 --yes 真執行
python3 ~/.claude/skills/jira/scripts/delete_subtree.py PROJECT-XXX --yes
```

> 預設 dry-run、Epic 屬主驗證、只動自己的 issue —— 三層保護。

---

## 常見問題

### Q1：Claude 沒有自動觸發 skill？

確認 `~/.claude/skills/jira/SKILL.md` 存在。Claude Code 會自動掃描 `~/.claude/skills/`，但如果你的 Claude Code 版本太舊可能要重啟。

### Q2：`selftest` 失敗 401

Token 過期或 email 對不上。重新申請 token：https://id.atlassian.com/manage-profile/security/api-tokens

### Q3：`assert_mine` 報錯說不是我的

該 Epic 的 assignee 和 reporter 都不是你的帳號。要嘛：
- 到 Jira 把 Epic assignee 改成自己
- 或換一個是你的 Epic 來測試

這是刻意的安全保護，避免誤改別人的工作項。

### Q4：要改成測試別人的 issue 怎麼辦？

`state_transition.py` 和 `delete_subtree.py` 支援 `--include-others` flag，但只有在你**很確定**要動別人項目時用。預設就是只動自己。

---

## 更深入

- 安全保證原理：[SKILL.md](SKILL.md) 的「核心原則 + 安全保證」表格
- 顆粒度規則：[references/granularity-rules.md](references/granularity-rules.md)
- 狀態機：[references/workflow-states.md](references/workflow-states.md)
- 模組識別啟發法：[references/module-heuristics.md](references/module-heuristics.md)
