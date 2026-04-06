from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.connectors.base import BaseConnector
from app.parsers.file_parser import FileParser
from app.repositories.document_repository import DocumentRepository, make_chunk_records, make_document_record
from app.repositories.source_repository import SourceRepository
from app.schemas.source import ScanSourceResponse
from app.services.connector_registry import ConnectorRegistry
from app.services.knowledge_ingestion_service import KnowledgeIngestionService
from app.utils import checksum_for_bytes


class IndexingService:
    # IndexingService 負責把來源掃描結果轉成可搜索的結構化索引。
    def __init__(self) -> None:
        self.source_repository = SourceRepository()
        self.document_repository = DocumentRepository()
        self.connector_registry = ConnectorRegistry()
        self.parser = FileParser()
        self.knowledge_ingestion_service = KnowledgeIngestionService()

    def scan_source(self, source_id: str) -> ScanSourceResponse:
        source = self.source_repository.get(source_id)
        if not source.is_enabled:
            raise ValueError("資料源已停用，請先啟用後再同步。")

        if source.type in {"web_page", "url_list", "rss_feed"}:
            return self._scan_external_source(source_id)

        connector = self.connector_registry.get(source.type)

        # 先把資料源狀態標記成 scanning，前端就能立即反映流程進度。
        self.source_repository.mark_sync_started(source_id, message="開始掃描本地資料源。")

        discovered_files = connector.scan_documents(source.config)
        errors: list[str] = []
        indexed_records: list[dict] = []
        skipped_count = 0

        if not discovered_files:
            self.source_repository.mark_sync_finished(
                source_id,
                status="failed",
                scanned_count=0,
                skipped_count=0,
                error_count=1,
                message="掃描失敗：資料夾內沒有可索引的支援文件。",
                error_message="資料夾內沒有可索引的支援文件。",
            )
            raise ValueError("資料夾內沒有可索引的支援文件。")

        try:
            for file_path in discovered_files:
                try:
                    indexed_records.append(self._build_index_record(source_id, source.config.path or "", connector, file_path))
                except Exception as error:  # noqa: BLE001
                    # 單檔案解析失敗不應阻擋整批索引，因此這裡收斂成 errors 清單。
                    errors.append(f"{file_path.name}: {error}")
                    skipped_count += 1

            self.document_repository.replace_for_source(source_id, indexed_records)
        except Exception as error:  # noqa: BLE001
            self.source_repository.mark_sync_finished(
                source_id,
                status="failed",
                scanned_count=0,
                skipped_count=skipped_count,
                error_count=max(len(errors), 1),
                message=f"掃描失敗：{error}",
                error_message=str(error),
            )
            raise

        sync_status = "warning" if errors else "healthy"
        self.source_repository.mark_sync_finished(
            source_id,
            status=sync_status,
            scanned_count=len(indexed_records),
            skipped_count=skipped_count,
            error_count=len(errors),
            message=f"掃描完成：成功 {len(indexed_records)}，略過 {skipped_count}，錯誤 {len(errors)}。",
            error_message="；".join(errors) if errors else None,
        )
        return ScanSourceResponse(
            source_id=source_id,
            scanned_count=len(indexed_records),
            skipped_count=skipped_count,
            errors=errors,
            scanned_at=self.source_repository.get(source_id).last_scan_at or self.source_repository.get(source_id).updated_at,
        )

    def _scan_external_source(self, source_id: str) -> ScanSourceResponse:
        self.source_repository.mark_sync_started(source_id, message="開始同步外部資料源。")
        try:
            run = self.knowledge_ingestion_service.refresh_external_source(source_id)
            errors = [item.reject_reason for item in run.items if item.reject_reason]
            sync_status = "warning" if errors else "healthy"
            self.source_repository.mark_sync_finished(
                source_id,
                status=sync_status,
                scanned_count=run.accepted_count + run.updated_count,
                skipped_count=run.rejected_count,
                error_count=len(errors),
                message=(
                    f"外部資料同步完成：新增/更新 {run.accepted_count + run.updated_count}，"
                    f"略過 {run.rejected_count}，錯誤 {len(errors)}。"
                ),
                error_message="；".join(errors) if errors else None,
            )
            refreshed_source = self.source_repository.get(source_id)
            return ScanSourceResponse(
                source_id=source_id,
                scanned_count=run.accepted_count + run.updated_count,
                skipped_count=run.rejected_count,
                errors=errors,
                scanned_at=refreshed_source.last_scan_at or refreshed_source.updated_at,
            )
        except Exception as error:  # noqa: BLE001
            self.source_repository.mark_sync_finished(
                source_id,
                status="failed",
                scanned_count=0,
                skipped_count=0,
                error_count=1,
                message=f"外部資料同步失敗：{error}",
                error_message=str(error),
            )
            raise

    def _build_index_record(
        self,
        source_id: str,
        base_path: str,
        connector: BaseConnector,
        file_path: Path,
    ) -> dict:
        # 讀取 bytes 後先算 checksum，後續若要做增量索引可以直接沿用。
        payload = connector.fetch_content(file_path)
        checksum = checksum_for_bytes(payload)
        parsed = self.parser.parse(file_path, payload)
        relative_path = str(file_path.resolve().relative_to(Path(base_path).expanduser().resolve()))
        chunks = make_chunk_records(parsed.text)

        return make_document_record(
            source_id=source_id,
            relative_path=relative_path,
            filename=file_path.name,
            extension=parsed.extension,
            mime_type=parsed.mime_type,
            file_size=file_path.stat().st_size,
            checksum=checksum,
            modified_at=_timestamp_from_path(file_path),
            content_preview=parsed.preview,
            extracted_text=parsed.text,
            chunks=chunks,
        )


def _timestamp_from_path(file_path: Path) -> str:
    # 將檔案系統 mtime 統一轉成 ISO 字串後再落庫。
    return datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc).isoformat()
