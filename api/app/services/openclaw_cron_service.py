from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.repositories.openclaw_daily_news_config_repository import OpenClawDailyNewsConfigRepository
from app.repositories.openclaw_instance_repository import OpenClawInstanceRepository
from app.repositories.openclaw_operation_log_repository import OpenClawOperationLogRepository
from app.repositories.openclaw_system_inspection_config_repository import OpenClawSystemInspectionConfigRepository
from app.repositories.openclaw_workflow_config_repository import OpenClawWorkflowConfigRepository
from app.schemas.openclaw_daily_news import OpenClawDailyNewsConfigResponse
from app.schemas.openclaw_instance import OpenClawInstanceResponse
from app.schemas.openclaw_system_inspection import OpenClawSystemInspectionConfigResponse
from app.schemas.workflow import WorkflowNewsBriefCreateRequest, WorkflowSystemInspectionCreateRequest
from app.services.openclaw_cli_adapter import OpenClawCliAdapter
from app.services.openclaw_errors import OpenClawServiceError
from app.services.openclaw_secret_cipher import OpenClawSecretCipher
from app.utils import truncate_text

CRON_MANAGED_WORKFLOW_TYPES = ("news_brief", "system_inspection")


@dataclass
class ManagedCronJob:
    workflow_type: str
    job_name: str
    cron_expression: str
    timezone: str
    agent_id: str
    message: str
    announce: bool
    channel: str | None
    to: str | None


@dataclass
class CronJobSnapshot:
    job_id: str
    name: str
    enabled: bool
    bridge_managed: bool


@dataclass
class CronRunSnapshot:
    run_id: str
    job_id: str
    occurred_at: str | None
    status: str | None


class OpenClawCronSchedulingService:
    source_mode = "cron"

    def __init__(
        self,
        repository: Optional[OpenClawInstanceRepository] = None,
        workflow_config_repository: Optional[OpenClawWorkflowConfigRepository] = None,
        daily_news_repository: Optional[OpenClawDailyNewsConfigRepository] = None,
        system_inspection_repository: Optional[OpenClawSystemInspectionConfigRepository] = None,
        operation_log_repository: Optional[OpenClawOperationLogRepository] = None,
        cli_adapter: Optional[OpenClawCliAdapter] = None,
        secret_cipher: Optional[OpenClawSecretCipher] = None,
    ) -> None:
        settings = get_settings()
        self.repository = repository or OpenClawInstanceRepository()
        self.workflow_config_repository = workflow_config_repository or OpenClawWorkflowConfigRepository()
        self.daily_news_repository = daily_news_repository or OpenClawDailyNewsConfigRepository()
        self.system_inspection_repository = system_inspection_repository or OpenClawSystemInspectionConfigRepository()
        self.operation_log_repository = operation_log_repository or OpenClawOperationLogRepository()
        self.cli_adapter = cli_adapter or OpenClawCliAdapter()
        self.secret_cipher = secret_cipher or OpenClawSecretCipher(settings.openclaw_secret_key)

    def reconcile_all(self) -> None:
        for instance in self.repository.list_all():
            self.reconcile_instance(instance.id)

    def reconcile_instance(self, instance_id: str) -> None:
        instance = self.repository.get(instance_id)
        token = self._resolve_token(instance.id)

        try:
            current_jobs = {
                job.name: job
                for job in self._list_cron_jobs(instance, token)
                if job.name
            }
        except OpenClawServiceError as error:
            self._log(
                instance_id=instance.id,
                operation_type="reconcile_openclaw_cron",
                target_id=instance.id,
                status="failed",
                request_summary={"instance_active": instance.is_active},
                response_summary=None,
                error_message=error.detail or error.message,
            )
            raise

        for job in self._build_managed_jobs(instance.id):
            existing = current_jobs.get(job.job_name)
            self._reconcile_job(instance=instance, token=token, job=job, existing=existing)

    def _build_managed_jobs(self, instance_id: str) -> list[ManagedCronJob]:
        jobs: list[ManagedCronJob] = []

        try:
            daily_news_config = self.daily_news_repository.get(instance_id)
        except KeyError:
            daily_news_config = None
        if daily_news_config is not None:
            jobs.append(self._build_daily_news_job(instance_id, daily_news_config))

        try:
            system_inspection_config = self.system_inspection_repository.get(instance_id)
        except KeyError:
            system_inspection_config = None
        if system_inspection_config is not None:
            jobs.append(self._build_system_inspection_job(instance_id, system_inspection_config))

        return jobs

    def _reconcile_job(
        self,
        *,
        instance: OpenClawInstanceResponse,
        token: str | None,
        job: ManagedCronJob,
        existing: CronJobSnapshot | None,
    ) -> None:
        should_enable = instance.is_active and self._is_workflow_enabled(instance.id, job.workflow_type)
        action = "noop"
        response_summary: dict[str, Any] = {
            "workflow_type": job.workflow_type,
            "job_name": job.job_name,
            "enabled": should_enable,
        }

        if existing is None and should_enable:
            payload = self.cli_adapter.add_cron_job(
                instance,
                token,
                name=job.job_name,
                cron_expression=job.cron_expression,
                timezone=job.timezone,
                agent_id=job.agent_id,
                message=job.message,
                announce=job.announce,
                channel=job.channel,
                to=job.to,
            )
            action = "created"
            response_summary.update({"job_id": str(payload.get("jobId") or payload.get("id") or job.job_name)})
        elif existing is not None and should_enable:
            self.cli_adapter.edit_cron_job(
                instance,
                token,
                job_id=existing.job_id,
                name=job.job_name,
                cron_expression=job.cron_expression,
                timezone=job.timezone,
                agent_id=job.agent_id,
                message=job.message,
                announce=job.announce,
                channel=job.channel,
                to=job.to,
            )
            action = "updated"
            response_summary.update({"job_id": existing.job_id})
            if not existing.enabled:
                self.cli_adapter.enable_cron_job(instance, token, job_id=existing.job_id)
                action = "enabled"
        elif existing is not None and not should_enable and existing.enabled:
            self.cli_adapter.disable_cron_job(instance, token, job_id=existing.job_id)
            action = "disabled"
            response_summary.update({"job_id": existing.job_id})
        elif existing is not None:
            response_summary.update({"job_id": existing.job_id})

        if action != "noop":
            self._log(
                instance_id=instance.id,
                operation_type="reconcile_openclaw_cron",
                target_id=response_summary.get("job_id"),
                status="success",
                request_summary={
                    "workflow_type": job.workflow_type,
                    "job_name": job.job_name,
                    "action": action,
                },
                response_summary=response_summary,
                error_message=None,
            )

    def _is_workflow_enabled(self, instance_id: str, workflow_type: str) -> bool:
        try:
            if workflow_type == "news_brief":
                return self.daily_news_repository.get(instance_id).enabled
            return self.system_inspection_repository.get(instance_id).enabled
        except KeyError:
            return False

    def _build_daily_news_job(self, instance_id: str, config: OpenClawDailyNewsConfigResponse) -> ManagedCronJob:
        owner = self._resolve_owner_agent(instance_id, specialist_key="daily_news_brief")
        channel, target = _resolve_delivery_route(
            delivery_channel=config.delivery_channel,
            telegram_target=config.telegram_target,
            discord_channel_id=config.discord_channel_id,
        )
        return ManagedCronJob(
            workflow_type="news_brief",
            job_name=f"daily-news:{instance_id}",
            cron_expression=_daily_cron_expression(config.schedule_time),
            timezone=config.schedule_timezone,
            agent_id=owner,
            message="收集并整理每日新闻简报。",
            announce=True,
            channel=channel,
            to=target,
        )

    def _build_system_inspection_job(
        self,
        instance_id: str,
        config: OpenClawSystemInspectionConfigResponse,
    ) -> ManagedCronJob:
        owner = self._resolve_owner_agent(instance_id, specialist_key="system_inspection")
        channel, target = _resolve_delivery_route(
            delivery_channel=config.delivery_channel,
            telegram_target=config.telegram_target,
            discord_channel_id=config.discord_channel_id,
        )
        return ManagedCronJob(
            workflow_type="system_inspection",
            job_name=f"system-inspection:{instance_id}",
            cron_expression=_daily_cron_expression(config.schedule_time),
            timezone=config.schedule_timezone,
            agent_id=owner,
            message="执行系统巡检与风险评估。",
            announce=True,
            channel=channel,
            to=target,
        )

    def _resolve_owner_agent(self, instance_id: str, *, specialist_key: str) -> str:
        try:
            config = self.workflow_config_repository.get(instance_id)
        except KeyError:
            return "main"

        specialist = getattr(config.specialist_agents, specialist_key, None)
        if specialist and specialist.enabled and specialist.agent_id:
            return specialist.agent_id
        return config.controller_agent_id

    def _list_cron_jobs(self, instance: OpenClawInstanceResponse, token: str | None) -> list[CronJobSnapshot]:
        payload = self.cli_adapter.list_cron_jobs(instance, token)
        jobs: list[CronJobSnapshot] = []
        for item in payload:
            job_id = str(item.get("jobId") or item.get("id") or "").strip()
            name = str(item.get("name") or job_id).strip()
            if not job_id or not name:
                continue
            delivery = item.get("delivery")
            delivery_mode = delivery.get("mode") if isinstance(delivery, dict) else None
            jobs.append(
                CronJobSnapshot(
                    job_id=job_id,
                    name=name,
                    enabled=bool(item.get("enabled", True)),
                    bridge_managed=delivery_mode != "announce",
                )
            )
        return jobs

    def _resolve_token(self, instance_id: str) -> Optional[str]:
        encrypted_token = self.repository.get_secret(instance_id)
        if encrypted_token is None:
            return None
        return self.secret_cipher.decrypt(encrypted_token)

    def _log(
        self,
        *,
        instance_id: str | None,
        operation_type: str,
        target_id: str | None,
        status: str,
        request_summary: dict[str, Any],
        response_summary: dict[str, Any] | None,
        error_message: str | None,
    ) -> None:
        self.operation_log_repository.create(
            instance_id=instance_id,
            operation_type=operation_type,
            target_type="cron_job",
            target_id=target_id,
            status=status,
            error_message=error_message,
            request_summary=request_summary,
            response_summary=response_summary,
            source_mode=self.source_mode,
        )


class OpenClawCronBridgeService:
    source_mode = "cron_bridge"

    def __init__(
        self,
        repository: Optional[OpenClawInstanceRepository] = None,
        daily_news_repository: Optional[OpenClawDailyNewsConfigRepository] = None,
        system_inspection_repository: Optional[OpenClawSystemInspectionConfigRepository] = None,
        workflow_service: Optional[Any] = None,
        scheduling_service: Optional[OpenClawCronSchedulingService] = None,
        operation_log_repository: Optional[OpenClawOperationLogRepository] = None,
        cli_adapter: Optional[OpenClawCliAdapter] = None,
        secret_cipher: Optional[OpenClawSecretCipher] = None,
        poll_seconds: Optional[int] = None,
    ) -> None:
        settings = get_settings()
        self.repository = repository or OpenClawInstanceRepository()
        self.daily_news_repository = daily_news_repository or OpenClawDailyNewsConfigRepository()
        self.system_inspection_repository = system_inspection_repository or OpenClawSystemInspectionConfigRepository()
        self.operation_log_repository = operation_log_repository or OpenClawOperationLogRepository()
        self.cli_adapter = cli_adapter or OpenClawCliAdapter()
        self.secret_cipher = secret_cipher or OpenClawSecretCipher(settings.openclaw_secret_key)
        self.scheduling_service = scheduling_service or OpenClawCronSchedulingService(
            repository=self.repository,
            daily_news_repository=self.daily_news_repository,
            system_inspection_repository=self.system_inspection_repository,
            operation_log_repository=self.operation_log_repository,
            cli_adapter=self.cli_adapter,
            secret_cipher=self.secret_cipher,
        )
        if workflow_service is None:
            from app.services.workflow_service import SearchReportWorkflowService

            workflow_service = SearchReportWorkflowService()
        self.workflow_service = workflow_service
        self.poll_seconds = poll_seconds or getattr(settings, "openclaw_cron_bridge_poll_seconds", 60)
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        try:
            self.scheduling_service.reconcile_all()
        except Exception:
            pass
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def run_pending_once(self) -> None:
        for instance in self.repository.list_all():
            self._consume_instance(instance)

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_pending_once()
            except Exception:
                pass
            self._stop_event.wait(self.poll_seconds)

    def _consume_instance(self, instance: OpenClawInstanceResponse) -> None:
        token = self._resolve_token(instance.id)
        try:
            jobs = self.scheduling_service._list_cron_jobs(instance, token)
        except OpenClawServiceError:
            return

        managed_jobs = {
            job.name: job
            for job in jobs
            if job.name in self._managed_job_names(instance.id) and job.bridge_managed
        }
        for workflow_type, job_name in self._workflow_job_pairs(instance.id):
            job = managed_jobs.get(job_name)
            if job is None:
                continue
            self._consume_job(instance=instance, token=token, workflow_type=workflow_type, job=job)

    def _consume_job(
        self,
        *,
        instance: OpenClawInstanceResponse,
        token: str | None,
        workflow_type: str,
        job: CronJobSnapshot,
    ) -> None:
        try:
            latest_run = self._load_latest_cron_run(instance, token, job.job_id)
        except OpenClawServiceError as error:
            self._log(
                instance_id=instance.id,
                operation_type="consume_openclaw_cron_run",
                target_id=job.job_id,
                status="failed",
                request_summary={"workflow_type": workflow_type, "job_name": job.name},
                response_summary=None,
                error_message=error.detail or error.message,
            )
            return

        if latest_run is None:
            return

        state = self._read_state(instance.id, workflow_type)
        if state.get("last_consumed_run_id") == latest_run.run_id:
            return

        scheduled_date = self._resolve_scheduled_date(instance.id, workflow_type, latest_run.occurred_at)
        config = self._get_workflow_config(instance.id, workflow_type)

        if config is None or not instance.is_active or not config.enabled:
            self._write_state(
                instance.id,
                workflow_type,
                {
                    "last_consumed_run_id": latest_run.run_id,
                    "last_consumed_at": latest_run.occurred_at,
                    "job_id": job.job_id,
                    "job_name": job.name,
                    "status": "blocked",
                },
            )
            self._log(
                instance_id=instance.id,
                operation_type="consume_openclaw_cron_run",
                target_id=job.job_id,
                status="blocked",
                request_summary={"workflow_type": workflow_type, "scheduled_date": scheduled_date},
                response_summary={"cron_run_id": latest_run.run_id, "job_name": job.name},
                error_message="workflow config missing, disabled, or instance inactive",
            )
            return

        if config.last_scheduled_date == scheduled_date:
            self._write_state(
                instance.id,
                workflow_type,
                {
                    "last_consumed_run_id": latest_run.run_id,
                    "last_consumed_at": latest_run.occurred_at,
                    "job_id": job.job_id,
                    "job_name": job.name,
                    "status": "noop",
                },
            )
            self._log(
                instance_id=instance.id,
                operation_type="consume_openclaw_cron_run",
                target_id=job.job_id,
                status="noop",
                request_summary={"workflow_type": workflow_type, "scheduled_date": scheduled_date},
                response_summary={"cron_run_id": latest_run.run_id, "job_name": job.name},
                error_message=None,
            )
            return

        try:
            if workflow_type == "news_brief":
                run, _ = self.workflow_service.create_news_brief_run(
                    WorkflowNewsBriefCreateRequest(
                        instance_id=instance.id,
                        trigger_source="cron",
                        scheduled_date=scheduled_date,
                        cron_job_id=job.job_id,
                        cron_job_name=job.name,
                        cron_run_id=latest_run.run_id,
                    )
                )
            else:
                run, _ = self.workflow_service.create_system_inspection_run(
                    WorkflowSystemInspectionCreateRequest(
                        instance_id=instance.id,
                        trigger_source="cron",
                        scheduled_date=scheduled_date,
                        cron_job_id=job.job_id,
                        cron_job_name=job.name,
                        cron_run_id=latest_run.run_id,
                    )
                )
        except OpenClawServiceError as error:
            self._log(
                instance_id=instance.id,
                operation_type="consume_openclaw_cron_run",
                target_id=job.job_id,
                status="failed",
                request_summary={"workflow_type": workflow_type, "scheduled_date": scheduled_date},
                response_summary={"cron_run_id": latest_run.run_id, "job_name": job.name},
                error_message=error.detail or error.message,
            )
            return

        self._write_state(
            instance.id,
            workflow_type,
            {
                "last_consumed_run_id": latest_run.run_id,
                "last_consumed_at": latest_run.occurred_at,
                "job_id": job.job_id,
                "job_name": job.name,
                "status": "created",
                "workflow_run_id": run.id,
            },
        )
        self._log(
            instance_id=instance.id,
            operation_type="consume_openclaw_cron_run",
            target_id=job.job_id,
            status="success",
            request_summary={"workflow_type": workflow_type, "scheduled_date": scheduled_date},
            response_summary={"cron_run_id": latest_run.run_id, "job_name": job.name, "workflow_run_id": run.id},
            error_message=None,
        )

    def _load_latest_cron_run(
        self,
        instance: OpenClawInstanceResponse,
        token: str | None,
        job_id: str,
    ) -> CronRunSnapshot | None:
        runs = self.cli_adapter.list_cron_runs(instance, token, job_id=job_id, limit=8)
        candidates: list[CronRunSnapshot] = []

        for item in runs:
            normalized_job_id = str(item.get("jobId") or item.get("job_id") or job_id).strip() or job_id
            run_id = str(item.get("runId") or item.get("id") or item.get("executionId") or "").strip()
            if not run_id:
                continue
            status = str(item.get("status") or item.get("state") or item.get("result") or "").strip().lower() or None
            occurred_at = _extract_cron_run_timestamp(item)
            if status and status not in {"ok", "success", "succeeded", "completed", "finished"}:
                continue
            candidates.append(CronRunSnapshot(run_id=run_id, job_id=normalized_job_id, occurred_at=occurred_at, status=status))

        if not candidates:
            return None

        candidates.sort(key=lambda item: item.occurred_at or "", reverse=True)
        return candidates[0]

    def _get_workflow_config(
        self,
        instance_id: str,
        workflow_type: str,
    ) -> OpenClawDailyNewsConfigResponse | OpenClawSystemInspectionConfigResponse | None:
        try:
            if workflow_type == "news_brief":
                return self.daily_news_repository.get(instance_id)
            return self.system_inspection_repository.get(instance_id)
        except KeyError:
            return None

    def _resolve_scheduled_date(self, instance_id: str, workflow_type: str, occurred_at: str | None) -> str:
        config = self._get_workflow_config(instance_id, workflow_type)
        timezone_name = getattr(config, "schedule_timezone", "Asia/Tokyo")
        try:
            zone = ZoneInfo(timezone_name)
        except Exception:
            zone = ZoneInfo("Asia/Tokyo")

        if occurred_at:
            try:
                return datetime.fromisoformat(occurred_at.replace("Z", "+00:00")).astimezone(zone).date().isoformat()
            except ValueError:
                pass
        return datetime.now(zone).date().isoformat()

    def _managed_job_names(self, instance_id: str) -> set[str]:
        return {job_name for _, job_name in self._workflow_job_pairs(instance_id)}

    @staticmethod
    def _workflow_job_pairs(instance_id: str) -> list[tuple[str, str]]:
        return [
            ("news_brief", f"daily-news:{instance_id}"),
            ("system_inspection", f"system-inspection:{instance_id}"),
        ]

    def _read_state(self, instance_id: str, workflow_type: str) -> dict[str, Any]:
        payload = self.repository.get_snapshot(instance_id, f"cron_bridge:{workflow_type}")
        return payload if isinstance(payload, dict) else {}

    def _write_state(self, instance_id: str, workflow_type: str, payload: dict[str, Any]) -> None:
        self.repository.upsert_snapshot(instance_id, f"cron_bridge:{workflow_type}", payload)

    def _resolve_token(self, instance_id: str) -> Optional[str]:
        encrypted_token = self.repository.get_secret(instance_id)
        if encrypted_token is None:
            return None
        return self.secret_cipher.decrypt(encrypted_token)

    def _log(
        self,
        *,
        instance_id: str | None,
        operation_type: str,
        target_id: str | None,
        status: str,
        request_summary: dict[str, Any],
        response_summary: dict[str, Any] | None,
        error_message: str | None,
    ) -> None:
        self.operation_log_repository.create(
            instance_id=instance_id,
            operation_type=operation_type,
            target_type="cron_run",
            target_id=target_id,
            status=status,
            error_message=error_message,
            request_summary=request_summary,
            response_summary=response_summary,
            source_mode=self.source_mode,
        )


def _daily_cron_expression(schedule_time: str) -> str:
    hour, minute = (schedule_time.split(":") + ["00"])[:2]
    return f"{int(minute)} {int(hour)} * * *"


def _extract_cron_run_timestamp(item: dict[str, Any]) -> str | None:
    for key in ("completedAt", "executedAt", "runAt", "startedAt", "createdAt", "timestamp"):
        value = item.get(key)
        normalized = _normalize_datetime_value(value)
        if normalized:
            return normalized
    return None


def _normalize_datetime_value(value: Any) -> str | None:
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 10_000_000_000:
            timestamp /= 1000
        return datetime.fromtimestamp(timestamp, tz=ZoneInfo("UTC")).isoformat()
    if isinstance(value, str) and value.strip():
        text = value.strip()
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).isoformat()
        except ValueError:
            return None
    return None


def _resolve_delivery_route(
    *,
    delivery_channel: str,
    telegram_target: str,
    discord_channel_id: str,
) -> tuple[str | None, str | None]:
    if delivery_channel == "discord":
        target = discord_channel_id.strip()
        return ("discord", target or None)
    target = telegram_target.strip()
    return ("telegram", target or None)


def summarize_cron_reconcile_error(error: Exception) -> str:
    if isinstance(error, OpenClawServiceError):
        return error.detail or error.message
    return truncate_text(str(error), max_length=240)
