"""Validacion y almacenamiento de archivos subidos.

Reglas:
- El nombre del usuario NUNCA se usa como ruta: se guarda con un UUID.
- Se valida el contenido real (magic bytes), no solo la extension.
- Los .docx/.pptx se inspeccionan como ZIP antes de parsearlos (zip bomb).
"""

from __future__ import annotations

import hashlib
import os
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from ..config import settings
from ..utils import new_id

CHUNK_SIZE = 1024 * 1024
MAX_OFFICE_ENTRIES = 5000
MAX_OFFICE_UNCOMPRESSED = 500 * 1024 * 1024
MAX_OFFICE_RATIO = 100
MIN_RATIO_CHECK_SIZE = 2 * 1024 * 1024

EXTENSIONS: dict[str, str] = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".pptx": "pptx",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".tif": "image",
    ".tiff": "image",
    ".bmp": "image",
    ".txt": "text",
    ".md": "text",
}

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._()\- ]+")


class UploadRejected(ValueError):
    """El archivo no pasa las comprobaciones de seguridad."""


@dataclass(slots=True)
class StoredFile:
    path: Path
    sha256: str
    size: int
    kind: str
    original_name: str


def safe_original_name(name: str | None) -> str:
    name = (name or "documento").replace("\\", "/").split("/")[-1]
    name = _SAFE_NAME_RE.sub("_", name).strip(" ._")
    return (name or "documento")[:180]


def kind_from_name(name: str) -> str | None:
    return EXTENSIONS.get(Path(name).suffix.lower())


def _sniff(head: bytes, kind: str) -> bool:
    if kind == "pdf":
        return head.startswith(b"%PDF-")
    if kind in {"docx", "pptx"}:
        return head.startswith(b"PK\x03\x04")
    if kind == "image":
        return (
            head.startswith(b"\xff\xd8\xff")          # JPEG
            or head.startswith(b"\x89PNG\r\n\x1a\n")  # PNG
            or (head[:4] == b"RIFF" and head[8:12] == b"WEBP")
            or head.startswith(b"II*\x00")            # TIFF LE
            or head.startswith(b"MM\x00*")            # TIFF BE
            or head.startswith(b"BM")                 # BMP
        )
    if kind == "text":
        return b"\x00" not in head
    return False


def validate_office_zip(path: Path, kind: str) -> None:
    """Detecta zip bombs y rutas maliciosas dentro de .docx/.pptx."""
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_OFFICE_ENTRIES:
                raise UploadRejected("El documento tiene demasiadas partes internas")

            total = 0
            names: set[str] = set()
            for info in infos:
                member = info.filename
                parts = PurePosixPath(member).parts
                if member.startswith("/") or ".." in parts:
                    raise UploadRejected("Ruta interna no permitida en el documento")
                if info.flag_bits & 0x1:
                    raise UploadRejected("El documento esta cifrado y no se puede procesar")
                names.add(member)
                total += info.file_size
                if total > MAX_OFFICE_UNCOMPRESSED:
                    raise UploadRejected("El documento descomprimido es demasiado grande")
                if (
                    info.compress_size > 0
                    and info.file_size > MIN_RATIO_CHECK_SIZE
                    and info.file_size / info.compress_size > MAX_OFFICE_RATIO
                ):
                    raise UploadRejected("El documento parece un zip bomb")

            if "[Content_Types].xml" not in names:
                raise UploadRejected("El archivo no es un documento de Office valido")
            prefix = "word/" if kind == "docx" else "ppt/"
            if not any(name.startswith(prefix) for name in names):
                raise UploadRejected("El contenido no corresponde a la extension")
    except zipfile.BadZipFile as exc:
        raise UploadRejected("El archivo ZIP esta corrupto") from exc


def validate_file(path: Path, kind: str) -> None:
    with path.open("rb") as handle:
        head = handle.read(64)
    if not _sniff(head, kind):
        raise UploadRejected("El contenido del archivo no coincide con su extension")
    if kind in {"docx", "pptx"}:
        validate_office_zip(path, kind)


async def save_upload(upload, max_mb: int | None = None) -> StoredFile:
    """Guarda un UploadFile de forma segura y devuelve sus metadatos."""
    max_bytes = (max_mb or settings.max_upload_mb) * 1024 * 1024
    original = safe_original_name(getattr(upload, "filename", None))
    kind = kind_from_name(original)
    if kind is None:
        raise UploadRejected("Tipo de archivo no admitido")

    settings.tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir = Path(settings.tmp_dir)
    upload_dir = Path(settings.uploads_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    tmp_path = tmp_dir / f"{new_id()}.part"
    digest = hashlib.sha256()
    size = 0

    try:
        with tmp_path.open("wb") as handle:
            while True:
                chunk = await upload.read(CHUNK_SIZE)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise UploadRejected(
                        f"El archivo supera el limite de {max_mb or settings.max_upload_mb} MB"
                    )
                digest.update(chunk)
                handle.write(chunk)

        if size == 0:
            raise UploadRejected("El archivo esta vacio")

        validate_file(tmp_path, kind)

        destination = upload_dir / f"{new_id()}{Path(original).suffix.lower()}"
        os.replace(tmp_path, destination)
        try:
            destination.chmod(0o600)
        except OSError:
            pass

        return StoredFile(
            path=destination,
            sha256=digest.hexdigest(),
            size=size,
            kind=kind,
            original_name=original,
        )
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def ensure_within(path: Path, root: Path) -> Path:
    """Comprueba que una ruta resuelta sigue dentro de un directorio."""
    resolved = path.resolve()
    root_resolved = root.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise UploadRejected("Ruta fuera del almacenamiento permitido")
    return resolved
