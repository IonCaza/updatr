from pydantic import BaseModel, Field


class SiteCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    display_name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(None, max_length=500)
    subnets: list[str] = []
    is_default: bool = False


class SiteUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=50)
    display_name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=500)
    subnets: list[str] | None = None
    is_default: bool | None = None


class SiteResponse(BaseModel):
    id: str
    name: str
    display_name: str
    description: str | None
    subnets: list[str]
    is_default: bool
    host_count: int = 0
    created_at: str
    updated_at: str
