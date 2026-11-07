"""Extraccion de paginas web con proteccion SSRF."""

from __future__ import annotations

import asyncio
import re

from ..security.ssrf import UnsafeURLError, safe_fetch
from .normalize import normalize_text
from .types import Block, ExtractionError, ExtractionResult

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)


def _extract_title(data: bytes) -> str | None:
    try:
        import trafilatura

        metadata = trafilatura.extract_metadata(data)
        if metadata and metadata.title:
            return metadata.title.strip() or None
    except Exception:
        pass
    try:
        match = _TITLE_RE.search(data.decode("utf-8", "replace"))
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip()[:200] or None
    except Exception:
        pass
    return None


def extract_web(url: str, **_: object) -> ExtractionResult:
    try:
        fetched = asyncio.run(
            safe_fetch(
                url,
                accept="text/html,application/xhtml+xml;q=0.9,text/plain;q=0.5",
            )
        )
    except UnsafeURLError as exc:
        raise ExtractionError(str(exc)) from exc

    if not fetched.data:
        raise ExtractionError("La pagina no devolvio contenido")

    try:
        import trafilatura

        text = trafilatura.extract(
            fetched.data,
            url=fetched.final_url,
            include_comments=False,
            include_tables=True,
            favor_recall=True,
        )
    except Exception as exc:
        raise ExtractionError(f"No se pudo analizar la pagina: {exc}") from exc

    text = normalize_text(text or "")
    if len(text) < 50:
        raise ExtractionError(
            "No se pudo extraer texto util de la pagina (puede requerir JavaScript o pago)"
        )

    title = _extract_title(fetched.data) or fetched.final_url

    return ExtractionResult(
        blocks=[Block(text=text, heading=title)],
        page_count=None,
        title=title,
    )
