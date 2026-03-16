import importlib

from fastapi.testclient import TestClient


def test_health_endpoint():
    from app.main import app

    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_config_loads():
    from app.config import Settings

    s = Settings(
        DATABASE_URL="postgresql+asyncpg://test:test@localhost/test",
        REDIS_URL="redis://localhost:6379/0",
        SECRET_KEY="test-secret",
        ENCRYPTION_KEY="test-key",
    )
    assert s.DATABASE_URL.startswith("postgresql")
    assert s.REDIS_URL.startswith("redis")


def test_database_module_imports():
    mod = importlib.import_module("app.database")
    assert hasattr(mod, "engine")
    assert hasattr(mod, "async_session")
    assert hasattr(mod, "sync_engine")
    assert hasattr(mod, "SyncSession")
    assert hasattr(mod, "Base")
    assert hasattr(mod, "get_db")


def test_celery_app_imports():
    mod = importlib.import_module("app.tasks.celery_app")
    assert hasattr(mod, "celery_app")
    assert mod.celery_app.main == "updatr"
