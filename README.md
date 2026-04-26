# claude-jira-skill

Claude Code 的 Jira skill — 自動分析專案 codebase，在 Jira 建立 Epic → Module → Subtask 三層結構，並依實測結果推進狀態。

## 功能

- **分析 codebase** → 產出模組清單與工時估算
- **三層結構建立**：Epic（hierarchyLevel=1）→ Module（=0）→ Subtask（=-1）
- **動態查 ID**（issuetype / transition 隨專案而異）
- **安全保證**：所有 destructive 操作前驗證 Epic 屬主；批次操作只動自己的 issue
- **預設 dry-run** for 刪除；要 `--yes` 才真執行
- **Test-before-Done**：沒實測不推「完成」

## 安裝

**一鍵安裝**（推薦，會自動 clone 到 `~/.claude/skills/jira`）：

```bash
curl -sL https://raw.githubusercontent.com/Intellitrust-Solutions/claude-jira-skill/main/install.sh | bash
```

**手動安裝**：

```bash
git clone https://github.com/Intellitrust-Solutions/claude-jira-skill.git ~/.claude/skills/jira
cd ~/.claude/skills/jira
./install.sh
```

裝完後編輯 `~/.claude/skills/jira/.env` 填入憑證，再跑：

```bash
python3 ~/.claude/skills/jira/scripts/jira_client.py selftest
```

## 前置條件

- Python 3.7+（用內建 `urllib` + `json`，無需 pip 套件）
- Jira Cloud 帳號 + [API token](https://id.atlassian.com/manage-profile/security/api-tokens)

## 兩層設定（重要）

設定刻意拆成兩層 —— 個人憑證跨專案共用，但 Epic Key 因專案而異：

### 全域層：`~/.claude/skills/jira/.env`
個人憑證，裝完一次就不用再動：
```
JIRA_BASE_URL=https://your-workspace.atlassian.net
JIRA_EMAIL=you@example.com
JIRA_API_TOKEN=...
```

### 專案層：每個用 skill 的專案各自設定 Epic Key

三種放法擇一（依優先序）：

| 放法 | 範例 | 適用情境 |
|---|---|---|
| **專案 `CLAUDE.md`**（推薦） | `本專案 Epic: PROJECT-XXX` | Claude 自動讀進 context，不用每次講 |
| 對話時直接講 | 「在 PROJECT-XXX 底下建模組」 | 最彈性 |
| 專案 `.env` | `JIRA_EPIC_KEY=PROJECT-XXX` | CI / 直接跑 CLI |

**為什麼不放全域**：Epic Key 跟著專案走，不該跟個人憑證綁在一起。例如同一個 Jira 帳號可能要管 5 個專案的 Epic，全域只塞一個就會誤改。

## 使用

在 Claude Code 中觸發：

- 「幫我分析專案建 Jira 結構」
- 「在 PROJECT-XXX 底下建 modules 和 tasks」
- 「依完成度更新狀態」

或直接呼叫 CLI（裝完後用 `~/.claude/skills/jira/` 為基準）：

```bash
python3 ~/.claude/skills/jira/scripts/jira_client.py whoami
python3 ~/.claude/skills/jira/scripts/jira_client.py issuetypes
python3 ~/.claude/skills/jira/scripts/jira_client.py transitions PROJECT-XXX
python3 ~/.claude/skills/jira/scripts/jira_client.py check-mine PROJECT-XXX
```

## 結構

```
claude-jira-skill/
├── SKILL.md                # skill 入口
├── scripts/                # Python 腳本（無外部依賴）
│   ├── jira_client.py      # API client
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

## License

MIT
