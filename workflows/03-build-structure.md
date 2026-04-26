# 階段 3：建立 Jira 結構

## 前置檢查

1. 已有 Epic Key（例：`PROJECT-XXX`）
2. 階段 1、2 已完成（模組清單 + subtask 清單 + 各自的 due date）
3. `.env` 已設定 Jira 憑證

## 步驟

### A. 動態查 Issue Type ID

每個 Jira 專案的 issuetype id 不同，**永遠先查**：

```bash
python3 scripts/jira_client.py issuetypes
```

預期輸出類似：
```
10000 | 大型工作 | hierarchyLevel=1
10004 | 任務     | hierarchyLevel=0
10002 | Subtask  | hierarchyLevel=-1
```

記錄：
- Middle type id（hierarchyLevel=0）
- Subtask type id（hierarchyLevel=-1，subtask=true）

### B. 取得自己的 accountId

```bash
python3 scripts/jira_client.py whoami
```

### C. 列出現有子項（避免重建重複）

```bash
python3 scripts/query_tree.py <EPIC_KEY>
```

若已有舊結構，使用者**明確確認後**才刪除：

```bash
python3 scripts/delete_subtree.py <EPIC_KEY> --yes
```

### D. 批次建立

準備結構定義 JSON（或 Python dict），呼叫：

```bash
python3 scripts/structure_builder.py --plan plan.json
```

`plan.json` 格式：
```json
{
  "middles": [
    {
      "summary": "基礎建設與安全防護",
      "due": "2026-04-23",
      "subtasks": [
        {"summary": "Laravel 12 + Inertia + Vite 專案腳手架", "hours": 3},
        {"summary": "資料庫核心 migration", "hours": 2}
      ]
    }
  ]
}
```

### E. 驗證

```bash
python3 scripts/query_tree.py <EPIC_KEY>
```

確認所有中型與小型都建立，狀態都是「待辦事項」。

## 常見坑

1. **hierarchyLevel 必須父=子+1**，不能跳層
2. **subtask 的 parent 必須是中型**，不能直接掛 Epic
3. **中文 summary 要用 `ensure_ascii=True` 組 JSON**，否則 terminal 會亂碼
4. **API 限速**：建議每請求間隔 0.05–0.1 秒
5. **結果寫 `~/.cache/jira-skill/build_result.json`**（chmod 0600，避免同機其他使用者讀取），下一階段才能用

## 下一步

→ [04-test-and-verify.md](04-test-and-verify.md)
