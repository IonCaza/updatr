import httpx

from app.models.deployment import RegistryConfig
from app.services.credential_service import decrypt


def _get_password(registry: RegistryConfig) -> str:
    return decrypt(registry.encrypted_password)


async def test_connection(url: str, username: str, password: str) -> dict:
    url = url.rstrip("/")
    try:
        async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
            health_resp = await client.get(f"{url}/api/v2.0/health")
            health_resp.raise_for_status()
            health_data = health_resp.json()

            auth_resp = await client.get(
                f"{url}/api/v2.0/users/current",
                auth=(username, password),
            )
            if auth_resp.status_code == 401:
                return {
                    "success": False,
                    "message": "Authentication failed: invalid username or password",
                    "harbor_version": None,
                }
            auth_resp.raise_for_status()

            version_resp = await client.get(
                f"{url}/api/v2.0/systeminfo",
                auth=(username, password),
            )
            harbor_version = None
            if version_resp.status_code == 200:
                info = version_resp.json()
                harbor_version = info.get("harbor_version")

            all_healthy = all(
                c.get("status") == "healthy"
                for c in health_data.get("components", [])
            )
            status_msg = "All components healthy" if all_healthy else "Some components unhealthy"

            return {
                "success": True,
                "message": f"Connected to Harbor. {status_msg}.",
                "harbor_version": harbor_version,
            }
    except httpx.ConnectError:
        return {
            "success": False,
            "message": f"Cannot connect to {url}",
            "harbor_version": None,
        }
    except httpx.HTTPStatusError as e:
        return {
            "success": False,
            "message": f"HTTP error: {e.response.status_code}",
            "harbor_version": None,
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Connection failed: {e}",
            "harbor_version": None,
        }


async def list_tags(registry: RegistryConfig, repo_name: str = "worker") -> list[dict]:
    url = registry.url.rstrip("/")
    password = _get_password(registry)
    async with httpx.AsyncClient(verify=False, timeout=15.0) as client:
        resp = await client.get(
            f"{url}/api/v2.0/projects/{registry.project}/repositories/{repo_name}/artifacts",
            auth=(registry.username, password),
            params={"page_size": 50, "with_tag": "true"},
        )
        resp.raise_for_status()
        artifacts = resp.json()

    tags = []
    for artifact in artifacts:
        for tag in artifact.get("tags") or []:
            tags.append({
                "name": tag["name"],
                "digest": artifact.get("digest", ""),
                "size": artifact.get("size", 0),
                "push_time": tag.get("push_time", ""),
                "scan_status": artifact.get("scan_overview", {})
                .get("application/vnd.security.vulnerability.report; version=1.1", {})
                .get("scan_status"),
            })
    return sorted(tags, key=lambda t: t.get("push_time", ""), reverse=True)


async def get_image_info(
    registry: RegistryConfig, repo_name: str, tag: str
) -> dict | None:
    url = registry.url.rstrip("/")
    password = _get_password(registry)
    async with httpx.AsyncClient(verify=False, timeout=15.0) as client:
        resp = await client.get(
            f"{url}/api/v2.0/projects/{registry.project}/repositories/{repo_name}/artifacts/{tag}",
            auth=(registry.username, password),
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
