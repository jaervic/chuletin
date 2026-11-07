"""Extraccion de texto en imagenes y fotos de apuntes (OCR)."""

from __future__ import annotations

from pathlib import Path

from .normalize import normalize_text
from .types import Block, ExtractionError, ExtractionResult


def extract_image(path: Path, *, ocr_lang: str = "spa+eng", **_: object) -> ExtractionResult:
    try:
        import pytesseract
        from PIL import Image, ImageOps
    except ImportError as exc:  # pragma: no cover
        raise ExtractionError(
            "El OCR necesita Pillow y pytesseract: pip install -r backend/requirements.txt"
        ) from exc

    try:
        image = Image.open(path)
        image = ImageOps.exif_transpose(image)
        image = image.convert("RGB")
    except Exception as exc:
        raise ExtractionError(f"No se pudo abrir la imagen: {exc}") from exc

    try:
        text = pytesseract.image_to_string(image, lang=ocr_lang)
    except pytesseract.TesseractNotFoundError as exc:
        raise ExtractionError(
            "Tesseract no esta instalado. Instalalo con: "
            "sudo apt install tesseract-ocr tesseract-ocr-spa"
        ) from exc
    except Exception:
        try:
            text = pytesseract.image_to_string(image, lang="eng")
        except Exception as exc:
            raise ExtractionError(f"Fallo el OCR de la imagen: {exc}") from exc

    text = normalize_text(text)
    if len(text) < 10:
        raise ExtractionError(
            "No se reconocio texto suficiente en la imagen. "
            "Prueba con una foto mas nitida o usa un PDF."
        )

    return ExtractionResult(blocks=[Block(text=text, page=1)], page_count=1)
