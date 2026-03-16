import importlib


def test_job_service_module_imports():
    mod = importlib.import_module("app.services.job_service")
    assert hasattr(mod, "create_job")
    assert hasattr(mod, "update_job_status")
    assert hasattr(mod, "add_job_event")
    assert hasattr(mod, "get_job")
    assert hasattr(mod, "list_jobs")
    assert callable(mod.create_job)
