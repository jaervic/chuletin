"""Utilidades compartidas por los routers."""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException

from .. import db
from ..config import settings
from ..schemas import DocumentOut
from ..search import indexer
from ..security.uploads import UploadRejected, ensure_within


def subject_exists(subject_id: str) -> bool:
    return db.query_one("SELECT 1 FROM subjects WHERE id = ?", (subject_id,)) is not None


def require_subject(subject_id: str) -> None:
    if not subject_exists(subject_id):
        raise HTTPException(status_code=404, detail="La materia no existe")


def document_row(document_id: str):
    row = db.query_one("SELECT * FROM documents WHERE id = ?", (document_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="El documento no existe")
    return row


def document_out(row) -> DocumentOut:
    return DocumentOut(
        id=row["id"],
        subject_id=row["subject_id"],
        title=row["title"],
        original_name=row["original_name"],
        source_type=row["source_type"],
        source_uri=row["source_uri"],
        size_bytes=int(row["size_bytes"] or 0),
        page_count=row["page_count"],
        status=row["status"],
        progress=float(row["progress"] or 0.0),
        error=row["error"],
        chunk_count=int(row["chunk_count"] or 0),
        created_at=row["created_at"],
        indexed_at=row["indexed_at"],
    )


def remove_document(document_id: str) -> None:
    row = document_row(document_id)
    indexer.delete_document_chunks(document_id)

    file_path = row["file_path"]
    if file_path:
        try:
            path = ensure_within(Path(file_path), Path(settings.uploads_dir))
            path.unlink(missing_ok=True)
        except (OSError, UploadRejected):
            pass

    db.execute("DELETE FROM documents WHERE id = ?", (document_id,))
