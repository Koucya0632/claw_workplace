from __future__ import annotations

from app.repositories.task_repository import TaskRepository
from app.schemas.report import MarkdownReportResponse


class ReportService:
    # ReportService 先專注於 Markdown 輸出，PDF 與其他格式留到後續版本。
    def __init__(self) -> None:
        self.task_repository = TaskRepository()

    def build_markdown_report(self, task_id: str) -> MarkdownReportResponse:
        task = self.task_repository.get_task(task_id)

        # 只有完成的摘要任務才允許輸出，避免拿到半成品或錯誤內容。
        if task.status != "completed" or task.result_payload is None:
            raise ValueError("任務尚未完成，無法匯出報告。")

        return MarkdownReportResponse(
            filename=f"openclaw-summary-{task.id}.md",
            markdown=task.result_payload.markdown,
        )

