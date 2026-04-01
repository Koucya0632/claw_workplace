from __future__ import annotations

from app.repositories.document_repository import DocumentRepository
from app.repositories.query_log_repository import QueryLogRepository
from app.schemas.search import SearchRequest, SearchResponse
from app.services.search_engine import SemanticSearchPlaceholder


class SearchService:
    # SearchService 封裝搜索與查詢日誌，router 只需專注處理輸入輸出。
    def __init__(self) -> None:
        self.document_repository = DocumentRepository()
        self.query_log_repository = QueryLogRepository()
        self.semantic_search = SemanticSearchPlaceholder()

    def search(self, payload: SearchRequest) -> SearchResponse:
        log_id = self.query_log_repository.start(payload.query, payload.source_id)

        try:
            response = self.document_repository.search(payload)
            response.semantic_search_ready = self.semantic_search.is_ready()
            self.query_log_repository.finish(log_id, response.total, "completed")
            return response
        except Exception as error:  # noqa: BLE001
            self.query_log_repository.finish(log_id, 0, "failed", str(error))
            raise

