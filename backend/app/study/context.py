"""Seleccion de fragmentos para generar material de estudio."""

from __future__ import annotations

import math
from dataclasses import dataclass

from .. import db
from ..config import settings
from ..search.retriever import search


@dataclass(slots=True)
class StudyChunk:
    chunk_id: int
    document_id: str
    document_title: str
    source_type: str
    page_from: int | None
    page_to: int | None
    heading: str | None
    text: str


def _scope(subject_id: str, document_ids: list[str] | None) -> tuple[str, list]:
    conditions = ["d.subject_id = ?", "d.status = 'ready'"]
    params: list[object] = [subject_id]
    if document_ids:
        placeholders = ",".join("?" for _ in document_ids)
        conditions.append(f"c.document_id IN ({placeholders})")
        params.extend(document_ids)
    return " AND ".join(conditions), params


def _from_row(row) -> StudyChunk:
    return StudyChunk(
        chunk_id=int(row["id"]),
        document_id=row["document_id"],
        document_title=row["document_title"],
        source_type=row["source_type"],
        page_from=row["page_from"],
        page_to=row["page_to"],
        heading=row["heading"],
        text=row["text"],
    )


def _sample(subject_id: str, document_ids: list[str] | None, limit: int) -> list[StudyChunk]:
    """Reparte la seleccion entre documentos para no sesgar el material."""
    where, params = _scope(subject_id, document_ids)
    rows = db.query(
        f"""
        SELECT c.id, c.document_id, c.ordinal, c.page_from, c.page_to, c.heading, c.text,
               d.title AS document_title, d.source_type
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE {where}
        ORDER BY d.created_at ASC, c.ordinal ASC
        """,
        tuple(params),
    )
    if not rows:
        return []

    grouped: dict[str, list] = {}
    for row in rows:
        grouped.setdefault(row["document_id"], []).append(row)

    per_document = max(1, math.ceil(limit / max(1, len(grouped))))
    chosen: list[StudyChunk] = []

    for document_rows in grouped.values():
        document_rows.sort(key=lambda item: item["ordinal"])
        if len(document_rows) <= per_document:
            picked = document_rows
        else:
            step = len(document_rows) / per_document
            picked = [document_rows[min(len(document_rows) - 1, int(i * step))] for i in range(per_document)]
        chosen.extend(_from_row(row) for row in picked)

    return chosen


def collect_chunks(
    subject_id: str,
    document_ids: list[str] | None = None,
    topic: str | None = None,
    limit: int | None = None,
    max_chars: int | None = None,
) -> list[StudyChunk]:
    """Devuelve fragmentos representativos del ambito elegido."""
    limit = limit or settings.study_max_chunks
    max_chars = max_chars or settings.study_max_chars

    selected: list[StudyChunk] = []
    seen: set[int] = set()

    topic = (topic or "").strip()
    if topic:
        try:
            for hit in search(
                topic,
                subject_id=subject_id,
                document_ids=document_ids or None,
                limit=min(limit, 6),
            ):
                if hit.chunk_id in seen:
                    continue
                seen.add(hit.chunk_id)
                selected.append(
                    StudyChunk(
                        chunk_id=hit.chunk_id,
                        document_id=hit.document_id,
                        document_title=hit.document_title,
                        source_type=hit.source_type,
                        page_from=hit.page_from,
                        page_to=hit.page_to,
                        heading=hit.heading,
                        text=hit.text,
                    )
                )
        except Exception:
            pass

    if len(selected) < limit:
        for chunk in _sample(subject_id, document_ids, limit):
            if len(selected) >= limit:
                break
            if chunk.chunk_id in seen:
                continue
            seen.add(chunk.chunk_id)
            selected.append(chunk)

    # Limita el tamano total del contexto enviado al modelo.
    result: list[StudyChunk] = []
    total = 0
    for chunk in selected:
        if result and total + len(chunk.text) > max_chars:
            break
        result.append(chunk)
        total += len(chunk.text)

    return result
