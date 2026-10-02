"""Associe les nouveaux documents à leur client d'API.

Revision ID: 20261003_0004
Revises: 20261002_0003
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261003_0004"
down_revision: str | None = "20261002_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "document_job",
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_document_job_client_id_api_client",
        "document_job",
        "api_client",
        ["client_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_document_job_client_id"),
        "document_job",
        ["client_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_document_job_client_id"), table_name="document_job")
    op.drop_constraint(
        "fk_document_job_client_id_api_client",
        "document_job",
        type_="foreignkey",
    )
    op.drop_column("document_job", "client_id")
