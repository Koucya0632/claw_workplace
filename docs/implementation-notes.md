# OpenClaw Phase 1 實作說明

## 專案結構

- `web/`：Next.js App Router 前端工作台。
- `api/`：FastAPI 後端與 SQLite/FTS5 檢索能力。
- `samples/`：本地資料夾接入的範例檔案。

## Phase 1 取捨

- 真接入只做本地資料夾。
- Google Drive / Notion 只保留 connector 介面與 disabled UI。
- 任務狀態採同步執行 + 可輪詢查詢，不額外引入背景工作系統。

