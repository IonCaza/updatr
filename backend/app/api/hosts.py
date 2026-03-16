from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.host import HostCreate, HostUpdate, HostResponse, ConnectivityResult
from app.services.host_service import create_host, get_host, list_hosts, update_host, delete_host, get_host_tree
from app.api.deps import get_current_user


class TagPatch(BaseModel):
    add: list[str] = []
    remove: list[str] = []

router = APIRouter(prefix="/hosts", tags=["hosts"], dependencies=[Depends(get_current_user)])


def _to_response(h) -> HostResponse:
    return HostResponse(
        id=h.id,
        display_name=h.display_name,
        hostname=h.hostname,
        os_type=h.os_type,
        ssh_port=h.ssh_port,
        winrm_port=h.winrm_port,
        winrm_use_ssl=h.winrm_use_ssl,
        site=h.site_rel.name if h.site_rel else h.site or "default",
        site_id=h.site_id,
        site_locked=h.site_locked or False,
        is_self=h.is_self or ("worker" in (h.roles or [])),
        parent_id=h.parent_id,
        roles=h.roles or [],
        worker_override=h.worker_override,
        tags=h.tags or [],
        credential_id=h.credential_id,
        is_active=h.is_active,
        created_at=h.created_at.isoformat(),
        updated_at=h.updated_at.isoformat(),
    )


@router.get("", response_model=list[HostResponse])
async def list_all_hosts(
    is_active: bool | None = None,
    tag: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    hosts = await list_hosts(db, is_active=is_active, tag=tag)
    return [_to_response(h) for h in hosts]


@router.post("", response_model=HostResponse, status_code=201)
async def create_new_host(body: HostCreate, db: AsyncSession = Depends(get_db)):
    roles = list(body.roles) if body.roles else []
    if body.is_self and "worker" not in roles:
        roles.append("worker")

    host = await create_host(
        db,
        display_name=body.display_name,
        hostname=body.hostname,
        os_type=body.os_type,
        ssh_port=body.ssh_port,
        winrm_port=body.winrm_port,
        winrm_use_ssl=body.winrm_use_ssl,
        site=body.site,
        site_id=body.site_id,
        site_locked=body.site_locked,
        is_self=body.is_self,
        parent_id=body.parent_id,
        roles=roles,
        worker_override=body.worker_override,
        tags=body.tags,
        credential_id=body.credential_id,
    )
    return _to_response(host)


@router.get("/tree")
async def get_hosts_tree(db: AsyncSession = Depends(get_db)):
    return await get_host_tree(db)


@router.get("/{host_id}", response_model=HostResponse)
async def get_single_host(host_id: str, db: AsyncSession = Depends(get_db)):
    host = await get_host(db, host_id)
    if not host:
        raise HTTPException(status_code=404, detail="Host not found")
    return _to_response(host)


@router.put("/{host_id}", response_model=HostResponse)
async def update_existing_host(
    host_id: str, body: HostUpdate, db: AsyncSession = Depends(get_db)
):
    updates = body.model_dump(exclude_unset=True)
    host = await update_host(db, host_id, **updates)
    if not host:
        raise HTTPException(status_code=404, detail="Host not found")
    return _to_response(host)


@router.delete("/{host_id}", status_code=204)
async def delete_existing_host(host_id: str, db: AsyncSession = Depends(get_db)):
    deleted = await delete_host(db, host_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Host not found")


@router.patch("/{host_id}/tags", response_model=HostResponse)
async def patch_tags(host_id: str, body: TagPatch, db: AsyncSession = Depends(get_db)):
    host = await get_host(db, host_id)
    if not host:
        raise HTTPException(status_code=404, detail="Host not found")
    current = set(host.tags or [])
    current.update(body.add)
    current -= set(body.remove)
    updated = await update_host(db, host_id, tags=sorted(current))
    return _to_response(updated)


@router.post("/{host_id}/test", response_model=ConnectivityResult)
async def test_connectivity(host_id: str, db: AsyncSession = Depends(get_db)):
    host = await get_host(db, host_id)
    if not host:
        raise HTTPException(status_code=404, detail="Host not found")
    import asyncio
    import time
    try:
        start = time.monotonic()
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(
                host.hostname,
                host.ssh_port if host.os_type != "windows" else host.winrm_port,
            ),
            timeout=5.0,
        )
        latency = (time.monotonic() - start) * 1000
        writer.close()
        await writer.wait_closed()
        return ConnectivityResult(success=True, latency_ms=round(latency, 2))
    except Exception as e:
        return ConnectivityResult(success=False, error=str(e))
