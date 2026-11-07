"""Redaccion de secretos en logs y mensajes de error."""

from __future__ import annotations

import re
import threading

_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z\-_]{30,}"),                  # Google
    re.compile(r"sk-ant-[A-Za-z0-9\-_]{20,}"),               # Anthropic
    re.compile(r"sk-[A-Za-z0-9\-_]{20,}"),                   # OpenAI / DeepSeek
    re.compile(r"ghp_[A-Za-z0-9]{30,}"),                     # GitHub
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}"),            # Slack
    re.compile(r"AKIA[0-9A-Z]{16}"),                         # AWS
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9\-_.]{16,}"),
]

_extra_secrets: set[str] = set()
_lock = threading.Lock()
_MIN_SECRET_LEN = 8


def register_secret(secret: str | None) -> None:
    """Registra una clave concreta para que nunca aparezca en logs."""
    if not secret:
        return
    secret = secret.strip()
    if len(secret) < _MIN_SECRET_LEN:
        return
    with _lock:
        _extra_secrets.add(secret)


def forget_secret(secret: str | None) -> None:
    if not secret:
        return
    with _lock:
        _extra_secrets.discard(secret.strip())


def redact(text: str | None) -> str:
    if not text:
        return ""
    cleaned = str(text)
    for pattern in _PATTERNS:
        cleaned = pattern.sub("***", cleaned)
    with _lock:
        secrets = sorted(_extra_secrets, key=len, reverse=True)
    for secret in secrets:
        if secret and secret in cleaned:
            cleaned = cleaned.replace(secret, "***")
    return cleaned


def key_hint(secret: str | None) -> str | None:
    """Pista no sensible de una clave: solo los ultimos 4 caracteres."""
    if not secret or len(secret) < 8:
        return None
    return "…" + secret[-4:]
