from pydantic import BaseModel, Field
from typing import Literal


class JobCreate(BaseModel):
    host_ids: list[str] = Field(default_factory=list)
    tags_filter: list[str] = Field(default_factory=list)
    patch_categories: list[str] = Field(default_factory=lambda: ["security", "critical"])
    reboot_policy: Literal["auto", "never", "if-required"] = "if-required"


class JobResponse(BaseModel):
    id: str
    status: str
    job_type: str
    host_ids: list[str]
    tags_filter: list[str]
    patch_categories: list[str]
    reboot_policy: str
    schedule_id: str | None
    started_at: str | None
    completed_at: str | None
    host_results: dict
    wave_plan: dict | None = None
    current_wave: int | None = None
    created_at: str


class JobEventResponse(BaseModel):
    id: str
    job_id: str
    host: str
    task_name: str
    status: str
    output: dict
    timestamp: str
