"""Deployment queue and lease history."""
from alembic import op
import sqlalchemy as sa

revision = "0004_deployment_queue"
down_revision = "0003_package_catalog"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "deployment_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("version_id", sa.Uuid(), sa.ForeignKey("software_versions.id"), nullable=False),
        sa.Column("operation", sa.String(12), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("created_by", "request_id", name="deployment_request_identity"),
        sa.CheckConstraint("operation IN ('install', 'uninstall')", name="deployment_operation"),
    )
    op.create_index("ix_deployment_jobs_created_at", "deployment_jobs", ["created_at"])
    op.create_table(
        "deployment_targets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("deployment_jobs.id"), nullable=False),
        sa.Column("device_id", sa.Uuid(), sa.ForeignKey("devices.id"), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("job_id", "device_id", name="deployment_device_identity"),
        sa.CheckConstraint("state IN ('queued', 'leased', 'running', 'not_executed', 'cancelled', 'failed')",
                           name="deployment_target_state"),
    )
    op.create_index("deployment_one_active_target", "deployment_targets", ["device_id"], unique=True,
                    postgresql_where=sa.text("state IN ('leased', 'running')"))
    op.create_index("deployment_target_device_state", "deployment_targets", ["device_id", "state"])
    op.create_table(
        "deployment_attempts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("target_id", sa.Uuid(), sa.ForeignKey("deployment_targets.id"), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("leased_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("outcome", sa.String(16)),
        sa.UniqueConstraint("target_id", "number", name="deployment_attempt_number"),
        sa.CheckConstraint("number BETWEEN 1 AND 5", name="deployment_attempt_range"),
        sa.CheckConstraint("outcome IS NULL OR outcome IN ('expired', 'not_executed', 'cancelled')",
                           name="deployment_attempt_outcome"),
    )
    op.create_table(
        "deployment_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("deployment_jobs.id"), nullable=False),
        sa.Column("target_id", sa.Uuid(), sa.ForeignKey("deployment_targets.id")),
        sa.Column("attempt_id", sa.Uuid(), sa.ForeignKey("deployment_attempts.id")),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("deployment_events_job_cursor", "deployment_events", ["job_id", "id"])


def downgrade():
    for table in ("deployment_events", "deployment_attempts", "deployment_targets", "deployment_jobs"):
        op.drop_table(table)
