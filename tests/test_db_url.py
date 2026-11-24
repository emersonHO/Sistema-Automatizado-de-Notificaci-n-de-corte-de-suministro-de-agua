from src.db import conninfo


def test_conninfo_database_url(monkeypatch):
    from src import config as cfg
    from src import db as dbmod

    monkeypatch.setattr(cfg, "DATABASE_URL", "postgres://u:p@host:5432/db")
    monkeypatch.setattr(cfg, "DB_SSLMODE", "require")
    monkeypatch.setattr(cfg, "EN_RENDER", False)
    monkeypatch.setattr(dbmod.config, "DATABASE_URL", "postgres://u:p@host:5432/db")
    monkeypatch.setattr(dbmod.config, "DB_SSLMODE", "require")
    monkeypatch.setattr(dbmod.config, "EN_RENDER", False)
    texto = conninfo()
    assert texto.startswith("postgresql://")
    assert "sslmode=require" in texto


def test_conninfo_local_sin_url(monkeypatch):
    from src import db as dbmod

    monkeypatch.setattr(dbmod.config, "DATABASE_URL", "")
    monkeypatch.setattr(dbmod.config, "DB_SSLMODE", "")
    monkeypatch.setattr(dbmod.config, "DB_HOST", "localhost")
    monkeypatch.setattr(dbmod.config, "DB_PORT", "5432")
    monkeypatch.setattr(dbmod.config, "DB_NAME", "notificaciones_agua_test")
    monkeypatch.setattr(dbmod.config, "DB_USER", "agua")
    monkeypatch.setattr(dbmod.config, "DB_PASSWORD", "x")
    texto = conninfo()
    assert "host=localhost" in texto
    assert "sslmode" not in texto
