from pathlib import Path

from src.url_publica import url_base


def test_url_base_lee_archivo_local():
    local = Path("data") / "url_publica.txt"
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_text("https://ejemplo-prueba.trycloudflare.com", encoding="utf-8")
    try:
        assert url_base() == "https://ejemplo-prueba.trycloudflare.com"
    finally:
        if local.exists():
            local.unlink()
