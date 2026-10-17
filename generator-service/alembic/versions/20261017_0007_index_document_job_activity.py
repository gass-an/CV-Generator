"""Indexe les consultations chronologiques de l'activité.

Revision ID: 20261017_0007
Revises: 20261010_0006
Create Date: 2026-10-17
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261017_0007"
down_revision: str | None = "20261010_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_document_job_created_at_id",
        "document_job",
        ["created_at", "id"],
        unique=False,
        postgresql_ops={"created_at": "DESC", "id": "DESC"},
    )
    op.create_index(
        "ix_document_job_status_created_at",
        "document_job",
        ["status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_document_job_completed_at",
        "document_job",
        ["completed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_document_job_completed_at", table_name="document_job")
    op.drop_index("ix_document_job_status_created_at", table_name="document_job")
    op.drop_index("ix_document_job_created_at_id", table_name="document_job")
