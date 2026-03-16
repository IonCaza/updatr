from pydantic import BaseModel, Field


class RegistryConfigCreate(BaseModel):
    url: str = Field(min_length=1, max_length=500)
    project: str = Field(default="updatr", min_length=1, max_length=100)
    username: str = Field(min_length=1, max_length=200)
    password: str | None = None
    build_host_id: str
    repo_path: str = Field(default="/opt/updatr", min_length=1, max_length=500)
    external_database_url: str | None = None
    external_redis_url: str | None = None


class RegistryConfigUpdate(BaseModel):
    url: str | None = Field(None, min_length=1, max_length=500)
    project: str | None = Field(None, min_length=1, max_length=100)
    username: str | None = Field(None, min_length=1, max_length=200)
    password: str | None = None
    build_host_id: str | None = None
    repo_path: str | None = Field(None, min_length=1, max_length=500)
    external_database_url: str | None = None
    external_redis_url: str | None = None


class RegistryConfigResponse(BaseModel):
    id: str
    name: str
    url: str
    project: str
    username: str
    build_host_id: str
    repo_path: str
    external_database_url: str | None
    external_redis_url: str | None
    is_active: bool
    created_at: str
    updated_at: str


class RegistryTestRequest(BaseModel):
    url: str = Field(min_length=1)
    username: str = Field(min_length=1)
    password: str | None = None


class ConnectivityTestRequest(BaseModel):
    url: str = Field(min_length=1)


class RegistryTestResponse(BaseModel):
    success: bool
    message: str
    harbor_version: str | None = None


class BuildRequest(BaseModel):
    image_tag: str = Field(min_length=1, max_length=200)
    git_ref: str = Field(default="main", min_length=1, max_length=200)


class BuildResponse(BaseModel):
    id: str
    registry_id: str
    image_tag: str
    git_ref: str
    status: str
    build_log: str | None
    error: str | None
    started_at: str | None
    completed_at: str | None
    created_at: str


class DeployRequest(BaseModel):
    host_ids: list[str] = Field(min_length=1)
    image_tag: str = Field(min_length=1, max_length=200)


class DeploymentResponse(BaseModel):
    id: str
    host_id: str
    registry_id: str
    image_tag: str
    status: str
    worker_site: str
    env_snapshot: dict | None
    error: str | None
    deployed_at: str | None
    last_health_check: str | None
    created_at: str


class DeploymentStatusItem(BaseModel):
    deployment_id: str | None
    host_id: str
    hostname: str
    display_name: str
    site: str
    current_tag: str | None
    status: str
    worker_site: str
    deployed_at: str | None
    last_health_check: str | None
    worker_online: bool


class DeploymentOverview(BaseModel):
    registry_configured: bool
    registry: RegistryConfigResponse | None
    latest_build: BuildResponse | None
    deployments: list[DeploymentStatusItem]
