import os
import importlib
from unittest.mock import MagicMock

from app.services.ansible_service import (
    build_inventory,
    write_temp_key_file,
    cleanup_temp_key_files,
    parse_events,
    TEMP_KEY_DIR,
)


def _make_host(os_type="linux", **overrides):
    host = MagicMock()
    host.id = overrides.get("id", "host-1")
    host.display_name = overrides.get("display_name", "web1")
    host.hostname = overrides.get("hostname", "192.168.1.10")
    host.os_type = os_type
    host.ssh_port = overrides.get("ssh_port", 22)
    host.winrm_port = overrides.get("winrm_port", 5986)
    host.winrm_use_ssl = overrides.get("winrm_use_ssl", True)
    host.credential_id = overrides.get("credential_id", "cred-1")
    return host


def _make_cred(cred_type="ssh-password", **overrides):
    from app.services.credential_service import encrypt

    cred = MagicMock()
    cred.username = overrides.get("username", "root")
    cred.type = cred_type
    cred.encrypted_password = encrypt("secret") if cred_type != "ssh-key" else None
    cred.encrypted_private_key = encrypt("KEY_CONTENT") if cred_type == "ssh-key" else None
    cred.encrypted_passphrase = None
    return cred


def test_build_inventory_linux():
    host = _make_host(os_type="linux")
    cred = _make_cred(cred_type="ssh-password")
    inv = build_inventory([host], {"cred-1": cred})
    linux_hosts = inv["all"]["children"]["linux"]["hosts"]
    assert "web1" in linux_hosts
    assert linux_hosts["web1"]["ansible_connection"] == "ssh"
    assert linux_hosts["web1"]["ansible_port"] == 22


def test_build_inventory_windows():
    host = _make_host(os_type="windows", display_name="win1", credential_id="cred-2")
    cred = _make_cred(cred_type="winrm-password")
    inv = build_inventory([host], {"cred-2": cred})
    win_hosts = inv["all"]["children"]["windows"]["hosts"]
    assert "win1" in win_hosts
    assert win_hosts["win1"]["ansible_connection"] == "winrm"
    assert win_hosts["win1"]["ansible_winrm_server_cert_validation"] == "ignore"


def test_write_and_cleanup_key():
    host_id = "test-host-key"
    path = write_temp_key_file("PRIVATE_KEY_CONTENT", host_id)
    assert os.path.exists(path)
    assert oct(os.stat(path).st_mode)[-3:] == "600"
    with open(path) as f:
        assert f.read() == "PRIVATE_KEY_CONTENT"
    cleanup_temp_key_files([host_id])
    assert not os.path.exists(path)


def test_parse_events():
    from app.services.ansible_service import PlaybookResult
    result = PlaybookResult(
        status="successful",
        rc=0,
        events=[
            {"host": "web1", "task": "Install", "status": "ok", "result": {"changed": True}},
            {"host": "web2", "task": "Install", "status": "failed", "result": {"msg": "err"}},
        ],
    )
    events = parse_events(result)
    assert len(events) == 2
    assert events[0]["status"] == "ok"
    assert events[1]["status"] == "failed"


def test_module_has_run_playbook():
    mod = importlib.import_module("app.services.ansible_service")
    assert hasattr(mod, "run_playbook")
    assert callable(mod.run_playbook)
