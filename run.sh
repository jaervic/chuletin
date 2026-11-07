#!/usr/bin/env bash
# Arranca Chuletin en local. Uso: ./run.sh
set -euo pipefail

cd "$(dirname "$0")"

PYTHON_BIN="${PYTHON_BIN:-python3}"
HOST="${CHULETIN_HOST:-127.0.0.1}"
PORT="${CHULETIN_PORT:-8000}"

if [ ! -d ".venv" ]; then
  echo "Creando entorno virtual..."
  "$PYTHON_BIN" -m venv .venv
fi

if [ ! -f ".venv/.chuletin-deps" ]; then
  echo "Instalando dependencias de Python (solo la primera vez)..."
  .venv/bin/pip install --upgrade pip -q
  .venv/bin/pip install -r backend/requirements.txt
  touch .venv/.chuletin-deps
fi

if [ -d "frontend" ] && [ -f "frontend/package.json" ] && [ ! -d "frontend/dist" ]; then
  if command -v npm >/dev/null 2>&1; then
    echo "Compilando el frontend..."
    (cd frontend && npm install --no-audit --no-fund && npm run build)
  else
    echo "Aviso: npm no esta instalado; se servira solo la API."
  fi
fi

export PYTHONPATH="$PWD/backend${PYTHONPATH:+:$PYTHONPATH}"

echo ""
echo "Chuletin en http://$HOST:$PORT"
echo "Pulsa Ctrl+C para detener."
echo ""

exec .venv/bin/uvicorn app.main:app --host "$HOST" --port "$PORT" --app-dir backend
