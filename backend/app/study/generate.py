"""Generacion de resumenes, esquemas, tarjetas y tests."""

from __future__ import annotations

import asyncio
import json
import logging
import re

from .. import db
from ..config import settings
from ..llm.base import ChatMessage
from ..llm.registry import build_client
from ..prompts_loader import study_prompt, study_system
from ..security.limits import study_semaphore
from ..security.redact import redact
from ..security.sanitize import safe_plain, sanitize_markdown
from ..utils import human_pages, new_id, seconds_to_timestamp, utcnow
from .context import StudyChunk, collect_chunks

logger = logging.getLogger("chuletin.study")

KIND_LABELS = {
    "summary": "Resumen",
    "outline": "Esquema",
    "deck": "Tarjetas",
    "quiz": "Test",
}


class StudyError(RuntimeError):
    """No se pudo generar el material de estudio."""


def _locator(chunk: StudyChunk) -> str | None:
    if chunk.source_type == "youtube":
        return seconds_to_timestamp(chunk.page_from)
    return human_pages(chunk.page_from, chunk.page_to)


def build_context(chunks: list[StudyChunk]) -> tuple[str, list[dict]]:
    blocks: list[str] = []
    citations: list[dict] = []

    for index, chunk in enumerate(chunks, start=1):
        meta = [f'Documento: "{safe_plain(chunk.document_title, 160)}"']
        locator = _locator(chunk)
        if locator:
            meta.append(locator)
        if chunk.heading:
            meta.append(f"seccion: {safe_plain(chunk.heading, 100)}")

        blocks.append(
            "\n".join(
                [
                    f"[{index}] " + " · ".join(meta),
                    f'<documento numero="{index}" fiabilidad="no_confiable">',
                    chunk.text,
                    "</documento>",
                ]
            )
        )
        citations.append(
            {
                "index": index,
                "document_id": chunk.document_id,
                "document_title": safe_plain(chunk.document_title, 200),
                "source_type": chunk.source_type,
                "page_from": chunk.page_from,
                "page_to": chunk.page_to,
                "heading": safe_plain(chunk.heading, 160) if chunk.heading else None,
                "snippet": safe_plain(chunk.text, 600),
                "score": 0.0,
                "locator": locator,
            }
        )

    return "\n\n".join(blocks), citations


def _extract_json(text: str) -> dict:
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise StudyError("El modelo no devolvio JSON")
    try:
        data = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise StudyError("El JSON devuelto no es valido") from exc
    if not isinstance(data, dict):
        raise StudyError("El JSON devuelto no tiene el formato esperado")
    return data


def _clean(value: object, limit: int) -> str:
    if not isinstance(value, str):
        return ""
    return safe_plain(value, limit)


def _source_index(value: object, max_index: int) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and 1 <= value <= max_index:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        number = int(value.strip())
        if 1 <= number <= max_index:
            return number
    return None


def validate_cards(data: dict, max_index: int, expected: int) -> list[tuple[str, str, int | None]]:
    raw = data.get("cards")
    if not isinstance(raw, list):
        raise StudyError("La respuesta no contiene una lista de tarjetas")

    cards: list[tuple[str, str, int | None]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        front = _clean(item.get("front"), 400)
        back = _clean(item.get("back"), 1200)
        if not front or not back:
            continue
        key = front.lower()
        if key in seen:
            continue
        seen.add(key)
        cards.append((front, back, _source_index(item.get("cite"), max_index)))
        if len(cards) >= expected:
            break

    if len(cards) < 3:
        raise StudyError("El modelo no genero tarjetas validas")
    return cards


def validate_quiz(data: dict, max_index: int, expected: int) -> list[dict]:
    raw = data.get("items")
    if not isinstance(raw, list):
        raise StudyError("La respuesta no contiene una lista de preguntas")

    items: list[dict] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        question = _clean(item.get("question"), 600)
        options_raw = item.get("options")
        if not question or not isinstance(options_raw, list) or len(options_raw) != 4:
            continue
        options = [_clean(option, 300) for option in options_raw]
        if any(not option for option in options) or len(set(options)) != 4:
            continue
        correct = item.get("correct")
        if isinstance(correct, str) and correct.strip().isdigit():
            correct = int(correct.strip())
        if not isinstance(correct, int) or isinstance(correct, bool) or not 0 <= correct <= 3:
            continue
        key = question.lower()
        if key in seen:
            continue
        seen.add(key)
        items.append(
            {
                "question": question,
                "options": options,
                "correct": correct,
                "explanation": _clean(item.get("explanation"), 400),
                "source_index": _source_index(item.get("cite"), max_index),
            }
        )
        if len(items) >= expected:
            break

    if len(items) < 3:
        raise StudyError("El modelo no genero preguntas validas")
    return items


def _insert_cards(set_id: str, cards: list[tuple[str, str, int | None]]) -> None:
    now = utcnow()
    rows = [
        (
            new_id(),
            set_id,
            front,
            back,
            source_index,
            2.5,
            0,
            0,
            0,
            now,
            now,
            None,
        )
        for front, back, source_index in cards
    ]
    db.execute_many(
        """
        INSERT INTO cards(
            id, set_id, front, back, source_index, ease, interval_days,
            repetitions, lapses, due_at, created_at, last_reviewed_at
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        rows,
    )


def _insert_quiz_items(set_id: str, items: list[dict]) -> None:
    rows = [
        (
            new_id(),
            set_id,
            position,
            item["question"],
            json.dumps(item["options"], ensure_ascii=False),
            item["correct"],
            item["explanation"] or None,
            item["source_index"],
            None,
            None,
        )
        for position, item in enumerate(items)
    ]
    db.execute_many(
        """
        INSERT INTO quiz_items(
            id, set_id, position, question, options, correct_index,
            explanation, source_index, chosen_index, is_correct
        ) VALUES(?,?,?,?,?,?,?,?,?,?)
        """,
        rows,
    )


async def _render(
    client,
    set_row,
    chunks: list[StudyChunk],
) -> tuple[str, list[dict]]:
    kind = set_row["kind"]
    context, citations = build_context(chunks)
    count = (
        settings.study_cards_default
        if kind == "deck"
        else settings.study_quiz_default
        if kind == "quiz"
        else 0
    )
    prompt = study_prompt(kind, context, set_row["topic"], count)
    system = study_system(kind)

    response = await client.complete(
        system,
        [ChatMessage(role="user", content=prompt)],
        temperature=0.2,
        max_tokens=2600,
    )
    return response.text.strip(), citations


async def generate_set(set_id: str) -> None:
    """Genera el contenido de un set y actualiza su estado."""
    async with study_semaphore():
        row = db.query_one("SELECT * FROM study_sets WHERE id = ?", (set_id,))
        if row is None:
            return

        try:
            document_ids = json.loads(row["document_ids"] or "[]")
            chunks = await asyncio.to_thread(
                collect_chunks,
                row["subject_id"],
                document_ids or None,
                row["topic"],
                settings.study_max_chunks,
                settings.study_max_chars,
            )
            if not chunks:
                raise StudyError(
                    "No hay documentos indexados en esta materia. "
                    "Sube y espera a que terminen de indexarse."
                )

            client = build_client()
            text, citations = await _render(client, row, chunks)
            kind = row["kind"]

            if kind in {"summary", "outline"}:
                content = sanitize_markdown(text)
                if len(content) < 40:
                    raise StudyError("El modelo devolvio una respuesta vacia")
                db.execute(
                    """
                    UPDATE study_sets
                    SET status = 'ready', content = ?, citations = ?, provider = ?,
                        model = ?, error = NULL, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        content,
                        json.dumps(citations, ensure_ascii=False),
                        client.provider_id,
                        client.model,
                        utcnow(),
                        set_id,
                    ),
                )
            else:
                max_index = len(citations)
                if kind == "deck":
                    cards = validate_cards(
                        _extract_json(text), max_index, settings.study_cards_default
                    )
                    _insert_cards(set_id, cards)
                    summary = f"{len(cards)} tarjetas"
                else:
                    items = validate_quiz(
                        _extract_json(text), max_index, settings.study_quiz_default
                    )
                    _insert_quiz_items(set_id, items)
                    summary = f"{len(items)} preguntas"

                db.execute(
                    """
                    UPDATE study_sets
                    SET status = 'ready', citations = ?, provider = ?, model = ?,
                        content = ?, error = NULL, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        json.dumps(citations, ensure_ascii=False),
                        client.provider_id,
                        client.model,
                        summary,
                        utcnow(),
                        set_id,
                    ),
                )

            logger.info("Set de estudio generado: %s (%s)", set_id, kind)
        except Exception as exc:  # noqa: BLE001 - se muestra en la interfaz
            message = redact(str(exc)) or exc.__class__.__name__
            logger.exception("Fallo al generar %s: %s", set_id, message)
            db.execute(
                """
                UPDATE study_sets SET status = 'error', error = ?, updated_at = ?
                WHERE id = ?
                """,
                (message[:600], utcnow(), set_id),
            )
