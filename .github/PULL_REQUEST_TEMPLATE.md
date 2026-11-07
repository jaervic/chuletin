## Que cambia

<!-- Una o dos frases. -->

## Por que

<!-- Contexto del problema. -->

## Como se ha probado

- [ ] `pytest -q`
- [ ] `ruff check backend tests`
- [ ] Prueba manual: <!-- describe -->

## Seguridad

- [ ] No introduce nuevas entradas no confiables
- [ ] Si toca red, pasa por `security/ssrf.py`
- [ ] Si toca salida, pasa por `security/sanitize.py`
- [ ] Actualiza `docs/THREAT_MODEL.md` si aplica
- [ ] No incluye claves ni datos personales

## Capturas (si hay cambios de interfaz)
