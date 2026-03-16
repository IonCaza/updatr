"""Tests for the jobs API router structure and endpoints."""

import importlib


def test_jobs_router_has_events_endpoint():
    mod = importlib.import_module("app.api.jobs")
    routes = [r.path for r in mod.router.routes]
    assert any("events" in r for r in routes), f"No events endpoint found in {routes}"


def test_jobs_router_has_stream_endpoint():
    mod = importlib.import_module("app.api.jobs")
    routes = [r.path for r in mod.stream_router.routes]
    assert any("stream" in r for r in routes), f"No stream endpoint found in {routes}"


def test_jobs_router_has_crud_endpoints():
    mod = importlib.import_module("app.api.jobs")
    routes = [r.path for r in mod.router.routes]
    methods = {}
    for r in mod.router.routes:
        for m in getattr(r, "methods", []):
            methods[m] = methods.get(m, 0) + 1
    assert methods.get("GET", 0) >= 3
    assert methods.get("POST", 0) >= 1
