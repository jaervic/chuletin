"""Pruebas de generacion y API del material de estudio."""

from __future__ import annotations

import json

import pytest
from app import db
from app.main import app
from app.study.generate import (
    StudyError,
    _extract_json,
    validate_cards,
    validate_quiz,
)
from app.utils import new_id, utcnow
from fastapi.testclient import TestClient


def test_extrae_json_con_bloques_de_codigo():
    text = '```json\n{"cards": []}\n```'
    assert _extract_json(text) == {"cards": []}


def test_json_invalido():
    with pytest.raises(StudyError):
        _extract_json("no hay json aqui")


def test_valida_tarjetas_y_elimina_duplicados():
    data = {
        "cards": [
            {"front": "¿Qué es la mitosis?", "back": "División celular", "cite": 1},
            {"front": "¿QUÉ ES LA MITOSIS?", "back": "Repetida", "cite": 1},
            {"front": "¿Qué fases tiene?", "back": "Profase, metafase…", "cite": 2},
            {"front": "¿Qué es la célula?", "back": "Unidad básica", "cite": 99},
        ]
    }
    cards = validate_cards(data, max_index=2, expected=10)
    assert len(cards) == 3
    assert cards[0] == ("¿Qué es la mitosis?", "División celular", 1)
    assert cards[2][2] is None  # cita fuera de rango


def test_tarjetas_insuficientes():
    with pytest.raises(StudyError):
        validate_cards({"cards": [{"front": "a", "back": "b"}]}, 1, 10)


def test_valida_preguntas():
    data = {
        "items": [
            {
                "question": "¿Cuál es la unidad básica?",
                "options": ["Célula", "Átomo", "Órgano", "Tejido"],
                "correct": 0,
                "explanation": "La célula es la unidad básica de la vida.",
                "cite": 1,
            },
            {
                "question": "Pregunta mala",
                "options": ["Solo dos", "Opciones"],
                "correct": 0,
            },
            {
                "question": "¿Qué produce la mitosis?",
                "options": ["Dos células", "Una", "Cero", "Cuatro"],
                "correct": 0,
            },
            {
                "question": "¿Qué es la fotosíntesis?",
                "options": ["Luz a energía", "División", "Respiración", "Digestión"],
                "correct": 0,
            },
        ]
    }
    items = validate_quiz(data, max_index=1, expected=10)
    assert len(items) == 3
    assert items[0]["options"][0] == "Célula"


def _seed_subject() -> tuple[str, str]:
    subject_id = new_id()
    document_id = new_id()
    db.execute(
        "INSERT INTO subjects(id, name, color, created_at) VALUES(?,?,?,?)",
        (subject_id, "Biología", "#6366f1", utcnow()),
    )
    db.execute(
        """
        INSERT INTO documents(
            id, subject_id, title, source_type, sha256, status, progress, created_at
        ) VALUES(?,?,?,?,?,'ready',1,?)
        """,
        (document_id, subject_id, "Apuntes", "pdf", new_id(), utcnow()),
    )
    return subject_id, document_id


def test_flujo_de_tarjetas(temp_db):
    with TestClient(app) as client:
        subject_id, _ = _seed_subject()
        set_id = new_id()
        card_id = new_id()
        now = utcnow()
        db.execute(
            """
            INSERT INTO study_sets(id, subject_id, kind, title, status, created_at, updated_at)
            VALUES(?,?,'deck','Mitosis','ready',?,?)
            """,
            (set_id, subject_id, now, now),
        )
        db.execute(
            """
            INSERT INTO cards(id, set_id, front, back, due_at, created_at)
            VALUES(?,?,?,?,?,?)
            """,
            (card_id, set_id, "¿Qué es la mitosis?", "División celular", now, now),
        )

        listing = client.get(f"/api/study/sets?subject_id={subject_id}&kind=deck")
        assert listing.status_code == 200
        assert listing.json()[0]["card_count"] == 1
        assert listing.json()[0]["due_count"] == 1

        detail = client.get(f"/api/study/sets/{set_id}")
        assert detail.status_code == 200
        assert detail.json()["cards"][0]["front"] == "¿Qué es la mitosis?"

        reviewed = client.post(f"/api/study/cards/{card_id}/review", json={"rating": 3})
        assert reviewed.status_code == 200
        assert reviewed.json()["interval_days"] == 1
        assert reviewed.json()["repetitions"] == 1

        due = client.get(f"/api/study/due?subject_id={subject_id}")
        assert due.json()["due"] == 0

        assert client.delete(f"/api/study/sets/{set_id}").status_code == 204


def test_flujo_de_test(temp_db):
    with TestClient(app) as client:
        subject_id, _ = _seed_subject()
        set_id = new_id()
        item_id = new_id()
        now = utcnow()
        db.execute(
            """
            INSERT INTO study_sets(id, subject_id, kind, title, status, created_at, updated_at)
            VALUES(?,?,'quiz','Tema 1','ready',?,?)
            """,
            (set_id, subject_id, now, now),
        )
        db.execute(
            """
            INSERT INTO quiz_items(
                id, set_id, position, question, options, correct_index, explanation
            ) VALUES(?,?,0,?,?,0,?)
            """,
            (
                item_id,
                set_id,
                "¿Unidad básica de la vida?",
                json.dumps(["Célula", "Átomo", "Órgano", "Tejido"]),
                "La célula.",
            ),
        )

        answer = client.post(
            f"/api/study/sets/{set_id}/quiz/{item_id}", json={"chosen_index": 0}
        )
        assert answer.status_code == 200
        assert answer.json()["is_correct"] == 1
        assert answer.json()["chosen_index"] == 0

        detail = client.get(f"/api/study/sets/{set_id}")
        assert detail.json()["set"]["score"] == 1.0

        assert (
            client.post(f"/api/study/sets/{set_id}/quiz/reset").status_code == 200
        )
        detail = client.get(f"/api/study/sets/{set_id}")
        assert detail.json()["set"]["score"] is None
        assert detail.json()["items"][0]["chosen_index"] is None


def test_material_inexistente(temp_db):
    with TestClient(app) as client:
        assert client.get("/api/study/sets/nope").status_code == 404
        assert client.delete("/api/study/sets/nope").status_code == 404
