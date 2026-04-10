import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from app.config import get_settings


SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS sources (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        type TEXT NOT NULL,
        config_json TEXT NOT NULL,
        status TEXT NOT NULL,
        is_enabled INTEGER NOT NULL DEFAULT 1,
        last_sync_status TEXT NOT NULL DEFAULT 'never_scanned',
        last_sync_error TEXT,
        last_sync_result_json TEXT NOT NULL DEFAULT '{}',
        last_scan_at TEXT,
        last_successful_sync_at TEXT,
        last_failed_sync_at TEXT,
        created_by TEXT,
        updated_by TEXT,
        role_hint TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS documents (
        id TEXT PRIMARY KEY,
        source_id TEXT NOT NULL,
        relative_path TEXT NOT NULL,
        filename TEXT NOT NULL,
        extension TEXT NOT NULL,
        mime_type TEXT,
        file_size INTEGER NOT NULL,
        checksum TEXT NOT NULL,
        modified_at TEXT NOT NULL,
        indexed_at TEXT NOT NULL,
        content_preview TEXT NOT NULL,
        extracted_text TEXT NOT NULL,
        document_kind TEXT NOT NULL DEFAULT 'local_file',
        source_url TEXT,
        canonical_url TEXT,
        published_at TEXT,
        language TEXT,
        status TEXT NOT NULL DEFAULT 'active',
        trust_score REAL,
        relevance_score REAL,
        duplicate_group_id TEXT,
        business_type TEXT,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        version_group_id TEXT,
        version_number INTEGER NOT NULL DEFAULT 1,
        supersedes_document_id TEXT,
        first_seen_at TEXT,
        last_seen_at TEXT,
        last_checked_at TEXT,
        created_by TEXT,
        updated_by TEXT,
        role_hint TEXT,
        FOREIGN KEY(source_id) REFERENCES sources(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS document_chunks (
        id TEXT PRIMARY KEY,
        document_id TEXT NOT NULL,
        chunk_index INTEGER NOT NULL,
        content TEXT NOT NULL,
        token_count INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(document_id) REFERENCES documents(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        task_type TEXT NOT NULL,
        status TEXT NOT NULL,
        input_payload TEXT NOT NULL,
        result_payload TEXT,
        error_message TEXT,
        created_by TEXT,
        updated_by TEXT,
        role_hint TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS task_events (
        id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL,
        role_name TEXT NOT NULL,
        role_status TEXT NOT NULL,
        message TEXT NOT NULL,
        metadata TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(task_id) REFERENCES tasks(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS query_logs (
        id TEXT PRIMARY KEY,
        query_text TEXT NOT NULL,
        source_filter TEXT,
        started_at TEXT NOT NULL,
        finished_at TEXT,
        result_count INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL,
        error_message TEXT,
        created_by TEXT,
        updated_by TEXT,
        role_hint TEXT
    )
    """,
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS document_chunks_fts
    USING fts5(chunk_id UNINDEXED, document_id UNINDEXED, filename, content)
    """,
    """
    CREATE TABLE IF NOT EXISTS openclaw_instances (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        gateway_url TEXT NOT NULL,
        is_active INTEGER NOT NULL DEFAULT 1,
        last_health_status TEXT,
        last_health_checked_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS openclaw_instance_secrets (
        instance_id TEXT PRIMARY KEY,
        encrypted_token TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(instance_id) REFERENCES openclaw_instances(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS openclaw_cached_snapshots (
        instance_id TEXT NOT NULL,
        snapshot_type TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY(instance_id, snapshot_type),
        FOREIGN KEY(instance_id) REFERENCES openclaw_instances(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS openclaw_operation_logs (
        id TEXT PRIMARY KEY,
        instance_id TEXT,
        operation_type TEXT NOT NULL,
        target_type TEXT NOT NULL,
        target_id TEXT,
        status TEXT NOT NULL,
        error_message TEXT,
        request_summary TEXT NOT NULL,
        response_summary TEXT,
        source_mode TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(instance_id) REFERENCES openclaw_instances(id) ON DELETE SET NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS openclaw_agent_capabilities (
        id TEXT PRIMARY KEY,
        instance_id TEXT NOT NULL,
        agent_id TEXT NOT NULL,
        capability_key TEXT NOT NULL,
        is_enabled INTEGER NOT NULL DEFAULT 0,
        config_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(instance_id, agent_id, capability_key),
        FOREIGN KEY(instance_id) REFERENCES openclaw_instances(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS openclaw_workflow_configs (
        instance_id TEXT PRIMARY KEY,
        controller_agent_id TEXT,
        search_agent_id TEXT NOT NULL,
        analysis_agent_id TEXT NOT NULL,
        report_agent_id TEXT NOT NULL,
        specialist_agents_json TEXT NOT NULL DEFAULT '{}',
        routing_rules_json TEXT NOT NULL DEFAULT '[]',
        handoff_policy_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(instance_id) REFERENCES openclaw_instances(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS openclaw_daily_news_configs (
        instance_id TEXT PRIMARY KEY,
        enabled INTEGER NOT NULL DEFAULT 1,
        brief_name TEXT NOT NULL,
        topic TEXT NOT NULL,
        keywords_json TEXT NOT NULL DEFAULT '[]',
        industries_json TEXT NOT NULL DEFAULT '[]',
        regions_json TEXT NOT NULL DEFAULT '[]',
        people_json TEXT NOT NULL DEFAULT '[]',
        companies_json TEXT NOT NULL DEFAULT '[]',
        source_domains_json TEXT NOT NULL DEFAULT '[]',
        source_urls_json TEXT NOT NULL DEFAULT '[]',
        must_include_json TEXT NOT NULL DEFAULT '[]',
        must_exclude_json TEXT NOT NULL DEFAULT '[]',
        focus_points_json TEXT NOT NULL DEFAULT '[]',
        output_format TEXT NOT NULL DEFAULT 'summary',
        delivery_channel TEXT NOT NULL DEFAULT 'telegram',
        telegram_target TEXT NOT NULL DEFAULT '',
        discord_channel_id TEXT NOT NULL DEFAULT '',
        schedule_timezone TEXT NOT NULL DEFAULT 'Asia/Tokyo',
        schedule_time TEXT NOT NULL DEFAULT '09:00',
        last_scheduled_date TEXT,
        last_run_id TEXT,
        last_delivery_status TEXT,
        last_delivery_error TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(instance_id) REFERENCES openclaw_instances(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS openclaw_system_inspection_configs (
        instance_id TEXT PRIMARY KEY,
        enabled INTEGER NOT NULL DEFAULT 0,
        schedule_timezone TEXT NOT NULL DEFAULT 'Asia/Tokyo',
        schedule_time TEXT NOT NULL DEFAULT '09:30',
        delivery_channel TEXT NOT NULL DEFAULT 'telegram',
        telegram_target TEXT NOT NULL DEFAULT '',
        discord_channel_id TEXT NOT NULL DEFAULT '',
        version_check_enabled INTEGER NOT NULL DEFAULT 1,
        log_review_enabled INTEGER NOT NULL DEFAULT 1,
        log_review_window_hours INTEGER NOT NULL DEFAULT 24,
        log_review_limit INTEGER NOT NULL DEFAULT 500,
        official_release_url TEXT NOT NULL DEFAULT 'https://docs.openclaw.ai/cli/agents',
        last_scheduled_date TEXT,
        last_run_id TEXT,
        last_delivery_status TEXT,
        last_delivery_error TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(instance_id) REFERENCES openclaw_instances(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS openclaw_development_configs (
        instance_id TEXT PRIMARY KEY,
        enabled INTEGER NOT NULL DEFAULT 0,
        delivery_channel TEXT NOT NULL DEFAULT 'discord',
        discord_channel_id TEXT NOT NULL DEFAULT '',
        last_run_id TEXT,
        last_delivery_status TEXT,
        last_delivery_error TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(instance_id) REFERENCES openclaw_instances(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS workflow_runs (
        id TEXT PRIMARY KEY,
        instance_id TEXT NOT NULL,
        workflow_type TEXT NOT NULL,
        status TEXT NOT NULL,
        current_stage TEXT,
        active_agent_id TEXT,
        overall_progress_percent INTEGER NOT NULL DEFAULT 0,
        input_payload TEXT NOT NULL,
        final_report_json TEXT,
        error_message TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(instance_id) REFERENCES openclaw_instances(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS workflow_stage_runs (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        stage_key TEXT NOT NULL,
        agent_id TEXT NOT NULL,
        status TEXT NOT NULL,
        progress_percent INTEGER NOT NULL DEFAULT 0,
        input_payload TEXT NOT NULL,
        output_payload TEXT,
        started_at TEXT,
        completed_at TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(run_id, stage_key),
        FOREIGN KEY(run_id) REFERENCES workflow_runs(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS workflow_events (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        stage_key TEXT,
        agent_id TEXT,
        status TEXT NOT NULL,
        progress_percent INTEGER NOT NULL DEFAULT 0,
        message TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(run_id) REFERENCES workflow_runs(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS document_tags (
        id TEXT PRIMARY KEY,
        document_id TEXT NOT NULL,
        tag_type TEXT NOT NULL,
        tag_value TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ingestion_runs (
        id TEXT PRIMARY KEY,
        source_id TEXT NOT NULL,
        topic TEXT NOT NULL,
        query TEXT NOT NULL,
        status TEXT NOT NULL,
        total_candidates INTEGER NOT NULL DEFAULT 0,
        accepted_count INTEGER NOT NULL DEFAULT 0,
        updated_count INTEGER NOT NULL DEFAULT 0,
        rejected_count INTEGER NOT NULL DEFAULT 0,
        agent_id TEXT,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        completed_at TEXT,
        FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ingestion_items (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        candidate_url TEXT NOT NULL,
        normalized_url TEXT,
        title TEXT NOT NULL,
        status TEXT NOT NULL,
        reject_reason TEXT,
        document_id TEXT,
        trust_score REAL,
        relevance_score REAL,
        duplicate_score REAL,
        checksum TEXT,
        source_domain TEXT NOT NULL DEFAULT '',
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        FOREIGN KEY(run_id) REFERENCES ingestion_runs(id) ON DELETE CASCADE,
        FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE SET NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS source_sync_events (
        id TEXT PRIMARY KEY,
        source_id TEXT NOT NULL,
        status TEXT NOT NULL,
        message TEXT NOT NULL,
        scanned_count INTEGER NOT NULL DEFAULT 0,
        skipped_count INTEGER NOT NULL DEFAULT 0,
        error_count INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE
    )
    """,
]

INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS idx_documents_canonical_url ON documents(canonical_url)",
    "CREATE INDEX IF NOT EXISTS idx_documents_version_group_id ON documents(version_group_id)",
    "CREATE INDEX IF NOT EXISTS idx_sources_last_sync_status ON sources(last_sync_status)",
    "CREATE INDEX IF NOT EXISTS idx_document_tags_document_id ON document_tags(document_id)",
    "CREATE INDEX IF NOT EXISTS idx_document_tags_type_value ON document_tags(tag_type, tag_value)",
    "CREATE INDEX IF NOT EXISTS idx_ingestion_runs_source_id ON ingestion_runs(source_id)",
    "CREATE INDEX IF NOT EXISTS idx_ingestion_items_run_id ON ingestion_items(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_source_sync_events_source_id ON source_sync_events(source_id)",
]


def adapt_json(value: Any) -> str:
    # 所有 JSON 欄位統一由 repository 層序列化，保持表結構簡單。
    return json.dumps(value, ensure_ascii=False)


def ensure_database_ready() -> None:
    # 啟動時先建立資料庫目錄與 schema，避免第一次請求才出現缺表錯誤。
    settings = get_settings()
    database_file: Path = settings.database_file
    database_file.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_file) as connection:
        for statement in SCHEMA_STATEMENTS:
            connection.execute(statement)
        _ensure_source_management_columns(connection)
        _ensure_openclaw_workflow_config_columns(connection)
        _ensure_openclaw_daily_news_columns(connection)
        _ensure_openclaw_system_inspection_columns(connection)
        _ensure_document_knowledge_columns(connection)
        for statement in INDEX_STATEMENTS:
            connection.execute(statement)
        connection.commit()


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    # 以 contextmanager 包裝 sqlite 連線，讓 service 可以安全地共用提交與關閉流程。
    settings = get_settings()
    connection = sqlite3.connect(settings.database_file)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def _ensure_openclaw_workflow_config_columns(connection: sqlite3.Connection) -> None:
    # SQLite 不會自動替既有資料表補欄位，因此這裡要顯式做 schema 漸進升級。
    rows = connection.execute("PRAGMA table_info(openclaw_workflow_configs)").fetchall()
    if not rows:
        return

    existing_columns = {row[1] for row in rows}
    if "controller_agent_id" not in existing_columns:
        connection.execute("ALTER TABLE openclaw_workflow_configs ADD COLUMN controller_agent_id TEXT")
        connection.execute("UPDATE openclaw_workflow_configs SET controller_agent_id = search_agent_id WHERE controller_agent_id IS NULL")
    if "specialist_agents_json" not in existing_columns:
        connection.execute("ALTER TABLE openclaw_workflow_configs ADD COLUMN specialist_agents_json TEXT NOT NULL DEFAULT '{}'")
    if "routing_rules_json" not in existing_columns:
        connection.execute("ALTER TABLE openclaw_workflow_configs ADD COLUMN routing_rules_json TEXT NOT NULL DEFAULT '[]'")
    if "handoff_policy_json" not in existing_columns:
        connection.execute("ALTER TABLE openclaw_workflow_configs ADD COLUMN handoff_policy_json TEXT NOT NULL DEFAULT '{}'")


def _ensure_source_management_columns(connection: sqlite3.Connection) -> None:
    rows = connection.execute("PRAGMA table_info(sources)").fetchall()
    if not rows:
        return

    existing_columns = {row[1] for row in rows}
    desired_columns = {
        "is_enabled": "INTEGER NOT NULL DEFAULT 1",
        "last_sync_status": "TEXT NOT NULL DEFAULT 'never_scanned'",
        "last_sync_error": "TEXT",
        "last_sync_result_json": "TEXT NOT NULL DEFAULT '{}'",
        "last_successful_sync_at": "TEXT",
        "last_failed_sync_at": "TEXT",
    }
    for column_name, definition in desired_columns.items():
        if column_name not in existing_columns:
            connection.execute(f"ALTER TABLE sources ADD COLUMN {column_name} {definition}")

    connection.execute(
        """
        UPDATE sources
        SET
            is_enabled = COALESCE(is_enabled, CASE WHEN status = 'disabled' THEN 0 ELSE 1 END),
            last_sync_status = CASE
                WHEN last_sync_status IS NOT NULL AND last_sync_status != '' THEN last_sync_status
                WHEN status = 'scanning' THEN 'syncing'
                WHEN status = 'ready' AND last_scan_at IS NOT NULL THEN 'healthy'
                ELSE 'never_scanned'
            END,
            last_sync_result_json = COALESCE(last_sync_result_json, '{}')
        """
    )


def _ensure_openclaw_daily_news_columns(connection: sqlite3.Connection) -> None:
    rows = connection.execute("PRAGMA table_info(openclaw_daily_news_configs)").fetchall()
    if not rows:
        return

    existing_columns = {row[1] for row in rows}
    if "delivery_channel" not in existing_columns:
        connection.execute("ALTER TABLE openclaw_daily_news_configs ADD COLUMN delivery_channel TEXT NOT NULL DEFAULT 'telegram'")
    if "discord_channel_id" not in existing_columns:
        connection.execute("ALTER TABLE openclaw_daily_news_configs ADD COLUMN discord_channel_id TEXT NOT NULL DEFAULT ''")


def _ensure_openclaw_system_inspection_columns(connection: sqlite3.Connection) -> None:
    rows = connection.execute("PRAGMA table_info(openclaw_system_inspection_configs)").fetchall()
    if not rows:
        return

    existing_columns = {row[1] for row in rows}
    if "delivery_channel" not in existing_columns:
        connection.execute("ALTER TABLE openclaw_system_inspection_configs ADD COLUMN delivery_channel TEXT NOT NULL DEFAULT 'telegram'")
    if "discord_channel_id" not in existing_columns:
        connection.execute("ALTER TABLE openclaw_system_inspection_configs ADD COLUMN discord_channel_id TEXT NOT NULL DEFAULT ''")


def _ensure_document_knowledge_columns(connection: sqlite3.Connection) -> None:
    rows = connection.execute("PRAGMA table_info(documents)").fetchall()
    if not rows:
        return

    existing_columns = {row[1] for row in rows}
    desired_columns = {
        "document_kind": "TEXT NOT NULL DEFAULT 'local_file'",
        "source_url": "TEXT",
        "canonical_url": "TEXT",
        "published_at": "TEXT",
        "language": "TEXT",
        "status": "TEXT NOT NULL DEFAULT 'active'",
        "trust_score": "REAL",
        "relevance_score": "REAL",
        "duplicate_group_id": "TEXT",
        "business_type": "TEXT",
        "metadata_json": "TEXT NOT NULL DEFAULT '{}'",
        "version_group_id": "TEXT",
        "version_number": "INTEGER NOT NULL DEFAULT 1",
        "supersedes_document_id": "TEXT",
        "first_seen_at": "TEXT",
        "last_seen_at": "TEXT",
        "last_checked_at": "TEXT",
    }
    for column_name, definition in desired_columns.items():
        if column_name not in existing_columns:
            connection.execute(f"ALTER TABLE documents ADD COLUMN {column_name} {definition}")
