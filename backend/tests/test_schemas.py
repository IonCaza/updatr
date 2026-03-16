import pytest
from pydantic import ValidationError

from app.schemas.auth import LoginRequest, SetupRequest, TokenResponse
from app.schemas.credential import CredentialCreate, CredentialResponse
from app.schemas.host import HostCreate, HostResponse, HostUpdate
from app.schemas.job import JobCreate, JobResponse
from app.schemas.schedule import ScheduleCreate, ScheduleResponse
from app.schemas.compliance import ComplianceSummary, HostComplianceDetail


def test_login_request_validates():
    req = LoginRequest(username="admin", password="secret")
    assert req.username == "admin"


def test_login_request_rejects_empty_username():
    with pytest.raises(ValidationError):
        LoginRequest(username="", password="secret")


def test_setup_request_rejects_short_password():
    with pytest.raises(ValidationError):
        SetupRequest(username="admin", password="short")


def test_credential_create_validates_type():
    c = CredentialCreate(
        name="my-key", type="ssh-key", username="root", private_key="KEY"
    )
    assert c.type == "ssh-key"


def test_credential_create_rejects_bad_type():
    with pytest.raises(ValidationError):
        CredentialCreate(name="bad", type="invalid", username="root")


def test_credential_response_omits_secrets():
    fields = set(CredentialResponse.model_fields.keys())
    assert "password" not in fields
    assert "private_key" not in fields
    assert "encrypted_password" not in fields


def test_host_create_validates_ports():
    h = HostCreate(
        display_name="web1",
        hostname="192.168.1.10",
        os_type="linux",
        credential_id="abc-123",
    )
    assert h.ssh_port == 22
    assert h.tags == []


def test_host_create_rejects_invalid_port():
    with pytest.raises(ValidationError):
        HostCreate(
            display_name="web1",
            hostname="x",
            os_type="linux",
            ssh_port=99999,
            credential_id="abc",
        )


def test_host_create_rejects_invalid_os():
    with pytest.raises(ValidationError):
        HostCreate(
            display_name="web1",
            hostname="x",
            os_type="macos",
            credential_id="abc",
        )


def test_host_update_allows_partial():
    u = HostUpdate(display_name="new-name")
    assert u.display_name == "new-name"
    assert u.hostname is None


def test_job_create_defaults():
    j = JobCreate(host_ids=["h1"])
    assert j.reboot_policy == "if-required"
    assert "security" in j.patch_categories


def test_schedule_create_validates():
    s = ScheduleCreate(name="nightly", cron_expression="0 2 * * *")
    assert s.reboot_policy == "if-required"
    assert "security" in s.patch_categories


def test_compliance_summary():
    cs = ComplianceSummary(
        total_hosts=10,
        compliant=8,
        non_compliant=2,
        reboot_required=1,
        unreachable=0,
        last_scan_at="2026-02-20T02:00:00Z",
    )
    assert cs.total_hosts == 10
