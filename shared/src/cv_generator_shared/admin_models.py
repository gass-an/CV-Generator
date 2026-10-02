import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from cv_generator_shared.database import Base


class AdminSession(Base):
    """Session serveur opaque de l'unique administrateur."""

    __tablename__ = "admin_session"
    __table_args__ = (
        CheckConstraint(
            "expires_at > created_at",
            name="ck_admin_session_expiration",
        ),
        CheckConstraint(
            "(is_authenticated AND username IS NOT NULL) OR "
            "(NOT is_authenticated AND username IS NULL)",
            name="ck_admin_session_identity",
        ),
    )

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    csrf_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    username: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_authenticated: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    form_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


class AdminLoginAttempt(Base):
    """Tentative de connexion persistée pour limiter la force brute."""

    __tablename__ = "admin_login_attempt"
    __table_args__ = (
        Index(
            "ix_admin_login_attempt_ip_time",
            "ip_address",
            "attempted_at",
        ),
        Index(
            "ix_admin_login_attempt_username_time",
            "username_hash",
            "attempted_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False)
    username_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
