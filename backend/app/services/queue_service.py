"""Centralized Celery queue routing.

Every task dispatch in the application resolves its target queue through
one of the public functions below.  No caller should hardcode queue names
or implement its own routing logic.

Public routing functions
------------------------
queue_for_host        -- host-targeted work (patch, compliance)
queue_for_subnet      -- subnet/CIDR-targeted work (discovery scans)
queue_for_control_plane -- control-plane-only work (orchestration, beat)
queue_for_deployment  -- deployment operations (build, deploy, stop, …)

Utility
-------
collect_site_queues   -- unique site queue names from a host list
get_active_queues     -- queues with at least one active Celery consumer

Constant
--------
FALLBACK_QUEUE        -- last-resort queue, must match the control plane's
                         site name so tasks always land on a live consumer
"""

from __future__ import annotations

import ipaddress
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.host import Host

logger = logging.getLogger(__name__)


# ── Fallback ──────────────────────────────────────────────────────────
# Must match the site name of the host running the control-plane worker.
# Used when no better queue can be determined.
FALLBACK_QUEUE = "cm"


# ── Private helpers ───────────────────────────────────────────────────

def _ensure_consumed(queue: str, active_queues: set[str] | None) -> str:
    """Return *queue* if it has a consumer, otherwise FALLBACK_QUEUE."""
    if active_queues is None:
        return queue
    if queue in active_queues:
        return queue
    logger.info(
        "Queue %r has no active consumer — rerouting to %s",
        queue, FALLBACK_QUEUE,
    )
    return FALLBACK_QUEUE


def _site_queue(host: Host) -> str:
    """Resolve the queue name for a host from its Site relationship.

    Falls back to the legacy ``host.site`` string field, then to
    FALLBACK_QUEUE if neither is set.
    """
    if host.site_rel:
        return host.site_rel.name
    return host.site or FALLBACK_QUEUE


def _is_worker_host(host: Host) -> bool:
    """True if this host runs a Celery worker OR any of its descendants do.

    Rebooting a parent (e.g. Proxmox hypervisor) would kill all child
    workers (e.g. Docker VM running the control plane).  Routing work
    for such a host to a *different* site prevents a worker from
    destroying itself mid-task.

    The ``children`` relationship uses ``lazy="selectin"`` so the tree
    is pre-loaded when the Host is queried.
    """
    if host.is_self:
        return True
    if host.roles and "worker" in host.roles:
        return True
    for child in host.children or []:
        if _is_worker_host(child):
            return True
    return False


# ── 1. Host-targeted routing ─────────────────────────────────────────

def queue_for_host(
    host: Host,
    all_sites: set[str] | None = None,
    active_queues: set[str] | None = None,
) -> str:
    """Choose the queue for work that targets a specific host.

    Used by: patch jobs, compliance scans — anything that runs an
    Ansible playbook or SSH command *against* this host.

    Routing priority:
      1. ``worker_override`` — explicit manual override always wins.
      2. Self-protection — if the host (or any descendant) runs a
         Celery worker, route to a *different* site so the worker
         never reboots the machine it lives on.
      3. Host's own site queue — but only if a consumer is active there.
      4. FALLBACK_QUEUE when no consumer exists for the resolved queue.
    """
    override = getattr(host, "worker_override", None)
    if override:
        return override

    own_site = _site_queue(host)

    if _is_worker_host(host):
        if all_sites:
            other_sites = all_sites - {own_site}
            if other_sites:
                resolved = sorted(other_sites)[0]
                return _ensure_consumed(resolved, active_queues)
        return _ensure_consumed(own_site, active_queues)

    return _ensure_consumed(own_site, active_queues)


# ── 2. Subnet / CIDR-targeted routing ────────────────────────────────

async def queue_for_subnet(target_cidr: str, db: AsyncSession) -> str:
    """Choose the queue for work that targets a network range.

    Used by: discovery scans — the scan should execute on the worker
    closest to the target network.

    Routing priority:
      1. Match the first IP of the target CIDR against each site's
         configured subnets.  The site whose subnet contains the IP
         gets the work.
      2. Falls back to the control-plane queue when no subnet matches.
    """
    from app.models.site import Site
    from app.services.site_service import match_site_for_ip

    first_ip = _first_ip_from_target(target_cidr)
    if first_ip:
        result = await db.execute(select(Site))
        sites = list(result.scalars().all())
        site = match_site_for_ip(first_ip, sites)
        if site:
            logger.debug(
                "queue_for_subnet: %s matched site %s", target_cidr, site.name,
            )
            return site.name

    return await queue_for_control_plane(db)


def _first_ip_from_target(target: str) -> str | None:
    """Extract the first usable IP address from a scan target string.

    Handles CIDR notation, single IPs, and space-separated multi-CIDR
    targets (as produced by the discovery target normalizer).
    """
    first_part = target.strip().split()[0] if target.strip() else ""
    if not first_part:
        return None
    try:
        network = ipaddress.ip_network(first_part, strict=False)
        return str(next(network.hosts(), network.network_address))
    except ValueError:
        pass
    try:
        return str(ipaddress.ip_address(first_part))
    except ValueError:
        return None


# ── 3. Control-plane routing ─────────────────────────────────────────

async def queue_for_control_plane(db: AsyncSession) -> str:
    """Choose the queue for coordinator / control-plane-only work.

    Used by: orchestrate_patch_job, celery-beat scheduled tasks.

    Routing priority:
      1. Host with ``is_self=True``.
      2. Host with ``control_plane`` in its roles.
      3. FALLBACK_QUEUE.
    """
    result = await db.execute(
        select(Host).where(Host.is_self == True)  # noqa: E712
    )
    cp_host = result.scalar_one_or_none()
    if cp_host:
        return _site_queue(cp_host)

    result = await db.execute(select(Host))
    for h in result.scalars().all():
        if h.roles and "control_plane" in h.roles:
            return _site_queue(h)

    return FALLBACK_QUEUE


# ── 4. Deployment routing ────────────────────────────────────────────

async def queue_for_deployment(db: AsyncSession) -> str:
    """Choose the queue for deployment operations.

    Used by: build_worker_image, deploy_worker_to_host,
    stop/restart/remove_deployed_worker.

    All deployment tasks are SSH-based operations executed FROM the
    build host TO the target.  They always route through the build
    host's worker queue because:
    - The build host has Docker and SSH access.
    - Target hosts may not have a worker yet (chicken-and-egg).

    Routing priority:
      1. Build host's site queue (from active RegistryConfig).
      2. Control-plane queue (if no registry is configured).
    """
    from app.models.deployment import RegistryConfig

    result = await db.execute(
        select(RegistryConfig)
        .where(RegistryConfig.is_active == True)  # noqa: E712
        .limit(1)
    )
    registry = result.scalar_one_or_none()

    if registry and registry.build_host_id:
        build_host = await db.get(Host, registry.build_host_id)
        if build_host:
            return _site_queue(build_host)

    return await queue_for_control_plane(db)


# ── Utility ──────────────────────────────────────────────────────────

def collect_site_queues(hosts: list[Host]) -> set[str]:
    """Return the set of unique site queue names from a list of hosts."""
    return {_site_queue(h) for h in hosts}


def get_active_queues() -> set[str]:
    """Return queue names that have at least one active Celery consumer.

    Uses the Celery control-plane inspect API with a short timeout.
    Falls back to ``{FALLBACK_QUEUE}`` on any error so dispatchers
    never block on an unreachable broker.

    **Synchronous** — call via ``asyncio.to_thread`` from async code.
    """
    from app.tasks.celery_app import celery_app

    try:
        result = celery_app.control.inspect(timeout=3.0).active_queues()
        if not result:
            return {FALLBACK_QUEUE}
        queues: set[str] = set()
        for worker_queues in result.values():
            for q in worker_queues:
                queues.add(q["name"])
        return queues or {FALLBACK_QUEUE}
    except Exception:
        logger.warning("Failed to inspect active Celery queues — using fallback")
        return {FALLBACK_QUEUE}
