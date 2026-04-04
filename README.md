# OpenClaw 智能辦公室 Phase 1

OpenClaw 智能辦公室是以 `搜索 -> 分析 -> 報告` 為核心的本地優先 AI 工作台。  
這個版本包含：

- `web/`：Next.js 像素風多角色工作台
- `api/`：FastAPI 後端、SQLite metadata、FTS5 全文搜索
- `openclaw management`：OpenClaw Instance / Agents / Devices / Config / Logs / Hooks 管理台
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
4. 啟動 Web

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

## 測試

```bash
python3 -m pytest api/app/tests
npm --workspace web run test
```

## Phase 1 重點

- 真接入：本地資料夾
- 已預留：Google Drive / Notion connector 與 UI
- 可用能力：一體化搜索-分析-報告工作流、全文搜索、流程可視化、結構化報告、Markdown 匯出

## MiniMax 設定

若要啟用摘要，請在專案根目錄 `.env` 至少設定：

```bash
MINIMAX_API_KEY=你的金鑰
MINIMAX_API_URL=https://api.minimaxi.com/v1/chat/completions
MINIMAX_MODEL=MiniMax-M2.5
```

## OpenClaw 管理整合 Phase 1

本專案已新增 `OpenClaw 管理` 區域，提供：

- OpenClaw Instance 建立、編輯、健康檢查
- Agents / Devices / Config / Logs 管理 API 與前端頁面
- Workflow agent mapping 管理頁，可為每個 instance 指定搜索 / 分析 / 報告三個 stage 的 agent
- `/hooks/agent`、`/hooks/wake` 手動派發入口
- 本專案自己的操作審計紀錄與快照摘要
- 可選擇為特定 OpenClaw agent 開啟 `search_api`，透過 repo 內原生 plugin 將本專案搜索索引暴露為 native tool

## 一體化搜索-分析-報告流程

新版 `/search` 已整合成主流程工作台，會在同一頁中展示：

- 搜索、分析、報告三個固定階段
- 每個階段的負責 agent、狀態、進度、輸入與輸出
- 目前正在處理中的 agent 與整體 workflow 進度
- 完整事件時間線與最終結構化報告

在啟動流程前，請先到 `OpenClaw 管理 -> Workflow` 為目標 instance 配置：

- `search_agent_id`
- `analysis_agent_id`
- `report_agent_id`

配置完成後，`/search` 送出一次查詢就會自動串行跑完三個階段，並保留整條處理鏈路供回看。

### 啟用前提

- API 執行環境需可呼叫 `openclaw` CLI
- API 與 OpenClaw Gateway 之間需可連線
- 若要保存 Gateway token，必須設定 `OPENCLAW_SECRET_KEY`

### OpenClaw 相關環境變數

```bash
OPENCLAW_CLI_BIN=openclaw
OPENCLAW_CLI_TIMEOUT_SECONDS=20
OPENCLAW_AGENT_DISPATCH_TIMEOUT_SECONDS=90
OPENCLAW_SECRET_KEY=請填入一組固定密鑰
OPENCLAW_AGENT_TOOL_API_BASE_URL=http://127.0.0.1:8000/api/v1
OPENCLAW_AGENT_SEARCH_DEFAULT_LIMIT=5
OPENCLAW_AGENT_DOCUMENT_MAX_CHARS=8000
```

若未設定 `OPENCLAW_SECRET_KEY`，仍可建立 Instance，但帶 token 的建立或更新操作會被拒絕。

### OpenClaw Agent 搜索能力

在 `OpenClaw 管理 -> Agents` 頁面中，可以為個別 agent 開啟 `search_api`。啟用後，本專案會：

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
