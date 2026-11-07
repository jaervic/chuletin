"""Estado del servicio."""

from __future__ import annotations

from fastapi import APIRouter

from .. import db
from ..config import settings

router = APIRouter(prefix="/api", tags=["health"])

VERSION = "0.1.0"


@router.get("/health")
def health() -> dict:
    try:
        documents = db.query_one("SELECT count(*) AS total FROM documents")
        chunks = db.query_one("SELECT count(*) AS total FROM chunks")
        ready = db.query_one(
            "SELECT count(*) AS total FROM documents WHERE status = 'ready'"
        )
        database_ok = True
    except Exception:
        documents = chunks = ready = None
        database_ok = False

    return {
        "status": "ok" if database_ok else "degraded",
        "version": VERSION,
        "database": {"ok": database_ok, "path": str(settings.database_path)},
        "documents": int(documents["total"]) if documents else 0,
        "documents_ready": int(ready["total"]) if ready else 0,
        "chunks": int(chunks["total"]) if chunks else 0,
        "vector_index": db.HAS_SQLITE_VEC,
    }
