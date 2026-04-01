from __future__ import annotations

from app.repositories.document_repository import DocumentRepository
from app.repositories.task_repository import TaskRepository
from app.schemas.task import TaskStatusResponse
from app.services.provider_factory import build_provider
from app.services.summary_service import SummaryService


class TaskOrchestrator:
    # TaskOrchestrator 負責把角色事件與摘要服務串成一條完整工作流。
    def __init__(self) -> None:
        self.task_repository = TaskRepository()
        self.document_repository = DocumentRepository()
        self.summary_service = SummaryService(build_provider())

    async def run_summary_task(self, document_id: str) -> TaskStatusResponse:
        task = self.task_repository.create_task("summary", {"document_id": document_id})

        # Chief 先接收需求，讓前端左側角色欄有第一個狀態可顯示。
        self.task_repository.add_event(task.id, "Chief Lobster", "running", "收到摘要任務，開始規劃工作流。")
        self.task_repository.update_status(task.id, "running")

        try:
            document = self.document_repository.get_document(document_id)
            self.task_repository.add_event(task.id, "Search Lobster", "completed", "已定位文件與相關內容。")
            self.task_repository.add_event(task.id, "Organize Lobster", "running", "開始整理重點、待辦與引用片段。")

            result = await self.summary_service.summarize_document(document)

            self.task_repository.add_event(task.id, "Organize Lobster", "completed", "文件摘要整理完成。")
            self.task_repository.add_event(task.id, "Chief Lobster", "completed", "摘要任務完成，已整合最終輸出。")
            self.task_repository.update_status(task.id, "completed", result.model_dump())
        except Exception as error:  # noqa: BLE001
            # 任務失敗時保留清楚錯誤訊息，方便前端給使用者重試入口。
            self.task_repository.add_event(task.id, "Chief Lobster", "failed", "摘要任務失敗。", {"error": str(error)})
            self.task_repository.update_status(task.id, "failed", error_message=str(error))

        return self.task_repository.get_task(task.id)

