"""Crée les sessions et tentatives de connexion administrateur.

Revision ID: 20261004_0005
Revises: 20261003_0004
Create Date: 2026-10-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261004_0005"
down_revision: str | None = "20261003_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "admin_session",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("csrf_hash", sa.String(length=64), nullable=False),
        sa.Column("username", sa.String(length=200), nullable=True),
        sa.Column("is_authenticated", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("form_token_hash", sa.String(length=64), nullable=True),
        sa.CheckConstraint(
            "expires_at > created_at", name="ck_admin_session_expiration"
        ),
        sa.CheckConstraint(
            "(is_authenticated AND username IS NOT NULL) OR "
            "(NOT is_authenticated AND username IS NULL)",
            name="ck_admin_session_identity",
        ),
        sa.PrimaryKeyConstraint("token_hash"),
    )
    op.create_table(
        "admin_login_attempt",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=False),
        sa.Column("username_hash", sa.String(length=64), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_admin_login_attempt_ip_time",
        "admin_login_attempt",
        ["ip_address", "attempted_at"],
        unique=False,
    )
    op.create_index(
        "ix_admin_login_attempt_username_time",
        "admin_login_attempt",
        ["username_hash", "attempted_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_admin_login_attempt_username_time", table_name="admin_login_attempt"
    )
    op.drop_index("ix_admin_login_attempt_ip_time", table_name="admin_login_attempt")
    op.drop_table("admin_login_attempt")
    op.drop_table("admin_session")
