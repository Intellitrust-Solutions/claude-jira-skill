# 階段 4：測試與驗證

## 職責分工

| 項目 | 由誰提供 |
|------|---------|
| 測試框架 + 統一輸出格式 | ✅ 此 skill（樣板 + state_transition 串接） |
| **實際測試內容**（驗證什麼 model/service/route） | ✅ **執行 skill 的當下，Claude 根據該專案 codebase 客製化** |
| Jira key 對應表 | ✅ 由 build 階段產出的 `/tmp/jira_build_result.json` 自動帶入 |

> Skill 不提供「跨專案通用測試」— 每個專案的測試內容必須由該次 Claude Code 對話**根據實際 codebase 撰寫**，否則只是空殼。

## 原則：Test-before-Done

**沒有測試證據絕不推「完成」**。預設所有新建 issue 落在「進行中」或「可供審查」。

| 證據 | 能推到哪 |
|------|---------|
| 代碼存在 + 整合 | 可供審查 |
| 自動化測試通過 | 完成 |
| 端對端手動測試 | 完成 |
| 僅檔案列表對齊 | ⚠ 不夠，只能可供審查 |

## 模組級整合測試

每個中型模組寫一個測試函式，驗證：

1. **Schema** — Model 欄位、表存在
2. **Class/Service 存在且可實例化**
3. **關鍵方法執行成功**（非 mock，真的呼叫）
4. **路由註冊**
5. **前端檔案存在**
6. **環境變數 / 憑證**
7. **端對端流程**（CRUD、扣庫、Email 發送等）

範本：[../templates/module_test.php.tmpl](../templates/module_test.php.tmpl)

## 跑測試

```bash
php /tmp/module_tests.php
```

輸出格式：
```
模組測試：PASS=10 / 共 10
✓ 基礎建設與安全防護  | 12 張表、6 套件、3 middleware、加密寫入皆 OK
✓ 使用者認證與 2FA    | Fortify + 9 routes + 角色系統皆齊
...
```

## 測試結果 → Jira 狀態映射

```bash
python3 scripts/state_transition.py --from /tmp/module_test_results.json
```

規則：
- 全模組 PASS → 該模組 + 所有 subtask 推「完成」
- 模組 FAIL → 該模組 + 所有 subtask 停在「進行中」
- 部分 FAIL → 只推 PASS 的模組

## 手動端對端測試建議

專案若有 UI，按鍵盤步驟也要測：
- 登入流程（含 2FA）
- 建立顧客 + 查看詳情
- 提交膚況問卷 → 看結果頁
- 建立預約 → 完成 → 確認扣庫
- 公開預約表單提交（含 Turnstile）
- 匯出 PDF

## 下一步

→ [05-transition-states.md](05-transition-states.md)
