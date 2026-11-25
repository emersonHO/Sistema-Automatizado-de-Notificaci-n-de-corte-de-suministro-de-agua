#!/bin/sh
set -e
mkdir -p /app/data/raw /app/data/processed /app/data/simulaciones /app/data/evaluacion
if [ "$(id -u)" = "0" ]; then
  chown -R appuser:appuser /app/data
  exec gosu appuser "$@"
fi
exec "$@"
