#!/bin/sh
set -e
port="${PORT:-8000}"
exec python -m uvicorn src.web.app:app --host 0.0.0.0 --port "$port"
