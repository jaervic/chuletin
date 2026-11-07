"""Proteccion contra SSRF.

Cualquier URL que venga del usuario (paginas web, YouTube) pasa por aqui
antes de abrirse. Se resuelve el DNS y se rechaza todo lo que no sea una
IP publica, incluyendo loopback, redes privadas, link-local y el endpoint
de metadatos de las nubes (169.254.169.254).
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx

from ..config import settings

ALLOWED_SCHEMES = {"http", "https"}
BLOCKED_PORTS = {
    22, 23, 25, 110, 143, 389, 445, 465, 587, 636,
    1433, 1521, 2049, 2375, 2376, 3306, 3389, 5432,
    5900, 6379, 9200, 11211, 27017,
}
MAX_REDIRECTS = 3


class UnsafeURLError(ValueError):
    """La URL no es segura o no se puede verificar."""


@dataclass(slots=True)
class FetchResult:
    data: bytes
    content_type: str
    final_url: str
    status_code: int


def _is_public_ip(raw_ip: str) -> bool:
    try:
        ip = ipaddress.ip_address(raw_ip)
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    if ip.is_multicast or ip.is_unspecified or ip.is_loopback or ip.is_link_local:
        return False
    return bool(ip.is_global)


def validate_url(url: str) -> tuple[str, str, int]:
    """Comprueba forma de la URL. Devuelve (url_normalizada, host, puerto)."""
    if not url or len(url) > 2048:
        raise UnsafeURLError("URL vacia o demasiado larga")
    url = url.strip()
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise UnsafeURLError("Solo se permiten enlaces http o https")
    if parts.username or parts.password:
        raise UnsafeURLError("La URL no puede incluir credenciales")
    host = parts.hostname
    if not host:
        raise UnsafeURLError("La URL no tiene host")
    try:
        port = parts.port or (443 if scheme == "https" else 80)
    except ValueError as exc:
        raise UnsafeURLError("Puerto no valido") from exc
    if port in BLOCKED_PORTS:
        raise UnsafeURLError("Ese puerto esta bloqueado por seguridad")
    if host in {"localhost", "metadata.google.internal"} or host.endswith(".local"):
        raise UnsafeURLError("Ese host esta bloqueado por seguridad")
    return url, host, port


async def _resolve_and_check(host: str, port: int) -> list[str]:
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(
            host, port, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP
        )
    except socket.gaierror as exc:
        raise UnsafeURLError(f"No se pudo resolver el host: {host}") from exc
    addresses = sorted({info[4][0] for info in infos})
    if not addresses:
        raise UnsafeURLError("El host no resuelve a ninguna direccion")
    for address in addresses:
        if not _is_public_ip(address):
            raise UnsafeURLError(
                "La URL apunta a una direccion interna; bloqueada por seguridad"
            )
    return addresses


async def safe_fetch(
    url: str,
    *,
    timeout: float | None = None,
    max_bytes: int | None = None,
    max_redirects: int | None = None,
    accept: str = "*/*",
) -> FetchResult:
    """Descarga una URL externa con validacion SSRF en cada salto."""
    timeout = settings.fetch_timeout_s if timeout is None else timeout
    max_bytes = settings.fetch_max_bytes if max_bytes is None else max_bytes
    max_redirects = settings.fetch_max_redirects if max_redirects is None else max_redirects

    current = url
    headers = {
        "User-Agent": "Chuletin/0.1 (+https://github.com/getchuletin/chuletin)",
        "Accept": accept,
        "Accept-Language": "es,en;q=0.8",
    }

    async with httpx.AsyncClient(
        follow_redirects=False,
        timeout=httpx.Timeout(timeout),
        trust_env=False,  # ignora proxies del entorno: evita saltarse las comprobaciones
        headers=headers,
    ) as client:
        for _hop in range(max_redirects + 1):
            current, host, port = validate_url(current)
            await _resolve_and_check(host, port)

            async with client.stream("GET", current) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        raise UnsafeURLError("Redireccion sin destino")
                    current = urljoin(current, location)
                    continue

                if response.status_code >= 400:
                    raise UnsafeURLError(
                        f"El servidor respondio con codigo {response.status_code}"
                    )

                content_type = response.headers.get("content-type", "").split(";")[0].strip()
                if content_type and not (
                    content_type.startswith("text/")
                    or content_type in {"application/xhtml+xml", "application/xml", "application/json"}
                    or content_type.startswith("image/")
                ):
                    raise UnsafeURLError(f"Tipo de contenido no admitido: {content_type}")

                chunks: list[bytes] = []
                total = 0
                async for chunk in response.aiter_bytes():
                    total += len(chunk)
                    if total > max_bytes:
                        raise UnsafeURLError("La pagina supera el tamano maximo permitido")
                    chunks.append(chunk)

                return FetchResult(
                    data=b"".join(chunks),
                    content_type=content_type,
                    final_url=str(response.url),
                    status_code=response.status_code,
                )

    raise UnsafeURLError("Demasiadas redirecciones")
