"""Indice vectorial.

Usa sqlite-vec cuando esta disponible y cae a busqueda por fuerza bruta
con numpy si la extension no se puede cargar. Los vectores se guardan
normalizados, asi que la distancia L2 ordena igual que el coseno.
"""

from __future__ import annotations

import re

import numpy as np

from .. import db

_DIM_SQL_RE = re.compile(r"\[(\d+)\]")
_available: bool | None = None
_dim: int | None = None


class VectorError(RuntimeError):
    pass


def _vec_present() -> bool:
    global _available
    if _available is None:
        try:
            row = db.query_one(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='chunks_vec'"
            )
            _available = db.HAS_SQLITE_VEC
            if not row and db.HAS_SQLITE_VEC:
                _available = True
        except Exception:
            _available = False
    return bool(_available)


def ensure_table(dim: int) -> bool:
    """Crea la tabla vec0 con la dimension del modelo actual."""
    global _available, _dim
    if not db.HAS_SQLITE_VEC:
        _available = False
        return False

    try:
        row = db.query_one("SELECT sql FROM sqlite_master WHERE name = 'chunks_vec'")
        if row is not None:
            match = _DIM_SQL_RE.search(row["sql"] or "")
            existing = int(match.group(1)) if match else None
            if existing and existing != dim:
                count_row = db.query_one("SELECT count(*) AS total FROM chunks_vec")
                if count_row and int(count_row["total"]) > 0:
                    raise VectorError(
                        "El modelo de embeddings cambio de dimension. "
                        "Borra los documentos y vuelve a indexarlos."
                    )
                db.execute("DROP TABLE chunks_vec")
                row = None

        if row is None:
            db.execute(
                f"CREATE VIRTUAL TABLE chunks_vec USING vec0("
                f"chunk_id INTEGER PRIMARY KEY, embedding FLOAT[{int(dim)}])"
            )
        _available = True
        _dim = dim
        db.set_setting("embed_dim", str(dim))
        return True
    except VectorError:
        raise
    except Exception:
        _available = False
        return False


def upsert_many(chunk_ids: list[int], matrix: np.ndarray) -> None:
    if not chunk_ids:
        return
    if _vec_present():
        try:
            db.execute_many(
                "INSERT INTO chunks_vec(chunk_id, embedding) VALUES (?, ?)",
                [
                    (int(chunk_id), np.asarray(vector, dtype=np.float32).tobytes())
                    for chunk_id, vector in zip(chunk_ids, matrix, strict=False)
                ],
            )
            return
        except Exception:
            pass
    # Sin indice: el respaldo lee la columna chunks.embedding.


def delete_chunks(chunk_ids: list[int]) -> None:
    if not chunk_ids:
        return
    if _vec_present():
        try:
            db.execute_many(
                "DELETE FROM chunks_vec WHERE chunk_id = ?",
                [(int(chunk_id),) for chunk_id in chunk_ids],
            )
        except Exception:
            pass


def knn(query_vector: np.ndarray, limit: int) -> list[tuple[int, float]]:
    """Devuelve [(chunk_id, distancia)] del mas parecido al menos."""
    if not _vec_present():
        return []

    vector = np.asarray(query_vector, dtype=np.float32).tobytes()
    try:
        rows = db.query(
            """
            SELECT chunk_id, distance
            FROM chunks_vec
            WHERE embedding MATCH ? AND k = ?
            """,
            (vector, int(limit)),
        )
    except Exception:
        return []

    hits = [(int(row["chunk_id"]), float(row["distance"])) for row in rows]
    hits.sort(key=lambda item: item[1])
    return hits


def brute_force(
    query_vector: np.ndarray,
    limit: int,
    *,
    subject_id: str | None = None,
    document_ids: list[str] | None = None,
) -> list[tuple[int, float]]:
    """Respaldo sin sqlite-vec: cosine sobre los vectores guardados."""
    conditions = ["c.embedding IS NOT NULL"]
    params: list[object] = []
    if subject_id:
        conditions.append("d.subject_id = ?")
        params.append(subject_id)
    if document_ids:
        placeholders = ",".join("?" for _ in document_ids)
        conditions.append(f"c.document_id IN ({placeholders})")
        params.extend(document_ids)

    rows = db.query(
        f"""
        SELECT c.id AS id, c.embedding AS embedding
        FROM chunks c JOIN documents d ON d.id = c.document_id
        WHERE {' AND '.join(conditions)}
        """,
        tuple(params),
    )
    if not rows:
        return []

    query = np.asarray(query_vector, dtype=np.float32)
    scored: list[tuple[int, float]] = []
    for row in rows:
        blob = row["embedding"]
        if not blob:
            continue
        vector = np.frombuffer(blob, dtype=np.float32)
        if vector.size != query.size:
            continue
        similarity = float(np.dot(query, vector))
        scored.append((int(row["id"]), 1.0 - similarity))
    scored.sort(key=lambda item: item[1])
    return scored[:limit]
