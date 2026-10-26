"""Ajoute la sélection LLM persistante et le modèle exact des jobs.

Revision ID: 20261026_0009
Revises: 20261018_0008
Create Date: 2026-10-26
"""

import os
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261026_0009"
down_revision: str | None = "20261018_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REFERENCE_MODEL = "ggml-org/Qwen3-14B-GGUF:Q4_K_M"


def upgrade() -> None:
    initial_model = os.getenv("LLM_MODEL", REFERENCE_MODEL).strip() or REFERENCE_MODEL
    op.create_table(
        "llm_configuration",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("selected_model", sa.String(255), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("id = 1", name="ck_llm_configuration_singleton"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        sa.text(
            "INSERT INTO llm_configuration (id, selected_model) VALUES (1, :model)"
        ).bindparams(model=initial_model)
    )
    op.add_column("document_job", sa.Column("llm_model", sa.String(255), nullable=True))
    # Les générations déjà terminées peuvent avoir utilisé plusieurs modèles :
    # leur provenance exacte reste donc inconnue. Seuls les jobs susceptibles
    # d'être repris doivent recevoir le modèle actif au moment de la migration.
    op.execute(
        sa.text(
            "UPDATE document_job SET llm_model = :model "
            "WHERE llm_model IS NULL AND status IN ('pending', 'processing')"
        ).bindparams(model=initial_model)
    )
    op.create_index(
        op.f("ix_document_job_llm_model"),
        "document_job",
        ["llm_model"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_document_job_llm_model"), table_name="document_job")
    op.drop_column("document_job", "llm_model")
    op.drop_table("llm_configuration")
