"""Configuracion comun de las pruebas."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ["CHULETIN_WARMUP"] = "false"
os.environ["CHULETIN_DATA_DIR"] = str(REPO_ROOT / "data-test")

from app import db  # noqa: E402
from app.config import settings  # noqa: E402


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "warmup", False)
    settings.ensure_dirs()
    db.init_db(settings.database_path)
    yield tmp_path
    db.close_all()


@pytest.fixture()
def sample_pdf(tmp_path) -> Path:
    """PDF de 3 paginas con texto conocido, generado al vuelo."""
    try:
        import pymupdf as fitz
    except ImportError:
        import fitz

    path = tmp_path / "apuntes.pdf"
    document = fitz.open()
    pages = [
        ("Tema 1: La celula", "La celula es la unidad basica de la vida. "
         "Todas las celulas tienen membrana plasmatica y material genetico. "
         "Las procariotas no tienen nucleo definido."),
        ("Tema 2: Mitosis", "La mitosis es el proceso de division celular. "
         "Consta de profase, metafase, anafase y telofase. "
         "El resultado son dos celulas hijas con la misma informacion genetica."),
        ("Tema 3: Teorema de Pitagoras", "En un triangulo rectangulo, el cuadrado "
         "de la hipotenusa es igual a la suma de los cuadrados de los catetos. "
         "Se expresa como a^2 + b^2 = c^2."),
    ]
    for title, body in pages:
        page = document.new_page()
        page.insert_text((72, 80), title, fontsize=18)
        page.insert_textbox(fitz.Rect(72, 110, 520, 400), body, fontsize=11)
    document.save(path)
    document.close()
    return path
