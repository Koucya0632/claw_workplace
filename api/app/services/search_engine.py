from __future__ import annotations

from abc import ABC, abstractmethod


class BaseSearchEngine(ABC):
    # BaseSearchEngine 為未來語意搜索預留抽象，Phase 1 不實作具體引擎。
    @abstractmethod
    def is_ready(self) -> bool:
        raise NotImplementedError


class SemanticSearchPlaceholder(BaseSearchEngine):
    # Phase 1 明確回傳未就緒，前端就能顯示「即將支援」而不是假裝可用。
    def is_ready(self) -> bool:
        return False

