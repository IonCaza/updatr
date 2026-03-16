from pydantic import BaseModel, Field
from typing import Literal


OsType = Literal["windows", "linux", "truenas", "proxmox"]
HostRole = Literal["control_plane", "worker", "docker_host"]


class HostCreate(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    hostname: str = Field(min_length=1, max_length=255)
    os_type: OsType
    ssh_port: int = Field(default=22, ge=1, le=65535)
    winrm_port: int = Field(default=5986, ge=1, le=65535)
    winrm_use_ssl: bool = True
    site: str = Field(default="default", min_length=1, max_length=50)
    site_id: str | None = None
    site_locked: bool = False
    is_self: bool = False
    parent_id: str | None = None
    roles: list[HostRole] = []
    worker_override: str | None = Field(None, max_length=50)
    tags: list[str] = []
    credential_id: str = Field(min_length=1)


class HostUpdate(BaseModel):
    display_name: str | None = Field(None, min_length=1, max_length=200)
    hostname: str | None = Field(None, min_length=1, max_length=255)
    os_type: OsType | None = None
    ssh_port: int | None = Field(None, ge=1, le=65535)
    winrm_port: int | None = Field(None, ge=1, le=65535)
    winrm_use_ssl: bool | None = None
    site: str | None = Field(None, min_length=1, max_length=50)
    site_id: str | None = None
    site_locked: bool | None = None
    is_self: bool | None = None
    parent_id: str | None = None
    roles: list[HostRole] | None = None
    worker_override: str | None = Field(None, max_length=50)
    tags: list[str] | None = None
    credential_id: str | None = None
    is_active: bool | None = None


class HostResponse(BaseModel):
    id: str
    display_name: str
    hostname: str
    os_type: str
    ssh_port: int
    winrm_port: int
    winrm_use_ssl: bool
    site: str
    site_id: str | None
    site_locked: bool
    is_self: bool
    parent_id: str | None
    roles: list[str]
    worker_override: str | None
    tags: list[str]
    credential_id: str
    is_active: bool
    created_at: str
    updated_at: str


class ConnectivityResult(BaseModel):
    success: bool
    latency_ms: float | None = None
    error: str | None = None
