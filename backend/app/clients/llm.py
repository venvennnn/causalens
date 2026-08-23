from __future__ import annotations

import json
import re
from typing import Any, Protocol

import httpx

from app.config import get_settings
from app.exceptions import LLMExtractionError
from app.logging import log

JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def parse_json_content(text: str) -> Any:
    stripped = (text or "").strip()
    if not stripped:
        raise LLMExtractionError("Empty LLM response")
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    match = JSON_FENCE.search(stripped)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(stripped[start : end + 1])
        except json.JSONDecodeError:
            pass
    start = stripped.find("[")
    end = stripped.rfind("]")
    if start != -1 and end > start:
        try:
            return json.loads(stripped[start : end + 1])
        except json.JSONDecodeError:
            pass
    raise LLMExtractionError("LLM did not return valid JSON")


class LLMClient(Protocol):
    async def complete_json(self, system: str, user: str) -> Any: ...


class OpenAIClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        if not self.settings.openai_api_key:
            raise LLMExtractionError("OPENAI_API_KEY is not configured")

    async def complete_json(self, system: str, user: str) -> Any:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.settings.openai_api_key, timeout=self.settings.llm_timeout_s)
        response = await client.chat.completions.create(
            model=self.settings.openai_model,
            temperature=self.settings.llm_temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        content = response.choices[0].message.content or ""
        return parse_json_content(content)


class AnthropicClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        if not self.settings.anthropic_api_key:
            raise LLMExtractionError("ANTHROPIC_API_KEY is not configured")

    async def complete_json(self, system: str, user: str) -> Any:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=self.settings.anthropic_api_key, timeout=self.settings.llm_timeout_s)
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=8000,
            temperature=self.settings.llm_temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        content = "".join(block.text for block in response.content if getattr(block, "text", None))
        return parse_json_content(content)


class GeminiClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        if not self.settings.gemini_api_key:
            raise LLMExtractionError("GEMINI_API_KEY is not configured")

    async def complete_json(self, system: str, user: str) -> Any:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.settings.gemini_model}:generateContent"
        )
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": self.settings.llm_temperature,
                "responseMimeType": "application/json",
            },
        }
        timeout = httpx.Timeout(self.settings.llm_timeout_s)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                url,
                params={"key": self.settings.gemini_api_key},
                json=payload,
            )
        if response.status_code >= 400:
            raise LLMExtractionError(f"Gemini returned HTTP {response.status_code}")
        data = response.json()
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMExtractionError("Gemini response missing text") from exc
        return parse_json_content(text)


def get_llm_client() -> LLMClient:
    settings = get_settings()
    provider = settings.llm_provider
    if provider == "anthropic":
        return AnthropicClient()
    if provider == "gemini":
        return GeminiClient()
    if settings.openai_api_key:
        return OpenAIClient()
    if settings.anthropic_api_key:
        return AnthropicClient()
    if settings.gemini_api_key:
        return GeminiClient()
    raise LLMExtractionError("No LLM API key configured")


def llm_available() -> bool:
    settings = get_settings()
    return bool(settings.openai_api_key or settings.anthropic_api_key or settings.gemini_api_key)


async def complete_json_with_repair(system: str, user: str) -> Any:
    client = get_llm_client()
    started = __import__("time").monotonic()
    try:
        result = await client.complete_json(system, user)
    except Exception as first_error:
        repair_user = (
            "Your previous response was not valid JSON. Return ONLY valid JSON matching the schema.\n\n"
            f"Original request:\n{user}"
        )
        try:
            result = await client.complete_json(system, repair_user)
        except Exception as second_error:
            duration_ms = int((__import__("time").monotonic() - started) * 1000)
            log.info(
                "llm_failed",
                extra={
                    "source": "llm",
                    "duration_ms": duration_ms,
                    "success": False,
                    "error": type(second_error).__name__,
                },
            )
            raise LLMExtractionError(str(first_error)) from second_error
    duration_ms = int((__import__("time").monotonic() - started) * 1000)
    log.info("llm_ok", extra={"source": "llm", "duration_ms": duration_ms, "success": True})
    return result
