"""Ajustes de proveedor de IA y OCR."""

from __future__ import annotations

from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import settings
from ..llm import registry
from ..schemas import ProviderConfig, ProviderOut, ProviderTest

router = APIRouter(prefix="/api/settings", tags=["settings"])


class OcrSetting(BaseModel):
    enabled: bool


def _validate_base_url(base_url: str | None) -> None:
    if not base_url:
        return
    parts = urlsplit(base_url)
    if parts.scheme not in {"http", "https"}:
        raise HTTPException(status_code=400, detail="La URL base debe ser http o https")
    if not parts.hostname:
        raise HTTPException(status_code=400, detail="La URL base no tiene host")


def _embedding_status() -> dict:
    model = None
    dimension = None
    try:
        from .. import db

        model = db.get_setting("embed_model")
        stored_dim = db.get_setting("embed_dim")
        dimension = int(stored_dim) if stored_dim else None
    except Exception:
        pass
    ready = False
    try:
        ready = any(settings.models_path.glob("**/*.onnx"))
    except OSError:
        ready = False
    return {"model": model, "dim": dimension, "ready": ready}


@router.get("")
def get_settings() -> dict:
    config = registry.load_config()
    providers = []
    for preset in registry.PRESETS:
        state = registry.provider_state(preset["id"], config)
        providers.append({**preset, **state})
    return {
        "current": config.get("provider"),
        "providers": providers,
        "ocr_enabled": _ocr_enabled(),
        "embeddings": _embedding_status(),
        "limits": {
            "max_upload_mb": settings.max_upload_mb,
            "max_pages": settings.max_pages,
            "max_context_chunks": settings.max_context_chunks,
        },
    }


def _ocr_enabled() -> bool:
    from .. import db

    return db.get_setting("ocr_enabled", "0") == "1"


@router.put("/provider", response_model=ProviderOut)
def update_provider(payload: ProviderConfig) -> ProviderOut:
    known = {preset["id"] for preset in registry.PRESETS}
    if payload.provider not in known:
        raise HTTPException(status_code=400, detail="Proveedor desconocido")
    _validate_base_url(payload.base_url)

    state = registry.save_provider(
        payload.provider,
        model=payload.model or None,
        api_key=payload.api_key,
        base_url=payload.base_url,
    )
    return ProviderOut(**state)


@router.post("/provider/test", response_model=ProviderTest)
async def test_provider(payload: ProviderConfig) -> ProviderTest:
    config = registry.load_config()
    entry = config["providers"].get(payload.provider, {}) or {}
    api_key = payload.api_key if payload.api_key else entry.get("api_key")
    base_url = payload.base_url or entry.get("base_url")
    model = payload.model or entry.get("model")

    _validate_base_url(base_url)
    ok, message, models = await registry.test_provider(
        provider_id=payload.provider,
        api_key=api_key,
        base_url=base_url,
        model=model,
    )
    return ProviderTest(ok=ok, message=message, models=models)


@router.get("/models")
async def list_models(provider: str) -> dict:
    config = registry.load_config()
    entry = config["providers"].get(provider, {}) or {}
    preset = registry.preset(provider)
    client = registry.make_client(
        provider_id=provider,
        api_key=entry.get("api_key"),
        base_url=entry.get("base_url") or preset["base_url"] or None,
        model=entry.get("model") or preset["default_model"],
        timeout=30.0,
    )
    try:
        models = await client.list_models()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"provider": provider, "models": models}


@router.put("/ocr")
def update_ocr(payload: OcrSetting) -> dict:
    from .. import db

    db.set_setting("ocr_enabled", "1" if payload.enabled else "0")
    return {"ocr_enabled": payload.enabled}
