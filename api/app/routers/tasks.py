from fastapi import APIRouter, HTTPException, status

from app.repositories.task_repository import TaskRepository
from app.schemas.task import SummaryTaskRequest, TaskStatusResponse
from app.services.task_orchestrator import TaskOrchestrator


router = APIRouter(tags=["tasks"])

task_repository = TaskRepository()
task_orchestrator = TaskOrchestrator()


@router.post("/tasks/summary", response_model=TaskStatusResponse, status_code=status.HTTP_201_CREATED)
async def create_summary_task(payload: SummaryTaskRequest) -> TaskStatusResponse:
    # 摘要任務同步執行，但仍保留 task/event 結構方便前端輪詢與追蹤。
    try:
        return await task_orchestrator.run_summary_task(payload.document_id)
    except Exception as error:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
def get_task(task_id: str) -> TaskStatusResponse:
    # 任務詳情 API 讓分析頁與報告頁都能回讀最新狀態。
    try:
        return task_repository.get_task(task_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

