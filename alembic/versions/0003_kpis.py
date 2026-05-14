"""kpis + kpi_entries tables

Revision ID: 0003_kpis
Revises: 0002_documents
Create Date: 2026-05-14 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0003_kpis"
down_revision: Union[str, None] = "0002_documents"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Two new enums (kpi_direction, reporting_frequency). The node_status enum
# already exists from 0001_initial — we reference it with create_type=False
# and no DO block.
kpi_direction_enum = postgresql.ENUM(
    "higher_is_better",
    "lower_is_better",
    name="kpi_direction",
    create_type=False,
)
reporting_frequency_enum = postgresql.ENUM(
    "daily",
    "weekly",
    "monthly",
    "quarterly",
    "annually",
    name="reporting_frequency",
    create_type=False,
)
node_status_enum = postgresql.ENUM(
    "active",
    "under_review",
    "deprecated",
    name="node_status",
    create_type=False,
)


def upgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE kpi_direction AS ENUM ('higher_is_better', 'lower_is_better');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE reporting_frequency AS ENUM (
                'daily', 'weekly', 'monthly', 'quarterly', 'annually'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    op.create_table(
        "kpis",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "node_id",
            sa.Integer(),
            sa.ForeignKey("nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("calculation_method", sa.Text(), nullable=True),
        sa.Column("unit", sa.String(length=64), nullable=True),
        sa.Column("target_value", sa.Float(), nullable=True),
        sa.Column("warning_threshold", sa.Float(), nullable=True),
        sa.Column(
            "direction",
            kpi_direction_enum,
            nullable=False,
            server_default="higher_is_better",
        ),
        sa.Column("owner", sa.String(length=255), nullable=False),
        sa.Column(
            "reporting_frequency", reporting_frequency_enum, nullable=True
        ),
        sa.Column("data_source", sa.Text(), nullable=True),
        sa.Column(
            "status",
            node_status_enum,
            nullable=False,
            server_default="active",
        ),
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
        if_not_exists=True,
    )
    op.create_index("ix_kpis_node_id", "kpis", ["node_id"], if_not_exists=True)
    op.create_index("ix_kpis_id", "kpis", ["id"], if_not_exists=True)

    op.create_table(
        "kpi_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "kpi_id",
            sa.Integer(),
            sa.ForeignKey("kpis.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period", sa.String(length=64), nullable=False),
        sa.Column("actual_value", sa.Float(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("entered_by", sa.String(length=255), nullable=True),
        sa.Column(
            "entered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        if_not_exists=True,
    )
    op.create_index(
        "ix_kpi_entries_kpi_id", "kpi_entries", ["kpi_id"], if_not_exists=True
    )
    op.create_index(
        "ix_kpi_entries_id", "kpi_entries", ["id"], if_not_exists=True
    )


def downgrade() -> None:
    op.drop_index("ix_kpi_entries_id", table_name="kpi_entries", if_exists=True)
    op.drop_index(
        "ix_kpi_entries_kpi_id", table_name="kpi_entries", if_exists=True
    )
    op.drop_table("kpi_entries", if_exists=True)

    op.drop_index("ix_kpis_id", table_name="kpis", if_exists=True)
    op.drop_index("ix_kpis_node_id", table_name="kpis", if_exists=True)
    op.drop_table("kpis", if_exists=True)

    # node_status is owned by 0001_initial — don't drop here.
    op.execute("DROP TYPE IF EXISTS reporting_frequency")
    op.execute("DROP TYPE IF EXISTS kpi_direction")
