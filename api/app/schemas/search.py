from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    # query 是 Phase 1 的唯一必要條件，其他篩選都屬於附加約束。
    query: str
    source_id: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    mode: str = "all"


class SearchResultItem(BaseModel):
    document_id: str
    source_id: str
    source_name: str
    filename: str
    relative_path: str
    snippet: str
    matched_on: str
    modified_at: datetime


class SearchResponse(BaseModel):
    items: list[SearchResultItem] = Field(default_factory=list)
    total: int = 0
    query_time_ms: int = 0
    semantic_search_ready: bool = False


class DocumentSummary(BaseModel):
    id: str
    source_id: str
    filename: str
    relative_path: str
    extension: str
    modified_at: datetime
    content_preview: str
    extracted_text: str
