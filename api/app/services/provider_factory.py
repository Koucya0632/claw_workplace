from __future__ import annotations

from app.config import get_settings
from app.providers.base import BaseLLMProvider
from app.providers.minimax import MiniMaxProvider


def build_provider() -> BaseLLMProvider:
    # Provider 工廠保留抽象，後續新增其他供應商時只需擴充這裡。
    settings = get_settings()
    if settings.llm_provider == "minimax":
        return MiniMaxProvider()
    raise ValueError(f"不支援的 LLM provider：{settings.llm_provider}")

