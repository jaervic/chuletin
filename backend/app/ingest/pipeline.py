"""Tuberia de indexacion: extraer, trocear, calcular embeddings y guardar."""

from __future__ import annotations

import asyncio
import logging

from .. import db
from ..config import settings
from ..llm import embeddings
from ..search import indexer, vectors
from ..security.limits import ingest_semaphore
from ..security.redact import redact
from ..utils import utcnow
from .chunker import chunk_blocks
from .runner import run_extraction
from .types import ExtractionError

logger = logging.getLogger("chuletin.ingest")

_ALLOWED_FIELDS = {
    "status",
    "progress",
    "error",
    "page_count",
    "chunk_count",
    "indexed_at",
    "title",
}


def _update(document_id: str, **fields) -> None:
    filtered = {key: value for key, value in fields.items() if key in _ALLOWED_FIELDS}
    if not filtered:
        return
    assignments = ", ".join(f"{key} = ?" for key in filtered)
    db.execute(
        f"UPDATE documents SET {assignments} WHERE id = ?",
        tuple(filtered.values()) + (document_id,),
    )


def _pick_title(row, extracted_title: str | None) -> str:
    current = (row["title"] or "").strip()
    original = (row["original_name"] or "").strip()
    if extracted_title and extracted_title.strip():
        if not current or current == original:
            return extracted_title.strip()[:200]
    return current or original or "Documento"


def extract_document(row) -> object:
    """Lanza la extraccion en el proceso aislado."""
    kind = row["source_type"]
    if kind in {"web", "youtube"}:
        url = row["source_uri"]
        if not url:
            raise ExtractionError("El documento no tiene URL de origen")
        return run_extraction(kind, url, {"url": url})

    path = row["file_path"]
    if not path:
        raise ExtractionError("Falta el archivo del documento")

    options: dict = {}
    if kind == "pdf":
        options.update(
            max_pages=settings.max_pages,
            ocr=db.get_setting("ocr_enabled", "0") == "1",
            ocr_lang=settings.ocr_lang,
            ocr_max_pages=settings.ocr_max_pages,
        )
    elif kind == "image":
        options.update(ocr_lang=settings.ocr_lang)

    return run_extraction(kind, str(path), options)


def _process(document_id: str) -> None:
    row = db.query_one("SELECT * FROM documents WHERE id = ?", (document_id,))
    if row is None:
        return

    try:
        _update(document_id, status="reading", progress=0.02, error=None)
        result = extract_document(row)

        _update(
            document_id,
            status="indexing",
            progress=0.1,
            page_count=result.page_count or row["page_count"],
            title=_pick_title(row, result.title),
        )

        chunks = chunk_blocks(result.blocks)
        if not chunks:
            raise ExtractionError("No se genero ningun fragmento de texto indexable")

        _, dimension = embeddings.model_info()
        vectors.ensure_table(dimension)

        indexer.delete_document_chunks(document_id)

        total = len(chunks)
        done = 0
        batch_size = max(1, settings.embed_batch_size)

        for start in range(0, total, batch_size):
            batch = chunks[start : start + batch_size]
            texts = [
                f"{chunk.heading}\n\n{chunk.text}" if chunk.heading else chunk.text
                for chunk in batch
            ]
            matrix = embeddings.embed_passages(texts)
            indexer.add_chunks(document_id, batch, matrix, start_ordinal=start)
            done += len(batch)
            _update(document_id, progress=0.1 + 0.88 * (done / max(total, 1)))

        _update(
            document_id,
            status="ready",
            progress=1.0,
            chunk_count=done,
            indexed_at=utcnow(),
        )
        logger.info("Documento indexado: %s (%s fragmentos)", document_id, done)

    except Exception as exc:  # noqa: BLE001 - se guarda el error para la UI
        message = redact(str(exc)) or exc.__class__.__name__
        logger.warning("Fallo la indexacion de %s: %s", document_id, message)
        try:
            indexer.delete_document_chunks(document_id)
        except Exception:
            pass
        _update(
            document_id,
            status="error",
            progress=0.0,
            error=message[:600],
            chunk_count=0,
        )


async def ingest_document(document_id: str) -> None:
    """Indexa un documento sin bloquear el bucle de eventos."""
    async with ingest_semaphore():
        await asyncio.to_thread(_process, document_id)


def start_ingestion(document_id: str) -> asyncio.Task:
    return asyncio.create_task(ingest_document(document_id))
