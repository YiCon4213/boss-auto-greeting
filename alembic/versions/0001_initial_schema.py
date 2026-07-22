"""Create the initial local agent schema."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def identity_and_timestamps() -> list[sa.Column]:
    return [
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "profiles",
        *identity_and_timestamps(),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_profiles_is_current", "profiles", ["is_current"])

    op.create_table(
        "base_greetings",
        *identity_and_timestamps(),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_base_greetings_is_current", "base_greetings", ["is_current"]
    )

    op.create_table(
        "model_configs",
        *identity_and_timestamps(),
        sa.Column("base_url", sa.String(length=500), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("temperature", sa.Float(), nullable=False),
        sa.Column("api_key_ref", sa.String(length=120), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_model_configs_is_current", "model_configs", ["is_current"]
    )

    op.create_table(
        "batches",
        *identity_and_timestamps(),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("limit", sa.Integer(), nullable=False),
        sa.Column("analysis_enabled", sa.Boolean(), nullable=False),
        sa.Column("greeting_enabled", sa.Boolean(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("counts", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "job_snapshots",
        *identity_and_timestamps(),
        sa.Column("batch_id", sa.String(length=32), nullable=False),
        sa.Column("job_identity_key", sa.String(length=255), nullable=False),
        sa.Column("jd_fingerprint", sa.String(length=128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "batch_id", "job_identity_key", name="uq_job_snapshots_batch_identity"
        ),
    )
    op.create_index("ix_job_snapshots_batch_id", "job_snapshots", ["batch_id"])

    op.create_table(
        "analyses",
        *identity_and_timestamps(),
        sa.Column("batch_id", sa.String(length=32), nullable=False),
        sa.Column("job_snapshot_id", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"]),
        sa.ForeignKeyConstraint(["job_snapshot_id"], ["job_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analyses_batch_id", "analyses", ["batch_id"])
    op.create_index(
        "ix_analyses_job_snapshot_id", "analyses", ["job_snapshot_id"]
    )

    op.create_table(
        "greetings",
        *identity_and_timestamps(),
        sa.Column("batch_id", sa.String(length=32), nullable=False),
        sa.Column("job_snapshot_id", sa.String(length=32), nullable=False),
        sa.Column("generated_text", sa.Text(), nullable=True),
        sa.Column("final_text", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"]),
        sa.ForeignKeyConstraint(["job_snapshot_id"], ["job_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_greetings_batch_id", "greetings", ["batch_id"])
    op.create_index(
        "ix_greetings_job_snapshot_id", "greetings", ["job_snapshot_id"]
    )

    op.create_table(
        "approval_versions",
        *identity_and_timestamps(),
        sa.Column("batch_id", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_approval_versions_batch_id", "approval_versions", ["batch_id"]
    )

    op.create_table(
        "delivery_items",
        *identity_and_timestamps(),
        sa.Column("batch_id", sa.String(length=32), nullable=False),
        sa.Column("approval_version_id", sa.String(length=32), nullable=False),
        sa.Column("job_snapshot_id", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("final_greeting", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["approval_version_id"], ["approval_versions.id"]),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"]),
        sa.ForeignKeyConstraint(["job_snapshot_id"], ["job_snapshots.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "approval_version_id",
            "job_snapshot_id",
            name="uq_delivery_items_approval_snapshot",
        ),
    )
    op.create_index("ix_delivery_items_batch_id", "delivery_items", ["batch_id"])
    op.create_index(
        "ix_delivery_items_approval_version_id",
        "delivery_items",
        ["approval_version_id"],
    )
    op.create_index(
        "ix_delivery_items_job_snapshot_id", "delivery_items", ["job_snapshot_id"]
    )

    op.create_table(
        "browser_tasks",
        *identity_and_timestamps(),
        sa.Column("batch_id", sa.String(length=32), nullable=True),
        sa.Column("task_type", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_browser_tasks_batch_id", "browser_tasks", ["batch_id"])

    op.create_table(
        "audit_events",
        *identity_and_timestamps(),
        sa.Column("batch_id", sa.String(length=32), nullable=True),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["batches.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_events_batch_id", "audit_events", ["batch_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_batch_id", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_browser_tasks_batch_id", table_name="browser_tasks")
    op.drop_table("browser_tasks")
    op.drop_index("ix_delivery_items_job_snapshot_id", table_name="delivery_items")
    op.drop_index("ix_delivery_items_approval_version_id", table_name="delivery_items")
    op.drop_index("ix_delivery_items_batch_id", table_name="delivery_items")
    op.drop_table("delivery_items")
    op.drop_index("ix_approval_versions_batch_id", table_name="approval_versions")
    op.drop_table("approval_versions")
    op.drop_index("ix_greetings_job_snapshot_id", table_name="greetings")
    op.drop_index("ix_greetings_batch_id", table_name="greetings")
    op.drop_table("greetings")
    op.drop_index("ix_analyses_job_snapshot_id", table_name="analyses")
    op.drop_index("ix_analyses_batch_id", table_name="analyses")
    op.drop_table("analyses")
    op.drop_index("ix_job_snapshots_batch_id", table_name="job_snapshots")
    op.drop_table("job_snapshots")
    op.drop_table("batches")
    op.drop_index("ix_model_configs_is_current", table_name="model_configs")
    op.drop_table("model_configs")
    op.drop_index("ix_base_greetings_is_current", table_name="base_greetings")
    op.drop_table("base_greetings")
    op.drop_index("ix_profiles_is_current", table_name="profiles")
    op.drop_table("profiles")
