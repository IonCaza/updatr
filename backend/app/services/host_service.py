from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.host import Host
from app.services.site_service import auto_assign_site


async def create_host(db: AsyncSession, **kwargs) -> Host:
    if not kwargs.get("site_id"):
        site = await auto_assign_site(kwargs.get("hostname", ""), db)
        if site:
            kwargs["site_id"] = site.id
            if not kwargs.get("site"):
                kwargs["site"] = site.name

    if kwargs.get("parent_id"):
        await _validate_parent(db, None, kwargs["parent_id"])

    host = Host(**kwargs)
    db.add(host)
    await db.commit()
    await db.refresh(host)
    return host


async def get_host(db: AsyncSession, host_id: str) -> Host | None:
    result = await db.execute(select(Host).where(Host.id == host_id))
    return result.scalar_one_or_none()


async def list_hosts(
    db: AsyncSession,
    is_active: bool | None = None,
    tag: str | None = None,
) -> list[Host]:
    stmt = select(Host).order_by(Host.display_name)
    if is_active is not None:
        stmt = stmt.where(Host.is_active == is_active)
    result = await db.execute(stmt)
    hosts = list(result.scalars().all())
    if tag:
        hosts = [h for h in hosts if tag in (h.tags or [])]
    return hosts


async def get_host_tree(db: AsyncSession) -> list[dict]:
    """Return all hosts as a nested tree structure."""
    hosts = await list_hosts(db, is_active=None)
    host_map = {h.id: h for h in hosts}
    children_of: dict[str | None, list[Host]] = {}
    for h in hosts:
        children_of.setdefault(h.parent_id, []).append(h)

    def build_node(host: Host) -> dict:
        return {
            "id": host.id,
            "display_name": host.display_name,
            "hostname": host.hostname,
            "os_type": host.os_type,
            "site": host.site_rel.name if host.site_rel else host.site or "default",
            "site_id": host.site_id,
            "parent_id": host.parent_id,
            "roles": host.roles or [],
            "is_active": host.is_active,
            "children": [
                build_node(c) for c in children_of.get(host.id, [])
            ],
        }

    roots = children_of.get(None, [])
    orphans = [h for h in hosts if h.parent_id and h.parent_id not in host_map]
    return [build_node(h) for h in roots + orphans]


NULLABLE_FIELDS = {"worker_override", "parent_id"}


async def update_host(db: AsyncSession, host_id: str, **kwargs) -> Host | None:
    host = await get_host(db, host_id)
    if not host:
        return None

    if "parent_id" in kwargs and kwargs["parent_id"] is not None:
        await _validate_parent(db, host_id, kwargs["parent_id"])

    for key, val in kwargs.items():
        if val is not None or key in NULLABLE_FIELDS:
            setattr(host, key, val)
    await db.commit()
    await db.refresh(host)
    return host


async def delete_host(db: AsyncSession, host_id: str) -> bool:
    host = await get_host(db, host_id)
    if not host:
        return False
    await db.delete(host)
    await db.commit()
    return True


async def _validate_parent(
    db: AsyncSession, host_id: str | None, parent_id: str
) -> None:
    """Walk up the tree to ensure setting parent_id won't create a cycle."""
    if host_id and parent_id == host_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="A host cannot be its own parent")

    visited: set[str] = set()
    current: str | None = parent_id
    while current:
        if host_id and current == host_id:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=400,
                detail="Setting this parent would create a cycle in the host hierarchy",
            )
        if current in visited:
            break
        visited.add(current)
        ancestor = await get_host(db, current)
        current = ancestor.parent_id if ancestor else None
