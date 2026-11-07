# Politica de seguridad

## Versiones soportadas

| Version | Soporte |
|---|---|
| 0.1.x (rama `main`) | Si |

## Como reportar una vulnerabilidad

**No abras un issue publico.**

Usa el **aviso privado de vulnerabilidades** de GitHub
(`Security` → `Report a vulnerability`) en el repositorio. Si no esta
disponible, escribe a los maintainers indicados en el perfil del proyecto.

Incluye, si puedes:

1. Version y sistema operativo.
2. Pasos para reproducir el problema.
3. Impacto que crees que tiene.
4. Prueba de concepto (sin datos personales ni claves reales).

### Plazos

- Acuse de recibo: **72 horas**.
- Primera evaluacion: **7 dias**.
- Divulgacion coordinada: **90 dias** desde el reporte, o antes si hay parche.

No se tomaran represalias contra quien reporte de buena fe.

## Alcance

En alcance:

- Evasion de las protecciones SSRF (`backend/app/security/ssrf.py`).
- Escritura o lectura fuera de `data/uploads` (path traversal).
- Ejecucion de codigo mediante documentos maliciosos.
- XSS a traves de la salida del modelo o de nombres de archivo.
- Fuga de claves de API en logs, errores o respuestas HTTP.
- Inyeccion SQL.
- Escalada por inyeccion de prompts que consiga saltarse el ambito de documentos.

Fuera de alcance:

- Ataques que requieran control fisico del equipo.
- Configuraciones que expongan el servidor en red sin autenticacion
  (Chuletin escucha solo en `127.0.0.1` por diseno).
- Vulnerabilidades de proveedores externos de IA.

## Que hace Chuletin para protegerse

- Escucha solo en `127.0.0.1` y aplica CSP, `nosniff` y politica de origen.
- Valida el contenido real de cada archivo (magic bytes) y los ZIP de Office.
- Extrae documentos en un subproceso con `RLIMIT_AS` y `RLIMIT_CPU`.
- Bloquea redirecciones y direcciones internas al leer URLs.
- Escapa y sanea toda salida antes de mostrarla.
- No registra claves ni contenido de documentos por defecto.
- Ejecuta analisis de seguridad en cada PR (CodeQL, Semgrep, pip-audit, gitleaks).

Detalles y riesgos residuales: [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md).
