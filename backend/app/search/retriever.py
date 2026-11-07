"""Busqueda hibrida: FTS5 (palabras clave) + vectores, fusionados con RRF."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .. import db
from ..config import settings
from ..security.sanitize import detect_injection
from . import vectors
from .rrf import reciprocal_rank_fusion

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
MAX_PER_DOCUMENT = 3
MAX_PER_PAGE = 2


@dataclass(slots=True)
class Hit:
    chunk_id: int
    document_id: str
    text: str
    page_from: int | None
    page_to: int | None
    heading: str | None
    score: float
    document_title: str
    source_type: str
    injection_flags: list[str]


def _fts_match(query: str) -> str:
    tokens: list[str] = []
    seen: set[str] = set()
    for token in _TOKEN_RE.findall(query.lower()):
        if len(token) < 2 or token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return " OR ".join(f'"{token}"*' for token in tokens[:12])


def _load_chunks(ids: list[int]) -> dict[int, dict]:
    if not ids:
        return {}
    placeholders = ",".join("?" for _ in ids)
    rows = db.query(
        f"""
        SELECT c.id, c.document_id, c.text, c.page_from, c.page_to, c.heading,
               d.title AS document_title, d.source_type, d.subject_id
        FROM chunks c
        JOIN documents d ON d.id = c.document_id
        WHERE c.id IN ({placeholders})
        """,
        tuple(ids),
    )
    return {int(row["id"]): dict(row) for row in rows}


def _in_scope(row: dict, subject_id: str | None, document_ids: list[str] | None) -> bool:
    if subject_id and row["subject_id"] != subject_id:
        return False
    if document_ids and row["document_id"] not in document_ids:
        return False
    return True


def _fts_search(
    match: str,
    limit: int,
    subject_id: str | None,
    document_ids: list[str] | None,
) -> list[int]:
    if not match:
        return []
    conditions = ["chunks_fts MATCH ?"]
    params: list[object] = [match]
    if subject_id:
        conditions.append("d.subject_id = ?")
        params.append(subject_id)
    if document_ids:
        placeholders = ",".join("?" for _ in document_ids)
        conditions.append(f"c.document_id IN ({placeholders})")
        params.extend(document_ids)

    try:
        rows = db.query(
            f"""
            SELECT c.id AS chunk_id
            FROM chunks_fts
            JOIN chunks c ON c.id = chunks_fts.rowid
            JOIN documents d ON d.id = c.document_id
            WHERE {' AND '.join(conditions)}
            ORDER BY bm25(chunks_fts)
            LIMIT ?
            """,
            tuple(params) + (limit,),
        )
    except Exception:
        return []
    return [int(row["chunk_id"]) for row in rows]


def _vector_search(
    question: str,
    limit: int,
    subject_id: str | None,
    document_ids: list[str] | None,
) -> list[int]:
    try:
        from ..llm.embeddings import embed_query

        query_vector = embed_query(question)
    except Exception:
        return []

    if vectors._vec_present():  # noqa: SLF001 - modulo interno propio
        raw = vectors.knn(query_vector, max(limit * 6, 60))
    else:
        raw = vectors.brute_force(
            query_vector, limit * 6, subject_id=subject_id, document_ids=document_ids
        )

    if not raw:
        return []

    ids = [chunk_id for chunk_id, _ in raw]
    details = _load_chunks(ids)
    ordered: list[int] = []
    for chunk_id in ids:
        row = details.get(chunk_id)
        if row and _in_scope(row, subject_id, document_ids):
            ordered.append(chunk_id)
        if len(ordered) >= limit:
            break
    return ordered


def search(
    question: str,
    *,
    subject_id: str | None = None,
    document_ids: list[str] | None = None,
    limit: int | None = None,
) -> list[Hit]:
    """Devuelve los fragmentos mas relevantes para una pregunta."""
    limit = limit or settings.max_context_chunks
    candidates = settings.retrieval_candidates

    keyword_ids = _fts_search(
        _fts_match(question), candidates, subject_id, document_ids
    )
    vector_ids = _vector_search(question, candidates, subject_id, document_ids)

    if not keyword_ids and not vector_ids:
        return []

    if vector_ids:
        fused = reciprocal_rank_fusion([vector_ids, keyword_ids])
    else:
        fused = reciprocal_rank_fusion([keyword_ids])

    ranked_ids = sorted(fused, key=lambda chunk_id: fused[chunk_id], reverse=True)
    details = _load_chunks(ranked_ids[: candidates * 2])

    hits: list[Hit] = []
    per_document: dict[str, int] = {}
    per_page: dict[tuple[str, int | None], int] = {}

    for chunk_id in ranked_ids:
        row = details.get(chunk_id)
        if not row:
            continue
        document_id = row["document_id"]
        if per_document.get(document_id, 0) >= MAX_PER_DOCUMENT:
            continue
        page_key = (document_id, row["page_from"])
        if row["page_from"] is not None and per_page.get(page_key, 0) >= MAX_PER_PAGE:
            continue

        per_document[document_id] = per_document.get(document_id, 0) + 1
        if row["page_from"] is not None:
            per_page[page_key] = per_page.get(page_key, 0) + 1

        hits.append(
            Hit(
                chunk_id=chunk_id,
                document_id=document_id,
                text=row["text"],
                page_from=row["page_from"],
                page_to=row["page_to"],
                heading=row["heading"],
                score=round(fused[chunk_id], 6),
                document_title=row["document_title"],
                source_type=row["source_type"],
                injection_flags=detect_injection(row["text"]),
            )
        )
        if len(hits) >= limit:
            break

    return hits
