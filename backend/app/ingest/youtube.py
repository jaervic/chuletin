"""Extraccion de transcripciones de YouTube."""

from __future__ import annotations

import asyncio
import json
import re
from urllib.parse import parse_qs, urlsplit

from ..security.ssrf import UnsafeURLError, safe_fetch
from .normalize import normalize_text
from .types import Block, ExtractionError, ExtractionResult

_ALLOWED_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
}
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_LANGUAGES = ["es", "es-ES", "es-419", "es-MX", "en", "en-US"]
GROUP_SECONDS = 25


def parse_video_id(url: str) -> str:
    parts = urlsplit((url or "").strip())
    if parts.scheme not in {"http", "https"}:
        raise ExtractionError("El enlace debe empezar por http o https")
    host = (parts.hostname or "").lower()
    if host not in _ALLOWED_HOSTS:
        raise ExtractionError("El enlace no es de YouTube")

    candidate = ""
    if host.endswith("youtu.be"):
        candidate = parts.path.strip("/").split("/")[0]
    elif parts.path.startswith("/watch"):
        candidate = (parse_qs(parts.query).get("v") or [""])[0]
    elif parts.path.startswith(("/shorts/", "/embed/", "/live/")):
        candidate = parts.path.strip("/").split("/")[1]

    if not _VIDEO_ID_RE.match(candidate or ""):
        raise ExtractionError("No se pudo identificar el video de YouTube")
    return candidate


def _fetch_transcript(video_id: str) -> list[dict]:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError as exc:  # pragma: no cover
        raise ExtractionError(
            "Falta youtube-transcript-api: pip install -r backend/requirements.txt"
        ) from exc

    try:  # API 1.x
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id, languages=_LANGUAGES)
        snippets = [
            {
                "text": snippet.text,
                "start": float(snippet.start),
                "duration": float(getattr(snippet, "duration", 0) or 0),
            }
            for snippet in fetched.snippets
        ]
        if snippets:
            return snippets
    except Exception:
        pass

    try:  # API 0.x
        return list(YouTubeTranscriptApi.get_transcript(video_id, languages=_LANGUAGES))
    except Exception as exc:
        raise ExtractionError(
            "Este video no tiene subtitulos disponibles. Prueba con otro video "
            "o sube el PDF/tema correspondiente."
        ) from exc


def _fetch_title(video_id: str) -> str | None:
    url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
    try:
        fetched = asyncio.run(safe_fetch(url, accept="application/json"))
        data = json.loads(fetched.data.decode("utf-8", "replace"))
        return (data.get("title") or "").strip() or None
    except (UnsafeURLError, Exception):
        return None


def extract_youtube(url: str, **_: object) -> ExtractionResult:
    video_id = parse_video_id(url)
    snippets = _fetch_transcript(video_id)
    title = _fetch_title(video_id) or f"YouTube {video_id}"

    blocks: list[Block] = []
    buffer: list[str] = []
    start: float | None = None
    last_end = 0.0

    for snippet in snippets:
        text = normalize_text(str(snippet.get("text", "")).replace("\n", " "))
        if not text:
            continue
        if start is None:
            start = float(snippet.get("start") or 0)
        buffer.append(text)
        last_end = float(snippet.get("start") or 0) + float(snippet.get("duration") or 0)
        if last_end - start >= GROUP_SECONDS:
            seconds = int(start)
            blocks.append(
                Block(
                    text=" ".join(buffer),
                    page=seconds,
                    seconds=seconds,
                    heading=f"Minuto {seconds // 60:02d}:{seconds % 60:02d}",
                )
            )
            buffer = []
            start = None

    if buffer and start is not None:
        seconds = int(start)
        blocks.append(
            Block(
                text=" ".join(buffer),
                page=seconds,
                seconds=seconds,
                heading=f"Minuto {seconds // 60:02d}:{seconds % 60:02d}",
            )
        )

    if not blocks:
        raise ExtractionError("La transcripcion del video esta vacia")

    return ExtractionResult(blocks=blocks, page_count=None, title=title)
