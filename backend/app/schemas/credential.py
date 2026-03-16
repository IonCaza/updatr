from pydantic import BaseModel, Field
from typing import Literal


class CredentialCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    type: Literal["ssh-password", "ssh-key", "winrm-password"]
    username: str = Field(min_length=1, max_length=200)
    password: str | None = None
    private_key: str | None = None
    passphrase: str | None = None


class CredentialUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    username: str | None = Field(None, min_length=1, max_length=200)
    password: str | None = None
    private_key: str | None = None
    passphrase: str | None = None


class CredentialResponse(BaseModel):
    id: str
    name: str
    type: str
    username: str
    created_at: str
    updated_at: str
