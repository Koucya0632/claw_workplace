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
    source_url: Optional[str] = None
    canonical_url: Optional[str] = None
    published_at: Optional[datetime] = None
    business_type: Optional[str] = None
    topic_tags: list[str] = Field(default_factory=list)
    credibility_tier: Optional[str] = None


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
    source_url: Optional[str] = None
    canonical_url: Optional[str] = None
    published_at: Optional[datetime] = None
    language: Optional[str] = None
    status: Optional[str] = None
    business_type: Optional[str] = None
    topic_tags: list[str] = Field(default_factory=list)
    credibility_tier: Optional[str] = None
    metadata: dict[str, object] = Field(default_factory=dict)


class DocumentVersionSummary(BaseModel):
    id: str
    filename: str
    source_url: Optional[str] = None
    canonical_url: Optional[str] = None
    checksum: str
    version_group_id: Optional[str] = None
    version_number: int = 1
    supersedes_document_id: Optional[str] = None
    status: Optional[str] = None
    indexed_at: datetime
    published_at: Optional[datetime] = None
