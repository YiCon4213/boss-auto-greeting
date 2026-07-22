"""Add browser task lease ownership and progress metadata."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("browser_tasks") as batch_op:
        batch_op.add_column(sa.Column("leased_by", sa.String(120), nullable=True))
        batch_op.add_column(
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0")
        )
        batch_op.add_column(
            sa.Column(
                "progress_sequence", sa.Integer(), nullable=False, server_default="-1"
            )
        )
        batch_op.add_column(sa.Column("acked_at", sa.DateTime(timezone=True)))
        batch_op.add_column(sa.Column("resolved_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    with op.batch_alter_table("browser_tasks") as batch_op:
        batch_op.drop_column("resolved_at")
        batch_op.drop_column("acked_at")
        batch_op.drop_column("progress_sequence")
        batch_op.drop_column("attempt_count")
        batch_op.drop_column("leased_by")
