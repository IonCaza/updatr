from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.host import Host
from app.models.compliance import ComplianceScan
from app.schemas.compliance import ComplianceSummary, HostComplianceDetail
from app.services.compliance_service import get_compliance_summary, get_host_compliance, get_hosts_by_status
from app.tasks.compliance_task import compliance_scan
from app.services.queue_service import queue_for_host, collect_site_queues
from app.api.deps import get_current_user

router = APIRouter(prefix="/compliance", tags=["compliance"], dependencies=[Depends(get_current_user)])


@router.get("/summary", response_model=ComplianceSummary)
async def summary(db: AsyncSession = Depends(get_db)):
    data = await get_compliance_summary(db)
    return ComplianceSummary(**data)


@router.get("/hosts-by-status")
async def hosts_by_status(db: AsyncSession = Depends(get_db)):
    return await get_hosts_by_status(db)


@router.get("/hosts/{host_id}", response_model=HostComplianceDetail)
async def host_detail(host_id: str, db: AsyncSession = Depends(get_db)):
    data = await get_host_compliance(db, host_id)
    if not data:
        raise HTTPException(status_code=404, detail="No compliance data for host")
    return HostComplianceDetail(**data)


@router.get("/scan-details")
async def scan_details(
    at: str = Query(..., description="ISO timestamp of the scan batch"),
    db: AsyncSession = Depends(get_db),
):
    """Return per-host results for a specific scan batch (matched by truncated second)."""
    try:
        scan_time = datetime.fromisoformat(at)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ISO timestamp")

    window_start = scan_time - timedelta(seconds=1)
    window_end = scan_time + timedelta(seconds=1)

    rows = await db.execute(
        select(ComplianceScan, Host)
        .join(Host, Host.id == ComplianceScan.host_id)
        .where(ComplianceScan.scanned_at.between(window_start, window_end))
        .order_by(Host.display_name)
    )

    hosts = []
    for scan, host in rows.all():
        if not scan.is_reachable:
            status = "unreachable"
        elif not scan.is_compliant:
            status = "non_compliant"
        elif scan.reboot_required:
            status = "reboot_required"
        else:
            status = "compliant"

        hosts.append(
            {
                "host_id": host.id,
                "display_name": host.display_name,
                "hostname": host.hostname,
                "os_type": host.os_type,
                "status": status,
                "pending_update_count": len(scan.pending_updates) if scan.pending_updates else 0,
                "reboot_required": scan.reboot_required,
                "worker_queue": scan.worker_queue,
                "raw_log": scan.raw_log or [],
            }
        )

    queues = sorted({h["worker_queue"] for h in hosts if h["worker_queue"]})
    return {"scanned_at": at, "queues": queues, "hosts": hosts}


@router.post("/scan", status_code=202)
async def trigger_scan(
    host_ids: list[str] | None = None,
    db: AsyncSession = Depends(get_db),
):
    host_load_opts = (
        selectinload(Host.children).selectinload(Host.children),
        selectinload(Host.site_rel),
    )
    if host_ids:
        result = await db.execute(
            select(Host).where(Host.id.in_(host_ids)).options(*host_load_opts)
        )
        hosts = list(result.scalars().all())
    else:
        result = await db.execute(
            select(Host).where(Host.is_active == True).options(*host_load_opts)
        )
        hosts = list(result.scalars().all())

    all_sites = collect_site_queues(hosts)
    hosts_by_queue: dict[str, list[str]] = {}
    for h in hosts:
        queue = queue_for_host(h, all_sites)
        hosts_by_queue.setdefault(queue, []).append(h.id)

    for queue, queue_host_ids in hosts_by_queue.items():
        compliance_scan.apply_async(args=[queue_host_ids], queue=queue)

    return {"message": f"Compliance scan triggered across {len(hosts_by_queue)} queue(s)"}
