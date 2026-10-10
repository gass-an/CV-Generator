"""Autorise les jobs de guides de préparation à l'entretien.

Revision ID: 20261010_0006
Revises: 20261004_0005
Create Date: 2026-10-10
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261010_0006"
down_revision: str | None = "20261004_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_document_job_document_type", "document_job", type_="check")
    op.create_check_constraint(
        "ck_document_job_document_type",
        "document_job",
        "document_type IN ('cv', 'cover_letter', 'interview_prep')",
    )


def downgrade() -> None:
    # Les lignes interview_prep sont conservées : le downgrade échoue si elles
    # existent encore plutôt que de modifier ou supprimer d'anciens jobs.
    op.drop_constraint("ck_document_job_document_type", "document_job", type_="check")
    op.create_check_constraint(
        "ck_document_job_document_type",
        "document_job",
        "document_type IN ('cv', 'cover_letter')",
    )
