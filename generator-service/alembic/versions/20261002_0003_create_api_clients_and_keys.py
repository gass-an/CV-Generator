"""Crée les clients et les clés d'API.

Revision ID: 20261002_0003
Revises: 20260929_0002
Create Date: 2026-10-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261002_0003"
down_revision: str | None = "20260929_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_client",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(is_active AND disabled_at IS NULL) OR "
            "(NOT is_active AND disabled_at IS NOT NULL)",
            name="ck_api_client_active_disabled_at",
        ),
        sa.CheckConstraint(
            "length(btrim(name)) > 0", name="ck_api_client_name_non_empty"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "api_key",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=True),
        sa.Column("prefix", sa.String(length=32), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "expires_at IS NULL OR expires_at > created_at",
            name="ck_api_key_expires_after_creation",
        ),
        sa.CheckConstraint(
            "name IS NULL OR length(btrim(name)) > 0",
            name="ck_api_key_name_non_empty",
        ),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= created_at",
            name="ck_api_key_revoked_after_creation",
        ),
        sa.ForeignKeyConstraint(["client_id"], ["api_client.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash", name="uq_api_key_key_hash"),
        sa.UniqueConstraint("prefix", name="uq_api_key_prefix"),
    )
    op.create_index(
        op.f("ix_api_key_client_id"), "api_key", ["client_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_api_key_client_id"), table_name="api_key")
    op.drop_table("api_key")
    op.drop_table("api_client")
