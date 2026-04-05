from __future__ import annotations

import json
from urllib import error

import pytest

from app.config import get_settings
from app.services.discord_delivery_client import DiscordDeliveryClient, _split_discord_messages
from app.services.telegram_delivery_client import TelegramDeliveryClient


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None


def test_send_markdown_uses_dedicated_bot_token(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request_obj, timeout):
        captured["url"] = request_obj.full_url
        captured["body"] = json.loads(request_obj.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse({"ok": True, "result": {"message_id": 42, "chat": {"id": "8351185582"}}})

    monkeypatch.setenv("OPENCLAW_DAILY_NEWS_TELEGRAM_BOT_TOKEN", "daily-news-bot-token")
    monkeypatch.setenv("OPENCLAW_DAILY_NEWS_TELEGRAM_TIMEOUT_SECONDS", "12")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    get_settings.cache_clear()

    client = TelegramDeliveryClient.from_daily_news_settings()
    result = client.send_markdown(chat_id="8351185582", text="# Daily News")

    assert result["message_id"] == 42
    assert captured["url"] == "https://api.telegram.org/botdaily-news-bot-token/sendMessage"
    assert captured["body"] == {
        "chat_id": "8351185582",
        "text": "# Daily News",
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    assert captured["timeout"] == 12
    get_settings.cache_clear()


def test_send_markdown_falls_back_to_plain_text_when_markdown_parse_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []

    class FakeHttpError(error.HTTPError):
        def __init__(self):
            super().__init__(
                url="https://api.telegram.org/botdaily-news-bot-token/sendMessage",
                code=400,
                msg="Bad Request",
                hdrs=None,
                fp=None,
            )

        def read(self) -> bytes:
            return json.dumps(
                {
                    "ok": False,
                    "error_code": 400,
                    "description": "Bad Request: can't parse entities: Can't find end of the entity",
                }
            ).encode("utf-8")

    def fake_urlopen(request_obj, timeout):
        body = json.loads(request_obj.data.decode("utf-8"))
        calls.append({"body": body, "timeout": timeout})
        if len(calls) == 1:
            raise FakeHttpError()
        return FakeResponse({"ok": True, "result": {"message_id": 99, "chat": {"id": "8351185582"}}})

    monkeypatch.setenv("OPENCLAW_DAILY_NEWS_TELEGRAM_BOT_TOKEN", "daily-news-bot-token")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    get_settings.cache_clear()

    client = TelegramDeliveryClient.from_daily_news_settings()
    result = client.send_markdown(chat_id="8351185582", text="# Daily News _brief_")

    assert result["message_id"] == 99
    assert calls[0]["body"]["parse_mode"] == "Markdown"
    assert "parse_mode" not in calls[1]["body"]
    assert calls[1]["body"]["text"] == "# Daily News _brief_"
    get_settings.cache_clear()


def test_system_inspection_uses_separate_bot_token(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request_obj, timeout):
        captured["url"] = request_obj.full_url
        captured["body"] = json.loads(request_obj.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse({"ok": True, "result": {"message_id": 7, "chat": {"id": "8351185582"}}})

    monkeypatch.setenv("OPENCLAW_DAILY_NEWS_TELEGRAM_BOT_TOKEN", "daily-news-bot-token")
    monkeypatch.setenv("OPENCLAW_SYSTEM_INSPECTION_TELEGRAM_BOT_TOKEN", "system-inspection-bot-token")
    monkeypatch.setenv("OPENCLAW_SYSTEM_INSPECTION_TELEGRAM_TIMEOUT_SECONDS", "18")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    get_settings.cache_clear()

    client = TelegramDeliveryClient.from_system_inspection_settings()
    result = client.send_markdown(chat_id="8351185582", text="# Inspection")

    assert result["message_id"] == 7
    assert captured["url"] == "https://api.telegram.org/botsystem-inspection-bot-token/sendMessage"
    assert captured["body"]["text"] == "# Inspection"
    assert captured["timeout"] == 18
    get_settings.cache_clear()


def test_discord_delivery_uses_dedicated_bot_token(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request_obj, timeout):
        captured["url"] = request_obj.full_url
        captured["body"] = json.loads(request_obj.data.decode("utf-8"))
        captured["headers"] = dict(request_obj.header_items())
        captured["timeout"] = timeout
        return FakeResponse({"id": "9001", "channel_id": "123456"})

    monkeypatch.setenv("OPENCLAW_DAILY_NEWS_DISCORD_BOT_TOKEN", "daily-news-discord-token")
    monkeypatch.setenv("OPENCLAW_DAILY_NEWS_DISCORD_TIMEOUT_SECONDS", "9")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    get_settings.cache_clear()

    client = DiscordDeliveryClient.from_daily_news_settings()
    result = client.send_text(channel_id="123456", text="daily brief")

    assert result["message_count"] == 1
    assert result["channel_id"] == "123456"
    assert captured["url"] == "https://discord.com/api/v10/channels/123456/messages"
    assert captured["body"] == {"content": "daily brief"}
    assert captured["headers"]["Authorization"] == "Bot daily-news-discord-token"
    assert captured["headers"]["User-agent"] == "DiscordBot (https://openclaw.local/discord-delivery, 1.0)"
    assert captured["headers"]["Accept"] == "application/json"
    assert captured["timeout"] == 9
    get_settings.cache_clear()


def test_discord_delivery_splits_long_messages() -> None:
    chunks = _split_discord_messages(("A" * 1000) + "\n\n" + ("B" * 1000), max_chars=1200)
    assert len(chunks) == 2
    assert chunks[0].startswith("A")
    assert chunks[1].startswith("B")
