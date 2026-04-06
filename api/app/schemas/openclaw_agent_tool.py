from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class OpenClawAgentToolSearchRequest(BaseModel):
    instance_id: Optional[str] = None
    agent_id: str
    session_id: str
    query: str
    source_id: Optional[str] = None
    limit: Optional[int] = None


class OpenClawAgentToolSearchItem(BaseModel):
    document_id: str
    source_id: str
    source_name: str
    filename: str
    relative_path: str
    snippet: str
    matched_on: str
    modified_at: datetime


class OpenClawAgentToolSearchResponse(BaseModel):
    query: str
    total: int
    query_time_ms: int
    items: list[OpenClawAgentToolSearchItem] = Field(default_factory=list)


class OpenClawAgentToolDocumentRequest(BaseModel):
    instance_id: Optional[str] = None
    agent_id: str
    session_id: str
    document_id: str
    max_chars: Optional[int] = None


class OpenClawAgentToolDocumentPayload(BaseModel):
    id: str
    source_id: str
    filename: str
    relative_path: str
    extension: str
    modified_at: datetime
    extracted_text: str


class OpenClawAgentToolDocumentResponse(BaseModel):
    document: OpenClawAgentToolDocumentPayload
    truncated: bool
    returned_chars: int
