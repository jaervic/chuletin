"""Biblioteca de documentos: subida, lista, descarga y borrado."""

from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse

from .. import db
from ..config import settings
from ..ingest.pipeline import start_ingestion
from ..ingest.youtube import parse_video_id
from ..schemas import DocumentOut, DocumentUpdate, TextIngest, UrlIngest
from ..security.limits import client_key, write_limiter
from ..security.ssrf import UnsafeURLError, validate_url
from ..security.uploads import UploadRejected, ensure_within, save_upload
from ..utils import new_id, slugify, utcnow
from .deps import document_out, document_row, remove_document, require_subject

router = APIRouter(prefix="/api/documents", tags=["documents"])

INLINE_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


def _limit(request: Request) -> None:
    if not write_limiter.allow(client_key(request)):
        raise HTTPException(status_code=429, detail="Demasiadas peticiones, espera un momento")


def _insert_document(
    *,
    subject_id: str,
    title: str,
    source_type: str,
    sha256: str,
    original_name: str | None = None,
    source_uri: str | None = None,
    file_path: str | None = None,
    size_bytes: int = 0,
) -> str:
    document_id = new_id()
    try:
        db.execute(
            """
            INSERT INTO documents(
                id, subject_id, title, original_name, source_type, source_uri,
                file_path, sha256, size_bytes, status, progress, created_at
            ) VALUES(?,?,?,?,?,?,?,?,?,'pending',0,?)
            """,
            (
                document_id,
                subject_id,
                title[:200],
                original_name,
                source_type,
                source_uri,
                file_path,
                sha256,
                size_bytes,
                utcnow(),
            ),
        )
    except Exception as exc:
        if "UNIQUE" in str(exc).upper():
            raise HTTPException(status_code=409, detail="Ese documento ya esta en la biblioteca") from exc
        raise
    return document_id


@router.post("", response_model=DocumentOut, status_code=201)
async def upload_document(
    request: Request,
    response: Response,
    subject_id: str = Form(...),
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
) -> DocumentOut:
    _limit(request)
    require_subject(subject_id)

    try:
        stored = await save_upload(file)
    except UploadRejected as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    existing = db.query_one("SELECT * FROM documents WHERE sha256 = ?", (stored.sha256,))
    if existing is not None:
        try:
            stored.path.unlink(missing_ok=True)
        except OSError:
            pass
        response.status_code = 200
        return document_out(existing)

    chosen_title = (title or "").strip() or Path(stored.original_name).stem or "Documento"
    document_id = _insert_document(
        subject_id=subject_id,
        title=chosen_title,
        source_type=stored.kind,
        sha256=stored.sha256,
        original_name=stored.original_name,
        file_path=str(stored.path),
        size_bytes=stored.size,
    )
    start_ingestion(document_id)
    return document_out(document_row(document_id))


@router.post("/url", response_model=DocumentOut, status_code=201)
def ingest_url(payload: UrlIngest, request: Request, response: Response) -> DocumentOut:
    _limit(request)
    require_subject(payload.subject_id)
    url = payload.url.strip()

    try:
        if payload.kind == "youtube":
            parse_video_id(url)
        else:
            url, _, _ = validate_url(url)
    except (UnsafeURLError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    digest = hashlib.sha256(f"{payload.kind}:{url}".encode("utf-8")).hexdigest()
    existing = db.query_one("SELECT * FROM documents WHERE sha256 = ?", (digest,))
    if existing is not None:
        response.status_code = 200
        return document_out(existing)

    title = "Enlace" if payload.kind == "web" else "Video de YouTube"
    document_id = _insert_document(
        subject_id=payload.subject_id,
        title=title,
        source_type=payload.kind,
        source_uri=url,
        sha256=digest,
    )
    start_ingestion(document_id)
    return document_out(document_row(document_id))


@router.post("/text", response_model=DocumentOut, status_code=201)
def ingest_text(payload: TextIngest, request: Request, response: Response) -> DocumentOut:
    _limit(request)
    require_subject(payload.subject_id)

    content = payload.text.strip()
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    existing = db.query_one("SELECT * FROM documents WHERE sha256 = ?", (digest,))
    if existing is not None:
        response.status_code = 200
        return document_out(existing)

    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    path = Path(settings.uploads_dir) / f"{new_id()}.txt"
    path.write_text(content, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass

    document_id = _insert_document(
        subject_id=payload.subject_id,
        title=payload.title,
        source_type="text",
        sha256=digest,
        original_name=slugify(payload.title) + ".txt",
        file_path=str(path),
        size_bytes=len(content.encode("utf-8")),
    )
    start_ingestion(document_id)
    return document_out(document_row(document_id))


@router.get("", response_model=list[DocumentOut])
def list_documents(subject_id: str | None = None) -> list[DocumentOut]:
    if subject_id:
        rows = db.query(
            "SELECT * FROM documents WHERE subject_id = ? ORDER BY created_at DESC",
            (subject_id,),
        )
    else:
        rows = db.query("SELECT * FROM documents ORDER BY created_at DESC")
    return [document_out(row) for row in rows]


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: str) -> DocumentOut:
    return document_out(document_row(document_id))


@router.get("/{document_id}/file")
def get_document_file(document_id: str):
    row = document_row(document_id)
    file_path = row["file_path"]
    if not file_path:
        raise HTTPException(status_code=404, detail="Este documento no tiene archivo local")

    try:
        path = ensure_within(Path(file_path), Path(settings.uploads_dir))
    except UploadRejected as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not path.exists():
        raise HTTPException(status_code=404, detail="El archivo ya no existe")

    suffix = path.suffix.lower()
    media_type = INLINE_TYPES.get(suffix) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    disposition = "inline" if suffix in INLINE_TYPES else "attachment"
    filename = (row["original_name"] or path.name).replace('"', "")

    return FileResponse(
        path,
        media_type=media_type,
        headers={
            "Content-Disposition": f'{disposition}; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=0, no-store",
            "Content-Security-Policy": "sandbox",
        },
    )


@router.patch("/{document_id}", response_model=DocumentOut)
def update_document(document_id: str, payload: DocumentUpdate) -> DocumentOut:
    row = document_row(document_id)
    title = (payload.title or row["title"]).strip()
    subject_id = payload.subject_id or row["subject_id"]
    if payload.subject_id:
        require_subject(payload.subject_id)

    db.execute(
        "UPDATE documents SET title = ?, subject_id = ? WHERE id = ?",
        (title[:200], subject_id, document_id),
    )
    return document_out(document_row(document_id))


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: str) -> None:
    remove_document(document_id)


@router.post("/{document_id}/reindex", response_model=DocumentOut)
def reindex_document(document_id: str, request: Request) -> DocumentOut:
    _limit(request)
    row = document_row(document_id)
    if row["status"] in {"reading", "indexing"}:
        raise HTTPException(status_code=409, detail="El documento ya se esta indexando")

    db.execute(
        "UPDATE documents SET status = 'pending', progress = 0, error = NULL, chunk_count = 0 WHERE id = ?",
        (document_id,),
    )
    start_ingestion(document_id)
    return document_out(document_row(document_id))
