from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

API_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = API_DIR.parent


class Settings(BaseSettings):
    # 讓設定類別自動從 .env 讀值，方便本地啟動與測試重用同一套設定來源。
    model_config = SettingsConfigDict(
        # 同時支援從 api/ 目錄與專案根目錄啟動服務，避免工作目錄不同就讀不到 .env。
        env_file=(API_DIR / ".env", REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API 啟動所需的主機與連接埠。
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")

    # SQLite 路徑會在第一次啟動時自動建立父目錄。
    database_path: str = Field(default="./data/openclaw.sqlite3", alias="OPENCLAW_DATABASE_PATH")

    # 本地資料夾 connector 只能掃描這個根路徑之內的資料，避免任意越界。
    local_source_base_path: str = Field(default="./samples/local_source", alias="OPENCLAW_LOCAL_SOURCE_BASE_PATH")

    # 支援的副檔名集合由字串拆成列表，方便 parser 與 UI 一起共用。
    allowed_extensions: str = Field(default="pdf,docx,txt,md,csv,xlsx", alias="OPENCLAW_ALLOWED_EXTENSIONS")

    # 摘要前先限制輸入長度，避免超長文件直接打爆模型配額與請求時間。
    summary_max_chars: int = Field(default=16000, alias="OPENCLAW_SUMMARY_MAX_CHARS")

    # OpenClaw 管理整合 Phase 1 透過 CLI 與 Hooks 對 Gateway 溝通。
    openclaw_cli_bin: str = Field(default="openclaw", alias="OPENCLAW_CLI_BIN")
    openclaw_cli_timeout_seconds: int = Field(default=20, alias="OPENCLAW_CLI_TIMEOUT_SECONDS")
    openclaw_agent_dispatch_timeout_seconds: int = Field(default=90, alias="OPENCLAW_AGENT_DISPATCH_TIMEOUT_SECONDS")
    openclaw_news_agent_dispatch_timeout_seconds: int = Field(default=180, alias="OPENCLAW_NEWS_AGENT_DISPATCH_TIMEOUT_SECONDS")
    openclaw_workflow_dispatch_retry_count: int = Field(default=1, alias="OPENCLAW_WORKFLOW_DISPATCH_RETRY_COUNT")
    openclaw_workflow_dispatch_retry_backoff_ms: int = Field(default=1200, alias="OPENCLAW_WORKFLOW_DISPATCH_RETRY_BACKOFF_MS")
    openclaw_secret_key: str = Field(default="", alias="OPENCLAW_SECRET_KEY")
    openclaw_agent_tool_api_base_url: str = Field(default="", alias="OPENCLAW_AGENT_TOOL_API_BASE_URL")
    openclaw_agent_search_default_limit: int = Field(default=5, alias="OPENCLAW_AGENT_SEARCH_DEFAULT_LIMIT")
    openclaw_agent_document_max_chars: int = Field(default=8000, alias="OPENCLAW_AGENT_DOCUMENT_MAX_CHARS")
    openclaw_knowledge_discovery_timeout_seconds: int = Field(default=15, alias="OPENCLAW_KNOWLEDGE_DISCOVERY_TIMEOUT_SECONDS")
    openclaw_knowledge_fetch_timeout_seconds: int = Field(default=20, alias="OPENCLAW_KNOWLEDGE_FETCH_TIMEOUT_SECONDS")
    openclaw_knowledge_default_limit: int = Field(default=5, alias="OPENCLAW_KNOWLEDGE_DEFAULT_LIMIT")
    openclaw_daily_news_telegram_bot_token: str = Field(default="", alias="OPENCLAW_DAILY_NEWS_TELEGRAM_BOT_TOKEN")
    openclaw_daily_news_telegram_timeout_seconds: int = Field(default=20, alias="OPENCLAW_DAILY_NEWS_TELEGRAM_TIMEOUT_SECONDS")
    openclaw_daily_news_discord_bot_token: str = Field(default="", alias="OPENCLAW_DAILY_NEWS_DISCORD_BOT_TOKEN")
    openclaw_daily_news_discord_timeout_seconds: int = Field(default=20, alias="OPENCLAW_DAILY_NEWS_DISCORD_TIMEOUT_SECONDS")
    openclaw_system_inspection_telegram_bot_token: str = Field(default="", alias="OPENCLAW_SYSTEM_INSPECTION_TELEGRAM_BOT_TOKEN")
    openclaw_system_inspection_telegram_timeout_seconds: int = Field(default=20, alias="OPENCLAW_SYSTEM_INSPECTION_TELEGRAM_TIMEOUT_SECONDS")
    openclaw_system_inspection_discord_bot_token: str = Field(default="", alias="OPENCLAW_SYSTEM_INSPECTION_DISCORD_BOT_TOKEN")
    openclaw_system_inspection_discord_timeout_seconds: int = Field(default=20, alias="OPENCLAW_SYSTEM_INSPECTION_DISCORD_TIMEOUT_SECONDS")

    # LLM provider 先保留抽象，只在這一版預設選 minimax。
    llm_provider: str = Field(default="minimax", alias="OPENCLAW_LLM_PROVIDER")
    minimax_api_key: str = Field(default="", alias="MINIMAX_API_KEY")
    minimax_api_url: str = Field(default="", alias="MINIMAX_API_URL")
    minimax_model: str = Field(default="MiniMax-M2.5", alias="MINIMAX_MODEL")
    minimax_timeout_seconds: int = Field(default=30, alias="MINIMAX_TIMEOUT_SECONDS")

    @property
    def database_file(self) -> Path:
        # 將資料庫字串轉成 Path，後續初始化 schema 與連線會共用這個結果。
        return Path(self.database_path).expanduser().resolve()

    @property
    def source_root(self) -> Path:
        # 本地資料源根目錄統一轉為絕對路徑，減少每個 connector 自己處理的重複邏輯。
        return Path(self.local_source_base_path).expanduser().resolve()

    @property
    def allowed_extension_list(self) -> list[str]:
        # 去除空白與點號，避免使用者在 env 中寫成 ".md, .txt" 時失效。
        cleaned: list[str] = []
        for item in self.allowed_extensions.split(","):
            normalized = item.strip().lower().lstrip(".")
            if normalized:
                cleaned.append(normalized)
        return cleaned

    @property
    def openclaw_agent_tool_api_base_url_resolved(self) -> str:
        # Agent workspace 內的工具腳本需要一個可直連本機 API 的穩定 base URL。
        if self.openclaw_agent_tool_api_base_url.strip():
            return self.openclaw_agent_tool_api_base_url.strip().rstrip("/")

        host = "127.0.0.1" if self.api_host in {"0.0.0.0", "::", ""} else self.api_host
        return f"http://{host}:{self.api_port}/api/v1"


@lru_cache
def get_settings() -> Settings:
    # 用快取避免每次依賴注入都重新解析環境變數。
    return Settings()
