#!/bin/sh
set -e
if [ -n "${RENDER:-}" ]; then
  if [ -z "${DATABASE_URL:-}" ]; then
    echo "Falta DATABASE_URL. En Render: Web Service → Environment → Add from PostgreSQL (Internal Database URL). No use localhost."
    exit 1
  fi
fi
port="${PORT:-8000}"
exec python -m uvicorn src.web.app:app --host 0.0.0.0 --port "$port"
