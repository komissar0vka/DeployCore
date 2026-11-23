"""Device enrollment, credentials, inventory and event history."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002_devices"
down_revision = "0001_system"
branch_labels = None
depends_on = None


def instant(name, nullable=False, **kwargs):
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable, **kwargs)


def device_key(primary_key=False, nullable=False):
    return sa.Column("device_id", sa.Uuid(), sa.ForeignKey("devices.id"), primary_key=primary_key, nullable=nullable)


def upgrade():
    op.create_table(
        "devices",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("hostname", sa.String(253), nullable=False),
        sa.Column("fqdn", sa.String(253), nullable=False),
        sa.Column("network_name", sa.String(253), nullable=False),
        sa.Column("domain_joined", sa.Boolean(), nullable=False),
        sa.Column("ips", JSONB(), nullable=False),
        sa.Column("os_version", sa.String(200), nullable=False),
        sa.Column("agent_version", sa.String(64), nullable=False),
        sa.Column("uptime_seconds", sa.BigInteger(), nullable=False),
        instant("created_at", server_default=sa.func.now()),
        instant("last_seen_at"), instant("deleted_at", nullable=True),
    )
    op.create_index("ix_devices_last_seen_at", "devices", ["last_seen_at"])
    op.create_table(
        "enrollment_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("max_uses", sa.Integer(), nullable=False),
        sa.Column("uses", sa.Integer(), nullable=False),
        instant("expires_at"), instant("revoked_at", nullable=True),
        instant("created_at", server_default=sa.func.now()),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        device_key(nullable=True),
        sa.CheckConstraint("max_uses BETWEEN 1 AND 100 AND uses BETWEEN 0 AND max_uses", name="enrollment_usage"),
        sa.CheckConstraint("device_id IS NULL OR max_uses = 1", name="enrollment_recovery_single_use"),
    )
    op.create_index("ix_enrollment_tokens_device_id", "enrollment_tokens", ["device_id"])
    op.create_table(
        "agents", device_key(primary_key=True),
        sa.Column("credential_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("enrollment_id", sa.Uuid(), sa.ForeignKey("enrollment_tokens.id"), nullable=False),
        instant("issued_at"), instant("revoked_at", nullable=True),
    )
    op.create_table("device_inventory", device_key(primary_key=True),
                    sa.Column("hardware", JSONB(), nullable=False),
                    sa.Column("fingerprint", sa.String(64), nullable=False), instant("collected_at"))
    op.create_table(
        "installed_software", sa.Column("id", sa.BigInteger(), primary_key=True), device_key(),
        sa.Column("name", sa.String(240), nullable=False),
        sa.Column("version", sa.String(120), nullable=False),
        sa.Column("publisher", sa.String(200), nullable=False),
        sa.UniqueConstraint("device_id", "name", "version", "publisher", name="software_identity"),
    )
    op.create_index("ix_installed_software_device_id", "installed_software", ["device_id"])
    op.create_table(
        "device_events", sa.Column("id", sa.BigInteger(), primary_key=True), device_key(),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.Column("action", sa.String(32), nullable=False), instant("created_at", server_default=sa.func.now()),
    )
    op.create_index("ix_device_events_device_id", "device_events", ["device_id"])


def downgrade():
    for name in ("device_events", "installed_software", "device_inventory", "agents", "enrollment_tokens", "devices"):
        op.drop_table(name)
