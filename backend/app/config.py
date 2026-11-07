"""Configuracion global de Chuletin.

Todo se configura por variables de entorno con prefijo CHULETIN_ o por el
fichero .env de la raiz del repositorio. Los valores por defecto estan
pensados para un equipo modesto (4 GB de RAM, sin GPU).
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CHULETIN_",
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Servidor: por defecto solo escucha en localhost.
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "info"

    # Datos
    data_dir: Path = REPO_ROOT / "data"

    # Limites de ingesta
    max_upload_mb: int = 50
    max_pages: int = 2000
    max_chunks_per_doc: int = 5000
    max_chunk_chars: int = 3200
    chunk_overlap_chars: int = 480
    embed_batch_size: int = 32

    # Limites de extraccion (subproceso aislado)
    extraction_timeout_s: int = 180
    extraction_mem_mb: int = 1024

    # Limites de red (SSRF)
    fetch_timeout_s: int = 15
    fetch_max_bytes: int = 8 * 1024 * 1024
    fetch_max_redirects: int = 3

    # Generacion
    max_question_chars: int = 4000
    max_context_chunks: int = 8
    retrieval_candidates: int = 30
    llm_timeout_s: int = 120

    # OCR
    ocr_lang: str = "spa+eng"
    ocr_max_pages: int = 40

    # Precarga del modelo de embeddings al arrancar
    warmup: bool = True

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def tmp_dir(self) -> Path:
        return self.data_dir / "tmp"

    @property
    def models_dir(self) -> Path:
        return self.data_dir / "models"

    @property
    def database_path(self) -> Path:
        return self.data_dir / "chuletin.db"

    @property
    def frontend_dist(self) -> Path:
        return REPO_ROOT / "frontend" / "dist"

    def ensure_dirs(self) -> None:
        """Crea los directorios de datos con permisos restrictivos."""
        for directory in (self.data_dir, self.uploads_dir, self.tmp_dir, self.models_dir):
            directory.mkdir(parents=True, exist_ok=True)
            try:
                directory.chmod(0o700)
            except OSError:
                pass


settings = Settings()
