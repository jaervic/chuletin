"""Proceso aislado de extraccion.

Se ejecuta como `python -m app.ingest.worker`, con limites duros de memoria
y CPU. Nunca se parsea un documento no confiable dentro del servidor.
"""

from __future__ import annotations

import io
import json
import os
import resource
import sys
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import asdict
from pathlib import Path

MARKER = "@@CHULETIN_JSON@@"

_ALLOWED_OPTIONS = {
    "max_pages",
    "ocr",
    "ocr_lang",
    "ocr_max_pages",
    "text",
    "url",
}


def _apply_limits() -> None:
    mem_mb = int(os.environ.get("CHULETIN_WORKER_MEM_MB", "1024"))
    cpu_s = int(os.environ.get("CHULETIN_WORKER_CPU_S", "180"))
    try:
        resource.setrlimit(resource.RLIMIT_AS, (mem_mb * 1024 * 1024, mem_mb * 1024 * 1024))
    except (ValueError, OSError):
        pass
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_s, cpu_s + 5))
    except (ValueError, OSError):
        pass
    try:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    except (ValueError, OSError):
        pass


def _dispatch(kind: str, target: str | None, options: dict):
    clean = {key: value for key, value in options.items() if key in _ALLOWED_OPTIONS}

    if kind == "text":
        from .normalize import normalize_text
        from .types import Block, ExtractionResult

        text = normalize_text(str(clean.get("text") or ""))
        if not text:
            raise ValueError("El texto esta vacio")
        return ExtractionResult(blocks=[Block(text=text)], page_count=None)

    if kind == "pdf":
        from .pdf import extract_pdf

        return extract_pdf(Path(target or ""), **clean)

    if kind == "docx":
        from .docx import extract_docx

        return extract_docx(Path(target or ""))

    if kind == "pptx":
        from .pptx import extract_pptx

        return extract_pptx(Path(target or ""))

    if kind == "image":
        from .image import extract_image

        return extract_image(Path(target or ""), **clean)

    if kind == "web":
        from .web import extract_web

        return extract_web(str(clean.get("url") or target or ""))

    if kind == "youtube":
        from .youtube import extract_youtube

        return extract_youtube(str(clean.get("url") or target or ""))

    raise ValueError(f"Tipo de documento no soportado: {kind}")


def main() -> int:
    _apply_limits()
    raw = sys.stdin.read()
    noise = io.StringIO()
    try:
        payload = json.loads(raw)
        kind = str(payload.get("kind") or "")
        target = payload.get("path")
        options = payload.get("options") or {}
        with redirect_stdout(noise), redirect_stderr(noise):
            result = _dispatch(kind, target, options)
        output = {"ok": True, "result": asdict(result)}
    except Exception as exc:  # noqa: BLE001 - se reporta al proceso padre
        output = {
            "ok": False,
            "error": f"{exc.__class__.__name__}: {exc}",
            "kind": str((payload or {}).get("kind") if isinstance(payload, dict) else ""),
        }

    sys.stdout.write(MARKER + json.dumps(output, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
