from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class OpenClawLogEntry(BaseModel):
    timestamp: Optional[str] = None
    level: Optional[str] = None
    message: str
    raw: Optional[str] = None
