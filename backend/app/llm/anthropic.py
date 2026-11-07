"""Cliente nativo para Anthropic (Claude)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from ..security.redact import redact
from .base import ChatMessage, LLMError, ProviderClient

DEFAULT_BASE = "https://api.anthropic.com/v1"
API_VERSION = "2023-06-01"


class AnthropicClient(ProviderClient):
    provider_id = "anthropic"

    def _base(self) -> str:
        return (self.base_url or DEFAULT_BASE).rstrip("/")

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise LLMError("Falta la clave de Anthropic")
        return {
            "x-api-key": self.api_key,
            "anthropic-version": API_VERSION,
            "content-type": "application/json",
        }

    async def stream(
        self,
        system: str,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1400,
    ) -> AsyncIterator[str]:
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
            "messages": [
                {"role": "assistant" if m.role == "assistant" else "user", "content": m.content}
                for m in messages
            ],
        }
        if system:
            body["system"] = system

        timeout = httpx.Timeout(self.timeout, connect=15.0)
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            try:
                async with client.stream(
                    "POST", f"{self._base()}/messages", json=body, headers=self._headers()
                ) as response:
                    if response.status_code >= 400:
                        raw = (await response.aread()).decode("utf-8", "replace")
                        raise LLMError(
                            f"Anthropic respondio {response.status_code}: {redact(raw)[:400]}"
                        )
                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line.startswith("data:"):
                            continue
                        data_text = line[5:].strip()
                        if not data_text or data_text == "[DONE]":
                            continue
                        try:
                            data = json.loads(data_text)
                        except json.JSONDecodeError:
                            continue
                        if data.get("type") == "error":
                            message = (data.get("error") or {}).get("message", "error")
                            raise LLMError(f"Anthropic: {redact(str(message))[:300]}")
                        if data.get("type") == "content_block_delta":
                            delta = data.get("delta") or {}
                            if delta.get("type") == "text_delta" and delta.get("text"):
                                yield delta["text"]
            except httpx.HTTPError as exc:
                raise LLMError(
                    f"No se pudo conectar con Anthropic: {redact(str(exc))}"
                ) from exc

    async def list_models(self) -> list[str]:
        timeout = httpx.Timeout(min(self.timeout, 30.0), connect=15.0)
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            try:
                response = await client.get(
                    f"{self._base()}/models",
                    headers=self._headers(),
                    params={"limit": 100},
                )
            except httpx.HTTPError as exc:
                raise LLMError(
                    f"No se pudo conectar con Anthropic: {redact(str(exc))}"
                ) from exc
        if response.status_code >= 400:
            raise LLMError(
                f"Anthropic respondio {response.status_code}: {redact(response.text)[:300]}"
            )
        data = response.json()
        return sorted(
            str(item.get("id"))
            for item in data.get("data", [])
            if item.get("id")
        )
