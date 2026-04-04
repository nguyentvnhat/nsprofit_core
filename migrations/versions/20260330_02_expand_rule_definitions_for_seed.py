"""expand rule_definitions for seed compatibility

Revision ID: 20260330_02
Revises: 20260330_01
Create Date: 2026-03-30
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import mysql


revision = "20260330_02"
down_revision = "20260330_01"
branch_labels = None
depends_on = None


def _has_column(table: str, col: str) -> bool:
    bind = op.get_bind()
    insp = inspect(bind)
    cols = [c["name"] for c in insp.get_columns(table)]
    return col in cols


def upgrade() -> None:
    # Legacy dumps may have rule_definitions with columns: rule_id, domain, yaml_source_path, ...
    # Newer code expects: rule_code, category, severity, condition_json, templates...
    # We add missing columns without dropping legacy ones.
    if not _has_column("rule_definitions", "rule_code"):
        op.add_column(
            "rule_definitions",
            sa.Column("rule_code", sa.String(length=128), nullable=True),
        )
        # Backfill from legacy `rule_id` when present.
        try:
            op.execute(sa.text("UPDATE rule_definitions SET rule_code = rule_id WHERE rule_code IS NULL"))
        except Exception:
            pass
        op.alter_column(
            "rule_definitions",
            "rule_code",
            existing_type=sa.String(length=128),
            nullable=False,
        )
        op.create_index("ix_rule_definitions_rule_code", "rule_definitions", ["rule_code"], unique=True)

    if not _has_column("rule_definitions", "category"):
        op.add_column(
            "rule_definitions",
            sa.Column("category", sa.String(length=64), nullable=False, server_default="general"),
        )
    if not _has_column("rule_definitions", "severity"):
        op.add_column(
            "rule_definitions",
            sa.Column("severity", sa.String(length=16), nullable=False, server_default="info"),
        )
    if not _has_column("rule_definitions", "condition_json"):
        op.add_column("rule_definitions", sa.Column("condition_json", mysql.JSON(), nullable=True))
    if not _has_column("rule_definitions", "title_template"):
        op.add_column("rule_definitions", sa.Column("title_template", sa.String(length=512), nullable=True))
    if not _has_column("rule_definitions", "summary_template"):
        op.add_column("rule_definitions", sa.Column("summary_template", sa.Text(), nullable=True))
    if not _has_column("rule_definitions", "implication_template"):
        op.add_column("rule_definitions", sa.Column("implication_template", sa.Text(), nullable=True))
    if not _has_column("rule_definitions", "action_template"):
        op.add_column("rule_definitions", sa.Column("action_template", sa.Text(), nullable=True))


def downgrade() -> None:
    # Keep downgrade minimal: do not drop legacy columns; only drop the added ones when present.
    bind = op.get_bind()
    insp = inspect(bind)
    cols = {c["name"] for c in insp.get_columns("rule_definitions")}

    if "ix_rule_definitions_rule_code" in {i["name"] for i in insp.get_indexes("rule_definitions")}:
        op.drop_index("ix_rule_definitions_rule_code", table_name="rule_definitions")

    for name in (
        "action_template",
        "implication_template",
        "summary_template",
        "title_template",
        "condition_json",
        "severity",
        "category",
        "rule_code",
    ):
        if name in cols:
            op.drop_column("rule_definitions", name)

