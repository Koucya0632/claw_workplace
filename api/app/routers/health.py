from fastapi import APIRouter

from app.config import get_settings
from app.services.provider_factory import build_provider


router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict:
    # 健康檢查同時回報資料庫路徑與 provider 狀態，方便前端設定頁快速診斷。
    settings = get_settings()
    provider = build_provider()
    return {
        "message": "ok",
        "database_path": str(settings.database_file),
        "provider": provider.health_check(),
    }

