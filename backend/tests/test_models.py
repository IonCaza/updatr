from app.database import Base
from app.models import User, Credential, Host, Job, JobEvent, Schedule, ComplianceScan


def test_all_models_registered():
    table_names = set(Base.metadata.tables.keys())
    expected = {
        "users",
        "credentials",
        "hosts",
        "jobs",
        "job_events",
        "schedules",
        "compliance_scans",
    }
    assert expected.issubset(table_names), f"Missing: {expected - table_names}"


def test_user_model_columns():
    cols = {c.name for c in User.__table__.columns}
    assert {"id", "username", "password_hash", "created_at"}.issubset(cols)


def test_credential_model_columns():
    cols = {c.name for c in Credential.__table__.columns}
    assert {
        "id",
        "name",
        "type",
        "username",
        "encrypted_password",
        "encrypted_private_key",
    }.issubset(cols)


def test_host_model_columns():
    cols = {c.name for c in Host.__table__.columns}
    assert {
        "id",
        "display_name",
        "hostname",
        "os_type",
        "tags",
        "credential_id",
        "is_active",
    }.issubset(cols)


def test_job_model_columns():
    cols = {c.name for c in Job.__table__.columns}
    assert {
        "id",
        "status",
        "job_type",
        "host_ids",
        "reboot_policy",
        "host_results",
    }.issubset(cols)


def test_job_event_model_columns():
    cols = {c.name for c in JobEvent.__table__.columns}
    assert {"id", "job_id", "host", "task_name", "status", "output"}.issubset(cols)


def test_schedule_model_columns():
    cols = {c.name for c in Schedule.__table__.columns}
    assert {
        "id",
        "name",
        "cron_expression",
        "host_ids",
        "is_active",
    }.issubset(cols)


def test_compliance_scan_model_columns():
    cols = {c.name for c in ComplianceScan.__table__.columns}
    assert {
        "id",
        "host_id",
        "is_compliant",
        "pending_updates",
        "reboot_required",
    }.issubset(cols)
