"""Orchestrate a multi-wave patch job.

This task coordinates wave execution:
1. Compute waves from the host hierarchy (or use pre-computed plan)
2. Execute each wave sequentially, dispatching patch_hosts for each
3. Wait for wave completion before proceeding to next wave
4. Track wave progress on the Job record (with resilient fallback to SQLite journal)
"""

import logging
import time
from datetime import datetime, timezone

from celery import group
from sqlalchemy import select

from app.database import SyncSession
from app.models.host import Host
from app.models.job import Job
from app.services.orchestration_service import compute_patch_waves
from app.services.orchestration_journal import try_update_db, wait_for_db_recovery, replay_journal
from app.services.queue_service import queue_for_host, collect_site_queues, FALLBACK_QUEUE
from app.tasks.celery_app import celery_app
from app.tasks.patch_task import patch_hosts

logger = logging.getLogger(__name__)


def _wave_has_control_plane(wave_hosts: list[dict]) -> bool:
    return any("control_plane" in (wh.get("roles") or []) for wh in wave_hosts)


def _wait_for_children_online(parent_ids: list[str], timeout: int = 300):
    """After a parent host reboots, poll until its children respond."""
    import asyncio
    import socket

    with SyncSession() as db:
        all_children = []
        for pid in parent_ids:
            children = list(
                db.execute(select(Host).where(Host.parent_id == pid))
                .scalars()
                .all()
            )
            all_children.extend(children)

    if not all_children:
        return

    logger.info("Waiting for %d children to come online after parent reboot", len(all_children))
    start = time.monotonic()
    pending = {c.id: c for c in all_children}

    while pending and (time.monotonic() - start) < timeout:
        for cid in list(pending):
            child = pending[cid]
            port = child.ssh_port if child.os_type != "windows" else child.winrm_port
            try:
                sock = socket.create_connection((child.hostname, port), timeout=3)
                sock.close()
                logger.info("Child %s is back online", child.display_name)
                del pending[cid]
            except (OSError, socket.timeout):
                pass
        if pending:
            time.sleep(5)

    if pending:
        logger.warning(
            "%d children still offline after %ds: %s",
            len(pending), timeout,
            [c.display_name for c in pending.values()],
        )


@celery_app.task(bind=True, name="orchestrate_patch_job")
def orchestrate_patch_job(
    self,
    job_id: str,
    host_ids: list[str],
    extra_vars: dict | None = None,
    wave_plan: dict | None = None,
):
    """Execute a patch job wave-by-wave with resilience."""
    logger.info("orchestrate_patch_job %s: starting for %d hosts", job_id, len(host_ids))

    # Replay any pending journal entries from previous runs
    replay_journal()

    try:
        with SyncSession() as db:
            job = db.execute(select(Job).where(Job.id == job_id)).scalar_one_or_none()
            if not job:
                logger.error("orchestrate_patch_job: job %s not found", job_id)
                return {"error": "job not found"}

            job.status = "running"
            job.started_at = datetime.now(timezone.utc)

            if wave_plan:
                job.wave_plan = wave_plan
            else:
                hosts = list(
                    db.execute(select(Host).where(Host.id.in_(host_ids))).scalars().all()
                )
                all_hosts = list(db.execute(select(Host)).scalars().all())
                plan = compute_patch_waves(hosts, all_hosts)
                wave_plan = plan
                job.wave_plan = plan

            db.commit()
    except Exception:
        logger.exception("orchestrate_patch_job %s: failed to initialize", job_id)
        try_update_db(job_id, None, "failed")
        raise

    waves = wave_plan.get("waves", [])
    if not waves:
        logger.warning("orchestrate_patch_job %s: no waves to execute", job_id)
        try_update_db(job_id, 0, "completed")
        return {"status": "completed", "waves_executed": 0}

    logger.info(
        "orchestrate_patch_job %s: executing %d wave(s)", job_id, len(waves)
    )

    for wave in waves:
        wave_idx = wave["index"]
        wave_hosts = wave["hosts"]
        wave_host_ids = [wh["id"] for wh in wave_hosts]

        logger.info(
            "orchestrate_patch_job %s: wave %d -- %d hosts: %s",
            job_id, wave_idx, len(wave_host_ids),
            [wh["display_name"] for wh in wave_hosts],
        )

        try_update_db(job_id, wave_idx, "running")

        # Load hosts for queue routing
        try:
            with SyncSession() as db:
                hosts = list(
                    db.execute(select(Host).where(Host.id.in_(wave_host_ids)))
                    .scalars()
                    .all()
                )
        except Exception:
            logger.warning("orchestrate_patch_job %s: DB read failed for wave %d, using plan data", job_id, wave_idx)
            hosts = []

        if hosts:
            all_sites = collect_site_queues(hosts)
            hosts_by_queue: dict[str, list[str]] = {}
            for h in hosts:
                queue = queue_for_host(h, all_sites)
                hosts_by_queue.setdefault(queue, []).append(h.id)
        else:
            hosts_by_queue = {FALLBACK_QUEUE: wave_host_ids}

        tasks = []
        for queue, queue_host_ids in hosts_by_queue.items():
            sig = patch_hosts.s(job_id, queue_host_ids, extra_vars or {})
            sig.set(queue=queue)
            tasks.append(sig)

        if tasks:
            result = group(tasks).apply_async()
            while not result.ready():
                time.sleep(2)

            if result.failed():
                logger.error(
                    "orchestrate_patch_job %s: wave %d had failures",
                    job_id, wave_idx,
                )

        logger.info("orchestrate_patch_job %s: wave %d complete", job_id, wave_idx)

        # If this wave contained parent hosts, wait for their children to come back online
        parent_ids_in_wave = [wh["id"] for wh in wave_hosts if wh.get("parent_id") is None or any(
            other_wh.get("parent_id") == wh["id"] for w in waves for other_wh in w["hosts"]
        )]
        if parent_ids_in_wave and wave_idx < len(waves) - 1:
            _wait_for_children_online(wave_host_ids)

        # If next wave has control plane, check DB is available
        if wave_idx < len(waves) - 1 and _wave_has_control_plane(waves[wave_idx + 1]["hosts"]):
            logger.info("orchestrate_patch_job %s: next wave has CP, checking DB", job_id)
            wait_for_db_recovery(max_wait=600)

    try_update_db(job_id, len(waves) - 1, "completed")
    replay_journal()

    logger.info("orchestrate_patch_job %s: all waves complete", job_id)
    return {"status": "completed", "waves_executed": len(waves)}
