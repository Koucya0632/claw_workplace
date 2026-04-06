from fastapi import APIRouter, HTTPException, Query, status
from typing import Optional

from app.schemas.knowledge import KnowledgeIngestRequest, KnowledgeIngestionRunResponse
from app.schemas.search import DocumentVersionSummary
from app.services.knowledge_ingestion_service import KnowledgeIngestionService


router = APIRouter(tags=["knowledge"])

knowledge_ingestion_service = KnowledgeIngestionService()


@router.post("/knowledge/ingest", response_model=KnowledgeIngestionRunResponse, status_code=status.HTTP_201_CREATED)
def ingest_knowledge(payload: KnowledgeIngestRequest) -> KnowledgeIngestionRunResponse:
    # 讓 support-agent 或後台任務可直接啟動一次外部知識接入流程。
    try:
        return knowledge_ingestion_service.ingest(payload)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/knowledge/ingestion-runs", response_model=list[KnowledgeIngestionRunResponse])
def list_ingestion_runs(
    source_id: Optional[str] = None,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[KnowledgeIngestionRunResponse]:
    return knowledge_ingestion_service.list_runs(source_id=source_id, limit=limit)


@router.get("/knowledge/documents/{document_id}/versions", response_model=list[DocumentVersionSummary])
def list_document_versions(document_id: str) -> list[DocumentVersionSummary]:
    try:
        return knowledge_ingestion_service.list_document_versions(document_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
