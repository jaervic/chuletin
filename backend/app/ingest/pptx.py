"""Extraccion de presentaciones PowerPoint (.pptx)."""

from __future__ import annotations

from pathlib import Path

from .normalize import normalize_text
from .types import Block, ExtractionError, ExtractionResult


def extract_pptx(path: Path, **_: object) -> ExtractionResult:
    try:
        from pptx import Presentation
    except ImportError as exc:  # pragma: no cover
        raise ExtractionError("python-pptx no esta instalado") from exc

    try:
        presentation = Presentation(str(path))
    except Exception as exc:
        raise ExtractionError(f"No se pudo abrir el PPTX: {exc}") from exc

    blocks: list[Block] = []
    title: str | None = None

    for index, slide in enumerate(presentation.slides, start=1):
        slide_title = None
        try:
            if slide.shapes.title is not None:
                slide_title = normalize_text(slide.shapes.title.text or "") or None
        except Exception:
            slide_title = None

        if slide_title and title is None:
            title = slide_title
        if slide_title:
            blocks.append(
                Block(text=slide_title, page=index, heading=slide_title, is_heading=True)
            )

        texts: list[str] = []
        for shape in slide.shapes:
            if not getattr(shape, "has_text_frame", False):
                continue
            text = normalize_text(shape.text_frame.text or "")
            if text and text != slide_title:
                texts.append(text)

        try:
            notes = slide.notes_slide
            if notes is not None and notes.notes_text_frame is not None:
                note_text = normalize_text(notes.notes_text_frame.text or "")
                if note_text and note_text not in texts:
                    texts.append(f"Notas: {note_text}")
        except Exception:
            pass

        if texts:
            blocks.append(Block(text="\n\n".join(texts), page=index, heading=slide_title))

    if not blocks:
        raise ExtractionError("La presentacion no contiene texto")

    return ExtractionResult(blocks=blocks, page_count=len(presentation.slides), title=title)
