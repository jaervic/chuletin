"""Carga de plantillas de prompt."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parent / "prompts"

FALLBACK_SYSTEM = (
    "Eres Chuletin. Responde solo con el contexto proporcionado y cita con [n]. "
    "Si la respuesta no esta en el contexto, dilo explicitamente."
)


@lru_cache(maxsize=8)
def load_prompt(name: str, default: str = "") -> str:
    path = PROMPT_DIR / name
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return default


STUDY_FILES = {
    "summary": "study_summary.md",
    "outline": "study_outline.md",
    "deck": "study_cards.md",
    "quiz": "study_quiz.md",
}

STUDY_EXTRA = {
    "summary": "",
    "outline": "",
    "deck": " Devuelve unicamente el JSON pedido, sin markdown alrededor.",
    "quiz": " Devuelve unicamente el JSON pedido, sin markdown alrededor.",
}


def study_system(kind: str) -> str:
    return system_prompt() + STUDY_EXTRA.get(kind, "")


def study_prompt(kind: str, context: str, topic: str | None, count: int) -> str:
    filename = STUDY_FILES.get(kind)
    if filename is None:
        raise ValueError(f"Tipo de estudio no soportado: {kind}")
    template = load_prompt(
        filename,
        "CONTEXTO:\n[[CONTEXT]]\n\nTEMA: [[TOPIC]]\n",
    )
    return (
        template.replace("[[CONTEXT]]", context)
        .replace("[[TOPIC]]", (topic or "").strip() or "todo el material")
        .replace("[[COUNT]]", str(count))
    )


def system_prompt() -> str:
    return load_prompt("system.md", FALLBACK_SYSTEM)


def chat_prompt(context: str, question: str) -> str:
    template = load_prompt(
        "chat.md",
        "CONTEXTO:\n{context}\n\nPREGUNTA:\n{question}",
    )
    return template.format(context=context, question=question)
