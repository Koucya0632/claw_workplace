from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


BusinessType = Literal["support", "product", "engineering", "compliance", "operations", "market", "finance", "security"]
KnowledgeSourceType = Literal["web_page", "url_list", "rss_feed"]


class KnowledgeIngestRequest(BaseModel):
    topic: str
    query: str = ""
    source_id: Optional[str] = None
    source_name: Optional[str] = None
    source_type: KnowledgeSourceType = "web_page"
    urls: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    must_include: list[str] = Field(default_factory=list)
    must_exclude: list[str] = Field(default_factory=list)
    business_type: Optional[BusinessType] = None
    time_window_days: Optional[int] = None
    limit: int = Field(default=5, ge=1, le=20)
    auto_publish: bool = True


class KnowledgeCandidate(BaseModel):
    title: str
    url: str
    snippet: str = ""
    source_name: str = ""
    source_domain: str = ""
    published_at: Optional[datetime] = None
    reason: str = ""


class KnowledgeIngestionItemResponse(BaseModel):
    id: str
    candidate_url: str
    normalized_url: Optional[str] = None
    title: str = ""
    status: str
    reject_reason: Optional[str] = None
    document_id: Optional[str] = None
    trust_score: Optional[float] = None
    relevance_score: Optional[float] = None
    duplicate_score: Optional[float] = None
    source_domain: str = ""
    created_at: datetime
    metadata: dict[str, object] = Field(default_factory=dict)


class KnowledgeIngestionRunResponse(BaseModel):
    id: str
    source_id: str
    source_name: str
    topic: str
    query: str = ""
    status: str
    total_candidates: int = 0
    accepted_count: int = 0
    updated_count: int = 0
    rejected_count: int = 0
    created_at: datetime
    completed_at: Optional[datetime] = None
    items: list[KnowledgeIngestionItemResponse] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)

