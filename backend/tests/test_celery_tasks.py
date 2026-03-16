import importlib


def test_patch_task_module():
    mod = importlib.import_module("app.tasks.patch_task")
    assert hasattr(mod, "patch_hosts")
    assert callable(mod.patch_hosts)


def test_patch_task_has_sync_helpers():
    mod = importlib.import_module("app.tasks.patch_task")
    assert hasattr(mod, "_load_hosts_and_creds")
    assert hasattr(mod, "_update_job_status")
    assert hasattr(mod, "_save_event")
    assert hasattr(mod, "_make_event_handler")


def test_patch_task_event_handler_produces_callable():
    from app.tasks.patch_task import _make_event_handler
    handler = _make_event_handler("fake-job-id")
    assert callable(handler)


def test_patch_task_event_handler_ignores_untracked():
    from app.tasks.patch_task import _make_event_handler
    handler = _make_event_handler("fake-job-id")
    handler({"event": "verbose", "event_data": {}})


def test_compliance_task_module():
    mod = importlib.import_module("app.tasks.compliance_task")
    assert hasattr(mod, "compliance_scan")
    assert callable(mod.compliance_scan)


def test_compliance_task_has_sync_helpers():
    mod = importlib.import_module("app.tasks.compliance_task")
    assert hasattr(mod, "_load_hosts")
    assert hasattr(mod, "_save_scan")


def test_celery_autodiscover_finds_tasks():
    from app.tasks.celery_app import celery_app
    celery_app.loader.import_module("app.tasks.patch_task")
    celery_app.loader.import_module("app.tasks.compliance_task")
    assert "patch_hosts" in celery_app.tasks or any(
        "patch_hosts" in t for t in celery_app.tasks
    )
