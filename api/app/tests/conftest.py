from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings


@pytest.fixture
def app_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    # 每個測試都使用獨立的資料庫與來源根目錄，避免互相污染。
    source_root = tmp_path / "sources"
    source_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("OPENCLAW_DATABASE_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("OPENCLAW_LOCAL_SOURCE_BASE_PATH", str(source_root))
    monkeypatch.setenv("OPENCLAW_SECRET_KEY", "test-openclaw-secret")
    monkeypatch.setenv("OPENCLAW_LLM_PROVIDER", "minimax")
    monkeypatch.setenv("MINIMAX_API_KEY", "")
    monkeypatch.setenv("MINIMAX_API_URL", "")

    get_settings.cache_clear()

    yield {"source_root": source_root}

    get_settings.cache_clear()


@pytest.fixture
def client(app_env: dict[str, Path]) -> TestClient:
    # 在環境變數就緒後再建立 app，確保 FastAPI 啟動時會讀到正確設定。
    from app.main import create_app

    return TestClient(create_app())
