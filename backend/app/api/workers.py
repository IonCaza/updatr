import asyncio

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.worker_alias import WorkerAlias
from app.models.host import Host
from app.tasks.celery_app import celery_app

router = APIRouter(
    prefix="/workers", tags=["workers"], dependencies=[Depends(get_current_user)]
)


class RenameBody(BaseModel):
    friendly_name: str = Field(min_length=1, max_length=200)


async def _get_aliases(db: AsyncSession) -> dict[str, str]:
    result = await db.execute(select(WorkerAlias))
    return {a.worker_name: a.friendly_name for a in result.scalars().all()}


@router.get("")
async def list_workers(db: AsyncSession = Depends(get_db)):
    loop = asyncio.get_event_loop()
    inspector = celery_app.control.inspect(timeout=2.0)

    ping_result, queues_result, active_result, stats_result = await asyncio.gather(
        loop.run_in_executor(None, inspector.ping),
        loop.run_in_executor(None, inspector.active_queues),
        loop.run_in_executor(None, inspector.active),
        loop.run_in_executor(None, inspector.stats),
    )

    aliases = await _get_aliases(db)

    if not ping_result:
        return []

    workers = []
    for name in ping_result:
        worker_queues = [
            q["name"] for q in (queues_result or {}).get(name, [])
        ]
        worker_active = (active_result or {}).get(name, [])
        worker_stats = (stats_result or {}).get(name, {})

        workers.append(
            {
                "name": name,
                "friendly_name": aliases.get(name),
                "status": "online",
                "queues": worker_queues,
                "active_tasks": len(worker_active),
                "uptime_seconds": worker_stats.get("uptime", None),
                "total_tasks": sum(
                    (worker_stats.get("total", {}) or {}).values()
                ),
            }
        )

    return workers


@router.put("/{worker_name}/rename")
async def rename_worker(
    worker_name: str,
    body: RenameBody,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(WorkerAlias).where(WorkerAlias.worker_name == worker_name)
    )
    alias = result.scalar_one_or_none()

    if alias:
        alias.friendly_name = body.friendly_name
    else:
        alias = WorkerAlias(
            worker_name=worker_name, friendly_name=body.friendly_name
        )
        db.add(alias)

    await db.commit()
    await db.refresh(alias)
    return {
        "worker_name": alias.worker_name,
        "friendly_name": alias.friendly_name,
    }


@router.get("/{worker_name}/hosts")
async def worker_hosts(worker_name: str, db: AsyncSession = Depends(get_db)):
    """Return hosts whose site or worker_override routes to this worker's queues."""
    loop = asyncio.get_event_loop()
    inspector = celery_app.control.inspect(timeout=2.0)
    queues_result = await loop.run_in_executor(None, inspector.active_queues)

    worker_queues = set()
    if queues_result and worker_name in queues_result:
        worker_queues = {q["name"] for q in queues_result[worker_name]}

    if not worker_queues:
        return []

    result = await db.execute(
        select(Host).where(Host.is_active == True).order_by(Host.display_name)
    )
    all_hosts = list(result.scalars().all())

    matched = []
    for h in all_hosts:
        site_name = h.site_rel.name if h.site_rel else h.site or "default"
        effective_queue = h.worker_override or site_name
        if effective_queue in worker_queues:
            matched.append(
                {
                    "id": h.id,
                    "display_name": h.display_name,
                    "hostname": h.hostname,
                    "os_type": h.os_type,
                    "site": site_name,
                    "worker_override": h.worker_override,
                }
            )

    return matched
