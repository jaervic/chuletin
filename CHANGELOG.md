# Historial de cambios

## 0.2.0 — Material de estudio

### Añadido

- **Resúmenes y esquemas** generados desde los documentos de una materia, con
  citas clicables a la página exacta.
- **Tarjetas de repaso** con algoritmo SM-2: cada tarjeta guarda facilidad,
  intervalo, repeticiones y fecha del próximo repaso.
- **Sesiones de repaso** con calificación en cuatro niveles (otra vez, difícil,
  bien, fácil) y atajos de teclado.
- **Tests de opción múltiple** con corrección inmediata, explicación, fuente y
  puntuación final.
- Nueva sección **Estudiar** en la interfaz, con pestañas por tipo de material.
- Endpoints `/api/study/*` y tablas `study_sets`, `cards`, `card_reviews` y
  `quiz_items`.
- Prueba de extremo a extremo ampliada: resumen, tarjetas y test con proveedor
  simulado.

### Cambiado

- El visor de PDF se carga de forma diferida: el paquete inicial baja de
  ~1 MB a ~680 kB.
- La base de datos migra a la versión de esquema 2 al arrancar.

## 0.1.0 — MVP

### Añadido

- Biblioteca por materias e ingesta de PDF, DOCX, PPTX, web, YouTube, imágenes
  (OCR) y texto pegado.
- Extracción en subproceso aislado con límites de memoria y CPU.
- Índice híbrido FTS5 + `sqlite-vec` con fusión RRF y umbral de similitud.
- Chat con streaming, citas verificables y panel de fuentes con visor de PDF.
- Interfaz web con tema claro y oscuro (diseño «Cuaderno»).
- Capa multi-proveedor: Gemini, Anthropic y cualquier API compatible con OpenAI.
- Módulo de seguridad: SSRF, validación de subidas, saneado, redacción de
  claves, CSRF y CSP.
- Licencia AGPL-3.0, modelo de amenazas y CI con CodeQL, Semgrep, pip-audit y
  gitleaks.
