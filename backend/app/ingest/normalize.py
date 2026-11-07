"""Normalizacion de texto extraido.

Los PDF y los DOCX rompen palabras con guiones al final de linea y meten
saltos de linea dentro de los parrafos. Esto lo corrige sin cargarse la
estructura de parrafos.
"""

from __future__ import annotations

import re

_HYPHEN_BREAK_RE = re.compile(r"(\w)-\n(\w)")
_SENTENCE_END_RE = re.compile(r"[.!?…:;]\s*$")
_BULLET_RE = re.compile(r"^\s*(?:[-*•·–—]|\d+[.)])\s+")


def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00ad", "")  # guion blando
    text = _HYPHEN_BREAK_RE.sub(r"\1\2", text)

    paragraphs = re.split(r"\n\s*\n", text)
    cleaned: list[str] = []
    for paragraph in paragraphs:
        lines = [line.rstrip() for line in paragraph.split("\n")]
        # Une lineas de un mismo parrafo, respetando vinetas y lineas cortas
        joined: list[str] = []
        buffer: list[str] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if _BULLET_RE.match(stripped):
                if buffer:
                    joined.append(" ".join(buffer))
                    buffer = []
                joined.append(stripped)
            else:
                buffer.append(stripped)
        if buffer:
            joined.append(" ".join(buffer))
        chunk = "\n".join(joined).strip()
        if chunk:
            cleaned.append(chunk)

    return "\n\n".join(cleaned).strip()


def looks_like_heading(text: str, max_len: int = 120) -> bool:
    text = text.strip()
    if not text or len(text) > max_len:
        return False
    if _SENTENCE_END_RE.search(text):
        return False
    words = text.split()
    if len(words) > 14:
        return False
    return bool(text)
