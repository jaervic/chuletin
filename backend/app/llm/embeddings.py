"""Embeddings locales (ONNX, sin PyTorch).

El modelo se elige automaticamente entre una lista de preferencias
multilingues. Todo se calcula en el equipo: los textos completos no salen
del ordenador.
"""

from __future__ import annotations

import os
import threading

import numpy as np

from ..config import settings

PREFERRED_MODELS = [
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "intfloat/multilingual-e5-small",
    "intfloat/multilingual-e5-base",
    "BAAI/bge-small-en-v1.5",
]

_model = None
_model_name: str | None = None
_model_dim: int | None = None
_lock = threading.Lock()
_query_prefix = ""
_passage_prefix = ""


class EmbeddingError(RuntimeError):
    pass


def _supported_models() -> dict[str, dict]:
    try:
        from fastembed import TextEmbedding
    except Exception as exc:  # pragma: no cover
        raise EmbeddingError(
            "fastembed no esta instalado. Ejecuta: pip install -r backend/requirements.txt"
        ) from exc
    try:
        entries = TextEmbedding.list_supported_models()
    except Exception as exc:  # pragma: no cover
        raise EmbeddingError(f"No se pudo consultar la lista de modelos: {exc}") from exc
    result: dict[str, dict] = {}
    for entry in entries:
        name = entry.get("model") or entry.get("model_name")
        if name:
            result[str(name)] = entry
    return result


def _choose_model() -> tuple[str, int]:
    supported = _supported_models()
    for candidate in PREFERRED_MODELS:
        if candidate in supported:
            dim = int(supported[candidate].get("dim") or 384)
            return candidate, dim
    if not supported:
        raise EmbeddingError("No hay modelos de embeddings disponibles")
    name = next(iter(supported))
    dim = int(supported[name].get("dim") or 384)
    return name, dim


def load_model():
    """Carga (una sola vez) el modelo de embeddings."""
    global _model, _model_name, _model_dim, _query_prefix, _passage_prefix
    if _model is not None:
        return _model

    with _lock:
        if _model is not None:
            return _model

        name, dim = _choose_model()
        settings.models_dir.mkdir(parents=True, exist_ok=True)
        threads = min(4, max(1, (os.cpu_count() or 4) // 2))
        try:
            from fastembed import TextEmbedding

            model = TextEmbedding(
                model_name=name,
                cache_dir=str(settings.models_dir),
                threads=threads,
            )
        except Exception as exc:  # pragma: no cover
            raise EmbeddingError(
                f"No se pudo cargar el modelo de embeddings ({name}): {exc}"
            ) from exc

        is_e5 = "e5" in name.lower()
        _query_prefix = "query: " if is_e5 else ""
        _passage_prefix = "passage: " if is_e5 else ""
        _model = model
        _model_name = name
        _model_dim = dim
        return model


def model_info() -> tuple[str, int]:
    load_model()
    try:
        from .. import db

        db.set_setting("embed_model", _model_name or "")
        db.set_setting("embed_dim", str(_model_dim or 384))
    except Exception:
        pass
    return _model_name or "desconocido", _model_dim or 384


def _normalize(matrix: np.ndarray) -> np.ndarray:
    matrix = np.asarray(matrix, dtype=np.float32)
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return matrix / norms


def embed_passages(texts: list[str]) -> np.ndarray:
    if not texts:
        return np.zeros((0, _model_dim or 384), dtype=np.float32)
    model = load_model()
    prepared = [_passage_prefix + text for text in texts]
    vectors = list(model.embed(prepared, batch_size=settings.embed_batch_size))
    return _normalize(np.vstack(vectors))


def embed_query(text: str) -> np.ndarray:
    model = load_model()
    vector = next(iter(model.embed([_query_prefix + text], batch_size=1)))
    return _normalize(np.asarray(vector, dtype=np.float32))[0]


def warmup_async() -> None:
    """Precarga el modelo en segundo plano si ya esta descargado."""
    if not settings.warmup:
        return

    def _run() -> None:
        try:
            load_model()
        except Exception:
            pass

    if settings.models_dir.exists():
        threading.Thread(target=_run, daemon=True).start()
