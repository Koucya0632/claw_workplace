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
- 前端新增 `OpenClaw 管理 -> Daily News`，可設定單一 Daily News Brief 與查看新聞 workflow 鏈路
- 前端新增 `OpenClaw 管理 -> System Inspection`，可設定版本巡檢、日誌視窗、Telegram 摘要與查看巡檢 workflow 鏈路
- 前端 Agents 頁可開關 `search_api`，並顯示 native plugin / ACPX bridge readiness
- 新增 per-instance workflow agent mapping，可指定主控秘書 agent、核心搜索 / 分析 / 報告 agent，以及多專職 agent 與 handoff policy
- 新增 OpenClaw 管理 API envelope，格式為 `success / data / error / meta`
- 新增後端 mock adapter 測試與前端管理頁互動測試

## 搜索-分析-報告一體化流程

本輪也把原本分離的 `/search`、`/analysis`、`/report` 收斂成以 `/search` 為主入口的 workflow 工作台，重點如下：

- 後端新增 `workflow_runs / workflow_stage_runs / workflow_events` 三張資料表
- 後端新增 `POST /api/v1/workflows/search-report`、`POST /api/v1/workflows/web-search`、`POST /api/v1/workflows/news-brief`、`POST /api/v1/workflows/{run_id}/continue-to-report`、`GET /api/v1/workflows/{run_id}`、`GET /api/v1/workflows`
- 後端以真實 OpenClaw agents 串行執行 `search -> analysis -> report`
- 後端新增第二種 `web_search` workflow type，使用 `understand -> search -> filter -> format` 四個 stage
- 後端新增第三種 `news_brief` workflow type，使用 `monitor -> search -> dedupe -> rank -> brief` 五個 stage
- 後端新增第四種 `system_inspection` workflow type，使用 `snapshot -> version_check -> log_review -> risk_assessment -> report` 五個 stage
- Daily News Telegram 投遞改走獨立 Bot API client，可與 OpenClaw 主聊天 bot 分離
- System Inspection 摘要可重用同一個 dedicated Telegram delivery client，不新增第三個 bot 配置
- 前端 `/search` 會輪詢 workflow run，展示各階段進度、active agent、輸入輸出與事件時間線
- 最終輸出改為結構化報告 + Markdown 並保留整條處理鏈路
- Web Search 支援自訂主題、網址 / 網站 / 網域、關鍵字、必須包含 / 排除條件、重點整理項與回傳格式
- Web Search 完成後可一鍵承接到分析 / 報告流程
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
- 主控秘書目前以系統層 orchestration + event timeline 方式落地，後續可再升級成真正的 controller agent turn。
- Daily News Brief 第一版只支援單一 brief 設定，固定每天 `09:00 JST` 自動執行與 Telegram 推送。
- System Inspection 第一版只做 application-layer 巡檢，不含主機 CPU / 記憶體 / 磁碟 / OS logs，固定每日 `09:30 JST` 執行。
