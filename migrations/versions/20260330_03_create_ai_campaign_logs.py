"""create ai_campaign_logs

Revision ID: 20260330_03
Revises: 20260330_02
Create Date: 2026-03-30
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import mysql


revision = "20260330_03"
down_revision = "20260330_02"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    return insp.has_table(name)


def upgrade() -> None:
    if _table_exists("ai_campaign_logs"):
        return

    op.create_table(
        "ai_campaign_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("store_id", sa.String(length=64), nullable=True),
        sa.Column("campaign_id", sa.String(length=64), nullable=True),
        # INPUT (context)
        sa.Column("industry", sa.String(length=128), nullable=True),
        sa.Column("aov", sa.Numeric(18, 2), nullable=True),
        sa.Column("inventory_level", sa.String(length=32), nullable=True),
        sa.Column("margin_estimate", sa.Numeric(5, 2), nullable=True),
        # AI OUTPUT
        sa.Column("ai_prompt", sa.Text(), nullable=True),
        sa.Column("ai_response", sa.Text(), nullable=True),
        sa.Column("campaign_type", sa.String(length=64), nullable=True),
        sa.Column("discount_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("products_selected", mysql.JSON(), nullable=True),
        # USER ACTION
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("modification_detail", mysql.JSON(), nullable=True),
        sa.Column("reject_reason", sa.String(length=32), nullable=True),
        # TIMING
        sa.Column(
            "created_at",
            sa.DateTime(timezone=False),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("decision_time_seconds", sa.Integer(), nullable=True),
        mysql_engine="InnoDB",
    )

    op.create_index("ix_ai_campaign_logs_store", "ai_campaign_logs", ["store_id"])
    op.create_index("ix_ai_campaign_logs_campaign", "ai_campaign_logs", ["campaign_id"])
    op.create_index("ix_ai_campaign_logs_status", "ai_campaign_logs", ["status"])
    op.create_index("ix_ai_campaign_logs_created_at", "ai_campaign_logs", ["created_at"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table("ai_campaign_logs"):
        return

    idx = {i["name"] for i in insp.get_indexes("ai_campaign_logs")}
    for name in (
        "ix_ai_campaign_logs_created_at",
        "ix_ai_campaign_logs_status",
        "ix_ai_campaign_logs_campaign",
        "ix_ai_campaign_logs_store",
    ):
        if name in idx:
            op.drop_index(name, table_name="ai_campaign_logs")
    op.drop_table("ai_campaign_logs")

