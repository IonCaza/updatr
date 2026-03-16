from datetime import datetime

from sqlalchemy import select, func, case, literal, union_all, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.models.compliance import ComplianceScan
from app.models.host import Host
from app.models.schedule import Schedule


async def get_activity_feed(db: AsyncSession, limit: int = 20) -> list[dict]:
    jobs = await _job_entries(db)
    scans = await _scan_entries(db)
    schedules = await _schedule_entries(db)

    combined = jobs + scans + schedules
    combined.sort(key=lambda e: e["timestamp"], reverse=True)
    return combined[:limit]


async def _job_entries(db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(Job).order_by(Job.created_at.desc()).limit(30)
    )
    entries = []
    for job in result.scalars().all():
        host_count = len(job.host_ids) if job.host_ids else 0
        ts = job.completed_at or job.started_at or job.created_at

        if job.status == "completed":
            title = f"Patch job completed"
            status = "completed"
        elif job.status == "failed":
            title = f"Patch job failed"
            status = "failed"
        elif job.status == "running":
            title = f"Patch job running"
            status = "running"
        else:
            title = f"Patch job queued"
            status = "triggered"

        entries.append({
            "id": job.id,
            "type": "job",
            "title": title,
            "detail": f"{host_count} host{'s' if host_count != 1 else ''}",
            "status": status,
            "timestamp": ts.isoformat(),
            "link": f"/jobs/{job.id}",
        })
    return entries


async def _scan_entries(db: AsyncSession) -> list[dict]:
    scan_time = func.date_trunc("second", ComplianceScan.scanned_at)
    result = await db.execute(
        select(
            scan_time.label("scan_time"),
            func.count().label("total"),
            func.sum(case((ComplianceScan.is_compliant == True, 1), else_=0)).label("compliant_count"),
            func.sum(case((ComplianceScan.is_reachable == False, 1), else_=0)).label("unreachable_count"),
            func.string_agg(
                func.distinct(ComplianceScan.worker_queue),
                literal(", "),
            ).label("queues"),
        )
        .group_by(scan_time)
        .order_by(scan_time.desc())
        .limit(20)
    )

    entries = []
    for row in result.all():
        total = row.total
        compliant = row.compliant_count or 0
        non_compliant = total - compliant - (row.unreachable_count or 0)
        unreachable = row.unreachable_count or 0

        parts = []
        if compliant:
            parts.append(f"{compliant} compliant")
        if non_compliant:
            parts.append(f"{non_compliant} non-compliant")
        if unreachable:
            parts.append(f"{unreachable} unreachable")

        queue_label = row.queues or None

        entries.append({
            "id": f"scan-{row.scan_time.isoformat()}",
            "type": "scan",
            "title": f"Compliance scan \u00B7 {total} host{'s' if total != 1 else ''} scanned",
            "detail": ", ".join(parts) if parts else "No results",
            "status": "completed",
            "timestamp": row.scan_time.isoformat(),
            "link": None,
            "scan_at": row.scan_time.isoformat(),
            "queues": queue_label,
        })
    return entries


async def _schedule_entries(db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(Schedule)
        .where(Schedule.last_run_at.isnot(None))
        .order_by(Schedule.last_run_at.desc())
        .limit(10)
    )
    entries = []
    for sched in result.scalars().all():
        host_count = len(sched.host_ids) if sched.host_ids else 0
        entries.append({
            "id": f"sched-{sched.id}",
            "type": "schedule",
            "title": f"Scheduled job \"{sched.name}\" ran",
            "detail": f"{host_count} host{'s' if host_count != 1 else ''}" if host_count else "Tag-based",
            "status": "completed",
            "timestamp": sched.last_run_at.isoformat(),
            "link": None,
        })
    return entries
