from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, SecretStr, field_validator, model_validator

from agent_app.domain.enums import BatchStatus


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


class BatchCreate(BaseModel):
    limit: int = Field(default=10, ge=1, le=50)
    analysis_enabled: bool = True
    greeting_enabled: bool = True
    source_url: HttpUrl

    @field_validator("source_url")
    @classmethod
    def validate_source_url(cls, value: HttpUrl) -> HttpUrl:
        if (
            value.scheme != "https"
            or value.host != "www.zhipin.com"
            or value.path != "/web/geek/jobs"
        ):
            raise ValueError(
                "source_url must be the HTTPS www.zhipin.com job list"
            )
        return value


class BatchRead(BaseModel):
    id: str
    status: BatchStatus
    limit: int
    analysis_enabled: bool
    greeting_enabled: bool
    source_url: HttpUrl
    counts: dict[str, int]
    available_actions: list[str]


BrowserTaskType = Literal["collect_batch", "execute_delivery", "pause"]


class BrowserTaskEnvelope(BaseModel):
    id: str
    type: BrowserTaskType
    payload: dict[str, object]
    lease_seconds: int = 30


class BrowserTaskWorker(BaseModel):
    worker_id: str = Field(min_length=1, max_length=120)


class BrowserTaskProgress(BrowserTaskWorker):
    sequence: int = Field(ge=0)
    status: str = Field(min_length=1, max_length=80)
    detail: dict[str, object] = Field(default_factory=dict)


class BrowserTaskResult(BaseModel):
    ok: bool
    result: dict[str, object] = Field(default_factory=dict)
    error_code: str = Field(default="", max_length=120)
    error_message: str = Field(default="", max_length=500)


class BrowserTaskResolution(BrowserTaskResult):
    worker_id: str = Field(min_length=1, max_length=120)


class JobSnapshotCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    encrypt_job_id: str = ""
    security_id: str = ""
    lid: str = ""
    title: str = Field(min_length=1, max_length=300)
    company: str = Field(min_length=1, max_length=300)
    salary: str = ""
    city: str = ""
    experience: str = ""
    degree: str = ""
    address: str = ""
    description: str = Field(min_length=1)
    skills: list[str] = Field(default_factory=list)
    boss_name: str = ""
    boss_title: str = ""
    boss_active: str = ""
    company_industry: str = ""
    company_size: str = ""
    company_stage: str = ""
    company_description: str = ""
    source_url: HttpUrl
    expectation_context: dict[str, object] = Field(default_factory=dict)
    captured_at: datetime

    @model_validator(mode="after")
    def require_reliable_identity(self):
        if not any((self.encrypt_job_id, self.security_id, self.lid)):
            raise ValueError("reliable job identity is required")
        return self


class JobSnapshotRead(BaseModel):
    id: str
    batch_id: str
    job_identity_key: str
    jd_fingerprint: str
    payload: dict[str, object]
    duplicate: bool
