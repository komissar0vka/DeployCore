from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Installation(Base):
    __tablename__ = "installation_settings"
    __table_args__ = (
        CheckConstraint("id = 1", name="installation_singleton"),
        CheckConstraint("heartbeat_seconds BETWEEN 15 AND 3600", name="installation_heartbeat_range"),
        CheckConstraint("language IN ('ru', 'en')", name="installation_language"),
    )

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False)
    organization: Mapped[str] = mapped_column(String(120))
    instance_name: Mapped[str] = mapped_column(String(120))
    agent_url: Mapped[str | None] = mapped_column(String(512))
    heartbeat_seconds: Mapped[int] = mapped_column(SmallInteger)
    language: Mapped[str] = mapped_column(String(2))
    configured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint(
        "role IN ('super_admin', 'administrator', 'viewer')", name="users_role"
    ),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LoginSession(Base):
    __tablename__ = "sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("audit_login_address", "action", "source", "created_at"),
        Index("audit_login_account", "action", "account_key", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    action: Mapped[str] = mapped_column(String(32))
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    target_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    source: Mapped[str | None] = mapped_column(String(45))
    account_key: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
