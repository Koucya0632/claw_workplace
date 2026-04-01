from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseLLMProvider(ABC):
    # BaseLLMProvider 定義摘要服務需要的最小能力集合。
    provider_name: str

    @abstractmethod
    def health_check(self) -> dict[str, Any]:
        # health_check 讓健康檢查頁可以回報 provider 是否已配置。
        raise NotImplementedError

    @abstractmethod
    async def summarize_document(self, document_title: str, document_text: str) -> dict[str, Any]:
        # 摘要方法回傳結構化字典，讓 SummaryService 不綁定單一供應商格式。
        raise NotImplementedError

