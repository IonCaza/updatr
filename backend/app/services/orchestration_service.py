"""Wave-based patch orchestration engine.

Uses topological ordering (Kahn's algorithm) to compute "waves" -- groups
of hosts that can be patched concurrently.  Within each wave, hosts at the
same hierarchy level are safe to patch in parallel.

Ordering principle:  **leaves first, roots last, control-plane deferred**.
This guarantees a child VM is patched (and rebooted) before its parent
hypervisor.  The control-plane host is placed in the very last wave so
it stays available as long as possible.
"""

from __future__ import annotations

from collections import defaultdict, deque
from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.host import Host


class WaveHost(TypedDict):
    id: str
    display_name: str
    hostname: str
    os_type: str
    parent_id: str | None
    roles: list[str]
    site: str
    site_id: str | None


class Wave(TypedDict):
    index: int
    hosts: list[WaveHost]
    label: str


class WavePlan(TypedDict):
    waves: list[Wave]
    warnings: list[str]


def _host_to_wave_host(h: Host) -> WaveHost:
    return WaveHost(
        id=h.id,
        display_name=h.display_name,
        hostname=h.hostname,
        os_type=h.os_type,
        parent_id=h.parent_id,
        roles=h.roles or [],
        site=h.site_rel.name if h.site_rel else h.site or "default",
        site_id=h.site_id,
    )


def compute_patch_waves(
    target_hosts: list[Host],
    all_hosts: list[Host] | None = None,
) -> WavePlan:
    """Compute ordered waves for patching *target_hosts*.

    Parameters
    ----------
    target_hosts : list[Host]
        The hosts the user selected to patch.
    all_hosts : list[Host] | None
        Full host inventory (for hierarchy context).  Falls back to
        *target_hosts* if not provided.
    """
    if all_hosts is None:
        all_hosts = target_hosts

    target_ids = {h.id for h in target_hosts}
    host_map = {h.id: h for h in all_hosts}
    target_map = {h.id: h for h in target_hosts}

    warnings: list[str] = []

    # Build adjacency: parent -> children (only within target set)
    children_of: dict[str | None, list[str]] = defaultdict(list)
    # in_degree counts how many *target* ancestors a target host has
    in_degree: dict[str, int] = {hid: 0 for hid in target_ids}

    for hid in target_ids:
        h = target_map[hid]
        pid = h.parent_id
        if pid and pid in target_ids:
            children_of[pid].append(hid)
            in_degree[hid] += 1

    # Check for ancestor-descendant chains deeper than direct parent
    for hid in target_ids:
        ancestor = target_map[hid].parent_id
        while ancestor and ancestor not in target_ids:
            anc_host = host_map.get(ancestor)
            if not anc_host:
                break
            ancestor = anc_host.parent_id
        if ancestor and ancestor in target_ids and ancestor != target_map[hid].parent_id:
            warnings.append(
                f"Host {target_map[hid].display_name} has indirect ancestor "
                f"{target_map[ancestor].display_name} in the target set -- "
                f"ensure intermediate hosts are handled."
            )

    # Kahn's algorithm -- leaves (in_degree==0) come first
    queue: deque[str] = deque()
    for hid, deg in in_degree.items():
        if deg == 0:
            queue.append(hid)

    waves_raw: list[list[str]] = []
    visited: set[str] = set()

    while queue:
        wave_ids: list[str] = list(queue)
        queue.clear()
        waves_raw.append(wave_ids)
        for hid in wave_ids:
            visited.add(hid)
            for child in children_of.get(hid, []):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

    # Detect cycle (shouldn't happen with validated data, but just in case)
    if len(visited) < len(target_ids):
        missed = target_ids - visited
        warnings.append(
            f"Cycle detected in host hierarchy involving: "
            f"{', '.join(target_map[m].display_name for m in missed)}"
        )
        waves_raw.append(list(missed))

    # Move control-plane hosts to the very last wave
    cp_ids: set[str] = set()
    for hid in target_ids:
        h = target_map[hid]
        if "control_plane" in (h.roles or []):
            cp_ids.add(hid)

    if cp_ids:
        new_waves: list[list[str]] = []
        deferred: list[str] = []
        for wave in waves_raw:
            regular = [hid for hid in wave if hid not in cp_ids]
            deferred.extend(hid for hid in wave if hid in cp_ids)
            if regular:
                new_waves.append(regular)
        if deferred:
            new_waves.append(deferred)
            warnings.append(
                "Control-plane host(s) deferred to final wave: "
                + ", ".join(target_map[d].display_name for d in deferred)
            )
        waves_raw = new_waves

    # Build final plan
    waves: list[Wave] = []
    for i, wave_ids in enumerate(waves_raw):
        has_cp = any(hid in cp_ids for hid in wave_ids)
        label = f"Wave {i + 1}"
        if has_cp:
            label += " (control plane)"
        elif i == 0 and len(waves_raw) > 1:
            label += " (leaves)"
        elif i == len(waves_raw) - 1 and not has_cp:
            label += " (roots)"

        waves.append(
            Wave(
                index=i,
                hosts=[_host_to_wave_host(target_map[hid]) for hid in wave_ids],
                label=label,
            )
        )

    return WavePlan(waves=waves, warnings=warnings)


class BlastRadiusEntry(TypedDict):
    host_id: str
    display_name: str
    hostname: str
    reason: str


class BlastRadius(TypedDict):
    affected: list[BlastRadiusEntry]
    summary: str


def compute_blast_radius(
    target_hosts: list[Host],
    all_hosts: list[Host],
) -> BlastRadius:
    """Identify non-target hosts that will experience downtime.

    When a parent host is patched (and potentially rebooted), all its
    children will go offline.  This function reports child hosts that
    are *not* in the target set but will still be affected.
    """
    target_ids = {h.id for h in target_hosts}
    host_map = {h.id: h for h in all_hosts}

    children_of: dict[str, list[Host]] = defaultdict(list)
    for h in all_hosts:
        if h.parent_id:
            children_of[h.parent_id].append(h)

    affected: list[BlastRadiusEntry] = []

    def _collect_non_target_descendants(parent_id: str, reason: str):
        for child in children_of.get(parent_id, []):
            if child.id not in target_ids:
                affected.append(
                    BlastRadiusEntry(
                        host_id=child.id,
                        display_name=child.display_name,
                        hostname=child.hostname,
                        reason=reason,
                    )
                )
            _collect_non_target_descendants(child.id, reason)

    for h in target_hosts:
        _collect_non_target_descendants(
            h.id,
            f"Child of target host {h.display_name} -- will go offline during reboot",
        )

    # Deduplicate by host_id
    seen: set[str] = set()
    unique: list[BlastRadiusEntry] = []
    for entry in affected:
        if entry["host_id"] not in seen:
            seen.add(entry["host_id"])
            unique.append(entry)

    summary = (
        f"{len(unique)} non-target host(s) will experience downtime"
        if unique
        else "No collateral downtime expected"
    )
    return BlastRadius(affected=unique, summary=summary)


async def compute_patch_waves_from_ids(
    host_ids: list[str], db: AsyncSession
) -> dict:
    """Load hosts by ID and compute waves + blast radius."""
    result = await db.execute(select(Host).where(Host.id.in_(host_ids)))
    target_hosts = list(result.scalars().all())

    all_result = await db.execute(select(Host))
    all_hosts = list(all_result.scalars().all())

    plan = compute_patch_waves(target_hosts, all_hosts)
    blast = compute_blast_radius(target_hosts, all_hosts)

    return {**plan, "blast_radius": blast}
