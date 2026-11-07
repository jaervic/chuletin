"""Interfaz comun de proveedores de IA."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field


class LLMError(RuntimeError):
    """Error controlado de un proveedor (mensaje ya saneado)."""


@dataclass(slots=True)
class ChatMessage:
    role: str  # "user" | "assistant"
    content: str


@dataclass(slots=True)
class LLMUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None


@dataclass(slots=True)
class LLMResponse:
    text: str
    model: str
    usage: LLMUsage = field(default_factory=LLMUsage)


class ProviderClient:
    """Contrato que implementan todos los proveedores."""

    provider_id: str = "desconocido"

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str | None,
        model: str,
        timeout: float = 120.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = (base_url or "").rstrip("/")
        self.model = model
        self.timeout = timeout

    async def stream(
        self,
        system: str,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1400,
    ) -> AsyncIterator[str]:
        raise NotImplementedError

    async def complete(
        self,
        system: str,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.2,
        max_tokens: int = 1400,
    ) -> LLMResponse:
        parts: list[str] = []
        async for chunk in self.stream(
            system, messages, temperature=temperature, max_tokens=max_tokens
        ):
            parts.append(chunk)
        return LLMResponse(text="".join(parts), model=self.model)

    async def list_models(self) -> list[str]:
        raise NotImplementedError
