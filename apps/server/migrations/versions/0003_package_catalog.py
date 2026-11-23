"""Package catalog, immutable artifacts and detection rules."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003_package_catalog"
down_revision = "0002_devices"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "software_packages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("publisher", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("publisher", "name", name="package_identity"),
    )
    op.create_table(
        "software_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("package_id", sa.Uuid(), sa.ForeignKey("software_packages.id"), nullable=False),
        sa.Column("version", sa.String(80), nullable=False),
        sa.Column("architecture", sa.String(3), nullable=False),
        sa.Column("installer", sa.String(3), nullable=False),
        sa.Column("min_windows_build", sa.Integer()),
        sa.Column("install_args", JSONB(), nullable=False),
        sa.Column("uninstall_args", JSONB()),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("success_codes", JSONB(), nullable=False),
        sa.Column("reboot_required", sa.Boolean(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("approved_by", sa.Uuid(), sa.ForeignKey("users.id")),
        sa.UniqueConstraint("package_id", "version", "architecture", name="package_version_identity"),
        sa.CheckConstraint("architecture IN ('x64', 'x86')", name="package_architecture"),
        sa.CheckConstraint("installer IN ('msi', 'exe')", name="package_installer"),
        sa.CheckConstraint("timeout_seconds BETWEEN 1 AND 86400", name="package_timeout"),
        sa.CheckConstraint("min_windows_build IS NULL OR min_windows_build > 0", name="package_os_build"),
    )
    op.create_table(
        "package_detection_rules",
        sa.Column("version_id", sa.Uuid(), sa.ForeignKey("software_versions.id"), primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("data", JSONB(), nullable=False),
        sa.CheckConstraint("kind IN ('msi_product', 'registry_software')", name="package_detection_kind"),
    )
    op.create_table(
        "package_artifacts",
        sa.Column("version_id", sa.Uuid(), sa.ForeignKey("software_versions.id"), primary_key=True),
        sa.Column("filename", sa.String(180), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("signature", sa.String(12), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("signature IN ('verified', 'unverified')", name="package_signature_status"),
        sa.CheckConstraint("size_bytes > 0", name="package_artifact_size"),
        sa.CheckConstraint("sha256 ~ '^[a-f0-9]{64}$'", name="package_sha256"),
    )


def downgrade():
    for table in ("package_artifacts", "package_detection_rules", "software_versions", "software_packages"):
        op.drop_table(table)
