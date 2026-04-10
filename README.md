# OpenClaw 智能辦公室

OpenClaw 智能辦公室目前是一套本地優先的多 agent 工作台，核心能力已從單純的 `搜索 -> 分析 -> 報告`，擴充到：

- OpenClaw 多 agent / 多通道協作
- `Web Search + Knowledge Ingest` 搜尋即入庫
- Daily News / System Inspection / Development 標準化 workflow
- Sources / Knowledge / Workflow / Delivery 的後台治理能力

目前系統包含：

- `web/`：Next.js 像素風多角色工作台
- `api/`：FastAPI 後端、SQLite metadata、FTS5 全文搜索
- `packages/control-center-engine/`：由 `.openclaw-control-center-main` 內部化而來的 TS runtime / HTTP / SSE engine
- `OpenClaw Control Center`：`/openclaw` 主控台與底下的 `Admin Tools`，包含 Instances / Agents / Devices / Config / Logs / Hooks
- `samples/`：可直接拿來試跑的本地資料夾範例

## 開發前先讀

所有後續開發與修改，都必須先閱讀以下文件，並以 `docs/development-guidelines.md` 作為第一優先的專案內部開發規範。

1. `OpenClaw_智能辦公室_整體方案書.md`
2. `docs/development-guidelines.md`
3. `README.md`

## 啟動方式

1. 複製 `.env.example` 為 `.env`
2. 安裝依賴
3. 啟動 API
4. 啟動 Control Center Engine
5. 啟動 Web
6. 啟動 OpenClaw Gateway

若只開 Web 或只開 API，`OpenClaw Control Center` 會部分可用；若要讓融合後的 `/openclaw` 主控台、底下的 `Admin Tools`、Discord / Telegram、agent 派發與 workflow 都正常工作，**API、Control Center Engine 與 Gateway 需要同時存活**。

### 基本環境變數

至少先確認：

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
API_HOST=0.0.0.0
API_PORT=8000
OPENCLAW_DATABASE_PATH=./data/openclaw.sqlite3
CONTROL_CENTER_ENGINE_PORT=4310
CONTROL_CENTER_ENGINE_BASE_URL=http://127.0.0.1:4310
OPENCLAW_RUNTIME_DIR=./data/control_center_runtime
READONLY_MODE=true
LOCAL_TOKEN_AUTH_REQUIRED=true
APPROVAL_ACTIONS_ENABLED=false
APPROVAL_ACTIONS_DRY_RUN=true
IMPORT_MUTATION_ENABLED=false
IMPORT_MUTATION_DRY_RUN=false
GATEWAY_URL=ws://127.0.0.1:18789
```

### API

```bash
cd api
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

### Web

```bash
cd web
npm install
npm run dev
```

### Control Center Engine

```bash
cd /Users/rex/Desktop/claw_kaisya
npm install
npm run dev:control-center-engine
```

若要同時開 Web + Control Center Engine，可直接在專案根目錄執行：

```bash
npm run dev:control-center-ui
```

### OpenClaw Gateway

```bash
cd /Users/rex/Desktop/claw_kaisya
set -a
source .env
set +a
openclaw gateway
```

如果 `.env` 裡有 `DISCORD_BOT_TOKEN`、Telegram bot token 或其他 delivery token，請用同一個 shell 先 `source .env` 再啟動 Gateway。

## 測試

```bash
python3 -m pytest api/app/tests
npm run build:control-center-engine
npm run test:control-center-engine
npm --workspace web run test
npm --workspace web run build
```

## Phase 1 重點

- 真接入：本地資料夾
- 已預留：Google Drive / Notion connector 與 UI
- 可用能力：一體化搜索-分析-報告工作流、條件化 Web Search、全文搜索、流程可視化、結構化報告、Markdown 匯出

## MiniMax 設定

若要啟用摘要，請在專案根目錄 `.env` 至少設定：

```bash
MINIMAX_API_KEY=你的金鑰
MINIMAX_API_URL=https://api.minimaxi.com/v1/chat/completions
MINIMAX_MODEL=MiniMax-M2.5
```

## OpenClaw Control Center 整合

本專案已新增融合後的 `OpenClaw Control Center` 主控台，並把既有管理能力歸類到其底下的 `Admin Tools`，提供：

- `/openclaw` 作為新的主控入口，並拆分 `Overview / Usage / Staff / Collaboration / Hall / Tasks / Documents / Memory / Settings`
- 由 Next.js 同源代理 `/api/control-center/*` 連到內部 `control-center-engine`
- 既有 `/openclaw/instances`、`/agents`、`/workflow`、`/devices`、`/logs` 等 `Admin Tools` 頁面完整保留
- 整個 `/openclaw/*` 區域現在共用同一套 `OpenClaw Control Center` shell、導航分組與資訊層級
- `/openclaw/*` 的排版骨架直接以 `.openclaw-control-center-main` 的實際 UI 結構為基準：left rail、hero head、overview-v3、hall 三欄與 task-room workbench 節奏都往 reference 對齊
- `claw_kaisya` 只主導像素工作台的視覺語言、元件拆分與中文文案節奏，不再另外發明一套 OpenClaw 區域版型
- control-center runtime / SSE / hall / task room / usage / diagnostics 能力保留在 `packages/control-center-engine/`

`Admin Tools` 仍包含：

- OpenClaw Instance 建立、編輯、健康檢查
- Agents / Devices / Config / Logs 管理 API 與前端頁面
- Workflow agent mapping 頁，可為每個 instance 指定主控秘書 agent、核心搜索 / 分析 / 報告 agent，以及多個專職 agent
- Development 頁，可建立 `development_execution` workflow
- Knowledge 頁，可回看 ingestion runs、版本鏈與來源治理
- Daily News Brief 頁，可設定新聞主題、關鍵字、來源條件、Telegram 目標與每日排程
- System Inspection 頁，可設定版本更新巡檢、日誌風險評估與 Telegram 摘要推送
- Sources 頁面已升級成 dashboard + management table + detail drawer，可做搜尋、篩選、排序、同步、編輯、啟用/停用與刪除
- `/hooks/agent`、`/hooks/wake` 手動派發入口
- 本專案自己的操作審計紀錄與快照摘要
- 可選擇為特定 OpenClaw agent 開啟 `search_api`，透過 repo 內原生 plugin 將本專案搜索索引暴露為 native tool

### 目前建議架構

目前建議採用「1 個主控入口 + 4 個專職 agent + 3 類對外通道」：

| 類型 | 角色 | 說明 |
| --- | --- | --- |
| 主控 agent | `main` | 主控秘書 / controller，負責接需求、路由、整合結果與最終回覆 |
| 專職 agent | `support-agent` | 內部搜索、讀文件、整理證據，並作為 Discord support 專用頻道入口 |
| 專職 agent | `daily-news-brief-agent` | Daily News workflow 專職，不作一般聊天入口 |
| 專職 agent | `system-inspection-agent` | 巡檢 workflow 專職，不作一般聊天入口 |
| 專職 agent | `fullstack-engineer-agent` | 工程任務唯一執行入口，負責分析、設計、排期、開發、測試、優化與結構化匯報；模型固定走 `openai-codex/gpt-5.4`（OpenAI Codex OAuth） |
| 互動入口 | `AI Office` | 主聊天 bot 外殼，承接 Telegram / Discord 一般互動 |
| 報告投遞 | `小新` | Daily News 專用 delivery-only bot |
| 報告投遞 | `小巡` | System Inspection 專用 delivery-only bot |

### 目前建議通道路由

- Telegram 主入口 -> `main`
- Discord `#一般` (`1490189668254486650`) -> `main`，需 mention
- Discord support 專用頻道 (`1490333478942675076`) -> `support-agent`，不需 mention
- Discord develop 專用頻道 (`1490511097147687035`) -> `fullstack-engineer-agent`，不需 mention
- Daily News 報告 -> `小新`
- System Inspection 報告 -> `小巡`

這個拓撲的原則是：

- `main` 管入口與整合
- `support-agent` 管搜尋與 Discord support 專用頻道
- `fullstack-engineer-agent` 管工程任務執行與標準化匯報
- `daily-news-brief-agent` / `system-inspection-agent` 只跑各自 workflow
- 報告投遞 bot 與互動式入口 bot 分離，避免聊天通道與報告通道互相影響
- `support-agent` / `fullstack-engineer-agent` 在完成任務或到達穩定 checkpoint 後，會透過 agent-to-agent session tool 自動回報給 `main`

## 一體化搜索-分析-報告流程

新版 `/search` 已整合成主流程工作台，會在同一頁中展示：

- `Project Workflow`：搜索、分析、報告三個固定階段
- `Web Search + Ingest`：`understand -> search -> filter -> ingest -> format` 五個固定階段
- `Daily News Brief`：可在 `OpenClaw Control Center -> Admin Tools` 設定每日新聞監控、去重、排序、摘要與 Telegram 投遞
- `System Inspection`：可在 `OpenClaw Control Center -> Admin Tools` 設定版本巡檢、日誌問題聚合、風險排序與升級建議
- `Development`：可在 `OpenClaw Control Center -> Admin Tools` 建立工程任務，強制保留問題定義、需求分析、方案設計、選型、排期、開發、測試、優化與 handoff
- 每個階段的負責 agent、狀態、進度、輸入與輸出
- 目前正在處理中的 agent 與整體 workflow 進度
- 完整事件時間線與最終結構化報告
- Web Search 可自訂主題、網址 / 網站 / 網域、關鍵字、必須包含 / 排除條件、重點整理欄位與回傳格式
- 高價值 Web Search 結果會自動走 knowledge ingestion，並依 `topic + domain 集合 + source_type` 合併到既有 source；找不到才新建 source
- Web Search 完成後可一鍵把結果接續送入分析 / 報告流程

`/openclaw/knowledge` 現在的定位是知識治理與回看頁，用來查看：

- ingestion runs
- document 版本鏈
- source 合併與更新結果

它不再是主要接入入口；主要入口已是 `/search` 的 `Web Search + Ingest`。

在啟動流程前，請先到 `OpenClaw Control Center -> Admin Tools -> Workflow` 為目標 instance 配置：

- `controller_agent_id`
- `search_agent_id`
- `analysis_agent_id`
- `report_agent_id`
- `specialist_agents`
- `routing_rules`
- `handoff_policy`

配置完成後，`/search` 送出一次查詢就會自動串行跑完對應階段，並保留整條處理鏈路供回看。

### Development Workflow / Fullstack Engineer Agent

在 `OpenClaw Control Center -> Admin Tools -> Workflow` 頁面中，可以把 `Fullstack Engineer Agent` 綁到 `specialist_agents.fullstack_engineer`；之後 `OpenClaw Control Center -> Admin Tools -> Development` 就能建立 `development_execution` workflow。

這條 workflow 固定執行：

- `problem_definition`
- `requirements_analysis`
- `solution_design`
- `technology_selection`
- `task_planning`
- `implementation`
- `testing`
- `optimization`
- `handoff`

規則是：

- 前 8 個 stage 都由 `fullstack-engineer-agent` 執行
- `handoff` 由 `main` 接收並保存最終結構化報告
- 不允許跳過分析、設計與測試
- Discord 工程頻道只是 intake / 協作入口；正式追蹤與最終報告仍以 `development_execution` workflow run 為準

Discord 專用工程頻道目前已接到 `fullstack-engineer-agent`，頻道 ID 是 `1490511097147687035`。對應 route 如下：

```json
{
  "type": "route",
  "agentId": "fullstack-engineer-agent",
  "match": {
    "channel": "discord",
    "peer": {
      "kind": "channel",
      "id": "1490511097147687035"
    }
  }
}
```

這個 `channel_id` 目前不在 web UI 管理，若之後變更，需同步更新 repo 內 `.openclaw/openclaw.json` 與實際 OpenClaw runtime config。

### 啟用前提

- API 執行環境需可呼叫 `openclaw` CLI
- API 與 OpenClaw Gateway 之間需可連線
- 若要保存 Gateway token，必須設定 `OPENCLAW_SECRET_KEY`

### OpenClaw 相關環境變數

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
API_HOST=0.0.0.0
API_PORT=8000
OPENCLAW_DATABASE_PATH=./data/openclaw.sqlite3
OPENCLAW_CLI_BIN=openclaw
OPENCLAW_CLI_TIMEOUT_SECONDS=20
OPENCLAW_AGENT_DISPATCH_TIMEOUT_SECONDS=90
OPENCLAW_NEWS_AGENT_DISPATCH_TIMEOUT_SECONDS=180
OPENCLAW_SECRET_KEY=請填入一組固定密鑰
OPENCLAW_AGENT_TOOL_API_BASE_URL=http://127.0.0.1:8000/api/v1
OPENCLAW_AGENT_SEARCH_DEFAULT_LIMIT=5
OPENCLAW_AGENT_DOCUMENT_MAX_CHARS=8000
DISCORD_BOT_TOKEN=AI Office 主聊天 Discord bot token
OPENCLAW_DAILY_NEWS_TELEGRAM_BOT_TOKEN=每日新聞專用 Telegram bot token
OPENCLAW_DAILY_NEWS_TELEGRAM_TIMEOUT_SECONDS=20
OPENCLAW_DAILY_NEWS_DISCORD_BOT_TOKEN=每日新聞專用 Discord bot token
OPENCLAW_DAILY_NEWS_DISCORD_TIMEOUT_SECONDS=20
OPENCLAW_SYSTEM_INSPECTION_TELEGRAM_BOT_TOKEN=系統巡檢專用 Telegram bot token
OPENCLAW_SYSTEM_INSPECTION_TELEGRAM_TIMEOUT_SECONDS=20
OPENCLAW_SYSTEM_INSPECTION_DISCORD_BOT_TOKEN=系統巡檢專用 Discord bot token
OPENCLAW_SYSTEM_INSPECTION_DISCORD_TIMEOUT_SECONDS=20
OPENCLAW_DEVELOPMENT_DISCORD_BOT_TOKEN=Development workflow 專用 Discord bot token
OPENCLAW_DEVELOPMENT_DISCORD_TIMEOUT_SECONDS=20
OPENCLAW_KNOWLEDGE_DISCOVERY_TIMEOUT_SECONDS=15
OPENCLAW_KNOWLEDGE_FETCH_TIMEOUT_SECONDS=20
OPENCLAW_KNOWLEDGE_DEFAULT_LIMIT=5
```

若未設定 `OPENCLAW_SECRET_KEY`，仍可建立 Instance，但帶 token 的建立或更新操作會被拒絕。

可把這些環境變數理解成 4 組：

- 基礎啟動：`NEXT_PUBLIC_API_BASE_URL`、`API_HOST`、`API_PORT`、`OPENCLAW_DATABASE_PATH`
- OpenClaw / Gateway：`OPENCLAW_*`、`DISCORD_BOT_TOKEN`
- Daily News / Inspection / Development delivery：`OPENCLAW_DAILY_NEWS_*`、`OPENCLAW_SYSTEM_INSPECTION_*`、`OPENCLAW_DEVELOPMENT_*`
- Knowledge ingest：`OPENCLAW_KNOWLEDGE_*`

### OpenClaw Agent 搜索能力

在 `OpenClaw Control Center -> Admin Tools -> Agents` 頁面中，可以為個別 agent 開啟 `search_api`。啟用後，本專案會：

- 自動 link / enable repo 內的 `openclaw-plugins/project-search`
- 把 `plugins.entries.project-search.config` 寫入 OpenClaw config
- 若 ACPX runtime 已啟用，會同步打開 `pluginToolsMcpBridge`
- 只允許被啟用 capability 的 agent 看見原生工具 `project_search` / `project_document`

這樣 agent 之後會直接呼叫原生 tool，而不是透過 `exec` 跑 workspace 腳本，因此 Telegram / Web session 不需要再開 `exec` 核准。

原生 tool 內部仍會安全地查詢本專案的 `/api/v1/openclaw/agent-tools/search` 與 `/api/v1/openclaw/agent-tools/document` 橋接 API，而不需要直接碰前端專用搜索接口。

舊的 workspace script 路徑：

- `.openclaw-smart-office/project_search.py`
- `.openclaw-smart-office/search-config.json`
- `SEARCH_API.md`

已進入 deprecated 狀態，不再是預設執行路徑。

### Daily News Brief Agent

在 `OpenClaw Control Center -> Admin Tools -> Daily News` 頁面中，可以為單一 instance 設定一份 Daily News Brief：

- 新聞主題
- 關鍵字 / 產業 / 地區 / 人物 / 公司
- 指定來源網域 / URL
- 必須包含 / 排除條件
- 需要重點整理的資訊
- Telegram 或 Discord 推送目標

系統會每天 `09:00 JST` 自動建立 `news_brief` workflow run，並依序執行：

- `monitor`
- `search`
- `dedupe`
- `rank`
- `brief`

完成後會保留完整鏈路、最終 Markdown，以及 Telegram / Discord 投遞狀態；也可在 `Admin Tools` 頁手動重跑一次當日簡報。

Daily News 的報告推送可切換 Telegram 或 Discord；Telegram 走 `OPENCLAW_DAILY_NEWS_TELEGRAM_BOT_TOKEN`，Discord 走 `OPENCLAW_DAILY_NEWS_DISCORD_BOT_TOKEN`，因此可以和 `.openclaw/openclaw.json` 裡主聊天 bot 分離，不會影響 `main` agent 的聊天 channel。

### System Inspection & Risk Assessment Agent

在 `OpenClaw Control Center -> Admin Tools -> System Inspection` 頁面中，可以為單一 instance 設定一份應用層巡檢：

- 每日巡檢排程（預設 `09:30 JST`）
- 版本檢查開關
- 日誌巡檢開關
- 日誌視窗與巡檢數量上限

System Inspection 的報告推送也可切換 Telegram 或 Discord；Telegram 走 `OPENCLAW_SYSTEM_INSPECTION_TELEGRAM_BOT_TOKEN`，Discord 走 `OPENCLAW_SYSTEM_INSPECTION_DISCORD_BOT_TOKEN`。
- 官方版本來源 URL
- Telegram 摘要推送目標

系統會建立 `system_inspection` workflow run，固定執行：

- `snapshot`
- `version_check`
- `log_review`
- `risk_assessment`
- `report`

完成後會產出：

- 巡檢總結
- 版本更新檢查
- 系統日誌問題清單
- 高優先級風險
- 修復與優化建議
- 待確認事項
- 建議執行順序

並可選擇將摘要推送到 Telegram，幫助快速判斷：

- 是否建議升級
- 先修什麼
- 哪些結論仍需驗證

## support-agent 知識接入與沉澱

`support-agent` 現在除了查既有 `project_search` / `project_document` 索引外，也主理外部知識接入與沉澱。

`搜尋 -> 篩選 -> 下載/提取 -> 清洗 -> 分類 -> 入庫 -> 索引 -> 更新`

第一版重點：

- 使用外網搜尋或指定 URL 收集候選資料
- 抓取 HTML / PDF / 可下載文字內容
- 依可信度、相關性、重複性決定是否入庫
- 直接沉澱到既有 `documents + document_chunks + FTS`，不另建第二套知識庫
- 為文件補上 `source_url / canonical_url / published_at / business_type / topic_tags / credibility_tier`
- 支援版本追蹤與更新鏈
- 這條能力既可以透過 `POST /api/v1/knowledge/ingest` 直接呼叫，也會由 `/search` 的 `Web Search + Ingest` 自動觸發

### 新增 API

- `POST /api/v1/knowledge/ingest`
  啟動一次外部知識接入
- `GET /api/v1/knowledge/ingestion-runs`
  查看接入批次與每筆候選處理結果
- `GET /api/v1/knowledge/documents/{id}/versions`
  查看文件版本鏈
- `POST /api/v1/sources`
  建立通用 source，現在可建立 `local / web_page / url_list / rss_feed`
- `POST /api/v1/sources/{id}/scan`
  `local` 會走原本掃描流程；`web_page / url_list / rss_feed` 會走 knowledge ingest refresh

### 接入 payload 範例

```json
{
  "topic": "OpenClaw 安全更新",
  "query": "OpenClaw security update",
  "source_name": "OpenClaw Security Feed",
  "source_type": "web_page",
  "urls": ["https://docs.openclaw.ai/security/update-1"],
  "keywords": ["security", "workflow"],
  "business_type": "security"
}
```

### 新增環境變數

```bash
OPENCLAW_KNOWLEDGE_DISCOVERY_TIMEOUT_SECONDS=15
OPENCLAW_KNOWLEDGE_FETCH_TIMEOUT_SECONDS=20
OPENCLAW_KNOWLEDGE_DEFAULT_LIMIT=5
```

這三個值分別控制：

- 外網候選搜尋逾時
- 網頁 / 文件抓取逾時
- 單次知識接入預設候選上限

### main -> support-agent 固定交接契約

現在建議 `main` 對 `support-agent` 使用固定 handoff contract，避免每次臨時拼 prompt。

三種標準 intent：

1. `retrieve_existing_knowledge`
   只查既有索引與已入庫知識。
2. `acquire_new_knowledge`
   需要外部搜尋、篩選、接入與知識沉澱。
3. `organize_evidence`
   需要對現有資料做去重、整理與結構化交接。

建議 handoff payload：

```json
{
  "intent": "retrieve_existing_knowledge | acquire_new_knowledge | organize_evidence",
  "goal": "一句話說明任務目標",
  "user_request": "原始需求摘要",
  "question_to_answer": "support-agent 要支撐的核心問題",
  "constraints": {
    "preferred_sources": [],
    "forbidden_sources": [],
    "time_window": null,
    "must_include": [],
    "must_exclude": [],
    "business_type": null,
    "store_if_high_value": false
  },
  "known_context": [],
  "expected_output": {
    "format": "evidence_brief | ingest_summary | organized_notes",
    "max_items": 5
  }
}
```

建議回傳 payload：

```json
{
  "summary": "一句話總結",
  "status": "completed | partial | blocked",
  "sources_checked": [],
  "accepted_sources": [],
  "rejected_sources": [],
  "evidence": [],
  "knowledge_actions": {
    "created_sources": [],
    "updated_sources": [],
    "ingestion_runs": [],
    "stored_documents": []
  },
  "gaps": [],
  "recommended_next_step": "controller 下一步建議"
}
```

治理原則：

- `main` 只負責 intake、路由、整合與對外回覆
- `support-agent` 主理搜尋、證據、知識接入與整理
- 若只是查既有資料，不應自動擴大到外部接入
- 若需要沉澱新知識，必須明確打開 `store_if_high_value`
- 若證據不足，`support-agent` 應回 `partial` 或 `blocked`，而不是硬下結論
