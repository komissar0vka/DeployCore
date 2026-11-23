"""Installation, user accounts, server sessions and audit events."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001_system"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    installation = op.create_table(
        "installation_settings",
        sa.Column("id", sa.SmallInteger(), primary_key=True, autoincrement=False),
        sa.Column("organization", sa.String(120), nullable=False),
        sa.Column("instance_name", sa.String(120), nullable=False),
        sa.Column("agent_url", sa.String(512)),
        sa.Column("heartbeat_seconds", sa.SmallInteger(), nullable=False),
        sa.Column("language", sa.String(2), nullable=False),
        sa.Column("configured_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("id = 1", name="installation_singleton"),
        sa.CheckConstraint("heartbeat_seconds BETWEEN 15 AND 3600", name="installation_heartbeat_range"),
        sa.CheckConstraint("language IN ('ru', 'en')", name="installation_language"),
    )
    op.bulk_insert(installation, [{
        "id": 1, "organization": "", "instance_name": "DeployCore",
        "heartbeat_seconds": 60, "language": "ru",
    }])
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("role IN ('super_admin', 'administrator', 'viewer')", name="users_role"),
    )
    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("target_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("source", sa.String(45)),
        sa.Column("account_key", sa.String(64)),
        sa.Column("details", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"])
    op.create_index("audit_login_address", "audit_events", ["action", "source", "created_at"])
    op.create_index("audit_login_account", "audit_events", ["action", "account_key", "created_at"])


def downgrade():
    op.drop_table("audit_events")
    op.drop_table("sessions")
    op.drop_table("users")
    op.drop_table("installation_settings")
