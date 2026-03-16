from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.deployment import RegistryConfig, ImageBuild, WorkerDeployment
from app.models.host import Host
from app.schemas.deployment import (
    ConnectivityTestRequest,
    RegistryConfigCreate,
    RegistryConfigUpdate,
    RegistryConfigResponse,
    RegistryTestRequest,
    RegistryTestResponse,
    BuildRequest,
    BuildResponse,
    DeployRequest,
    DeploymentResponse,
    DeploymentStatusItem,
    DeploymentOverview,
)
from app.services import registry_service
from app.services.credential_service import encrypt
from app.services.queue_service import queue_for_deployment

router = APIRouter(
    prefix="/deployment",
    tags=["deployment"],
    dependencies=[Depends(get_current_user)],
)


def _registry_response(r: RegistryConfig) -> dict:
    return {
        "id": r.id,
        "name": r.name,
        "url": r.url,
        "project": r.project,
        "username": r.username,
        "build_host_id": r.build_host_id,
        "repo_path": r.repo_path,
        "external_database_url": r.external_database_url,
        "external_redis_url": r.external_redis_url,
        "is_active": r.is_active,
        "created_at": r.created_at.isoformat() if r.created_at else "",
        "updated_at": r.updated_at.isoformat() if r.updated_at else "",
    }


def _build_response(b: ImageBuild) -> dict:
    return {
        "id": b.id,
        "registry_id": b.registry_id,
        "image_tag": b.image_tag,
        "git_ref": b.git_ref,
        "status": b.status,
        "build_log": b.build_log,
        "error": b.error,
        "started_at": b.started_at.isoformat() if b.started_at else None,
        "completed_at": b.completed_at.isoformat() if b.completed_at else None,
        "created_at": b.created_at.isoformat() if b.created_at else "",
    }


def _deployment_response(d: WorkerDeployment) -> dict:
    return {
        "id": d.id,
        "host_id": d.host_id,
        "registry_id": d.registry_id,
        "image_tag": d.image_tag,
        "status": d.status,
        "worker_site": d.worker_site,
        "env_snapshot": d.env_snapshot,
        "error": d.error,
        "deployed_at": d.deployed_at.isoformat() if d.deployed_at else None,
        "last_health_check": d.last_health_check.isoformat() if d.last_health_check else None,
        "created_at": d.created_at.isoformat() if d.created_at else "",
    }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


@router.get("/registry")
async def get_registry(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(RegistryConfig).where(RegistryConfig.is_active == True).limit(1)  # noqa: E712
    )
    registry = result.scalar_one_or_none()
    if not registry:
        raise HTTPException(status_code=404, detail="No registry configured")
    return _registry_response(registry)


@router.post("/registry", status_code=201)
async def create_or_update_registry(
    body: RegistryConfigCreate, db: AsyncSession = Depends(get_db)
):
    host = await db.get(Host, body.build_host_id)
    if not host:
        raise HTTPException(status_code=400, detail="Build host not found")
    if "docker_host" not in (host.roles or []):
        raise HTTPException(
            status_code=400,
            detail="Build host must have the 'docker_host' role",
        )

    result = await db.execute(
        select(RegistryConfig).where(RegistryConfig.name == "primary")
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.url = body.url
        existing.project = body.project
        existing.username = body.username
        if body.password and body.password not in ("", "unchanged"):
            existing.encrypted_password = encrypt(body.password)
        existing.build_host_id = body.build_host_id
        existing.repo_path = body.repo_path
        existing.external_database_url = body.external_database_url
        existing.external_redis_url = body.external_redis_url
        existing.is_active = True
        await db.commit()
        await db.refresh(existing)
        return _registry_response(existing)

    if not body.password:
        raise HTTPException(status_code=400, detail="Password is required for new configuration")

    registry = RegistryConfig(
        name="primary",
        url=body.url,
        project=body.project,
        username=body.username,
        encrypted_password=encrypt(body.password),
        build_host_id=body.build_host_id,
        repo_path=body.repo_path,
        external_database_url=body.external_database_url,
        external_redis_url=body.external_redis_url,
    )
    db.add(registry)
    await db.commit()
    await db.refresh(registry)
    return _registry_response(registry)


@router.post("/registry/test")
async def test_registry(body: RegistryTestRequest, db: AsyncSession = Depends(get_db)):
    password = body.password
    if not password:
        reg_result = await db.execute(
            select(RegistryConfig).where(RegistryConfig.is_active == True).limit(1)  # noqa: E712
        )
        existing = reg_result.scalar_one_or_none()
        if existing:
            from app.services.credential_service import decrypt
            password = decrypt(existing.encrypted_password)
        else:
            return {"success": False, "message": "Password is required for first-time test"}
    result = await registry_service.test_connection(body.url, body.username, password)
    return result


@router.post("/test-database")
async def test_database(body: ConnectivityTestRequest):
    import asyncpg
    from urllib.parse import urlparse, parse_qs

    try:
        raw = body.url.replace("postgresql+asyncpg://", "postgresql://")
        parsed = urlparse(raw)
        conn = await asyncpg.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            user=parsed.username or "updatr",
            password=parsed.password or "",
            database=parsed.path.lstrip("/") or "updatr",
            timeout=10,
        )
        version = await conn.fetchval("SELECT version()")
        await conn.close()
        short_ver = version.split(",")[0] if version else "connected"
        return {"success": True, "message": short_ver}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.post("/test-redis")
async def test_redis(body: ConnectivityTestRequest):
    import redis.asyncio as aioredis
    from urllib.parse import urlparse

    try:
        parsed = urlparse(body.url)
        r = aioredis.Redis(
            host=parsed.hostname or "localhost",
            port=parsed.port or 6379,
            password=parsed.password or None,
            db=int(parsed.path.lstrip("/") or "0"),
            socket_connect_timeout=10,
        )
        info = await r.info("server")
        await r.aclose()
        version = info.get("redis_version", "connected")
        return {"success": True, "message": f"Redis {version}"}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.delete("/registry", status_code=204)
async def delete_registry(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(RegistryConfig).where(RegistryConfig.name == "primary")
    )
    registry = result.scalar_one_or_none()
    if not registry:
        raise HTTPException(status_code=404, detail="No registry configured")
    registry.is_active = False
    await db.commit()


# ---------------------------------------------------------------------------
# Builds
# ---------------------------------------------------------------------------


async def _get_active_registry(db: AsyncSession) -> RegistryConfig:
    result = await db.execute(
        select(RegistryConfig).where(RegistryConfig.is_active == True).limit(1)  # noqa: E712
    )
    registry = result.scalar_one_or_none()
    if not registry:
        raise HTTPException(status_code=400, detail="No registry configured. Set up a registry first.")
    return registry


@router.post("/builds", status_code=201)
async def trigger_build(body: BuildRequest, db: AsyncSession = Depends(get_db)):
    registry = await _get_active_registry(db)
    queue = await queue_for_deployment(db)

    build = ImageBuild(
        registry_id=registry.id,
        image_tag=body.image_tag,
        git_ref=body.git_ref,
        status="pending",
    )
    db.add(build)
    await db.commit()
    await db.refresh(build)

    from app.tasks.deployment_task import build_worker_image
    build_worker_image.apply_async(args=[build.id], queue=queue)

    return _build_response(build)


@router.get("/builds")
async def list_builds(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ImageBuild).order_by(ImageBuild.created_at.desc()).limit(50)
    )
    builds = result.scalars().all()
    return [_build_response(b) for b in builds]


@router.get("/builds/{build_id}")
async def get_build(build_id: str, db: AsyncSession = Depends(get_db)):
    build = await db.get(ImageBuild, build_id)
    if not build:
        raise HTTPException(status_code=404, detail="Build not found")
    return _build_response(build)


# ---------------------------------------------------------------------------
# Deployments
# ---------------------------------------------------------------------------


@router.post("/deploy", status_code=201)
async def deploy_workers(body: DeployRequest, db: AsyncSession = Depends(get_db)):
    registry = await _get_active_registry(db)
    queue = await queue_for_deployment(db)

    result = await db.execute(
        select(Host).where(Host.id.in_(body.host_ids))
    )
    hosts = list(result.scalars().all())

    if len(hosts) != len(body.host_ids):
        found_ids = {h.id for h in hosts}
        missing = [hid for hid in body.host_ids if hid not in found_ids]
        raise HTTPException(status_code=400, detail=f"Hosts not found: {missing}")

    for host in hosts:
        if "docker_host" not in (host.roles or []):
            raise HTTPException(
                status_code=400,
                detail=f"Host '{host.display_name}' does not have the 'docker_host' role",
            )

    deployments = []
    for host in hosts:
        site_name = host.site
        if host.site_rel:
            site_name = host.site_rel.name

        if "worker" not in (host.roles or []):
            roles = list(host.roles or [])
            roles.append("worker")
            host.roles = roles

        deployment = WorkerDeployment(
            host_id=host.id,
            registry_id=registry.id,
            image_tag=body.image_tag,
            status="pending",
            worker_site=site_name,
        )
        db.add(deployment)
        deployments.append(deployment)

    await db.commit()
    for d in deployments:
        await db.refresh(d)

    from app.tasks.deployment_task import deploy_worker_to_host
    for d in deployments:
        deploy_worker_to_host.apply_async(args=[d.id], queue=queue)

    return [_deployment_response(d) for d in deployments]


@router.get("/deployments")
async def list_deployments(db: AsyncSession = Depends(get_db)):
    subquery = (
        select(
            WorkerDeployment.host_id,
            WorkerDeployment.id,
            WorkerDeployment.created_at,
        )
        .distinct(WorkerDeployment.host_id)
        .order_by(WorkerDeployment.host_id, WorkerDeployment.created_at.desc())
        .subquery()
    )

    result = await db.execute(
        select(WorkerDeployment)
        .join(subquery, WorkerDeployment.id == subquery.c.id)
        .order_by(WorkerDeployment.created_at.desc())
    )
    deployments = result.scalars().all()
    return [_deployment_response(d) for d in deployments]


@router.post("/deployments/{deployment_id}/stop")
async def stop_deployment(deployment_id: str, db: AsyncSession = Depends(get_db)):
    deployment = await db.get(WorkerDeployment, deployment_id)
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")

    queue = await queue_for_deployment(db)

    from app.tasks.deployment_task import stop_deployed_worker
    stop_deployed_worker.apply_async(args=[deployment_id], queue=queue)

    return {"status": "stopping", "deployment_id": deployment_id}


@router.post("/deployments/{deployment_id}/remove")
async def remove_deployment(deployment_id: str, db: AsyncSession = Depends(get_db)):
    deployment = await db.get(WorkerDeployment, deployment_id)
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")

    host = await db.get(Host, deployment.host_id)
    if host and host.is_self:
        raise HTTPException(
            status_code=400,
            detail="Cannot remove the control plane worker. Use docker compose on the host directly.",
        )

    queue = await queue_for_deployment(db)

    from app.tasks.deployment_task import remove_deployed_worker
    remove_deployed_worker.apply_async(args=[deployment_id], queue=queue)

    return {"status": "removing", "deployment_id": deployment_id}


@router.post("/deployments/{deployment_id}/restart")
async def restart_deployment(deployment_id: str, db: AsyncSession = Depends(get_db)):
    deployment = await db.get(WorkerDeployment, deployment_id)
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")

    queue = await queue_for_deployment(db)

    from app.tasks.deployment_task import restart_deployed_worker
    restart_deployed_worker.apply_async(args=[deployment_id], queue=queue)

    return {"status": "restarting", "deployment_id": deployment_id}


# ---------------------------------------------------------------------------
# Status / Overview
# ---------------------------------------------------------------------------


@router.get("/status")
async def deployment_status(db: AsyncSession = Depends(get_db)):
    reg_result = await db.execute(
        select(RegistryConfig).where(RegistryConfig.is_active == True).limit(1)  # noqa: E712
    )
    registry = reg_result.scalar_one_or_none()

    latest_build = None
    if registry:
        build_result = await db.execute(
            select(ImageBuild)
            .where(ImageBuild.registry_id == registry.id)
            .order_by(ImageBuild.created_at.desc())
            .limit(1)
        )
        build = build_result.scalar_one_or_none()
        if build:
            latest_build = _build_response(build)

    docker_hosts_result = await db.execute(select(Host).where(Host.is_active == True))  # noqa: E712
    docker_hosts = [
        h for h in docker_hosts_result.scalars().all()
        if "docker_host" in (h.roles or [])
    ]

    live_queues: set[str] = set()
    try:
        from celery import current_app as celery_app
        inspector = celery_app.control.inspect(timeout=3.0)
        active_queues = inspector.active_queues() or {}
        for queues in active_queues.values():
            for q in queues:
                live_queues.add(q.get("name", ""))
    except Exception:
        pass

    deployment_items = []
    for host in docker_hosts:
        dep_result = await db.execute(
            select(WorkerDeployment)
            .where(WorkerDeployment.host_id == host.id)
            .order_by(WorkerDeployment.created_at.desc())
            .limit(1)
        )
        dep = dep_result.scalar_one_or_none()

        site_name = host.site
        if host.site_rel:
            site_name = host.site_rel.name

        has_live_worker = site_name in live_queues

        if dep:
            status = dep.status
            worker_online = dep.status == "running" or has_live_worker
        elif has_live_worker:
            status = "running (compose)"
            worker_online = True
        else:
            status = "not_deployed"
            worker_online = False

        deployment_items.append({
            "deployment_id": dep.id if dep else None,
            "host_id": host.id,
            "hostname": host.hostname,
            "display_name": host.display_name,
            "site": site_name,
            "current_tag": dep.image_tag if dep else None,
            "status": status,
            "worker_site": site_name,
            "deployed_at": dep.deployed_at.isoformat() if dep and dep.deployed_at else None,
            "last_health_check": dep.last_health_check.isoformat() if dep and dep.last_health_check else None,
            "worker_online": worker_online,
        })

    return {
        "registry_configured": registry is not None,
        "registry": _registry_response(registry) if registry else None,
        "latest_build": latest_build,
        "deployments": deployment_items,
    }


@router.get("/docker-hosts")
async def list_docker_hosts(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Host).where(Host.is_active == True)  # noqa: E712
    )
    hosts = [
        h for h in result.scalars().all()
        if "docker_host" in (h.roles or [])
    ]
    return [
        {
            "id": h.id,
            "display_name": h.display_name,
            "hostname": h.hostname,
            "site": h.site_rel.name if h.site_rel else h.site,
            "roles": h.roles or [],
        }
        for h in hosts
    ]


@router.get("/tags")
async def list_registry_tags(db: AsyncSession = Depends(get_db)):
    registry = await _get_active_registry(db)
    try:
        tags = await registry_service.list_tags(registry)
        return tags
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch tags from registry: {e}")
