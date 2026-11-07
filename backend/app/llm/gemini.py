"""Cliente nativo para Google Gemini (API generateContent)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from ..security.redact import redact
from .base import ChatMessage, LLMError, ProviderClient

DEFAULT_BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiClient(ProviderClient):
    provider_id = "gemini"

    def _base(self) -> str:
        return (self.base_url or DEFAULT_BASE).rstrip("/")

    def _endpoint(self, action: str) -> str:
        return f"{self._base()}/models/{self.model}:{action}"

    def _body(self, system: str, messages: list[ChatMessage], temperature: float, max_tokens: int) -> dict:
        contents = []
        for message in messages:
            role = "model" if message.role == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": message.content}]})
        body: dict = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        return body

    @staticmethod
    def _extract_text(payload: dict) -> str:
        feedback = payload.get("promptFeedback") or {}
        if feedback.get("blockReason"):
            raise LLMError("El proveedor bloqueo la peticion por sus filtros de seguridad")
        text_parts: list[str] = []
        for candidate in payload.get("candidates") or []:
            content = candidate.get("content") or {}
            for part in content.get("parts") or []:
                piece = part.get("text")
                if piece:
                    text_parts.append(piece)
        return "".join(text_parts)

    async def stream(
        self,
        system: str,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1400,
    ) -> AsyncIterator[str]:
        if not self.api_key:
            raise LLMError("Falta la clave de Gemini")
        params = {"alt": "sse", "key": self.api_key}
        body = self._body(system, messages, temperature, max_tokens)

        timeout = httpx.Timeout(self.timeout, connect=15.0)
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            try:
                async with client.stream(
                    "POST", self._endpoint("streamGenerateContent"), params=params, json=body
                ) as response:
                    if response.status_code >= 400:
                        raw = (await response.aread()).decode("utf-8", "replace")
                        raise LLMError(
                            f"Gemini respondio {response.status_code}: {redact(raw)[:400]}"
                        )
                    async for line in response.aiter_lines():
                        line = line.strip()
                        if not line.startswith("data:"):
                            continue
                        payload_text = line[5:].strip()
                        if not payload_text or payload_text == "[DONE]":
                            continue
                        try:
                            payload = json.loads(payload_text)
                        except json.JSONDecodeError:
                            continue
                        piece = self._extract_text(payload)
                        if piece:
                            yield piece
            except httpx.HTTPError as exc:
                raise LLMError(f"No se pudo conectar con Gemini: {redact(str(exc))}") from exc

    async def list_models(self) -> list[str]:
        if not self.api_key:
            raise LLMError("Falta la clave de Gemini")
        timeout = httpx.Timeout(min(self.timeout, 30.0), connect=15.0)
        async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
            try:
                response = await client.get(
                    f"{self._base()}/models",
                    params={"key": self.api_key, "pageSize": 200},
                )
            except httpx.HTTPError as exc:
                raise LLMError(f"No se pudo conectar con Gemini: {redact(str(exc))}") from exc
        if response.status_code >= 400:
            raise LLMError(
                f"Gemini respondio {response.status_code}: {redact(response.text)[:300]}"
            )
        data = response.json()
        models = []
        for item in data.get("models", []):
            name = str(item.get("name", "")).replace("models/", "")
            methods = item.get("supportedGenerationMethods") or []
            if name and (not methods or "generateContent" in methods):
                models.append(name)
        return sorted(models)
