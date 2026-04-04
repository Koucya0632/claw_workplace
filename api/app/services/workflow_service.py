from __future__ import annotations

import json
import re
import threading
import time
from typing import Any, Optional

from app.repositories.openclaw_instance_repository import OpenClawInstanceRepository
from app.repositories.openclaw_operation_log_repository import OpenClawOperationLogRepository
from app.repositories.openclaw_workflow_config_repository import OpenClawWorkflowConfigRepository
from app.repositories.workflow_repository import WorkflowRepository
from app.schemas.openclaw_workflow_config import OpenClawWorkflowConfigResponse, OpenClawWorkflowConfigUpdateRequest
from app.schemas.workflow import (
    WORKFLOW_TYPE_SEARCH_REPORT,
    WORKFLOW_TYPE_WEB_SEARCH,
    WorkflowAnalysisStageOutput,
    WorkflowReportPayload,
    WorkflowRunResponse,
    WorkflowSearchReportCreateRequest,
    WorkflowSearchStageOutput,
    WorkflowWebSearchCreateRequest,
    WorkflowWebSearchFilterOutput,
    WorkflowWebSearchResult,
    WorkflowWebSearchSearchOutput,
    WorkflowWebSearchSourceItem,
    WorkflowWebSearchUnderstandOutput,
)
from app.services.openclaw_cli_adapter import OpenClawCliAdapter
from app.services.openclaw_errors import OpenClawServiceError
from app.services.openclaw_hook_client import OpenClawHookClient
from app.services.openclaw_secret_cipher import OpenClawSecretCipher
from app.utils import truncate_text, utc_now_iso


SEARCH_STAGE_KEY = "search"
ANALYSIS_STAGE_KEY = "analysis"
REPORT_STAGE_KEY = "report"
UNDERSTAND_STAGE_KEY = "understand"
FILTER_STAGE_KEY = "filter"
FORMAT_STAGE_KEY = "format"

SEARCH_REPORT_STAGE_SEQUENCE = (SEARCH_STAGE_KEY, ANALYSIS_STAGE_KEY, REPORT_STAGE_KEY)
WEB_SEARCH_STAGE_SEQUENCE = (UNDERSTAND_STAGE_KEY, SEARCH_STAGE_KEY, FILTER_STAGE_KEY, FORMAT_STAGE_KEY)

SEARCH_REPORT_RUN_PROGRESS_START = {
    SEARCH_STAGE_KEY: 5,
    ANALYSIS_STAGE_KEY: 40,
    REPORT_STAGE_KEY: 75,
}
SEARCH_REPORT_RUN_PROGRESS_DONE = {
    SEARCH_STAGE_KEY: 34,
    ANALYSIS_STAGE_KEY: 67,
    REPORT_STAGE_KEY: 100,
}
SEARCH_REPORT_STAGE_RUNNING_PROGRESS = {
    SEARCH_STAGE_KEY: 15,
    ANALYSIS_STAGE_KEY: 50,
    REPORT_STAGE_KEY: 85,
}

WEB_SEARCH_RUN_PROGRESS_START = {
    UNDERSTAND_STAGE_KEY: 5,
    SEARCH_STAGE_KEY: 25,
    FILTER_STAGE_KEY: 55,
    FORMAT_STAGE_KEY: 82,
}
WEB_SEARCH_RUN_PROGRESS_DONE = {
    UNDERSTAND_STAGE_KEY: 20,
    SEARCH_STAGE_KEY: 50,
    FILTER_STAGE_KEY: 78,
    FORMAT_STAGE_KEY: 100,
}
WEB_SEARCH_STAGE_RUNNING_PROGRESS = {
    UNDERSTAND_STAGE_KEY: 25,
    SEARCH_STAGE_KEY: 45,
    FILTER_STAGE_KEY: 72,
    FORMAT_STAGE_KEY: 92,
}


class OpenClawWorkflowConfigService:
    # workflow config service 負責驗證三個 stage 的 agent mapping，避免 workflow 執行時才發現 agent 不存在。
    source_mode = "repository"

    def __init__(
        self,
        repository: Optional[OpenClawInstanceRepository] = None,
        workflow_config_repository: Optional[OpenClawWorkflowConfigRepository] = None,
        operation_log_repository: Optional[OpenClawOperationLogRepository] = None,
        cli_adapter: Optional[OpenClawCliAdapter] = None,
        secret_cipher: Optional[OpenClawSecretCipher] = None,
    ) -> None:
        from app.config import get_settings

        settings = get_settings()
        self.repository = repository or OpenClawInstanceRepository()
        self.workflow_config_repository = workflow_config_repository or OpenClawWorkflowConfigRepository()
        self.operation_log_repository = operation_log_repository or OpenClawOperationLogRepository()
        self.cli_adapter = cli_adapter or OpenClawCliAdapter()
        self.secret_cipher = secret_cipher or OpenClawSecretCipher(settings.openclaw_secret_key)

    def get_config(self, instance_id: str) -> tuple[OpenClawWorkflowConfigResponse, int]:
        started_at = time.perf_counter()
        self.repository.get(instance_id)
        try:
            return self.workflow_config_repository.get(instance_id), _elapsed_ms(started_at)
        except KeyError as error:
            raise OpenClawServiceError(
                "尚未設定 workflow agent mapping。",
                detail=str(error),
                status_code=404,
                source_mode=self.source_mode,
            ) from error

    def update_config(self, payload: OpenClawWorkflowConfigUpdateRequest) -> tuple[OpenClawWorkflowConfigResponse, int]:
        started_at = time.perf_counter()
        instance, token = self._load_context(payload.instance_id)
        request_summary = payload.model_dump()

        try:
            agent_ids = {
                str(item.get("id") or item.get("agent_id") or "")
                for item in self.cli_adapter.list_agents(instance, token)
            }
            missing = [
                agent_id
                for agent_id in (payload.search_agent_id, payload.analysis_agent_id, payload.report_agent_id)
                if agent_id not in agent_ids
            ]
            if missing:
                raise OpenClawServiceError(
                    "workflow agent mapping 包含不存在的 agent。",
                    detail=f"missing={','.join(missing)}",
                    status_code=400,
                    source_mode=self.cli_adapter.source_mode,
                )

            config = self.workflow_config_repository.upsert(
                instance_id=payload.instance_id,
                search_agent_id=payload.search_agent_id,
                analysis_agent_id=payload.analysis_agent_id,
                report_agent_id=payload.report_agent_id,
            )
            self.operation_log_repository.create(
                instance_id=payload.instance_id,
                operation_type="configure_workflow_agents",
                target_type="workflow_config",
                target_id=payload.instance_id,
                status="success",
                error_message=None,
                request_summary=request_summary,
                response_summary=config.model_dump(mode="json"),
                source_mode=self.source_mode,
            )
            return config, _elapsed_ms(started_at)
        except OpenClawServiceError as error:
            self.operation_log_repository.create(
                instance_id=payload.instance_id,
                operation_type="configure_workflow_agents",
                target_type="workflow_config",
                target_id=payload.instance_id,
                status="failed",
                error_message=error.detail or error.message,
                request_summary=request_summary,
                response_summary=None,
                source_mode=error.source_mode or self.source_mode,
            )
            raise

    def _load_context(self, instance_id: str):
        instance = self.repository.get(instance_id)
        encrypted_token = self.repository.get_secret(instance_id)
        token = self.secret_cipher.decrypt(encrypted_token) if encrypted_token else None
        return instance, token


class SearchReportWorkflowService:
    # Workflow service 同時支援 search_report 與 web_search，兩者都共用 run/stage/event persistence。
    source_mode = "workflow"

    def __init__(
        self,
        repository: Optional[OpenClawInstanceRepository] = None,
        workflow_repository: Optional[WorkflowRepository] = None,
        workflow_config_repository: Optional[OpenClawWorkflowConfigRepository] = None,
        operation_log_repository: Optional[OpenClawOperationLogRepository] = None,
        hook_client: Optional[OpenClawHookClient] = None,
        cli_adapter: Optional[OpenClawCliAdapter] = None,
        secret_cipher: Optional[OpenClawSecretCipher] = None,
        *,
        run_inline: bool = False,
    ) -> None:
        from app.config import get_settings

        settings = get_settings()
        self.repository = repository or OpenClawInstanceRepository()
        self.workflow_repository = workflow_repository or WorkflowRepository()
        self.workflow_config_repository = workflow_config_repository or OpenClawWorkflowConfigRepository()
        self.operation_log_repository = operation_log_repository or OpenClawOperationLogRepository()
        self.hook_client = hook_client or OpenClawHookClient()
        self.cli_adapter = cli_adapter or OpenClawCliAdapter()
        self.secret_cipher = secret_cipher or OpenClawSecretCipher(settings.openclaw_secret_key)
        self.run_inline = run_inline

    def create_run(self, payload: WorkflowSearchReportCreateRequest) -> tuple[WorkflowRunResponse, int]:
        started_at = time.perf_counter()
        self._ensure_instance_exists(payload.instance_id)
        config = self._get_config_or_error(payload.instance_id)

        run = self.workflow_repository.create_run(
            instance_id=payload.instance_id,
            workflow_type=WORKFLOW_TYPE_SEARCH_REPORT,
            input_payload=payload.model_dump(),
            stage_configs=[
                {"stage_key": SEARCH_STAGE_KEY, "agent_id": config.search_agent_id},
                {"stage_key": ANALYSIS_STAGE_KEY, "agent_id": config.analysis_agent_id},
                {"stage_key": REPORT_STAGE_KEY, "agent_id": config.report_agent_id},
            ],
        )
        self.workflow_repository.add_event(
            run_id=run.id,
            stage_key=None,
            agent_id=None,
            status="pending",
            progress_percent=0,
            message="已建立搜索-分析-報告工作流，等待 agent 啟動。",
            payload={"query": payload.query, "source_id": payload.source_id},
        )
        self._start_run(run.id)
        return self.workflow_repository.get_run(run.id), _elapsed_ms(started_at)

    def create_web_search_run(self, payload: WorkflowWebSearchCreateRequest) -> tuple[WorkflowRunResponse, int]:
        started_at = time.perf_counter()
        self._ensure_instance_exists(payload.instance_id)
        config = self._get_config_or_error(payload.instance_id)

        run = self.workflow_repository.create_run(
            instance_id=payload.instance_id,
            workflow_type=WORKFLOW_TYPE_WEB_SEARCH,
            input_payload=payload.model_dump(),
            stage_configs=[
                {"stage_key": UNDERSTAND_STAGE_KEY, "agent_id": config.search_agent_id},
                {"stage_key": SEARCH_STAGE_KEY, "agent_id": config.search_agent_id},
                {"stage_key": FILTER_STAGE_KEY, "agent_id": config.search_agent_id},
                {"stage_key": FORMAT_STAGE_KEY, "agent_id": config.search_agent_id},
            ],
        )
        self.workflow_repository.add_event(
            run_id=run.id,
            stage_key=None,
            agent_id=None,
            status="pending",
            progress_percent=0,
            message="已建立 Web Search 工作流，等待 search agent 啟動。",
            payload={
                "topic": payload.topic,
                "output_format": payload.output_format,
                "include_project_sources": payload.include_project_sources,
            },
        )
        self._start_run(run.id)
        return self.workflow_repository.get_run(run.id), _elapsed_ms(started_at)

    def continue_to_report(self, run_id: str) -> tuple[WorkflowRunResponse, int]:
        started_at = time.perf_counter()
        web_run = self.workflow_repository.get_run(run_id)
        if web_run.workflow_type != WORKFLOW_TYPE_WEB_SEARCH:
            raise OpenClawServiceError(
                "只有 Web Search run 可以接續分析/報告流程。",
                detail="workflow_type 必須是 web_search。",
                status_code=400,
                source_mode=self.source_mode,
            )
        if web_run.status != "completed" or web_run.final_web_result is None:
            raise OpenClawServiceError(
                "只有已完成的 Web Search run 才能接續分析/報告流程。",
                detail="請先等 Web Search 完成。",
                status_code=400,
                source_mode=self.source_mode,
            )

        config = self._get_config_or_error(web_run.instance_id)
        continued_run = self.workflow_repository.create_run(
            instance_id=web_run.instance_id,
            workflow_type=WORKFLOW_TYPE_SEARCH_REPORT,
            input_payload={
                "instance_id": web_run.instance_id,
                "query": str(web_run.input_payload.get("topic") or ""),
                "source_id": web_run.input_payload.get("source_id"),
                "continued_from_run_id": web_run.id,
                "web_search_result": web_run.final_web_result.model_dump(),
            },
            stage_configs=[
                {"stage_key": SEARCH_STAGE_KEY, "agent_id": config.search_agent_id},
                {"stage_key": ANALYSIS_STAGE_KEY, "agent_id": config.analysis_agent_id},
                {"stage_key": REPORT_STAGE_KEY, "agent_id": config.report_agent_id},
            ],
        )
        self.workflow_repository.add_event(
            run_id=continued_run.id,
            stage_key=None,
            agent_id=None,
            status="pending",
            progress_percent=0,
            message="已建立分析/報告接續流程，將承接 Web Search 的中間成果。",
            payload={"continued_from_run_id": web_run.id},
        )

        search_output = _web_result_to_search_output(web_run.final_web_result)
        now = utc_now_iso()
        self.workflow_repository.update_stage(
            run_id=continued_run.id,
            stage_key=SEARCH_STAGE_KEY,
            status="completed",
            progress_percent=100,
            input_payload={"continued_from_run_id": web_run.id, "topic": web_run.input_payload.get("topic")},
            output_payload=search_output.model_dump(),
            started_at=now,
            completed_at=now,
        )
        self.workflow_repository.update_run_status(
            run_id=continued_run.id,
            status="running",
            current_stage=SEARCH_STAGE_KEY,
            active_agent_id=config.search_agent_id,
            overall_progress_percent=SEARCH_REPORT_RUN_PROGRESS_DONE[SEARCH_STAGE_KEY],
            error_message=None,
        )
        self.workflow_repository.add_event(
            run_id=continued_run.id,
            stage_key=SEARCH_STAGE_KEY,
            agent_id=config.search_agent_id,
            status="completed",
            progress_percent=SEARCH_REPORT_RUN_PROGRESS_DONE[SEARCH_STAGE_KEY],
            message="已承接 Web Search 結果，跳過搜索階段，準備進入分析。",
            payload={"source_count": len(web_run.final_web_result.included_sources)},
        )
        self._start_run(continued_run.id)
        return self.workflow_repository.get_run(continued_run.id), _elapsed_ms(started_at)

    def get_run(self, run_id: str) -> tuple[WorkflowRunResponse, int]:
        started_at = time.perf_counter()
        try:
            return self.workflow_repository.get_run(run_id), _elapsed_ms(started_at)
        except KeyError as error:
            raise OpenClawServiceError(
                "找不到指定的 workflow run。",
                detail=str(error),
                status_code=404,
                source_mode=self.source_mode,
            ) from error

    def list_runs(
        self,
        *,
        instance_id: str | None = None,
        workflow_type: str | None = None,
        limit: int = 20,
    ) -> tuple[list[WorkflowRunResponse], int]:
        started_at = time.perf_counter()
        if instance_id:
            self._ensure_instance_exists(instance_id)
        return (
            self.workflow_repository.list_runs(instance_id=instance_id, workflow_type=workflow_type, limit=limit),
            _elapsed_ms(started_at),
        )

    def _start_run(self, run_id: str) -> None:
        if self.run_inline:
            self._execute_run(run_id)
            return
        thread = threading.Thread(target=self._execute_run, args=(run_id,), daemon=True)
        thread.start()

    def _execute_run(self, run_id: str) -> None:
        run = self.workflow_repository.get_run(run_id)
        try:
            if run.workflow_type == WORKFLOW_TYPE_WEB_SEARCH:
                self._execute_web_search_run(run.id)
            else:
                self._execute_search_report_run(run.id)
        except OpenClawServiceError:
            raise

    def _execute_search_report_run(self, run_id: str) -> None:
        run = self.workflow_repository.get_run(run_id)
        config = self._get_config_or_error(run.instance_id)

        try:
            search_stage = self._get_stage(run, SEARCH_STAGE_KEY)
            if search_stage.status == "completed" and isinstance(search_stage.output_payload, dict):
                search_output = WorkflowSearchStageOutput(**search_stage.output_payload)
            else:
                search_output = self._run_search_stage(run, config.search_agent_id)

            analysis_output = self._run_analysis_stage(self.workflow_repository.get_run(run.id), config.analysis_agent_id, search_output)
            report_output = self._run_report_stage(
                self.workflow_repository.get_run(run.id),
                config.report_agent_id,
                search_output,
                analysis_output,
            )

            self.workflow_repository.update_run_status(
                run_id=run.id,
                status="completed",
                current_stage=REPORT_STAGE_KEY,
                active_agent_id=config.report_agent_id,
                overall_progress_percent=100,
                final_payload=report_output.model_dump(),
                error_message=None,
            )
            self.workflow_repository.add_event(
                run_id=run.id,
                stage_key=REPORT_STAGE_KEY,
                agent_id=config.report_agent_id,
                status="completed",
                progress_percent=100,
                message="完整報告已生成，可回看全鏈路與匯出 Markdown。",
                payload={"title": report_output.title},
            )
        except OpenClawServiceError as error:
            self._mark_run_failed(run.id, error)

    def _execute_web_search_run(self, run_id: str) -> None:
        run = self.workflow_repository.get_run(run_id)
        config = self._get_config_or_error(run.instance_id)
        search_agent_id = config.search_agent_id

        try:
            understand_output = self._run_web_understand_stage(run, search_agent_id)
            search_output = self._run_web_search_stage(self.workflow_repository.get_run(run.id), search_agent_id, understand_output)
            filter_output = self._run_web_filter_stage(self.workflow_repository.get_run(run.id), search_agent_id, understand_output, search_output)
            formatted_output = self._run_web_format_stage(
                self.workflow_repository.get_run(run.id),
                search_agent_id,
                understand_output,
                filter_output,
            )

            self.workflow_repository.update_run_status(
                run_id=run.id,
                status="completed",
                current_stage=FORMAT_STAGE_KEY,
                active_agent_id=search_agent_id,
                overall_progress_percent=100,
                final_payload=formatted_output.model_dump(),
                error_message=None,
            )
            self.workflow_repository.add_event(
                run_id=run.id,
                stage_key=FORMAT_STAGE_KEY,
                agent_id=search_agent_id,
                status="completed",
                progress_percent=100,
                message="Web Search 已完成，可直接回看整理結果，或送入分析/報告流程。",
                payload={"title": formatted_output.title, "source_count": len(formatted_output.included_sources)},
            )
        except OpenClawServiceError as error:
            self._mark_run_failed(run.id, error)

    def _run_search_stage(self, run: WorkflowRunResponse, agent_id: str) -> WorkflowSearchStageOutput:
        input_payload = {
            "query": run.input_payload.get("query"),
            "source_id": run.input_payload.get("source_id"),
        }
        self._mark_stage_running(
            run_id=run.id,
            stage_key=SEARCH_STAGE_KEY,
            agent_id=agent_id,
            input_payload=input_payload,
            run_progress=SEARCH_REPORT_RUN_PROGRESS_START[SEARCH_STAGE_KEY],
            stage_progress=SEARCH_REPORT_STAGE_RUNNING_PROGRESS[SEARCH_STAGE_KEY],
            message="搜索資料中...",
        )
        self.workflow_repository.add_event(
            run_id=run.id,
            stage_key=SEARCH_STAGE_KEY,
            agent_id=agent_id,
            status="running",
            progress_percent=25,
            message="正在整理來源...",
            payload=input_payload,
        )
        try:
            response_payload = self._dispatch_agent(
                instance_id=run.instance_id,
                agent_id=agent_id,
                session_key=f"{run.id}-{SEARCH_STAGE_KEY}",
                message=_build_search_prompt(query=str(run.input_payload.get("query") or ""), source_id=run.input_payload.get("source_id")),
                metadata={"workflow_run_id": run.id, "stage_key": SEARCH_STAGE_KEY, "workflow_type": run.workflow_type},
            )
            search_output = _parse_agent_output(response_payload, WorkflowSearchStageOutput, "搜索階段")
            self.workflow_repository.update_stage(
                run_id=run.id,
                stage_key=SEARCH_STAGE_KEY,
                status="completed",
                progress_percent=100,
                output_payload=search_output.model_dump(),
                completed_at=utc_now_iso(),
            )
            self.workflow_repository.update_run_status(
                run_id=run.id,
                status="running",
                current_stage=SEARCH_STAGE_KEY,
                active_agent_id=agent_id,
                overall_progress_percent=SEARCH_REPORT_RUN_PROGRESS_DONE[SEARCH_STAGE_KEY],
                error_message=None,
            )
            self.workflow_repository.add_event(
                run_id=run.id,
                stage_key=SEARCH_STAGE_KEY,
                agent_id=agent_id,
                status="completed",
                progress_percent=SEARCH_REPORT_RUN_PROGRESS_DONE[SEARCH_STAGE_KEY],
                message="搜索階段完成，已整理候選來源。",
                payload={"candidate_count": len(search_output.candidates), "selected_count": len(search_output.selected_documents)},
            )
            return search_output
        except OpenClawServiceError as error:
            self._mark_stage_failed(run_id=run.id, stage_key=SEARCH_STAGE_KEY, agent_id=agent_id, error=error)
            raise

    def _run_analysis_stage(
        self,
        run: WorkflowRunResponse,
        agent_id: str,
        search_output: WorkflowSearchStageOutput,
    ) -> WorkflowAnalysisStageOutput:
        input_payload = {
            "query": run.input_payload.get("query"),
            "search_output": search_output.model_dump(),
        }
        self._mark_stage_running(
            run_id=run.id,
            stage_key=ANALYSIS_STAGE_KEY,
            agent_id=agent_id,
            input_payload=input_payload,
            run_progress=SEARCH_REPORT_RUN_PROGRESS_START[ANALYSIS_STAGE_KEY],
            stage_progress=SEARCH_REPORT_STAGE_RUNNING_PROGRESS[ANALYSIS_STAGE_KEY],
            message="正在分析重點...",
        )

        try:
            response_payload = self._dispatch_agent(
                instance_id=run.instance_id,
                agent_id=agent_id,
                session_key=f"{run.id}-{ANALYSIS_STAGE_KEY}",
                message=_build_analysis_prompt(query=str(run.input_payload.get("query") or ""), search_output=search_output.model_dump()),
                metadata={"workflow_run_id": run.id, "stage_key": ANALYSIS_STAGE_KEY, "workflow_type": run.workflow_type},
            )
            analysis_output = _parse_agent_output(response_payload, WorkflowAnalysisStageOutput, "分析階段")
            self.workflow_repository.update_stage(
                run_id=run.id,
                stage_key=ANALYSIS_STAGE_KEY,
                status="completed",
                progress_percent=100,
                output_payload=analysis_output.model_dump(),
                completed_at=utc_now_iso(),
            )
            self.workflow_repository.update_run_status(
                run_id=run.id,
                status="running",
                current_stage=ANALYSIS_STAGE_KEY,
                active_agent_id=agent_id,
                overall_progress_percent=SEARCH_REPORT_RUN_PROGRESS_DONE[ANALYSIS_STAGE_KEY],
                error_message=None,
            )
            self.workflow_repository.add_event(
                run_id=run.id,
                stage_key=ANALYSIS_STAGE_KEY,
                agent_id=agent_id,
                status="completed",
                progress_percent=SEARCH_REPORT_RUN_PROGRESS_DONE[ANALYSIS_STAGE_KEY],
                message="分析階段完成，已整理重點、風險與待辦。",
                payload={"highlight_count": len(analysis_output.highlights), "risk_count": len(analysis_output.risks)},
            )
            return analysis_output
        except OpenClawServiceError as error:
            self._mark_stage_failed(run_id=run.id, stage_key=ANALYSIS_STAGE_KEY, agent_id=agent_id, error=error)
            raise

    def _run_report_stage(
        self,
        run: WorkflowRunResponse,
        agent_id: str,
        search_output: WorkflowSearchStageOutput,
        analysis_output: WorkflowAnalysisStageOutput,
    ) -> WorkflowReportPayload:
        input_payload = {
            "query": run.input_payload.get("query"),
            "search_output": search_output.model_dump(),
            "analysis_output": analysis_output.model_dump(),
        }
        self._mark_stage_running(
            run_id=run.id,
            stage_key=REPORT_STAGE_KEY,
            agent_id=agent_id,
            input_payload=input_payload,
            run_progress=SEARCH_REPORT_RUN_PROGRESS_START[REPORT_STAGE_KEY],
            stage_progress=SEARCH_REPORT_STAGE_RUNNING_PROGRESS[REPORT_STAGE_KEY],
            message="正在生成報告...",
        )

        try:
            response_payload = self._dispatch_agent(
                instance_id=run.instance_id,
                agent_id=agent_id,
                session_key=f"{run.id}-{REPORT_STAGE_KEY}",
                message=_build_report_prompt(query=str(run.input_payload.get("query") or ""), analysis_output=analysis_output.model_dump()),
                metadata={"workflow_run_id": run.id, "stage_key": REPORT_STAGE_KEY, "workflow_type": run.workflow_type},
            )
            report_output = _parse_agent_output(response_payload, WorkflowReportPayload, "報告階段")
            self.workflow_repository.update_stage(
                run_id=run.id,
                stage_key=REPORT_STAGE_KEY,
                status="completed",
                progress_percent=100,
                output_payload=report_output.model_dump(),
                completed_at=utc_now_iso(),
            )
            self.workflow_repository.update_run_status(
                run_id=run.id,
                status="running",
                current_stage=REPORT_STAGE_KEY,
                active_agent_id=agent_id,
                overall_progress_percent=100,
                final_payload=report_output.model_dump(),
                error_message=None,
            )
            return report_output
        except OpenClawServiceError as error:
            self._mark_stage_failed(run_id=run.id, stage_key=REPORT_STAGE_KEY, agent_id=agent_id, error=error)
            raise

    def _run_web_understand_stage(self, run: WorkflowRunResponse, agent_id: str) -> WorkflowWebSearchUnderstandOutput:
        input_payload = dict(run.input_payload)
        self._mark_stage_running(
            run_id=run.id,
            stage_key=UNDERSTAND_STAGE_KEY,
            agent_id=agent_id,
            input_payload=input_payload,
            run_progress=WEB_SEARCH_RUN_PROGRESS_START[UNDERSTAND_STAGE_KEY],
            stage_progress=WEB_SEARCH_STAGE_RUNNING_PROGRESS[UNDERSTAND_STAGE_KEY],
            message="正在理解搜尋目標...",
        )
        try:
            response_payload = self._dispatch_agent(
                instance_id=run.instance_id,
                agent_id=agent_id,
                session_key=f"{run.id}-{UNDERSTAND_STAGE_KEY}",
                message=_build_web_understand_prompt(run.input_payload),
                metadata={"workflow_run_id": run.id, "stage_key": UNDERSTAND_STAGE_KEY, "workflow_type": run.workflow_type},
            )
            understand_output = _parse_agent_output(response_payload, WorkflowWebSearchUnderstandOutput, "理解階段")
            self.workflow_repository.update_stage(
                run_id=run.id,
                stage_key=UNDERSTAND_STAGE_KEY,
                status="completed",
                progress_percent=100,
                output_payload=understand_output.model_dump(),
                completed_at=utc_now_iso(),
            )
            self.workflow_repository.update_run_status(
                run_id=run.id,
                status="running",
                current_stage=UNDERSTAND_STAGE_KEY,
                active_agent_id=agent_id,
                overall_progress_percent=WEB_SEARCH_RUN_PROGRESS_DONE[UNDERSTAND_STAGE_KEY],
                error_message=None,
            )
            self.workflow_repository.add_event(
                run_id=run.id,
                stage_key=UNDERSTAND_STAGE_KEY,
                agent_id=agent_id,
                status="completed",
                progress_percent=WEB_SEARCH_RUN_PROGRESS_DONE[UNDERSTAND_STAGE_KEY],
                message="已整理搜尋意圖與查詢策略。",
                payload={"keywords": understand_output.keywords, "output_format": understand_output.output_format},
            )
            return understand_output
        except OpenClawServiceError as error:
            self._mark_stage_failed(run_id=run.id, stage_key=UNDERSTAND_STAGE_KEY, agent_id=agent_id, error=error)
            raise

    def _run_web_search_stage(
        self,
        run: WorkflowRunResponse,
        agent_id: str,
        understand_output: WorkflowWebSearchUnderstandOutput,
    ) -> WorkflowWebSearchSearchOutput:
        input_payload = {"request": run.input_payload, "understand_output": understand_output.model_dump()}
        self._mark_stage_running(
            run_id=run.id,
            stage_key=SEARCH_STAGE_KEY,
            agent_id=agent_id,
            input_payload=input_payload,
            run_progress=WEB_SEARCH_RUN_PROGRESS_START[SEARCH_STAGE_KEY],
            stage_progress=WEB_SEARCH_STAGE_RUNNING_PROGRESS[SEARCH_STAGE_KEY],
            message="根據條件搜尋外部資料中...",
        )
        self.workflow_repository.add_event(
            run_id=run.id,
            stage_key=SEARCH_STAGE_KEY,
            agent_id=agent_id,
            status="running",
            progress_percent=40,
            message="正在擷取與任務最相關的內容...",
            payload={"keywords": understand_output.keywords, "target_domains": understand_output.target_domains},
        )
        try:
            response_payload = self._dispatch_agent(
                instance_id=run.instance_id,
                agent_id=agent_id,
                session_key=f"{run.id}-{SEARCH_STAGE_KEY}",
                message=_build_web_search_prompt(run.input_payload, understand_output),
                metadata={"workflow_run_id": run.id, "stage_key": SEARCH_STAGE_KEY, "workflow_type": run.workflow_type},
            )
            search_output = _parse_agent_output(response_payload, WorkflowWebSearchSearchOutput, "Web Search 搜尋階段")
            self.workflow_repository.update_stage(
                run_id=run.id,
                stage_key=SEARCH_STAGE_KEY,
                status="completed",
                progress_percent=100,
                output_payload=search_output.model_dump(),
                completed_at=utc_now_iso(),
            )
            self.workflow_repository.update_run_status(
                run_id=run.id,
                status="running",
                current_stage=SEARCH_STAGE_KEY,
                active_agent_id=agent_id,
                overall_progress_percent=WEB_SEARCH_RUN_PROGRESS_DONE[SEARCH_STAGE_KEY],
                error_message=None,
            )
            self.workflow_repository.add_event(
                run_id=run.id,
                stage_key=SEARCH_STAGE_KEY,
                agent_id=agent_id,
                status="completed",
                progress_percent=WEB_SEARCH_RUN_PROGRESS_DONE[SEARCH_STAGE_KEY],
                message="搜尋階段完成，已取得候選網站與資料來源。",
                payload={"source_count": len(search_output.sources)},
            )
            return search_output
        except OpenClawServiceError as error:
            self._mark_stage_failed(run_id=run.id, stage_key=SEARCH_STAGE_KEY, agent_id=agent_id, error=error)
            raise

    def _run_web_filter_stage(
        self,
        run: WorkflowRunResponse,
        agent_id: str,
        understand_output: WorkflowWebSearchUnderstandOutput,
        search_output: WorkflowWebSearchSearchOutput,
    ) -> WorkflowWebSearchFilterOutput:
        input_payload = {
            "understand_output": understand_output.model_dump(),
            "search_output": search_output.model_dump(),
        }
        self._mark_stage_running(
            run_id=run.id,
            stage_key=FILTER_STAGE_KEY,
            agent_id=agent_id,
            input_payload=input_payload,
            run_progress=WEB_SEARCH_RUN_PROGRESS_START[FILTER_STAGE_KEY],
            stage_progress=WEB_SEARCH_STAGE_RUNNING_PROGRESS[FILTER_STAGE_KEY],
            message="正在過濾無關資訊...",
        )
        try:
            response_payload = self._dispatch_agent(
                instance_id=run.instance_id,
                agent_id=agent_id,
                session_key=f"{run.id}-{FILTER_STAGE_KEY}",
                message=_build_web_filter_prompt(understand_output, search_output),
                metadata={"workflow_run_id": run.id, "stage_key": FILTER_STAGE_KEY, "workflow_type": run.workflow_type},
            )
            filter_output = _parse_agent_output(response_payload, WorkflowWebSearchFilterOutput, "Web Search 過濾階段")
            self.workflow_repository.update_stage(
                run_id=run.id,
                stage_key=FILTER_STAGE_KEY,
                status="completed",
                progress_percent=100,
                output_payload=filter_output.model_dump(),
                completed_at=utc_now_iso(),
            )
            self.workflow_repository.update_run_status(
                run_id=run.id,
                status="running",
                current_stage=FILTER_STAGE_KEY,
                active_agent_id=agent_id,
                overall_progress_percent=WEB_SEARCH_RUN_PROGRESS_DONE[FILTER_STAGE_KEY],
                error_message=None,
            )
            self.workflow_repository.add_event(
                run_id=run.id,
                stage_key=FILTER_STAGE_KEY,
                agent_id=agent_id,
                status="completed",
                progress_percent=WEB_SEARCH_RUN_PROGRESS_DONE[FILTER_STAGE_KEY],
                message="已完成來源過濾與重點抽取。",
                payload={"kept_count": len(filter_output.kept_sources), "discarded_count": filter_output.discarded_count},
            )
            return filter_output
        except OpenClawServiceError as error:
            self._mark_stage_failed(run_id=run.id, stage_key=FILTER_STAGE_KEY, agent_id=agent_id, error=error)
            raise

    def _run_web_format_stage(
        self,
        run: WorkflowRunResponse,
        agent_id: str,
        understand_output: WorkflowWebSearchUnderstandOutput,
        filter_output: WorkflowWebSearchFilterOutput,
    ) -> WorkflowWebSearchResult:
        input_payload = {
            "understand_output": understand_output.model_dump(),
            "filter_output": filter_output.model_dump(),
        }
        self._mark_stage_running(
            run_id=run.id,
            stage_key=FORMAT_STAGE_KEY,
            agent_id=agent_id,
            input_payload=input_payload,
            run_progress=WEB_SEARCH_RUN_PROGRESS_START[FORMAT_STAGE_KEY],
            stage_progress=WEB_SEARCH_STAGE_RUNNING_PROGRESS[FORMAT_STAGE_KEY],
            message="正在格式化搜尋結果...",
        )
        self.workflow_repository.add_event(
            run_id=run.id,
            stage_key=FORMAT_STAGE_KEY,
            agent_id=agent_id,
            status="running",
            progress_percent=95,
            message="正在以指定格式輸出結果...",
            payload={"output_format": understand_output.output_format},
        )
        try:
            response_payload = self._dispatch_agent(
                instance_id=run.instance_id,
                agent_id=agent_id,
                session_key=f"{run.id}-{FORMAT_STAGE_KEY}",
                message=_build_web_format_prompt(run.input_payload, understand_output, filter_output),
                metadata={"workflow_run_id": run.id, "stage_key": FORMAT_STAGE_KEY, "workflow_type": run.workflow_type},
            )
            result_output = _parse_agent_output(response_payload, WorkflowWebSearchResult, "Web Search 格式化階段")
            self.workflow_repository.update_stage(
                run_id=run.id,
                stage_key=FORMAT_STAGE_KEY,
                status="completed",
                progress_percent=100,
                output_payload=result_output.model_dump(),
                completed_at=utc_now_iso(),
            )
            self.workflow_repository.update_run_status(
                run_id=run.id,
                status="running",
                current_stage=FORMAT_STAGE_KEY,
                active_agent_id=agent_id,
                overall_progress_percent=100,
                final_payload=result_output.model_dump(),
                error_message=None,
            )
            return result_output
        except OpenClawServiceError as error:
            self._mark_stage_failed(run_id=run.id, stage_key=FORMAT_STAGE_KEY, agent_id=agent_id, error=error)
            raise

    def _mark_stage_running(
        self,
        *,
        run_id: str,
        stage_key: str,
        agent_id: str,
        input_payload: dict[str, Any],
        run_progress: int,
        stage_progress: int,
        message: str,
    ) -> None:
        started_at = utc_now_iso()
        self.workflow_repository.update_stage(
            run_id=run_id,
            stage_key=stage_key,
            status="running",
            progress_percent=stage_progress,
            input_payload=input_payload,
            started_at=started_at,
        )
        self.workflow_repository.update_run_status(
            run_id=run_id,
            status="running",
            current_stage=stage_key,
            active_agent_id=agent_id,
            overall_progress_percent=run_progress,
            error_message=None,
        )
        self.workflow_repository.add_event(
            run_id=run_id,
            stage_key=stage_key,
            agent_id=agent_id,
            status="running",
            progress_percent=run_progress,
            message=message,
            payload=input_payload,
        )

    def _dispatch_agent(
        self,
        *,
        instance_id: str,
        agent_id: str,
        session_key: str,
        message: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        instance, token = self._load_context(instance_id)
        request_summary = {
            "agent_id": agent_id,
            "session_key": session_key,
            "message_preview": truncate_text(message, 200),
        }
        try:
            result = self.hook_client.dispatch_agent(
                instance,
                token,
                {
                    "agent_id": agent_id,
                    "session_key": session_key,
                    "message": message,
                    "deliver": False,
                    "metadata": metadata,
                },
            )
            self.operation_log_repository.create(
                instance_id=instance_id,
                operation_type="dispatch_workflow_stage",
                target_type="workflow_stage",
                target_id=f"{agent_id}:{session_key}",
                status="success",
                error_message=None,
                request_summary=request_summary,
                response_summary={"status": result.get("status"), "summary": result.get("summary")},
                source_mode=self.hook_client.source_mode,
            )
            return result
        except OpenClawServiceError as error:
            self.operation_log_repository.create(
                instance_id=instance_id,
                operation_type="dispatch_workflow_stage",
                target_type="workflow_stage",
                target_id=f"{agent_id}:{session_key}",
                status="failed",
                error_message=error.detail or error.message,
                request_summary=request_summary,
                response_summary=None,
                source_mode=error.source_mode or self.hook_client.source_mode,
            )
            raise

    def _mark_stage_failed(self, *, run_id: str, stage_key: str, agent_id: str, error: OpenClawServiceError) -> None:
        self.workflow_repository.update_stage(
            run_id=run_id,
            stage_key=stage_key,
            status="failed",
            progress_percent=100,
            completed_at=utc_now_iso(),
        )
        self.workflow_repository.add_event(
            run_id=run_id,
            stage_key=stage_key,
            agent_id=agent_id,
            status="failed",
            progress_percent=100,
            message=f"{stage_key} 階段失敗。",
            payload={"error": error.detail or error.message},
        )

    def _mark_run_failed(self, run_id: str, error: OpenClawServiceError) -> None:
        failed_run = self.workflow_repository.get_run(run_id)
        self.workflow_repository.update_run_status(
            run_id=run_id,
            status="failed",
            current_stage=failed_run.current_stage,
            active_agent_id=failed_run.active_agent_id,
            overall_progress_percent=failed_run.overall_progress_percent,
            final_payload=_extract_final_payload(failed_run),
            error_message=error.detail or error.message,
        )
        self.workflow_repository.add_event(
            run_id=run_id,
            stage_key=failed_run.current_stage,
            agent_id=failed_run.active_agent_id,
            status="failed",
            progress_percent=failed_run.overall_progress_percent,
            message="工作流失敗，已保留目前鏈路與錯誤點。",
            payload={"error": error.detail or error.message},
        )

    def _ensure_instance_exists(self, instance_id: str) -> None:
        self.repository.get(instance_id)

    def _get_config_or_error(self, instance_id: str) -> OpenClawWorkflowConfigResponse:
        try:
            return self.workflow_config_repository.get(instance_id)
        except KeyError as error:
            raise OpenClawServiceError(
                "此 Instance 尚未設定搜索、分析、報告三階段 agent。",
                detail="尚未設定搜索、分析、報告三階段 agent。",
                status_code=400,
                source_mode=self.source_mode,
            ) from error

    def _load_context(self, instance_id: str):
        instance = self.repository.get(instance_id)
        encrypted_token = self.repository.get_secret(instance_id)
        token = self.secret_cipher.decrypt(encrypted_token) if encrypted_token else None
        return instance, token

    @staticmethod
    def _get_stage(run: WorkflowRunResponse, stage_key: str):
        for stage in run.stages:
            if stage.stage_key == stage_key:
                return stage
        raise OpenClawServiceError(
            "找不到指定的 workflow stage。",
            detail=f"missing stage: {stage_key}",
            status_code=500,
            source_mode="workflow",
        )


def _build_search_prompt(*, query: str, source_id: Any) -> str:
    source_scope = f"僅限 source_id={source_id}" if isinstance(source_id, str) and source_id else "可跨所有已索引資料源"
    return (
        "你是搜索階段代理，必須使用 project_search 與 project_document 工具完成工作，不可改用 exec、web_search 或自行假設結果。\n"
        f"查詢：{query}\n"
        f"資料範圍：{source_scope}\n"
        "請先用 project_search 找候選文件，再用 project_document 讀取最重要的 1-3 份文件全文，最後只輸出 JSON。\n"
        "JSON schema:\n"
        "{\n"
        '  "summary": "一句話說明搜索結論",\n'
        '  "candidates": [{"document_id":"...", "filename":"...", "relative_path":"...", "source_id":"...", "source_name":"...", "snippet":"...", "reason":"..."}],\n'
        '  "selected_documents": [{"document_id":"...", "filename":"...", "relative_path":"...", "source_id":"...", "source_name":"...", "snippet":"...", "reason":"..."}],\n'
        '  "source_overview": ["..."]\n'
        "}\n"
        "不要輸出解釋文字，不要包 <final>。"
    )


def _build_analysis_prompt(*, query: str, search_output: dict[str, Any]) -> str:
    return (
        "你是分析階段代理。請根據以下搜索階段結果，整理多文件綜合分析，只輸出 JSON。\n"
        f"原始查詢：{query}\n"
        f"搜索結果：{json.dumps(search_output, ensure_ascii=False)}\n"
        "JSON schema:\n"
        "{\n"
        '  "summary": "整體分析摘要",\n'
        '  "highlights": ["..."],\n'
        '  "risks": ["..."],\n'
        '  "todos": ["..."],\n'
        '  "evidence": [{"document_id":"...", "filename":"...", "quote":"...", "reason":"..."}]\n'
        "}\n"
        "不要輸出 Markdown，不要輸出額外文字。"
    )


def _build_report_prompt(*, query: str, analysis_output: dict[str, Any]) -> str:
    return (
        "你是報告階段代理。請根據以下分析輸出生成可交付報告，只輸出 JSON。\n"
        f"原始查詢：{query}\n"
        f"分析結果：{json.dumps(analysis_output, ensure_ascii=False)}\n"
        "JSON schema:\n"
        "{\n"
        '  "title": "報告標題",\n'
        '  "executive_summary": "總結",\n'
        '  "highlights": ["..."],\n'
        '  "recommendations": ["..."],\n'
        '  "evidence": [{"document_id":"...", "filename":"...", "quote":"...", "reason":"..."}],\n'
        '  "sections": [{"title":"...", "summary":"...", "bullets":["..."], "body":"..."}],\n'
        '  "appendix": ["..."],\n'
        '  "markdown": "# ..."\n'
        "}\n"
        "不要輸出額外說明。"
    )


def _build_web_understand_prompt(request_payload: dict[str, Any]) -> str:
    return (
        "你是 Web Search 的理解階段代理。請先理解使用者的搜尋目標與條件，之後其他階段會承接你的輸出。\n"
        f"原始請求：{json.dumps(request_payload, ensure_ascii=False)}\n"
        "只輸出 JSON，不要使用 Markdown。\n"
        "JSON schema:\n"
        "{\n"
        '  "goal_summary": "一句話總結這次搜尋任務",\n'
        '  "normalized_topic": "重寫後的主題",\n'
        '  "search_plan": ["..."],\n'
        '  "keywords": ["..."],\n'
        '  "target_urls": ["..."],\n'
        '  "target_sites": ["..."],\n'
        '  "target_domains": ["..."],\n'
        '  "must_include": ["..."],\n'
        '  "must_exclude": ["..."],\n'
        '  "focus_points": ["..."],\n'
        '  "output_format": "summary|bullets|table|comparison",\n'
        '  "include_project_sources": true\n'
        "}\n"
        "不要輸出額外文字。"
    )


def _build_web_search_prompt(request_payload: dict[str, Any], understand_output: WorkflowWebSearchUnderstandOutput) -> str:
    return (
        "你是 Web Search 的搜尋階段代理，必須使用 OpenClaw 內建 web_search 工具完成外網搜尋。\n"
        "若 include_project_sources=true 且目前有 project_search / project_document，也可補充 1-2 筆專案索引結果。\n"
        f"原始請求：{json.dumps(request_payload, ensure_ascii=False)}\n"
        f"理解階段輸出：{json.dumps(understand_output.model_dump(), ensure_ascii=False)}\n"
        "請根據 topic、網址、網站、網域、關鍵字、include/exclude 條件執行搜尋，再只輸出 JSON。\n"
        "JSON schema:\n"
        "{\n"
        '  "summary": "一句話說明搜尋結果",\n'
        '  "search_queries": ["..."],\n'
        '  "sources": [\n'
        '    {\n'
        '      "title": "...",\n'
        '      "source_type": "web|project",\n'
        '      "snippet": "...",\n'
        '      "reason": "...",\n'
        '      "matched_keywords": ["..."],\n'
        '      "url": "https://...",\n'
        '      "domain": "example.com",\n'
        '      "source_name": "...",\n'
        '      "document_id": "...",\n'
        '      "relative_path": "..."\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "不要輸出額外說明。"
    )


def _build_web_filter_prompt(
    understand_output: WorkflowWebSearchUnderstandOutput,
    search_output: WorkflowWebSearchSearchOutput,
) -> str:
    return (
        "你是 Web Search 的過濾階段代理。請根據 must_include、must_exclude、focus_points 與搜尋目標過濾來源。\n"
        f"理解階段輸出：{json.dumps(understand_output.model_dump(), ensure_ascii=False)}\n"
        f"搜尋階段輸出：{json.dumps(search_output.model_dump(), ensure_ascii=False)}\n"
        "請只留下真正相關的來源與資訊，並只輸出 JSON。\n"
        "JSON schema:\n"
        "{\n"
        '  "summary": "一句話說明過濾後結果",\n'
        '  "kept_sources": [\n'
        '    {\n'
        '      "title": "...",\n'
        '      "source_type": "web|project",\n'
        '      "snippet": "...",\n'
        '      "reason": "...",\n'
        '      "matched_keywords": ["..."],\n'
        '      "url": "https://...",\n'
        '      "domain": "example.com",\n'
        '      "source_name": "...",\n'
        '      "document_id": "...",\n'
        '      "relative_path": "..."\n'
        "    }\n"
        "  ],\n"
        '  "discarded_count": 0,\n'
        '  "extracted_points": ["..."],\n'
        '  "focus_answers": ["..."]\n'
        "}\n"
        "不要輸出額外說明。"
    )


def _build_web_format_prompt(
    request_payload: dict[str, Any],
    understand_output: WorkflowWebSearchUnderstandOutput,
    filter_output: WorkflowWebSearchFilterOutput,
) -> str:
    return (
        "你是 Web Search 的格式化階段代理。請把已過濾的結果轉成使用者指定格式，並保留清楚來源。\n"
        f"原始請求：{json.dumps(request_payload, ensure_ascii=False)}\n"
        f"理解階段輸出：{json.dumps(understand_output.model_dump(), ensure_ascii=False)}\n"
        f"過濾階段輸出：{json.dumps(filter_output.model_dump(), ensure_ascii=False)}\n"
        "只輸出 JSON。\n"
        "JSON schema:\n"
        "{\n"
        '  "title": "結果標題",\n'
        '  "requested_format": "summary|bullets|table|comparison",\n'
        '  "summary": "最終摘要",\n'
        '  "key_points": ["..."],\n'
        '  "focus_answers": ["..."],\n'
        '  "included_sources": [\n'
        '    {\n'
        '      "title": "...",\n'
        '      "source_type": "web|project",\n'
        '      "snippet": "...",\n'
        '      "reason": "...",\n'
        '      "matched_keywords": ["..."],\n'
        '      "url": "https://...",\n'
        '      "domain": "example.com",\n'
        '      "source_name": "...",\n'
        '      "document_id": "...",\n'
        '      "relative_path": "..."\n'
        "    }\n"
        "  ],\n"
        '  "applied_filters": ["..."],\n'
        '  "structured_output": "依指定格式排好的主要內容",\n'
        '  "markdown": "# ..."\n'
        "}\n"
        "不要輸出額外說明。"
    )


def _web_result_to_search_output(result: WorkflowWebSearchResult) -> WorkflowSearchStageOutput:
    candidates = []
    for source in result.included_sources:
        if source.document_id and source.source_name:
            candidates.append(
                {
                    "document_id": source.document_id,
                    "filename": source.title,
                    "relative_path": source.relative_path or source.title,
                    "source_id": source.source_name,
                    "source_name": source.source_name,
                    "snippet": source.snippet,
                    "reason": source.reason,
                }
            )

    if not candidates:
        candidates = [
            {
                "document_id": source.document_id or (source.url or source.title),
                "filename": source.title,
                "relative_path": source.relative_path or source.url or source.title,
                "source_id": source.source_name or source.domain or source.source_type,
                "source_name": source.source_name or source.domain or source.source_type,
                "snippet": source.snippet,
                "reason": source.reason,
            }
            for source in result.included_sources
        ]

    return WorkflowSearchStageOutput(
        summary=result.summary,
        candidates=candidates,
        selected_documents=candidates[: min(3, len(candidates))],
        source_overview=[source.title for source in result.included_sources[:5]],
    )


def _extract_final_payload(run: WorkflowRunResponse) -> dict[str, Any] | None:
    if run.final_report is not None:
        return run.final_report.model_dump()
    if run.final_web_result is not None:
        return run.final_web_result.model_dump()
    return None


def _parse_agent_output(payload: dict[str, Any], schema, stage_label: str):
    text_payload = _extract_agent_text(payload)
    if not text_payload:
        raise OpenClawServiceError(
            f"{stage_label} 沒有產出可解析文字。",
            detail=truncate_text(json.dumps(payload, ensure_ascii=False)),
            source_mode="workflow",
        )

    try:
        return schema(**_extract_json_object(text_payload))
    except Exception as error:  # noqa: BLE001
        raise OpenClawServiceError(
            f"{stage_label} 輸出格式不正確。",
            detail=truncate_text(text_payload, 400),
            source_mode="workflow",
        ) from error


def _extract_agent_text(payload: dict[str, Any]) -> str:
    result = payload.get("result")
    if isinstance(result, dict):
        payloads = result.get("payloads")
        if isinstance(payloads, list):
            for item in payloads:
                if isinstance(item, dict) and isinstance(item.get("text"), str) and item["text"].strip():
                    return item["text"].strip()

    if isinstance(payload.get("text"), str):
        return payload["text"].strip()

    return ""


def _extract_json_object(text_payload: str) -> dict[str, Any]:
    fenced_match = re.search(r"```json\s*(\{.*?\})\s*```", text_payload, flags=re.DOTALL)
    if fenced_match:
        return json.loads(fenced_match.group(1))

    decoder = json.JSONDecoder()
    for start_index, char in enumerate(text_payload):
        if char != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(text_payload[start_index:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    return json.loads(text_payload)


def _elapsed_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)
