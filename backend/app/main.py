"""Punto de entrada de Chuletin."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import db
from .api import chat, documents, health, settings_api, study, subjects
from .config import settings
from .llm import embeddings
from .security.uploads import UploadRejected

logger = logging.getLogger("chuletin")

CSP = (
    "default-src 'self'; "
    "img-src 'self' data: blob:; "
    "font-src 'self' data:; "
    "style-src 'self' 'unsafe-inline'; "
    "script-src 'self'; "
    "connect-src 'self'; "
    "worker-src 'self' blob:; "
    "frame-src 'self' blob:; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "form-action 'self'; "
    "frame-ancestors 'self'"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings.ensure_dirs()
    db.init_db(settings.database_path)
    logger.info("Chuletin listo en http://%s:%s", settings.host, settings.port)
    embeddings.warmup_async()
    try:
        yield
    finally:
        db.close_all()


app = FastAPI(
    title="Chuletin",
    description="Estudia con tus propios apuntes, con citas verificables.",
    version="0.2.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("origin")
        if origin:
            host = request.headers.get("host", "")
            if origin not in {f"http://{host}", f"https://{host}"}:
                return JSONResponse({"detail": "Origen no permitido"}, status_code=403)
        if request.headers.get("sec-fetch-site") == "cross-site":
            return JSONResponse({"detail": "Peticion entre sitios bloqueada"}, status_code=403)

    declared = request.headers.get("content-length")
    if declared and declared.isdigit():
        if int(declared) > (settings.max_upload_mb + 10) * 1024 * 1024:
            return JSONResponse({"detail": "La peticion es demasiado grande"}, status_code=413)

    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    if not request.url.path.startswith("/api/docs"):
        response.headers.setdefault("Content-Security-Policy", CSP)
    return response


@app.exception_handler(UploadRejected)
async def upload_rejected_handler(request: Request, exc: UploadRejected):
    return JSONResponse({"detail": str(exc)}, status_code=400)


app.include_router(health.router)
app.include_router(subjects.router)
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(settings_api.router)
app.include_router(study.router)


def _mount_frontend() -> None:
    dist = settings.frontend_dist
    index = dist / "index.html"
    if not index.exists():
        @app.get("/")
        def api_root() -> dict:
            return {
                "name": "Chuletin",
                "version": "0.2.0",
                "message": "El frontend no esta compilado. Ejecuta ./run.sh",
                "docs": "/api/docs",
            }
        return

    assets = dist / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse({"detail": "No encontrado"}, status_code=404)
        candidate = (dist / full_path).resolve()
        try:
            candidate.relative_to(dist.resolve())
        except ValueError:
            return JSONResponse({"detail": "No encontrado"}, status_code=404)
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)


_mount_frontend()
