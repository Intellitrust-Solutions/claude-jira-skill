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

```bash
git clone https://github.com/<your-account>/claude-jira-skill.git ~/.claude/skills/jira
cd ~/.claude/skills/jira
./install.sh
```

或手動：

```bash
cp .env.example .env
# 編輯 .env 填入 JIRA_BASE_URL / JIRA_EMAIL / JIRA_API_TOKEN
python3 scripts/jira_client.py selftest
```

## 前置條件

- Python 3.7+（用內建 `urllib` + `json`，無需 pip 套件）
- Jira Cloud 帳號 + [API token](https://id.atlassian.com/manage-profile/security/api-tokens)

## 使用

在 Claude Code 中觸發：

- 「幫我分析專案建 Jira 結構」
- 「在 PROJECT-491 底下建 modules 和 tasks」
- 「依完成度更新狀態」

或直接呼叫 CLI：

```bash
python3 scripts/jira_client.py whoami
python3 scripts/jira_client.py issuetypes
python3 scripts/jira_client.py transitions PROJECT-491
python3 scripts/jira_client.py check-mine PROJECT-491
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
