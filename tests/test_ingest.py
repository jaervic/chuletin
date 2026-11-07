"""Pruebas de extraccion en el proceso aislado."""

from __future__ import annotations

from pathlib import Path

from app.ingest.runner import run_extraction


def test_extrae_pdf_con_numeros_de_pagina(sample_pdf: Path):
    result = run_extraction("pdf", str(sample_pdf))
    assert result.page_count == 3

    pages = {block.page for block in result.blocks}
    assert {1, 2, 3}.issubset(pages)

    text = " ".join(block.text for block in result.blocks).lower()
    assert "celula" in text
    assert "mitosis" in text
    assert "triangulo rectangulo" in text


def test_extrae_docx(tmp_path: Path):
    import docx

    document = docx.Document()
    document.add_heading("Tema 1: Genetica", level=1)
    document.add_paragraph("El ADN contiene la informacion genetica de los seres vivos.")
    path = tmp_path / "apuntes.docx"
    document.save(path)

    result = run_extraction("docx", str(path))
    text = " ".join(block.text for block in result.blocks).lower()
    assert "adn" in text
    assert any(block.is_heading for block in result.blocks)


def test_extrae_pptx(tmp_path: Path):
    from pptx import Presentation

    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[1])
    slide.shapes.title.text = "Tema 2: Fotosintesis"
    slide.placeholders[1].text = "Las plantas convierten la luz en energia quimica."
    path = tmp_path / "clase.pptx"
    presentation.save(path)

    result = run_extraction("pptx", str(path))
    text = " ".join(block.text for block in result.blocks).lower()
    assert "fotosintesis" in text
    assert all(block.page is not None for block in result.blocks)


def test_pdf_corrupto_da_error_claro(tmp_path: Path):
    import pytest
    from app.ingest.types import ExtractionError

    broken = tmp_path / "roto.pdf"
    broken.write_bytes(b"%PDF-1.4\nbasura sin estructura")
    with pytest.raises(ExtractionError):
        run_extraction("pdf", str(broken))
