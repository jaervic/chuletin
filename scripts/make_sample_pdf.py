"""Genera un PDF de ejemplo con tres temas para pruebas.

Uso: python scripts/make_sample_pdf.py /ruta/apuntes.pdf
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    import pymupdf as fitz
except ImportError:  # pragma: no cover
    import fitz

PAGES = [
    (
        "Tema 1: La célula",
        "La célula es la unidad básica de la vida. Todas las células tienen "
        "membrana plasmática y material genético. Las procariotas no tienen "
        "núcleo definido, mientras que las eucariotas sí.",
    ),
    (
        "Tema 2: Mitosis",
        "La mitosis es la división celular que produce dos células hijas con "
        "la misma información genética. Consta de profase, metafase, anafase "
        "y telofase.",
    ),
    (
        "Tema 3: Teorema de Pitágoras",
        "En un triángulo rectángulo, el cuadrado de la hipotenusa es igual a "
        "la suma de los cuadrados de los catetos. Se expresa como "
        "a^2 + b^2 = c^2.",
    ),
]


def build(path: Path) -> Path:
    document = fitz.open()
    for title, body in PAGES:
        page = document.new_page()
        page.insert_text((72, 80), title, fontsize=18)
        page.insert_textbox(fitz.Rect(72, 110, 520, 420), body, fontsize=11)
    document.save(path)
    document.close()
    return path


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "apuntes.pdf")
    target.parent.mkdir(parents=True, exist_ok=True)
    build(target)
    print(target)
