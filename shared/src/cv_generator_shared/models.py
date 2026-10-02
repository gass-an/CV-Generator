import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cv_generator_shared.database import Base


class ApiClient(Base):
    """Personne autorisée à posséder une ou plusieurs clés d'API."""

    __tablename__ = "api_client"
    __table_args__ = (
        CheckConstraint("length(btrim(name)) > 0", name="ck_api_client_name_non_empty"),
        CheckConstraint(
            "(is_active AND disabled_at IS NULL) OR "
            "(NOT is_active AND disabled_at IS NOT NULL)",
            name="ck_api_client_active_disabled_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    disabled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    keys: Mapped[list["ApiKey"]] = relationship(back_populates="client")


class ApiKey(Base):
    """Empreinte persistée d'une clé d'API, sans son secret."""

    __tablename__ = "api_key"
    __table_args__ = (
        CheckConstraint(
            "name IS NULL OR length(btrim(name)) > 0",
            name="ck_api_key_name_non_empty",
        ),
        CheckConstraint(
            "expires_at IS NULL OR expires_at > created_at",
            name="ck_api_key_expires_after_creation",
        ),
        CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= created_at",
            name="ck_api_key_revoked_after_creation",
        ),
        UniqueConstraint("prefix", name="uq_api_key_prefix"),
        UniqueConstraint("key_hash", name="uq_api_key_key_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_client.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    prefix: Mapped[str] = mapped_column(String(32), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    client: Mapped[ApiClient] = relationship(back_populates="keys")
