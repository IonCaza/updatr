import json
from datetime import datetime, timezone

import redis
from sqlalchemy import select

from app.config import settings
from app.database import SyncSession
from app.models.credential import Credential
from app.models.host import Host
from app.models.job import Job, JobEvent
from app.services.ansible_service import (
    build_inventory,
    cleanup_temp_key_files,
    run_playbook,
)
from app.tasks.celery_app import celery_app

_redis = redis.Redis.from_url(settings.REDIS_URL)

TRACKED_EVENTS = frozenset({
    "runner_on_ok", "runner_on_failed", "runner_on_unreachable",
    "runner_on_skipped", "playbook_on_task_start", "runner_on_start",
})


def _load_hosts_and_creds(host_ids: list[str]):
    with SyncSession() as db:
        hosts = list(db.execute(select(Host).where(Host.id.in_(host_ids))).scalars().all())
        cred_ids = {h.credential_id for h in hosts}
        creds = {c.id: c for c in db.execute(select(Credential).where(Credential.id.in_(cred_ids))).scalars().all()}
    return hosts, creds


def _update_job_status(job_id: str, status: str, results: dict | None = None):
    with SyncSession() as db:
        job = db.execute(select(Job).where(Job.id == job_id)).scalar_one_or_none()
        if not job:
            return
        job.status = status
        if status == "running":
            job.started_at = datetime.now(timezone.utc)
        if status in ("completed", "failed"):
            job.completed_at = datetime.now(timezone.utc)
        if results:
            job.host_results = results
        db.commit()

    _publish(job_id, {"type": "status", "status": status})


def _save_event(job_id: str, host: str, task_name: str, status: str, output: dict):
    with SyncSession() as db:
        event = JobEvent(
            job_id=job_id,
            host=host,
            task_name=task_name,
            status=status,
            output=output,
        )
        db.add(event)
        db.commit()


def _publish(job_id: str, data: dict):
    try:
        _redis.publish(f"job:{job_id}", json.dumps(data, default=str))
    except Exception:
        pass


def _make_event_handler(job_id: str):
    def handler(event: dict):
        event_type = event.get("event", "")
        if event_type not in TRACKED_EVENTS:
            return

        event_data = event.get("event_data", {})
        host = event_data.get("host", "")
        task = event_data.get("task", event_data.get("name", ""))
        status = event_type.replace("runner_on_", "").replace("playbook_on_", "")
        result = event_data.get("res", {})

        stdout = result.get("stdout", "")
        stderr = result.get("stderr", "")
        msg = result.get("msg", "")
        output = {}
        if stdout:
            output["stdout"] = stdout[:2000]
        if stderr:
            output["stderr"] = stderr[:2000]
        if msg:
            output["msg"] = msg[:2000]

        log_entry = {
            "type": "event",
            "event": event_type,
            "host": host,
            "task": task,
            "status": status,
            "output": output,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        _publish(job_id, log_entry)

        if host and event_type in ("runner_on_ok", "runner_on_failed", "runner_on_unreachable"):
            _save_event(job_id, host, task, status, output)

    return handler


@celery_app.task(bind=True, name="patch_hosts")
def patch_hosts(self, job_id: str, host_ids: list[str], extra_vars: dict | None = None):
    _update_job_status(job_id, "running")

    try:
        hosts, creds = _load_hosts_and_creds(host_ids)
        if not hosts:
            _update_job_status(job_id, "failed", {"error": "No hosts found"})
            return

        inventory = build_inventory(hosts, creds)
        handler = _make_event_handler(job_id)

        playbook_map = {
            "linux": "patch_linux.yml",
            "windows": "patch_windows.yml",
            "truenas": "patch_truenas.yml",
            "proxmox": "patch_proxmox.yml",
        }
        hosts_by_type: dict[str, list] = {}
        for h in hosts:
            hosts_by_type.setdefault(h.os_type, []).append(h)

        all_events = []
        vars_dict = extra_vars or {}

        for os_type, playbook in playbook_map.items():
            if os_type in hosts_by_type:
                result = run_playbook(playbook, inventory, vars_dict, event_handler=handler)
                all_events.extend(result.events)

        host_results = {}
        for event in all_events:
            host = event["host"]
            if host not in host_results:
                host_results[host] = {"status": "ok", "events": []}
            host_results[host]["events"].append(event)
            if event["status"] == "failed":
                host_results[host]["status"] = "failed"

        cleanup_temp_key_files([h.id for h in hosts])
        _update_job_status(job_id, "completed", host_results)

    except Exception as exc:
        cleanup_temp_key_files(host_ids)
        _update_job_status(job_id, "failed", {"error": str(exc)})
        raise self.retry(exc=exc, max_retries=1, countdown=30)
