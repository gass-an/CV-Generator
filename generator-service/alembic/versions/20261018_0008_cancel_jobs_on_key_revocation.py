"""Associe les générations à leur clé et ajoute l'annulation métier.

Revision ID: 20261018_0008
Revises: 20261017_0007
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261018_0008"
down_revision: str | None = "20261017_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "document_job",
        sa.Column("api_key_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "document_job",
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "document_job", sa.Column("cancellation_reason", sa.String(128), nullable=True)
    )
    op.create_foreign_key(
        "fk_document_job_api_key_id_api_key",
        "document_job",
        "api_key",
        ["api_key_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_document_job_api_key_id"),
        "document_job",
        ["api_key_id"],
        unique=False,
    )
    op.drop_constraint("ck_document_job_status", "document_job", type_="check")
    op.create_check_constraint(
        "ck_document_job_status",
        "document_job",
        "status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')",
    )


def downgrade() -> None:
    op.execute(
        "UPDATE document_job SET status = 'failed', completed_at = cancelled_at "
        "WHERE status = 'cancelled'"
    )
    op.drop_constraint("ck_document_job_status", "document_job", type_="check")
    op.create_check_constraint(
        "ck_document_job_status",
        "document_job",
        "status IN ('pending', 'processing', 'completed', 'failed')",
    )
    op.drop_index(op.f("ix_document_job_api_key_id"), table_name="document_job")
    op.drop_constraint(
        "fk_document_job_api_key_id_api_key", "document_job", type_="foreignkey"
    )
    op.drop_column("document_job", "cancellation_reason")
    op.drop_column("document_job", "cancelled_at")
    op.drop_column("document_job", "api_key_id")
