from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class OpenClawConfigSetRequest(BaseModel):
    instance_id: str
    path: str
    value: Any


class OpenClawConfigValidateRequest(BaseModel):
    instance_id: str
    path: str
    value: Any


class OpenClawConfigResponse(BaseModel):
    path: str
    value: Any


class OpenClawConfigValidationResponse(BaseModel):
    valid: bool
    messages: list[str]
