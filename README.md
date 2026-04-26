# claude-jira-skill

Claude Code 的 Jira skill — 自動分析專案 codebase，在 Jira 建立 Epic → Module → Subtask 三層結構，並依實測結果推進狀態。

## 功能

- **分析 codebase** → 產出模組清單與工時估算
- **三層結構建立**：Epic（hierarchyLevel=1）→ Module（=0）→ Subtask（=-1）
- **動態查 ID**（issuetype / transition 隨專案而異）
- **安全保證**：所有 destructive 操作前驗證 Epic 屬主；批次操作只動自己的 issue
- **預設 dry-run** for 刪除；要 `--yes` 才真執行
- **Test-before-Done**：沒實測不推「完成」

---

## 前置檢查

```bash
which python3 git    # 都要有
python3 --version    # 必須 ≥ 3.7
```

外加：

- Jira Cloud 帳號 + [API token](https://id.atlassian.com/manage-profile/security/api-tokens)
- 待測試的 Jira Epic（你必須是 assignee 或 reporter，否則 `assert_mine` 會擋）

---

## 安裝（全域，一次就好）

**一鍵安裝**（推薦）：

```bash
curl -sL https://raw.githubusercontent.com/Intellitrust-Solutions/claude-jira-skill/main/install.sh | bash
```

**手動安裝**：

```bash
git clone https://github.com/Intellitrust-Solutions/claude-jira-skill.git ~/.claude/skills/jira
cd ~/.claude/skills/jira
./install.sh
```

**Fork 版自用**：

```bash
REPO_URL=https://github.com/your-org/your-fork.git \
  curl -sL https://raw.githubusercontent.com/your-org/your-fork/main/install.sh | bash
```

---

## 第一次使用流程

依序跑完下面 5 步，每步都是前一步的 sanity check。

### 1. 編輯憑證

```bash
nano ~/.claude/skills/jira/.env
```

填入：

```
JIRA_BASE_URL=https://your-workspace.atlassian.net    # 必須 https://，否則會 raise
JIRA_EMAIL=you@example.com
JIRA_API_TOKEN=...
```

> 為什麼強制 `https://`：Basic Auth token 走 plaintext，`http://` 會被 jira_client.py 拒絕。

### 2. 自檢憑證

```bash
python3 ~/.claude/skills/jira/scripts/jira_client.py selftest
```

預期看到 `"status": "OK"`。401 → token 失效或 email 對不上。

### 3. 在測試專案的 CLAUDE.md 寫 Epic Key

到你想測試的專案根目錄，編輯 `CLAUDE.md`：

```markdown
本專案 Jira Epic: PROJECT-XXX
```

### 4. 驗證 Epic 屬主

```bash
python3 ~/.claude/skills/jira/scripts/jira_client.py check-mine PROJECT-XXX
```

`✓ 屬於你` → 繼續。`✗ 拒絕` → 到 Jira 把 Epic assignee 改成自己，或換一個是你的 Epic。

### 5. 在 Claude Code 中觸發

進入測試專案，啟動 Claude Code：

> 「幫我分析這個專案的 codebase，在 PROJECT-XXX 底下建 module 和 subtask」

Claude 會先給你計畫，**等你確認**才動手建立。

---

## 兩層設定（為什麼這樣拆）

設定刻意拆成兩層 —— 個人憑證跨專案共用，但 Epic Key 因專案而異。

### 全域層：`~/.claude/skills/jira/.env`

個人憑證，裝完一次就不用再動。

### 專案層：每個用 skill 的專案各自設定 Epic Key

三種放法擇一（依優先序）：

| 放法 | 範例 | 適用情境 |
|---|---|---|
| **專案 `CLAUDE.md`**（推薦） | `本專案 Epic: PROJECT-XXX` | Claude 自動讀進 context |
| 對話時直接講 | 「在 PROJECT-XXX 底下建模組」 | 最彈性 |
| 專案 `.env` | `JIRA_EPIC_KEY=PROJECT-XXX` | CI / 直接跑 CLI |

**為什麼不放全域**：Epic Key 跟著專案走。同一個 Jira 帳號可能要管 5 個專案的 Epic，全域只塞一個會誤改。

---

## 安全建議：先 dry-run

任何會動 Jira 的操作，建議先 dry-run 看會做什麼：

```bash
# 結構建立 dry-run
python3 ~/.claude/skills/jira/scripts/structure_builder.py --plan plan.json --dry-run

# 刪除預設就是 dry-run（不加 --yes 不會真刪）
python3 ~/.claude/skills/jira/scripts/delete_subtree.py PROJECT-XXX
```

確認無誤再去掉 `--dry-run` / 加 `--yes`。

---

## 常見錯誤對照表

| 症狀 | 原因 | 解法 |
|---|---|---|
| `selftest` 401 | token 過期或 email 對不上 | [重新申請 token](https://id.atlassian.com/manage-profile/security/api-tokens) |
| `JIRA_BASE_URL 必須以 https:// 開頭` | .env 填了 http:// | 改成 https:// |
| `assert_mine` 拒絕 | Epic 不是你的 assignee/reporter | 到 Jira 把 Epic assign 給自己，或換 Epic |
| `缺少 Epic Key` | 沒在 CLI 帶 + 沒設 JIRA_EPIC_KEY | 加 CLI 參數，或在專案 .env 設 |
| Claude 沒觸發 skill | Claude Code 沒掃到 `~/.claude/skills/jira` | 重啟 Claude Code |
| `import jira_client` 失敗 | 沒在 skill 目錄下跑 | 用 `~/.claude/skills/jira/scripts/...` 完整路徑 |

---

## CLI 速查

```bash
python3 ~/.claude/skills/jira/scripts/jira_client.py whoami
python3 ~/.claude/skills/jira/scripts/jira_client.py issuetypes
python3 ~/.claude/skills/jira/scripts/jira_client.py transitions PROJECT-XXX
python3 ~/.claude/skills/jira/scripts/jira_client.py check-mine PROJECT-XXX
python3 ~/.claude/skills/jira/scripts/query_tree.py PROJECT-XXX
python3 ~/.claude/skills/jira/scripts/query_tree.py PROJECT-XXX --stats
```

---

## 結構

```
claude-jira-skill/
├── SKILL.md                # skill 入口（Claude 讀這份）
├── scripts/                # Python 腳本（無外部依賴，純 stdlib）
│   ├── jira_client.py      # API client + output_path() + resolve_epic_key()
│   ├── structure_builder.py
│   ├── state_transition.py
│   ├── ownership_filter.py
│   ├── delete_subtree.py
│   └── query_tree.py
├── workflows/              # 5 階段流程文件
├── references/             # 顆粒度規則 / 狀態機 / 模組識別
└── templates/              # 測試樣板（PHP / Python / TS）
```

詳見 [SKILL.md](SKILL.md)。

## 輸出位置

所有腳本輸出寫到 `~/.cache/jira-skill/`（chmod 0700 / 0600），避免共享機其他使用者讀取。

## License

MIT
