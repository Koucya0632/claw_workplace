from __future__ import annotations

import json
from typing import Any
from urllib import error, request

from app.services.openclaw_errors import OpenClawServiceError
from app.utils import truncate_text


class TelegramDeliveryClient:
    source_mode = "telegram_http"

    def __init__(self, *, bot_token: str, timeout_seconds: int = 20, source_mode: str = "telegram_http") -> None:
        self.bot_token = bot_token.strip()
        self.timeout_seconds = timeout_seconds
        self.source_mode = source_mode

    @classmethod
    def from_daily_news_settings(cls) -> "TelegramDeliveryClient":
        from app.config import get_settings

        settings = get_settings()
        return cls(
            bot_token=settings.openclaw_daily_news_telegram_bot_token,
            timeout_seconds=settings.openclaw_daily_news_telegram_timeout_seconds,
            source_mode="telegram_http_daily_news",
        )

    @classmethod
    def from_system_inspection_settings(cls) -> "TelegramDeliveryClient":
        from app.config import get_settings

        settings = get_settings()
        token = settings.openclaw_system_inspection_telegram_bot_token.strip() or settings.openclaw_daily_news_telegram_bot_token
        timeout_seconds = settings.openclaw_system_inspection_telegram_timeout_seconds
        return cls(
            bot_token=token,
            timeout_seconds=timeout_seconds,
            source_mode="telegram_http_system_inspection",
        )

    def send_markdown(self, *, chat_id: str, text: str) -> dict[str, Any]:
        try:
            return self._send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
        except OpenClawServiceError as error:
            detail = (error.detail or "").lower()
            if "can't parse entities" not in detail:
                raise
            return self._send_message(chat_id=chat_id, text=text, parse_mode=None)

    def _send_message(self, *, chat_id: str, text: str, parse_mode: str | None) -> dict[str, Any]:
        if not self.bot_token:
            raise OpenClawServiceError(
                "尚未設定 Telegram 推送 bot token。",
                detail="請在 .env 設定對應的 Telegram bot token。",
                status_code=400,
                source_mode=self.source_mode,
            )

        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode

        body = json.dumps(payload).encode("utf-8")
        api_request = request.Request(
            url=f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
            data=body,
            headers={"Content-Type": "application/json"},
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
                "Daily News Telegram 推送失敗。",
                detail=truncate_text(detail, 400),
                status_code=400,
                source_mode=self.source_mode,
            ) from http_error
        except Exception as request_error:  # noqa: BLE001
            raise OpenClawServiceError(
                "無法呼叫 Telegram Bot API。",
                detail=str(request_error),
                status_code=400,
                source_mode=self.source_mode,
            ) from request_error

        if not payload.get("ok"):
            raise OpenClawServiceError(
                "Telegram Bot API 回傳失敗。",
                detail=truncate_text(json.dumps(payload, ensure_ascii=False), 400),
                status_code=400,
                source_mode=self.source_mode,
            )

        result = payload.get("result")
        return result if isinstance(result, dict) else {"result": result}
