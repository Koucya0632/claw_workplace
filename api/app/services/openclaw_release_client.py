from __future__ import annotations

import json
import re
from typing import Any
from urllib import error, request

from app.services.openclaw_errors import OpenClawServiceError
from app.utils import truncate_text


VERSION_PATTERN = re.compile(r"\b\d{4}\.\d+\.\d+\b")


class OpenClawReleaseClient:
    source_mode = "official_release"

    def __init__(self, timeout_seconds: int = 15) -> None:
        self.timeout_seconds = timeout_seconds

    def fetch_release_summary(self, url: str) -> dict[str, Any]:
        try:
            with request.urlopen(url, timeout=self.timeout_seconds) as response:
                body = response.read().decode("utf-8", errors="ignore")
        except error.HTTPError as http_error:
            raise OpenClawServiceError(
                "無法取得 OpenClaw 官方版本資訊。",
                detail=str(http_error),
                source_mode=self.source_mode,
            ) from http_error
        except Exception as request_error:  # noqa: BLE001
            raise OpenClawServiceError(
                "無法取得 OpenClaw 官方版本資訊。",
                detail=str(request_error),
                source_mode=self.source_mode,
            ) from request_error

        versions = VERSION_PATTERN.findall(body)
        latest_version = versions[0] if versions else None
        summary_lines = _extract_summary_lines(body)
        return {
            "latest_version": latest_version,
            "release_summary": summary_lines[:6],
            "raw_excerpt": truncate_text(body, 1200),
            "source_url": url,
        }


def _extract_summary_lines(body: str) -> list[str]:
    if body.lstrip().startswith("{"):
        try:
            payload = json.loads(body)
            if isinstance(payload, dict):
                values = []
                for value in payload.values():
                    if isinstance(value, str):
                        values.append(value)
                    elif isinstance(value, list):
                        values.extend([item for item in value if isinstance(item, str)])
                return [truncate_text(line.strip(), 160) for line in values if line.strip()]
        except Exception:
            pass

    lines = []
    for raw_line in body.splitlines():
        line = raw_line.strip(" -#*\t")
        if len(line) < 20:
            continue
        if "{" in line and "}" in line:
            continue
        lines.append(truncate_text(line, 160))
    return lines
