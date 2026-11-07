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


def system_prompt() -> str:
    return load_prompt("system.md", FALLBACK_SYSTEM)


def chat_prompt(context: str, question: str) -> str:
    template = load_prompt(
        "chat.md",
        "CONTEXTO:\n{context}\n\nPREGUNTA:\n{question}",
    )
    return template.format(context=context, question=question)
