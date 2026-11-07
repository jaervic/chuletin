#!/usr/bin/env bash
# Prueba de humo completa de la interfaz con un proveedor LLM falso.
set -euo pipefail

cd "$(dirname "$0")/.."

PORT="${PORT:-8021}"
MOCK_PORT="${MOCK_PORT:-8099}"
TMP="$(mktemp -d /tmp/chuletin-ui-XXXXXX)"
SAMPLE="$TMP/apuntes.pdf"

cleanup() {
  [ -n "${APP_PID:-}" ] && kill "$APP_PID" 2>/dev/null || true
  [ -n "${MOCK_PID:-}" ] && kill "$MOCK_PID" 2>/dev/null || true
}
trap cleanup EXIT

.venv/bin/python scripts/make_sample_pdf.py "$SAMPLE" >/dev/null

PYTHONPATH="$PWD:$PWD/backend" .venv/bin/uvicorn scripts.mock_llm:app \
  --host 127.0.0.1 --port "$MOCK_PORT" >"$TMP/mock.log" 2>&1 &
MOCK_PID=$!

PYTHONPATH="$PWD/backend" \
CHULETIN_WARMUP=false \
CHULETIN_DATA_DIR="$TMP" \
CHULETIN_MODELS_DIR="$PWD/data/models" \
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$PORT" >"$TMP/app.log" 2>&1 &
APP_PID=$!

for _ in $(seq 1 40); do
  if curl -sf "http://127.0.0.1:$PORT/api/health" >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

CHULETIN_URL="http://127.0.0.1:$PORT" \
CHULETIN_MOCK_URL="http://127.0.0.1:$MOCK_PORT/v1" \
SAMPLE_PDF="$SAMPLE" \
SHOTS_DIR="$TMP" \
node frontend/scripts/ui_smoke.mjs

echo "Capturas en: $TMP"
