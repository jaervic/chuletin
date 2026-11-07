"""Extraccion de PDF con PyMuPDF, conservando numeros de pagina."""

from __future__ import annotations

import io
from collections import Counter
from pathlib import Path

from .normalize import looks_like_heading, normalize_text
from .types import Block, ExtractionError, ExtractionResult

BOLD_FLAG = 1 << 4
MIN_TEXT_PER_PAGE = 25


def _analyse_page(page, page_number: int, heading: str | None) -> tuple[list[Block], str | None]:
    data = page.get_text("dict")
    text_blocks = [block for block in data.get("blocks", []) if block.get("type") == 0]

    sizes: Counter[float] = Counter()
    for block in text_blocks:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = (span.get("text") or "").strip()
                if text:
                    sizes[round(float(span.get("size") or 0), 1)] += len(text)

    body_size = sizes.most_common(1)[0][0] if sizes else 0.0
    blocks: list[Block] = []

    for raw_block in text_blocks:
        lines: list[str] = []
        max_size = 0.0
        for line in raw_block.get("lines", []):
            pieces: list[str] = []
            for span in line.get("spans", []):
                text = span.get("text") or ""
                if not text.strip():
                    continue
                pieces.append(text)
                max_size = max(max_size, float(span.get("size") or 0))
                if int(span.get("flags") or 0) & BOLD_FLAG:
                    pass
            if pieces:
                lines.append("".join(pieces).strip())

        text = normalize_text("\n".join(line for line in lines if line))
        if not text:
            continue

        is_heading = (
            body_size > 0
            and max_size >= body_size * 1.15
            and looks_like_heading(text)
        )
        if is_heading:
            heading = text
            blocks.append(Block(text=text, page=page_number, heading=heading, is_heading=True))
            continue

        blocks.append(Block(text=text, page=page_number, heading=heading))

    return blocks, heading


def _ocr_page(page, language: str) -> tuple[str, str | None]:
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return "", "El OCR no esta disponible: faltan pytesseract o Pillow"

    pixmap = page.get_pixmap(dpi=200)
    image = Image.open(io.BytesIO(pixmap.tobytes("png")))
    try:
        return pytesseract.image_to_string(image, lang=language), None
    except pytesseract.TesseractNotFoundError:
        return "", "Tesseract no esta instalado; las paginas escaneadas no se pueden leer"
    except Exception:
        try:
            return pytesseract.image_to_string(image, lang="eng"), None
        except Exception as exc:
            return "", f"Fallo el OCR: {exc}"


def extract_pdf(
    path: Path,
    *,
    max_pages: int = 2000,
    ocr: bool = False,
    ocr_lang: str = "spa+eng",
    ocr_max_pages: int = 40,
) -> ExtractionResult:
    try:
        try:
            import pymupdf as fitz  # PyMuPDF >= 1.24
        except ImportError:  # pragma: no cover
            import fitz
    except ImportError as exc:  # pragma: no cover
        raise ExtractionError("PyMuPDF no esta instalado") from exc

    try:
        document = fitz.open(path)
    except Exception as exc:
        raise ExtractionError(f"No se pudo abrir el PDF: {exc}") from exc

    try:
        if document.needs_pass:
            raise ExtractionError("El PDF esta protegido con contrasena")

        page_count = int(document.page_count)
        if page_count == 0:
            raise ExtractionError("El PDF no tiene paginas")

        blocks: list[Block] = []
        ocr_pages: list[int] = []
        warnings: list[str] = []
        heading: str | None = None

        for index in range(min(page_count, max_pages)):
            page = document.load_page(index)
            page_number = index + 1
            page_blocks, heading = _analyse_page(page, page_number, heading)
            text_length = sum(len(block.text) for block in page_blocks)

            if text_length < MIN_TEXT_PER_PAGE:
                ocr_pages.append(page_number)
                if ocr and len(ocr_pages) <= ocr_max_pages:
                    text, warning = _ocr_page(page, ocr_lang)
                    if warning:
                        warnings.append(warning)
                    elif text.strip():
                        blocks.append(
                            Block(
                                text=normalize_text(text),
                                page=page_number,
                                heading=heading,
                            )
                        )
                continue

            blocks.extend(page_blocks)

        if not blocks:
            if ocr_pages:
                raise ExtractionError(
                    "El PDF parece escaneado y no se pudo leer texto. "
                    "Activa el OCR en Ajustes o sube una version con texto."
                )
            raise ExtractionError("No se encontro texto en el PDF")

        metadata = document.metadata or {}
        title = (metadata.get("title") or "").strip() or None

        warning = None
        if ocr_pages and not ocr:
            warning = (
                f"{len(ocr_pages)} pagina(s) sin texto (escaneadas). "
                "Activa el OCR para incluirlas."
            )
        elif warnings:
            warning = warnings[0]

        return ExtractionResult(
            blocks=blocks,
            page_count=page_count,
            title=title,
            needs_ocr=bool(ocr_pages),
            ocr_pages=ocr_pages,
            warning=warning,
        )
    finally:
        document.close()
