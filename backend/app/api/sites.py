from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.site import Site
from app.models.host import Host
from app.schemas.site import SiteCreate, SiteUpdate, SiteResponse
from app.services.site_service import validate_subnets

router = APIRouter(
    prefix="/sites", tags=["sites"], dependencies=[Depends(get_current_user)]
)


def _site_response(site: Site, host_count: int = 0) -> dict:
    return {
        "id": site.id,
        "name": site.name,
        "display_name": site.display_name,
        "description": site.description,
        "subnets": site.subnets or [],
        "is_default": site.is_default,
        "host_count": host_count,
        "created_at": site.created_at.isoformat() if site.created_at else "",
        "updated_at": site.updated_at.isoformat() if site.updated_at else "",
    }


@router.get("")
async def list_sites(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Site, func.count(Host.id).label("host_count"))
        .outerjoin(Host, Host.site_id == Site.id)
        .group_by(Site.id)
        .order_by(Site.name)
    )
    rows = result.all()
    return [_site_response(site, count) for site, count in rows]


@router.post("", status_code=201)
async def create_site(body: SiteCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(Site).where(Site.name == body.name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Site name already exists")

    try:
        subnets = validate_subnets(body.subnets)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if body.is_default:
        await db.execute(
            select(Site).where(Site.is_default == True)  # noqa: E712
        )
        await _clear_default_flag(db)

    site = Site(
        name=body.name,
        display_name=body.display_name,
        description=body.description,
        subnets=subnets,
        is_default=body.is_default,
    )
    db.add(site)
    await db.commit()
    await db.refresh(site)
    return _site_response(site)


@router.get("/{site_id}")
async def get_site(site_id: str, db: AsyncSession = Depends(get_db)):
    site = await db.get(Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    count_result = await db.execute(
        select(func.count(Host.id)).where(Host.site_id == site_id)
    )
    host_count = count_result.scalar() or 0
    return _site_response(site, host_count)


@router.put("/{site_id}")
async def update_site(
    site_id: str, body: SiteUpdate, db: AsyncSession = Depends(get_db)
):
    site = await db.get(Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    if body.name is not None and body.name != site.name:
        dup = await db.execute(select(Site).where(Site.name == body.name))
        if dup.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Site name already exists")
        site.name = body.name

    if body.display_name is not None:
        site.display_name = body.display_name
    if body.description is not None:
        site.description = body.description
    if body.subnets is not None:
        try:
            site.subnets = validate_subnets(body.subnets)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    if body.is_default is not None:
        if body.is_default and not site.is_default:
            await _clear_default_flag(db)
        site.is_default = body.is_default

    await db.commit()
    await db.refresh(site)

    count_result = await db.execute(
        select(func.count(Host.id)).where(Host.site_id == site_id)
    )
    host_count = count_result.scalar() or 0
    return _site_response(site, host_count)


@router.delete("/{site_id}", status_code=204)
async def delete_site(site_id: str, db: AsyncSession = Depends(get_db)):
    site = await db.get(Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    if site.is_default:
        raise HTTPException(
            status_code=400, detail="Cannot delete the default site"
        )

    default = await _get_default(db)
    if default:
        await db.execute(
            select(Host).where(Host.site_id == site_id)
        )
        result = await db.execute(
            select(Host).where(Host.site_id == site_id)
        )
        for host in result.scalars().all():
            host.site_id = default.id
            host.site = default.name
        await db.flush()

    await db.delete(site)
    await db.commit()


@router.post("/{site_id}/detect")
async def rerun_detection(site_id: str, db: AsyncSession = Depends(get_db)):
    """Re-run subnet auto-detection: assign unlocked hosts to this site if their IP matches."""
    site = await db.get(Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    if not site.subnets:
        return {"assigned": 0}

    from app.services.site_service import match_site_for_ip

    result = await db.execute(
        select(Host).where(Host.site_locked == False)  # noqa: E712
    )
    hosts = result.scalars().all()

    all_sites_result = await db.execute(select(Site))
    all_sites = list(all_sites_result.scalars().all())

    assigned = 0
    for host in hosts:
        matched = match_site_for_ip(host.hostname, all_sites)
        if matched and matched.id != host.site_id:
            host.site_id = matched.id
            host.site = matched.name
            assigned += 1

    await db.commit()
    return {"assigned": assigned}


async def _clear_default_flag(db: AsyncSession):
    result = await db.execute(
        select(Site).where(Site.is_default == True)  # noqa: E712
    )
    for s in result.scalars().all():
        s.is_default = False


async def _get_default(db: AsyncSession) -> Site | None:
    result = await db.execute(
        select(Site).where(Site.is_default == True)  # noqa: E712
    )
    return result.scalar_one_or_none()
