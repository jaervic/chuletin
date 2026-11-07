"""Catalogo de proveedores y seleccion del cliente activo."""

from __future__ import annotations

import json

from .. import db
from ..security.redact import forget_secret, key_hint, redact, register_secret
from .anthropic import AnthropicClient
from .base import ChatMessage, LLMError, ProviderClient
from .gemini import GeminiClient
from .openai_compat import OpenAICompatClient

CONFIG_KEY = "llm_config"

PRESETS: list[dict] = [
    {
        "id": "gemini",
        "label": "Google Gemini",
        "kind": "gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "default_model": "gemini-2.5-flash",
        "requires_key": True,
        "help_url": "https://aistudio.google.com/apikey",
    },
    {
        "id": "deepseek",
        "label": "DeepSeek",
        "kind": "openai",
        "base_url": "https://api.deepseek.com/v1",
        "default_model": "deepseek-chat",
        "requires_key": True,
        "help_url": "https://platform.deepseek.com/api_keys",
    },
    {
        "id": "opencode",
        "label": "OpenCode Go",
        "kind": "openai",
        "base_url": "",
        "default_model": "",
        "requires_key": True,
        "help_url": "",
    },
    {
        "id": "openai",
        "label": "OpenAI",
        "kind": "openai",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4.1-mini",
        "requires_key": True,
        "help_url": "https://platform.openai.com/api-keys",
    },
    {
        "id": "anthropic",
        "label": "Anthropic (Claude)",
        "kind": "anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "default_model": "claude-sonnet-4-5",
        "requires_key": True,
        "help_url": "https://console.anthropic.com/settings/keys",
    },
    {
        "id": "openrouter",
        "label": "OpenRouter",
        "kind": "openai",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "google/gemini-2.5-flash",
        "requires_key": True,
        "help_url": "https://openrouter.ai/keys",
    },
    {
        "id": "groq",
        "label": "Groq",
        "kind": "openai",
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
        "requires_key": True,
        "help_url": "https://console.groq.com/keys",
    },
    {
        "id": "ollama",
        "label": "Ollama (local)",
        "kind": "openai",
        "base_url": "http://127.0.0.1:11434/v1",
        "default_model": "llama3.2",
        "requires_key": False,
        "help_url": "https://ollama.com",
    },
]

PRESETS_BY_ID = {preset["id"]: preset for preset in PRESETS}


def preset(provider_id: str) -> dict:
    found = PRESETS_BY_ID.get(provider_id)
    if found:
        return found
    return {
        "id": provider_id,
        "label": provider_id,
        "kind": "openai",
        "base_url": "",
        "default_model": "",
        "requires_key": False,
        "help_url": "",
    }


def load_config() -> dict:
    raw = db.get_setting(CONFIG_KEY)
    data: dict = {}
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                data = parsed
        except json.JSONDecodeError:
            data = {}
    data.setdefault("provider", "gemini")
    providers = data.get("providers")
    if not isinstance(providers, dict):
        providers = {}
    data["providers"] = providers
    for entry in providers.values():
        if isinstance(entry, dict):
            register_secret(entry.get("api_key"))
    return data


def save_config(config: dict) -> None:
    db.set_setting(CONFIG_KEY, json.dumps(config, ensure_ascii=False))


def provider_state(provider_id: str, config: dict | None = None) -> dict:
    config = config or load_config()
    info = preset(provider_id)
    entry = config["providers"].get(provider_id, {}) or {}
    return {
        "provider": provider_id,
        "model": entry.get("model") or info["default_model"],
        "base_url": entry.get("base_url") or info["base_url"] or None,
        "has_key": bool(entry.get("api_key")),
        "key_hint": key_hint(entry.get("api_key")),
    }


def save_provider(
    provider_id: str,
    *,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> dict:
    config = load_config()
    entry = dict(config["providers"].get(provider_id, {}) or {})

    if model is not None:
        entry["model"] = model.strip()
    if base_url is not None:
        entry["base_url"] = base_url.strip()
    if api_key is not None:
        old = entry.get("api_key")
        new_key = api_key.strip()
        if new_key:
            if old and old != new_key:
                forget_secret(old)
            entry["api_key"] = new_key
            register_secret(new_key)
        else:
            forget_secret(old)
            entry.pop("api_key", None)

    config["providers"][provider_id] = entry
    config["provider"] = provider_id
    save_config(config)
    return provider_state(provider_id, config)


def make_client(
    *,
    provider_id: str,
    api_key: str | None,
    base_url: str | None,
    model: str,
    timeout: float = 120.0,
) -> ProviderClient:
    info = preset(provider_id)
    kind = info["kind"]
    if kind == "gemini":
        return GeminiClient(api_key=api_key, base_url=base_url, model=model, timeout=timeout)
    if kind == "anthropic":
        return AnthropicClient(api_key=api_key, base_url=base_url, model=model, timeout=timeout)
    client = OpenAICompatClient(
        api_key=api_key, base_url=base_url, model=model, timeout=timeout
    )
    client.provider_id = provider_id
    return client


def build_client(provider_id: str | None = None, model: str | None = None) -> ProviderClient:
    config = load_config()
    pid = provider_id or config.get("provider") or "gemini"
    info = preset(pid)
    entry = config["providers"].get(pid, {}) or {}
    api_key = entry.get("api_key")
    base_url = entry.get("base_url") or info["base_url"]
    chosen_model = model or entry.get("model") or info["default_model"]

    if info["requires_key"] and not api_key:
        raise LLMError(
            f"Falta la clave de {info['label']}. Configurala en Ajustes."
        )
    if not base_url and info["kind"] == "openai":
        raise LLMError(
            f"Falta la URL base de {info['label']}. Configurala en Ajustes."
        )
    if not chosen_model:
        raise LLMError(
            f"Falta el modelo de {info['label']}. Elige uno en Ajustes."
        )
    return make_client(
        provider_id=pid,
        api_key=api_key,
        base_url=base_url,
        model=chosen_model,
        timeout=float(db.get_setting("llm_timeout_s", "120") or 120),
    )


async def test_provider(
    *,
    provider_id: str,
    api_key: str | None,
    base_url: str | None,
    model: str | None,
) -> tuple[bool, str, list[str]]:
    info = preset(provider_id)
    try:
        client = make_client(
            provider_id=provider_id,
            api_key=api_key,
            base_url=base_url or info["base_url"] or None,
            model=model or info["default_model"],
            timeout=30.0,
        )
        try:
            models = await client.list_models()
        except LLMError:
            models = []
        if models:
            return True, f"Conexion correcta. {len(models)} modelos disponibles.", models
        # Algunos proveedores no exponen /models: probamos una llamada minima.
        await client.complete(
            "Responde solo con la palabra ok.",
            [ChatMessage(role="user", content="ok")],
            max_tokens=5,
            temperature=0.0,
        )
        return True, "Conexion correcta.", []
    except LLMError as exc:
        return False, redact(str(exc)), []
    except Exception as exc:  # pragma: no cover - defensivo
        return False, redact(f"Error inesperado: {exc}"), []
