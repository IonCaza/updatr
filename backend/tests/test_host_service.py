import importlib


def test_host_service_module():
    mod = importlib.import_module("app.services.host_service")
    assert hasattr(mod, "create_host")
    assert hasattr(mod, "get_host")
    assert hasattr(mod, "list_hosts")
    assert hasattr(mod, "update_host")
    assert hasattr(mod, "delete_host")


def test_api_routers_registered():
    from app.main import app
    paths = [r.path for r in app.routes]
    assert any("/api/auth" in p for p in paths)
    assert any("/api/credentials" in p for p in paths)
    assert any("/api/hosts" in p for p in paths)
