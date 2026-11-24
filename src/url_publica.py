"""URL que se pone en correos. Prioriza el archivo escrito por el túnel."""

from __future__ import annotations

from pathlib import Path

from src.config import BASE_DIR, BASE_URL


def url_base() -> str:
    for ruta in (
        Path("/app/data/url_publica.txt"),
        BASE_DIR / "data" / "url_publica.txt",
    ):
        try:
            if ruta.is_file():
                texto = ruta.read_text(encoding="utf-8").strip().split()[0]
                if texto.startswith("https://") or texto.startswith("http://"):
                    return texto.rstrip("/")
        except OSError:
            continue
    return (BASE_URL or "http://127.0.0.1:8000").rstrip("/")
