from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from agent_app.domain.enums import BatchStatus, DeliveryStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return uuid4().hex


class Base(DeclarativeBase):
    pass


class IdMixin:
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class Profile(IdMixin, TimestampMixin, Base):
    __tablename__ = "profiles"

    version: Mapped[int] = mapped_column(Integer, default=1)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class BaseGreeting(IdMixin, TimestampMixin, Base):
    __tablename__ = "base_greetings"

    version: Mapped[int] = mapped_column(Integer, default=1)
    text: Mapped[str] = mapped_column(Text)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class ModelConfig(IdMixin, TimestampMixin, Base):
    __tablename__ = "model_configs"

    base_url: Mapped[str] = mapped_column(String(500))
    model: Mapped[str] = mapped_column(String(120))
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30)
    temperature: Mapped[float] = mapped_column(Float, default=0.2)
    api_key_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class Batch(IdMixin, TimestampMixin, Base):
    __tablename__ = "batches"

    status: Mapped[str] = mapped_column(String(40), default=BatchStatus.DRAFT.value)
    limit: Mapped[int] = mapped_column(Integer, default=10)
    analysis_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    greeting_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    source_url: Mapped[str] = mapped_column(Text)
    counts: Mapped[dict] = mapped_column(JSON, default=dict)


class JobSnapshot(IdMixin, TimestampMixin, Base):
    __tablename__ = "job_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "batch_id", "job_identity_key", name="uq_job_snapshots_batch_identity"
        ),
    )

    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id"), index=True)
    job_identity_key: Mapped[str] = mapped_column(String(255))
    jd_fingerprint: Mapped[str] = mapped_column(String(128))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class Analysis(IdMixin, TimestampMixin, Base):
    __tablename__ = "analyses"

    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id"), index=True)
    job_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("job_snapshots.id"), index=True
    )
    status: Mapped[str] = mapped_column(String(40), default="pending")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class Greeting(IdMixin, TimestampMixin, Base):
    __tablename__ = "greetings"

    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id"), index=True)
    job_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("job_snapshots.id"), index=True
    )
    generated_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class ApprovalVersion(IdMixin, TimestampMixin, Base):
    __tablename__ = "approval_versions"

    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class DeliveryItem(IdMixin, TimestampMixin, Base):
    __tablename__ = "delivery_items"
    __table_args__ = (
        UniqueConstraint(
            "approval_version_id",
            "job_snapshot_id",
            name="uq_delivery_items_approval_snapshot",
        ),
    )

    batch_id: Mapped[str] = mapped_column(ForeignKey("batches.id"), index=True)
    approval_version_id: Mapped[str] = mapped_column(
        ForeignKey("approval_versions.id"), index=True
    )
    job_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("job_snapshots.id"), index=True
    )
    status: Mapped[str] = mapped_column(
        String(40), default=DeliveryStatus.APPROVED.value
    )
    final_greeting: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class BrowserTask(IdMixin, TimestampMixin, Base):
    __tablename__ = "browser_tasks"

    batch_id: Mapped[str | None] = mapped_column(
        ForeignKey("batches.id"), nullable=True, index=True
    )
    task_type: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(40), default="pending")
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AuditEvent(IdMixin, TimestampMixin, Base):
    __tablename__ = "audit_events"

    batch_id: Mapped[str | None] = mapped_column(
        ForeignKey("batches.id"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(120))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
