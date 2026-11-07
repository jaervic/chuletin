"""Extraccion de documentos Word (.docx)."""

from __future__ import annotations

from pathlib import Path

from .normalize import normalize_text
from .types import Block, ExtractionError, ExtractionResult

_HEADING_PREFIXES = ("heading", "título", "titulo", "title", "subtítulo", "subtitle")


def _iter_block_items(document):
    """Recorre parrafos y tablas en el orden real del documento."""
    from docx.oxml.ns import qn
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    body = document.element.body
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, document)
        elif child.tag == qn("w:tbl"):
            yield Table(child, document)


def _style_name(paragraph) -> str:
    try:
        return (paragraph.style.name or "").strip().lower()
    except Exception:
        return ""


def extract_docx(path: Path, **_: object) -> ExtractionResult:
    try:
        import docx
    except ImportError as exc:  # pragma: no cover
        raise ExtractionError("python-docx no esta instalado") from exc

    try:
        document = docx.Document(str(path))
    except Exception as exc:
        raise ExtractionError(f"No se pudo abrir el DOCX: {exc}") from exc

    blocks: list[Block] = []
    heading: str | None = None

    for item in _iter_block_items(document):
        if hasattr(item, "rows"):  # tabla
            rows: list[str] = []
            for row in item.rows:
                cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                if any(cells):
                    rows.append(" | ".join(cells))
            table_text = normalize_text("\n".join(rows))
            if table_text:
                blocks.append(Block(text=table_text, heading=heading))
            continue

        text = normalize_text(item.text or "")
        if not text:
            continue

        style = _style_name(item)
        if any(style.startswith(prefix) for prefix in _HEADING_PREFIXES):
            heading = text
            blocks.append(Block(text=text, heading=text, is_heading=True))
            continue

        blocks.append(Block(text=text, heading=heading))

    if not blocks:
        raise ExtractionError("El documento no contiene texto")

    title = None
    try:
        core = document.core_properties
        title = (core.title or "").strip() or None
    except Exception:
        title = None

    return ExtractionResult(blocks=blocks, page_count=None, title=title)
