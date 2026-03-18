from collections import defaultdict

from sqlalchemy import select

from app.database import SyncSession
from app.models.compliance import ComplianceScan
from app.models.credential import Credential
from app.models.host import Host
from app.services.ansible_service import (
    build_inventory,
    cleanup_temp_key_files,
    parse_events,
    run_playbook,
)
from app.services.queue_service import queue_for_host, collect_site_queues
from app.tasks.celery_app import celery_app


def _load_hosts(host_ids: list[str] | None = None):
    with SyncSession() as db:
        if host_ids:
            hosts = list(db.execute(select(Host).where(Host.id.in_(host_ids))).scalars().all())
        else:
            hosts = list(db.execute(select(Host).where(Host.is_active == True)).scalars().all())
        cred_ids = {h.credential_id for h in hosts}
        creds = {c.id: c for c in db.execute(select(Credential).where(Credential.id.in_(cred_ids))).scalars().all()}
    return hosts, creds


def _save_scan(host_id: str, is_compliant: bool, is_reachable: bool,
               reboot_required: bool, pending_updates: list | None = None,
               worker_queue: str | None = None, raw_log: list | None = None):
    with SyncSession() as db:
        scan = ComplianceScan(
            host_id=host_id,
            is_compliant=is_compliant,
            is_reachable=is_reachable,
            reboot_required=reboot_required,
            pending_updates=pending_updates or [],
            worker_queue=worker_queue,
            raw_log=raw_log or [],
        )
        db.add(scan)
        db.commit()


@celery_app.task(name="compliance_scan", bind=True)
def compliance_scan(self, host_ids: list[str] | None = None):
    delivery = getattr(self.request, "delivery_info", None) or {}
    worker_queue = delivery.get("routing_key") or delivery.get("exchange") or None

    hosts, creds = _load_hosts(host_ids)

    if not hosts:
        return {"status": "no_hosts"}

    inventory = build_inventory(hosts, creds)

    playbook_map = {
        "linux": "compliance_linux.yml",
        "windows": "compliance_windows.yml",
        "truenas": "compliance_truenas.yml",
        "proxmox": "compliance_proxmox.yml",
    }
    hosts_by_type: dict[str, list] = {}
    for h in hosts:
        hosts_by_type.setdefault(h.os_type, []).append(h)

    host_name_to_id = {h.display_name: h.id for h in hosts}
    all_events = []

    for os_type, playbook in playbook_map.items():
        if os_type in hosts_by_type:
            result = run_playbook(playbook, inventory)
            all_events.extend(parse_events(result))

    host_compliance: dict[str, dict] = {}
    host_events: dict[str, list] = defaultdict(list)

    for event in all_events:
        host_name = event["host"]
        host_id = host_name_to_id.get(host_name)
        if not host_id:
            continue

        if host_id not in host_compliance:
            host_compliance[host_id] = {
                "is_reachable": True,
                "compliance_result": {},
            }

        if event["status"] == "unreachable":
            host_compliance[host_id]["is_reachable"] = False

        compliance = event.get("result", {}).get("ansible_facts", {}).get("compliance_result")
        if compliance:
            host_compliance[host_id]["compliance_result"] = compliance

        result = event.get("result", {})
        log_entry: dict = {
            "task": event["task"],
            "status": event["status"],
            "output": {},
        }
        for key in ("stdout", "stderr", "msg"):
            val = result.get(key, "")
            if val:
                log_entry["output"][key] = str(val)[:2000]
        host_events[host_id].append(log_entry)

    scanned = set()
    for host_id, info in host_compliance.items():
        scanned.add(host_id)
        compliance = info["compliance_result"]
        events_log = host_events.get(host_id, [])

        if not compliance:
            _save_scan(
                host_id=host_id,
                is_compliant=False,
                is_reachable=info["is_reachable"],
                reboot_required=False,
                pending_updates=[],
                worker_queue=worker_queue,
                raw_log=events_log,
            )
            continue

        updates_list = compliance.get("pending_updates", [])

        _save_scan(
            host_id=host_id,
            is_compliant=len(updates_list) == 0,
            is_reachable=info["is_reachable"],
            reboot_required=bool(compliance.get("reboot_required", False)),
            pending_updates=updates_list,
            worker_queue=worker_queue,
            raw_log=events_log,
        )

    unreachable_hosts = set(host_name_to_id.values()) - scanned
    for hid in unreachable_hosts:
        _save_scan(
            host_id=hid,
            is_compliant=False,
            is_reachable=False,
            reboot_required=False,
            worker_queue=worker_queue,
            raw_log=[{"task": "connect", "status": "unreachable", "output": {}}],
        )

    cleanup_temp_key_files([h.id for h in hosts])
    return {"scanned": len(scanned), "unreachable": len(unreachable_hosts)}


@celery_app.task(name="compliance_fanout")
def compliance_fanout():
    with SyncSession() as db:
        hosts = list(
            db.execute(select(Host).where(Host.is_active == True)).scalars().all()
        )

    if not hosts:
        return {"status": "no_hosts"}

    all_sites = collect_site_queues(hosts)
    hosts_by_queue: dict[str, list[str]] = defaultdict(list)
    for h in hosts:
        queue = queue_for_host(h, all_sites)
        hosts_by_queue[queue].append(h.id)

    for queue, queue_host_ids in hosts_by_queue.items():
        compliance_scan.apply_async(args=[queue_host_ids], queue=queue)

    return {"dispatched": len(hosts_by_queue)}
