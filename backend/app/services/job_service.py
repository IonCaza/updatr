from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job, JobEvent


async def create_job(
    db: AsyncSession,
    job_type: str,
    host_ids: list[str],
    tags_filter: list[str] | None = None,
    patch_categories: list[str] | None = None,
    reboot_policy: str = "if-required",
    schedule_id: str | None = None,
) -> Job:
    job = Job(
        job_type=job_type,
        host_ids=host_ids,
        tags_filter=tags_filter or [],
        patch_categories=patch_categories or ["security", "critical"],
        reboot_policy=reboot_policy,
        schedule_id=schedule_id,
        status="queued",
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


async def update_job_status(
    db: AsyncSession, job_id: str, status: str
) -> Job | None:
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        return None
    job.status = status
    if status == "running" and not job.started_at:
        job.started_at = datetime.now(timezone.utc)
    if status in ("completed", "failed", "cancelled"):
        job.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(job)
    return job


async def add_job_event(
    db: AsyncSession,
    job_id: str,
    host: str,
    task_name: str,
    status: str,
    output: dict | None = None,
) -> JobEvent:
    event = JobEvent(
        job_id=job_id,
        host=host,
        task_name=task_name,
        status=status,
        output=output or {},
    )
    db.add(event)
    await db.commit()
    return event


async def get_job(db: AsyncSession, job_id: str) -> Job | None:
    result = await db.execute(select(Job).where(Job.id == job_id))
    return result.scalar_one_or_none()


async def list_jobs(
    db: AsyncSession, status: str | None = None, limit: int = 50
) -> list[Job]:
    stmt = select(Job).order_by(Job.created_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(Job.status == status)
    result = await db.execute(stmt)
    return list(result.scalars().all())
