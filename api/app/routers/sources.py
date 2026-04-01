from fastapi import APIRouter, HTTPException, status

from app.repositories.source_repository import SourceRepository
from app.schemas.source import ScanSourceResponse, SourceCreateRequest, SourceResponse
from app.services.connector_registry import ConnectorRegistry
from app.services.indexing_service import IndexingService


router = APIRouter(tags=["sources"])

source_repository = SourceRepository()
indexing_service = IndexingService()
connector_registry = ConnectorRegistry()


@router.post("/sources/local", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
def create_local_source(payload: SourceCreateRequest) -> SourceResponse:
    # Phase 1 只允許 local 真接入，因此這裡直接擋掉其他型別。
    if payload.type != "local":
        raise HTTPException(status_code=400, detail="Phase 1 只支援建立 local 資料源。")

    try:
        connector_registry.get(payload.type).validate_config(payload.config)
        return source_repository.create(payload)
    except Exception as error:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/sources", response_model=list[SourceResponse])
def list_sources() -> list[SourceResponse]:
    # 列出所有資料源，讓設定頁與搜索頁都能共用。
    return source_repository.list_all()


@router.post("/sources/{source_id}/scan", response_model=ScanSourceResponse)
def scan_source(source_id: str) -> ScanSourceResponse:
    # 掃描流程若遇到空資料夾或權限問題，這裡都會明確轉成 400。
    try:
        return indexing_service.scan_source(source_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(error)) from error
