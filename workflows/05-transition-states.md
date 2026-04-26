# 階段 5：狀態轉換

## 狀態機

```
待辦事項 ──(start work / id:2)──▶ 進行中
                                    │
                                    ├──(Ready / id:3)──▶ 可供審查
                                    │                     │
                                    │                     ├──(UAT / id:5)──▶ UAT
                                    │                     │                   │
                                    │                     │                   └──(Release / id:4)──▶ 完成
                                    │                     │
                                    │                     └──(back / id:11)──▶ 進行中
                                    │
                                    └──(CANCEL / id:10)──▶ CANCEL

  完成 ──(back / id:14)──▶ 待辦事項
```

> **⚠ Transition ID 每專案不同，必須動態查詢：**  
> `python3 scripts/state_transition.py --list <KEY>`

## 完整推進路徑

從「待辦事項」到「完成」需 4 步：
1. 待辦事項 → 進行中（start work）
2. 進行中 → 可供審查（Ready）
3. 可供審查 → UAT（UAT）
4. UAT → 完成（Release）

## 使用 script

### 推進到可供審查（代碼完成但未測試）
```bash
python3 scripts/state_transition.py --keys keys.txt --target 可供審查
```

### 推進到完成（已測試通過）
```bash
python3 scripts/state_transition.py --keys passed.txt --target 完成
```

### 從完成退回可供審查（發現問題時）
```bash
python3 scripts/state_transition.py --keys redo.txt --target 可供審查
```

Script 會自動：
1. 查當前狀態
2. 動態取得可用 transitions
3. 找出最短路徑
4. 逐步執行

## 常見場景

### 情境 A：新建結構，全部預設進行中
建立後不轉狀態（預設落在「待辦事項」）→ 手動 transition 到「進行中」：
```bash
python3 scripts/state_transition.py --all-under PROJECT-XXX --target 進行中
```

### 情境 B：測試通過的自動推「完成」
```bash
# 1. 跑測試
php ~/.cache/jira-skill/module_tests.php
# 2. 根據結果推進
python3 scripts/state_transition.py --from ~/.cache/jira-skill/module_test_results.json
```

### 情境 C：全部退回重測
```bash
python3 scripts/state_transition.py --all-under PROJECT-XXX --target 進行中
```

## 批次原則

- **永遠先查當前狀態**（不假設）
- **動態取 transition id**（不寫死）
- **失敗立即停止該項目**（不繼續推進錯誤狀態）
- **結果寫 JSON 回報**
