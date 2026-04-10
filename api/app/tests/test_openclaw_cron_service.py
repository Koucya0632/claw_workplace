from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.repositories.database import ensure_database_ready
from app.repositories.openclaw_daily_news_config_repository import OpenClawDailyNewsConfigRepository
from app.repositories.openclaw_instance_repository import OpenClawInstanceRepository
from app.repositories.openclaw_operation_log_repository import OpenClawOperationLogRepository
from app.repositories.openclaw_system_inspection_config_repository import OpenClawSystemInspectionConfigRepository
from app.repositories.openclaw_workflow_config_repository import OpenClawWorkflowConfigRepository
from app.schemas.openclaw_daily_news import OpenClawDailyNewsConfigRequest
from app.schemas.openclaw_instance import OpenClawInstanceCreateRequest
from app.schemas.openclaw_system_inspection import OpenClawSystemInspectionConfigRequest
from app.schemas.openclaw_workflow_config import (
    OpenClawWorkflowHandoffPolicy,
    OpenClawWorkflowSpecialistAgents,
)
from app.schemas.workflow import WorkflowNewsBriefCreateRequest
from app.services.openclaw_cron_service import OpenClawCronBridgeService, OpenClawCronSchedulingService
from app.services.openclaw_errors import OpenClawServiceError
from app.services.workflow_service import SearchReportWorkflowService

class FakeCronCliAdapter:
    source_mode = "cli"

    def __init__(self) -> None:
        self.jobs: dict[str, dict[str, object]] = {}
        self.runs_by_job_id: dict[str, list[dict[str, object]]] = {}
        self.add_calls: list[dict[str, str]] = []
        self.edit_calls: list[dict[str, str]] = []
        self.enable_calls: list[str] = []
        self.disable_calls: list[str] = []

    def list_cron_jobs(self, instance, token):
        return list(self.jobs.values())

    def add_cron_job(
        self,
        instance,
        token,
        *,
        name: str,
        cron_expression: str,
        timezone: str,
        agent_id: str | None = None,
        system_event: str | None = None,
        message: str | None = None,
        announce: bool = False,
        channel: str | None = None,
        to: str | None = None,
    ):
        job_id = f"job-{len(self.jobs) + 1}"
        payload = {
            "jobId": job_id,
            "name": name,
            "enabled": True,
            "cron": cron_expression,
            "tz": timezone,
            "agentId": agent_id,
            "systemEvent": system_event,
            "message": message,
            "delivery": {"mode": "announce" if announce else "none", "channel": channel, "to": to},
        }
        self.jobs[name] = payload
        self.add_calls.append(
            {
                "name": name,
                "cron": cron_expression,
                "timezone": timezone,
                "agent_id": agent_id or "",
                "message": message or "",
                "channel": channel or "",
                "to": to or "",
            }
        )
        return payload

    def edit_cron_job(
        self,
        instance,
        token,
        *,
        job_id: str,
        name: str,
        cron_expression: str,
        timezone: str,
        agent_id: str | None = None,
        system_event: str | None = None,
        message: str | None = None,
        announce: bool = False,
        channel: str | None = None,
        to: str | None = None,
    ):
        payload = self.jobs.get(name, {"jobId": job_id, "name": name, "enabled": True})
        payload.update(
            {
                "cron": cron_expression,
                "tz": timezone,
                "agentId": agent_id,
                "systemEvent": system_event,
                "message": message,
                "delivery": {"mode": "announce" if announce else "none", "channel": channel, "to": to},
            }
        )
        self.jobs[name] = payload
        self.edit_calls.append(
            {
                "job_id": job_id,
                "name": name,
                "cron": cron_expression,
                "timezone": timezone,
                "agent_id": agent_id or "",
                "message": message or "",
                "channel": channel or "",
                "to": to or "",
            }
        )
        return payload

    def enable_cron_job(self, instance, token, *, job_id: str):
        for payload in self.jobs.values():
            if payload.get("jobId") == job_id:
                payload["enabled"] = True
        self.enable_calls.append(job_id)
        return {"message": f"enabled {job_id}"}

    def disable_cron_job(self, instance, token, *, job_id: str):
        for payload in self.jobs.values():
            if payload.get("jobId") == job_id:
                payload["enabled"] = False
        self.disable_calls.append(job_id)
        return {"message": f"disabled {job_id}"}

    def list_cron_runs(self, instance, token, *, job_id: str | None = None, limit: int = 20):
        if not job_id:
            return []
        return self.runs_by_job_id.get(job_id, [])[:limit]


class FakeBridgeWorkflowService:
    def __init__(self) -> None:
        self.news_calls: list[WorkflowNewsBriefCreateRequest] = []
        self.inspection_calls: list[object] = []

    def create_news_brief_run(self, payload: WorkflowNewsBriefCreateRequest):
        self.news_calls.append(payload)
        return SimpleNamespace(id=f"wfr-news-{len(self.news_calls)}"), 0

    def create_system_inspection_run(self, payload):
        self.inspection_calls.append(payload)
        return SimpleNamespace(id=f"wfr-inspection-{len(self.inspection_calls)}"), 0


def _seed_instance_and_workflow() -> tuple[str, OpenClawInstanceRepository, OpenClawWorkflowConfigRepository]:
    ensure_database_ready()
    instance_repository = OpenClawInstanceRepository()
    workflow_config_repository = OpenClawWorkflowConfigRepository()
    instance = instance_repository.create(
        OpenClawInstanceCreateRequest(
            name="Primary Gateway",
            gateway_url="ws://127.0.0.1:18789",
            is_active=True,
        )
    )
    workflow_config_repository.upsert(
        instance_id=instance.id,
        controller_agent_id="main",
        search_agent_id="search-agent",
        analysis_agent_id="analysis-agent",
        report_agent_id="report-agent",
        specialist_agents=OpenClawWorkflowSpecialistAgents(),
        routing_rules=[],
        handoff_policy=OpenClawWorkflowHandoffPolicy(),
    )
    return instance.id, instance_repository, workflow_config_repository


def test_create_app_uses_openclaw_cron_bridge(app_env) -> None:
    from app.main import create_app

    app = create_app()

    assert hasattr(app.state, "openclaw_cron_bridge")
    assert not hasattr(app.state, "daily_news_scheduler")
    assert not hasattr(app.state, "system_inspection_scheduler")


def test_cron_reconcile_creates_and_disables_deterministic_jobs(app_env) -> None:
    instance_id, instance_repository, workflow_config_repository = _seed_instance_and_workflow()
    daily_news_repository = OpenClawDailyNewsConfigRepository()
    system_inspection_repository = OpenClawSystemInspectionConfigRepository()
    operation_log_repository = OpenClawOperationLogRepository()
    cli_adapter = FakeCronCliAdapter()

    daily_news_repository.upsert(
        OpenClawDailyNewsConfigRequest(
            instance_id=instance_id,
            enabled=True,
            topic="AI news",
            delivery_channel="discord",
            discord_channel_id="1490256212229488742",
            schedule_timezone="Asia/Tokyo",
            schedule_time="09:00",
        )
    )
    system_inspection_repository.upsert(
        OpenClawSystemInspectionConfigRequest(
            instance_id=instance_id,
            enabled=False,
            schedule_timezone="Asia/Tokyo",
            schedule_time="09:30",
        )
    )

    service = OpenClawCronSchedulingService(
        repository=instance_repository,
        workflow_config_repository=workflow_config_repository,
        daily_news_repository=daily_news_repository,
        system_inspection_repository=system_inspection_repository,
        operation_log_repository=operation_log_repository,
        cli_adapter=cli_adapter,
    )

    service.reconcile_instance(instance_id)

    assert cli_adapter.add_calls == [
        {
            "name": f"daily-news:{instance_id}",
            "cron": "0 9 * * *",
            "timezone": "Asia/Tokyo",
            "agent_id": "main",
            "message": "收集并整理每日新闻简报。",
            "channel": "discord",
            "to": "1490256212229488742",
        }
    ]
    created_job_id = str(cli_adapter.jobs[f"daily-news:{instance_id}"]["jobId"])

    daily_news_repository.upsert(
        OpenClawDailyNewsConfigRequest(
            instance_id=instance_id,
            enabled=False,
            topic="AI news",
            delivery_channel="discord",
            discord_channel_id="1490256212229488742",
            schedule_timezone="Asia/Tokyo",
            schedule_time="09:00",
        )
    )
    service.reconcile_instance(instance_id)

    assert cli_adapter.disable_calls == [created_job_id]


def test_cron_bridge_consumes_new_run_once_and_marks_cursor(app_env) -> None:
    instance_id, instance_repository, workflow_config_repository = _seed_instance_and_workflow()
    daily_news_repository = OpenClawDailyNewsConfigRepository()
    operation_log_repository = OpenClawOperationLogRepository()
    cli_adapter = FakeCronCliAdapter()
    workflow_service = FakeBridgeWorkflowService()

    daily_news_repository.upsert(
        OpenClawDailyNewsConfigRequest(
            instance_id=instance_id,
            enabled=True,
            topic="AI news",
            delivery_channel="discord",
            discord_channel_id="1490256212229488742",
            schedule_timezone="Asia/Tokyo",
            schedule_time="09:00",
        )
    )

    job_name = f"daily-news:{instance_id}"
    cli_adapter.jobs[job_name] = {
        "jobId": "job-1",
        "name": job_name,
        "enabled": True,
        "delivery": {"mode": "announce", "channel": "discord", "to": "1490256212229488742"},
    }
    cli_adapter.runs_by_job_id["job-1"] = [
        {
            "runId": "cron-run-1",
            "jobId": "job-1",
            "status": "completed",
            "completedAt": "2026-04-08T00:00:00Z",
        }
    ]

    scheduling_service = OpenClawCronSchedulingService(
        repository=instance_repository,
        workflow_config_repository=workflow_config_repository,
        daily_news_repository=daily_news_repository,
        operation_log_repository=operation_log_repository,
        cli_adapter=cli_adapter,
    )
    bridge = OpenClawCronBridgeService(
        repository=instance_repository,
        daily_news_repository=daily_news_repository,
        operation_log_repository=operation_log_repository,
        workflow_service=workflow_service,
        scheduling_service=scheduling_service,
        cli_adapter=cli_adapter,
        poll_seconds=3600,
    )

    bridge.run_pending_once()
    bridge.run_pending_once()

    assert workflow_service.news_calls == []
    assert instance_repository.get_snapshot(instance_id, "cron_bridge:news_brief") is None


def test_news_brief_cron_trigger_marks_schedule_and_manual_run_stays_available(app_env) -> None:
    instance_id, instance_repository, workflow_config_repository = _seed_instance_and_workflow()
    daily_news_repository = OpenClawDailyNewsConfigRepository()
    system_inspection_repository = OpenClawSystemInspectionConfigRepository()
    operation_log_repository = OpenClawOperationLogRepository()

    daily_news_repository.upsert(
        OpenClawDailyNewsConfigRequest(
            instance_id=instance_id,
            enabled=True,
            topic="AI news",
            schedule_timezone="Asia/Tokyo",
            schedule_time="09:00",
        )
    )

    service = SearchReportWorkflowService(
        repository=instance_repository,
        workflow_repository=None,
        workflow_config_repository=workflow_config_repository,
        daily_news_repository=daily_news_repository,
        system_inspection_repository=system_inspection_repository,
        operation_log_repository=operation_log_repository,
        run_inline=False,
    )
    service._start_run = lambda run_id: None  # type: ignore[method-assign]

    run, _ = service.create_news_brief_run(
        WorkflowNewsBriefCreateRequest(
            instance_id=instance_id,
            trigger_source="cron",
            scheduled_date="2026-04-08",
            cron_job_id="job-1",
            cron_run_id="cron-run-1",
        )
    )
    assert run.input_payload["trigger_source"] == "cron"
    assert daily_news_repository.get(instance_id).last_scheduled_date == "2026-04-08"

    with pytest.raises(OpenClawServiceError):
        service.create_news_brief_run(
            WorkflowNewsBriefCreateRequest(
                instance_id=instance_id,
                trigger_source="cron",
                scheduled_date="2026-04-08",
                cron_job_id="job-1",
                cron_run_id="cron-run-2",
            )
        )

    manual_run, _ = service.create_news_brief_run(WorkflowNewsBriefCreateRequest(instance_id=instance_id))
    assert manual_run.id != run.id
