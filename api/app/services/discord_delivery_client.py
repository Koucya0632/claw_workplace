from __future__ import annotations

import json
from urllib import error, request

from app.services.openclaw_errors import OpenClawServiceError
from app.utils import truncate_text

DISCORD_MESSAGE_MAX_CHARS = 1800
DISCORD_HTTP_USER_AGENT = "DiscordBot (https://openclaw.local/discord-delivery, 1.0)"


def _split_discord_messages(text: str, *, max_chars: int = DISCORD_MESSAGE_MAX_CHARS) -> list[str]:
    normalized = text.strip()
    if not normalized:
        return [""]
    if len(normalized) <= max_chars:
        return [normalized]

    paragraphs = [part.strip() for part in normalized.split("\n\n") if part.strip()]
    if not paragraphs:
        paragraphs = [normalized]

    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = ""
        if len(paragraph) <= max_chars:
            current = paragraph
            continue
        start = 0
        while start < len(paragraph):
            end = min(start + max_chars, len(paragraph))
            chunks.append(paragraph[start:end])
            start = end

    if current:
        chunks.append(current)
    return chunks or [normalized[:max_chars]]


class DiscordDeliveryClient:
    def __init__(self, *, bot_token: str, timeout_seconds: int = 20, source_mode: str = "discord_http") -> None:
        self.bot_token = bot_token.strip()
        self.timeout_seconds = timeout_seconds
        self.source_mode = source_mode

    @classmethod
    def from_daily_news_settings(cls) -> "DiscordDeliveryClient":
        from app.config import get_settings

        settings = get_settings()
        return cls(
            bot_token=settings.openclaw_daily_news_discord_bot_token,
            timeout_seconds=settings.openclaw_daily_news_discord_timeout_seconds,
            source_mode="discord_http_daily_news",
        )

    @classmethod
    def from_system_inspection_settings(cls) -> "DiscordDeliveryClient":
        from app.config import get_settings

        settings = get_settings()
        token = settings.openclaw_system_inspection_discord_bot_token.strip() or settings.openclaw_daily_news_discord_bot_token
        timeout_seconds = settings.openclaw_system_inspection_discord_timeout_seconds
        return cls(
            bot_token=token,
            timeout_seconds=timeout_seconds,
            source_mode="discord_http_system_inspection",
        )

    @classmethod
    def from_development_settings(cls) -> "DiscordDeliveryClient":
        from app.config import get_settings

        settings = get_settings()
        token = settings.openclaw_development_discord_bot_token.strip() or settings.openclaw_daily_news_discord_bot_token
        timeout_seconds = settings.openclaw_development_discord_timeout_seconds
        return cls(
            bot_token=token,
            timeout_seconds=timeout_seconds,
            source_mode="discord_http_development",
        )

    def send_text(self, *, channel_id: str, text: str) -> dict[str, object]:
        if not self.bot_token:
            raise OpenClawServiceError(
                "尚未設定 Discord 推送 bot token。",
                detail="請在 .env 設定對應的 Discord bot token。",
                status_code=400,
                source_mode=self.source_mode,
            )

        messages = _split_discord_messages(text)
        message_ids: list[str] = []
        channel_result: str | None = None
        for content in messages:
            result = self._send_message(channel_id=channel_id, text=content)
            message_id = str(result.get("id", ""))
            if message_id:
                message_ids.append(message_id)
            channel_result = str(result.get("channel_id", channel_result or channel_id))

        return {
            "message_ids": message_ids,
            "channel_id": channel_result or channel_id,
            "message_count": len(messages),
        }

    def _send_message(self, *, channel_id: str, text: str) -> dict[str, object]:
        payload = {"content": text}
        body = json.dumps(payload).encode("utf-8")
        api_request = request.Request(
            url=f"https://discord.com/api/v10/channels/{channel_id}/messages",
            data=body,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bot {self.bot_token}",
                "User-Agent": DISCORD_HTTP_USER_AGENT,
            },
            method="POST",
        )

        try:
            with request.urlopen(api_request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as http_error:
            detail = ""
            try:
                detail = http_error.read().decode("utf-8")
            except Exception:
                detail = str(http_error)
            raise OpenClawServiceError(
                "Discord 報告推送失敗。",
                detail=truncate_text(detail, 400),
                status_code=400,
                source_mode=self.source_mode,
            ) from http_error
        except Exception as request_error:  # noqa: BLE001
            raise OpenClawServiceError(
                "無法呼叫 Discord Bot API。",
                detail=str(request_error),
                status_code=400,
                source_mode=self.source_mode,
            ) from request_error

        if isinstance(payload, dict) and payload.get("id"):
            return payload

        raise OpenClawServiceError(
            "Discord Bot API 回傳失敗。",
            detail=truncate_text(json.dumps(payload, ensure_ascii=False), 400),
            status_code=400,
            source_mode=self.source_mode,
        )
