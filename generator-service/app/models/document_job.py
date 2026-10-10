import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DocumentType(StrEnum):
    """Types de documents persistés et traités par le worker."""

    CV = "cv"
    COVER_LETTER = "cover_letter"
    INTERVIEW_PREP = "interview_prep"


class DocumentJobStatus(StrEnum):
    """Étapes persistées d'une génération de document."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentJob(Base):
    """Job persistant partagé par l'API et le worker de génération."""

    __tablename__ = "document_job"
    __table_args__ = (
        CheckConstraint(
            "document_type IN ('cv', 'cover_letter', 'interview_prep')",
            name="ck_document_job_document_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_document_job_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("api_client.id"),
        nullable=True,
        index=True,
    )
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(
            DocumentType,
            length=32,
            native_enum=False,
            values_callable=lambda values: [value.value for value in values],
        ),
        index=True,
    )
    status: Mapped[DocumentJobStatus] = mapped_column(
        Enum(
            DocumentJobStatus,
            length=32,
            native_enum=False,
            values_callable=lambda values: [value.value for value in values],
        ),
        index=True,
    )

    avp_number: Mapped[str] = mapped_column(String(128))
    resume_data: Mapped[dict[str, Any]] = mapped_column(JSONB)

    result_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_format: Mapped[str | None] = mapped_column(String(32), nullable=True)

    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
