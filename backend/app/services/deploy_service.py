import logging
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from textwrap import dedent

from celery import current_app as celery_app
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.deployment import RegistryConfig, WorkerDeployment
from app.models.host import Host
from app.services.credential_service import decrypt

logger = logging.getLogger(__name__)

TEMP_KEY_DIR = Path(tempfile.gettempdir()) / "updatr_keys"
REMOTE_WORKER_DIR = "/opt/updatr-worker"


def generate_env_vars(registry: RegistryConfig, host: Host) -> dict:
    db_url = registry.external_database_url or settings.EXTERNAL_DATABASE_URL or settings.DATABASE_URL
    redis_url = registry.external_redis_url or settings.EXTERNAL_REDIS_URL or settings.REDIS_URL

    site_name = host.site
    if host.site_rel:
        site_name = host.site_rel.name

    return {
        "DATABASE_URL": db_url,
        "REDIS_URL": redis_url,
        "ENCRYPTION_KEY": settings.ENCRYPTION_KEY,
        "WORKER_SITE": site_name,
    }


def generate_compose_content(registry: RegistryConfig, image_tag: str, site_name: str) -> str:
    registry_host = registry.url.rstrip("/").split("://", 1)[-1]
    image_ref = f"{registry_host}/{registry.project}/worker:{image_tag}"
    return dedent(f"""\
        services:
          celery-worker:
            image: {image_ref}
            command: >-
              celery -A app.tasks.celery_app worker
              -Q {site_name}
              -l info
              --hostname=worker@{site_name}
            cap_add:
              - NET_RAW
              - NET_ADMIN
            deploy:
              resources:
                limits:
                  memory: 2g
                  pids: 512
            env_file: .env
            restart: unless-stopped
    """)


def generate_env_file_content(env_vars: dict) -> str:
    lines = []
    for key, value in env_vars.items():
        lines.append(f"{key}={value}")
    return "\n".join(lines) + "\n"


def _ssh_args_for_host(host: Host, command: str) -> list[str]:
    credential = host.credential
    args = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "ConnectTimeout=15",
        "-p", str(host.ssh_port),
    ]

    if credential.type == "ssh-key" and credential.encrypted_private_key:
        key_content = decrypt(credential.encrypted_private_key)
        TEMP_KEY_DIR.mkdir(parents=True, exist_ok=True)
        key_path = TEMP_KEY_DIR / f"deploy_{host.id}.pem"
        key_path.write_text(key_content)
        key_path.chmod(0o600)
        args.extend(["-i", str(key_path)])
    elif credential.type == "ssh-password" and credential.encrypted_password:
        password = decrypt(credential.encrypted_password)
        args = ["sshpass", "-p", password, *args]

    args.append(f"{credential.username}@{host.hostname}")
    args.append(command)
    return args


def _scp_content_to_host(host: Host, content: str, remote_path: str):
    credential = host.credential
    args = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "ConnectTimeout=15",
        "-p", str(host.ssh_port),
    ]

    if credential.type == "ssh-key" and credential.encrypted_private_key:
        key_path = TEMP_KEY_DIR / f"deploy_{host.id}.pem"
        if key_path.exists():
            args.extend(["-i", str(key_path)])
    elif credential.type == "ssh-password" and credential.encrypted_password:
        password = decrypt(credential.encrypted_password)
        args = ["sshpass", "-p", password, *args]

    args.append(f"{credential.username}@{host.hostname}")
    args.append(f"cat > {remote_path}")

    proc = subprocess.run(
        args,
        input=content,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Failed to write {remote_path}: {proc.stderr}")


def _run_ssh(host: Host, command: str, timeout: int = 120, sudo: bool = False) -> dict:
    if sudo:
        command = _wrap_sudo(host, command)
    args = _ssh_args_for_host(host, command)
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        output = proc.stdout
        if proc.stderr:
            output += f"\n{proc.stderr}"
        return {"returncode": proc.returncode, "output": output}
    except subprocess.TimeoutExpired:
        return {"returncode": -1, "output": f"Command timed out after {timeout}s"}
    except Exception as e:
        return {"returncode": -1, "output": f"SSH error: {e}"}


def _wrap_sudo(host: Host, command: str) -> str:
    """Wrap a command with sudo, piping the credential password via -S
    for password-based creds. Key-based creds rely on NOPASSWD sudo."""
    credential = host.credential
    if credential.type == "ssh-password" and credential.encrypted_password:
        password = decrypt(credential.encrypted_password)
        safe_pw = password.replace("'", "'\\''")
        return f"echo '{safe_pw}' | sudo -S sh -c '{command}'"
    return f"sudo {command}"


def _cleanup_key(host_id: str):
    path = TEMP_KEY_DIR / f"deploy_{host_id}.pem"
    if path.exists():
        path.unlink()


def deploy_worker(deployment_id: str, db: Session):
    deployment: WorkerDeployment = (
        db.query(WorkerDeployment)
        .filter(WorkerDeployment.id == deployment_id)
        .first()
    )
    if not deployment:
        logger.error("Deployment %s not found", deployment_id)
        return

    host = deployment.host
    registry = deployment.registry

    deployment.status = "deploying"
    db.commit()

    try:
        env_vars = generate_env_vars(registry, host)
        deployment.env_snapshot = {k: v for k, v in env_vars.items() if k != "ENCRYPTION_KEY"}
        db.commit()

        compose_content = generate_compose_content(
            registry, deployment.image_tag, deployment.worker_site
        )
        env_file_content = generate_env_file_content(env_vars)

        ssh_user = host.credential.username
        result = _run_ssh(
            host,
            f"mkdir -p {REMOTE_WORKER_DIR} && chown {ssh_user}:{ssh_user} {REMOTE_WORKER_DIR}",
            sudo=True,
        )
        if result["returncode"] != 0:
            raise RuntimeError(f"Failed to create directory: {result['output']}")

        _scp_content_to_host(host, compose_content, f"{REMOTE_WORKER_DIR}/docker-compose.yml")
        _scp_content_to_host(host, env_file_content, f"{REMOTE_WORKER_DIR}/.env")

        registry_password = decrypt(registry.encrypted_password)
        login_cmd = (
            f"echo '{registry_password}' | docker login {registry.url.rstrip('/')} "
            f"-u {registry.username} --password-stdin"
        )
        result = _run_ssh(host, login_cmd)
        if result["returncode"] != 0:
            raise RuntimeError(f"Docker login failed: {result['output']}")

        result = _run_ssh(
            host,
            f"cd {REMOTE_WORKER_DIR} && docker compose pull && docker compose up -d",
            timeout=300,
        )
        if result["returncode"] != 0:
            raise RuntimeError(f"Docker compose up failed: {result['output']}")

        deployment.status = "running"
        deployment.deployed_at = datetime.now(timezone.utc)
        deployment.error = None
        db.commit()

    except Exception as e:
        logger.exception("Deployment %s failed", deployment_id)
        deployment.status = "failed"
        deployment.error = str(e)
        db.commit()
    finally:
        _cleanup_key(host.id)


def stop_worker(deployment: WorkerDeployment, db: Session):
    host = deployment.host
    try:
        result = _run_ssh(host, f"cd {REMOTE_WORKER_DIR} && docker compose down")
        if result["returncode"] != 0:
            raise RuntimeError(f"Stop failed: {result['output']}")
        deployment.status = "stopped"
        deployment.error = None
        db.commit()
    except Exception as e:
        deployment.error = str(e)
        db.commit()
        raise
    finally:
        _cleanup_key(host.id)


def restart_worker(deployment: WorkerDeployment, db: Session):
    host = deployment.host
    try:
        result = _run_ssh(
            host,
            f"cd {REMOTE_WORKER_DIR} && docker compose restart",
            timeout=120,
        )
        if result["returncode"] != 0:
            raise RuntimeError(f"Restart failed: {result['output']}")
        deployment.status = "running"
        deployment.error = None
        deployment.deployed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception as e:
        deployment.error = str(e)
        db.commit()
        raise
    finally:
        _cleanup_key(host.id)


def remove_worker(deployment: WorkerDeployment, db: Session):
    """Stop the worker, remove its containers/images, and clean up the deploy directory."""
    host = deployment.host
    try:
        result = _run_ssh(
            host,
            f"cd {REMOTE_WORKER_DIR} && docker compose down --rmi all --volumes 2>/dev/null; rm -rf {REMOTE_WORKER_DIR}",
            timeout=120,
            sudo=True,
        )
        if result["returncode"] != 0:
            raise RuntimeError(f"Remove failed: {result['output']}")
        deployment.status = "removed"
        deployment.error = None

        if "worker" in (host.roles or []):
            host.roles = [r for r in host.roles if r != "worker"]

        db.commit()
    except Exception as e:
        deployment.error = str(e)
        db.commit()
        raise
    finally:
        _cleanup_key(host.id)


def check_all_deployments_health(db: Session):
    deployments = (
        db.query(WorkerDeployment)
        .filter(WorkerDeployment.status.in_(["running", "unhealthy"]))
        .all()
    )
    if not deployments:
        return

    try:
        inspector = celery_app.control.inspect(timeout=5.0)
        active_queues = inspector.active_queues() or {}
    except Exception:
        logger.warning("Failed to inspect Celery workers for health check")
        return

    online_worker_names = set()
    for worker_name, queues in active_queues.items():
        online_worker_names.add(worker_name)

    now = datetime.now(timezone.utc)
    for deployment in deployments:
        expected_hostname = f"worker@{deployment.worker_site}"
        is_online = any(
            name.endswith(expected_hostname) or name == expected_hostname
            for name in online_worker_names
        )

        deployment.last_health_check = now
        if is_online:
            if deployment.status == "unhealthy":
                deployment.status = "running"
        else:
            deployment.status = "unhealthy"

    db.commit()
