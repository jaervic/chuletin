"""Gestion de materias."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import db
from ..schemas import SubjectCreate, SubjectOut
from ..utils import new_id, utcnow
from .deps import remove_document

router = APIRouter(prefix="/api/subjects", tags=["subjects"])


@router.get("", response_model=list[SubjectOut])
def list_subjects() -> list[SubjectOut]:
    rows = db.query(
        """
        SELECT s.id, s.name, s.color, s.created_at,
               (SELECT count(*) FROM documents d WHERE d.subject_id = s.id) AS document_count
        FROM subjects s
        ORDER BY s.name COLLATE NOCASE
        """
    )
    return [
        SubjectOut(
            id=row["id"],
            name=row["name"],
            color=row["color"],
            created_at=row["created_at"],
            document_count=int(row["document_count"] or 0),
        )
        for row in rows
    ]


@router.post("", response_model=SubjectOut, status_code=201)
def create_subject(payload: SubjectCreate) -> SubjectOut:
    exists = db.query_one(
        "SELECT id FROM subjects WHERE name = ? COLLATE NOCASE", (payload.name,)
    )
    if exists:
        raise HTTPException(status_code=409, detail="Ya existe una materia con ese nombre")

    subject_id = new_id()
    created = utcnow()
    db.execute(
        "INSERT INTO subjects(id, name, color, created_at) VALUES(?,?,?,?)",
        (subject_id, payload.name, payload.color, created),
    )
    return SubjectOut(
        id=subject_id,
        name=payload.name,
        color=payload.color,
        created_at=created,
        document_count=0,
    )


@router.patch("/{subject_id}", response_model=SubjectOut)
def update_subject(subject_id: str, payload: SubjectCreate) -> SubjectOut:
    row = db.query_one("SELECT * FROM subjects WHERE id = ?", (subject_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="La materia no existe")
    clash = db.query_one(
        "SELECT id FROM subjects WHERE name = ? COLLATE NOCASE AND id <> ?",
        (payload.name, subject_id),
    )
    if clash:
        raise HTTPException(status_code=409, detail="Ya existe una materia con ese nombre")

    db.execute(
        "UPDATE subjects SET name = ?, color = ? WHERE id = ?",
        (payload.name, payload.color, subject_id),
    )
    return SubjectOut(
        id=subject_id,
        name=payload.name,
        color=payload.color,
        created_at=row["created_at"],
        document_count=0,
    )


@router.delete("/{subject_id}", status_code=204)
def delete_subject(subject_id: str) -> None:
    row = db.query_one("SELECT id FROM subjects WHERE id = ?", (subject_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="La materia no existe")

    documents = db.query("SELECT id FROM documents WHERE subject_id = ?", (subject_id,))
    for document in documents:
        remove_document(document["id"])

    db.execute("DELETE FROM subjects WHERE id = ?", (subject_id,))
