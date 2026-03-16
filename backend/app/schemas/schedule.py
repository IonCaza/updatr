from pydantic import BaseModel, Field
from typing import Literal


class ScheduleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    cron_expression: str = Field(min_length=1, max_length=100)
    host_ids: list[str] | None = None
    tags_filter: list[str] | None = None
    patch_categories: list[str] = Field(default_factory=lambda: ["security", "critical"])
    reboot_policy: Literal["auto", "never", "if-required"] = "if-required"


class ScheduleUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    cron_expression: str | None = Field(None, min_length=1, max_length=100)
    host_ids: list[str] | None = None
    tags_filter: list[str] | None = None
    patch_categories: list[str] | None = None
    reboot_policy: Literal["auto", "never", "if-required"] | None = None
    is_active: bool | None = None


class ScheduleResponse(BaseModel):
    id: str
    name: str
    cron_expression: str
    host_ids: list[str] | None
    tags_filter: list[str] | None
    patch_categories: list[str]
    reboot_policy: str
    is_active: bool
    last_run_at: str | None
    next_run_at: str | None
    created_at: str
    updated_at: str
