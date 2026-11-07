"""Saneado de texto y deteccion de inyeccion de prompts."""

from __future__ import annotations

import html
import re

_TAG_RE = re.compile(r"<[^>]{0,400}>")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WS_RE = re.compile(r"\s+")

_DANGEROUS_BLOCK_RE = re.compile(
    r"<\s*(script|iframe|object|embed|style|form|base|link|meta)\b[^>]*>.*?<\s*/\s*\1\s*>",
    re.IGNORECASE | re.DOTALL,
)
_DANGEROUS_TAG_RE = re.compile(
    r"<\s*/?\s*(script|iframe|object|embed|style|form|base|link|meta)\b[^>]*>",
    re.IGNORECASE,
)
_EVENT_HANDLER_RE = re.compile(r"\son[a-z]{3,20}\s*=", re.IGNORECASE)
_DANGEROUS_URL_RE = re.compile(
    r"\]\(\s*(?:javascript|data|vbscript)\s*:", re.IGNORECASE
)

_INJECTION_PATTERNS = [
    r"ignora\s+(?:todas\s+)?(?:las\s+)?instrucciones",
    r"olvida\s+(?:todas\s+)?(?:tus\s+)?instrucciones",
    r"ignore\s+(?:all\s+)?(?:the\s+)?(?:previous\s+)?instructions",
    r"disregard\s+(?:all\s+)?(?:previous\s+)?instructions",
    r"system\s*prompt",
    r"prompt\s+del\s+sistema",
    r"act[uú]a\s+como\s+(?:un|una)\s+",
    r"you\s+are\s+now\s+",
    r"revela\s+(?:tu|el)\s+",
    r"reveal\s+(?:your|the)\s+",
    r"api[\s_-]?key",
    r"clave\s+(?:de\s+)?api",
    r"</?\s*(?:system|assistant|user)\s*>",
]
_INJECTION_RE = [re.compile(pattern, re.IGNORECASE) for pattern in _INJECTION_PATTERNS]


def strip_html(text: str) -> str:
    text = _DANGEROUS_BLOCK_RE.sub(" ", text or "")
    text = _DANGEROUS_TAG_RE.sub(" ", text)
    text = _TAG_RE.sub(" ", text)
    return text


def collapse(text: str) -> str:
    return _WS_RE.sub(" ", _CONTROL_RE.sub(" ", text or "")).strip()


def safe_plain(text: str, limit: int = 600) -> str:
    """Texto plano seguro para mostrar en una cita."""
    text = collapse(html.unescape(strip_html(text or "")))
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text


def safe_title(text: str, limit: int = 200) -> str:
    return safe_plain(text, limit) or "Documento"


def sanitize_markdown(text: str) -> str:
    """Defensa en profundidad sobre la salida del modelo.

    El frontend ya renderiza Markdown sin HTML crudo, pero aqui quitamos
    etiquetas peligrosas y enlaces con esquemas ejecutables.
    """
    text = _DANGEROUS_BLOCK_RE.sub("", text or "")
    text = _DANGEROUS_TAG_RE.sub("", text)
    text = _EVENT_HANDLER_RE.sub(" data-bloqueado=", text)
    text = _DANGEROUS_URL_RE.sub("](bloqueado:", text)
    return text


def detect_injection(text: str) -> list[str]:
    """Devuelve los patrones sospechosos encontrados en un texto."""
    found: list[str] = []
    if not text:
        return found
    sample = text[:20000]
    for pattern in _INJECTION_RE:
        match = pattern.search(sample)
        if match:
            found.append(match.group(0)[:80])
        if len(found) >= 5:
            break
    return found
