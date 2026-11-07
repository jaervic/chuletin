"""Tipos compartidos por los extractores."""

from __future__ import annotations

from dataclasses import dataclass, field


class ExtractionError(RuntimeError):
    """No se pudo extraer texto del documento."""


@dataclass(slots=True)
class Block:
    """Fragmento de texto tal y como aparece en el documento origen."""

    text: str
    page: int | None = None
    heading: str | None = None
    seconds: int | None = None
    is_heading: bool = False


@dataclass(slots=True)
class Chunk:
    """Trozo listo para indexar."""

    text: str
    page_from: int | None
    page_to: int | None
    heading: str | None
    n_chars: int
    seconds: int | None = None


@dataclass(slots=True)
class ExtractionResult:
    blocks: list[Block]
    page_count: int | None = None
    title: str | None = None
    needs_ocr: bool = False
    ocr_pages: list[int] = field(default_factory=list)
    warning: str | None = None
