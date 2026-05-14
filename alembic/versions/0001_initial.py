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


# Enum value lists — defined once and referenced by both CREATE TYPE
# (via DO block below) and the column type definitions (with create_type=False
# so SQLAlchemy never tries to issue its own CREATE TYPE).
REVIEW_FREQUENCY_VALUES = ("monthly", "quarterly", "annually")
NODE_STATUS_VALUES = ("active", "under_review", "deprecated")


def upgrade() -> None:
    # PostgreSQL has no `CREATE TYPE IF NOT EXISTS`, so wrap each CREATE TYPE
    # in a DO block that swallows the duplicate_object exception. This makes
    # the migration idempotent across partial failures.
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE review_frequency AS ENUM ('monthly', 'quarterly', 'annually');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE node_status AS ENUM ('active', 'under_review', 'deprecated');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

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
            sa.Enum(
                *REVIEW_FREQUENCY_VALUES,
                name="review_frequency",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("last_review_date", sa.Date(), nullable=True),
        sa.Column("next_review_date", sa.Date(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                *NODE_STATUS_VALUES,
                name="node_status",
                create_type=False,
            ),
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
        if_not_exists=True,
    )
    op.create_index("ix_nodes_parent_id", "nodes", ["parent_id"], if_not_exists=True)
    op.create_index("ix_nodes_level", "nodes", ["level"], if_not_exists=True)
    op.create_index("ix_nodes_id", "nodes", ["id"], if_not_exists=True)


def downgrade() -> None:
    op.drop_index("ix_nodes_id", table_name="nodes", if_exists=True)
    op.drop_index("ix_nodes_level", table_name="nodes", if_exists=True)
    op.drop_index("ix_nodes_parent_id", table_name="nodes", if_exists=True)
    op.drop_table("nodes", if_exists=True)
    op.execute("DROP TYPE IF EXISTS node_status")
    op.execute("DROP TYPE IF EXISTS review_frequency")
