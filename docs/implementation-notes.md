# OpenClaw Phase 1 實作說明

## 專案結構

- `web/`：Next.js App Router 前端工作台。
- `api/`：FastAPI 後端與 SQLite/FTS5 檢索能力。
- `samples/`：本地資料夾接入的範例檔案。

## OpenClaw 管理整合 Phase 1 MVP

本輪已新增 OpenClaw 管理整合骨架，重點如下：

- 後端新增 OpenClaw instance / secret / snapshot / operation log 資料表
- 後端新增 agent capability registry，支援 per-agent `search_api` 能力開關
- 後端新增 CLI adapter、hook client、instance/management/hook service 與管理 API
- 後端新增 `openclaw/agent-tools/search`、`openclaw/agent-tools/document` 橋接 API，讓 agent 可查本專案索引
- 後端新增 repo-local `project-search` 原生 plugin，取代舊的 workspace exec 搜索腳本
- 前端新增 `OpenClaw 管理` 導覽與 `overview / instances / agents / devices / config / logs / actions` 頁面
- 前端 Agents 頁可開關 `search_api`，並顯示 native plugin / ACPX bridge readiness
- 新增 per-instance workflow agent mapping，可指定搜索 / 分析 / 報告三個 stage 分別交給哪個 OpenClaw agent
- 新增 OpenClaw 管理 API envelope，格式為 `success / data / error / meta`
- 新增後端 mock adapter 測試與前端管理頁互動測試

## 搜索-分析-報告一體化流程

本輪也把原本分離的 `/search`、`/analysis`、`/report` 收斂成以 `/search` 為主入口的 workflow 工作台，重點如下：

- 後端新增 `workflow_runs / workflow_stage_runs / workflow_events` 三張資料表
- 後端新增 `POST /api/v1/workflows/search-report`、`GET /api/v1/workflows/{run_id}`、`GET /api/v1/workflows`
- 後端以真實 OpenClaw agents 串行執行 `search -> analysis -> report`
- 前端 `/search` 會輪詢 workflow run，展示三階段進度、active agent、輸入輸出與事件時間線
- 最終輸出改為結構化報告 + Markdown 並保留整條處理鏈路
- `/analysis`、`/report` 不再是獨立主流程，會導回 `/search?runId=...`

## 本輪刻意延後

- Gateway WebSocket RPC
- Channels / Approvals / QR / Pairing
- 真正的登入與 RBAC
- SSH / password 類型的 instance auth mode
- 自動事件路由與 project binding
- plugin 自動卸載與獨立 plugin 管理頁

## Phase 1 取捨

- 真接入只做本地資料夾。
- Google Drive / Notion 只保留 connector 介面與 disabled UI。
- 任務狀態採同步執行 + 可輪詢查詢，不額外引入背景工作系統。
- workflow run 採背景 thread 串行執行，不額外引入 queue / worker 系統。
