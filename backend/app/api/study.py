"""Material de estudio: resumenes, esquemas, tarjetas y tests."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, Request

from .. import db
from ..schemas import CardReview, QuizAnswer, StudyCreate
from ..security.limits import client_key, write_limiter
from ..study.generate import KIND_LABELS, generate_set
from ..study.sm2 import review as schedule_review
from ..utils import new_id, utcnow
from .deps import require_subject

router = APIRouter(prefix="/api/study", tags=["study"])

VALID_KINDS = {"summary", "outline", "deck", "quiz"}


def _set_row(set_id: str):
    row = db.query_one("SELECT * FROM study_sets WHERE id = ?", (set_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="El material no existe")
    return row


def _set_dict(row) -> dict:
    keys = row.keys()
    return {
        "id": row["id"],
        "subject_id": row["subject_id"],
        "kind": row["kind"],
        "title": row["title"],
        "topic": row["topic"],
        "status": row["status"],
        "content": row["content"] if "content" in keys else None,
        "provider": row["provider"],
        "model": row["model"],
        "error": row["error"],
        "score": row["score"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "card_count": row["card_count"] if "card_count" in keys else None,
        "due_count": row["due_count"] if "due_count" in keys else None,
        "item_count": row["item_count"] if "item_count" in keys else None,
        "answered_count": row["answered_count"] if "answered_count" in keys else None,
    }


def _card_dict(row) -> dict:
    return {
        "id": row["id"],
        "set_id": row["set_id"],
        "front": row["front"],
        "back": row["back"],
        "source_index": row["source_index"],
        "ease": row["ease"],
        "interval_days": row["interval_days"],
        "repetitions": row["repetitions"],
        "lapses": row["lapses"],
        "due_at": row["due_at"],
        "created_at": row["created_at"],
        "last_reviewed_at": row["last_reviewed_at"],
    }


def _item_dict(row) -> dict:
    try:
        options = json.loads(row["options"] or "[]")
    except json.JSONDecodeError:
        options = []
    return {
        "id": row["id"],
        "set_id": row["set_id"],
        "position": row["position"],
        "question": row["question"],
        "options": options,
        "correct_index": row["correct_index"],
        "explanation": row["explanation"],
        "source_index": row["source_index"],
        "chosen_index": row["chosen_index"],
        "is_correct": row["is_correct"],
    }


def _citations(row) -> list[dict]:
    try:
        data = json.loads(row["citations"] or "[]")
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return []


@router.get("/sets")
def list_sets(subject_id: str, kind: str | None = None) -> list[dict]:
    if kind and kind not in VALID_KINDS:
        raise HTTPException(status_code=400, detail="Tipo no valido")

    now = utcnow()
    sql = """
        SELECT s.*,
            (SELECT count(*) FROM cards c WHERE c.set_id = s.id) AS card_count,
            (SELECT count(*) FROM cards c WHERE c.set_id = s.id AND c.due_at <= ?) AS due_count,
            (SELECT count(*) FROM quiz_items q WHERE q.set_id = s.id) AS item_count,
            (SELECT count(*) FROM quiz_items q WHERE q.set_id = s.id AND q.chosen_index IS NOT NULL) AS answered_count
        FROM study_sets s
        WHERE s.subject_id = ?
    """
    params: list[object] = [now, subject_id]
    if kind:
        sql += " AND s.kind = ?"
        params.append(kind)
    sql += " ORDER BY s.created_at DESC"

    rows = db.query(sql, tuple(params))
    return [_set_dict(row) for row in rows]


@router.post("/sets", status_code=201)
async def create_set(payload: StudyCreate, request: Request) -> dict:
    if not write_limiter.allow(client_key(request)):
        raise HTTPException(status_code=429, detail="Demasiadas peticiones, espera un momento")

    require_subject(payload.subject_id)
    if payload.kind not in VALID_KINDS:
        raise HTTPException(status_code=400, detail="Tipo no valido")

    document_ids: list[str] = []
    if payload.document_ids:
        placeholders = ",".join("?" for _ in payload.document_ids)
        rows = db.query(
            f"SELECT id FROM documents WHERE subject_id = ? AND id IN ({placeholders})",
            tuple([payload.subject_id, *payload.document_ids]),
        )
        valid = {row["id"] for row in rows}
        document_ids = [item for item in payload.document_ids if item in valid]

    topic = (payload.topic or "").strip() or None
    subject = db.query_one("SELECT name FROM subjects WHERE id = ?", (payload.subject_id,))
    title = topic or f"{KIND_LABELS[payload.kind]} · {subject['name'] if subject else 'materia'}"

    set_id = new_id()
    now = utcnow()
    db.execute(
        """
        INSERT INTO study_sets(
            id, subject_id, kind, title, topic, status, document_ids,
            created_at, updated_at
        ) VALUES(?,?,?,?,?,'generating',?,?,?)
        """,
        (
            set_id,
            payload.subject_id,
            payload.kind,
            title[:200],
            topic,
            json.dumps(document_ids),
            now,
            now,
        ),
    )

    asyncio.create_task(generate_set(set_id))
    return _set_dict(_set_row(set_id))


@router.get("/sets/{set_id}")
def get_set(set_id: str) -> dict:
    row = _set_row(set_id)
    detail = {"set": _set_dict(row), "citations": _citations(row)}

    if row["kind"] == "deck":
        cards = db.query(
            "SELECT * FROM cards WHERE set_id = ? ORDER BY created_at, rowid",
            (set_id,),
        )
        detail["cards"] = [_card_dict(card) for card in cards]
    elif row["kind"] == "quiz":
        items = db.query(
            "SELECT * FROM quiz_items WHERE set_id = ? ORDER BY position",
            (set_id,),
        )
        detail["items"] = [_item_dict(item) for item in items]

    return detail


@router.delete("/sets/{set_id}", status_code=204)
def delete_set(set_id: str) -> None:
    _set_row(set_id)
    db.execute("DELETE FROM study_sets WHERE id = ?", (set_id,))


@router.post("/cards/{card_id}/review")
def review_card(card_id: str, payload: CardReview) -> dict:
    row = db.query_one("SELECT * FROM cards WHERE id = ?", (card_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="La tarjeta no existe")

    schedule = schedule_review(
        ease=row["ease"],
        interval_days=row["interval_days"],
        repetitions=row["repetitions"],
        lapses=row["lapses"],
        rating=payload.rating,
    )
    now = utcnow()
    db.execute(
        """
        UPDATE cards
        SET ease = ?, interval_days = ?, repetitions = ?, lapses = ?,
            due_at = ?, last_reviewed_at = ?
        WHERE id = ?
        """,
        (
            schedule.ease,
            schedule.interval_days,
            schedule.repetitions,
            schedule.lapses,
            schedule.due_at,
            now,
            card_id,
        ),
    )
    db.execute(
        """
        INSERT INTO card_reviews(card_id, rating, interval_after, ease_after, reviewed_at)
        VALUES(?,?,?,?,?)
        """,
        (card_id, payload.rating, schedule.interval_days, schedule.ease, now),
    )
    updated = db.query_one("SELECT * FROM cards WHERE id = ?", (card_id,))
    return _card_dict(updated)


@router.get("/due")
def due_cards(subject_id: str) -> dict:
    row = db.query_one(
        """
        SELECT count(*) AS total
        FROM cards c JOIN study_sets s ON s.id = c.set_id
        WHERE s.subject_id = ? AND c.due_at <= ?
        """,
        (subject_id, utcnow()),
    )
    return {"subject_id": subject_id, "due": int(row["total"]) if row else 0}


@router.post("/sets/{set_id}/quiz/reset")
def reset_quiz(set_id: str) -> dict:
    _set_row(set_id)
    db.execute(
        "UPDATE quiz_items SET chosen_index = NULL, is_correct = NULL WHERE set_id = ?",
        (set_id,),
    )
    db.execute(
        "UPDATE study_sets SET score = NULL, updated_at = ? WHERE id = ?",
        (utcnow(), set_id),
    )
    return {"ok": True}


@router.post("/sets/{set_id}/quiz/{item_id}")
def answer_quiz(set_id: str, item_id: str, payload: QuizAnswer) -> dict:
    row = db.query_one(
        "SELECT * FROM quiz_items WHERE id = ? AND set_id = ?", (item_id, set_id)
    )
    if row is None:
        raise HTTPException(status_code=404, detail="La pregunta no existe")

    if row["chosen_index"] is None:
        is_correct = 1 if payload.chosen_index == row["correct_index"] else 0
        db.execute(
            "UPDATE quiz_items SET chosen_index = ?, is_correct = ? WHERE id = ?",
            (payload.chosen_index, is_correct, item_id),
        )
        stats = db.query_one(
            """
            SELECT count(*) AS total,
                   sum(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) AS correct,
                   sum(CASE WHEN chosen_index IS NOT NULL THEN 1 ELSE 0 END) AS answered
            FROM quiz_items WHERE set_id = ?
            """,
            (set_id,),
        )
        answered = int(stats["answered"] or 0)
        if answered:
            score = round(float(stats["correct"] or 0) / answered, 4)
            db.execute(
                "UPDATE study_sets SET score = ?, updated_at = ? WHERE id = ?",
                (score, utcnow(), set_id),
            )

    updated = db.query_one("SELECT * FROM quiz_items WHERE id = ?", (item_id,))
    return _item_dict(updated)
