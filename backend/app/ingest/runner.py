"""Lanzador del proceso aislado de extraccion."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from ..config import settings
from ..security.redact import redact
from .types import Block, ExtractionError, ExtractionResult

BACKEND_DIR = Path(__file__).resolve().parents[2]
MARKER = "@@CHULETIN_JSON@@"


def run_extraction(
    kind: str,
    target: str | None = None,
    options: dict | None = None,
    *,
    timeout: int | None = None,
) -> ExtractionResult:
    timeout = timeout or settings.extraction_timeout_s
    payload = json.dumps(
        {"kind": kind, "path": target, "options": options or {}}, ensure_ascii=False
    )

    env = os.environ.copy()
    current_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (
        f"{BACKEND_DIR}{os.pathsep}{current_pythonpath}" if current_pythonpath else str(BACKEND_DIR)
    )
    env["CHULETIN_WORKER_MEM_MB"] = str(settings.extraction_mem_mb)
    env["CHULETIN_WORKER_CPU_S"] = str(timeout)

    try:
        completed = subprocess.run(
            [sys.executable, "-m", "app.ingest.worker"],
            input=payload,
            text=True,
            capture_output=True,
            timeout=timeout,
            cwd=str(BACKEND_DIR),
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ExtractionError(
            f"La extraccion tardo mas de {timeout} segundos y se cancelo"
        ) from exc
    except OSError as exc:
        raise ExtractionError(f"No se pudo lanzar el extractor: {exc}") from exc

    stdout = completed.stdout or ""
    if MARKER not in stdout:
        detail = redact((completed.stderr or stdout).strip())[-300:]
        raise ExtractionError(f"El extractor fallo: {detail or 'sin salida'}")

    raw = stdout.split(MARKER, 1)[1].strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ExtractionError("El extractor devolvio una respuesta ilegible") from exc

    if not data.get("ok"):
        error = redact(str(data.get("error") or "error desconocido"))
        raise ExtractionError(error)

    result = data.get("result") or {}
    blocks = [Block(**block) for block in result.get("blocks") or []]
    return ExtractionResult(
        blocks=blocks,
        page_count=result.get("page_count"),
        title=result.get("title"),
        needs_ocr=bool(result.get("needs_ocr")),
        ocr_pages=list(result.get("ocr_pages") or []),
        warning=result.get("warning"),
    )
