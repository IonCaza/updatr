import asyncio
import json

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from jwt import ExpiredSignatureError, InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.models.host import Host
from app.models.job import JobEvent
from app.models.user import User
from app.schemas.job import JobCreate, JobResponse
from app.services.auth_service import decode_token
from app.services.job_service import create_job, get_job, list_jobs
from app.services.orchestration_service import compute_patch_waves
from app.tasks.patch_task import patch_hosts
from app.tasks.orchestrate_task import orchestrate_patch_job
from app.services.queue_service import queue_for_host, collect_site_queues, queue_for_control_plane
from app.api.deps import get_current_user

router = APIRouter(prefix="/jobs", tags=["jobs"], dependencies=[Depends(get_current_user)])
stream_router = APIRouter(prefix="/jobs", tags=["jobs"])


def _to_response(j) -> JobResponse:
    return JobResponse(
        id=j.id,
        status=j.status,
        job_type=j.job_type,
        host_ids=j.host_ids or [],
        tags_filter=j.tags_filter or [],
        patch_categories=j.patch_categories or [],
        reboot_policy=j.reboot_policy,
        schedule_id=str(j.schedule_id) if j.schedule_id else None,
        started_at=j.started_at.isoformat() if j.started_at else None,
        completed_at=j.completed_at.isoformat() if j.completed_at else None,
        host_results=j.host_results or {},
        wave_plan=j.wave_plan,
        current_wave=j.current_wave,
        created_at=j.created_at.isoformat(),
    )


@router.post("", response_model=JobResponse, status_code=201)
async def create_patch_job(body: JobCreate, db: AsyncSession = Depends(get_db)):
    job = await create_job(
        db,
        job_type="patch",
        host_ids=body.host_ids,
        tags_filter=body.tags_filter,
        patch_categories=body.patch_categories,
        reboot_policy=body.reboot_policy,
    )

    host_load_opts = (
        selectinload(Host.children).selectinload(Host.children),
        selectinload(Host.site_rel),
    )
    result = await db.execute(
        select(Host).where(Host.id.in_(body.host_ids)).options(*host_load_opts)
    )
    hosts = list(result.scalars().all())

    has_hierarchy = any(h.parent_id for h in hosts)

    extra = {"reboot_policy": body.reboot_policy}

    if has_hierarchy:
        all_hosts = list((await db.execute(select(Host))).scalars().all())
        plan = compute_patch_waves(hosts, all_hosts)
        job.wave_plan = plan
        await db.commit()
        await db.refresh(job)

        cp_queue = await queue_for_control_plane(db)
        orchestrate_patch_job.apply_async(
            args=[job.id, body.host_ids, extra, plan],
            queue=cp_queue,
        )
    else:
        all_sites = collect_site_queues(hosts)
        hosts_by_queue: dict[str, list[str]] = {}
        for h in hosts:
            queue = queue_for_host(h, all_sites)
            hosts_by_queue.setdefault(queue, []).append(h.id)

        for queue, queue_host_ids in hosts_by_queue.items():
            patch_hosts.apply_async(
                args=[job.id, queue_host_ids, extra],
                queue=queue,
            )

    return _to_response(job)


@router.post("/plan")
async def preview_patch_plan(body: JobCreate, db: AsyncSession = Depends(get_db)):
    """Preview the wave execution plan without creating a job."""
    from app.services.orchestration_service import compute_patch_waves_from_ids

    if not body.host_ids:
        raise HTTPException(status_code=400, detail="No host IDs provided")

    plan = await compute_patch_waves_from_ids(body.host_ids, db)
    return plan


@router.get("", response_model=list[JobResponse])
async def list_all_jobs(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    jobs = await list_jobs(db, status=status)
    return [_to_response(j) for j in jobs]


@router.get("/{job_id}", response_model=JobResponse)
async def get_single_job(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _to_response(job)


@router.get("/{job_id}/events")
async def get_job_events(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(JobEvent)
        .where(JobEvent.job_id == job_id)
        .order_by(JobEvent.timestamp.asc())
    )
    events = result.scalars().all()
    return [
        {
            "id": e.id,
            "host": e.host,
            "task": e.task_name,
            "status": e.status,
            "output": e.output,
            "timestamp": e.timestamp.isoformat(),
        }
        for e in events
    ]


@stream_router.get("/{job_id}/stream")
async def stream_job_events(job_id: str, token: str = Query(...)):
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token")
    except (ExpiredSignatureError, InvalidTokenError):
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    async def event_generator():
        r = aioredis.from_url(settings.REDIS_URL)
        pubsub = r.pubsub()
        await pubsub.subscribe(f"job:{job_id}")
        try:
            while True:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg["type"] == "message":
                    data = msg["data"]
                    if isinstance(data, bytes):
                        data = data.decode()
                    yield f"data: {data}\n\n"
                    parsed = json.loads(data)
                    if parsed.get("type") == "status" and parsed.get("status") in ("completed", "failed"):
                        yield f"data: {json.dumps({'type': 'done'})}\n\n"
                        break
                else:
                    yield f": keepalive\n\n"
                await asyncio.sleep(0.1)
        finally:
            await pubsub.unsubscribe(f"job:{job_id}")
            await pubsub.close()
            await r.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
