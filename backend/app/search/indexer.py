"""Escritura de fragmentos en SQLite (tabla, FTS5 y vectores)."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np

from .. import db
from ..ingest.types import Chunk
from ..utils import norm_for_search, utcnow
from . import vectors


def add_chunks(
    document_id: str,
    chunks: Iterable[Chunk],
    matrix: np.ndarray,
    *,
    start_ordinal: int = 0,
) -> int:
    inserted_ids: list[int] = []
    created = utcnow()

    for index, (chunk, vector) in enumerate(zip(chunks, matrix, strict=False)):
        text_norm = norm_for_search(chunk.text)
        chunk_id = db.insert_returning_id(
            """
            INSERT INTO chunks(
                document_id, ordinal, page_from, page_to, heading,
                text, text_norm, n_chars, embedding, created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                document_id,
                start_ordinal + index,
                chunk.page_from,
                chunk.page_to,
                chunk.heading,
                chunk.text,
                text_norm,
                chunk.n_chars,
                np.asarray(vector, dtype=np.float32).tobytes(),
                created,
            ),
        )
        db.execute(
            "INSERT INTO chunks_fts(rowid, text_norm) VALUES (?, ?)",
            (chunk_id, text_norm),
        )
        inserted_ids.append(chunk_id)

    vectors.upsert_many(inserted_ids, matrix)
    return len(inserted_ids)


def delete_document_chunks(document_id: str) -> None:
    rows = db.query("SELECT id FROM chunks WHERE document_id = ?", (document_id,))
    ids = [int(row["id"]) for row in rows]
    if not ids:
        return
    db.execute_many("DELETE FROM chunks_fts WHERE rowid = ?", [(i,) for i in ids])
    vectors.delete_chunks(ids)
    db.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
