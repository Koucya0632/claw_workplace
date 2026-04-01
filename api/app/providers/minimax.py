from __future__ import annotations

import json
from typing import Any

import httpx

from app.config import get_settings
from app.providers.base import BaseLLMProvider


class MiniMaxProvider(BaseLLMProvider):
    # MiniMaxProvider 先做成可配置 HTTP 端點，避免把未知的官方端點格式寫死。
    provider_name = "minimax"

    def health_check(self) -> dict[str, Any]:
        settings = get_settings()

        # 如果 API Key 或 URL 沒填，直接回報未就緒，前端也能據此提示使用者。
        ready = bool(settings.minimax_api_key and settings.minimax_api_url)
        return {
            "provider": self.provider_name,
            "ready": ready,
            "api_url_configured": bool(settings.minimax_api_url),
            "model": settings.minimax_model,
        }

    async def summarize_document(self, document_title: str, document_text: str) -> dict[str, Any]:
        settings = get_settings()

        # 這版不允許 silently fallback，因此配置缺失時直接拋錯。
        if not settings.minimax_api_key or not settings.minimax_api_url:
            raise RuntimeError("MiniMax 尚未配置 API URL 或 API Key。")

        # Prompt 要求盡量回傳 JSON，便於後端直接轉成結構化摘要結果。
        system_prompt = (
            "你是 OpenClaw 智能辦公室的 Organize Lobster。"
            "請針對輸入文件輸出 JSON，欄位必須包含 summary、highlights、todos、source_quotes。"
        )
        user_prompt = f"文件標題：{document_title}\n\n文件內容：\n{document_text}"

        payload = {
            # 使用官方文件中的有效模型名，避免送出不存在的模型導致 400。
            "model": settings.minimax_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
        }

        # 以 Bearer token 送出是最常見形式；若供應商格式不同，可用 env URL 配合後續微調。
        headers = {
            "Authorization": f"Bearer {settings.minimax_api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=settings.minimax_timeout_seconds) as client:
            response = await client.post(settings.minimax_api_url, headers=headers, json=payload)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as error:
                # 把供應商原始錯誤本文帶出去，之後定位 400/401/422 會快很多。
                raise RuntimeError(
                    f"MiniMax API 請求失敗：{error.response.status_code} {error.response.text}"
                ) from error
            data = response.json()

        # 這裡容忍幾種常見回應形狀，避免前端或供應商小改動就整條流程失效。
        content = None
        if isinstance(data, dict):
            choices = data.get("choices")
            if isinstance(choices, list) and choices:
                content = choices[0].get("message", {}).get("content")
            if content is None:
                content = data.get("reply") or data.get("content") or data.get("text")

        if content is None:
            raise RuntimeError("MiniMax 回應格式無法解析。")

        # 若模型已回 JSON 字串就直接解；否則以純摘要文字包成最小結構。
        try:
            parsed = json.loads(_strip_code_fence(content))
        except json.JSONDecodeError:
            parsed = {
                "summary": str(content),
                "highlights": [],
                "todos": [],
                "source_quotes": [],
            }

        return {
            "summary": str(parsed.get("summary", "")),
            "highlights": [str(item) for item in parsed.get("highlights", [])],
            "todos": [str(item) for item in parsed.get("todos", [])],
            "source_quotes": [str(item) for item in parsed.get("source_quotes", [])],
        }


def _strip_code_fence(content: str) -> str:
    # 有些模型會把 JSON 包在 ```json 區塊內，這裡先清掉外殼再解析。
    stripped = content.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()
    return stripped
