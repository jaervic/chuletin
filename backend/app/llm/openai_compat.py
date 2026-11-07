"""Cliente generico compatible con la API de OpenAI.

Cubre OpenAI, DeepSeek, OpenCode Go, OpenRouter, Groq, Ollama y LM Studio.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from ..security.redact import redact
from .base import ChatMessage, LLMError, ProviderClient


class OpenAICompatClient(ProviderClient):
    provider_id = "openai"

    def _endpoint(self, path: str) -> str:
        if not self.base_url:
            raise LLMError("Falta la URL base del proveedor")
        return f"{self.base_url}{path}"

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def stream(
        self,
        system: str,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1400,
    ) -> AsyncIterator[str]:
        payload_messages = []
        if system:
            payload_messages.append({"role": "system", "content": system})
        for message in messages:
            payload_messages.append({"role": message.role, "content": message.content})

        body = {
            "model": self.model,
            "messages": payload_messages,
            "stream": True,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        timeout = httpx.Timeout(self.timeout, connect=15.0)
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            try:
                async with client.stream(
                    "POST", self._endpoint("/chat/completions"), json=body, headers=self._headers()
                ) as response:
                    if response.status_code >= 400:
                        raw = (await response.aread()).decode("utf-8", "replace")
                        raise LLMError(
                            f"El proveedor respondio {response.status_code}: {redact(raw)[:400]}"
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
                        for choice in data.get("choices") or []:
                            delta = choice.get("delta") or {}
                            piece = delta.get("content")
                            if piece:
                                yield piece
            except httpx.HTTPError as exc:
                raise LLMError(
                    f"No se pudo conectar con el proveedor: {redact(str(exc))}"
                ) from exc

    async def list_models(self) -> list[str]:
        timeout = httpx.Timeout(min(self.timeout, 30.0), connect=15.0)
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            try:
                response = await client.get(
                    self._endpoint("/models"), headers=self._headers()
                )
            except httpx.HTTPError as exc:
                raise LLMError(
                    f"No se pudo conectar con el proveedor: {redact(str(exc))}"
                ) from exc
        if response.status_code >= 400:
            raise LLMError(
                f"El proveedor respondio {response.status_code}: {redact(response.text)[:300]}"
            )
        try:
            data = response.json()
        except json.JSONDecodeError as exc:
            raise LLMError("El proveedor devolvio una respuesta no valida") from exc
        items = data.get("data") if isinstance(data, dict) else None
        if not isinstance(items, list):
            items = data.get("models") if isinstance(data, dict) else None
        models: list[str] = []
        for item in items or []:
            if isinstance(item, str):
                models.append(item)
            elif isinstance(item, dict):
                identifier = item.get("id") or item.get("name")
                if identifier:
                    models.append(str(identifier))
        return sorted(set(models))
