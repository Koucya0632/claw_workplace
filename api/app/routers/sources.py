from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.repositories.source_repository import SourceRepository
from app.schemas.source import (
    ScanSourceResponse,
    SourceCreateRequest,
    SourceDetailResponse,
    SourceMetricsResponse,
    SourceResponse,
    SourceSummaryResponse,
    SourceSyncEventResponse,
    SourceUpdateRequest,
)
from app.services.connector_registry import ConnectorRegistry
from app.services.indexing_service import IndexingService


router = APIRouter(tags=["sources"])

source_repository = SourceRepository()
indexing_service = IndexingService()
connector_registry = ConnectorRegistry()


@router.post("/sources", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
def create_source(payload: SourceCreateRequest) -> SourceResponse:
    # Source 建立前先走 connector config 驗證，避免把明顯無效的 source 寫進資料庫。
    try:
        connector_registry.get(payload.type).validate_config(payload.config)
        return source_repository.create(payload)
    except Exception as error:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/sources/local", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
def create_local_source(payload: SourceCreateRequest) -> SourceResponse:
    # 舊入口保留給既有前端，內部仍轉到通用 source 建立流程。
    if payload.type != "local":
        raise HTTPException(status_code=400, detail="請改用 /api/v1/sources 建立非 local 資料源。")
    return create_source(payload)


@router.get("/sources/summary", response_model=SourceMetricsResponse)
def get_sources_summary() -> SourceMetricsResponse:
    return source_repository.get_metrics()


@router.get("/sources", response_model=list[SourceSummaryResponse])
def list_sources(
    q: Optional[str] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    type_filter: Optional[str] = Query(default=None, alias="type"),
    sort: str = Query(default="updated_at"),
    order: str = Query(default="desc"),
) -> list[SourceSummaryResponse]:
    # 列出所有資料源，讓設定頁、搜索頁與知識接入頁都能共用。
    return source_repository.list_all(
        q=q,
        status=status_filter,
        type=type_filter,
        sort=sort,  # type: ignore[arg-type]
        order=order,  # type: ignore[arg-type]
    )


@router.get("/sources/{source_id}", response_model=SourceDetailResponse)
def get_source(source_id: str) -> SourceDetailResponse:
    try:
        return source_repository.get_detail(source_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/sources/{source_id}/activity", response_model=list[SourceSyncEventResponse])
def get_source_activity(source_id: str) -> list[SourceSyncEventResponse]:
    try:
        source_repository.get(source_id)
        return source_repository.list_activity(source_id, limit=10)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.patch("/sources/{source_id}", response_model=SourceResponse)
def update_source(source_id: str, payload: SourceUpdateRequest) -> SourceResponse:
    try:
        current = source_repository.get(source_id)
        if payload.config is not None:
            connector_registry.get(current.type).validate_config(payload.config)
        return source_repository.update(source_id, payload)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/sources/{source_id}/enable", response_model=SourceResponse)
def enable_source(source_id: str) -> SourceResponse:
    try:
        return source_repository.set_enabled(source_id, True)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/sources/{source_id}/disable", response_model=SourceResponse)
def disable_source(source_id: str) -> SourceResponse:
    try:
        return source_repository.set_enabled(source_id, False)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(source_id: str) -> None:
    try:
        source_repository.delete(source_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/sources/{source_id}/scan", response_model=ScanSourceResponse)
def scan_source(source_id: str) -> ScanSourceResponse:
    # 掃描流程若遇到空資料夾或權限問題，這裡都會明確轉成 400。
    try:
        return indexing_service.scan_source(source_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(error)) from error
