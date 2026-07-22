from typing import Any

from pydantic import BaseModel, Field, HttpUrl, SecretStr


class ProfileUpdate(BaseModel):
    target_roles: list[str] | None = None
    target_directions: list[str] | None = None
    desired_work: str | None = None
    focus_skills: list[str] | None = None
    excluded_directions: list[str] | None = None
    summary: str | None = None
    education: list[dict[str, Any]] | None = None
    skills: list[str] | None = None
    projects: list[dict[str, Any]] | None = None
    employment: list[dict[str, Any]] | None = None
    research: list[dict[str, Any]] | None = None
    competitions: list[dict[str, Any]] | None = None
    open_source: list[dict[str, Any]] | None = None
    strengths: list[str] | None = None
    availability: dict[str, Any] | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    field_visibility: dict[str, bool] = Field(default_factory=dict)


class ProfileRead(ProfileUpdate):
    id: str
    version: int


class ModelConfigUpdate(BaseModel):
    base_url: HttpUrl
    model: str = Field(min_length=1, max_length=120)
    timeout_seconds: int = Field(default=30, ge=5, le=120)
    temperature: float = Field(default=0.2, ge=0, le=1)
    api_key: SecretStr | None = None


class ModelConfigRead(BaseModel):
    base_url: HttpUrl
    model: str
    timeout_seconds: int
    temperature: float
    api_key_configured: bool
