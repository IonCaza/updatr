import asyncio
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.deployment import RegistryConfig, ImageBuild
from app.services.credential_service import decrypt

logger = logging.getLogger(__name__)

TEMP_KEY_DIR = Path(tempfile.gettempdir()) / "updatr_keys"


def _ssh_args(host, credential, command: str) -> list[str]:
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
        key_path = TEMP_KEY_DIR / f"build_{host.id}.pem"
        key_path.write_text(key_content)
        key_path.chmod(0o600)
        args.extend(["-i", str(key_path)])
    elif credential.type == "ssh-password" and credential.encrypted_password:
        password = decrypt(credential.encrypted_password)
        args = [
            "sshpass", "-p", password,
            *args,
        ]

    args.append(f"{credential.username}@{host.hostname}")
    args.append(command)
    return args


def _cleanup_key(host_id: str):
    path = TEMP_KEY_DIR / f"build_{host_id}.pem"
    if path.exists():
        path.unlink()


def build_and_push(build_id: str, db: Session):
    build: ImageBuild = db.query(ImageBuild).filter(ImageBuild.id == build_id).first()
    if not build:
        logger.error("Build %s not found", build_id)
        return

    registry: RegistryConfig = build.registry
    build_host = registry.build_host
    credential = build_host.credential

    registry_host = registry.url.rstrip("/").split("://", 1)[-1]
    image_name = f"{registry_host}/{registry.project}/worker"
    full_tag = f"{image_name}:{build.image_tag}"

    build.status = "building"
    build.started_at = datetime.now(timezone.utc)
    build.build_log = ""
    db.commit()

    registry_password = decrypt(registry.encrypted_password)

    steps = [
        (
            "Fetching latest code",
            f"git config --global --add safe.directory {registry.repo_path} && cd {registry.repo_path} && git fetch --all && git checkout {build.git_ref} && git pull origin {build.git_ref}",
        ),
        (
            "Building Docker image",
            f"cd {registry.repo_path} && docker build -f backend/Dockerfile -t {full_tag} ./backend",
        ),
        (
            "Logging into registry",
            f"echo '{registry_password}' | docker login {registry.url.rstrip('/')} -u {registry.username} --password-stdin",
        ),
        (
            "Pushing image",
            f"docker push {full_tag}",
        ),
    ]

    try:
        for step_name, command in steps:
            build.build_log += f"\n=== {step_name} ===\n"
            db.commit()

            if step_name == "Pushing image":
                build.status = "pushing"
                db.commit()

            ssh_args = _ssh_args(build_host, credential, command)
            result = _run_ssh_sync(ssh_args)

            build.build_log += result["output"]
            db.commit()

            if result["returncode"] != 0:
                build.status = "failed"
                build.error = f"Step '{step_name}' failed (exit code {result['returncode']})"
                build.completed_at = datetime.now(timezone.utc)
                db.commit()
                return

        build.status = "completed"
        build.completed_at = datetime.now(timezone.utc)
        db.commit()

    except Exception as e:
        logger.exception("Build %s failed", build_id)
        build.status = "failed"
        build.error = str(e)
        build.completed_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        _cleanup_key(build_host.id)


def _run_ssh_sync(args: list[str]) -> dict:
    import subprocess

    try:
        proc = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=600,
        )
        output = proc.stdout
        if proc.stderr:
            output += f"\n{proc.stderr}"
        return {"returncode": proc.returncode, "output": output}
    except subprocess.TimeoutExpired:
        return {"returncode": -1, "output": "Command timed out after 600 seconds"}
    except Exception as e:
        return {"returncode": -1, "output": f"SSH execution error: {e}"}
