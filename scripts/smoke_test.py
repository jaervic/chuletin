"""Prueba de extremo a extremo sin interfaz.

Crea una base de datos temporal, indexa un PDF de ejemplo y lanza una
busqueda. Sirve para comprobar que embeddings y recuperacion funcionan.

Uso: python scripts/smoke_test.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))
os.environ["CHULETIN_WARMUP"] = "false"


def main() -> int:
    from app import db
    from app.config import settings

    workdir = Path(tempfile.mkdtemp(prefix="chuletin-smoke-"))
    settings.data_dir = workdir
    settings.models_dir = REPO_ROOT / "data" / "models"
    settings.ensure_dirs()
    db.init_db(workdir / "smoke.db")

    try:
        import pymupdf as fitz
    except ImportError:
        import fitz

    pdf_path = workdir / "apuntes.pdf"
    document = fitz.open()
    pages = [
        (
            "Tema 1: La celula",
            "La celula es la unidad basica de la vida. Todas las celulas "
            "tienen membrana plasmatica y material genetico.",
        ),
        (
            "Tema 2: Mitosis",
            "La mitosis es la division celular que produce dos celulas hijas "
            "con la misma informacion genetica.",
        ),
        (
            "Tema 3: Teorema de Pitagoras",
            "En un triangulo rectangulo, el cuadrado de la hipotenusa es igual "
            "a la suma de los cuadrados de los catetos: a^2 + b^2 = c^2.",
        ),
    ]
    for title, body in pages:
        page = document.new_page()
        page.insert_text((72, 80), title, fontsize=18)
        page.insert_textbox(fitz.Rect(72, 110, 520, 400), body, fontsize=11)
    document.save(pdf_path)
    document.close()

    from app.ingest.pipeline import _process
    from app.search.retriever import search
    from app.utils import new_id, utcnow

    subject_id = new_id()
    document_id = new_id()
    db.execute(
        "INSERT INTO subjects(id, name, color, created_at) VALUES(?,?,?,?)",
        (subject_id, "Biologia", "#6366f1", utcnow()),
    )
    db.execute(
        """
        INSERT INTO documents(
            id, subject_id, title, original_name, source_type, file_path,
            sha256, size_bytes, status, progress, created_at
        ) VALUES(?,?,?,?,?,?,?,?,'pending',0,?)
        """,
        (
            document_id,
            subject_id,
            "Apuntes de biologia",
            pdf_path.name,
            "pdf",
            str(pdf_path),
            "smoke-" + document_id,
            pdf_path.stat().st_size,
            utcnow(),
        ),
    )

    print("Indexando PDF de ejemplo...")
    _process(document_id)

    row = db.query_one("SELECT status, chunk_count, error FROM documents WHERE id = ?", (document_id,))
    print(f"Estado: {row['status']} · fragmentos: {row['chunk_count']}")
    if row["status"] != "ready":
        print(f"Error: {row['error']}")
        return 1

    for question in (
        "Que es la mitosis?",
        "Como se calcula la hipotenusa?",
        "Que dice sobre la fotosintesis?",
    ):
        hits = search(question, limit=3)
        print(f"\nPregunta: {question}")
        if not hits:
            print("  sin resultados")
            continue
        for hit in hits:
            locator = f"p. {hit.page_from}" if hit.page_from else "sin pagina"
            print(f"  [{hit.score:.4f}] {hit.document_title} · {locator}")
            print(f"      {hit.text[:110]}...")

    db.close_all()
    print("\nPrueba completada.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
