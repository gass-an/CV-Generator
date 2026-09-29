"""Allow cover-letter document jobs.

Revision ID: 20260929_0002
Revises: 20260927_0001
Create Date: 2026-09-29
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260929_0002"
down_revision: str | None = "20260927_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_document_job_document_type",
        "document_job",
        type_="check",
    )
    op.create_check_constraint(
        "ck_document_job_document_type",
        "document_job",
        "document_type IN ('cv', 'cover_letter')",
    )


def downgrade() -> None:
    # This downgrade intentionally preserves all rows. Recreating the narrower
    # constraint will fail if any cover_letter rows still exist.
    op.drop_constraint(
        "ck_document_job_document_type",
        "document_job",
        type_="check",
    )
    op.create_check_constraint(
        "ck_document_job_document_type",
        "document_job",
        "document_type IN ('cv')",
    )
