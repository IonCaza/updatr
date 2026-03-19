from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.compliance import ComplianceScan
from app.models.host import Host


async def get_compliance_summary(db: AsyncSession) -> dict:
    total_hosts = await db.scalar(select(func.count()).select_from(Host).where(Host.is_active == True))

    subq = (
        select(
            ComplianceScan.host_id,
            func.max(ComplianceScan.scanned_at).label("latest"),
        )
        .group_by(ComplianceScan.host_id)
        .subquery()
    )
    latest_scans = await db.execute(
        select(ComplianceScan)
        .join(subq, (ComplianceScan.host_id == subq.c.host_id) & (ComplianceScan.scanned_at == subq.c.latest))
    )
    scans = list(latest_scans.scalars().all())

    unreachable = 0
    non_compliant = 0
    reboot_required = 0
    compliant = 0
    for s in scans:
        if not s.is_reachable:
            unreachable += 1
        elif not s.is_compliant:
            non_compliant += 1
        elif s.reboot_required:
            reboot_required += 1
        else:
            compliant += 1

    last_scan = max((s.scanned_at for s in scans), default=None)

    return {
        "total_hosts": total_hosts or 0,
        "compliant": compliant,
        "non_compliant": non_compliant,
        "reboot_required": reboot_required,
        "unreachable": unreachable,
        "last_scan_at": last_scan.isoformat() if last_scan else None,
    }


async def get_hosts_by_status(db: AsyncSession) -> dict:
    subq = (
        select(
            ComplianceScan.host_id,
            func.max(ComplianceScan.scanned_at).label("latest"),
        )
        .group_by(ComplianceScan.host_id)
        .subquery()
    )
    rows = await db.execute(
        select(ComplianceScan, Host)
        .join(subq, (ComplianceScan.host_id == subq.c.host_id) & (ComplianceScan.scanned_at == subq.c.latest))
        .join(Host, Host.id == ComplianceScan.host_id)
    )

    groups: dict[str, list] = {
        "compliant": [],
        "non_compliant": [],
        "reboot_required": [],
        "unreachable": [],
    }
    for scan, host in rows.all():
        entry = {
            "host_id": host.id,
            "display_name": host.display_name,
            "hostname": host.hostname,
            "os_type": host.os_type,
            "pending_update_count": len(scan.pending_updates) if scan.pending_updates else 0,
            "scanned_at": scan.scanned_at.isoformat() if scan.scanned_at else None,
        }
        if not scan.is_reachable:
            groups["unreachable"].append(entry)
        elif not scan.is_compliant:
            groups["non_compliant"].append(entry)
        elif scan.reboot_required:
            groups["reboot_required"].append(entry)
        else:
            groups["compliant"].append(entry)
    return groups


async def get_host_compliance(db: AsyncSession, host_id: str) -> dict | None:
    result = await db.execute(
        select(ComplianceScan)
        .where(ComplianceScan.host_id == host_id)
        .order_by(ComplianceScan.scanned_at.desc())
        .limit(1)
    )
    scan = result.scalar_one_or_none()
    if not scan:
        return None

    host_result = await db.execute(select(Host).where(Host.id == host_id))
    host = host_result.scalar_one_or_none()
    if not host:
        return None

    return {
        "host_id": host.id,
        "hostname": host.hostname,
        "display_name": host.display_name,
        "os_type": host.os_type,
        "is_compliant": scan.is_compliant,
        "is_reachable": scan.is_reachable,
        "reboot_required": scan.reboot_required,
        "pending_updates": scan.pending_updates or [],
        "scanned_at": scan.scanned_at.isoformat() if scan.scanned_at else None,
        "raw_log": scan.raw_log or [],
    }
