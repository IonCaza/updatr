import os
import yaml


PLAYBOOK_DIR = os.path.join(
    os.path.dirname(__file__), "..", "app", "ansible", "playbooks"
)

EXPECTED_PLAYBOOKS = [
    "ping.yml",
    "patch_linux.yml",
    "patch_windows.yml",
    "compliance_linux.yml",
    "compliance_windows.yml",
    "reboot.yml",
]


def test_all_playbooks_exist():
    for name in EXPECTED_PLAYBOOKS:
        path = os.path.join(PLAYBOOK_DIR, name)
        assert os.path.exists(path), f"Missing playbook: {name}"


def test_playbooks_are_valid_yaml():
    for name in EXPECTED_PLAYBOOKS:
        path = os.path.join(PLAYBOOK_DIR, name)
        with open(path) as f:
            data = yaml.safe_load(f)
        assert isinstance(data, list), f"{name} should be a list of plays"
        assert len(data) > 0, f"{name} should have at least one play"


def test_each_play_has_hosts_and_tasks():
    for name in EXPECTED_PLAYBOOKS:
        path = os.path.join(PLAYBOOK_DIR, name)
        with open(path) as f:
            plays = yaml.safe_load(f)
        for play in plays:
            assert "hosts" in play, f"{name}: play missing 'hosts'"
            assert "tasks" in play, f"{name}: play missing 'tasks'"


def test_ping_playbook_targets_both_os():
    path = os.path.join(PLAYBOOK_DIR, "ping.yml")
    with open(path) as f:
        plays = yaml.safe_load(f)
    hosts_targeted = {p["hosts"] for p in plays}
    assert "linux" in hosts_targeted
    assert "windows" in hosts_targeted


def test_patch_linux_has_reboot_task():
    path = os.path.join(PLAYBOOK_DIR, "patch_linux.yml")
    with open(path) as f:
        plays = yaml.safe_load(f)
    task_names = [t.get("name", "") for p in plays for t in p["tasks"]]
    assert any("reboot" in n.lower() for n in task_names)
