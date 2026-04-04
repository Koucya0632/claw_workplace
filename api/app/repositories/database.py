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
        last_scan_at TEXT,
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
        search_agent_id TEXT NOT NULL,
        analysis_agent_id TEXT NOT NULL,
        report_agent_id TEXT NOT NULL,
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
