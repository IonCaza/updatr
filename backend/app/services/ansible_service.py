import json
import os
import shutil
import tempfile
from pathlib import Path

import ansible_runner

from app.services.credential_service import decrypt

PLAYBOOK_DIR = Path(__file__).parent.parent / "ansible" / "playbooks"
TEMP_KEY_DIR = Path(tempfile.gettempdir()) / "updatr_keys"


SSH_OS_TYPES = frozenset({"linux", "truenas", "proxmox"})

INVENTORY_GROUPS = ("linux", "windows", "truenas", "proxmox")


def build_inventory(hosts: list, credentials: dict) -> dict:
    inventory = {
        "all": {
            "children": {g: {"hosts": {}} for g in INVENTORY_GROUPS},
        },
    }

    for host in hosts:
        cred = credentials.get(host.credential_id)
        if not cred:
            continue

        group = host.os_type if host.os_type in INVENTORY_GROUPS else "linux"
        host_vars = {"ansible_host": host.hostname}

        if host.os_type in SSH_OS_TYPES:
            host_vars["ansible_connection"] = "ssh"
            host_vars["ansible_port"] = host.ssh_port
            host_vars["ansible_user"] = cred.username
            host_vars["ansible_ssh_common_args"] = (
                "-o ServerAliveInterval=30 -o ServerAliveCountMax=120"
            )

            if cred.type == "ssh-password" and cred.encrypted_password:
                host_vars["ansible_password"] = decrypt(cred.encrypted_password)
            elif cred.type == "ssh-key" and cred.encrypted_private_key:
                key_path = write_temp_key_file(
                    decrypt(cred.encrypted_private_key), host.id
                )
                host_vars["ansible_ssh_private_key_file"] = key_path
                if cred.encrypted_passphrase:
                    host_vars["ansible_ssh_pass"] = decrypt(cred.encrypted_passphrase)
        else:
            host_vars["ansible_connection"] = "winrm"
            host_vars["ansible_port"] = host.winrm_port
            host_vars["ansible_user"] = cred.username
            host_vars["ansible_winrm_transport"] = "ntlm"
            host_vars["ansible_winrm_scheme"] = "https" if host.winrm_use_ssl else "http"
            host_vars["ansible_winrm_server_cert_validation"] = "ignore"
            if cred.encrypted_password:
                host_vars["ansible_password"] = decrypt(cred.encrypted_password)

        inventory["all"]["children"][group]["hosts"][host.display_name] = host_vars

    return inventory


def write_temp_key_file(key_content: str, host_id: str) -> str:
    TEMP_KEY_DIR.mkdir(parents=True, exist_ok=True)
    path = TEMP_KEY_DIR / f"{host_id}.pem"
    path.write_text(key_content)
    path.chmod(0o600)
    return str(path)


def cleanup_temp_key_files(host_ids: list[str]) -> None:
    for hid in host_ids:
        path = TEMP_KEY_DIR / f"{hid}.pem"
        if path.exists():
            path.unlink()


class PlaybookResult:
    def __init__(self, status: str, rc: int, events: list[dict]):
        self.status = status
        self.rc = rc
        self.events = events


def run_playbook(
    playbook_name: str,
    inventory: dict,
    extra_vars: dict | None = None,
    event_handler=None,
) -> PlaybookResult:
    private_data_dir = tempfile.mkdtemp(prefix="updatr_ansible_")
    inv_dir = Path(private_data_dir) / "inventory"
    inv_dir.mkdir()
    (inv_dir / "hosts.json").write_text(json.dumps(inventory))

    playbook_path = str(PLAYBOOK_DIR / playbook_name)

    envvars = {"ANSIBLE_HOST_KEY_CHECKING": "False"}

    runner = ansible_runner.run(
        private_data_dir=private_data_dir,
        playbook=playbook_path,
        inventory=str(inv_dir / "hosts.json"),
        extravars=extra_vars or {},
        event_handler=event_handler,
        envvars=envvars,
        quiet=True,
    )

    events = _extract_events(runner)
    status = runner.status
    rc = runner.rc if runner.rc is not None else -1

    shutil.rmtree(private_data_dir, ignore_errors=True)
    return PlaybookResult(status=status, rc=rc, events=events)


def _extract_events(runner) -> list[dict]:
    events = []
    try:
        for event in runner.events:
            event_data = event.get("event_data", {})
            if event.get("event") in ("runner_on_ok", "runner_on_failed", "runner_on_unreachable"):
                events.append({
                    "host": event_data.get("host", ""),
                    "task": event_data.get("task", ""),
                    "status": event["event"].replace("runner_on_", ""),
                    "result": event_data.get("res", {}),
                })
    except Exception:
        pass
    return events


def parse_events(result: PlaybookResult) -> list[dict]:
    return result.events
