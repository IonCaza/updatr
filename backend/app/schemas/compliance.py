from pydantic import BaseModel


class ComplianceSummary(BaseModel):
    total_hosts: int
    compliant: int
    non_compliant: int
    reboot_required: int
    unreachable: int
    last_scan_at: str | None


class PendingUpdate(BaseModel):
    name: str
    severity: str | None = None
    kb_number: str | None = None
    published_date: str | None = None


class ScanLogEntry(BaseModel):
    task: str
    status: str
    output: dict = {}


class HostComplianceDetail(BaseModel):
    host_id: str
    hostname: str
    display_name: str
    os_type: str
    is_compliant: bool
    is_reachable: bool
    reboot_required: bool
    pending_updates: list[PendingUpdate]
    scanned_at: str | None
    raw_log: list[ScanLogEntry] = []
