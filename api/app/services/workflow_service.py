from __future__ import annotations

import json
import re
import random
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Any, Optional

from app.repositories.openclaw_daily_news_config_repository import OpenClawDailyNewsConfigRepository
from app.repositories.openclaw_development_config_repository import OpenClawDevelopmentConfigRepository
from app.repositories.openclaw_agent_capability_repository import OpenClawAgentCapabilityRepository
from app.repositories.openclaw_instance_repository import OpenClawInstanceRepository
from app.repositories.openclaw_operation_log_repository import OpenClawOperationLogRepository
from app.repositories.openclaw_system_inspection_config_repository import OpenClawSystemInspectionConfigRepository
from app.repositories.openclaw_workflow_config_repository import OpenClawWorkflowConfigRepository
from app.repositories.workflow_repository import WorkflowRepository
from app.schemas.knowledge import KnowledgeIngestRequest
from app.schemas.openclaw_daily_news import OpenClawDailyNewsConfigRequest, OpenClawDailyNewsConfigResponse
from app.schemas.openclaw_development import OpenClawDevelopmentConfigRequest, OpenClawDevelopmentConfigResponse
from app.schemas.openclaw_system_inspection import (
    OpenClawSystemInspectionConfigRequest,
    OpenClawSystemInspectionConfigResponse,
)
from app.schemas.openclaw_workflow_config import OpenClawWorkflowConfigResponse, OpenClawWorkflowConfigUpdateRequest
from app.schemas.workflow import (
    WORKFLOW_TYPE_DEVELOPMENT_EXECUTION,
    WORKFLOW_TYPE_NEWS_BRIEF,
    WORKFLOW_TYPE_SEARCH_REPORT,
    WORKFLOW_TYPE_SYSTEM_INSPECTION,
    WORKFLOW_TYPE_WEB_SEARCH,
    WorkflowAnalysisStageOutput,
    WorkflowDevelopmentDesignOutput,
    WorkflowDevelopmentExecutionCreateRequest,
    WorkflowDevelopmentExecutionReportPayload,
    WorkflowDevelopmentImplementationOutput,
    WorkflowDevelopmentOptimizationOutput,
    WorkflowDevelopmentProblemDefinitionOutput,
    WorkflowDevelopmentRequirementsOutput,
    WorkflowDevelopmentTaskPlanningOutput,
    WorkflowDevelopmentTechnologySelectionOutput,
    WorkflowDevelopmentTestingOutput,
    WorkflowNewsBriefCreateRequest,
    WorkflowNewsBriefPayload,
    WorkflowNewsDedupeOutput,
    WorkflowNewsMonitorOutput,
    WorkflowNewsRankOutput,
    WorkflowNewsSourceItem,
    WorkflowNewsSearchOutput,
    WorkflowNewsStory,
    WorkflowReportPayload,
    WorkflowRunResponse,
    WorkflowSearchReportCreateRequest,
    WorkflowSearchStageOutput,
    WorkflowSystemInspectionCreateRequest,
    WorkflowSystemInspectionLogIssue,
    WorkflowSystemInspectionLogReviewOutput,
    WorkflowSystemInspectionReportDraft,
    WorkflowSystemInspectionReportPayload,
    WorkflowSystemInspectionRiskOutput,
    WorkflowSystemInspectionSnapshotOutput,
    WorkflowSystemInspectionVersionOutput,
    WorkflowWebSearchCreateRequest,
    WorkflowWebSearchFilterOutput,
    WorkflowWebSearchIngestOutput,
    WorkflowWebSearchResult,
    WorkflowWebSearchSearchOutput,
    WorkflowWebSearchSourceItem,
    WorkflowWebSearchUnderstandOutput,
)
from app.services.knowledge_ingestion_service import KnowledgeIngestionService
from app.services.openclaw_cli_adapter import OpenClawCliAdapter
from app.services.openclaw_cron_service import OpenClawCronSchedulingService, summarize_cron_reconcile_error
from app.services.openclaw_errors import OpenClawServiceError
from app.services.openclaw_hook_client import OpenClawHookClient
from app.services.openclaw_release_client import OpenClawReleaseClient
from app.services.openclaw_secret_cipher import OpenClawSecretCipher
from app.services.discord_delivery_client import DiscordDeliveryClient
from app.services.telegram_delivery_client import TelegramDeliveryClient
from app.utils import truncate_text, utc_now_iso


SEARCH_STAGE_KEY = "search"
ANALYSIS_STAGE_KEY = "analysis"
REPORT_STAGE_KEY = "report"
UNDERSTAND_STAGE_KEY = "understand"
FILTER_STAGE_KEY = "filter"
INGEST_STAGE_KEY = "ingest"
FORMAT_STAGE_KEY = "format"
MONITOR_STAGE_KEY = "monitor"
DEDUPE_STAGE_KEY = "dedupe"
RANK_STAGE_KEY = "rank"
BRIEF_STAGE_KEY = "brief"
SNAPSHOT_STAGE_KEY = "snapshot"
VERSION_CHECK_STAGE_KEY = "version_check"
LOG_REVIEW_STAGE_KEY = "log_review"
RISK_ASSESSMENT_STAGE_KEY = "risk_assessment"
PROBLEM_DEFINITION_STAGE_KEY = "problem_definition"
REQUIREMENTS_ANALYSIS_STAGE_KEY = "requirements_analysis"
SOLUTION_DESIGN_STAGE_KEY = "solution_design"
TECHNOLOGY_SELECTION_STAGE_KEY = "technology_selection"
TASK_PLANNING_STAGE_KEY = "task_planning"
IMPLEMENTATION_STAGE_KEY = "implementation"
TESTING_STAGE_KEY = "testing"
OPTIMIZATION_STAGE_KEY = "optimization"
HANDOFF_STAGE_KEY = "handoff"
DEVELOPMENT_DELIVERY_AGENT_ID = "fullstack-engineer-agent"

SEARCH_REPORT_STAGE_SEQUENCE = (SEARCH_STAGE_KEY, ANALYSIS_STAGE_KEY, REPORT_STAGE_KEY)
WEB_SEARCH_STAGE_SEQUENCE = (UNDERSTAND_STAGE_KEY, SEARCH_STAGE_KEY, FILTER_STAGE_KEY, INGEST_STAGE_KEY, FORMAT_STAGE_KEY)
NEWS_BRIEF_STAGE_SEQUENCE = (MONITOR_STAGE_KEY, SEARCH_STAGE_KEY, DEDUPE_STAGE_KEY, RANK_STAGE_KEY, BRIEF_STAGE_KEY)
SYSTEM_INSPECTION_STAGE_SEQUENCE = (SNAPSHOT_STAGE_KEY, VERSION_CHECK_STAGE_KEY, LOG_REVIEW_STAGE_KEY, RISK_ASSESSMENT_STAGE_KEY, REPORT_STAGE_KEY)
DEVELOPMENT_EXECUTION_STAGE_SEQUENCE = (
    PROBLEM_DEFINITION_STAGE_KEY,
    REQUIREMENTS_ANALYSIS_STAGE_KEY,
    SOLUTION_DESIGN_STAGE_KEY,
    TECHNOLOGY_SELECTION_STAGE_KEY,
    TASK_PLANNING_STAGE_KEY,
    IMPLEMENTATION_STAGE_KEY,
    TESTING_STAGE_KEY,
    OPTIMIZATION_STAGE_KEY,
    HANDOFF_STAGE_KEY,
)


def _default_development_config(instance_id: str) -> OpenClawDevelopmentConfigResponse:
    epoch = datetime.fromtimestamp(0, timezone.utc)
    return OpenClawDevelopmentConfigResponse(
        instance_id=instance_id,
        enabled=False,
        delivery_channel="discord",
        discord_channel_id="",
        last_run_id=None,
        last_delivery_status=None,
        last_delivery_error=None,
        config_source="default",
        effective_delivery_source="none",
        effective_discord_channel_id=None,
        effective_delivery_reason=None,
        created_at=epoch,
        updated_at=epoch,
    )


def _resolve_development_runtime_route_channel() -> str | None:
    from app.config import REPO_ROOT, get_settings

    settings = get_settings()
    candidate_paths = [settings.openclaw_home_dir / "openclaw.json", REPO_ROOT / ".openclaw" / "openclaw.json"]
    seen_paths: set[Path] = set()
    for config_path in candidate_paths:
        if config_path in seen_paths:
            continue
        seen_paths.add(config_path)
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        bindings = payload.get("bindings")
        if not isinstance(bindings, list):
            continue

        for binding in bindings:
            if not isinstance(binding, dict):
                continue
            if binding.get("type") != "route" or binding.get("agentId") != DEVELOPMENT_DELIVERY_AGENT_ID:
                continue

            match = binding.get("match")
            if not isinstance(match, dict) or match.get("channel") != "discord":
                continue

            peer = match.get("peer")
            if not isinstance(peer, dict) or peer.get("kind") != "channel":
                continue

            channel_id = str(peer.get("id") or "").strip()
            if channel_id:
                return channel_id
    return None


def _resolve_development_delivery_target(
    instance_id: str,
    config: OpenClawDevelopmentConfigResponse | None,
) -> dict[str, str | None]:
    if config is not None:
        if config.enabled and config.discord_channel_id.strip():
            return {
                "target": config.discord_channel_id.strip(),
                "source": "development_config",
                "reason": "已使用 Development 專屬 Discord 設定。",
            }
        return {
            "target": None,
            "source": "none",
            "reason": "Development 專屬設定已停用 Discord 匯報。",
        }

    runtime_channel_id = _resolve_development_runtime_route_channel()
    if runtime_channel_id:
        return {
            "target": runtime_channel_id,
            "source": "runtime_route",
            "reason": f"未找到 Development 專屬設定，已回退使用 Discord #develop route（{runtime_channel_id}）。",
        }

    return {
        "target": None,
        "source": "none",
        "reason": "未找到 Development 專屬設定，且 runtime route 未配置 fullstack-engineer-agent 的 Discord channel。",
    }


def _enrich_development_config_response(
    instance_id: str,
    config: OpenClawDevelopmentConfigResponse | None,
) -> OpenClawDevelopmentConfigResponse:
    base = config.model_copy() if config is not None else _default_development_config(instance_id)
    resolution = _resolve_development_delivery_target(instance_id, config)
    return base.model_copy(
        update={
            "config_source": "stored" if config is not None else "default",
            "effective_delivery_source": resolution["source"],
            "effective_discord_channel_id": resolution["target"],
            "effective_delivery_reason": resolution["reason"],
        }
    )

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
    INGEST_STAGE_KEY: 75,
    FORMAT_STAGE_KEY: 88,
}
WEB_SEARCH_RUN_PROGRESS_DONE = {
    UNDERSTAND_STAGE_KEY: 20,
    SEARCH_STAGE_KEY: 50,
    FILTER_STAGE_KEY: 70,
    INGEST_STAGE_KEY: 86,
    FORMAT_STAGE_KEY: 100,
}
WEB_SEARCH_STAGE_RUNNING_PROGRESS = {
    UNDERSTAND_STAGE_KEY: 25,
    SEARCH_STAGE_KEY: 45,
    FILTER_STAGE_KEY: 66,
    INGEST_STAGE_KEY: 82,
    FORMAT_STAGE_KEY: 94,
}

NEWS_BRIEF_RUN_PROGRESS_START = {
    MONITOR_STAGE_KEY: 5,
    SEARCH_STAGE_KEY: 20,
    DEDUPE_STAGE_KEY: 45,
    RANK_STAGE_KEY: 70,
    BRIEF_STAGE_KEY: 88,
}
NEWS_BRIEF_RUN_PROGRESS_DONE = {
    MONITOR_STAGE_KEY: 15,
    SEARCH_STAGE_KEY: 40,
    DEDUPE_STAGE_KEY: 65,
    RANK_STAGE_KEY: 85,
    BRIEF_STAGE_KEY: 100,
}
NEWS_BRIEF_STAGE_RUNNING_PROGRESS = {
    MONITOR_STAGE_KEY: 18,
    SEARCH_STAGE_KEY: 35,
    DEDUPE_STAGE_KEY: 55,
    RANK_STAGE_KEY: 78,
    BRIEF_STAGE_KEY: 94,
}
SYSTEM_INSPECTION_RUN_PROGRESS_START = {
    SNAPSHOT_STAGE_KEY: 5,
    VERSION_CHECK_STAGE_KEY: 20,
    LOG_REVIEW_STAGE_KEY: 45,
    RISK_ASSESSMENT_STAGE_KEY: 70,
    REPORT_STAGE_KEY: 88,
}
SYSTEM_INSPECTION_RUN_PROGRESS_DONE = {
    SNAPSHOT_STAGE_KEY: 15,
    VERSION_CHECK_STAGE_KEY: 40,
    LOG_REVIEW_STAGE_KEY: 65,
    RISK_ASSESSMENT_STAGE_KEY: 85,
    REPORT_STAGE_KEY: 100,
}
SYSTEM_INSPECTION_STAGE_RUNNING_PROGRESS = {
    SNAPSHOT_STAGE_KEY: 18,
    VERSION_CHECK_STAGE_KEY: 35,
    LOG_REVIEW_STAGE_KEY: 58,
    RISK_ASSESSMENT_STAGE_KEY: 80,
    REPORT_STAGE_KEY: 94,
}
DEVELOPMENT_EXECUTION_RUN_PROGRESS_START = {
    PROBLEM_DEFINITION_STAGE_KEY: 5,
    REQUIREMENTS_ANALYSIS_STAGE_KEY: 16,
    SOLUTION_DESIGN_STAGE_KEY: 28,
    TECHNOLOGY_SELECTION_STAGE_KEY: 40,
    TASK_PLANNING_STAGE_KEY: 52,
    IMPLEMENTATION_STAGE_KEY: 66,
    TESTING_STAGE_KEY: 80,
    OPTIMIZATION_STAGE_KEY: 90,
    HANDOFF_STAGE_KEY: 96,
}
DEVELOPMENT_EXECUTION_RUN_PROGRESS_DONE = {
    PROBLEM_DEFINITION_STAGE_KEY: 12,
    REQUIREMENTS_ANALYSIS_STAGE_KEY: 24,
    SOLUTION_DESIGN_STAGE_KEY: 36,
    TECHNOLOGY_SELECTION_STAGE_KEY: 48,
    TASK_PLANNING_STAGE_KEY: 60,
    IMPLEMENTATION_STAGE_KEY: 75,
    TESTING_STAGE_KEY: 88,
    OPTIMIZATION_STAGE_KEY: 96,
    HANDOFF_STAGE_KEY: 100,
}
DEVELOPMENT_EXECUTION_STAGE_RUNNING_PROGRESS = {
    PROBLEM_DEFINITION_STAGE_KEY: 10,
    REQUIREMENTS_ANALYSIS_STAGE_KEY: 22,
    SOLUTION_DESIGN_STAGE_KEY: 34,
    TECHNOLOGY_SELECTION_STAGE_KEY: 46,
    TASK_PLANNING_STAGE_KEY: 58,
    IMPLEMENTATION_STAGE_KEY: 72,
    TESTING_STAGE_KEY: 85,
    OPTIMIZATION_STAGE_KEY: 94,
    HANDOFF_STAGE_KEY: 98,
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
        cron_scheduling_service: Optional[OpenClawCronSchedulingService] = None,
    ) -> None:
        from app.config import get_settings

        settings = get_settings()
        self.repository = repository or OpenClawInstanceRepository()
        self.workflow_config_repository = workflow_config_repository or OpenClawWorkflowConfigRepository()
        self.operation_log_repository = operation_log_repository or OpenClawOperationLogRepository()
        self.cli_adapter = cli_adapter or OpenClawCliAdapter()
        self.secret_cipher = secret_cipher or OpenClawSecretCipher(settings.openclaw_secret_key)
        self.cron_scheduling_service = cron_scheduling_service or OpenClawCronSchedulingService(
            repository=self.repository,
            workflow_config_repository=self.workflow_config_repository,
            operation_log_repository=self.operation_log_repository,
            cli_adapter=self.cli_adapter,
            secret_cipher=self.secret_cipher,
        )

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
            invalid_specialists = [
                key
                for key, binding in payload.specialist_agents.model_dump().items()
                if isinstance(binding, dict) and binding.get("enabled") and not str(binding.get("agent_id") or "").strip()
            ]
            if invalid_specialists:
                raise OpenClawServiceError(
                    "已啟用的專職 agent 必須指定 agent_id。",
                    detail=f"missing specialist agent_id={','.join(invalid_specialists)}",
                    status_code=400,
                    source_mode=self.source_mode,
                )

            agent_ids = {
                str(item.get("id") or item.get("agent_id") or "")
                for item in self.cli_adapter.list_agents(instance, token)
            }
            missing = sorted(
                {
                    agent_id
                    for agent_id in _collect_config_agent_ids(payload)
                    if agent_id not in agent_ids
                }
            )
            if missing:
                raise OpenClawServiceError(
                    "workflow agent mapping 包含不存在的 agent。",
                    detail=f"missing={','.join(missing)}",
                    status_code=400,
                    source_mode=self.cli_adapter.source_mode,
                )

            config = self.workflow_config_repository.upsert(
                instance_id=payload.instance_id,
                controller_agent_id=payload.controller_agent_id,
                search_agent_id=payload.search_agent_id,
                analysis_agent_id=payload.analysis_agent_id,
                report_agent_id=payload.report_agent_id,
                specialist_agents=payload.specialist_agents,
                routing_rules=payload.routing_rules,
                handoff_policy=payload.handoff_policy,
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
            try:
                self.cron_scheduling_service.reconcile_instance(payload.instance_id)
            except Exception as error:  # noqa: BLE001
                self.operation_log_repository.create(
                    instance_id=payload.instance_id,
                    operation_type="configure_workflow_agents_cron_reconcile",
                    target_type="workflow_config",
                    target_id=payload.instance_id,
                    status="failed",
                    error_message=summarize_cron_reconcile_error(error),
                    request_summary={"instance_id": payload.instance_id},
                    response_summary=None,
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


class OpenClawDailyNewsConfigService:
    source_mode = "repository"

    def __init__(
        self,
        repository: Optional[OpenClawInstanceRepository] = None,
        daily_news_repository: Optional[OpenClawDailyNewsConfigRepository] = None,
        operation_log_repository: Optional[OpenClawOperationLogRepository] = None,
        cron_scheduling_service: Optional[OpenClawCronSchedulingService] = None,
    ) -> None:
        self.repository = repository or OpenClawInstanceRepository()
        self.daily_news_repository = daily_news_repository or OpenClawDailyNewsConfigRepository()
        self.operation_log_repository = operation_log_repository or OpenClawOperationLogRepository()
        self.cron_scheduling_service = cron_scheduling_service or OpenClawCronSchedulingService(
            repository=self.repository,
            daily_news_repository=self.daily_news_repository,
            operation_log_repository=self.operation_log_repository,
        )

    def get_config(self, instance_id: str) -> tuple[OpenClawDailyNewsConfigResponse, int]:
        started_at = time.perf_counter()
        self.repository.get(instance_id)
        try:
            return self.daily_news_repository.get(instance_id), _elapsed_ms(started_at)
        except KeyError as error:
            raise OpenClawServiceError(
                "尚未設定 Daily News Brief。",
                detail=str(error),
                status_code=404,
                source_mode=self.source_mode,
            ) from error

    def update_config(self, payload: OpenClawDailyNewsConfigRequest) -> tuple[OpenClawDailyNewsConfigResponse, int]:
        started_at = time.perf_counter()
        self.repository.get(payload.instance_id)
        if payload.enabled and not payload.topic.strip():
            raise OpenClawServiceError(
                "啟用 Daily News Brief 前，必須填寫主題。",
                detail="topic 必填。",
                status_code=400,
                source_mode=self.source_mode,
            )
        if payload.enabled and payload.delivery_channel == "telegram" and not payload.telegram_target.strip():
            raise OpenClawServiceError(
                "啟用 Daily News Brief 前，必須填寫 Telegram 目標。",
                detail="delivery_channel=telegram 時 telegram_target 必填。",
                status_code=400,
                source_mode=self.source_mode,
            )
        if payload.enabled and payload.delivery_channel == "discord" and not payload.discord_channel_id.strip():
            raise OpenClawServiceError(
                "啟用 Daily News Brief 前，必須填寫 Discord 頻道 ID。",
                detail="delivery_channel=discord 時 discord_channel_id 必填。",
                status_code=400,
                source_mode=self.source_mode,
            )

        config = self.daily_news_repository.upsert(payload)
        self.operation_log_repository.create(
            instance_id=payload.instance_id,
            operation_type="configure_daily_news",
            target_type="daily_news_config",
            target_id=payload.instance_id,
            status="success",
            error_message=None,
            request_summary=payload.model_dump(),
            response_summary=config.model_dump(mode="json"),
            source_mode=self.source_mode,
        )
        try:
            self.cron_scheduling_service.reconcile_instance(payload.instance_id)
        except Exception as error:  # noqa: BLE001
            self.operation_log_repository.create(
                instance_id=payload.instance_id,
                operation_type="configure_daily_news_cron_reconcile",
                target_type="daily_news_config",
                target_id=payload.instance_id,
                status="failed",
                error_message=summarize_cron_reconcile_error(error),
                request_summary={"instance_id": payload.instance_id},
                response_summary=None,
                source_mode=self.source_mode,
            )
        return config, _elapsed_ms(started_at)


class OpenClawSystemInspectionConfigService:
    source_mode = "repository"

    def __init__(
        self,
        repository: Optional[OpenClawInstanceRepository] = None,
        system_inspection_repository: Optional[OpenClawSystemInspectionConfigRepository] = None,
        operation_log_repository: Optional[OpenClawOperationLogRepository] = None,
        cron_scheduling_service: Optional[OpenClawCronSchedulingService] = None,
    ) -> None:
        self.repository = repository or OpenClawInstanceRepository()
        self.system_inspection_repository = system_inspection_repository or OpenClawSystemInspectionConfigRepository()
        self.operation_log_repository = operation_log_repository or OpenClawOperationLogRepository()
        self.cron_scheduling_service = cron_scheduling_service or OpenClawCronSchedulingService(
            repository=self.repository,
            system_inspection_repository=self.system_inspection_repository,
            operation_log_repository=self.operation_log_repository,
        )

    def get_config(self, instance_id: str) -> tuple[OpenClawSystemInspectionConfigResponse, int]:
        started_at = time.perf_counter()
        self.repository.get(instance_id)
        try:
            return self.system_inspection_repository.get(instance_id), _elapsed_ms(started_at)
        except KeyError as error:
            raise OpenClawServiceError(
                "尚未設定系統巡檢與風險評估。",
                detail=str(error),
                status_code=404,
                source_mode=self.source_mode,
            ) from error

    def update_config(self, payload: OpenClawSystemInspectionConfigRequest) -> tuple[OpenClawSystemInspectionConfigResponse, int]:
        started_at = time.perf_counter()
        self.repository.get(payload.instance_id)
        if payload.enabled and payload.delivery_channel == "discord" and not payload.discord_channel_id.strip():
            raise OpenClawServiceError(
                "啟用系統巡檢 Discord 推送前，必須填寫 Discord 頻道 ID。",
                detail="delivery_channel=discord 時 discord_channel_id 必填。",
                status_code=400,
                source_mode=self.source_mode,
            )
        config = self.system_inspection_repository.upsert(payload)
        self.operation_log_repository.create(
            instance_id=payload.instance_id,
            operation_type="configure_system_inspection",
            target_type="system_inspection_config",
            target_id=payload.instance_id,
            status="success",
            error_message=None,
            request_summary=payload.model_dump(),
            response_summary=config.model_dump(mode="json"),
            source_mode=self.source_mode,
        )
        try:
            self.cron_scheduling_service.reconcile_instance(payload.instance_id)
        except Exception as error:  # noqa: BLE001
            self.operation_log_repository.create(
                instance_id=payload.instance_id,
                operation_type="configure_system_inspection_cron_reconcile",
                target_type="system_inspection_config",
                target_id=payload.instance_id,
                status="failed",
                error_message=summarize_cron_reconcile_error(error),
                request_summary={"instance_id": payload.instance_id},
                response_summary=None,
                source_mode=self.source_mode,
        )
        return config, _elapsed_ms(started_at)


class OpenClawDevelopmentConfigService:
    source_mode = "repository"

    def __init__(
        self,
        repository: Optional[OpenClawInstanceRepository] = None,
        development_repository: Optional[OpenClawDevelopmentConfigRepository] = None,
        operation_log_repository: Optional[OpenClawOperationLogRepository] = None,
    ) -> None:
        self.repository = repository or OpenClawInstanceRepository()
        self.development_repository = development_repository or OpenClawDevelopmentConfigRepository()
        self.operation_log_repository = operation_log_repository or OpenClawOperationLogRepository()

    def get_config(self, instance_id: str) -> tuple[OpenClawDevelopmentConfigResponse, int]:
        started_at = time.perf_counter()
        self.repository.get(instance_id)
        try:
            stored_config = self.development_repository.get(instance_id)
        except KeyError:
            stored_config = None
        return _enrich_development_config_response(instance_id, stored_config), _elapsed_ms(started_at)

    def update_config(self, payload: OpenClawDevelopmentConfigRequest) -> tuple[OpenClawDevelopmentConfigResponse, int]:
        started_at = time.perf_counter()
        self.repository.get(payload.instance_id)
        if payload.enabled and not payload.discord_channel_id.strip():
            raise OpenClawServiceError(
                "啟用 Development Discord 匯報前，必須填寫 Discord 頻道 ID。",
                detail="delivery_channel=discord 時 discord_channel_id 必填。",
                status_code=400,
                source_mode=self.source_mode,
            )

        config = _enrich_development_config_response(payload.instance_id, self.development_repository.upsert(payload))
        self.operation_log_repository.create(
            instance_id=payload.instance_id,
            operation_type="configure_development_delivery",
            target_type="development_config",
            target_id=payload.instance_id,
            status="success",
            error_message=None,
            request_summary=payload.model_dump(),
            response_summary=config.model_dump(mode="json"),
            source_mode=self.source_mode,
        )
        return config, _elapsed_ms(started_at)


class SearchReportWorkflowService:
    # Workflow service 同時支援 search_report 與 web_search，兩者都共用 run/stage/event persistence。
    source_mode = "workflow"

    def __init__(
        self,
        repository: Optional[OpenClawInstanceRepository] = None,
        workflow_repository: Optional[WorkflowRepository] = None,
        workflow_config_repository: Optional[OpenClawWorkflowConfigRepository] = None,
        daily_news_repository: Optional[OpenClawDailyNewsConfigRepository] = None,
        development_repository: Optional[OpenClawDevelopmentConfigRepository] = None,
        system_inspection_repository: Optional[OpenClawSystemInspectionConfigRepository] = None,
        capability_repository: Optional[OpenClawAgentCapabilityRepository] = None,
        operation_log_repository: Optional[OpenClawOperationLogRepository] = None,
        knowledge_ingestion_service: Optional[KnowledgeIngestionService] = None,
        hook_client: Optional[OpenClawHookClient] = None,
        telegram_delivery_client: Optional[TelegramDeliveryClient] = None,
        discord_delivery_client: Optional[DiscordDeliveryClient] = None,
        development_discord_delivery_client: Optional[DiscordDeliveryClient] = None,
        system_inspection_telegram_delivery_client: Optional[TelegramDeliveryClient] = None,
        system_inspection_discord_delivery_client: Optional[DiscordDeliveryClient] = None,
        cli_adapter: Optional[OpenClawCliAdapter] = None,
        release_client: Optional[OpenClawReleaseClient] = None,
        secret_cipher: Optional[OpenClawSecretCipher] = None,
        *,
        run_inline: bool = False,
    ) -> None:
        from app.config import get_settings

        settings = get_settings()
        self.repository = repository or OpenClawInstanceRepository()
        self.workflow_repository = workflow_repository or WorkflowRepository()
        self.workflow_config_repository = workflow_config_repository or OpenClawWorkflowConfigRepository()
        self.daily_news_repository = daily_news_repository or OpenClawDailyNewsConfigRepository()
        self.development_repository = development_repository or OpenClawDevelopmentConfigRepository()
        self.system_inspection_repository = system_inspection_repository or OpenClawSystemInspectionConfigRepository()
        self.capability_repository = capability_repository or OpenClawAgentCapabilityRepository()
        self.operation_log_repository = operation_log_repository or OpenClawOperationLogRepository()
        self.knowledge_ingestion_service = knowledge_ingestion_service or KnowledgeIngestionService()
        self.hook_client = hook_client or OpenClawHookClient()
        self.telegram_delivery_client = telegram_delivery_client or TelegramDeliveryClient.from_daily_news_settings()
        self.discord_delivery_client = discord_delivery_client or DiscordDeliveryClient.from_daily_news_settings()
        self.development_discord_delivery_client = (
            development_discord_delivery_client
            or (discord_delivery_client if discord_delivery_client is not None else DiscordDeliveryClient.from_development_settings())
        )
        self.system_inspection_telegram_delivery_client = (
            system_inspection_telegram_delivery_client
            or (telegram_delivery_client if telegram_delivery_client is not None else TelegramDeliveryClient.from_system_inspection_settings())
        )
        self.system_inspection_discord_delivery_client = (
            system_inspection_discord_delivery_client
            or (discord_delivery_client if discord_delivery_client is not None else DiscordDeliveryClient.from_system_inspection_settings())
        )
        self.cli_adapter = cli_adapter or OpenClawCliAdapter()
        self.release_client = release_client or OpenClawReleaseClient()
        self.secret_cipher = secret_cipher or OpenClawSecretCipher(settings.openclaw_secret_key)
        self.news_agent_dispatch_timeout_seconds = settings.openclaw_news_agent_dispatch_timeout_seconds
        self.workflow_dispatch_retry_count = max(0, settings.openclaw_workflow_dispatch_retry_count)
        self.workflow_dispatch_retry_backoff_ms = max(0, settings.openclaw_workflow_dispatch_retry_backoff_ms)
        self.run_inline = run_inline

    def create_run(self, payload: WorkflowSearchReportCreateRequest) -> tuple[WorkflowRunResponse, int]:
        started_at = time.perf_counter()
        self._ensure_instance_exists(payload.instance_id)
        config = self._get_config_or_error(payload.instance_id)
        stage_agents = _resolve_search_report_stage_agents(config)

        run = self.workflow_repository.create_run(
            instance_id=payload.instance_id,
            workflow_type=WORKFLOW_TYPE_SEARCH_REPORT,
            input_payload={
                **payload.model_dump(),
                "controller_agent_id": config.controller_agent_id,
                "specialist_snapshot": _specialist_snapshot(config),
            },
            stage_configs=[
                {"stage_key": SEARCH_STAGE_KEY, "agent_id": stage_agents[SEARCH_STAGE_KEY]},
                {"stage_key": ANALYSIS_STAGE_KEY, "agent_id": stage_agents[ANALYSIS_STAGE_KEY]},
                {"stage_key": REPORT_STAGE_KEY, "agent_id": stage_agents[REPORT_STAGE_KEY]},
            ],
        )
        self.workflow_repository.add_event(
            run_id=run.id,
            stage_key=None,
            agent_id=config.controller_agent_id,
            status="pending",
            progress_percent=0,
            message="主控秘書已接手任務，正在建立搜索-分析-報告工作流。",
            payload={
                "query": payload.query,
                "source_id": payload.source_id,
                "controller_agent_id": config.controller_agent_id,
                "stage_agents": stage_agents,
            },
        )
        self._start_run(run.id)
        return self.workflow_repository.get_run(run.id), _elapsed_ms(started_at)

    def create_web_search_run(self, payload: WorkflowWebSearchCreateRequest) -> tuple[WorkflowRunResponse, int]:
        started_at = time.perf_counter()
        self._ensure_instance_exists(payload.instance_id)
        config = self._get_config_or_error(payload.instance_id)
        stage_agents = _resolve_web_search_stage_agents(config)

        run = self.workflow_repository.create_run(
            instance_id=payload.instance_id,
            workflow_type=WORKFLOW_TYPE_WEB_SEARCH,
            input_payload={
                **payload.model_dump(),
                "controller_agent_id": config.controller_agent_id,
                "specialist_snapshot": _specialist_snapshot(config),
            },
            stage_configs=[
                {"stage_key": UNDERSTAND_STAGE_KEY, "agent_id": stage_agents[UNDERSTAND_STAGE_KEY]},
                {"stage_key": SEARCH_STAGE_KEY, "agent_id": stage_agents[SEARCH_STAGE_KEY]},
                {"stage_key": FILTER_STAGE_KEY, "agent_id": stage_agents[FILTER_STAGE_KEY]},
                {"stage_key": INGEST_STAGE_KEY, "agent_id": stage_agents[INGEST_STAGE_KEY]},
                {"stage_key": FORMAT_STAGE_KEY, "agent_id": stage_agents[FORMAT_STAGE_KEY]},
            ],
        )
        self.workflow_repository.add_event(
            run_id=run.id,
            stage_key=None,
            agent_id=config.controller_agent_id,
            status="pending",
            progress_percent=0,
            message="主控秘書已接手任務，正在規劃 Web Search 專職路徑。",
            payload={
                "topic": payload.topic,
                "output_format": payload.output_format,
                "include_project_sources": payload.include_project_sources,
                "controller_agent_id": config.controller_agent_id,
                "stage_agents": stage_agents,
            },
        )
        self._start_run(run.id)
        return self.workflow_repository.get_run(run.id), _elapsed_ms(started_at)

    def create_news_brief_run(self, payload: WorkflowNewsBriefCreateRequest) -> tuple[WorkflowRunResponse, int]:
        started_at = time.perf_counter()
        self._ensure_instance_exists(payload.instance_id)
        config = self._get_config_or_error(payload.instance_id)
        daily_news_config = self._get_daily_news_config_or_error(payload.instance_id)
        stage_agents = _resolve_news_brief_stage_agents(config)
        scheduled_date = payload.scheduled_date or self._today_in_timezone(daily_news_config.schedule_timezone)

        if payload.trigger_source == "cron" and daily_news_config.last_scheduled_date == scheduled_date:
            raise OpenClawServiceError(
                "Daily News Brief 今日的自動排程已觸發過。",
                detail=f"scheduled_date={scheduled_date}",
                status_code=409,
                source_mode=self.source_mode,
            )

        run = self.workflow_repository.create_run(
            instance_id=payload.instance_id,
            workflow_type=WORKFLOW_TYPE_NEWS_BRIEF,
            input_payload={
                **payload.model_dump(),
                "daily_news_config": daily_news_config.model_dump(mode="json"),
                "controller_agent_id": config.controller_agent_id,
                "specialist_snapshot": _specialist_snapshot(config),
            },
            stage_configs=[
                {"stage_key": MONITOR_STAGE_KEY, "agent_id": stage_agents[MONITOR_STAGE_KEY]},
                {"stage_key": SEARCH_STAGE_KEY, "agent_id": stage_agents[SEARCH_STAGE_KEY]},
                {"stage_key": DEDUPE_STAGE_KEY, "agent_id": stage_agents[DEDUPE_STAGE_KEY]},
                {"stage_key": RANK_STAGE_KEY, "agent_id": stage_agents[RANK_STAGE_KEY]},
                {"stage_key": BRIEF_STAGE_KEY, "agent_id": stage_agents[BRIEF_STAGE_KEY]},
            ],
        )
        self.workflow_repository.add_event(
            run_id=run.id,
            stage_key=None,
            agent_id=config.controller_agent_id,
            status="pending",
            progress_percent=0,
            message="主控秘書已接手 Daily News Brief 任務，正在安排新聞監控與摘要流程。",
            payload={
                "brief_name": daily_news_config.brief_name,
                "topic": daily_news_config.topic,
                "controller_agent_id": config.controller_agent_id,
                "stage_agents": stage_agents,
                "trigger_source": payload.trigger_source,
                "scheduled_date": scheduled_date,
                "cron_job_id": payload.cron_job_id,
                "cron_job_name": payload.cron_job_name,
                "cron_run_id": payload.cron_run_id,
            },
        )
        if payload.trigger_source == "cron":
            self.daily_news_repository.mark_run(
                instance_id=payload.instance_id,
                scheduled_date=scheduled_date,
                run_id=run.id,
            )
            self.workflow_repository.add_event(
                run_id=run.id,
                stage_key=None,
                agent_id=config.controller_agent_id,
                status="pending",
                progress_percent=0,
                message="OpenClaw cron 已觸發 Daily News Brief，自動建立今日簡報流程。",
                payload={
                    "trigger_source": payload.trigger_source,
                    "scheduled_date": scheduled_date,
                    "cron_job_id": payload.cron_job_id,
                    "cron_job_name": payload.cron_job_name,
                    "cron_run_id": payload.cron_run_id,
                },
            )
        self._start_run(run.id)
        return self.workflow_repository.get_run(run.id), _elapsed_ms(started_at)

    def create_system_inspection_run(self, payload: WorkflowSystemInspectionCreateRequest) -> tuple[WorkflowRunResponse, int]:
        started_at = time.perf_counter()
        self._ensure_instance_exists(payload.instance_id)
        config = self._get_config_or_error(payload.instance_id)
        inspection_config = self._get_system_inspection_config_or_error(payload.instance_id)
        stage_agents = _resolve_system_inspection_stage_agents(config)
        scheduled_date = payload.scheduled_date or self._today_in_timezone(inspection_config.schedule_timezone)

        if payload.trigger_source == "cron" and inspection_config.last_scheduled_date == scheduled_date:
            raise OpenClawServiceError(
                "System Inspection 今日的自動排程已觸發過。",
                detail=f"scheduled_date={scheduled_date}",
                status_code=409,
                source_mode=self.source_mode,
            )

        run = self.workflow_repository.create_run(
            instance_id=payload.instance_id,
            workflow_type=WORKFLOW_TYPE_SYSTEM_INSPECTION,
            input_payload={
                **payload.model_dump(),
                "system_inspection_config": inspection_config.model_dump(mode="json"),
                "controller_agent_id": config.controller_agent_id,
                "specialist_snapshot": _specialist_snapshot(config),
            },
            stage_configs=[
                {"stage_key": SNAPSHOT_STAGE_KEY, "agent_id": stage_agents[SNAPSHOT_STAGE_KEY]},
                {"stage_key": VERSION_CHECK_STAGE_KEY, "agent_id": stage_agents[VERSION_CHECK_STAGE_KEY]},
                {"stage_key": LOG_REVIEW_STAGE_KEY, "agent_id": stage_agents[LOG_REVIEW_STAGE_KEY]},
                {"stage_key": RISK_ASSESSMENT_STAGE_KEY, "agent_id": stage_agents[RISK_ASSESSMENT_STAGE_KEY]},
                {"stage_key": REPORT_STAGE_KEY, "agent_id": stage_agents[REPORT_STAGE_KEY]},
            ],
        )
        self.workflow_repository.add_event(
            run_id=run.id,
            stage_key=None,
            agent_id=config.controller_agent_id,
            status="pending",
            progress_percent=0,
            message="主控秘書已建立系統巡檢與風險評估流程。",
            payload={
                "stage_agents": stage_agents,
                "schedule_time": inspection_config.schedule_time,
                "trigger_source": payload.trigger_source,
                "scheduled_date": scheduled_date,
                "cron_job_id": payload.cron_job_id,
                "cron_job_name": payload.cron_job_name,
                "cron_run_id": payload.cron_run_id,
            },
        )
        if payload.trigger_source == "cron":
            self.system_inspection_repository.mark_run(
                instance_id=payload.instance_id,
                scheduled_date=scheduled_date,
                run_id=run.id,
            )
            self.workflow_repository.add_event(
                run_id=run.id,
                stage_key=None,
                agent_id=config.controller_agent_id,
                status="pending",
                progress_percent=0,
                message="OpenClaw cron 已觸發 System Inspection，自動建立今日巡檢流程。",
                payload={
                    "trigger_source": payload.trigger_source,
                    "scheduled_date": scheduled_date,
                    "cron_job_id": payload.cron_job_id,
                    "cron_job_name": payload.cron_job_name,
                    "cron_run_id": payload.cron_run_id,
                },
            )
        self._start_run(run.id)
        return self.workflow_repository.get_run(run.id), _elapsed_ms(started_at)

    def create_development_execution_run(self, payload: WorkflowDevelopmentExecutionCreateRequest) -> tuple[WorkflowRunResponse, int]:
        started_at = time.perf_counter()
        self._ensure_instance_exists(payload.instance_id)
        config = self._get_config_or_error(payload.instance_id)
        stage_agents = _resolve_development_stage_agents(config)

        run = self.workflow_repository.create_run(
            instance_id=payload.instance_id,
            workflow_type=WORKFLOW_TYPE_DEVELOPMENT_EXECUTION,
            input_payload={
                **payload.model_dump(),
                "controller_agent_id": config.controller_agent_id,
                "specialist_snapshot": _specialist_snapshot(config),
            },
            stage_configs=[
                {"stage_key": PROBLEM_DEFINITION_STAGE_KEY, "agent_id": stage_agents[PROBLEM_DEFINITION_STAGE_KEY]},
                {"stage_key": REQUIREMENTS_ANALYSIS_STAGE_KEY, "agent_id": stage_agents[REQUIREMENTS_ANALYSIS_STAGE_KEY]},
                {"stage_key": SOLUTION_DESIGN_STAGE_KEY, "agent_id": stage_agents[SOLUTION_DESIGN_STAGE_KEY]},
                {"stage_key": TECHNOLOGY_SELECTION_STAGE_KEY, "agent_id": stage_agents[TECHNOLOGY_SELECTION_STAGE_KEY]},
                {"stage_key": TASK_PLANNING_STAGE_KEY, "agent_id": stage_agents[TASK_PLANNING_STAGE_KEY]},
                {"stage_key": IMPLEMENTATION_STAGE_KEY, "agent_id": stage_agents[IMPLEMENTATION_STAGE_KEY]},
                {"stage_key": TESTING_STAGE_KEY, "agent_id": stage_agents[TESTING_STAGE_KEY]},
                {"stage_key": OPTIMIZATION_STAGE_KEY, "agent_id": stage_agents[OPTIMIZATION_STAGE_KEY]},
                {"stage_key": HANDOFF_STAGE_KEY, "agent_id": stage_agents[HANDOFF_STAGE_KEY]},
            ],
        )
        self.workflow_repository.add_event(
            run_id=run.id,
            stage_key=None,
            agent_id=config.controller_agent_id,
            status="pending",
            progress_percent=0,
            message="主控秘書已建立 Development Workflow，正將工程任務派交全端工程師 Agent。",
            payload={"task_name": payload.task_name, "stage_agents": stage_agents},
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
        stage_agents = _resolve_search_report_stage_agents(config)
        continued_run = self.workflow_repository.create_run(
            instance_id=web_run.instance_id,
            workflow_type=WORKFLOW_TYPE_SEARCH_REPORT,
            input_payload={
                "instance_id": web_run.instance_id,
                "query": str(web_run.input_payload.get("topic") or ""),
                "source_id": web_run.input_payload.get("source_id"),
                "continued_from_run_id": web_run.id,
                "web_search_result": web_run.final_web_result.model_dump(),
                "controller_agent_id": config.controller_agent_id,
                "specialist_snapshot": _specialist_snapshot(config),
            },
            stage_configs=[
                {"stage_key": SEARCH_STAGE_KEY, "agent_id": stage_agents[SEARCH_STAGE_KEY]},
                {"stage_key": ANALYSIS_STAGE_KEY, "agent_id": stage_agents[ANALYSIS_STAGE_KEY]},
                {"stage_key": REPORT_STAGE_KEY, "agent_id": stage_agents[REPORT_STAGE_KEY]},
            ],
        )
        self.workflow_repository.add_event(
            run_id=continued_run.id,
            stage_key=None,
            agent_id=config.controller_agent_id,
            status="pending",
            progress_percent=0,
            message="主控秘書已建立分析/報告接續流程，將承接 Web Search 中間成果。",
            payload={"continued_from_run_id": web_run.id, "stage_agents": stage_agents},
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
            active_agent_id=stage_agents[SEARCH_STAGE_KEY],
            overall_progress_percent=SEARCH_REPORT_RUN_PROGRESS_DONE[SEARCH_STAGE_KEY],
            error_message=None,
        )
        self.workflow_repository.add_event(
            run_id=continued_run.id,
            stage_key=SEARCH_STAGE_KEY,
            agent_id=stage_agents[SEARCH_STAGE_KEY],
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
            elif run.workflow_type == WORKFLOW_TYPE_NEWS_BRIEF:
                self._execute_news_brief_run(run.id)
            elif run.workflow_type == WORKFLOW_TYPE_SYSTEM_INSPECTION:
                self._execute_system_inspection_run(run.id)
            elif run.workflow_type == WORKFLOW_TYPE_DEVELOPMENT_EXECUTION:
                self._execute_development_execution_run(run.id)
            else:
                self._execute_search_report_run(run.id)
        except OpenClawServiceError:
            raise

    def _execute_search_report_run(self, run_id: str) -> None:
        run = self.workflow_repository.get_run(run_id)
        config = self._get_config_or_error(run.instance_id)
        stage_agents = _resolve_search_report_stage_agents(config)

        try:
            self._add_controller_event(
                run_id=run.id,
                controller_agent_id=config.controller_agent_id,
                progress_percent=2,
                message="主控秘書已完成任務拆分，正在依序派工給搜索、分析、報告專職代理。",
                payload={"stage_agents": stage_agents},
            )
            search_stage = self._get_stage(run, SEARCH_STAGE_KEY)
            if search_stage.status == "completed" and isinstance(search_stage.output_payload, dict):
                search_output = WorkflowSearchStageOutput(**search_stage.output_payload)
            else:
                search_output = self._run_search_stage(run, stage_agents[SEARCH_STAGE_KEY])

            analysis_output = self._run_analysis_stage(self.workflow_repository.get_run(run.id), stage_agents[ANALYSIS_STAGE_KEY], search_output)
            report_output = self._run_report_stage(
                self.workflow_repository.get_run(run.id),
                stage_agents[REPORT_STAGE_KEY],
                search_output,
                analysis_output,
            )

            self.workflow_repository.update_run_status(
                run_id=run.id,
                status="completed",
                current_stage=REPORT_STAGE_KEY,
                active_agent_id=stage_agents[REPORT_STAGE_KEY],
                overall_progress_percent=100,
                final_payload=report_output.model_dump(),
                error_message=None,
            )
            self._add_controller_event(
                run_id=run.id,
                controller_agent_id=config.controller_agent_id,
                progress_percent=100,
                message="主控秘書已完成結果整合，準備對外回報。",
                payload={"final_stage": REPORT_STAGE_KEY, "report_title": report_output.title},
            )
            self.workflow_repository.add_event(
                run_id=run.id,
                stage_key=REPORT_STAGE_KEY,
                agent_id=stage_agents[REPORT_STAGE_KEY],
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
        stage_agents = _resolve_web_search_stage_agents(config)

        try:
            self._add_controller_event(
                run_id=run.id,
                controller_agent_id=config.controller_agent_id,
                progress_percent=2,
                message="主控秘書已完成任務理解與分派，將由多專職代理接棒處理。",
                payload={"stage_agents": stage_agents},
            )
            understand_output = self._run_web_understand_stage(run, stage_agents[UNDERSTAND_STAGE_KEY])
            search_output = self._run_web_search_stage(self.workflow_repository.get_run(run.id), stage_agents[SEARCH_STAGE_KEY], understand_output)
            filter_output = self._run_web_filter_stage(self.workflow_repository.get_run(run.id), stage_agents[FILTER_STAGE_KEY], understand_output, search_output)
            ingest_output = self._run_web_ingest_stage(
                self.workflow_repository.get_run(run.id),
                stage_agents[INGEST_STAGE_KEY],
                understand_output,
                filter_output,
            )
            formatted_output = self._run_web_format_stage(
                self.workflow_repository.get_run(run.id),
                stage_agents[FORMAT_STAGE_KEY],
                understand_output,
                filter_output,
                ingest_output,
            )

            self.workflow_repository.update_run_status(
                run_id=run.id,
                status="completed",
                current_stage=FORMAT_STAGE_KEY,
                active_agent_id=stage_agents[FORMAT_STAGE_KEY],
                overall_progress_percent=100,
                final_payload=formatted_output.model_dump(),
                error_message=None,
            )
            self._add_controller_event(
                run_id=run.id,
                controller_agent_id=config.controller_agent_id,
                progress_percent=100,
                message="主控秘書已整合 Web Search 結果，等待使用者回看或接續分析/報告。",
                payload={"final_stage": FORMAT_STAGE_KEY, "title": formatted_output.title},
            )
            self.workflow_repository.add_event(
                run_id=run.id,
                stage_key=FORMAT_STAGE_KEY,
                agent_id=stage_agents[FORMAT_STAGE_KEY],
                status="completed",
                progress_percent=100,
                message="Web Search 已完成，可直接回看整理結果，或送入分析/報告流程。",
                payload={"title": formatted_output.title, "source_count": len(formatted_output.included_sources)},
            )
        except OpenClawServiceError as error:
            self._mark_run_failed(run.id, error)

    def _execute_news_brief_run(self, run_id: str) -> None:
        run = self.workflow_repository.get_run(run_id)
        config = self._get_config_or_error(run.instance_id)
        daily_news_config = self._get_daily_news_config_or_error(run.instance_id)
        stage_agents = _resolve_news_brief_stage_agents(config)

        try:
            self._add_controller_event(
                run_id=run.id,
                controller_agent_id=config.controller_agent_id,
                progress_percent=2,
                message="主控秘書已建立每日新聞簡報流程，正在派工給新聞專職代理。",
                payload={"stage_agents": stage_agents, "brief_name": daily_news_config.brief_name},
            )
            monitor_output = self._run_news_monitor_stage(run, stage_agents[MONITOR_STAGE_KEY], daily_news_config)
            search_output = self._run_news_search_stage(self.workflow_repository.get_run(run.id), stage_agents[SEARCH_STAGE_KEY], daily_news_config, monitor_output)
            dedupe_output = self._run_news_dedupe_stage(self.workflow_repository.get_run(run.id), stage_agents[DEDUPE_STAGE_KEY], daily_news_config, search_output)
            rank_output = self._run_news_rank_stage(self.workflow_repository.get_run(run.id), stage_agents[RANK_STAGE_KEY], daily_news_config, dedupe_output)
            brief_output = self._run_news_brief_stage(
                self.workflow_repository.get_run(run.id),
                stage_agents[BRIEF_STAGE_KEY],
                daily_news_config,
                search_output,
                dedupe_output,
                rank_output,
            )

            delivery_status = "skipped"
            delivery_error = None
            delivery_target = None
            if self._has_delivery_target(
                delivery_channel=daily_news_config.delivery_channel,
                telegram_target=daily_news_config.telegram_target,
                discord_channel_id=daily_news_config.discord_channel_id,
            ):
                delivery_target = self._delivery_target_value(
                    delivery_channel=daily_news_config.delivery_channel,
                    telegram_target=daily_news_config.telegram_target,
                    discord_channel_id=daily_news_config.discord_channel_id,
                )
                try:
                    self._deliver_news_brief(
                        instance_id=run.instance_id,
                        delivery_channel=daily_news_config.delivery_channel,
                        delivery_target=delivery_target,
                        brief_payload=brief_output,
                        run_id=run.id,
                    )
                    delivery_status = "delivered"
                except OpenClawServiceError as error:
                    delivery_status = "failed"
                    delivery_error = error.detail or error.message
                    self.workflow_repository.add_event(
                        run_id=run.id,
                        stage_key=BRIEF_STAGE_KEY,
                        agent_id=config.controller_agent_id,
                        status="failed",
                        progress_percent=100,
                        message=f"Daily News Brief 已生成，但 {self._delivery_channel_label(daily_news_config.delivery_channel)} 推送失敗。",
                        payload={"error": delivery_error},
                    )

            final_payload = brief_output.model_copy(
                update={
                    "delivery_status": delivery_status,
                    "delivery_target": delivery_target,
                    "delivery_error": delivery_error,
                }
            )
            self.workflow_repository.update_run_status(
                run_id=run.id,
                status="completed",
                current_stage=BRIEF_STAGE_KEY,
                active_agent_id=stage_agents[BRIEF_STAGE_KEY],
                overall_progress_percent=100,
                final_payload=final_payload.model_dump(),
                error_message=None,
            )
            self.daily_news_repository.mark_run(
                instance_id=run.instance_id,
                scheduled_date=self._scheduled_date_for_run(run, daily_news_config.schedule_timezone),
                run_id=run.id,
                delivery_status=delivery_status,
                delivery_error=delivery_error,
            )
            self._add_controller_event(
                run_id=run.id,
                controller_agent_id=config.controller_agent_id,
                progress_percent=100,
                message="主控秘書已完成每日新聞整合與推送處理。",
                payload={
                    "delivery_status": delivery_status,
                    "delivery_channel": daily_news_config.delivery_channel,
                    "delivery_target": delivery_target,
                },
            )
            self.workflow_repository.add_event(
                run_id=run.id,
                stage_key=BRIEF_STAGE_KEY,
                agent_id=stage_agents[BRIEF_STAGE_KEY],
                status="completed",
                progress_percent=100,
                message="每日新聞 Brief 已完成，可回看結果與投遞狀態。",
                payload={"top_story_count": len(final_payload.top_stories), "delivery_status": delivery_status},
            )
        except OpenClawServiceError as error:
            self._mark_run_failed(run.id, error)

    def _execute_system_inspection_run(self, run_id: str) -> None:
        run = self.workflow_repository.get_run(run_id)
        config = self._get_config_or_error(run.instance_id)
        inspection_config = self._get_system_inspection_config_or_error(run.instance_id)
        stage_agents = _resolve_system_inspection_stage_agents(config)

        try:
            self._add_controller_event(
                run_id=run.id,
                controller_agent_id=config.controller_agent_id,
                progress_percent=2,
                message="主控秘書已接手系統巡檢任務，正在收集版本、日誌與風險資料。",
                payload={"stage_agents": stage_agents},
            )
            snapshot_output = self._run_system_snapshot_stage(run, stage_agents[SNAPSHOT_STAGE_KEY], config)
            version_output = self._run_system_version_check_stage(self.workflow_repository.get_run(run.id), stage_agents[VERSION_CHECK_STAGE_KEY], inspection_config, snapshot_output)
            log_review_output = self._run_system_log_review_stage(self.workflow_repository.get_run(run.id), stage_agents[LOG_REVIEW_STAGE_KEY], inspection_config, snapshot_output)
            risk_output = self._run_system_risk_assessment_stage(
                self.workflow_repository.get_run(run.id),
                stage_agents[RISK_ASSESSMENT_STAGE_KEY],
                inspection_config,
                version_output,
                log_review_output,
            )
            report_output = self._run_system_report_stage(
                self.workflow_repository.get_run(run.id),
                stage_agents[REPORT_STAGE_KEY],
                inspection_config,
                version_output,
                log_review_output,
                risk_output,
            )

            delivery_status = "skipped"
            delivery_error = None
            delivery_target = None
            if self._has_delivery_target(
                delivery_channel=inspection_config.delivery_channel,
                telegram_target=inspection_config.telegram_target,
                discord_channel_id=inspection_config.discord_channel_id,
            ):
                delivery_target = self._delivery_target_value(
                    delivery_channel=inspection_config.delivery_channel,
                    telegram_target=inspection_config.telegram_target,
                    discord_channel_id=inspection_config.discord_channel_id,
                )
                try:
                    self._deliver_system_inspection_summary(
                        instance_id=run.instance_id,
                        delivery_channel=inspection_config.delivery_channel,
                        delivery_target=delivery_target,
                        report_payload=report_output,
                        run_id=run.id,
                    )
                    delivery_status = "delivered"
                except OpenClawServiceError as error:
                    delivery_status = "failed"
                    delivery_error = error.detail or error.message

            repair_workflow_created = False
            repair_workflow_run_id = None
            repair_workflow_reason = None
            if self._should_create_system_inspection_repair_workflow(report_output):
                try:
                    repair_request = self._build_system_inspection_repair_request(
                        run=run,
                        inspection_config=inspection_config,
                        report_output=report_output,
                    )
                    repair_run, _ = self.create_development_execution_run(repair_request)
                    repair_workflow_created = True
                    repair_workflow_run_id = repair_run.id
                except OpenClawServiceError as error:
                    repair_workflow_reason = f"主控秘書已整理巡檢修復項，但建立 Development Workflow 失敗：{error.detail or error.message}"
            else:
                repair_workflow_reason = "本次巡檢無可執行修復項，因此未建立工程流程。"

            final_payload = report_output.model_copy(
                update={
                    "delivery_status": delivery_status,
                    "delivery_target": delivery_target,
                    "delivery_error": delivery_error,
                    "repair_workflow_created": repair_workflow_created,
                    "repair_workflow_run_id": repair_workflow_run_id,
                    "repair_workflow_reason": repair_workflow_reason,
                }
            )
            self.workflow_repository.update_run_status(
                run_id=run.id,
                status="completed",
                current_stage=REPORT_STAGE_KEY,
                active_agent_id=stage_agents[REPORT_STAGE_KEY],
                overall_progress_percent=100,
                final_payload=final_payload.model_dump(),
                error_message=None,
            )
            self.system_inspection_repository.mark_run(
                instance_id=run.instance_id,
                scheduled_date=self._scheduled_date_for_run(run, inspection_config.schedule_timezone),
                run_id=run.id,
                delivery_status=delivery_status,
                delivery_error=delivery_error,
            )
            completion_message = "主控秘書已完成系統巡檢整合與風險建議整理。"
            if repair_workflow_created and repair_workflow_run_id:
                completion_message = "主控秘書已將巡檢修復項交給 Fullstack Engineer Agent，並建立 Development Workflow。"
            elif repair_workflow_reason and "未建立工程流程" in repair_workflow_reason:
                completion_message = "主控秘書已完成系統巡檢整合與風險建議整理，本次無需建立 Development Workflow。"
            elif repair_workflow_reason:
                completion_message = "主控秘書已完成系統巡檢整合與風險建議整理，但自動交辦 Development Workflow 失敗。"
            self._add_controller_event(
                run_id=run.id,
                controller_agent_id=config.controller_agent_id,
                progress_percent=100,
                message=completion_message,
                payload={
                    "upgrade_recommendation": report_output.version_update_check.upgrade_recommendation,
                    "delivery_status": delivery_status,
                    "repair_workflow_created": repair_workflow_created,
                    "repair_workflow_run_id": repair_workflow_run_id,
                    "repair_workflow_reason": repair_workflow_reason,
                },
                status="completed",
            )
        except OpenClawServiceError as error:
            self._mark_run_failed(run.id, error)

    def _should_create_system_inspection_repair_workflow(
        self,
        report_output: WorkflowSystemInspectionReportPayload,
    ) -> bool:
        return bool(_dedupe_non_empty_strings(report_output.fix_and_optimization_actions)) or bool(report_output.high_priority_risks)

    def _build_system_inspection_repair_request(
        self,
        *,
        run: WorkflowRunResponse,
        inspection_config: OpenClawSystemInspectionConfigResponse,
        report_output: WorkflowSystemInspectionReportPayload,
    ) -> WorkflowDevelopmentExecutionCreateRequest:
        scheduled_date = self._scheduled_date_for_run(run, inspection_config.schedule_timezone)
        instance = self.repository.get(run.instance_id)
        task_name_parts = ["修復 System Inspection 發現問題"]
        if instance.name.strip():
            task_name_parts.append(instance.name.strip())
        task_name_parts.append(scheduled_date or run.created_at.strftime("%Y-%m-%d"))

        problem_background_parts = [
            f"巡檢摘要：{'；'.join(_dedupe_non_empty_strings(report_output.inspection_summary)[:3])}",
            f"版本差異：{report_output.version_update_check.version_gap}",
            f"日誌觀察：{report_output.log_review.summary}",
        ]
        if report_output.high_priority_risks:
            risk_summary = "；".join(
                truncate_text(issue.description, max_length=120) for issue in report_output.high_priority_risks[:3]
            )
            problem_background_parts.append(f"高優先風險：{risk_summary}")

        success_criteria = _dedupe_non_empty_strings(
            [
                *report_output.fix_and_optimization_actions,
                *[action for issue in report_output.high_priority_risks for action in issue.fix_actions],
                *report_output.version_update_check.regression_test_checklist,
            ]
        )
        if not success_criteria:
            success_criteria = ["完成本次巡檢列出的修復、驗證與交接。"]

        context_payload = {
            "system_inspection_run_id": run.id,
            "trigger_source": run.input_payload.get("trigger_source"),
            "version_update_check": _compact_system_version_output(report_output.version_update_check),
            "log_review": _compact_system_log_review_output(report_output.log_review),
            "high_priority_risks": [_compact_system_issue(issue) for issue in report_output.high_priority_risks[:5]],
            "recommended_execution_order": report_output.recommended_execution_order[:6],
        }

        return WorkflowDevelopmentExecutionCreateRequest(
            instance_id=run.instance_id,
            task_name=" - ".join(task_name_parts),
            problem_background="\n".join(part for part in problem_background_parts if part.strip()),
            goal="根據系統巡檢結果完成修復、驗證與交接。",
            trigger_source="system_inspection_handoff",
            continued_from_run_id=run.id,
            origin_workflow_type="system_inspection",
            constraints=[
                "沿用現有系統與部署方式",
                "避免破壞現有 workflow / channel delivery",
                "若涉及升級需先驗證相容性",
            ],
            success_criteria=success_criteria,
            context=json.dumps(context_payload, ensure_ascii=False),
            attachments=[],
            references=[f"workflow_run:{run.id}", f"system_inspection_report:{run.id}"],
        )

    def _execute_development_execution_run(self, run_id: str) -> None:
        run = self.workflow_repository.get_run(run_id)
        config = self._get_config_or_error(run.instance_id)
        stage_agents = _resolve_development_stage_agents(config)

        try:
            self._add_controller_event(
                run_id=run.id,
                controller_agent_id=config.controller_agent_id,
                progress_percent=2,
                message="主控秘書已接手工程任務，要求全端工程師 Agent 依序完成分析、設計、排期、開發與測試。",
                payload={"task_name": run.input_payload.get("task_name"), "stage_agents": stage_agents},
            )
            problem_output = self._run_development_problem_definition_stage(run, stage_agents[PROBLEM_DEFINITION_STAGE_KEY])
            requirements_output = self._run_development_requirements_stage(
                self.workflow_repository.get_run(run.id),
                stage_agents[REQUIREMENTS_ANALYSIS_STAGE_KEY],
                problem_output,
            )
            design_output = self._run_development_design_stage(
                self.workflow_repository.get_run(run.id),
                stage_agents[SOLUTION_DESIGN_STAGE_KEY],
                problem_output,
                requirements_output,
            )
            technology_output = self._run_development_technology_stage(
                self.workflow_repository.get_run(run.id),
                stage_agents[TECHNOLOGY_SELECTION_STAGE_KEY],
                problem_output,
                requirements_output,
                design_output,
            )
            planning_output = self._run_development_task_planning_stage(
                self.workflow_repository.get_run(run.id),
                stage_agents[TASK_PLANNING_STAGE_KEY],
                problem_output,
                requirements_output,
                design_output,
                technology_output,
            )
            implementation_output = self._run_development_implementation_stage(
                self.workflow_repository.get_run(run.id),
                stage_agents[IMPLEMENTATION_STAGE_KEY],
                problem_output,
                design_output,
                planning_output,
            )
            testing_output = self._run_development_testing_stage(
                self.workflow_repository.get_run(run.id),
                stage_agents[TESTING_STAGE_KEY],
                problem_output,
                planning_output,
                implementation_output,
            )
            optimization_output = self._run_development_optimization_stage(
                self.workflow_repository.get_run(run.id),
                stage_agents[OPTIMIZATION_STAGE_KEY],
                planning_output,
                implementation_output,
                testing_output,
            )
            handoff_output = self._run_development_handoff_stage(
                self.workflow_repository.get_run(run.id),
                stage_agents[HANDOFF_STAGE_KEY],
                problem_output,
                requirements_output,
                design_output,
                technology_output,
                planning_output,
                implementation_output,
                testing_output,
                optimization_output,
            )
            delivery_status = "skipped"
            delivery_target = None
            delivery_error = None
            delivery_source = "none"
            delivery_reason = None
            delivery_resolution = self._resolve_development_delivery_target(run.instance_id)
            delivery_target = delivery_resolution["target"]
            delivery_source = delivery_resolution["source"]
            delivery_reason = delivery_resolution["reason"]
            if delivery_target:
                try:
                    self._deliver_development_report(
                        instance_id=run.instance_id,
                        delivery_target=delivery_target,
                        text=_build_development_delivery_markdown(run=run, report_payload=handoff_output),
                        run_id=run.id,
                    )
                    delivery_status = "delivered"
                    self.workflow_repository.add_event(
                        run_id=run.id,
                        stage_key=HANDOFF_STAGE_KEY,
                        agent_id=config.controller_agent_id,
                        status="completed",
                        progress_percent=100,
                        message="Development 匯報已推送到 Discord。",
                        payload={
                            "delivery_status": delivery_status,
                            "delivery_target": delivery_target,
                            "delivery_source": delivery_source,
                            "delivery_reason": delivery_reason,
                        },
                    )
                except OpenClawServiceError as report_delivery_error:
                    delivery_status = "failed"
                    delivery_error = report_delivery_error.detail or report_delivery_error.message
                    self.workflow_repository.add_event(
                        run_id=run.id,
                        stage_key=HANDOFF_STAGE_KEY,
                        agent_id=config.controller_agent_id,
                        status="failed",
                        progress_percent=100,
                        message="Development 已完成，但 Discord 匯報推送失敗。",
                        payload={
                            "delivery_status": delivery_status,
                            "delivery_target": delivery_target,
                            "delivery_error": delivery_error,
                            "delivery_source": delivery_source,
                            "delivery_reason": delivery_reason,
                        },
                    )
            else:
                self.workflow_repository.add_event(
                    run_id=run.id,
                    stage_key=HANDOFF_STAGE_KEY,
                    agent_id=config.controller_agent_id,
                    status="completed",
                    progress_percent=100,
                    message="Development 已完成，但未找到 Discord 匯報目標，已略過外部匯報。",
                    payload={
                        "delivery_status": delivery_status,
                        "delivery_target": delivery_target,
                        "delivery_source": delivery_source,
                        "delivery_reason": delivery_reason,
                    },
                )
            if delivery_resolution["config"] is not None:
                self.development_repository.mark_delivery(
                    instance_id=run.instance_id,
                    run_id=run.id,
                    delivery_status=delivery_status,
                    delivery_error=delivery_error,
                )
            handoff_output = handoff_output.model_copy(
                update={
                    "delivery_status": delivery_status,
                    "delivery_target": delivery_target,
                    "delivery_error": delivery_error,
                    "delivery_source": delivery_source,
                    "delivery_reason": delivery_reason,
                }
            )

            self.workflow_repository.update_run_status(
                run_id=run.id,
                status="completed",
                current_stage=HANDOFF_STAGE_KEY,
                active_agent_id=stage_agents[HANDOFF_STAGE_KEY],
                overall_progress_percent=100,
                final_payload=handoff_output.model_dump(),
                error_message=None,
            )
            self._add_controller_event(
                run_id=run.id,
                controller_agent_id=config.controller_agent_id,
                progress_percent=100,
                message="主控秘書已收到全端工程師 Agent 的結構化開發報告。",
                payload={
                    "task_name": handoff_output.task_name,
                    "final_summary": handoff_output.final_summary,
                    "delivery_status": handoff_output.delivery_status,
                    "delivery_target": handoff_output.delivery_target,
                },
            )
            self.workflow_repository.add_event(
                run_id=run.id,
                stage_key=HANDOFF_STAGE_KEY,
                agent_id=stage_agents[HANDOFF_STAGE_KEY],
                status="completed",
                progress_percent=100,
                message="工程任務已完成結構化匯報，可回看完整分析、設計、開發與測試結果。",
                payload={"task_name": handoff_output.task_name},
            )
        except OpenClawServiceError as error:
            self._mark_run_failed(run.id, error)
            self._deliver_failed_development_report(run_id=run.id, controller_agent_id=config.controller_agent_id)

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
        ingest_output: WorkflowWebSearchIngestOutput,
    ) -> WorkflowWebSearchResult:
        input_payload = {
            "understand_output": understand_output.model_dump(),
            "filter_output": filter_output.model_dump(),
            "ingest_output": ingest_output.model_dump(),
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
                message=_build_web_format_prompt(run.input_payload, understand_output, filter_output, ingest_output),
                metadata={"workflow_run_id": run.id, "stage_key": FORMAT_STAGE_KEY, "workflow_type": run.workflow_type},
            )
            result_output = _parse_agent_output(response_payload, WorkflowWebSearchResult, "Web Search 格式化階段")
            result_output = result_output.model_copy(
                update={
                    "ingestion_run_id": ingest_output.ingestion_run_id,
                    "ingest_result": ingest_output,
                }
            )
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

    def _run_web_ingest_stage(
        self,
        run: WorkflowRunResponse,
        agent_id: str,
        understand_output: WorkflowWebSearchUnderstandOutput,
        filter_output: WorkflowWebSearchFilterOutput,
    ) -> WorkflowWebSearchIngestOutput:
        kept_urls = [item.url for item in filter_output.kept_sources if item.url]
        if not kept_urls:
            ingest_output = WorkflowWebSearchIngestOutput(
                source_resolution="merged",
                ingest_summary="本次保留來源僅含既有專案內容或無可入庫 URL，因此未新增知識庫文件。",
                source_name=None,
            )
            self.workflow_repository.update_stage(
                run_id=run.id,
                stage_key=INGEST_STAGE_KEY,
                status="completed",
                progress_percent=100,
                output_payload=ingest_output.model_dump(),
                completed_at=utc_now_iso(),
            )
            self.workflow_repository.update_run_status(
                run_id=run.id,
                status="running",
                current_stage=INGEST_STAGE_KEY,
                active_agent_id=agent_id,
                overall_progress_percent=WEB_SEARCH_RUN_PROGRESS_DONE[INGEST_STAGE_KEY],
                error_message=None,
            )
            self.workflow_repository.add_event(
                run_id=run.id,
                stage_key=INGEST_STAGE_KEY,
                agent_id=agent_id,
                status="completed",
                progress_percent=WEB_SEARCH_RUN_PROGRESS_DONE[INGEST_STAGE_KEY],
                message="本次沒有新的外部來源需要入庫，已保留搜尋與過濾結果。",
                payload={"ingestion_run_id": None, "stored_count": 0, "updated_count": 0, "rejected_count": 0},
            )
            return ingest_output
        input_payload = {
            "topic": understand_output.normalized_topic,
            "kept_sources": [item.model_dump() for item in filter_output.kept_sources],
            "suggested_business_type": filter_output.suggested_business_type,
            "source_merge_hint": run.input_payload.get("source_merge_hint"),
        }
        self._mark_stage_running(
            run_id=run.id,
            stage_key=INGEST_STAGE_KEY,
            agent_id=agent_id,
            input_payload=input_payload,
            run_progress=WEB_SEARCH_RUN_PROGRESS_START[INGEST_STAGE_KEY],
            stage_progress=WEB_SEARCH_STAGE_RUNNING_PROGRESS[INGEST_STAGE_KEY],
            message="正在把高價值搜尋結果寫入知識庫...",
        )
        try:
            ingest_request = KnowledgeIngestRequest(
                topic=understand_output.normalized_topic,
                query=str(run.input_payload.get("topic") or understand_output.normalized_topic),
                source_id=None,
                source_name=(str(run.input_payload.get("source_merge_hint") or "").strip() or f"Web Search: {understand_output.normalized_topic}"),
                source_type="url_list" if len(kept_urls) > 1 else "web_page",
                urls=kept_urls,
                domains=list(dict.fromkeys([item.domain for item in filter_output.kept_sources if item.domain])),
                keywords=understand_output.keywords,
                must_include=understand_output.must_include,
                must_exclude=understand_output.must_exclude,
                business_type=(run.input_payload.get("business_type") or filter_output.suggested_business_type),
                limit=min(len(kept_urls), int(run.input_payload.get("result_limit") or 5)) or int(run.input_payload.get("result_limit") or 5),
                auto_publish=bool(run.input_payload.get("auto_publish", True)),
            )
            ingestion_run = self.knowledge_ingestion_service.ingest(ingest_request)
            metadata = ingestion_run.metadata or {}
            source_resolution = str(metadata.get("source_resolution") or "created")
            ingest_output = WorkflowWebSearchIngestOutput(
                source_resolution=source_resolution if source_resolution in {"explicit_source", "merged", "created"} else "created",
                created_source_id=metadata.get("created_source_id"),
                merged_source_id=metadata.get("merged_source_id"),
                ingestion_run_id=ingestion_run.id,
                stored_documents=[item.document_id for item in ingestion_run.items if item.status == "accepted" and item.document_id],
                updated_documents=[item.document_id for item in ingestion_run.items if item.status == "updated" and item.document_id],
                rejected_documents=[item.candidate_url for item in ingestion_run.items if item.status == "rejected"],
                ingest_summary=(
                    f"已將 {ingestion_run.accepted_count} 筆新文件、{ingestion_run.updated_count} 筆更新寫入知識庫，"
                    f"並拒收 {ingestion_run.rejected_count} 筆低價值來源。"
                ),
                source_name=ingestion_run.source_name,
            )
            self.workflow_repository.update_stage(
                run_id=run.id,
                stage_key=INGEST_STAGE_KEY,
                status="completed",
                progress_percent=100,
                output_payload=ingest_output.model_dump(),
                completed_at=utc_now_iso(),
            )
            self.workflow_repository.update_run_status(
                run_id=run.id,
                status="running",
                current_stage=INGEST_STAGE_KEY,
                active_agent_id=agent_id,
                overall_progress_percent=WEB_SEARCH_RUN_PROGRESS_DONE[INGEST_STAGE_KEY],
                error_message=None,
            )
            self.workflow_repository.add_event(
                run_id=run.id,
                stage_key=INGEST_STAGE_KEY,
                agent_id=agent_id,
                status="completed",
                progress_percent=WEB_SEARCH_RUN_PROGRESS_DONE[INGEST_STAGE_KEY],
                message="高價值 Web Search 來源已完成入庫與來源合併。",
                payload={
                    "ingestion_run_id": ingest_output.ingestion_run_id,
                    "source_resolution": ingest_output.source_resolution,
                    "stored_count": len(ingest_output.stored_documents),
                    "updated_count": len(ingest_output.updated_documents),
                    "rejected_count": len(ingest_output.rejected_documents),
                },
            )
            return ingest_output
        except OpenClawServiceError as error:
            self._mark_stage_failed(run_id=run.id, stage_key=INGEST_STAGE_KEY, agent_id=agent_id, error=error)
            raise

    def _run_news_monitor_stage(
        self,
        run: WorkflowRunResponse,
        agent_id: str,
        daily_news_config: OpenClawDailyNewsConfigResponse,
    ) -> WorkflowNewsMonitorOutput:
        input_payload = {"daily_news_config": daily_news_config.model_dump(mode="json")}
        self._mark_stage_running(
            run_id=run.id,
            stage_key=MONITOR_STAGE_KEY,
            agent_id=agent_id,
            input_payload=input_payload,
            run_progress=NEWS_BRIEF_RUN_PROGRESS_START[MONITOR_STAGE_KEY],
            stage_progress=NEWS_BRIEF_STAGE_RUNNING_PROGRESS[MONITOR_STAGE_KEY],
            message="正在確認今日新聞追蹤範圍...",
        )
        try:
            response_payload = self._dispatch_agent(
                instance_id=run.instance_id,
                agent_id=agent_id,
                session_key=f"{run.id}-{MONITOR_STAGE_KEY}",
                message=_build_news_monitor_prompt(daily_news_config),
                metadata={"workflow_run_id": run.id, "stage_key": MONITOR_STAGE_KEY, "workflow_type": run.workflow_type},
            )
            monitor_output = _parse_agent_output(response_payload, WorkflowNewsMonitorOutput, "Daily News 監控階段")
            self.workflow_repository.update_stage(
                run_id=run.id,
                stage_key=MONITOR_STAGE_KEY,
                status="completed",
                progress_percent=100,
                output_payload=monitor_output.model_dump(),
                completed_at=utc_now_iso(),
            )
            self.workflow_repository.update_run_status(
                run_id=run.id,
                status="running",
                current_stage=MONITOR_STAGE_KEY,
                active_agent_id=agent_id,
                overall_progress_percent=NEWS_BRIEF_RUN_PROGRESS_DONE[MONITOR_STAGE_KEY],
                error_message=None,
            )
            self.workflow_repository.add_event(
                run_id=run.id,
                stage_key=MONITOR_STAGE_KEY,
                agent_id=agent_id,
                status="completed",
                progress_percent=NEWS_BRIEF_RUN_PROGRESS_DONE[MONITOR_STAGE_KEY],
                message="已整理今日新聞追蹤範圍與搜尋策略。",
                payload={"search_queries": monitor_output.search_queries},
            )
            return monitor_output
        except OpenClawServiceError as error:
            self._mark_stage_failed(run_id=run.id, stage_key=MONITOR_STAGE_KEY, agent_id=agent_id, error=error)
            raise

    def _run_news_search_stage(
        self,
        run: WorkflowRunResponse,
        agent_id: str,
        daily_news_config: OpenClawDailyNewsConfigResponse,
        monitor_output: WorkflowNewsMonitorOutput,
    ) -> WorkflowNewsSearchOutput:
        input_payload = {"daily_news_config": daily_news_config.model_dump(mode="json"), "monitor_output": monitor_output.model_dump()}
        self._mark_stage_running(
            run_id=run.id,
            stage_key=SEARCH_STAGE_KEY,
            agent_id=agent_id,
            input_payload=input_payload,
            run_progress=NEWS_BRIEF_RUN_PROGRESS_START[SEARCH_STAGE_KEY],
            stage_progress=NEWS_BRIEF_STAGE_RUNNING_PROGRESS[SEARCH_STAGE_KEY],
            message="正在蒐集最新新聞...",
        )
        self.workflow_repository.add_event(
            run_id=run.id,
            stage_key=SEARCH_STAGE_KEY,
            agent_id=agent_id,
            status="running",
            progress_percent=35,
            message="正在擷取可信來源與最新報導...",
            payload={"queries": monitor_output.search_queries},
        )
        try:
            response_payload = self._dispatch_agent(
                instance_id=run.instance_id,
                agent_id=agent_id,
                session_key=f"{run.id}-{SEARCH_STAGE_KEY}",
                message=_build_news_search_prompt(daily_news_config, monitor_output),
                metadata={"workflow_run_id": run.id, "stage_key": SEARCH_STAGE_KEY, "workflow_type": run.workflow_type},
            )
            search_output = _parse_agent_output(response_payload, WorkflowNewsSearchOutput, "Daily News 搜尋階段")
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
                overall_progress_percent=NEWS_BRIEF_RUN_PROGRESS_DONE[SEARCH_STAGE_KEY],
                error_message=None,
            )
            self.workflow_repository.add_event(
                run_id=run.id,
                stage_key=SEARCH_STAGE_KEY,
                agent_id=agent_id,
                status="completed",
                progress_percent=NEWS_BRIEF_RUN_PROGRESS_DONE[SEARCH_STAGE_KEY],
                message="已取得候選新聞來源。",
                payload={"source_count": len(search_output.raw_sources)},
            )
            return search_output
        except OpenClawServiceError as error:
            self._mark_stage_failed(run_id=run.id, stage_key=SEARCH_STAGE_KEY, agent_id=agent_id, error=error)
            raise

    def _run_news_dedupe_stage(
        self,
        run: WorkflowRunResponse,
        agent_id: str,
        daily_news_config: OpenClawDailyNewsConfigResponse,
        search_output: WorkflowNewsSearchOutput,
    ) -> WorkflowNewsDedupeOutput:
        input_payload = {"daily_news_config": daily_news_config.model_dump(mode="json"), "search_output": search_output.model_dump()}
        self._mark_stage_running(
            run_id=run.id,
            stage_key=DEDUPE_STAGE_KEY,
            agent_id=agent_id,
            input_payload=input_payload,
            run_progress=NEWS_BRIEF_RUN_PROGRESS_START[DEDUPE_STAGE_KEY],
            stage_progress=NEWS_BRIEF_STAGE_RUNNING_PROGRESS[DEDUPE_STAGE_KEY],
            message="正在去重並合併相同事件...",
        )
        try:
            response_payload = self._dispatch_agent(
                instance_id=run.instance_id,
                agent_id=agent_id,
                session_key=f"{run.id}-{DEDUPE_STAGE_KEY}",
                message=_build_news_dedupe_prompt(daily_news_config, search_output),
                metadata={"workflow_run_id": run.id, "stage_key": DEDUPE_STAGE_KEY, "workflow_type": run.workflow_type},
            )
            dedupe_output = _parse_agent_output(response_payload, WorkflowNewsDedupeOutput, "Daily News 去重階段")
            self.workflow_repository.update_stage(
                run_id=run.id,
                stage_key=DEDUPE_STAGE_KEY,
                status="completed",
                progress_percent=100,
                output_payload=dedupe_output.model_dump(),
                completed_at=utc_now_iso(),
            )
            self.workflow_repository.update_run_status(
                run_id=run.id,
                status="running",
                current_stage=DEDUPE_STAGE_KEY,
                active_agent_id=agent_id,
                overall_progress_percent=NEWS_BRIEF_RUN_PROGRESS_DONE[DEDUPE_STAGE_KEY],
                error_message=None,
            )
            self.workflow_repository.add_event(
                run_id=run.id,
                stage_key=DEDUPE_STAGE_KEY,
                agent_id=agent_id,
                status="completed",
                progress_percent=NEWS_BRIEF_RUN_PROGRESS_DONE[DEDUPE_STAGE_KEY],
                message="已完成新聞去重與事件合併。",
                payload={"story_count": len(dedupe_output.unique_stories), "removed_duplicates": dedupe_output.removed_duplicates},
            )
            return dedupe_output
        except OpenClawServiceError as error:
            if _is_agent_timeout_error(error):
                dedupe_output = _fallback_news_dedupe_output(search_output)
                self.workflow_repository.update_stage(
                    run_id=run.id,
                    stage_key=DEDUPE_STAGE_KEY,
                    status="completed",
                    progress_percent=100,
                    output_payload=dedupe_output.model_dump(),
                    completed_at=utc_now_iso(),
                )
                self.workflow_repository.update_run_status(
                    run_id=run.id,
                    status="running",
                    current_stage=DEDUPE_STAGE_KEY,
                    active_agent_id=agent_id,
                    overall_progress_percent=NEWS_BRIEF_RUN_PROGRESS_DONE[DEDUPE_STAGE_KEY],
                    error_message=None,
                )
                self.workflow_repository.add_event(
                    run_id=run.id,
                    stage_key=DEDUPE_STAGE_KEY,
                    agent_id=agent_id,
                    status="completed",
                    progress_percent=NEWS_BRIEF_RUN_PROGRESS_DONE[DEDUPE_STAGE_KEY],
                    message="去重代理逾時，已改用本地規則完成新聞去重。",
                    payload={
                        "story_count": len(dedupe_output.unique_stories),
                        "removed_duplicates": dedupe_output.removed_duplicates,
                        "fallback_reason": error.detail or error.message,
                    },
                )
                return dedupe_output
            self._mark_stage_failed(run_id=run.id, stage_key=DEDUPE_STAGE_KEY, agent_id=agent_id, error=error)
            raise

    def _run_news_rank_stage(
        self,
        run: WorkflowRunResponse,
        agent_id: str,
        daily_news_config: OpenClawDailyNewsConfigResponse,
        dedupe_output: WorkflowNewsDedupeOutput,
    ) -> WorkflowNewsRankOutput:
        input_payload = {"daily_news_config": daily_news_config.model_dump(mode="json"), "dedupe_output": dedupe_output.model_dump()}
        self._mark_stage_running(
            run_id=run.id,
            stage_key=RANK_STAGE_KEY,
            agent_id=agent_id,
            input_payload=input_payload,
            run_progress=NEWS_BRIEF_RUN_PROGRESS_START[RANK_STAGE_KEY],
            stage_progress=NEWS_BRIEF_STAGE_RUNNING_PROGRESS[RANK_STAGE_KEY],
            message="正在依重要性排序新聞...",
        )
        try:
            response_payload = self._dispatch_agent(
                instance_id=run.instance_id,
                agent_id=agent_id,
                session_key=f"{run.id}-{RANK_STAGE_KEY}",
                message=_build_news_rank_prompt(daily_news_config, dedupe_output),
                metadata={"workflow_run_id": run.id, "stage_key": RANK_STAGE_KEY, "workflow_type": run.workflow_type},
            )
            rank_output = _parse_agent_output(response_payload, WorkflowNewsRankOutput, "Daily News 排序階段")
            self.workflow_repository.update_stage(
                run_id=run.id,
                stage_key=RANK_STAGE_KEY,
                status="completed",
                progress_percent=100,
                output_payload=rank_output.model_dump(),
                completed_at=utc_now_iso(),
            )
            self.workflow_repository.update_run_status(
                run_id=run.id,
                status="running",
                current_stage=RANK_STAGE_KEY,
                active_agent_id=agent_id,
                overall_progress_percent=NEWS_BRIEF_RUN_PROGRESS_DONE[RANK_STAGE_KEY],
                error_message=None,
            )
            self.workflow_repository.add_event(
                run_id=run.id,
                stage_key=RANK_STAGE_KEY,
                agent_id=agent_id,
                status="completed",
                progress_percent=NEWS_BRIEF_RUN_PROGRESS_DONE[RANK_STAGE_KEY],
                message="已完成重要新聞排序與焦點判斷。",
                payload={"top_count": len(rank_output.top_stories), "other_count": len(rank_output.other_stories)},
            )
            return rank_output
        except OpenClawServiceError as error:
            self._mark_stage_failed(run_id=run.id, stage_key=RANK_STAGE_KEY, agent_id=agent_id, error=error)
            raise

    def _run_news_brief_stage(
        self,
        run: WorkflowRunResponse,
        agent_id: str,
        daily_news_config: OpenClawDailyNewsConfigResponse,
        search_output: WorkflowNewsSearchOutput,
        dedupe_output: WorkflowNewsDedupeOutput,
        rank_output: WorkflowNewsRankOutput,
    ) -> WorkflowNewsBriefPayload:
        input_payload = {
            "daily_news_config": daily_news_config.model_dump(mode="json"),
            "search_output": search_output.model_dump(),
            "dedupe_output": dedupe_output.model_dump(),
            "rank_output": rank_output.model_dump(),
        }
        self._mark_stage_running(
            run_id=run.id,
            stage_key=BRIEF_STAGE_KEY,
            agent_id=agent_id,
            input_payload=input_payload,
            run_progress=NEWS_BRIEF_RUN_PROGRESS_START[BRIEF_STAGE_KEY],
            stage_progress=NEWS_BRIEF_STAGE_RUNNING_PROGRESS[BRIEF_STAGE_KEY],
            message="正在生成每日新聞簡報...",
        )
        try:
            response_payload = self._dispatch_agent(
                instance_id=run.instance_id,
                agent_id=agent_id,
                session_key=f"{run.id}-{BRIEF_STAGE_KEY}",
                message=_build_news_brief_prompt(daily_news_config, dedupe_output, rank_output),
                metadata={"workflow_run_id": run.id, "stage_key": BRIEF_STAGE_KEY, "workflow_type": run.workflow_type},
            )
            brief_output = _parse_agent_output(response_payload, WorkflowNewsBriefPayload, "Daily News 簡報階段")
            self.workflow_repository.update_stage(
                run_id=run.id,
                stage_key=BRIEF_STAGE_KEY,
                status="completed",
                progress_percent=100,
                output_payload=brief_output.model_dump(),
                completed_at=utc_now_iso(),
            )
            self.workflow_repository.update_run_status(
                run_id=run.id,
                status="running",
                current_stage=BRIEF_STAGE_KEY,
                active_agent_id=agent_id,
                overall_progress_percent=NEWS_BRIEF_RUN_PROGRESS_DONE[BRIEF_STAGE_KEY],
                final_payload=brief_output.model_dump(),
                error_message=None,
            )
            return brief_output
        except OpenClawServiceError as error:
            self._mark_stage_failed(run_id=run.id, stage_key=BRIEF_STAGE_KEY, agent_id=agent_id, error=error)
            raise

    def _run_development_structured_stage(
        self,
        *,
        run: WorkflowRunResponse,
        agent_id: str,
        stage_key: str,
        input_payload: dict[str, Any],
        message: str,
        prompt: str,
        schema,
        completion_message: str,
        completion_payload: dict[str, Any],
    ):
        self._mark_stage_running(
            run_id=run.id,
            stage_key=stage_key,
            agent_id=agent_id,
            input_payload=input_payload,
            run_progress=DEVELOPMENT_EXECUTION_RUN_PROGRESS_START[stage_key],
            stage_progress=DEVELOPMENT_EXECUTION_STAGE_RUNNING_PROGRESS[stage_key],
            message=message,
        )
        try:
            response_payload = self._dispatch_agent(
                instance_id=run.instance_id,
                agent_id=agent_id,
                session_key=f"{run.id}-{stage_key}",
                message=prompt,
                metadata={"workflow_run_id": run.id, "stage_key": stage_key, "workflow_type": run.workflow_type},
            )
            output = _parse_agent_output(response_payload, schema, f"Development {stage_key} 階段")
            self.workflow_repository.update_stage(
                run_id=run.id,
                stage_key=stage_key,
                status="completed",
                progress_percent=100,
                output_payload=output.model_dump(),
                completed_at=utc_now_iso(),
            )
            self.workflow_repository.update_run_status(
                run_id=run.id,
                status="running",
                current_stage=stage_key,
                active_agent_id=agent_id,
                overall_progress_percent=DEVELOPMENT_EXECUTION_RUN_PROGRESS_DONE[stage_key],
                error_message=None,
            )
            self.workflow_repository.add_event(
                run_id=run.id,
                stage_key=stage_key,
                agent_id=agent_id,
                status="completed",
                progress_percent=DEVELOPMENT_EXECUTION_RUN_PROGRESS_DONE[stage_key],
                message=completion_message,
                payload=completion_payload,
            )
            return output
        except OpenClawServiceError as error:
            self._mark_stage_failed(run_id=run.id, stage_key=stage_key, agent_id=agent_id, error=error)
            raise

    def _run_development_problem_definition_stage(
        self,
        run: WorkflowRunResponse,
        agent_id: str,
    ) -> WorkflowDevelopmentProblemDefinitionOutput:
        input_payload = {
            "task_name": run.input_payload.get("task_name"),
            "problem_background": run.input_payload.get("problem_background"),
            "goal": run.input_payload.get("goal"),
            "constraints": run.input_payload.get("constraints"),
            "success_criteria": run.input_payload.get("success_criteria"),
            "context": run.input_payload.get("context"),
            "attachments": run.input_payload.get("attachments"),
            "references": run.input_payload.get("references"),
        }
        return self._run_development_structured_stage(
            run=run,
            agent_id=agent_id,
            stage_key=PROBLEM_DEFINITION_STAGE_KEY,
            input_payload=input_payload,
            message="正在釐清問題背景、目標與成功標準...",
            prompt=_build_development_problem_definition_prompt(input_payload),
            schema=WorkflowDevelopmentProblemDefinitionOutput,
            completion_message="問題定義已完成，已明確任務背景、目標、限制與成功標準。",
            completion_payload={"task_name": input_payload.get("task_name")},
        )

    def _run_development_requirements_stage(
        self,
        run: WorkflowRunResponse,
        agent_id: str,
        problem_output: WorkflowDevelopmentProblemDefinitionOutput,
    ) -> WorkflowDevelopmentRequirementsOutput:
        input_payload = {"problem_definition": problem_output.model_dump()}
        return self._run_development_structured_stage(
            run=run,
            agent_id=agent_id,
            stage_key=REQUIREMENTS_ANALYSIS_STAGE_KEY,
            input_payload=input_payload,
            message="正在分析功能需求、非功能需求、風險與依賴項...",
            prompt=_build_development_requirements_prompt(problem_output),
            schema=WorkflowDevelopmentRequirementsOutput,
            completion_message="需求分析已完成，已整理功能、非功能需求、風險與依賴。",
            completion_payload={
                "functional_count": len(problem_output.success_criteria),
                "risk_count_hint": 0,
            },
        )

    def _run_development_design_stage(
        self,
        run: WorkflowRunResponse,
        agent_id: str,
        problem_output: WorkflowDevelopmentProblemDefinitionOutput,
        requirements_output: WorkflowDevelopmentRequirementsOutput,
    ) -> WorkflowDevelopmentDesignOutput:
        input_payload = {
            "problem_definition": problem_output.model_dump(),
            "requirements_analysis": requirements_output.model_dump(),
        }
        return self._run_development_structured_stage(
            run=run,
            agent_id=agent_id,
            stage_key=SOLUTION_DESIGN_STAGE_KEY,
            input_payload=input_payload,
            message="正在設計可落地的模組、流程、資料結構與介面...",
            prompt=_build_development_design_prompt(problem_output, requirements_output),
            schema=WorkflowDevelopmentDesignOutput,
            completion_message="方案設計已完成，已整理模組、流程與介面規劃。",
            completion_payload={"module_count": len(requirements_output.functional_requirements)},
        )

    def _run_development_technology_stage(
        self,
        run: WorkflowRunResponse,
        agent_id: str,
        problem_output: WorkflowDevelopmentProblemDefinitionOutput,
        requirements_output: WorkflowDevelopmentRequirementsOutput,
        design_output: WorkflowDevelopmentDesignOutput,
    ) -> WorkflowDevelopmentTechnologySelectionOutput:
        input_payload = {
            "problem_definition": problem_output.model_dump(),
            "requirements_analysis": requirements_output.model_dump(),
            "solution_design": design_output.model_dump(),
        }
        return self._run_development_structured_stage(
            run=run,
            agent_id=agent_id,
            stage_key=TECHNOLOGY_SELECTION_STAGE_KEY,
            input_payload=input_payload,
            message="正在完成技術選型與理由說明...",
            prompt=_build_development_technology_prompt(problem_output, requirements_output, design_output),
            schema=WorkflowDevelopmentTechnologySelectionOutput,
            completion_message="技術選型已完成，已說明採用方案與選擇理由。",
            completion_payload={"selection_count": len(design_output.modules)},
        )

    def _run_development_task_planning_stage(
        self,
        run: WorkflowRunResponse,
        agent_id: str,
        problem_output: WorkflowDevelopmentProblemDefinitionOutput,
        requirements_output: WorkflowDevelopmentRequirementsOutput,
        design_output: WorkflowDevelopmentDesignOutput,
        technology_output: WorkflowDevelopmentTechnologySelectionOutput,
    ) -> WorkflowDevelopmentTaskPlanningOutput:
        input_payload = {
            "problem_definition": problem_output.model_dump(),
            "requirements_analysis": requirements_output.model_dump(),
            "solution_design": design_output.model_dump(),
            "technology_selection": technology_output.model_dump(),
        }
        return self._run_development_structured_stage(
            run=run,
            agent_id=agent_id,
            stage_key=TASK_PLANNING_STAGE_KEY,
            input_payload=input_payload,
            message="正在拆分任務、安排優先級與預估排期...",
            prompt=_build_development_task_planning_prompt(problem_output, requirements_output, design_output, technology_output),
            schema=WorkflowDevelopmentTaskPlanningOutput,
            completion_message="任務拆分與排期已完成，已整理優先級與預估時程。",
            completion_payload={"task_count": len(technology_output.selections)},
        )

    def _run_development_implementation_stage(
        self,
        run: WorkflowRunResponse,
        agent_id: str,
        problem_output: WorkflowDevelopmentProblemDefinitionOutput,
        design_output: WorkflowDevelopmentDesignOutput,
        planning_output: WorkflowDevelopmentTaskPlanningOutput,
    ) -> WorkflowDevelopmentImplementationOutput:
        input_payload = {
            "problem_definition": problem_output.model_dump(),
            "solution_design": design_output.model_dump(),
            "task_planning": planning_output.model_dump(),
        }
        return self._run_development_structured_stage(
            run=run,
            agent_id=agent_id,
            stage_key=IMPLEMENTATION_STAGE_KEY,
            input_payload=input_payload,
            message="正在依照計畫執行開發實作...",
            prompt=_build_development_implementation_prompt(problem_output, design_output, planning_output),
            schema=WorkflowDevelopmentImplementationOutput,
            completion_message="開發實作階段已完成，已整理完成項目與變更模組。",
            completion_payload={"task_count": len(planning_output.tasks)},
        )

    def _run_development_testing_stage(
        self,
        run: WorkflowRunResponse,
        agent_id: str,
        problem_output: WorkflowDevelopmentProblemDefinitionOutput,
        planning_output: WorkflowDevelopmentTaskPlanningOutput,
        implementation_output: WorkflowDevelopmentImplementationOutput,
    ) -> WorkflowDevelopmentTestingOutput:
        input_payload = {
            "problem_definition": problem_output.model_dump(),
            "task_planning": planning_output.model_dump(),
            "implementation": implementation_output.model_dump(),
        }
        return self._run_development_structured_stage(
            run=run,
            agent_id=agent_id,
            stage_key=TESTING_STAGE_KEY,
            input_payload=input_payload,
            message="正在持續測試與驗證開發成果...",
            prompt=_build_development_testing_prompt(problem_output, planning_output, implementation_output),
            schema=WorkflowDevelopmentTestingOutput,
            completion_message="測試與驗證已完成，已整理測試結果與剩餘缺口。",
            completion_payload={"completed_items": len(implementation_output.completed_items)},
        )

    def _run_development_optimization_stage(
        self,
        run: WorkflowRunResponse,
        agent_id: str,
        planning_output: WorkflowDevelopmentTaskPlanningOutput,
        implementation_output: WorkflowDevelopmentImplementationOutput,
        testing_output: WorkflowDevelopmentTestingOutput,
    ) -> WorkflowDevelopmentOptimizationOutput:
        input_payload = {
            "task_planning": planning_output.model_dump(),
            "implementation": implementation_output.model_dump(),
            "testing": testing_output.model_dump(),
        }
        return self._run_development_structured_stage(
            run=run,
            agent_id=agent_id,
            stage_key=OPTIMIZATION_STAGE_KEY,
            input_payload=input_payload,
            message="正在根據測試結果與回饋持續優化...",
            prompt=_build_development_optimization_prompt(planning_output, implementation_output, testing_output),
            schema=WorkflowDevelopmentOptimizationOutput,
            completion_message="優化階段已完成，已整理改進方向、風險與待辦。",
            completion_payload={"improvement_count": len(testing_output.test_results)},
        )

    def _run_development_handoff_stage(
        self,
        run: WorkflowRunResponse,
        agent_id: str,
        problem_output: WorkflowDevelopmentProblemDefinitionOutput,
        requirements_output: WorkflowDevelopmentRequirementsOutput,
        design_output: WorkflowDevelopmentDesignOutput,
        technology_output: WorkflowDevelopmentTechnologySelectionOutput,
        planning_output: WorkflowDevelopmentTaskPlanningOutput,
        implementation_output: WorkflowDevelopmentImplementationOutput,
        testing_output: WorkflowDevelopmentTestingOutput,
        optimization_output: WorkflowDevelopmentOptimizationOutput,
    ) -> WorkflowDevelopmentExecutionReportPayload:
        input_payload = {
            "problem_definition": problem_output.model_dump(),
            "requirements_analysis": requirements_output.model_dump(),
            "solution_design": design_output.model_dump(),
            "technology_selection": technology_output.model_dump(),
            "task_planning": planning_output.model_dump(),
            "implementation": implementation_output.model_dump(),
            "testing": testing_output.model_dump(),
            "optimization": optimization_output.model_dump(),
        }
        self._mark_stage_running(
            run_id=run.id,
            stage_key=HANDOFF_STAGE_KEY,
            agent_id=agent_id,
            input_payload=input_payload,
            run_progress=DEVELOPMENT_EXECUTION_RUN_PROGRESS_START[HANDOFF_STAGE_KEY],
            stage_progress=DEVELOPMENT_EXECUTION_STAGE_RUNNING_PROGRESS[HANDOFF_STAGE_KEY],
            message="主控秘書正在接收全端工程師 Agent 的結構化開發報告...",
        )
        try:
            response_payload = self._dispatch_agent(
                instance_id=run.instance_id,
                agent_id=agent_id,
                session_key=f"{run.id}-{HANDOFF_STAGE_KEY}",
                message=_build_development_handoff_prompt(
                    problem_output,
                    requirements_output,
                    design_output,
                    technology_output,
                    planning_output,
                    implementation_output,
                    testing_output,
                    optimization_output,
                ),
                metadata={"workflow_run_id": run.id, "stage_key": HANDOFF_STAGE_KEY, "workflow_type": run.workflow_type},
            )
            handoff_fallback_reason = None
            try:
                output = _parse_agent_output(
                    response_payload,
                    WorkflowDevelopmentExecutionReportPayload,
                    f"Development {HANDOFF_STAGE_KEY} 階段",
                )
            except OpenClawServiceError as error:
                output = _build_development_handoff_output_fallback(
                    problem_output=problem_output,
                    requirements_output=requirements_output,
                    design_output=design_output,
                    technology_output=technology_output,
                    planning_output=planning_output,
                    implementation_output=implementation_output,
                    testing_output=testing_output,
                    optimization_output=optimization_output,
                    error=error,
                )
                handoff_fallback_reason = error.detail or error.message
            self.workflow_repository.update_stage(
                run_id=run.id,
                stage_key=HANDOFF_STAGE_KEY,
                status="completed",
                progress_percent=100,
                output_payload=output.model_dump(),
                completed_at=utc_now_iso(),
            )
            self.workflow_repository.update_run_status(
                run_id=run.id,
                status="running",
                current_stage=HANDOFF_STAGE_KEY,
                active_agent_id=agent_id,
                overall_progress_percent=DEVELOPMENT_EXECUTION_RUN_PROGRESS_DONE[HANDOFF_STAGE_KEY],
                error_message=None,
            )
            self.workflow_repository.add_event(
                run_id=run.id,
                stage_key=HANDOFF_STAGE_KEY,
                agent_id=agent_id,
                status="completed",
                progress_percent=DEVELOPMENT_EXECUTION_RUN_PROGRESS_DONE[HANDOFF_STAGE_KEY],
                message="已完成結構化匯報並交還給 Main Agent。",
                payload={
                    "task_name": output.task_name,
                    "final_summary": output.final_summary,
                    "fallback_used": bool(handoff_fallback_reason),
                    "fallback_reason": handoff_fallback_reason,
                },
            )
            return output
        except OpenClawServiceError as error:
            self._mark_stage_failed(run_id=run.id, stage_key=HANDOFF_STAGE_KEY, agent_id=agent_id, error=error)
            raise

    def _run_system_snapshot_stage(
        self,
        run: WorkflowRunResponse,
        agent_id: str,
        config: OpenClawWorkflowConfigResponse,
    ) -> WorkflowSystemInspectionSnapshotOutput:
        self._mark_stage_running(
            run_id=run.id,
            stage_key=SNAPSHOT_STAGE_KEY,
            agent_id=agent_id,
            input_payload={"instance_id": run.instance_id},
            run_progress=SYSTEM_INSPECTION_RUN_PROGRESS_START[SNAPSHOT_STAGE_KEY],
            stage_progress=SYSTEM_INSPECTION_STAGE_RUNNING_PROGRESS[SNAPSHOT_STAGE_KEY],
            message="正在收集版本、設定與近期異常快照...",
        )
        try:
            snapshot_output = self._collect_system_snapshot(run.instance_id, config)
            self.workflow_repository.update_stage(
                run_id=run.id,
                stage_key=SNAPSHOT_STAGE_KEY,
                status="completed",
                progress_percent=100,
                output_payload=snapshot_output.model_dump(),
                completed_at=utc_now_iso(),
            )
            self.workflow_repository.update_run_status(
                run_id=run.id,
                status="running",
                current_stage=SNAPSHOT_STAGE_KEY,
                active_agent_id=agent_id,
                overall_progress_percent=SYSTEM_INSPECTION_RUN_PROGRESS_DONE[SNAPSHOT_STAGE_KEY],
                error_message=None,
            )
            self.workflow_repository.add_event(
                run_id=run.id,
                stage_key=SNAPSHOT_STAGE_KEY,
                agent_id=agent_id,
                status="completed",
                progress_percent=SYSTEM_INSPECTION_RUN_PROGRESS_DONE[SNAPSHOT_STAGE_KEY],
                message="系統快照已完成，準備進入版本與日誌巡檢。",
                payload={"current_version": snapshot_output.current_version, "recent_failure_count": len(snapshot_output.recent_workflow_failures)},
            )
            return snapshot_output
        except OpenClawServiceError as error:
            self._mark_stage_failed(run_id=run.id, stage_key=SNAPSHOT_STAGE_KEY, agent_id=agent_id, error=error)
            raise

    def _run_system_version_check_stage(
        self,
        run: WorkflowRunResponse,
        agent_id: str,
        inspection_config: OpenClawSystemInspectionConfigResponse,
        snapshot_output: WorkflowSystemInspectionSnapshotOutput,
    ) -> WorkflowSystemInspectionVersionOutput:
        cli_update_summary = self._fetch_cli_update_summary()
        official_release = self._fetch_official_release_summary(inspection_config.official_release_url) if inspection_config.version_check_enabled else {
            "latest_version": None,
            "release_summary": [],
            "latest_version_status": "skipped",
        }
        input_payload = {
            "inspection_config": inspection_config.model_dump(mode="json"),
            "snapshot_output": snapshot_output.model_dump(),
            "cli_update_summary": cli_update_summary,
            "official_release": official_release,
        }
        self._mark_stage_running(
            run_id=run.id,
            stage_key=VERSION_CHECK_STAGE_KEY,
            agent_id=agent_id,
            input_payload=input_payload,
            run_progress=SYSTEM_INSPECTION_RUN_PROGRESS_START[VERSION_CHECK_STAGE_KEY],
            stage_progress=SYSTEM_INSPECTION_STAGE_RUNNING_PROGRESS[VERSION_CHECK_STAGE_KEY],
            message="正在比對目前版本與官方最新版本...",
        )
        try:
            response_payload = self._dispatch_agent(
                instance_id=run.instance_id,
                agent_id=agent_id,
                session_key=f"{run.id}-{VERSION_CHECK_STAGE_KEY}",
                message=_build_system_version_check_prompt(snapshot_output, cli_update_summary, official_release),
                metadata={"workflow_run_id": run.id, "stage_key": VERSION_CHECK_STAGE_KEY, "workflow_type": run.workflow_type},
            )
            version_fallback_reason = None
            try:
                version_output = _parse_agent_output(response_payload, WorkflowSystemInspectionVersionOutput, "系統巡檢版本階段")
            except OpenClawServiceError as error:
                version_output = _build_system_version_output_fallback(
                    snapshot_output=snapshot_output,
                    cli_update_summary=cli_update_summary,
                    official_release=official_release,
                    error=error,
                )
                version_fallback_reason = error.detail or error.message
            version_output = _normalize_system_version_output(version_output, snapshot_output, cli_update_summary, official_release)
            self.workflow_repository.update_stage(
                run_id=run.id,
                stage_key=VERSION_CHECK_STAGE_KEY,
                status="completed",
                progress_percent=100,
                output_payload=version_output.model_dump(),
                completed_at=utc_now_iso(),
            )
            self.workflow_repository.update_run_status(
                run_id=run.id,
                status="running",
                current_stage=VERSION_CHECK_STAGE_KEY,
                active_agent_id=agent_id,
                overall_progress_percent=SYSTEM_INSPECTION_RUN_PROGRESS_DONE[VERSION_CHECK_STAGE_KEY],
                error_message=None,
            )
            self.workflow_repository.add_event(
                run_id=run.id,
                stage_key=VERSION_CHECK_STAGE_KEY,
                agent_id=agent_id,
                status="completed",
                progress_percent=SYSTEM_INSPECTION_RUN_PROGRESS_DONE[VERSION_CHECK_STAGE_KEY],
                message="版本差異與升級風險評估已完成。",
                payload={
                    "current_version": version_output.current_version,
                    "latest_version": version_output.latest_version,
                    "recommendation": version_output.upgrade_recommendation,
                    "fallback_used": bool(version_fallback_reason),
                    "fallback_reason": version_fallback_reason,
                },
            )
            return version_output
        except OpenClawServiceError as error:
            self._mark_stage_failed(run_id=run.id, stage_key=VERSION_CHECK_STAGE_KEY, agent_id=agent_id, error=error)
            raise

    def _run_system_log_review_stage(
        self,
        run: WorkflowRunResponse,
        agent_id: str,
        inspection_config: OpenClawSystemInspectionConfigResponse,
        snapshot_output: WorkflowSystemInspectionSnapshotOutput,
    ) -> WorkflowSystemInspectionLogReviewOutput:
        aggregated_issues = _aggregate_system_issues(snapshot_output.recent_operation_logs, snapshot_output.recent_workflow_failures, snapshot_output.gateway_log_excerpt)
        input_payload = {
            "inspection_config": inspection_config.model_dump(mode="json"),
            "snapshot_output": snapshot_output.model_dump(),
            "aggregated_issues": [issue.model_dump() for issue in aggregated_issues],
        }
        self._mark_stage_running(
            run_id=run.id,
            stage_key=LOG_REVIEW_STAGE_KEY,
            agent_id=agent_id,
            input_payload=input_payload,
            run_progress=SYSTEM_INSPECTION_RUN_PROGRESS_START[LOG_REVIEW_STAGE_KEY],
            stage_progress=SYSTEM_INSPECTION_STAGE_RUNNING_PROGRESS[LOG_REVIEW_STAGE_KEY],
            message="正在巡檢 error、warning、timeout 與重試模式...",
        )
        try:
            response_payload = self._dispatch_agent(
                instance_id=run.instance_id,
                agent_id=agent_id,
                session_key=f"{run.id}-{LOG_REVIEW_STAGE_KEY}",
                message=_build_system_log_review_prompt(inspection_config, aggregated_issues),
                metadata={"workflow_run_id": run.id, "stage_key": LOG_REVIEW_STAGE_KEY, "workflow_type": run.workflow_type},
            )
            log_review_fallback_reason = None
            try:
                log_review_output = _parse_agent_output(response_payload, WorkflowSystemInspectionLogReviewOutput, "系統巡檢日誌階段")
            except OpenClawServiceError as error:
                log_review_output = _build_system_log_review_output_fallback(
                    inspection_config=inspection_config,
                    aggregated_issues=aggregated_issues,
                    snapshot_output=snapshot_output,
                    error=error,
                )
                log_review_fallback_reason = error.detail or error.message
            self.workflow_repository.update_stage(
                run_id=run.id,
                stage_key=LOG_REVIEW_STAGE_KEY,
                status="completed",
                progress_percent=100,
                output_payload=log_review_output.model_dump(),
                completed_at=utc_now_iso(),
            )
            self.workflow_repository.update_run_status(
                run_id=run.id,
                status="running",
                current_stage=LOG_REVIEW_STAGE_KEY,
                active_agent_id=agent_id,
                overall_progress_percent=SYSTEM_INSPECTION_RUN_PROGRESS_DONE[LOG_REVIEW_STAGE_KEY],
                error_message=None,
            )
            self.workflow_repository.add_event(
                run_id=run.id,
                stage_key=LOG_REVIEW_STAGE_KEY,
                agent_id=agent_id,
                status="completed",
                progress_percent=SYSTEM_INSPECTION_RUN_PROGRESS_DONE[LOG_REVIEW_STAGE_KEY],
                message="高頻錯誤、重複性問題與效能風險已整理完成。",
                payload={
                    "issue_count": len(log_review_output.issues),
                    "fallback_used": bool(log_review_fallback_reason),
                    "fallback_reason": log_review_fallback_reason,
                },
            )
            return log_review_output
        except OpenClawServiceError as error:
            self._mark_stage_failed(run_id=run.id, stage_key=LOG_REVIEW_STAGE_KEY, agent_id=agent_id, error=error)
            raise

    def _run_system_risk_assessment_stage(
        self,
        run: WorkflowRunResponse,
        agent_id: str,
        inspection_config: OpenClawSystemInspectionConfigResponse,
        version_output: WorkflowSystemInspectionVersionOutput,
        log_review_output: WorkflowSystemInspectionLogReviewOutput,
    ) -> WorkflowSystemInspectionRiskOutput:
        input_payload = {
            "inspection_config": inspection_config.model_dump(mode="json"),
            "version_output": version_output.model_dump(),
            "log_review_output": log_review_output.model_dump(),
        }
        self._mark_stage_running(
            run_id=run.id,
            stage_key=RISK_ASSESSMENT_STAGE_KEY,
            agent_id=agent_id,
            input_payload=input_payload,
            run_progress=SYSTEM_INSPECTION_RUN_PROGRESS_START[RISK_ASSESSMENT_STAGE_KEY],
            stage_progress=SYSTEM_INSPECTION_STAGE_RUNNING_PROGRESS[RISK_ASSESSMENT_STAGE_KEY],
            message="正在整合升級風險與系統異常優先級...",
        )
        try:
            response_payload = self._dispatch_agent(
                instance_id=run.instance_id,
                agent_id=agent_id,
                session_key=f"{run.id}-{RISK_ASSESSMENT_STAGE_KEY}",
                message=_build_system_risk_assessment_prompt(version_output, log_review_output),
                metadata={"workflow_run_id": run.id, "stage_key": RISK_ASSESSMENT_STAGE_KEY, "workflow_type": run.workflow_type},
            )
            risk_fallback_reason = None
            try:
                risk_output = _parse_agent_output(response_payload, WorkflowSystemInspectionRiskOutput, "系統巡檢風險階段")
            except OpenClawServiceError as error:
                risk_output = _build_system_risk_output_fallback(
                    version_output=version_output,
                    log_review_output=log_review_output,
                    error=error,
                )
                risk_fallback_reason = error.detail or error.message
            self.workflow_repository.update_stage(
                run_id=run.id,
                stage_key=RISK_ASSESSMENT_STAGE_KEY,
                status="completed",
                progress_percent=100,
                output_payload=risk_output.model_dump(),
                completed_at=utc_now_iso(),
            )
            self.workflow_repository.update_run_status(
                run_id=run.id,
                status="running",
                current_stage=RISK_ASSESSMENT_STAGE_KEY,
                active_agent_id=agent_id,
                overall_progress_percent=SYSTEM_INSPECTION_RUN_PROGRESS_DONE[RISK_ASSESSMENT_STAGE_KEY],
                error_message=None,
            )
            self.workflow_repository.add_event(
                run_id=run.id,
                stage_key=RISK_ASSESSMENT_STAGE_KEY,
                agent_id=agent_id,
                status="completed",
                progress_percent=SYSTEM_INSPECTION_RUN_PROGRESS_DONE[RISK_ASSESSMENT_STAGE_KEY],
                message="高優先級風險與立即行動建議已完成。",
                payload={
                    "high_priority_count": len(risk_output.high_priority_risks),
                    "fallback_used": bool(risk_fallback_reason),
                    "fallback_reason": risk_fallback_reason,
                },
            )
            return risk_output
        except OpenClawServiceError as error:
            self._mark_stage_failed(run_id=run.id, stage_key=RISK_ASSESSMENT_STAGE_KEY, agent_id=agent_id, error=error)
            raise

    def _run_system_report_stage(
        self,
        run: WorkflowRunResponse,
        agent_id: str,
        inspection_config: OpenClawSystemInspectionConfigResponse,
        version_output: WorkflowSystemInspectionVersionOutput,
        log_review_output: WorkflowSystemInspectionLogReviewOutput,
        risk_output: WorkflowSystemInspectionRiskOutput,
    ) -> WorkflowSystemInspectionReportPayload:
        input_payload = {
            "inspection_config": {
                "instance_id": inspection_config.instance_id,
                "schedule_timezone": inspection_config.schedule_timezone,
                "schedule_time": inspection_config.schedule_time,
                "delivery_channel": inspection_config.delivery_channel,
                "delivery_target": self._delivery_target_value(
                    delivery_channel=inspection_config.delivery_channel,
                    telegram_target=inspection_config.telegram_target,
                    discord_channel_id=inspection_config.discord_channel_id,
                ),
            },
            "version_output": _compact_system_version_output(version_output),
            "log_review_output": _compact_system_log_review_output(log_review_output),
            "risk_output": _compact_system_risk_output(risk_output),
        }
        self._mark_stage_running(
            run_id=run.id,
            stage_key=REPORT_STAGE_KEY,
            agent_id=agent_id,
            input_payload=input_payload,
            run_progress=SYSTEM_INSPECTION_RUN_PROGRESS_START[REPORT_STAGE_KEY],
            stage_progress=SYSTEM_INSPECTION_STAGE_RUNNING_PROGRESS[REPORT_STAGE_KEY],
            message="正在生成巡檢總結、修復順序與 Telegram 摘要...",
        )
        try:
            response_payload = self._dispatch_agent(
                instance_id=run.instance_id,
                agent_id=agent_id,
                session_key=f"{run.id}-{REPORT_STAGE_KEY}",
                message=_build_system_report_prompt(
                    _compact_system_version_output(version_output),
                    _compact_system_log_review_output(log_review_output),
                    _compact_system_risk_output(risk_output),
                ),
                metadata={"workflow_run_id": run.id, "stage_key": REPORT_STAGE_KEY, "workflow_type": run.workflow_type},
            )
            report_fallback_reason = None
            try:
                report_output = _parse_system_report_output(response_payload, version_output, log_review_output, risk_output)
            except OpenClawServiceError as error:
                report_output = _build_system_report_output_fallback(
                    version_output=version_output,
                    log_review_output=log_review_output,
                    risk_output=risk_output,
                    error=error,
                )
                report_fallback_reason = error.detail or error.message
            report_output = _normalize_system_report_payload(report_output, version_output, log_review_output, risk_output)
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
            self.workflow_repository.add_event(
                run_id=run.id,
                stage_key=REPORT_STAGE_KEY,
                agent_id=agent_id,
                status="completed",
                progress_percent=100,
                message="巡檢總結報告已完成。",
                payload={
                    "fallback_used": bool(report_fallback_reason),
                    "fallback_reason": report_fallback_reason,
                    "title": report_output.title,
                },
            )
            return report_output
        except OpenClawServiceError as error:
            self._mark_stage_failed(run_id=run.id, stage_key=REPORT_STAGE_KEY, agent_id=agent_id, error=error)
            raise

    def _collect_system_snapshot(
        self,
        instance_id: str,
        config: OpenClawWorkflowConfigResponse,
    ) -> WorkflowSystemInspectionSnapshotOutput:
        instance, token = self._load_context(instance_id)
        try:
            current_version = self.cli_adapter.get_version()
        except OpenClawServiceError as error:
            current_version = f"unknown ({error.detail or error.message})"

        last_touched_version = None
        try:
            global_meta = self.cli_adapter.get_global_config("meta.lastTouchedVersion")
            raw_value = global_meta.get("value") if isinstance(global_meta, dict) else None
            if isinstance(raw_value, str) and raw_value.strip():
                last_touched_version = raw_value.strip()
        except OpenClawServiceError:
            last_touched_version = None

        try:
            plugin_summary = self.cli_adapter.inspect_plugin("project-search")
        except OpenClawServiceError as error:
            plugin_summary = {"status": "unknown", "error": error.detail or error.message}

        gateway_logs: list[dict[str, Any]]
        try:
            gateway_logs = self.cli_adapter.get_logs(instance, token, limit=12)[:12]
        except OpenClawServiceError as error:
            gateway_logs = [{"level": "error", "message": error.detail or error.message}]

        recent_runs = self.workflow_repository.list_runs(instance_id=instance_id, limit=12)
        recent_failures = [
            {
                "run_id": item.id,
                "workflow_type": item.workflow_type,
                "status": item.status,
                "current_stage": item.current_stage,
                "active_agent_id": item.active_agent_id,
                "error_message": item.error_message,
                "updated_at": item.updated_at.isoformat(),
            }
            for item in recent_runs
            if item.status == "failed"
        ][:6]
        capability_summary = [
            {
                "agent_id": record.agent_id,
                "capability_key": record.capability_key,
                "is_enabled": record.is_enabled,
            }
            for record in self.capability_repository.list_for_instance(instance_id=instance_id)
        ]
        operation_logs = [
            {
                "operation_type": item.operation_type,
                "status": item.status,
                "target_type": item.target_type,
                "error_message": item.error_message,
                "created_at": item.created_at.isoformat(),
                "request_summary": item.request_summary,
            }
            for item in self.operation_log_repository.list_recent(instance_id=instance_id, limit=20)
        ]

        return WorkflowSystemInspectionSnapshotOutput(
            current_version=current_version,
            latest_touched_version=last_touched_version,
            instance_count=len(self.repository.list_all()),
            workflow_mapping=_specialist_snapshot(config),
            capability_summary=capability_summary,
            plugin_summary=plugin_summary if isinstance(plugin_summary, dict) else {"raw": plugin_summary},
            recent_workflow_failures=recent_failures,
            recent_operation_logs=operation_logs,
            gateway_log_excerpt=[_normalize_gateway_log_item(item) for item in gateway_logs[:10]],
        )

    def _fetch_official_release_summary(self, url: str) -> dict[str, Any]:
        try:
            payload = self.release_client.fetch_release_summary(url)
            return {
                **payload,
                "latest_version_status": "available" if payload.get("latest_version") else "unknown",
            }
        except OpenClawServiceError as error:
            return {
                "latest_version": None,
                "release_summary": [],
                "latest_version_status": "unknown",
                "assumption": error.detail or error.message,
                "verification_steps": [f"手動打開 {url} 確認最新 release 或 changelog。"],
            }

    def _fetch_cli_update_summary(self) -> dict[str, Any]:
        try:
            return self.cli_adapter.get_update_summary()
        except OpenClawServiceError as error:
            return {
                "generated_at": utc_now_iso(),
                "status": "unknown",
                "current_version": None,
                "latest_version": None,
                "channel_label": None,
                "update_available": False,
                "assumption": error.detail or error.message,
                "verification_steps": ["手動執行 `openclaw status --json` 與 `openclaw update status --json` 確認最新版本狀態。"],
            }

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
        timeout_seconds = self.news_agent_dispatch_timeout_seconds if metadata.get("workflow_type") in {WORKFLOW_TYPE_NEWS_BRIEF, WORKFLOW_TYPE_SYSTEM_INSPECTION} else None
        request_summary = {
            "agent_id": agent_id,
            "session_key": session_key,
            "workflow_run_id": metadata.get("workflow_run_id"),
            "workflow_type": metadata.get("workflow_type"),
            "stage_key": metadata.get("stage_key"),
            "timeout_seconds": timeout_seconds,
            "message_preview": truncate_text(message, 200),
        }
        max_attempts = 1 + self.workflow_dispatch_retry_count
        retryable_failure_kinds = {"embedded_model_timeout", "dispatch_timeout"}

        for attempt in range(1, max_attempts + 1):
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
                        "timeout_seconds": timeout_seconds,
                    },
                )
                dispatch_meta = result.get("_dispatch_meta") if isinstance(result, dict) else None
                self.operation_log_repository.create(
                    instance_id=instance_id,
                    operation_type="dispatch_workflow_stage",
                    target_type="workflow_stage",
                    target_id=f"{agent_id}:{session_key}",
                    status="success",
                    error_message=None,
                    request_summary={**request_summary, "attempt": attempt, "max_attempts": max_attempts},
                    response_summary={
                        "status": result.get("status"),
                        "summary": result.get("summary"),
                        "returncode": dispatch_meta.get("returncode") if isinstance(dispatch_meta, dict) else None,
                        "duration_ms": dispatch_meta.get("duration_ms") if isinstance(dispatch_meta, dict) else None,
                        "stdout_preview": dispatch_meta.get("stdout_preview") if isinstance(dispatch_meta, dict) else None,
                        "stderr_preview": dispatch_meta.get("stderr_preview") if isinstance(dispatch_meta, dict) else None,
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                    },
                    source_mode=self.hook_client.source_mode,
                )
                return result
            except OpenClawServiceError as error:
                error_meta = error.metadata if isinstance(error.metadata, dict) else {}
                failure_kind = error_meta.get("failure_kind")
                will_retry = attempt < max_attempts and failure_kind in retryable_failure_kinds
                self.operation_log_repository.create(
                    instance_id=instance_id,
                    operation_type="dispatch_workflow_stage",
                    target_type="workflow_stage",
                    target_id=f"{agent_id}:{session_key}",
                    status="failed",
                    error_message=error.detail or error.message,
                    request_summary={**request_summary, "attempt": attempt, "max_attempts": max_attempts},
                    response_summary={
                        "failure_kind": failure_kind,
                        "returncode": error_meta.get("returncode"),
                        "duration_ms": error_meta.get("duration_ms"),
                        "stdout_preview": error_meta.get("stdout_preview"),
                        "stderr_preview": error_meta.get("stderr_preview"),
                        "timeout_seconds": error_meta.get("timeout_seconds"),
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "will_retry": will_retry,
                    },
                    source_mode=error.source_mode or self.hook_client.source_mode,
                )
                if not will_retry:
                    raise
                sleep_ms = self.workflow_dispatch_retry_backoff_ms + random.randint(0, 300)
                time.sleep(sleep_ms / 1000)

        raise OpenClawServiceError(
            "OpenClaw agent 派發失敗。",
            detail="dispatch workflow stage exhausted retries",
            source_mode=self.hook_client.source_mode,
        )

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
        controller_agent_id = str(failed_run.input_payload.get("controller_agent_id") or "")
        if controller_agent_id:
            self._add_controller_event(
                run_id=run_id,
                controller_agent_id=controller_agent_id,
                progress_percent=failed_run.overall_progress_percent,
                message="主控秘書已標記此任務需要人工接管或後續處理。",
                payload=_build_manual_review_payload(failed_run, error),
                status="failed",
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

    def _get_daily_news_config_or_error(self, instance_id: str) -> OpenClawDailyNewsConfigResponse:
        try:
            return self.daily_news_repository.get(instance_id)
        except KeyError as error:
            raise OpenClawServiceError(
                "此 Instance 尚未設定 Daily News Brief。",
                detail="請先到 OpenClaw Daily News 頁設定主題、來源與投遞目標。",
                status_code=400,
                source_mode=self.source_mode,
            ) from error

    def _get_system_inspection_config_or_error(self, instance_id: str) -> OpenClawSystemInspectionConfigResponse:
        try:
            return self.system_inspection_repository.get(instance_id)
        except KeyError as error:
            raise OpenClawServiceError(
                "此 Instance 尚未設定系統巡檢與風險評估。",
                detail="請先到 OpenClaw System Inspection 頁設定排程、投遞目標與官方版本來源。",
                status_code=400,
                source_mode=self.source_mode,
            ) from error

    def _get_development_config(self, instance_id: str) -> OpenClawDevelopmentConfigResponse | None:
        try:
            return self.development_repository.get(instance_id)
        except KeyError:
            return None

    def _resolve_development_delivery_target(self, instance_id: str) -> dict[str, Any]:
        config = self._get_development_config(instance_id)
        resolution = _resolve_development_delivery_target(instance_id, config)
        resolution["config"] = config
        return resolution

    def _load_context(self, instance_id: str):
        instance = self.repository.get(instance_id)
        encrypted_token = self.repository.get_secret(instance_id)
        token = self.secret_cipher.decrypt(encrypted_token) if encrypted_token else None
        return instance, token

    @staticmethod
    def _delivery_channel_label(delivery_channel: str) -> str:
        return "Discord" if delivery_channel == "discord" else "Telegram"

    @staticmethod
    def _delivery_target_value(*, delivery_channel: str, telegram_target: str, discord_channel_id: str) -> str | None:
        target = discord_channel_id if delivery_channel == "discord" else telegram_target
        normalized = target.strip()
        return normalized or None

    @classmethod
    def _has_delivery_target(cls, *, delivery_channel: str, telegram_target: str, discord_channel_id: str) -> bool:
        return cls._delivery_target_value(
            delivery_channel=delivery_channel,
            telegram_target=telegram_target,
            discord_channel_id=discord_channel_id,
        ) is not None

    def _deliver_news_brief(
        self,
        *,
        instance_id: str,
        delivery_channel: str,
        delivery_target: str,
        brief_payload: WorkflowNewsBriefPayload,
        run_id: str,
    ) -> None:
        target_type = delivery_channel
        request_summary = {"delivery_channel": delivery_channel, "delivery_target": delivery_target, "run_id": run_id}
        try:
            if delivery_channel == "discord":
                result = self.discord_delivery_client.send_text(channel_id=delivery_target, text=brief_payload.markdown)
                source_mode = self.discord_delivery_client.source_mode
                response_summary = {
                    "channel_id": result.get("channel_id"),
                    "message_ids": result.get("message_ids"),
                    "message_count": result.get("message_count"),
                }
            else:
                result = self.telegram_delivery_client.send_markdown(chat_id=delivery_target, text=brief_payload.markdown)
                source_mode = self.telegram_delivery_client.source_mode
                response_summary = {"message_id": result.get("message_id"), "chat": result.get("chat")}
            self.operation_log_repository.create(
                instance_id=instance_id,
                operation_type="deliver_daily_news_brief",
                target_type=target_type,
                target_id=delivery_target,
                status="success",
                error_message=None,
                request_summary=request_summary,
                response_summary=response_summary,
                source_mode=source_mode,
            )
        except OpenClawServiceError as error:
            self.operation_log_repository.create(
                instance_id=instance_id,
                operation_type="deliver_daily_news_brief",
                target_type=target_type,
                target_id=delivery_target,
                status="failed",
                error_message=error.detail or error.message,
                request_summary=request_summary,
                response_summary=None,
                source_mode=error.source_mode or (
                    self.discord_delivery_client.source_mode if delivery_channel == "discord" else self.telegram_delivery_client.source_mode
                ),
            )
            raise

    def _deliver_system_inspection_summary(
        self,
        *,
        instance_id: str,
        delivery_channel: str,
        delivery_target: str,
        report_payload: WorkflowSystemInspectionReportPayload,
        run_id: str,
    ) -> None:
        target_type = delivery_channel
        request_summary = {"delivery_channel": delivery_channel, "delivery_target": delivery_target, "run_id": run_id}
        try:
            if delivery_channel == "discord":
                result = self.system_inspection_discord_delivery_client.send_text(
                    channel_id=delivery_target,
                    text=report_payload.telegram_summary,
                )
                source_mode = self.system_inspection_discord_delivery_client.source_mode
                response_summary = {
                    "channel_id": result.get("channel_id"),
                    "message_ids": result.get("message_ids"),
                    "message_count": result.get("message_count"),
                }
            else:
                result = self.system_inspection_telegram_delivery_client.send_markdown(
                    chat_id=delivery_target,
                    text=report_payload.telegram_summary,
                )
                source_mode = self.system_inspection_telegram_delivery_client.source_mode
                response_summary = {"message_id": result.get("message_id"), "chat": result.get("chat")}
            self.operation_log_repository.create(
                instance_id=instance_id,
                operation_type="deliver_system_inspection_summary",
                target_type=target_type,
                target_id=delivery_target,
                status="success",
                error_message=None,
                request_summary=request_summary,
                response_summary=response_summary,
                source_mode=source_mode,
            )
        except OpenClawServiceError as error:
            self.operation_log_repository.create(
                instance_id=instance_id,
                operation_type="deliver_system_inspection_summary",
                target_type=target_type,
                target_id=delivery_target,
                status="failed",
                error_message=error.detail or error.message,
                request_summary=request_summary,
                response_summary=None,
                source_mode=error.source_mode or (
                    self.system_inspection_discord_delivery_client.source_mode
                    if delivery_channel == "discord"
                    else self.system_inspection_telegram_delivery_client.source_mode
                ),
            )
            raise

    def _deliver_development_report(
        self,
        *,
        instance_id: str,
        delivery_target: str,
        text: str,
        run_id: str,
    ) -> None:
        request_summary = {"delivery_channel": "discord", "delivery_target": delivery_target, "run_id": run_id}
        try:
            result = self.development_discord_delivery_client.send_text(channel_id=delivery_target, text=text)
            self.operation_log_repository.create(
                instance_id=instance_id,
                operation_type="deliver_development_report",
                target_type="discord",
                target_id=delivery_target,
                status="success",
                error_message=None,
                request_summary=request_summary,
                response_summary={
                    "channel_id": result.get("channel_id"),
                    "message_ids": result.get("message_ids"),
                    "message_count": result.get("message_count"),
                },
                source_mode=self.development_discord_delivery_client.source_mode,
            )
        except OpenClawServiceError as error:
            self.operation_log_repository.create(
                instance_id=instance_id,
                operation_type="deliver_development_report",
                target_type="discord",
                target_id=delivery_target,
                status="failed",
                error_message=error.detail or error.message,
                request_summary=request_summary,
                response_summary=None,
                source_mode=error.source_mode or self.development_discord_delivery_client.source_mode,
            )
            raise

    def _deliver_failed_development_report(self, *, run_id: str, controller_agent_id: str | None = None) -> None:
        failed_run = self.workflow_repository.get_run(run_id)
        delivery_resolution = self._resolve_development_delivery_target(failed_run.instance_id)
        delivery_target = delivery_resolution["target"]
        delivery_status = "delivered"
        delivery_error = None
        delivery_source = delivery_resolution["source"]
        delivery_reason = delivery_resolution["reason"]
        if not delivery_target:
            self.workflow_repository.add_event(
                run_id=failed_run.id,
                stage_key=failed_run.current_stage,
                agent_id=controller_agent_id or failed_run.active_agent_id,
                status="completed",
                progress_percent=failed_run.overall_progress_percent,
                message="Development 失敗後未找到 Discord 匯報目標，已略過外部匯報。",
                payload={
                    "delivery_status": "skipped",
                    "delivery_target": None,
                    "delivery_source": delivery_source,
                    "delivery_reason": delivery_reason,
                },
            )
            if delivery_resolution["config"] is not None:
                self.development_repository.mark_delivery(
                    instance_id=failed_run.instance_id,
                    run_id=failed_run.id,
                    delivery_status="skipped",
                    delivery_error=None,
                )
            return

        try:
            self._deliver_development_report(
                instance_id=failed_run.instance_id,
                delivery_target=delivery_target,
                text=_build_failed_development_delivery_markdown(failed_run),
                run_id=failed_run.id,
            )
            self.workflow_repository.add_event(
                run_id=failed_run.id,
                stage_key=failed_run.current_stage,
                agent_id=controller_agent_id or failed_run.active_agent_id,
                status="completed",
                progress_percent=failed_run.overall_progress_percent,
                message="Development 失敗摘要已推送到 Discord。",
                payload={
                    "delivery_status": delivery_status,
                    "delivery_target": delivery_target,
                    "delivery_source": delivery_source,
                    "delivery_reason": delivery_reason,
                },
            )
        except OpenClawServiceError as error:
            delivery_status = "failed"
            delivery_error = error.detail or error.message
            self.workflow_repository.add_event(
                run_id=failed_run.id,
                stage_key=failed_run.current_stage,
                agent_id=controller_agent_id or failed_run.active_agent_id,
                status="failed",
                progress_percent=failed_run.overall_progress_percent,
                message="Development 失敗後嘗試推送 Discord 摘要，但發送失敗。",
                payload={
                    "delivery_status": delivery_status,
                    "delivery_target": delivery_target,
                    "delivery_error": delivery_error,
                    "delivery_source": delivery_source,
                    "delivery_reason": delivery_reason,
                },
            )

        if delivery_resolution["config"] is not None:
            self.development_repository.mark_delivery(
                instance_id=failed_run.instance_id,
                run_id=failed_run.id,
                delivery_status=delivery_status,
                delivery_error=delivery_error,
            )

    @staticmethod
    def _jst_today() -> str:
        return datetime.now(ZoneInfo("Asia/Tokyo")).date().isoformat()

    @staticmethod
    def _today_in_timezone(timezone_name: str) -> str:
        try:
            return datetime.now(ZoneInfo(timezone_name)).date().isoformat()
        except Exception:
            return datetime.now(ZoneInfo("Asia/Tokyo")).date().isoformat()

    def _scheduled_date_for_run(self, run: WorkflowRunResponse, timezone_name: str) -> str:
        candidate = run.input_payload.get("scheduled_date")
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
        return self._today_in_timezone(timezone_name)

    def _add_controller_event(
        self,
        *,
        run_id: str,
        controller_agent_id: str,
        progress_percent: int,
        message: str,
        payload: dict[str, Any],
        status: str = "running",
    ) -> None:
        self.workflow_repository.add_event(
            run_id=run_id,
            stage_key=None,
            agent_id=controller_agent_id,
            status=status,
            progress_percent=progress_percent,
            message=message,
            payload=payload,
        )

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


class DailyNewsScheduler:
    source_mode = "scheduler"

    def __init__(
        self,
        workflow_service: Optional[SearchReportWorkflowService] = None,
        daily_news_service: Optional[OpenClawDailyNewsConfigService] = None,
    ) -> None:
        from app.config import get_settings

        self.settings = get_settings()
        self.workflow_service = workflow_service or SearchReportWorkflowService()
        self.daily_news_service = daily_news_service or OpenClawDailyNewsConfigService()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_pending_once()
            except Exception:
                pass
            self._stop_event.wait(60)

    def run_pending_once(self, now: datetime | None = None) -> None:
        current = now or datetime.now(ZoneInfo("Asia/Tokyo"))
        for config in self.daily_news_service.daily_news_repository.list_enabled():
            if not _should_run_daily_news(config, current):
                continue
            run, _ = self.workflow_service.create_news_brief_run(WorkflowNewsBriefCreateRequest(instance_id=config.instance_id))
            self.daily_news_service.daily_news_repository.mark_run(
                instance_id=config.instance_id,
                scheduled_date=current.astimezone(ZoneInfo(config.schedule_timezone)).date().isoformat(),
                run_id=run.id,
            )


class SystemInspectionScheduler:
    source_mode = "scheduler"

    def __init__(
        self,
        workflow_service: Optional[SearchReportWorkflowService] = None,
        system_inspection_service: Optional[OpenClawSystemInspectionConfigService] = None,
    ) -> None:
        self.workflow_service = workflow_service or SearchReportWorkflowService()
        self.system_inspection_service = system_inspection_service or OpenClawSystemInspectionConfigService()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_pending_once()
            except Exception:
                pass
            self._stop_event.wait(60)

    def run_pending_once(self, now: datetime | None = None) -> None:
        current = now or datetime.now(ZoneInfo("Asia/Tokyo"))
        for config in self.system_inspection_service.system_inspection_repository.list_enabled():
            if not _should_run_system_inspection(config, current):
                continue
            run, _ = self.workflow_service.create_system_inspection_run(WorkflowSystemInspectionCreateRequest(instance_id=config.instance_id))
            self.system_inspection_service.system_inspection_repository.mark_run(
                instance_id=config.instance_id,
                scheduled_date=current.astimezone(ZoneInfo(config.schedule_timezone)).date().isoformat(),
                run_id=run.id,
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
        "你是 Web Search + Knowledge Ingest 的理解階段代理。請先理解使用者的搜尋目標、入庫意圖與條件，之後其他階段會承接你的輸出。\n"
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
        "你是 Web Search + Knowledge Ingest 的搜尋階段代理，必須使用 OpenClaw 內建 web_search 工具完成外網搜尋。\n"
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
        "你是 Web Search + Knowledge Ingest 的過濾階段代理。請根據 must_include、must_exclude、focus_points 與搜尋目標過濾來源，並指出哪些來源值得入庫。\n"
        f"理解階段輸出：{json.dumps(understand_output.model_dump(), ensure_ascii=False)}\n"
        f"搜尋階段輸出：{json.dumps(search_output.model_dump(), ensure_ascii=False)}\n"
        "請只留下真正相關且值得沉澱的來源與資訊，並只輸出 JSON。\n"
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
        '  "rejected_sources": [\n'
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
        '  "focus_answers": ["..."],\n'
        '  "ingest_reason": "一句話說明為何這些來源值得入庫",\n'
        '  "suggested_business_type": "support|product|engineering|compliance|operations|market|finance|security|null",\n'
        '  "suggested_topic_tags": ["..."]\n'
        "}\n"
        "不要輸出額外說明。"
    )


def _build_web_format_prompt(
    request_payload: dict[str, Any],
    understand_output: WorkflowWebSearchUnderstandOutput,
    filter_output: WorkflowWebSearchFilterOutput,
    ingest_output: WorkflowWebSearchIngestOutput,
) -> str:
    return (
        "你是 Web Search + Knowledge Ingest 的格式化階段代理。請把已過濾的結果與入庫摘要整合成使用者指定格式，並保留清楚來源。\n"
        f"原始請求：{json.dumps(request_payload, ensure_ascii=False)}\n"
        f"理解階段輸出：{json.dumps(understand_output.model_dump(), ensure_ascii=False)}\n"
        f"過濾階段輸出：{json.dumps(filter_output.model_dump(), ensure_ascii=False)}\n"
        f"入庫階段輸出：{json.dumps(ingest_output.model_dump(), ensure_ascii=False)}\n"
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
        '  "ingestion_run_id": "krun_...",\n'
        '  "ingest_result": {\n'
        '    "source_resolution": "explicit_source|merged|created",\n'
        '    "created_source_id": "...",\n'
        '    "merged_source_id": "...",\n'
        '    "ingestion_run_id": "krun_...",\n'
        '    "stored_documents": ["doc_..."],\n'
        '    "updated_documents": ["doc_..."],\n'
        '    "rejected_documents": ["https://..."],\n'
        '    "ingest_summary": "...",\n'
        '    "source_name": "..."\n'
        "  },\n"
        '  "structured_output": "依指定格式排好的主要內容",\n'
        '  "markdown": "# ..."\n'
        "}\n"
        "不要輸出額外說明。"
    )


def _build_news_monitor_prompt(config: OpenClawDailyNewsConfigResponse) -> str:
    compact_config = _compact_daily_news_config(config)
    return (
        "你是 Daily News Brief 的監控階段代理。請根據以下設定整理今日新聞監控範圍，只輸出 JSON。\n"
        f"設定：{json.dumps(compact_config, ensure_ascii=False)}\n"
        "JSON schema:\n"
        "{\n"
        '  "goal_summary": "一句話說明今日追蹤重點",\n'
        '  "tracking_scope": ["..."],\n'
        '  "search_queries": ["..."],\n'
        '  "watch_focus": ["..."]\n'
        "}\n"
        "不要輸出額外文字。"
    )


def _build_news_search_prompt(
    config: OpenClawDailyNewsConfigResponse,
    monitor_output: WorkflowNewsMonitorOutput,
) -> str:
    compact_config = _compact_daily_news_config(config)
    compact_monitor_output = _compact_news_monitor_output(monitor_output)
    return (
        "你是 Daily News Brief 的搜尋階段代理，必須使用 OpenClaw 內建 web_search 工具蒐集最新新聞。\n"
        "只聚焦指定主題、關鍵字、產業、地區、人物、公司與來源，優先可信主流來源。\n"
        "優先輸出 6 則以內、最值得進入後續去重與排序的候選新聞。\n"
        f"設定：{json.dumps(compact_config, ensure_ascii=False)}\n"
        f"監控輸出：{json.dumps(compact_monitor_output, ensure_ascii=False)}\n"
        "只輸出 JSON。\n"
        "{\n"
        '  "summary": "一句話說明今天搜到的新聞狀況",\n'
        '  "raw_sources": [{"title":"...", "snippet":"...", "source_name":"...", "reason":"...", "published_at":"...", "url":"https://...", "domain":"..."}]\n'
        "}\n"
        "不要輸出額外文字。"
    )


def _build_news_dedupe_prompt(
    config: OpenClawDailyNewsConfigResponse,
    search_output: WorkflowNewsSearchOutput,
) -> str:
    compact_search_output = _compact_news_search_output(search_output)
    compact_config = _compact_daily_news_config(config)
    return (
        "你是 Daily News Brief 的去重階段代理。請將同一事件的多篇新聞合併，去除重複、低可信與弱相關內容。\n"
        f"設定：{json.dumps(compact_config, ensure_ascii=False)}\n"
        f"搜尋輸出：{json.dumps(compact_search_output, ensure_ascii=False)}\n"
        "只輸出 JSON。\n"
        "{\n"
        '  "summary": "一句話說明去重結果",\n'
        '  "unique_stories": [{"title":"...", "summary":"...", "importance_reason":"...", "possible_impact":"...", "sources":[{"title":"...", "snippet":"...", "source_name":"...", "reason":"...", "published_at":"...", "url":"https://...", "domain":"..."}], "published_at":"...", "background":"...", "watch_points":["..."], "event_key":"..."}],\n'
        '  "removed_duplicates": 0,\n'
        '  "dedupe_notes": ["..."]\n'
        "}\n"
        "不要輸出額外文字。"
    )


def _build_news_rank_prompt(
    config: OpenClawDailyNewsConfigResponse,
    dedupe_output: WorkflowNewsDedupeOutput,
) -> str:
    compact_dedupe_output = _compact_news_dedupe_output(dedupe_output)
    compact_config = _compact_daily_news_config(config)
    return (
        "你是 Daily News Brief 的排序階段代理。請依重要性、時效性、影響力、相關性排序新聞，並標記不完整或有爭議資訊。\n"
        f"設定：{json.dumps(compact_config, ensure_ascii=False)}\n"
        f"去重輸出：{json.dumps(compact_dedupe_output, ensure_ascii=False)}\n"
        "只輸出 JSON。\n"
        "{\n"
        '  "summary": "一句話說明排序結果",\n'
        '  "top_stories": [{"title":"...", "summary":"...", "importance_reason":"...", "possible_impact":"...", "sources":[{"title":"...", "snippet":"...", "source_name":"...", "reason":"...", "published_at":"...", "url":"https://...", "domain":"..."}], "published_at":"...", "background":"...", "watch_points":["..."], "event_key":"..."}],\n'
        '  "other_stories": [{"title":"...", "summary":"...", "importance_reason":"...", "possible_impact":"...", "sources":[{"title":"...", "snippet":"...", "source_name":"...", "reason":"...", "published_at":"...", "url":"https://...", "domain":"..."}], "published_at":"...", "background":"...", "watch_points":["..."], "event_key":"..."}],\n'
        '  "trend_summary": "...",\n'
        '  "watch_items": ["..."],\n'
        '  "uncertainties": ["..."]\n'
        "}\n"
        "不要輸出額外文字。"
    )


def _build_news_brief_prompt(
    config: OpenClawDailyNewsConfigResponse,
    dedupe_output: WorkflowNewsDedupeOutput,
    rank_output: WorkflowNewsRankOutput,
) -> str:
    compact_dedupe_output = _compact_news_brief_dedupe_snapshot(dedupe_output)
    compact_rank_output = _compact_news_rank_output(rank_output)
    compact_config = _compact_daily_news_config(config)
    return (
        "你是 Daily News Brief 的簡報階段代理。請根據排序結果輸出高品質每日簡報。\n"
        "風格要求：簡潔、清晰、專業、可快速閱讀、重點優先。\n"
        f"設定：{json.dumps(compact_config, ensure_ascii=False)}\n"
        f"去重輸出：{json.dumps(compact_dedupe_output, ensure_ascii=False)}\n"
        f"排序輸出：{json.dumps(compact_rank_output, ensure_ascii=False)}\n"
        "只輸出 JSON。\n"
        "{\n"
        '  "title": "每日新聞 Brief",\n'
        '  "top_stories": [{"title":"...", "summary":"...", "importance_reason":"...", "possible_impact":"...", "sources":[{"title":"...", "snippet":"...", "source_name":"...", "reason":"...", "published_at":"...", "url":"https://...", "domain":"..."}], "published_at":"...", "background":"...", "watch_points":["..."], "event_key":"..."}],\n'
        '  "other_stories": [{"title":"...", "summary":"...", "importance_reason":"...", "possible_impact":"...", "sources":[{"title":"...", "snippet":"...", "source_name":"...", "reason":"...", "published_at":"...", "url":"https://...", "domain":"..."}], "published_at":"...", "background":"...", "watch_points":["..."], "event_key":"..."}],\n'
        '  "trend_summary": "...",\n'
        '  "watch_items": ["..."],\n'
        '  "dedupe_notes": ["..."],\n'
        '  "uncertainties": ["..."],\n'
        '  "raw_sources": [{"title":"...", "snippet":"...", "source_name":"...", "reason":"...", "published_at":"...", "url":"https://...", "domain":"..."}],\n'
        '  "markdown": "# 每日新聞 Brief\\n\\n## 一、今日最重要新聞\\n..."\n'
        "}\n"
        "不要輸出額外文字。"
    )


def _build_system_version_check_prompt(
    snapshot_output: WorkflowSystemInspectionSnapshotOutput,
    cli_update_summary: dict[str, Any],
    official_release: dict[str, Any],
) -> str:
    return (
        "你是 OpenClaw 系統巡檢的版本更新代理。請以 CLI update summary 作為版本真源，並用官方 release 摘要補充 breaking changes、相容性與升級注意事項。\n"
        f"系統快照：{json.dumps(snapshot_output.model_dump(), ensure_ascii=False)}\n"
        f"CLI update summary（真源）：{json.dumps(cli_update_summary, ensure_ascii=False)}\n"
        f"官方 release 摘要（輔助上下文）：{json.dumps(official_release, ensure_ascii=False)}\n"
        "latest_version、latest_version_status、update_available、channel_label 必須優先依據 CLI update summary；官方 release 摘要不能覆蓋 CLI 的版本判斷。\n"
        "若 CLI update summary 無法取得，必須標註假設與驗證方法，不可把 docs 頁面上的第一個版本號當成真源。\n"
        "只輸出 JSON。\n"
        "{\n"
        '  "current_version": "...",\n'
        '  "latest_version": "...",\n'
        '  "latest_version_status": "available|unknown|skipped",\n'
        '  "update_available": true,\n'
        '  "channel_label": "stable (default)",\n'
        '  "version_source": "openclaw_cli_update|official_release_fallback|unknown",\n'
        '  "version_gap": "...",\n'
        '  "release_summary": ["..."],\n'
        '  "breaking_changes": ["..."],\n'
        '  "deprecations": ["..."],\n'
        '  "compatibility_risks": ["..."],\n'
        '  "affected_areas": {"agent_config":["..."], "tool_permissions":["..."], "prompt_logic":["..."], "workflow":["..."], "plugins_skills":["..."], "ui_console":["..."], "deployment_runtime":["..."]},\n'
        '  "upgrade_recommendation": "upgrade_now|test_before_upgrade|do_not_upgrade_yet",\n'
        '  "regression_test_checklist": ["..."],\n'
        '  "assumptions": ["..."],\n'
        '  "verification_steps": ["..."]\n'
        "}\n"
        "不要輸出額外文字。"
    )


def _normalize_system_version_output(
    version_output: WorkflowSystemInspectionVersionOutput,
    snapshot_output: WorkflowSystemInspectionSnapshotOutput,
    cli_update_summary: dict[str, Any],
    official_release: dict[str, Any],
) -> WorkflowSystemInspectionVersionOutput:
    cli_current_version = _optional_clean_string(cli_update_summary.get("current_version"))
    cli_latest_version = _optional_clean_string(cli_update_summary.get("latest_version"))
    cli_channel_label = _optional_clean_string(cli_update_summary.get("channel_label"))
    cli_update_available = cli_update_summary.get("update_available")
    release_summary = version_output.release_summary or [
        item for item in official_release.get("release_summary", []) if isinstance(item, str) and item.strip()
    ]

    if cli_current_version or cli_latest_version:
        latest_version_status = "available" if cli_latest_version else "unknown"
        version_source = "openclaw_cli_update"
    else:
        latest_version_status = str(official_release.get("latest_version_status") or version_output.latest_version_status or "unknown")
        version_source = "official_release_fallback" if official_release.get("latest_version") else "unknown"

    return version_output.model_copy(
        update={
            "current_version": cli_current_version or snapshot_output.current_version or version_output.current_version,
            "latest_version": cli_latest_version or version_output.latest_version,
            "latest_version_status": latest_version_status,
            "update_available": cli_update_available if isinstance(cli_update_available, bool) else version_output.update_available,
            "channel_label": cli_channel_label or version_output.channel_label,
            "version_source": version_source,
            "release_summary": release_summary,
        }
    )


def _build_system_version_output_fallback(
    *,
    snapshot_output: WorkflowSystemInspectionSnapshotOutput,
    cli_update_summary: dict[str, Any],
    official_release: dict[str, Any],
    error: OpenClawServiceError,
) -> WorkflowSystemInspectionVersionOutput:
    cli_current_version = _optional_clean_string(cli_update_summary.get("current_version"))
    cli_latest_version = _optional_clean_string(cli_update_summary.get("latest_version"))
    cli_channel_label = _optional_clean_string(cli_update_summary.get("channel_label"))
    cli_update_available = cli_update_summary.get("update_available")

    release_summary = [
        item for item in official_release.get("release_summary", []) if isinstance(item, str) and item.strip()
    ]
    latest_version_status = "available" if cli_latest_version else str(official_release.get("latest_version_status") or "unknown")
    latest_version = cli_latest_version or _optional_clean_string(official_release.get("latest_version"))
    current_version = cli_current_version or snapshot_output.current_version or "unknown"
    update_available = bool(cli_update_available) if isinstance(cli_update_available, bool) else bool(latest_version)
    version_gap = ""
    if current_version and latest_version:
        version_gap = "matched" if current_version == latest_version else f"{current_version} -> {latest_version}"

    assumptions = [f"Agent 未回傳可解析文字，版本欄位改採 CLI update summary fallback：{error.detail or error.message}"]
    assumption = _optional_clean_string(cli_update_summary.get("assumption"))
    if assumption:
        assumptions.append(assumption)

    verification_steps = [
        "重新執行 `openclaw status --json` 與 `openclaw update status --json` 確認版本資訊。",
    ]
    verification_steps.extend(
        item for item in cli_update_summary.get("verification_steps", []) if isinstance(item, str) and item.strip()
    )

    compatibility_risks = list(
        dict.fromkeys(
            item for item in official_release.get("compatibility_risks", []) if isinstance(item, str) and item.strip()
        )
    )

    return WorkflowSystemInspectionVersionOutput(
        current_version=current_version,
        latest_version=latest_version,
        latest_version_status=latest_version_status,
        update_available=update_available,
        channel_label=cli_channel_label,
        version_source="openclaw_cli_update" if cli_current_version or cli_latest_version else "official_release_fallback",
        version_gap=version_gap,
        release_summary=release_summary,
        breaking_changes=[
            item for item in official_release.get("breaking_changes", []) if isinstance(item, str) and item.strip()
        ],
        deprecations=[
            item for item in official_release.get("deprecations", []) if isinstance(item, str) and item.strip()
        ],
        compatibility_risks=compatibility_risks,
        affected_areas={
            key: [item for item in value if isinstance(item, str) and item.strip()]
            for key, value in official_release.get("affected_areas", {}).items()
            if isinstance(key, str) and isinstance(value, list)
        },
        upgrade_recommendation="test_before_upgrade" if latest_version and latest_version != current_version else "do_not_upgrade_yet",
        regression_test_checklist=[
            item for item in official_release.get("regression_test_checklist", []) if isinstance(item, str) and item.strip()
        ],
        assumptions=assumptions,
        verification_steps=list(dict.fromkeys(verification_steps)),
    )


def _normalize_system_report_payload(
    report_output: WorkflowSystemInspectionReportPayload,
    version_output: WorkflowSystemInspectionVersionOutput,
    log_review_output: WorkflowSystemInspectionLogReviewOutput,
    risk_output: WorkflowSystemInspectionRiskOutput,
) -> WorkflowSystemInspectionReportPayload:
    title = report_output.title.strip() or "系統巡檢與風險評估報告"
    draft = WorkflowSystemInspectionReportDraft(
        title=title,
        inspection_summary=report_output.inspection_summary,
        fix_and_optimization_actions=report_output.fix_and_optimization_actions,
        open_questions=report_output.open_questions,
        recommended_execution_order=report_output.recommended_execution_order,
        telegram_summary=report_output.telegram_summary,
        markdown=report_output.markdown,
    )
    markdown = _build_system_inspection_markdown(
        title,
        version_output,
        log_review_output,
        risk_output,
        draft,
    )
    telegram_summary = draft.telegram_summary.strip() or _build_system_inspection_telegram_summary(
        title,
        version_output,
        risk_output,
        draft,
    )
    return report_output.model_copy(
        update={
            "version_update_check": version_output,
            "telegram_summary": telegram_summary,
            "markdown": markdown,
        }
    )


def _build_system_report_output_fallback(
    *,
    version_output: WorkflowSystemInspectionVersionOutput,
    log_review_output: WorkflowSystemInspectionLogReviewOutput,
    risk_output: WorkflowSystemInspectionRiskOutput,
    error: OpenClawServiceError,
) -> WorkflowSystemInspectionReportPayload:
    inspection_summary = _dedupe_non_empty_strings(
        [
            risk_output.summary,
            log_review_output.summary,
            f"版本更新檢查：{version_output.current_version} -> {version_output.latest_version or 'unknown'} ({version_output.upgrade_recommendation})",
        ]
    )
    fix_and_optimization_actions = _dedupe_non_empty_strings(
        [
            *risk_output.immediate_actions,
            *[action for issue in risk_output.high_priority_risks for action in issue.fix_actions],
            *version_output.regression_test_checklist,
        ]
    )
    recommended_execution_order = fix_and_optimization_actions[:] or _dedupe_non_empty_strings(
        [
            "先確認版本資訊與 CLI update summary 一致。",
            "再依高優先風險逐項修復與驗證。",
        ]
    )
    open_questions = _dedupe_non_empty_strings(
        [
            *version_output.assumptions,
            *risk_output.assumptions,
            f"Agent 未回傳可解析文字，巡檢報告改採 deterministic fallback：{error.detail or error.message}",
        ]
    )
    draft = WorkflowSystemInspectionReportDraft(
        title="系統巡檢與風險評估報告",
        inspection_summary=inspection_summary,
        fix_and_optimization_actions=fix_and_optimization_actions,
        open_questions=open_questions,
        recommended_execution_order=recommended_execution_order,
        telegram_summary="",
        markdown="",
    )
    return _coerce_system_report_output(draft, version_output, log_review_output, risk_output)


def _build_system_risk_output_fallback(
    *,
    version_output: WorkflowSystemInspectionVersionOutput,
    log_review_output: WorkflowSystemInspectionLogReviewOutput,
    error: OpenClawServiceError,
) -> WorkflowSystemInspectionRiskOutput:
    prioritized_issues = sorted(
        log_review_output.issues,
        key=lambda issue: (_severity_rank(issue.severity), issue.priority, -issue.frequency),
    )
    high_priority_risks = [
        issue for issue in prioritized_issues if issue.severity in {"critical", "high"} or issue.priority in {"p0", "p1"}
    ][:5]
    if not high_priority_risks:
        high_priority_risks = prioritized_issues[:3]

    immediate_actions = _dedupe_non_empty_strings(
        [
            *[action for issue in high_priority_risks for action in issue.fix_actions],
            *[action for issue in high_priority_risks for action in issue.optimization_actions],
            *version_output.regression_test_checklist,
        ]
    )
    if not immediate_actions and version_output.latest_version and version_output.latest_version != version_output.current_version:
        immediate_actions = [
            "先修復目前高優先風險，再決定是否進行版本升級。",
            "完成 staging 回歸驗證後再評估升級正式環境。",
        ]

    summary_parts = []
    if high_priority_risks:
        top_issue = high_priority_risks[0]
        summary_parts.append(
            f"目前已整理出 {len(high_priority_risks)} 項高優先風險，最急迫的是 {truncate_text(top_issue.description, max_length=80)}。"
        )
    if log_review_output.summary:
        summary_parts.append(truncate_text(log_review_output.summary, max_length=140))
    if version_output.latest_version and version_output.latest_version != version_output.current_version:
        summary_parts.append(
            f"版本面目前建議 {version_output.upgrade_recommendation}，先確認 {version_output.current_version} 到 {version_output.latest_version} 的相容性。"
        )
    summary_parts.append("Agent 未回傳可解析文字，本次風險結論改採 deterministic fallback。")

    assumptions = _dedupe_non_empty_strings(
        [
            *version_output.assumptions,
            f"fallback reason: {error.detail or error.message}",
        ]
    )
    verification_steps = _dedupe_non_empty_strings(
        [
            *[step for issue in high_priority_risks for step in issue.verification_steps],
            *version_output.verification_steps,
            "修復後重新執行 System Inspection，確認 risk_assessment 與 report 皆能完成。",
        ]
    )

    return WorkflowSystemInspectionRiskOutput(
        summary=" ".join(summary_parts),
        upgrade_recommendation=version_output.upgrade_recommendation,
        high_priority_risks=high_priority_risks,
        immediate_actions=immediate_actions,
        assumptions=assumptions,
        verification_steps=verification_steps,
    )


def _build_development_handoff_output_fallback(
    *,
    problem_output: WorkflowDevelopmentProblemDefinitionOutput,
    requirements_output: WorkflowDevelopmentRequirementsOutput,
    design_output: WorkflowDevelopmentDesignOutput,
    technology_output: WorkflowDevelopmentTechnologySelectionOutput,
    planning_output: WorkflowDevelopmentTaskPlanningOutput,
    implementation_output: WorkflowDevelopmentImplementationOutput,
    testing_output: WorkflowDevelopmentTestingOutput,
    optimization_output: WorkflowDevelopmentOptimizationOutput,
    error: OpenClawServiceError,
) -> WorkflowDevelopmentExecutionReportPayload:
    requirements_analysis = _dedupe_non_empty_strings(
        [
            *requirements_output.functional_requirements,
            *requirements_output.non_functional_requirements,
            *requirements_output.risks,
        ]
    )
    solution_design = _dedupe_non_empty_strings(
        [
            *design_output.modules,
            *design_output.flows,
            *design_output.interfaces,
            *design_output.data_structures,
        ]
    )
    development_results = _dedupe_non_empty_strings(
        [
            implementation_output.summary,
            *implementation_output.completed_items,
            *implementation_output.changed_modules,
            *implementation_output.notable_decisions,
        ]
    )
    test_results = _dedupe_non_empty_strings(
        [
            testing_output.summary,
            *testing_output.test_results,
            *testing_output.test_cases,
        ]
    )
    risks_and_todos = _dedupe_non_empty_strings(
        [
            *testing_output.remaining_gaps,
            *optimization_output.follow_up_todos,
            *optimization_output.known_limits,
            f"handoff fallback reason: {error.detail or error.message}",
        ]
    )
    final_summary_parts = _dedupe_non_empty_strings(
        [
            optimization_output.summary,
            implementation_output.summary,
            testing_output.summary,
            "Main Agent 未回傳可解析文字，handoff 改採 deterministic fallback 匯總前序工程階段成果。",
        ]
    )

    return WorkflowDevelopmentExecutionReportPayload(
        task_name=problem_output.task_name,
        problem_definition=problem_output.problem_background,
        requirements_analysis=requirements_analysis,
        solution_design=solution_design,
        technology_selection=technology_output.selections,
        task_breakdown_schedule=planning_output.tasks,
        development_results=development_results,
        test_results=test_results,
        risks_and_todos=risks_and_todos,
        final_summary=" ".join(final_summary_parts),
    )


def _build_development_delivery_markdown(
    *,
    run: WorkflowRunResponse,
    report_payload: WorkflowDevelopmentExecutionReportPayload,
) -> str:
    sections = [
        f"# Development Workflow Report\n\n## Task\n- {report_payload.task_name}",
        f"## Final Summary\n{report_payload.final_summary}",
        f"## Problem Definition\n{report_payload.problem_definition}",
        _render_markdown_list("Requirements Analysis", report_payload.requirements_analysis),
        _render_markdown_list("Solution Design", report_payload.solution_design),
        _render_markdown_list("Development Results", report_payload.development_results),
        _render_markdown_list("Test Results", report_payload.test_results),
        _render_markdown_list("Risks And Todos", report_payload.risks_and_todos),
        _render_development_technology_markdown(report_payload.technology_selection),
        _render_development_schedule_markdown(report_payload.task_breakdown_schedule),
        f"## Run\n- Workflow ID: {run.id}\n- Instance ID: {run.instance_id}\n- OpenClaw URL: /openclaw/development?instanceId={run.instance_id}&runId={run.id}",
    ]
    return "\n\n".join(section for section in sections if section.strip())


def _build_failed_development_delivery_markdown(run: WorkflowRunResponse) -> str:
    recent_stage_event = next((event for event in reversed(run.events) if event.stage_key == run.current_stage), None)
    summary = run.error_message or (
        recent_stage_event.message.strip() if recent_stage_event and recent_stage_event.message.strip() else "Development workflow failed."
    )
    message_lines = [
        "# Development Workflow Failed",
        "",
        "## Task",
        f"- {run.input_payload.get('task_name') or '未命名工程任務'}",
        f"- Workflow ID: {run.id}",
        f"- Instance ID: {run.instance_id}",
        f"- Failed Stage: {run.current_stage or 'unknown'}",
        "",
        "## Failure Summary",
        str(summary).strip(),
    ]
    if recent_stage_event and recent_stage_event.message.strip():
        message_lines.extend(["", "## Latest Event", recent_stage_event.message.strip()])
    message_lines.extend(["", f"OpenClaw URL: /openclaw/development?instanceId={run.instance_id}&runId={run.id}"])
    return "\n".join(line for line in message_lines if line is not None)


def _render_markdown_list(title: str, items: list[str]) -> str:
    cleaned = _dedupe_non_empty_strings(items)
    if not cleaned:
        return ""
    body = "\n".join(f"- {item}" for item in cleaned[:8])
    return f"## {title}\n{body}"


def _render_development_technology_markdown(items: list[Any]) -> str:
    if not items:
        return ""
    rows = []
    for item in items[:8]:
        if not hasattr(item, "category"):
            continue
        rows.append(f"- {item.category}: {item.choice} ({item.reason})")
    return f"## Technology Selection\n" + "\n".join(rows) if rows else ""


def _render_development_schedule_markdown(items: list[Any]) -> str:
    if not items:
        return ""
    rows = []
    for item in items[:8]:
        if not hasattr(item, "title"):
            continue
        rows.append(f"- {item.title} [{item.priority} / {item.estimate}] {item.description}".strip())
    return f"## Task Breakdown\n" + "\n".join(rows) if rows else ""


def _build_system_log_review_output_fallback(
    *,
    inspection_config: OpenClawSystemInspectionConfigResponse,
    aggregated_issues: list[WorkflowSystemInspectionLogIssue],
    snapshot_output: WorkflowSystemInspectionSnapshotOutput,
    error: OpenClawServiceError,
) -> WorkflowSystemInspectionLogReviewOutput:
    summary_parts = []
    if aggregated_issues:
        summary_parts.append(
            f"已從 operation logs、workflow failures 與 gateway logs 整理出 {len(aggregated_issues)} 項可觀測問題。"
        )
        top_issue = aggregated_issues[0]
        summary_parts.append(f"目前最需要先處理的是 {truncate_text(top_issue.description, max_length=96)}。")
    else:
        summary_parts.append("近期日誌未聚合出明確高優先問題。")

    if snapshot_output.recent_workflow_failures:
        summary_parts.append(f"近期 workflow failure 共 {len(snapshot_output.recent_workflow_failures)} 筆。")
    if snapshot_output.gateway_log_excerpt:
        summary_parts.append(f"gateway logs 摘錄 {len(snapshot_output.gateway_log_excerpt)} 筆。")
    summary_parts.append("Agent 未回傳可解析文字，本次日誌巡檢改採 deterministic fallback。")
    summary_parts.append(f"fallback reason: {error.detail or error.message}")

    return WorkflowSystemInspectionLogReviewOutput(
        summary=" ".join(summary_parts),
        issues=aggregated_issues[:8],
        log_window_hours=inspection_config.log_review_window_hours,
        inspected_log_count=(
            len(snapshot_output.recent_operation_logs)
            + len(snapshot_output.recent_workflow_failures)
            + len(snapshot_output.gateway_log_excerpt)
        ),
    )


def _optional_clean_string(value: Any) -> str | None:
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    return None


def _dedupe_non_empty_strings(values: list[Any]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _optional_clean_string(value)
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return deduped


def _build_system_log_review_prompt(
    inspection_config: OpenClawSystemInspectionConfigResponse,
    aggregated_issues: list[WorkflowSystemInspectionLogIssue],
) -> str:
    return (
        "你是 OpenClaw 系統巡檢的日誌代理。請根據已聚合的錯誤、warning、timeout、retry、delivery 失敗模式，整理問題清單。\n"
        f"巡檢設定：{json.dumps(inspection_config.model_dump(mode='json'), ensure_ascii=False)}\n"
        f"已聚合問題：{json.dumps([issue.model_dump() for issue in aggregated_issues], ensure_ascii=False)}\n"
        "重點是先給具體修復方案與優先順序，不只描述現象。\n"
        "只輸出 JSON。\n"
        "{\n"
        '  "summary": "...",\n'
        '  "issues": [{"issue_key":"...", "category":"error|warning|timeout|retry|crash|performance|security|config_drift", "description":"...", "frequency":1, "first_seen_at":"...", "last_seen_at":"...", "possible_root_causes":["..."], "affected_components":["..."], "impact_scope":"...", "severity":"critical|high|medium|low", "fix_actions":["..."], "optimization_actions":["..."], "priority":"p0|p1|p2|p3", "assumptions":["..."], "verification_steps":["..."]}],\n'
        '  "log_window_hours": 24,\n'
        '  "inspected_log_count": 0\n'
        "}\n"
        "不要輸出額外文字。"
    )


def _build_system_risk_assessment_prompt(
    version_output: WorkflowSystemInspectionVersionOutput,
    log_review_output: WorkflowSystemInspectionLogReviewOutput,
) -> str:
    return (
        "你是 OpenClaw 系統巡檢的風險評估代理。請整合版本風險與日誌問題，回答『是否升級』與『先修什麼』。\n"
        f"版本檢查：{json.dumps(version_output.model_dump(), ensure_ascii=False)}\n"
        f"日誌巡檢：{json.dumps(log_review_output.model_dump(), ensure_ascii=False)}\n"
        "只輸出 JSON。\n"
        "{\n"
        '  "summary": "...",\n'
        '  "upgrade_recommendation": "upgrade_now|test_before_upgrade|do_not_upgrade_yet",\n'
        '  "high_priority_risks": [{"issue_key":"...", "category":"error", "description":"...", "frequency":1, "severity":"high", "priority":"p1", "possible_root_causes":["..."], "affected_components":["..."], "impact_scope":"...", "fix_actions":["..."], "optimization_actions":["..."], "assumptions":["..."], "verification_steps":["..."]}],\n'
        '  "immediate_actions": ["..."],\n'
        '  "assumptions": ["..."],\n'
        '  "verification_steps": ["..."]\n'
        "}\n"
        "不要輸出額外文字。"
    )


def _build_system_report_prompt(
    version_output: dict[str, Any],
    log_review_output: dict[str, Any],
    risk_output: dict[str, Any],
) -> str:
    return (
        "你是 OpenClaw 系統巡檢的報告代理。請根據已完成的版本檢查、日誌巡檢、風險評估，整理出可支援『是否升級』與『先修什麼』的決策摘要。\n"
        "不要重複輸出完整的版本檢查、日誌問題清單或高優先級風險物件，後端會自動附上那些結構化欄位。\n"
        f"版本檢查摘要：{json.dumps(version_output, ensure_ascii=False)}\n"
        f"日誌巡檢摘要：{json.dumps(log_review_output, ensure_ascii=False)}\n"
        f"風險評估摘要：{json.dumps(risk_output, ensure_ascii=False)}\n"
        "請專注輸出：巡檢總結、修復與優化建議、待確認事項、建議執行順序，以及 Telegram 摘要。\n"
        "markdown 欄位可留空，後端會自動組裝完整 Markdown 報告。\n"
        "只輸出 JSON。\n"
        "{\n"
        '  "title": "系統巡檢與風險評估報告",\n'
        '  "inspection_summary": ["..."],\n'
        '  "fix_and_optimization_actions": ["..."],\n'
        '  "open_questions": ["..."],\n'
        '  "recommended_execution_order": ["..."],\n'
        '  "telegram_summary": "...",\n'
        '  "markdown": ""\n'
        "}\n"
        "不要輸出額外文字。"
    )


def _build_development_problem_definition_prompt(request_payload: dict[str, Any]) -> str:
    return (
        "你是全端工程師 Agent。這是 Development Workflow 的第一階段，你不可跳過分析、設計與測試導向思維。\n"
        f"原始任務：{json.dumps(request_payload, ensure_ascii=False)}\n"
        "請先明確問題背景、目標、限制與成功標準。只輸出 JSON。\n"
        "{\n"
        '  "task_name": "...",\n'
        '  "summary": "...",\n'
        '  "problem_background": "...",\n'
        '  "goal": "...",\n'
        '  "constraints": ["..."],\n'
        '  "success_criteria": ["..."]\n'
        "}\n"
        "不要輸出額外文字。"
    )


def _build_development_requirements_prompt(problem_output: WorkflowDevelopmentProblemDefinitionOutput) -> str:
    return (
        "你是全端工程師 Agent，現在處於需求分析階段。請基於已確認的問題定義，分析功能需求、非功能需求、風險與依賴項。\n"
        f"問題定義：{json.dumps(problem_output.model_dump(), ensure_ascii=False)}\n"
        "只輸出 JSON。\n"
        "{\n"
        '  "summary": "...",\n'
        '  "functional_requirements": ["..."],\n'
        '  "non_functional_requirements": ["..."],\n'
        '  "risks": ["..."],\n'
        '  "dependencies": ["..."]\n'
        "}\n"
        "不要輸出額外文字。"
    )


def _build_development_design_prompt(
    problem_output: WorkflowDevelopmentProblemDefinitionOutput,
    requirements_output: WorkflowDevelopmentRequirementsOutput,
) -> str:
    return (
        "你是全端工程師 Agent，現在處於方案設計階段。請設計可落地的模組、流程、資料結構與介面。\n"
        f"問題定義：{json.dumps(problem_output.model_dump(), ensure_ascii=False)}\n"
        f"需求分析：{json.dumps(requirements_output.model_dump(), ensure_ascii=False)}\n"
        "只輸出 JSON。\n"
        "{\n"
        '  "summary": "...",\n'
        '  "modules": ["..."],\n'
        '  "flows": ["..."],\n'
        '  "data_structures": ["..."],\n'
        '  "interfaces": ["..."]\n'
        "}\n"
        "不要輸出額外文字。"
    )


def _build_development_technology_prompt(
    problem_output: WorkflowDevelopmentProblemDefinitionOutput,
    requirements_output: WorkflowDevelopmentRequirementsOutput,
    design_output: WorkflowDevelopmentDesignOutput,
) -> str:
    return (
        "你是全端工程師 Agent，現在處於技術選型階段。請說明採用哪些技術與原因。\n"
        f"問題定義：{json.dumps(problem_output.model_dump(), ensure_ascii=False)}\n"
        f"需求分析：{json.dumps(requirements_output.model_dump(), ensure_ascii=False)}\n"
        f"方案設計：{json.dumps(design_output.model_dump(), ensure_ascii=False)}\n"
        "只輸出 JSON。\n"
        "{\n"
        '  "summary": "...",\n'
        '  "selections": [{"category":"frontend|backend|database|testing|deployment|tooling", "choice":"...", "reason":"..."}]\n'
        "}\n"
        "不要輸出額外文字。"
    )


def _build_development_task_planning_prompt(
    problem_output: WorkflowDevelopmentProblemDefinitionOutput,
    requirements_output: WorkflowDevelopmentRequirementsOutput,
    design_output: WorkflowDevelopmentDesignOutput,
    technology_output: WorkflowDevelopmentTechnologySelectionOutput,
) -> str:
    return (
        "你是全端工程師 Agent，現在處於任務拆分 / 排期階段。請安排優先級與預估排期。\n"
        f"問題定義：{json.dumps(problem_output.model_dump(), ensure_ascii=False)}\n"
        f"需求分析：{json.dumps(requirements_output.model_dump(), ensure_ascii=False)}\n"
        f"方案設計：{json.dumps(design_output.model_dump(), ensure_ascii=False)}\n"
        f"技術選型：{json.dumps(technology_output.model_dump(), ensure_ascii=False)}\n"
        "只輸出 JSON。\n"
        "{\n"
        '  "summary": "...",\n'
        '  "tasks": [{"title":"...", "priority":"p0|p1|p2|p3", "estimate":"...", "description":"..."}],\n'
        '  "schedule": ["..."]\n'
        "}\n"
        "不要輸出額外文字。"
    )


def _build_development_implementation_prompt(
    problem_output: WorkflowDevelopmentProblemDefinitionOutput,
    design_output: WorkflowDevelopmentDesignOutput,
    planning_output: WorkflowDevelopmentTaskPlanningOutput,
) -> str:
    return (
        "你是全端工程師 Agent，現在處於開發階段。請依照既有設計與排期完成實作摘要。\n"
        f"問題定義：{json.dumps(problem_output.model_dump(), ensure_ascii=False)}\n"
        f"方案設計：{json.dumps(design_output.model_dump(), ensure_ascii=False)}\n"
        f"任務拆分：{json.dumps(planning_output.model_dump(), ensure_ascii=False)}\n"
        "只輸出 JSON。\n"
        "{\n"
        '  "summary": "...",\n'
        '  "completed_items": ["..."],\n'
        '  "changed_modules": ["..."],\n'
        '  "notable_decisions": ["..."]\n'
        "}\n"
        "不要輸出額外文字。"
    )


def _build_development_testing_prompt(
    problem_output: WorkflowDevelopmentProblemDefinitionOutput,
    planning_output: WorkflowDevelopmentTaskPlanningOutput,
    implementation_output: WorkflowDevelopmentImplementationOutput,
) -> str:
    return (
        "你是全端工程師 Agent，現在處於持續測試階段。請基於實作結果整理測試案例、測試結果與剩餘缺口。\n"
        f"問題定義：{json.dumps(problem_output.model_dump(), ensure_ascii=False)}\n"
        f"任務拆分：{json.dumps(planning_output.model_dump(), ensure_ascii=False)}\n"
        f"開發結果：{json.dumps(implementation_output.model_dump(), ensure_ascii=False)}\n"
        "只輸出 JSON。\n"
        "{\n"
        '  "summary": "...",\n'
        '  "test_cases": ["..."],\n'
        '  "test_results": ["..."],\n'
        '  "validation_status": "passed|partial|failed",\n'
        '  "remaining_gaps": ["..."]\n'
        "}\n"
        "不要輸出額外文字。"
    )


def _build_development_optimization_prompt(
    planning_output: WorkflowDevelopmentTaskPlanningOutput,
    implementation_output: WorkflowDevelopmentImplementationOutput,
    testing_output: WorkflowDevelopmentTestingOutput,
) -> str:
    return (
        "你是全端工程師 Agent，現在處於迭代優化階段。請根據測試結果與回饋整理可執行的優化。\n"
        f"任務拆分：{json.dumps(planning_output.model_dump(), ensure_ascii=False)}\n"
        f"開發結果：{json.dumps(implementation_output.model_dump(), ensure_ascii=False)}\n"
        f"測試結果：{json.dumps(testing_output.model_dump(), ensure_ascii=False)}\n"
        "只輸出 JSON。\n"
        "{\n"
        '  "summary": "...",\n'
        '  "improvements": ["..."],\n'
        '  "follow_up_todos": ["..."],\n'
        '  "known_limits": ["..."]\n'
        "}\n"
        "不要輸出額外文字。"
    )


def _build_development_handoff_prompt(
    problem_output: WorkflowDevelopmentProblemDefinitionOutput,
    requirements_output: WorkflowDevelopmentRequirementsOutput,
    design_output: WorkflowDevelopmentDesignOutput,
    technology_output: WorkflowDevelopmentTechnologySelectionOutput,
    planning_output: WorkflowDevelopmentTaskPlanningOutput,
    implementation_output: WorkflowDevelopmentImplementationOutput,
    testing_output: WorkflowDevelopmentTestingOutput,
    optimization_output: WorkflowDevelopmentOptimizationOutput,
) -> str:
    return (
        "你是 Main Agent，現在處於 Development Workflow 的 handoff 階段。請接收全端工程師 Agent 的完整成果，整理成固定結構化報告。\n"
        f"問題定義：{json.dumps(problem_output.model_dump(), ensure_ascii=False)}\n"
        f"需求分析：{json.dumps(requirements_output.model_dump(), ensure_ascii=False)}\n"
        f"方案設計：{json.dumps(design_output.model_dump(), ensure_ascii=False)}\n"
        f"技術選型：{json.dumps(technology_output.model_dump(), ensure_ascii=False)}\n"
        f"任務拆分：{json.dumps(planning_output.model_dump(), ensure_ascii=False)}\n"
        f"開發結果：{json.dumps(implementation_output.model_dump(), ensure_ascii=False)}\n"
        f"測試結果：{json.dumps(testing_output.model_dump(), ensure_ascii=False)}\n"
        f"優化結果：{json.dumps(optimization_output.model_dump(), ensure_ascii=False)}\n"
        "只輸出 JSON。\n"
        "{\n"
        '  "task_name": "...",\n'
        '  "problem_definition": "...",\n'
        '  "requirements_analysis": ["..."],\n'
        '  "solution_design": ["..."],\n'
        '  "technology_selection": [{"category":"...", "choice":"...", "reason":"..."}],\n'
        '  "task_breakdown_schedule": [{"title":"...", "priority":"p0|p1|p2|p3", "estimate":"...", "description":"..."}],\n'
        '  "development_results": ["..."],\n'
        '  "test_results": ["..."],\n'
        '  "risks_and_todos": ["..."],\n'
        '  "final_summary": "..."\n'
        "}\n"
        "不要輸出額外文字。"
    )


def _compact_news_source_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": truncate_text(str(item.get("title") or ""), max_length=140),
        "snippet": truncate_text(str(item.get("snippet") or ""), max_length=240),
        "source_name": truncate_text(str(item.get("source_name") or ""), max_length=80),
        "reason": truncate_text(str(item.get("reason") or ""), max_length=120),
        "published_at": item.get("published_at"),
        "url": item.get("url"),
        "domain": item.get("domain"),
    }


def _compact_news_story(story: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": truncate_text(str(story.get("title") or ""), max_length=140),
        "summary": truncate_text(str(story.get("summary") or ""), max_length=180),
        "importance_reason": truncate_text(str(story.get("importance_reason") or ""), max_length=120),
        "possible_impact": truncate_text(str(story.get("possible_impact") or ""), max_length=140),
        "sources": [
            _compact_news_source_item(source)
            for source in (story.get("sources") or [])[:2]
            if isinstance(source, dict)
        ],
        "published_at": story.get("published_at"),
        "background": truncate_text(str(story.get("background") or ""), max_length=120),
        "watch_points": [truncate_text(str(point), max_length=60) for point in (story.get("watch_points") or [])[:3]],
        "event_key": truncate_text(str(story.get("event_key") or ""), max_length=80),
    }


def _compact_news_search_output(search_output: WorkflowNewsSearchOutput) -> dict[str, Any]:
    payload = search_output.model_dump()
    payload["summary"] = truncate_text(str(payload.get("summary") or ""), max_length=240)
    payload["raw_sources"] = [_compact_news_source_item(item) for item in payload.get("raw_sources", [])[:8]]
    return payload


def _fallback_news_dedupe_output(search_output: WorkflowNewsSearchOutput) -> WorkflowNewsDedupeOutput:
    grouped: dict[str, list[WorkflowNewsSourceItem]] = {}
    story_titles: dict[str, str] = {}

    for source in search_output.raw_sources:
        event_key = _guess_news_event_key(source)
        grouped.setdefault(event_key, []).append(source)
        story_titles.setdefault(event_key, source.title)

    unique_stories: list[WorkflowNewsStory] = []
    for event_key, sources in list(grouped.items())[:6]:
        primary = sources[0]
        summary = truncate_text(primary.snippet or primary.reason or primary.title, max_length=180)
        unique_stories.append(
            WorkflowNewsStory(
                title=truncate_text(story_titles.get(event_key) or primary.title, max_length=140),
                summary=summary,
                importance_reason=truncate_text(primary.reason or "來自主流或高相關來源的候選新聞。", max_length=120),
                possible_impact=truncate_text("建議人工複核是否需要併入今日重點與後續追蹤。", max_length=140),
                sources=sources[:3],
                published_at=primary.published_at,
                background=truncate_text(primary.snippet or "", max_length=120),
                watch_points=[
                    "檢查是否與既有事件重複",
                    "確認是否有後續官方或主流來源跟進",
                ],
                event_key=event_key,
            )
        )

    removed_duplicates = max(0, len(search_output.raw_sources) - len(unique_stories))
    return WorkflowNewsDedupeOutput(
        summary="去重代理逾時，已改用本地規則整理候選事件。",
        unique_stories=unique_stories,
        removed_duplicates=removed_duplicates,
        dedupe_notes=[
            "本次結果由本地 fallback 規則生成，建議人工複核重複事件合併品質。",
            "如需更精準去重，可稍後重跑或縮小新聞主題範圍。",
        ],
    )


def _guess_news_event_key(source: WorkflowNewsSourceItem) -> str:
    title = (source.title or "").strip().lower()
    normalized = "".join(character if character.isalnum() else " " for character in title)
    tokens = [token for token in normalized.split() if token][:8]
    if tokens:
        return "-".join(tokens[:6])
    if source.url:
        return truncate_text(source.url, max_length=80)
    if source.domain:
        return truncate_text(source.domain, max_length=80)
    return "news-event"


def _compact_news_monitor_output(monitor_output: WorkflowNewsMonitorOutput) -> dict[str, Any]:
    payload = monitor_output.model_dump()
    payload["goal_summary"] = truncate_text(str(payload.get("goal_summary") or ""), max_length=180)
    payload["tracking_scope"] = [truncate_text(str(item), max_length=80) for item in payload.get("tracking_scope", [])[:4]]
    payload["search_queries"] = [truncate_text(str(item), max_length=80) for item in payload.get("search_queries", [])[:4]]
    payload["watch_focus"] = [truncate_text(str(item), max_length=80) for item in payload.get("watch_focus", [])[:4]]
    return payload


def _compact_news_dedupe_output(dedupe_output: WorkflowNewsDedupeOutput) -> dict[str, Any]:
    payload = dedupe_output.model_dump()
    payload["summary"] = truncate_text(str(payload.get("summary") or ""), max_length=240)
    payload["unique_stories"] = [_compact_news_story(story) for story in payload.get("unique_stories", [])[:4]]
    payload["dedupe_notes"] = [truncate_text(str(note), max_length=100) for note in payload.get("dedupe_notes", [])[:4]]
    return payload


def _compact_news_rank_output(rank_output: WorkflowNewsRankOutput) -> dict[str, Any]:
    payload = rank_output.model_dump()
    payload["summary"] = truncate_text(str(payload.get("summary") or ""), max_length=240)
    payload["top_stories"] = [_compact_news_story(story) for story in payload.get("top_stories", [])[:3]]
    payload["other_stories"] = [_compact_news_story(story) for story in payload.get("other_stories", [])[:3]]
    payload["trend_summary"] = truncate_text(str(payload.get("trend_summary") or ""), max_length=180)
    payload["watch_items"] = [truncate_text(str(item), max_length=80) for item in payload.get("watch_items", [])[:4]]
    payload["uncertainties"] = [truncate_text(str(item), max_length=80) for item in payload.get("uncertainties", [])[:4]]
    return payload


def _compact_news_brief_dedupe_snapshot(dedupe_output: WorkflowNewsDedupeOutput) -> dict[str, Any]:
    return {
        "summary": truncate_text(dedupe_output.summary, max_length=180),
        "removed_duplicates": dedupe_output.removed_duplicates,
        "dedupe_notes": [truncate_text(str(note), max_length=100) for note in dedupe_output.dedupe_notes[:4]],
    }


def _compact_daily_news_config(config: OpenClawDailyNewsConfigResponse) -> dict[str, Any]:
    return {
        "brief_name": config.brief_name,
        "topic": truncate_text(config.topic, max_length=120),
        "keywords": config.keywords[:6],
        "industries": config.industries[:4],
        "regions": config.regions[:4],
        "people": config.people[:6],
        "companies": config.companies[:6],
        "source_domains": config.source_domains[:6],
        "source_urls": config.source_urls[:4],
        "must_include": config.must_include[:6],
        "must_exclude": config.must_exclude[:6],
        "focus_points": config.focus_points[:6],
        "output_format": config.output_format,
    }


def _compact_system_issue(issue: WorkflowSystemInspectionLogIssue) -> dict[str, Any]:
    return {
        "issue_key": truncate_text(issue.issue_key, max_length=80),
        "category": issue.category,
        "description": truncate_text(issue.description, max_length=180),
        "frequency": issue.frequency,
        "severity": issue.severity,
        "priority": issue.priority,
        "affected_components": [truncate_text(str(item), max_length=60) for item in issue.affected_components[:4]],
        "fix_actions": [truncate_text(str(item), max_length=80) for item in issue.fix_actions[:3]],
        "assumptions": [truncate_text(str(item), max_length=80) for item in issue.assumptions[:2]],
        "verification_steps": [truncate_text(str(item), max_length=80) for item in issue.verification_steps[:2]],
    }


def _compact_system_version_output(version_output: WorkflowSystemInspectionVersionOutput) -> dict[str, Any]:
    return {
        "current_version": version_output.current_version,
        "latest_version": version_output.latest_version,
        "latest_version_status": version_output.latest_version_status,
        "update_available": version_output.update_available,
        "channel_label": version_output.channel_label,
        "version_source": version_output.version_source,
        "version_gap": truncate_text(version_output.version_gap, max_length=120),
        "upgrade_recommendation": version_output.upgrade_recommendation,
        "release_summary": [truncate_text(str(item), max_length=140) for item in version_output.release_summary[:4]],
        "compatibility_risks": [truncate_text(str(item), max_length=140) for item in version_output.compatibility_risks[:4]],
        "regression_test_checklist": [truncate_text(str(item), max_length=100) for item in version_output.regression_test_checklist[:4]],
        "assumptions": [truncate_text(str(item), max_length=100) for item in version_output.assumptions[:3]],
        "verification_steps": [truncate_text(str(item), max_length=100) for item in version_output.verification_steps[:3]],
    }


def _compact_system_log_review_output(log_review_output: WorkflowSystemInspectionLogReviewOutput) -> dict[str, Any]:
    return {
        "summary": truncate_text(log_review_output.summary, max_length=220),
        "log_window_hours": log_review_output.log_window_hours,
        "inspected_log_count": log_review_output.inspected_log_count,
        "issues": [_compact_system_issue(issue) for issue in log_review_output.issues[:4]],
    }


def _compact_system_risk_output(risk_output: WorkflowSystemInspectionRiskOutput) -> dict[str, Any]:
    return {
        "summary": truncate_text(risk_output.summary, max_length=220),
        "upgrade_recommendation": risk_output.upgrade_recommendation,
        "high_priority_risks": [_compact_system_issue(issue) for issue in risk_output.high_priority_risks[:4]],
        "immediate_actions": [truncate_text(str(item), max_length=100) for item in risk_output.immediate_actions[:5]],
        "assumptions": [truncate_text(str(item), max_length=100) for item in risk_output.assumptions[:3]],
        "verification_steps": [truncate_text(str(item), max_length=100) for item in risk_output.verification_steps[:3]],
    }


def _build_system_inspection_telegram_summary(
    title: str,
    version_output: WorkflowSystemInspectionVersionOutput,
    risk_output: WorkflowSystemInspectionRiskOutput,
    report_draft: WorkflowSystemInspectionReportDraft,
) -> str:
    lines = [title, f"升級建議：{version_output.upgrade_recommendation}"]
    lines.extend([f"- {item}" for item in (report_draft.inspection_summary or [risk_output.summary])[:3]])
    if risk_output.high_priority_risks:
        lines.append("高優先級風險：")
        lines.extend(
            [
                f"- {issue.priority.upper()} {truncate_text(issue.description, max_length=90)}"
                for issue in risk_output.high_priority_risks[:3]
            ]
        )
    if report_draft.recommended_execution_order:
        lines.append("建議順序：")
        lines.extend([f"- {item}" for item in report_draft.recommended_execution_order[:3]])
    return "\n".join(lines)


def _build_system_inspection_markdown(
    title: str,
    version_output: WorkflowSystemInspectionVersionOutput,
    log_review_output: WorkflowSystemInspectionLogReviewOutput,
    risk_output: WorkflowSystemInspectionRiskOutput,
    report_draft: WorkflowSystemInspectionReportDraft,
) -> str:
    sections = [
        f"# {title}",
        "",
        "## 1. 巡檢總結",
        *[f"- {item}" for item in report_draft.inspection_summary],
        "",
        "## 2. 版本更新檢查",
        f"- 目前版本：{version_output.current_version}",
        f"- 最新版本：{version_output.latest_version or 'unknown'}",
        f"- 升級建議：{version_output.upgrade_recommendation}",
        *[f"- {item}" for item in version_output.release_summary[:5]],
        "",
        "## 3. 系統日誌問題清單",
        f"- 巡檢視窗：{log_review_output.log_window_hours} 小時",
        f"- 檢查筆數：{log_review_output.inspected_log_count}",
        *[
            f"- [{issue.priority.upper()}] {issue.description}"
            for issue in log_review_output.issues[:6]
        ],
        "",
        "## 4. 高優先級風險",
        *[
            f"- [{issue.priority.upper()}] {issue.description}"
            for issue in risk_output.high_priority_risks[:5]
        ],
        "",
        "## 5. 修復與優化建議",
        *[f"- {item}" for item in report_draft.fix_and_optimization_actions],
        "",
        "## 6. 待確認事項",
        *[f"- {item}" for item in report_draft.open_questions],
        "",
        "## 7. 建議執行順序",
        *[f"{index + 1}. {item}" for index, item in enumerate(report_draft.recommended_execution_order)],
    ]
    return "\n".join(section for section in sections if section is not None)


def _coerce_system_report_output(
    report_draft: WorkflowSystemInspectionReportDraft,
    version_output: WorkflowSystemInspectionVersionOutput,
    log_review_output: WorkflowSystemInspectionLogReviewOutput,
    risk_output: WorkflowSystemInspectionRiskOutput,
) -> WorkflowSystemInspectionReportPayload:
    title = report_draft.title.strip() or "系統巡檢與風險評估報告"
    inspection_summary = report_draft.inspection_summary or [risk_output.summary or log_review_output.summary]
    fix_and_optimization_actions = report_draft.fix_and_optimization_actions or risk_output.immediate_actions
    recommended_execution_order = report_draft.recommended_execution_order or risk_output.immediate_actions
    telegram_summary = report_draft.telegram_summary.strip() or _build_system_inspection_telegram_summary(
        title,
        version_output,
        risk_output,
        report_draft,
    )
    markdown = report_draft.markdown.strip() or _build_system_inspection_markdown(
        title,
        version_output,
        log_review_output,
        risk_output,
        report_draft,
    )
    return WorkflowSystemInspectionReportPayload(
        title=title,
        inspection_summary=inspection_summary,
        version_update_check=version_output,
        log_review=log_review_output,
        high_priority_risks=risk_output.high_priority_risks,
        fix_and_optimization_actions=fix_and_optimization_actions,
        open_questions=report_draft.open_questions,
        recommended_execution_order=recommended_execution_order,
        telegram_summary=telegram_summary,
        markdown=markdown,
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
    if run.final_news_brief is not None:
        return run.final_news_brief.model_dump()
    if run.final_system_inspection is not None:
        return run.final_system_inspection.model_dump()
    if run.final_development_report is not None:
        return run.final_development_report.model_dump()
    return None


def _specialist_snapshot(config: OpenClawWorkflowConfigResponse) -> dict[str, Any]:
    return {
        "controller_agent_id": config.controller_agent_id,
        "search_agent_id": config.search_agent_id,
        "analysis_agent_id": config.analysis_agent_id,
        "report_agent_id": config.report_agent_id,
        "specialist_agents": config.specialist_agents.model_dump(),
        "routing_rules": [rule.model_dump() for rule in config.routing_rules],
        "handoff_policy": config.handoff_policy.model_dump(),
    }


def _resolve_specialist_agent(config: OpenClawWorkflowConfigResponse, specialist_key: str, fallback_agent_id: str) -> str:
    specialist_binding = getattr(config.specialist_agents, specialist_key)
    if specialist_binding.enabled and specialist_binding.agent_id:
        return specialist_binding.agent_id
    return fallback_agent_id


def _resolve_search_report_stage_agents(config: OpenClawWorkflowConfigResponse) -> dict[str, str]:
    return {
        SEARCH_STAGE_KEY: config.search_agent_id,
        ANALYSIS_STAGE_KEY: config.analysis_agent_id,
        REPORT_STAGE_KEY: _resolve_specialist_agent(config, "writer", config.report_agent_id),
    }


def _resolve_web_search_stage_agents(config: OpenClawWorkflowConfigResponse) -> dict[str, str]:
    return {
        UNDERSTAND_STAGE_KEY: config.controller_agent_id,
        SEARCH_STAGE_KEY: _resolve_specialist_agent(config, "search_web", config.search_agent_id),
        FILTER_STAGE_KEY: _resolve_specialist_agent(config, "organizer", config.controller_agent_id),
        INGEST_STAGE_KEY: _resolve_specialist_agent(config, "organizer", config.controller_agent_id),
        FORMAT_STAGE_KEY: _resolve_specialist_agent(config, "writer", config.report_agent_id),
    }


def _resolve_news_brief_stage_agents(config: OpenClawWorkflowConfigResponse) -> dict[str, str]:
    specialist_agent_id = _resolve_specialist_agent(config, "daily_news_brief", config.controller_agent_id)
    return {
        MONITOR_STAGE_KEY: config.controller_agent_id,
        SEARCH_STAGE_KEY: specialist_agent_id,
        DEDUPE_STAGE_KEY: specialist_agent_id,
        RANK_STAGE_KEY: specialist_agent_id,
        BRIEF_STAGE_KEY: specialist_agent_id,
    }


def _resolve_system_inspection_stage_agents(config: OpenClawWorkflowConfigResponse) -> dict[str, str]:
    specialist_agent_id = _resolve_specialist_agent(config, "system_inspection", config.controller_agent_id)
    return {
        SNAPSHOT_STAGE_KEY: config.controller_agent_id,
        VERSION_CHECK_STAGE_KEY: specialist_agent_id,
        LOG_REVIEW_STAGE_KEY: specialist_agent_id,
        RISK_ASSESSMENT_STAGE_KEY: specialist_agent_id,
        REPORT_STAGE_KEY: config.controller_agent_id,
    }


def _resolve_development_stage_agents(config: OpenClawWorkflowConfigResponse) -> dict[str, str]:
    specialist_agent_id = _resolve_specialist_agent(config, "fullstack_engineer", config.controller_agent_id)
    return {
        PROBLEM_DEFINITION_STAGE_KEY: specialist_agent_id,
        REQUIREMENTS_ANALYSIS_STAGE_KEY: specialist_agent_id,
        SOLUTION_DESIGN_STAGE_KEY: specialist_agent_id,
        TECHNOLOGY_SELECTION_STAGE_KEY: specialist_agent_id,
        TASK_PLANNING_STAGE_KEY: specialist_agent_id,
        IMPLEMENTATION_STAGE_KEY: specialist_agent_id,
        TESTING_STAGE_KEY: specialist_agent_id,
        OPTIMIZATION_STAGE_KEY: specialist_agent_id,
        HANDOFF_STAGE_KEY: config.controller_agent_id,
    }


def _collect_config_agent_ids(payload: OpenClawWorkflowConfigUpdateRequest) -> list[str]:
    collected = [
        payload.controller_agent_id,
        payload.search_agent_id,
        payload.analysis_agent_id,
        payload.report_agent_id,
    ]
    for binding in payload.specialist_agents.model_dump().values():
        if isinstance(binding, dict) and binding.get("enabled") and binding.get("agent_id"):
            collected.append(str(binding["agent_id"]))
    return [agent_id for agent_id in collected if agent_id]


def _should_run_daily_news(config: OpenClawDailyNewsConfigResponse, now: datetime) -> bool:
    try:
        config_now = now.astimezone(ZoneInfo(config.schedule_timezone))
    except Exception:
        config_now = now.astimezone(ZoneInfo("Asia/Tokyo"))

    hour, minute = (config.schedule_time.split(":") + ["00"])[:2]
    due = (config_now.hour, config_now.minute) >= (int(hour), int(minute))
    today = config_now.date().isoformat()
    return due and config.last_scheduled_date != today


def _should_run_system_inspection(config: OpenClawSystemInspectionConfigResponse, now: datetime) -> bool:
    try:
        config_now = now.astimezone(ZoneInfo(config.schedule_timezone))
    except Exception:
        config_now = now.astimezone(ZoneInfo("Asia/Tokyo"))

    hour, minute = (config.schedule_time.split(":") + ["00"])[:2]
    due = (config_now.hour, config_now.minute) >= (int(hour), int(minute))
    today = config_now.date().isoformat()
    return due and config.last_scheduled_date != today


def _normalize_gateway_log_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "timestamp": item.get("timestamp") or item.get("time"),
        "level": item.get("level") or item.get("type"),
        "message": truncate_text(str(item.get("message") or item.get("raw") or item), max_length=220),
    }


def _aggregate_system_issues(
    recent_operation_logs: list[dict[str, Any]],
    recent_workflow_failures: list[dict[str, Any]],
    gateway_log_excerpt: list[dict[str, Any]],
) -> list[WorkflowSystemInspectionLogIssue]:
    grouped: dict[str, dict[str, Any]] = {}

    def touch_issue(
        *,
        issue_key: str,
        category: str,
        description: str,
        seen_at: str | None,
        affected_component: str,
        impact_scope: str,
        severity: str,
        priority: str,
        root_cause: str,
        fix_action: str,
        optimization_action: str,
    ) -> None:
        record = grouped.setdefault(
            issue_key,
            {
                "issue_key": issue_key,
                "category": category,
                "description": description,
                "frequency": 0,
                "first_seen_at": seen_at,
                "last_seen_at": seen_at,
                "possible_root_causes": [],
                "affected_components": [],
                "impact_scope": impact_scope,
                "severity": severity,
                "fix_actions": [],
                "optimization_actions": [],
                "priority": priority,
                "assumptions": [],
                "verification_steps": ["重跑對應 workflow stage，確認錯誤是否消失。"],
            },
        )
        record["frequency"] += 1
        if seen_at and (record["first_seen_at"] is None or seen_at < record["first_seen_at"]):
            record["first_seen_at"] = seen_at
        if seen_at and (record["last_seen_at"] is None or seen_at > record["last_seen_at"]):
            record["last_seen_at"] = seen_at
        if root_cause not in record["possible_root_causes"]:
            record["possible_root_causes"].append(root_cause)
        if affected_component not in record["affected_components"]:
            record["affected_components"].append(affected_component)
        if fix_action not in record["fix_actions"]:
            record["fix_actions"].append(fix_action)
        if optimization_action not in record["optimization_actions"]:
            record["optimization_actions"].append(optimization_action)

    for item in recent_operation_logs:
        operation_type = str(item.get("operation_type") or "")
        error_message = str(item.get("error_message") or "")
        status = str(item.get("status") or "")
        created_at = item.get("created_at")
        normalized = f"{operation_type} {error_message}".lower()
        if status != "failed" and "warning" not in normalized and "timeout" not in normalized:
            continue
        if "timeout" in normalized:
            touch_issue(
                issue_key=f"timeout:{operation_type}",
                category="timeout",
                description=f"{operation_type} 高機率存在 timeout 問題。",
                seen_at=created_at,
                affected_component="workflow_dispatch",
                impact_scope="workflow stage 可能中斷或需人工重試",
                severity="high",
                priority="p1",
                root_cause="agent prompt 過大、CLI timeout 太短或工具鏈過慢",
                fix_action="縮短 prompt、限制輸入量，必要時延長 timeout。",
                optimization_action="為高成本 stage 建立獨立 timeout 與輸入壓縮策略。",
            )
        elif "unknown agent id" in normalized:
            touch_issue(
                issue_key="agent_unknown",
                category="config_drift",
                description="workflow 指向的 agent 與實際 OpenClaw runtime 設定不一致。",
                seen_at=created_at,
                affected_component="agent_config",
                impact_scope="對應 specialist workflow 直接失敗",
                severity="high",
                priority="p1",
                root_cause="本地 repo 設定與 ~/.openclaw runtime config 漂移",
                fix_action="確認 runtime openclaw.json 是否已建立並啟用對應 agent。",
                optimization_action="在 workflow 執行前加強 agent existence preflight 檢查。",
            )
        elif "can't parse entities" in normalized:
            touch_issue(
                issue_key="telegram_parse_entities",
                category="warning",
                description="Telegram Markdown 內容有特殊字元，曾造成投遞失敗。",
                seen_at=created_at,
                affected_component="telegram_delivery",
                impact_scope="通知可能延遲或回退為純文字",
                severity="medium",
                priority="p2",
                root_cause="Markdown 實體字元未逃脫",
                fix_action="保持 Markdown fallback to plain text 啟用。",
                optimization_action="後續可補 Telegram Markdown 轉義器。",
            )
        else:
            touch_issue(
                issue_key=f"failed:{operation_type}",
                category="error",
                description=f"{operation_type} 在近期 operation logs 中有失敗紀錄。",
                seen_at=created_at,
                affected_component=operation_type or "unknown",
                impact_scope="可能影響對應操作與自動化流程",
                severity="medium",
                priority="p2",
                root_cause=error_message or "需回看 operation log 詳情",
                fix_action="回看失敗 operation log 與對應 workflow stage payload。",
                optimization_action="補強 preflight 驗證與 error normalization。",
            )

    for failure in recent_workflow_failures:
        stage = str(failure.get("current_stage") or "unknown")
        error_message = str(failure.get("error_message") or "")
        seen_at = failure.get("updated_at")
        touch_issue(
            issue_key=f"workflow_failed:{stage}",
            category="error",
            description=f"{stage} 階段近期有 workflow 失敗。",
            seen_at=seen_at,
            affected_component=f"workflow:{stage}",
            impact_scope="該階段任務可能需人工接管",
            severity="high" if stage in {SEARCH_STAGE_KEY, DEDUPE_STAGE_KEY, VERSION_CHECK_STAGE_KEY} else "medium",
            priority="p1" if stage in {SEARCH_STAGE_KEY, DEDUPE_STAGE_KEY, VERSION_CHECK_STAGE_KEY} else "p2",
            root_cause=error_message or "需查看 workflow event timeline",
            fix_action="檢查該 stage 的 agent prompt、tools 與輸入大小。",
            optimization_action="對高失敗 stage 補重試策略與更小的 stage payload。",
        )

    for item in gateway_log_excerpt:
        message = str(item.get("message") or "")
        level = str(item.get("level") or "").lower()
        if not message:
            continue
        if "warn" in level or "error" in level:
            touch_issue(
                issue_key=f"gateway:{truncate_text(message, 60)}",
                category="warning" if "warn" in level else "error",
                description=truncate_text(message, 120),
                seen_at=item.get("timestamp"),
                affected_component="gateway_runtime",
                impact_scope="Gateway 執行狀態可能不穩或有異常警訊",
                severity="medium" if "warn" in level else "high",
                priority="p2" if "warn" in level else "p1",
                root_cause="需查看 gateway logs 原文與近期操作關聯",
                fix_action="回看 gateway logs 上下文並比對近期 deploy/config 變更。",
                optimization_action="將高頻 warning 建立 signature-based dashboard。",
            )

    issues = [WorkflowSystemInspectionLogIssue(**payload) for payload in grouped.values()]
    return sorted(issues, key=lambda item: (_priority_rank(item.priority), -item.frequency, _severity_rank(item.severity)))


def _priority_rank(priority: str) -> int:
    return {"p0": 0, "p1": 1, "p2": 2, "p3": 3}.get(priority, 9)


def _severity_rank(severity: str) -> int:
    return {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(severity, 9)


def _build_manual_review_payload(run: WorkflowRunResponse, error: OpenClawServiceError) -> dict[str, Any]:
    return {
        "manual_review_required": True,
        "manual_review_reason": error.detail or error.message,
        "blocked_stage": run.current_stage,
        "recommended_action": "請檢查對應專職 agent 輸出、工具可用性與 handoff policy，必要時由主控秘書人工改派或接管。",
    }


def _is_agent_timeout_error(error: OpenClawServiceError) -> bool:
    detail = (error.detail or "").lower()
    message = (error.message or "").lower()
    return "timeout=" in detail or "逾時" in message or "timed out" in detail


def _parse_agent_output(payload: dict[str, Any], schema, stage_label: str):
    text_payload = _extract_agent_text(payload)
    if not text_payload:
        structured_payload = _extract_structured_agent_payload(payload)
        if structured_payload is not None:
            try:
                return schema(**structured_payload)
            except Exception:
                pass
        raise OpenClawServiceError(
            f"{stage_label} 沒有產出可解析文字。",
            detail=_build_missing_text_detail(payload),
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


def _parse_system_report_output(
    payload: dict[str, Any],
    version_output: WorkflowSystemInspectionVersionOutput,
    log_review_output: WorkflowSystemInspectionLogReviewOutput,
    risk_output: WorkflowSystemInspectionRiskOutput,
) -> WorkflowSystemInspectionReportPayload:
    text_payload = _extract_agent_text(payload)
    if not text_payload:
        raise OpenClawServiceError(
            "系統巡檢報告階段沒有產出可解析文字。",
            detail=_build_missing_text_detail(payload),
            source_mode="workflow",
        )

    parsed = _extract_json_object(text_payload)
    try:
        return WorkflowSystemInspectionReportPayload(**parsed)
    except Exception:
        try:
            draft = WorkflowSystemInspectionReportDraft(**parsed)
        except Exception as error:  # noqa: BLE001
            raise OpenClawServiceError(
                "系統巡檢報告階段輸出格式不正確。",
                detail=truncate_text(text_payload, 400),
                source_mode="workflow",
            ) from error
        return _coerce_system_report_output(draft, version_output, log_review_output, risk_output)


def _extract_agent_text(payload: dict[str, Any]) -> str:
    result = payload.get("result")
    if isinstance(result, dict):
        payloads = result.get("payloads")
        if isinstance(payloads, list):
            for item in payloads:
                if isinstance(item, dict) and isinstance(item.get("text"), str) and item["text"].strip():
                    return item["text"].strip()
        for key in ["text", "output_text", "content"]:
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        message = result.get("message")
        if isinstance(message, dict):
            for key in ["text", "content"]:
                value = message.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        if isinstance(message, str) and message.strip():
            return message.strip()

    for key in ["text", "output_text", "content"]:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    message = payload.get("message")
    if isinstance(message, dict):
        for key in ["text", "content"]:
            value = message.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    if isinstance(message, str) and message.strip():
        return message.strip()
    return ""


def _extract_structured_agent_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    for candidate in _iter_structured_payload_candidates(payload):
        if isinstance(candidate, dict):
            return candidate
    return None


def _iter_structured_payload_candidates(value: Any) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[int] = set()

    def visit(node: Any, depth: int = 0) -> None:
        if depth > 4:
            return

        node_id = id(node)
        if node_id in seen:
            return
        seen.add(node_id)

        if isinstance(node, dict):
            if _looks_like_structured_agent_payload(node):
                candidates.append(node)

            result = node.get("result")
            if isinstance(result, dict):
                visit(result, depth + 1)
                payloads = result.get("payloads")
                if isinstance(payloads, list):
                    for item in payloads:
                        visit(item, depth + 1)

            for key in ("payload", "content", "message", "detail", "error", "data", "value"):
                child = node.get(key)
                if isinstance(child, dict):
                    visit(child, depth + 1)
                elif isinstance(child, str):
                    parsed = _parse_structured_json_candidate(child)
                    if isinstance(parsed, dict):
                        visit(parsed, depth + 1)

        elif isinstance(node, list):
            for item in node:
                visit(item, depth + 1)
        elif isinstance(node, str):
            parsed = _parse_structured_json_candidate(node)
            if isinstance(parsed, dict):
                visit(parsed, depth + 1)

    visit(value)
    return candidates


def _parse_structured_json_candidate(value: str) -> dict[str, Any] | None:
    text = value.strip()
    if not text:
        return None
    try:
        parsed = _extract_json_object(text)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _looks_like_structured_agent_payload(payload: dict[str, Any]) -> bool:
    summary = _optional_clean_string(payload.get("summary"))
    if not summary:
        return False

    structured_list_fields = (
        "completed_items",
        "changed_modules",
        "notable_decisions",
        "test_cases",
        "test_results",
        "improvements",
        "follow_up_todos",
        "tasks",
        "schedule",
        "functional_requirements",
        "non_functional_requirements",
        "risks",
        "dependencies",
        "modules",
        "flows",
        "data_structures",
        "interfaces",
        "selections",
    )
    return any(isinstance(payload.get(key), list) for key in structured_list_fields)


def _build_missing_text_detail(payload: dict[str, Any]) -> str:
    result = payload.get("result")
    result_payload = result if isinstance(result, dict) else {}
    meta = result_payload.get("meta") if isinstance(result_payload, dict) else None
    meta_payload = meta if isinstance(meta, dict) else {}
    agent_meta = meta_payload.get("agentMeta") if isinstance(meta_payload.get("agentMeta"), dict) else {}

    fields = _detect_text_field_presence(payload)
    details: list[str] = []
    status = _optional_clean_string(payload.get("status"))
    summary = _optional_clean_string(payload.get("summary"))
    provider = _optional_clean_string(agent_meta.get("provider"))
    model = _optional_clean_string(agent_meta.get("model"))
    structured_payload = _extract_structured_agent_payload(payload)
    structured_summary = _optional_clean_string(structured_payload.get("summary")) if isinstance(structured_payload, dict) else None
    structured_highlights = _collect_structured_payload_highlights(structured_payload)

    if structured_summary:
        details.append(f"summary={structured_summary}")
    elif summary:
        details.append(f"summary={summary}")

    for item in structured_highlights[:3]:
        details.append(item)

    if status:
        details.append(f"status={status}")
    if provider:
        details.append(f"provider={provider}")
    if model:
        details.append(f"model={model}")
    details.append(
        "text_fields=" + (",".join(fields) if fields else "none")
    )

    detail = " / ".join(details)
    return truncate_text(detail or json.dumps(payload, ensure_ascii=False), 400)


def _collect_structured_payload_highlights(payload: dict[str, Any] | None) -> list[str]:
    if not isinstance(payload, dict):
        return []

    highlights: list[str] = []
    field_labels = {
        "completed_items": "completed",
        "changed_modules": "modules",
        "notable_decisions": "decisions",
        "test_results": "tests",
        "improvements": "improvements",
        "follow_up_todos": "todos",
        "tasks": "tasks",
    }

    for key, label in field_labels.items():
        value = payload.get(key)
        if not isinstance(value, list):
            continue
        cleaned = [
            _optional_clean_string(item)
            for item in value
            if isinstance(item, str) and _optional_clean_string(item)
        ]
        if cleaned:
            highlights.append(f"{label}={'; '.join(cleaned[:2])}")

    return highlights


def _detect_text_field_presence(payload: dict[str, Any]) -> list[str]:
    fields: list[str] = []
    result = payload.get("result")
    if isinstance(result, dict):
        payloads = result.get("payloads")
        if isinstance(payloads, list):
            for item in payloads:
                if isinstance(item, dict) and isinstance(item.get("text"), str) and item["text"].strip():
                    fields.append("result.payloads[].text")
                    break
        for key in ["text", "output_text", "content"]:
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                fields.append(f"result.{key}")
        message = result.get("message")
        if isinstance(message, dict):
            for key in ["text", "content"]:
                value = message.get(key)
                if isinstance(value, str) and value.strip():
                    fields.append(f"result.message.{key}")
        elif isinstance(message, str) and message.strip():
            fields.append("result.message")
    for key in ["text", "output_text", "content"]:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            fields.append(key)
    message = payload.get("message")
    if isinstance(message, dict):
        for key in ["text", "content"]:
            value = message.get(key)
            if isinstance(value, str) and value.strip():
                fields.append(f"message.{key}")
    elif isinstance(message, str) and message.strip():
        fields.append("message")

    return fields


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
