"""add merchants + uploads.merchant_id (nullable)

Revision ID: 20260331_00
Revises: 20260330_03
Create Date: 2026-03-31

Additive-only:
- create `merchants` table if missing
- add `uploads.merchant_id` column (nullable) if missing
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import mysql


revision = "20260331_00"
down_revision = "20260330_03"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return insp.has_table(name)


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    cols = insp.get_columns(table)
    return any(c.get("name") == column for c in cols)


def upgrade() -> None:
    if not _table_exists("merchants"):
        op.create_table(
            "merchants",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("merchant_code", sa.String(length=64), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=False),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=False),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            mysql_engine="InnoDB",
        )
        op.create_index("ux_merchants_code", "merchants", ["merchant_code"], unique=True)

    if _table_exists("uploads") and not _column_exists("uploads", "merchant_id"):
        op.add_column("uploads", sa.Column("merchant_id", sa.Integer(), nullable=True))
        op.create_index("ix_uploads_merchant_id", "uploads", ["merchant_id"])
        # best-effort FK; if it fails in some MySQL variants, column/index still exist
        try:
            op.create_foreign_key(
                "fk_uploads_merchant_id_merchants",
                "uploads",
                "merchants",
                ["merchant_id"],
                ["id"],
                ondelete="SET NULL",
            )
        except Exception:
            pass


def downgrade() -> None:
    # Additive-only policy: do not attempt to drop columns/tables automatically.
    pass

