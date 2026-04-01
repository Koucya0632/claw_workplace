from fastapi import APIRouter, HTTPException

from app.repositories.document_repository import DocumentRepository
from app.schemas.search import DocumentSummary


router = APIRouter(tags=["documents"])

document_repository = DocumentRepository()


@router.get("/documents/{document_id}", response_model=DocumentSummary)
def get_document(document_id: str) -> DocumentSummary:
    # 文件詳情給搜索預覽與摘要頁共用。
    try:
        return document_repository.get_document(document_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

