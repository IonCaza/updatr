import ipaddress
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.discovery import DiscoveryScan, DiscoveredHost
from app.models.host import Host
from app.services.queue_service import queue_for_subnet
from app.tasks.discovery_task import discovery_scan

router = APIRouter(
    prefix="/discovery", tags=["discovery"], dependencies=[Depends(get_current_user)]
)

VALID_DEPTHS = {"quick", "standard", "deep"}
RANGE_RE = re.compile(
    r"^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s*-\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})$"
)


def _validate_and_normalize_target(target: str) -> str:
    """Validate target and convert to nmap-compatible format.

    Accepts CIDR, single IP, or full IP range (A.B.C.D-W.X.Y.Z).
    Full IP ranges are converted to space-separated CIDRs since nmap
    does not support arbitrary start-end IP notation.
    """
    target = target.strip()

    try:
        ipaddress.ip_network(target, strict=False)
        return target
    except ValueError:
        pass

    try:
        ipaddress.ip_address(target)
        return target
    except ValueError:
        pass

    match = RANGE_RE.match(target)
    if match:
        try:
            first = ipaddress.IPv4Address(match.group(1))
            last = ipaddress.IPv4Address(match.group(2))
            if first > last:
                first, last = last, first
            cidrs = list(ipaddress.summarize_address_range(first, last))
            return " ".join(str(c) for c in cidrs)
        except (ValueError, TypeError):
            pass

    raise HTTPException(
        status_code=400,
        detail="Target must be a CIDR (192.168.1.0/24), single IP, or range (10.0.0.1-10.0.0.50)",
    )


class ScanRequest(BaseModel):
    target: str = Field(min_length=1, max_length=200)
    depth: str = Field(default="standard")


class HostImportEntry(BaseModel):
    host_id: str
    os_type: str | None = None
    credential_id: str | None = None


class ImportRequest(BaseModel):
    hosts: list[HostImportEntry] = Field(min_length=1)
    default_credential_id: str
    site: str = Field(default="default")


@router.post("/scan", status_code=202)
async def start_scan(body: ScanRequest, db: AsyncSession = Depends(get_db)):
    if body.depth not in VALID_DEPTHS:
        raise HTTPException(status_code=400, detail=f"Depth must be one of: {', '.join(VALID_DEPTHS)}")
    target = _validate_and_normalize_target(body.target)

    scan = DiscoveryScan(target=target, depth=body.depth)
    db.add(scan)
    await db.commit()
    await db.refresh(scan)

    queue = await queue_for_subnet(target, db)
    discovery_scan.apply_async(args=[scan.id], queue=queue)

    return {"scan_id": scan.id, "status": "pending"}


@router.get("/scans")
async def list_scans(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(DiscoveryScan).order_by(DiscoveryScan.started_at.desc()).limit(20)
    )
    scans = result.scalars().all()
    return [
        {
            "id": s.id,
            "target": s.target,
            "depth": s.depth,
            "status": s.status,
            "host_count": s.host_count,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "completed_at": s.completed_at.isoformat() if s.completed_at else None,
            "error": s.error,
        }
        for s in scans
    ]


@router.get("/{scan_id}")
async def get_scan(scan_id: str, db: AsyncSession = Depends(get_db)):
    scan = await db.get(DiscoveryScan, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    result = await db.execute(
        select(DiscoveredHost)
        .where(DiscoveredHost.scan_id == scan_id)
        .order_by(DiscoveredHost.ip_address)
    )
    hosts = result.scalars().all()

    return {
        "id": scan.id,
        "target": scan.target,
        "depth": scan.depth,
        "status": scan.status,
        "host_count": scan.host_count,
        "error": scan.error,
        "started_at": scan.started_at.isoformat() if scan.started_at else None,
        "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
        "hosts": [
            {
                "id": h.id,
                "ip_address": h.ip_address,
                "hostname": h.hostname,
                "os_guess": h.os_guess,
                "os_type": h.os_type,
                "os_confidence": h.os_confidence,
                "open_ports": h.open_ports or [],
                "imported": h.imported,
            }
            for h in hosts
        ],
    }


@router.post("/import")
async def import_hosts(body: ImportRequest, db: AsyncSession = Depends(get_db)):
    from app.services.site_service import auto_assign_site

    host_ids = [h.host_id for h in body.hosts]
    overrides = {h.host_id: h for h in body.hosts}

    result = await db.execute(
        select(DiscoveredHost).where(DiscoveredHost.id.in_(host_ids))
    )
    discovered = list(result.scalars().all())
    if not discovered:
        raise HTTPException(status_code=404, detail="No matching discovered hosts")

    existing = await db.execute(select(Host.hostname))
    existing_hostnames = {row[0] for row in existing.all()}

    imported = []
    skipped = []
    for dh in discovered:
        if dh.imported:
            skipped.append(dh.ip_address)
            continue

        host_address = dh.hostname or dh.ip_address
        if host_address in existing_hostnames:
            skipped.append(host_address)
            dh.imported = True
            continue

        entry = overrides.get(dh.id)
        os_type = (
            (entry.os_type if entry and entry.os_type else None)
            or (dh.os_type if dh.os_type != "unknown" else "linux")
        )
        cred_id = (
            (entry.credential_id if entry and entry.credential_id else None)
            or body.default_credential_id
        )

        detected_site = await auto_assign_site(dh.ip_address, db)
        site_name = detected_site.name if detected_site else body.site
        site_id = detected_site.id if detected_site else None

        host = Host(
            display_name=dh.hostname or dh.ip_address,
            hostname=host_address,
            os_type=os_type,
            credential_id=cred_id,
            site=site_name,
            site_id=site_id,
            ssh_port=22,
            winrm_port=5986,
            winrm_use_ssl=True,
        )
        db.add(host)
        dh.imported = True
        imported.append(dh.ip_address)
        existing_hostnames.add(host_address)

    await db.commit()
    return {
        "imported": len(imported),
        "skipped": len(skipped),
        "imported_hosts": imported,
        "skipped_hosts": skipped,
    }
