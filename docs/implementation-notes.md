# OpenClaw Phase 1 實作說明

## 專案結構

- `web/`：Next.js App Router 前端工作台。
- `api/`：FastAPI 後端與 SQLite/FTS5 檢索能力。
- `samples/`：本地資料夾接入的範例檔案。

## OpenClaw 管理整合 Phase 1 MVP

本輪已新增 OpenClaw 管理整合骨架，重點如下：

- 後端新增 OpenClaw instance / secret / snapshot / operation log 資料表
- 後端新增 CLI adapter、hook client、instance/management/hook service 與管理 API
- 前端新增 `OpenClaw 管理` 導覽與 `overview / instances / agents / devices / config / logs / actions` 頁面
- 新增 OpenClaw 管理 API envelope，格式為 `success / data / error / meta`
- 新增後端 mock adapter 測試與前端管理頁互動測試

## 本輪刻意延後

- Gateway WebSocket RPC
- Channels / Approvals / QR / Pairing
- 真正的登入與 RBAC
- SSH / password 類型的 instance auth mode
- 自動事件路由與 project binding

## Phase 1 取捨

- 真接入只做本地資料夾。
- Google Drive / Notion 只保留 connector 介面與 disabled UI。
- 任務狀態採同步執行 + 可輪詢查詢，不額外引入背景工作系統。
