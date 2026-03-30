"""create promotion_drafts

Revision ID: 20260330_01
Revises: 
Create Date: 2026-03-30
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision = "20260330_01"
down_revision = "20260330_00"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "promotion_drafts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("upload_id", sa.Integer(), sa.ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("source", sa.String(length=128), nullable=False, server_default="unknown"),
        sa.Column("entity_type", sa.String(length=32), nullable=False, server_default="sku"),
        sa.Column("entity_key", sa.String(length=128), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="draft"),
        sa.Column("draft_json", mysql.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        mysql_engine="InnoDB",
    )
    op.create_index("ix_promotion_drafts_upload", "promotion_drafts", ["upload_id"])
    op.create_index("ix_promotion_drafts_entity", "promotion_drafts", ["entity_type", "entity_key"])
    op.create_index("ix_promotion_drafts_status", "promotion_drafts", ["status"])
    op.create_index("ix_promotion_drafts_level", "promotion_drafts", ["level"])


def downgrade() -> None:
    op.drop_index("ix_promotion_drafts_level", table_name="promotion_drafts")
    op.drop_index("ix_promotion_drafts_status", table_name="promotion_drafts")
    op.drop_index("ix_promotion_drafts_entity", table_name="promotion_drafts")
    op.drop_index("ix_promotion_drafts_upload", table_name="promotion_drafts")
    op.drop_table("promotion_drafts")

