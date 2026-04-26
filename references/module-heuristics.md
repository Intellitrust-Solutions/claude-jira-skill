# 模組識別啟發法

## Laravel / PHP

### 掃描位置
- `app/Http/Controllers/` — 每個子目錄 / 同前綴 = 一個模組
- `resources/js/pages/` — 對應前端頁面（Inertia.js 常見）
- `routes/web.php` / `routes/api.php` — 路由分組
- `app/Models/` — 對應資料實體
- `app/Services/` — 商業邏輯（歸屬到它服務的模組）

### 模組歸納範例
```
CustomerController + customers/*.vue + /customers routes + Customer.php
  → 「顧客管理」模組
```

## Django / Python

### 掃描位置
- `apps/*/` 或 `project/*/` — 每個 app 一個模組
- `urls.py` — 路由分組
- `models.py` + `views.py` — 資料+邏輯
- `templates/<app>/` — 模板

### 模組通常就是 Django app

## Next.js / React

### 掃描位置
- `app/<route>/` 或 `pages/<route>/` — 路由區塊
- `lib/<domain>/` — 商業邏輯
- `components/<domain>/` — 特定模組元件
- `components/ui/` — 共用元件（不成模組）

### 判斷：同一路由區塊 + 同一 lib + 同一 components domain = 一個模組

## Ruby on Rails

### 掃描位置
- `app/controllers/<module>_controller.rb`
- `app/models/<entity>.rb`
- `app/views/<module>/*`
- `config/routes.rb` 的 namespace

## 共通原則

### 1. 從使用者功能視角歸納
不是「技術層面」分類，是「使用者用得到什麼 feature」。
- ✅ 顧客管理、預約排程、庫存管理
- ❌ Controllers 層、Models 層、Services 層

### 2. 基礎建設併入「基礎建設模組」
- Middleware（CORS、auth guards）
- 主題 CSS
- 資料庫 migration 骨架
- 開發工具配置

### 3. 認證相關視情況拆
- 小專案 → 併進 基礎建設
- 中專案 → 獨立「使用者認證」模組
- 大專案 → 拆「認證」+「權限」+「2FA」

### 4. 商業邏輯 Service 跟隨它服務的模組
```
SkinScoringService → 膚況分析模組（不獨立）
InventoryDeductionService → 庫存管理模組（不獨立）
NotificationService → 系統通知模組（若跨多功能才獨立）
```

## 典型專案的模組範例

> 以下取自 **SleepingBeauty 實作案例**，純作 reference。實際模組需由 Claude 依當前 codebase 重新識別。

### 美容業 ERP（SleepingBeauty 案例）
1. 基礎建設與安全防護
2. 使用者認證與 2FA
3. 個人設定
4. 顧客管理
5. 服務/療程分析與評分
6. 預約排程
7. 線上預約與顧客回饋
8. 庫存管理
9. Dashboard 與統計報表
10. 系統日誌與 Email 通知

### 電商平台
1. 基礎建設
2. 商品管理（SKU / 分類 / 圖片）
3. 訂單流程（購物車 / 結帳 / 付款）
4. 會員系統
5. 促銷/優惠券
6. 物流整合
7. 評價與客服
8. 後台管理

### SaaS Dashboard
1. 基礎建設
2. 認證與權限（多租戶）
3. 帳號與團隊管理
4. 核心功能（依業務領域）
5. 儀表板與報表
6. 整合 API（webhooks / SSO / 第三方）
7. 通知系統
8. 計費與訂閱

## 落實在 Jira

把模組當中型任務建立，**命名用功能描述**而非技術術語：
- ✅ 「顧客管理」
- ❌ 「CustomerController + Model + Views」
