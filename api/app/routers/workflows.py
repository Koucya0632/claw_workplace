from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.workflow import WorkflowRunResponse, WorkflowSearchReportCreateRequest
from app.services.openclaw_errors import OpenClawServiceError
from app.services.workflow_service import SearchReportWorkflowService


router = APIRouter(tags=["workflows"])

workflow_service = SearchReportWorkflowService()


@router.post("/workflows/search-report", response_model=WorkflowRunResponse, status_code=status.HTTP_201_CREATED)
def create_search_report_workflow(payload: WorkflowSearchReportCreateRequest) -> WorkflowRunResponse:
    # workflow 建立只負責回傳 run 骨架，實際執行在背景 thread 內進行。
    try:
        run, _ = workflow_service.create_run(payload)
        return run
    except OpenClawServiceError as error:
        raise HTTPException(status_code=error.status_code or 400, detail=error.detail or error.message) from error
    except Exception as error:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/workflows/{run_id}", response_model=WorkflowRunResponse)
def get_workflow_run(run_id: str) -> WorkflowRunResponse:
    try:
        run, _ = workflow_service.get_run(run_id)
        return run
    except OpenClawServiceError as error:
        raise HTTPException(status_code=error.status_code or 404, detail=error.detail or error.message) from error
    except Exception as error:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/workflows", response_model=list[WorkflowRunResponse])
def list_workflow_runs(
    instance_id: Optional[str] = Query(None, alias="instanceId"),
    limit: int = Query(20, ge=1, le=100),
) -> list[WorkflowRunResponse]:
    try:
        runs, _ = workflow_service.list_runs(instance_id=instance_id, limit=limit)
        return runs
    except OpenClawServiceError as error:
        raise HTTPException(status_code=error.status_code or 400, detail=error.detail or error.message) from error
    except Exception as error:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(error)) from error
