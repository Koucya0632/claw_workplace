from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now() -> datetime:
    # 所有時間一律用 UTC 儲存，前端再自行轉換，避免跨時區比對出錯。
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    # SQLite 以文字欄位保存時間時，統一使用 ISO 格式最容易互通。
    return utc_now().isoformat()


def new_id(prefix: str) -> str:
    # 以可讀前綴加 UUID 組成主鍵，除錯時比純 UUID 更容易判讀資料類型。
    return f"{prefix}_{uuid4().hex}"


def checksum_for_bytes(payload: bytes) -> str:
    # 文件 checksum 用於判斷是否重複索引或後續做增量更新。
    return hashlib.md5(payload).hexdigest()


def json_dumps(value: Any) -> str:
    # 所有 JSON 儲存都走同一個出口，避免中文被轉成難讀的 escape 字串。
    return json.dumps(value, ensure_ascii=False)


def json_loads(value: str | None, fallback: Any) -> Any:
    # 資料庫中的 JSON 欄位可能為空字串或 None，因此這裡做統一保護。
    if not value:
        return fallback
    return json.loads(value)


def truncate_text(value: str, max_length: int = 240) -> str:
    # 審計與錯誤摘要只保留前段內容，避免把大量輸出直接塞進資料庫。
    if len(value) <= max_length:
        return value
    return f"{value[: max_length - 3]}..."
