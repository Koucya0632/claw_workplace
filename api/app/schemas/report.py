from __future__ import annotations

from pydantic import BaseModel


class MarkdownReportRequest(BaseModel):
    # 報告輸入先接受 task_id，之後若要支援自訂章節可再補更多欄位。
    task_id: str


class MarkdownReportResponse(BaseModel):
    filename: str
    markdown: str
