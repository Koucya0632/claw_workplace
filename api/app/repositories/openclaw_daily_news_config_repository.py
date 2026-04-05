from __future__ import annotations

import sqlite3
from datetime import datetime

from app.repositories.database import adapt_json, get_connection
from app.schemas.openclaw_daily_news import OpenClawDailyNewsConfigRequest, OpenClawDailyNewsConfigResponse
from app.utils import json_loads, utc_now_iso


class OpenClawDailyNewsConfigRepository:
    def get(self, instance_id: str) -> OpenClawDailyNewsConfigResponse:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM openclaw_daily_news_configs
                WHERE instance_id = ?
                """,
                (instance_id,),
            ).fetchone()

        if row is None:
            raise KeyError(f"找不到 daily news 設定：{instance_id}")

        return self._row_to_model(row)

    def upsert(self, payload: OpenClawDailyNewsConfigRequest) -> OpenClawDailyNewsConfigResponse:
        now = utc_now_iso()
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO openclaw_daily_news_configs (
                    instance_id, enabled, brief_name, topic, keywords_json, industries_json, regions_json, people_json,
                    companies_json, source_domains_json, source_urls_json, must_include_json, must_exclude_json,
                    focus_points_json, output_format, delivery_channel, telegram_target, discord_channel_id,
                    schedule_timezone, schedule_time, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(instance_id) DO UPDATE SET
                    enabled = excluded.enabled,
                    brief_name = excluded.brief_name,
                    topic = excluded.topic,
                    keywords_json = excluded.keywords_json,
                    industries_json = excluded.industries_json,
                    regions_json = excluded.regions_json,
                    people_json = excluded.people_json,
                    companies_json = excluded.companies_json,
                    source_domains_json = excluded.source_domains_json,
                    source_urls_json = excluded.source_urls_json,
                    must_include_json = excluded.must_include_json,
                    must_exclude_json = excluded.must_exclude_json,
                    focus_points_json = excluded.focus_points_json,
                    output_format = excluded.output_format,
                    delivery_channel = excluded.delivery_channel,
                    telegram_target = excluded.telegram_target,
                    discord_channel_id = excluded.discord_channel_id,
                    schedule_timezone = excluded.schedule_timezone,
                    schedule_time = excluded.schedule_time,
                    updated_at = excluded.updated_at
                """,
                (
                    payload.instance_id,
                    1 if payload.enabled else 0,
                    payload.brief_name,
                    payload.topic,
                    adapt_json(payload.keywords),
                    adapt_json(payload.industries),
                    adapt_json(payload.regions),
                    adapt_json(payload.people),
                    adapt_json(payload.companies),
                    adapt_json(payload.source_domains),
                    adapt_json(payload.source_urls),
                    adapt_json(payload.must_include),
                    adapt_json(payload.must_exclude),
                    adapt_json(payload.focus_points),
                    payload.output_format,
                    payload.delivery_channel,
                    payload.telegram_target,
                    payload.discord_channel_id,
                    payload.schedule_timezone,
                    payload.schedule_time,
                    now,
                    now,
                ),
            )
        return self.get(payload.instance_id)

    def mark_run(
        self,
        *,
        instance_id: str,
        scheduled_date: str,
        run_id: str,
        delivery_status: str | None = None,
        delivery_error: str | None = None,
    ) -> None:
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE openclaw_daily_news_configs
                SET last_scheduled_date = ?,
                    last_run_id = ?,
                    last_delivery_status = COALESCE(?, last_delivery_status),
                    last_delivery_error = ?,
                    updated_at = ?
                WHERE instance_id = ?
                """,
                (scheduled_date, run_id, delivery_status, delivery_error, utc_now_iso(), instance_id),
            )

    def list_enabled(self) -> list[OpenClawDailyNewsConfigResponse]:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM openclaw_daily_news_configs
                WHERE enabled = 1
                ORDER BY updated_at DESC
                """
            ).fetchall()
        return [self._row_to_model(row) for row in rows]

    def _row_to_model(self, row: sqlite3.Row) -> OpenClawDailyNewsConfigResponse:
        return OpenClawDailyNewsConfigResponse(
            instance_id=row["instance_id"],
            enabled=bool(row["enabled"]),
            brief_name=row["brief_name"],
            topic=row["topic"],
            keywords=json_loads(row["keywords_json"], []),
            industries=json_loads(row["industries_json"], []),
            regions=json_loads(row["regions_json"], []),
            people=json_loads(row["people_json"], []),
            companies=json_loads(row["companies_json"], []),
            source_domains=json_loads(row["source_domains_json"], []),
            source_urls=json_loads(row["source_urls_json"], []),
            must_include=json_loads(row["must_include_json"], []),
            must_exclude=json_loads(row["must_exclude_json"], []),
            focus_points=json_loads(row["focus_points_json"], []),
            output_format=row["output_format"],
            delivery_channel=row["delivery_channel"],
            telegram_target=row["telegram_target"],
            discord_channel_id=row["discord_channel_id"],
            schedule_timezone=row["schedule_timezone"],
            schedule_time=row["schedule_time"],
            last_scheduled_date=row["last_scheduled_date"],
            last_run_id=row["last_run_id"],
            last_delivery_status=row["last_delivery_status"],
            last_delivery_error=row["last_delivery_error"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
