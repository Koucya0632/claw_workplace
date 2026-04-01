from __future__ import annotations

from typing import Any

from app.providers.base import BaseLLMProvider


class MockLLMProvider(BaseLLMProvider):
    # Mock provider 只供測試用，讓摘要流程不依賴外部 API。
    provider_name = "mock"

    def health_check(self) -> dict[str, Any]:
        return {"provider": self.provider_name, "ready": True}

    async def summarize_document(self, document_title: str, document_text: str) -> dict[str, Any]:
        trimmed = document_text[:120]
        return {
            "summary": f"{document_title} 的重點摘要：{trimmed}",
            "highlights": ["文件已成功進入 mock 摘要流程。", "可用於驗證任務與報告格式。"],
            "todos": ["檢查真實 MiniMax 設定。"],
            "source_quotes": [trimmed],
        }

