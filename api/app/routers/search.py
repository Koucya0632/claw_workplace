from fastapi import APIRouter, HTTPException

from app.schemas.search import SearchRequest, SearchResponse
from app.services.search_service import SearchService


router = APIRouter(tags=["search"])

search_service = SearchService()


@router.post("/search", response_model=SearchResponse)
def search_documents(payload: SearchRequest) -> SearchResponse:
    # 搜索 API 直接轉交 service，若出錯則回傳清楚 detail 給前端。
    try:
        return search_service.search(payload)
    except Exception as error:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(error)) from error

