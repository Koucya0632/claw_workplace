from fastapi import APIRouter, HTTPException

from app.schemas.report import MarkdownReportRequest, MarkdownReportResponse
from app.services.report_service import ReportService


router = APIRouter(tags=["reports"])

report_service = ReportService()


@router.post("/reports/markdown", response_model=MarkdownReportResponse)
def export_markdown_report(payload: MarkdownReportRequest) -> MarkdownReportResponse:
    # 報告匯出只做 Markdown，若任務未完成會回傳清楚錯誤。
    try:
        return report_service.build_markdown_report(payload.task_id)
    except Exception as error:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(error)) from error
