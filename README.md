# OpenClaw 智能辦公室 Phase 1

OpenClaw 智能辦公室是以 `搜索 -> 整理 -> 輸出` 為核心的本地優先 AI 工作台。  
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
- 可用能力：檔名搜索、全文搜索、文件預覽、單文件摘要、Markdown 匯出

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
- `/hooks/agent`、`/hooks/wake` 手動派發入口
- 本專案自己的操作審計紀錄與快照摘要

### 啟用前提

- API 執行環境需可呼叫 `openclaw` CLI
- API 與 OpenClaw Gateway 之間需可連線
- 若要保存 Gateway token，必須設定 `OPENCLAW_SECRET_KEY`

### OpenClaw 相關環境變數

```bash
OPENCLAW_CLI_BIN=openclaw
OPENCLAW_CLI_TIMEOUT_SECONDS=20
OPENCLAW_SECRET_KEY=請填入一組固定密鑰
```

若未設定 `OPENCLAW_SECRET_KEY`，仍可建立 Instance，但帶 token 的建立或更新操作會被拒絕。
