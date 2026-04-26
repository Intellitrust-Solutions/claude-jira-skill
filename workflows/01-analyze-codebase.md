# 階段 1：分析 Codebase → 模組清單

## 目的
從專案檔案結構歸納出**自然模組**（feature domains），作為中型任務層級。

## 掃描來源（依優先順序）

### Laravel / PHP 專案
- `app/Http/Controllers/` — 每個子目錄 / 同前綴 Controller = 一個模組
- `resources/js/pages/` — 對應前端頁面
- `routes/web.php` — 路由分組
- `app/Models/` — 資料實體關係
- `app/Services/` — 商業邏輯

### Django / Python
- `apps/*/` — 每個 app 一個模組
- `urls.py` — 路由分組
- `models.py` — 資料實體

### Next.js / React
- `app/` 或 `pages/` — 路由區塊
- `components/` — 共用元件（不獨立成模組）

## 歸納模組的判斷原則

1. **同一功能域的 Controller + View + Route + Model 視為同一模組**  
   範例：`CustomerController` + `customers/*.vue` + `/customers` routes + `Customer.php` = 「顧客管理」

2. **基礎建設與跨模組通用程式碼併入「基礎建設」模組**  
   範例：middleware、layouts、CSS 主題、migrations

3. **商業邏輯 service 併入它所服務的功能模組**  
   範例：`SkinScoringService` → 膚況分析模組

4. **認證、權限、2FA 視情況拆一個模組**  
   範例：Fortify + 2FA 合成「使用者認證與 2FA」

## 工時估算（粗略）

| 檔案類型 | 工時 |
|---------|------|
| Controller CRUD | 2–4h |
| Vue 頁面（中等複雜度） | 2–4h |
| Service class | 2–5h |
| Middleware | 1–2h |
| Migration（複雜表） | 0.5–1h |
| Model + 關聯 | 1–2h |

模組總工時 = 所有檔案工時加總。

## 輸出格式

以表格呈現給使用者確認：

```
| 模組 | 包含內容 | 預估工時 | 建議 subtask 數 |
|------|---------|---------|----------------|
| 顧客管理 | CustomerController + 3 Vue + Model | 12h | 4–5 |
| 膚況分析 | SkinAnalysisController + ScoringService + 3 Vue | 20h | 7–8 |
...
```

## 常見錯誤

- ❌ 把每個檔案當模組（太細）
- ❌ 把整個系統當一個模組（太粗）
- ❌ 強制湊滿 N 個模組（應該依實際功能域）

## 下一步

確認模組清單 → [02-design-granularity.md](02-design-granularity.md)
