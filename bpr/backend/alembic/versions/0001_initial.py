"""initial nodes table

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-13 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    review_frequency = sa.Enum(
        "monthly", "quarterly", "annually", name="review_frequency"
    )
    node_status = sa.Enum(
        "active", "under_review", "deprecated", name="node_status"
    )
    review_frequency.create(op.get_bind(), checkfirst=True)
    node_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "nodes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "parent_id",
            sa.Integer(),
            sa.ForeignKey("nodes.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner", sa.String(length=255), nullable=True),
        sa.Column(
            "review_frequency",
            sa.Enum(name="review_frequency", create_type=False),
            nullable=True,
        ),
        sa.Column("last_review_date", sa.Date(), nullable=True),
        sa.Column("next_review_date", sa.Date(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(name="node_status", create_type=False),
            nullable=False,
            server_default="active",
        ),
        sa.Column("linked_procedure_url", sa.Text(), nullable=True),
        sa.Column("kpi_name", sa.String(length=255), nullable=True),
        sa.Column("kpi_target", sa.String(length=255), nullable=True),
        sa.Column("kpi_current", sa.String(length=255), nullable=True),
        sa.Column("camunda_process_key", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("level >= 1 AND level <= 4", name="ck_nodes_level_range"),
        sa.UniqueConstraint("code", name="uq_nodes_code"),
    )
    op.create_index("ix_nodes_parent_id", "nodes", ["parent_id"])
    op.create_index("ix_nodes_level", "nodes", ["level"])
    op.create_index("ix_nodes_id", "nodes", ["id"])


def downgrade() -> None:
    op.drop_index("ix_nodes_id", table_name="nodes")
    op.drop_index("ix_nodes_level", table_name="nodes")
    op.drop_index("ix_nodes_parent_id", table_name="nodes")
    op.drop_table("nodes")
    sa.Enum(name="node_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="review_frequency").drop(op.get_bind(), checkfirst=True)
