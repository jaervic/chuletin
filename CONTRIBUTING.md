# Contribuir a Chuletín

Gracias por querer ayudar. Este proyecto es pequeno y prioriza claridad,
privacidad y seguridad por encima de funcionalidades.

## Antes de empezar

- Lee [SECURITY.md](SECURITY.md) y [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md).
- Para fallos de seguridad, **no abras un issue publico**.
- Para cambios grandes, abre antes una propuesta (issue) y espera respuesta.

## Entorno

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements-dev.txt
export PYTHONPATH=backend
.venv/bin/python -m pytest -q
.venv/bin/ruff check backend tests
```

## Reglas del proyecto

1. **Todo dato externo es no confiable**: documentos, HTML, transcripciones y
   salida del modelo.
2. **Nunca** interpolar SQL ni construir rutas con nombres de usuario.
3. Toda funcionalidad nueva de red pasa por `security/ssrf.py`.
4. Toda salida que se muestre pasa por `security/sanitize.py`.
5. Nada de telemetria ni llamadas externas no documentadas.
6. Los mensajes de error al usuario no incluyen claves ni rutas absolutas.
7. Cada correccion de seguridad necesita su prueba en `tests/test_security.py`.

## Estilo

- Python 3.10+, tipado moderno, comentarios en espanol.
- `ruff` sin avisos.
- Lineas de hasta 100 caracteres.
- Commits en imperativo y con prefijo: `feat:`, `fix:`, `docs:`, `test:`,
  `security:`, `refactor:`.

## Pull requests

- Una idea por PR.
- Incluye pruebas.
- Actualiza la documentacion si cambia el comportamiento.
- Si toca seguridad, actualiza el modelo de amenazas.
- La rama `main` esta protegida: se requiere revision y CI en verde.

## Licencia

Al contribuir aceptas que tu aportacion se publique bajo AGPL-3.0.
