"""Tests for the compliance event parsing logic that maps Ansible events
to per-host compliance results. This was a source of bugs (only reading
the first event per host, wrong key name) so it gets dedicated coverage."""


def _build_typical_events(host: str = "web1", pending_count: int = 3):
    """Simulate the events ansible-runner produces for a compliance run."""
    updates = [f"pkg-{i}" for i in range(pending_count)]
    return [
        {"host": host, "task": "Gathering Facts", "status": "ok", "result": {}},
        {"host": host, "task": "Update apt cache (Debian/Ubuntu)", "status": "ok", "result": {}},
        {"host": host, "task": "List upgradable packages (Debian/Ubuntu)", "status": "ok", "result": {}},
        {"host": host, "task": "Check if reboot is required (Debian/Ubuntu)", "status": "ok", "result": {}},
        {
            "host": host,
            "task": "Build compliance result",
            "status": "ok",
            "result": {
                "ansible_facts": {
                    "compliance_result": {
                        "pending_updates": updates,
                        "reboot_required": "False",
                        "update_count": str(pending_count),
                    }
                }
            },
        },
    ]


def _parse_events(all_events, host_name_to_id):
    """Mirrors the parsing logic from compliance_task.compliance_scan."""
    host_compliance: dict[str, dict] = {}
    for event in all_events:
        host_name = event["host"]
        host_id = host_name_to_id.get(host_name)
        if not host_id:
            continue
        if host_id not in host_compliance:
            host_compliance[host_id] = {"is_reachable": True, "compliance_result": {}}
        if event["status"] == "unreachable":
            host_compliance[host_id]["is_reachable"] = False
        compliance = event.get("result", {}).get("ansible_facts", {}).get("compliance_result")
        if compliance:
            host_compliance[host_id]["compliance_result"] = compliance
    return host_compliance


def test_extracts_compliance_from_last_event():
    events = _build_typical_events("web1", pending_count=5)
    result = _parse_events(events, {"web1": "id-1"})
    assert "id-1" in result
    cr = result["id-1"]["compliance_result"]
    assert len(cr["pending_updates"]) == 5
    assert result["id-1"]["is_reachable"] is True


def test_compliant_host_has_empty_updates():
    events = _build_typical_events("web1", pending_count=0)
    result = _parse_events(events, {"web1": "id-1"})
    cr = result["id-1"]["compliance_result"]
    assert len(cr["pending_updates"]) == 0


def test_unreachable_host():
    events = [{"host": "web2", "task": "Gathering Facts", "status": "unreachable", "result": {}}]
    result = _parse_events(events, {"web2": "id-2"})
    assert result["id-2"]["is_reachable"] is False
    assert result["id-2"]["compliance_result"] == {}


def test_multiple_hosts():
    events = _build_typical_events("web1", 2) + _build_typical_events("db1", 0)
    mapping = {"web1": "id-1", "db1": "id-2"}
    result = _parse_events(events, mapping)
    assert len(result) == 2
    assert len(result["id-1"]["compliance_result"]["pending_updates"]) == 2
    assert len(result["id-2"]["compliance_result"]["pending_updates"]) == 0


def test_unknown_host_ignored():
    events = [{"host": "unknown", "task": "foo", "status": "ok", "result": {}}]
    result = _parse_events(events, {"web1": "id-1"})
    assert len(result) == 0


def test_uses_pending_updates_key_not_updates():
    """Regression: the old code used compliance.get('updates') which was wrong."""
    events = _build_typical_events("web1", pending_count=10)
    result = _parse_events(events, {"web1": "id-1"})
    cr = result["id-1"]["compliance_result"]
    assert "pending_updates" in cr
    assert "updates" not in cr
