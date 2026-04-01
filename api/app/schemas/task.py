from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.schemas.common import RoleStatusEvent


class SummaryTaskRequest(BaseModel):
    # 摘要任務先只允許單一 document_id，為 Phase 2 多文件分析保留擴充空間。
    document_id: str


class SummaryTaskResult(BaseModel):
    summary: str
    highlights: list[str] = Field(default_factory=list)
    todos: list[str] = Field(default_factory=list)
    source_quotes: list[str] = Field(default_factory=list)
    markdown: str


class TaskStatusResponse(BaseModel):
    id: str
    task_type: str
    status: str
    input_payload: dict[str, Any]
    result_payload: Optional[SummaryTaskResult] = None
    error_message: Optional[str] = None
    events: list[RoleStatusEvent] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
