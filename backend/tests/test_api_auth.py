import importlib


def test_auth_router_exists():
    mod = importlib.import_module("app.api.auth")
    assert hasattr(mod, "router")
    routes = [r.path for r in mod.router.routes]
    assert any("setup" in r for r in routes)
    assert any("login" in r for r in routes)
    assert any("refresh" in r for r in routes)
    assert any("me" in r for r in routes)


def test_deps_module():
    mod = importlib.import_module("app.api.deps")
    assert hasattr(mod, "get_current_user")
    assert callable(mod.get_current_user)
