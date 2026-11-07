"""Utilidades pequenas y sin dependencias."""

from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import datetime, timezone

_WS_RE = re.compile(r"[ \t\u00a0]+")
_MULTI_NL_RE = re.compile(r"\n{3,}")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def utcnow() -> str:
    """Fecha ISO 8601 en UTC, sin microsegundos."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex


def clean_text(text: str) -> str:
    """Normaliza espacios, saltos de linea y caracteres de control."""
    text = unicodedata.normalize("NFC", text or "")
    text = _CONTROL_RE.sub(" ", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WS_RE.sub(" ", text)
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)
    return _MULTI_NL_RE.sub("\n\n", text).strip()


def norm_for_search(text: str) -> str:
    """Version para el indice FTS (minusculas y espacios colapsados)."""
    return clean_text(text).lower()


def truncate(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def slugify(text: str, limit: int = 60) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:limit] or "documento"


def human_pages(page_from: int | None, page_to: int | None) -> str | None:
    if page_from is None:
        return None
    if page_to is None or page_to == page_from:
        return f"p. {page_from}"
    return f"pp. {page_from}-{page_to}"


def seconds_to_timestamp(seconds: int | float | None) -> str | None:
    if seconds is None:
        return None
    total = int(seconds)
    return f"{total // 60:02d}:{total % 60:02d}"
