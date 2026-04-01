from __future__ import annotations

from app.config import get_settings
from app.providers.base import BaseLLMProvider
from app.schemas.search import DocumentSummary
from app.schemas.task import SummaryTaskResult


class SummaryService:
    # SummaryService 負責整理摘要 prompt 與最終結果格式，不直接處理任務狀態。
    def __init__(self, provider: BaseLLMProvider) -> None:
        self.provider = provider

    async def summarize_document(self, document: DocumentSummary) -> SummaryTaskResult:
        settings = get_settings()

        # 摘要前先截斷內容，避免大文件導致模型成本與延遲失控。
        trimmed_text = document.extracted_text[: settings.summary_max_chars]
        provider_result = await self.provider.summarize_document(document.filename, trimmed_text)
        markdown = self._build_markdown(document.filename, provider_result)

        return SummaryTaskResult(
            summary=provider_result.get("summary", ""),
            highlights=provider_result.get("highlights", []),
            todos=provider_result.get("todos", []),
            source_quotes=provider_result.get("source_quotes", []),
            markdown=markdown,
        )

    def _build_markdown(self, title: str, result: dict) -> str:
        # Markdown 會同時被報告頁與匯出功能共用，因此在這裡統一生成。
        highlight_lines = "\n".join(f"- {item}" for item in result.get("highlights", []))
        todo_lines = "\n".join(f"- {item}" for item in result.get("todos", []))
        quote_lines = "\n".join(f"> {item}" for item in result.get("source_quotes", []))

        return (
            f"# {title} 摘要報告\n\n"
            f"## 摘要\n\n{result.get('summary', '')}\n\n"
            f"## 重點\n\n{highlight_lines or '- 無'}\n\n"
            f"## 待辦\n\n{todo_lines or '- 無'}\n\n"
            f"## 引用片段\n\n{quote_lines or '> 無'}\n"
        )

