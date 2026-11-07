"""Troceado de texto en fragmentos indexables.

Se respeta el limite de caracteres, se solapa un poco el final de cada
trozo con el principio del siguiente y se arrastra el titulo de seccion
para que las citas tengan contexto.
"""

from __future__ import annotations

import re

from ..config import settings
from .types import Block, Chunk

_PARAGRAPH_RE = re.compile(r"\n{2,}")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+")
_HARD_SPLIT_RE = re.compile(r"\s+")
MIN_CARRY = 120


def _split_long_paragraph(paragraph: str, max_chars: int) -> list[str]:
    if len(paragraph) <= max_chars:
        return [paragraph]
    pieces: list[str] = []
    current = ""
    for sentence in _SENTENCE_SPLIT_RE.split(paragraph):
        if not sentence:
            continue
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            pieces.append(current)
        if len(sentence) <= max_chars:
            current = sentence
            continue
        # Frase gigante: corte duro por palabras.
        words = _HARD_SPLIT_RE.split(sentence)
        buffer = ""
        for word in words:
            candidate = f"{buffer} {word}".strip() if buffer else word
            if len(candidate) <= max_chars:
                buffer = candidate
            else:
                if buffer:
                    pieces.append(buffer)
                buffer = word
        current = buffer
    if current:
        pieces.append(current)
    return [piece for piece in pieces if piece.strip()]


def _carry_tail(text: str, overlap: int) -> str:
    if overlap <= 0 or len(text) <= overlap:
        return ""
    tail = text[-overlap:]
    space = tail.find(" ")
    if space != -1:
        tail = tail[space + 1 :]
    return tail.strip()


def chunk_blocks(
    blocks: list[Block],
    *,
    max_chars: int | None = None,
    overlap_chars: int | None = None,
    max_chunks: int | None = None,
) -> list[Chunk]:
    max_chars = max_chars or settings.max_chunk_chars
    overlap_chars = settings.chunk_overlap_chars if overlap_chars is None else overlap_chars
    max_chunks = max_chunks or settings.max_chunks_per_doc

    chunks: list[Chunk] = []
    buffer: list[str] = []
    buffer_len = 0
    page_from: int | None = None
    page_to: int | None = None
    seconds: int | None = None
    heading: str | None = None
    carry_text = ""
    carry_page: int | None = None

    def flush() -> None:
        nonlocal buffer, buffer_len, page_from, page_to, seconds, carry_text, carry_page
        text = "\n\n".join(buffer).strip()
        buffer, buffer_len = [], 0
        if not text:
            return
        chunks.append(
            Chunk(
                text=text,
                page_from=page_from,
                page_to=page_to,
                heading=heading,
                n_chars=len(text),
                seconds=seconds,
            )
        )
        if len(text) > MIN_CARRY:
            carry_text = _carry_tail(text, overlap_chars)
            carry_page = page_to if page_to is not None else page_from
        else:
            carry_text, carry_page = "", None
        page_from = None
        page_to = None
        seconds = None

    for block in blocks:
        if block.is_heading:
            if block.text.strip():
                heading = block.text.strip()
            continue
        if block.heading:
            heading = block.heading

        for paragraph in _PARAGRAPH_RE.split(block.text):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            for piece in _split_long_paragraph(paragraph, max_chars):
                if buffer and buffer_len + len(piece) + 2 > max_chars:
                    flush()
                if not buffer and carry_text and len(carry_text) + len(piece) + 2 <= max_chars:
                    buffer.append(carry_text)
                    buffer_len = len(carry_text)
                    page_from = carry_page
                buffer.append(piece)
                buffer_len += len(piece) + 2
                if page_from is None:
                    page_from = block.page if block.page is not None else block.page
                if block.page is not None:
                    page_to = block.page
                if seconds is None and block.seconds is not None:
                    seconds = block.seconds
                if len(chunks) >= max_chunks:
                    break
            if len(chunks) >= max_chunks:
                break
        if len(chunks) >= max_chunks:
            break

    flush()
    return chunks[:max_chunks]
