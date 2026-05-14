"""documents table

Revision ID: 0002_documents
Revises: 0001_initial
Create Date: 2026-05-14 00:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0002_documents"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Same pattern as 0001_initial: use postgresql.ENUM directly with
# create_type=False so SQLAlchemy never tries to emit CREATE TYPE
# during op.create_table. The DO blocks below own type creation.
doc_type_enum = postgresql.ENUM(
    "procedure",
    "work_instruction",
    "form",
    "certificate",
    "policy",
    "reference",
    "ci_event",
    "audit_report",
    "training_record",
    name="doc_type",
    create_type=False,
)

# review_frequency already exists from 0001_initial; we just reference it
# (create_type=False so no attempt to create) and re-use the existing PG type.
review_frequency_enum = postgresql.ENUM(
    "monthly",
    "quarterly",
    "annually",
    name="review_frequency",
    create_type=False,
)


def upgrade() -> None:
    # PostgreSQL has no `CREATE TYPE IF NOT EXISTS`. DO block makes this idempotent.
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE doc_type AS ENUM (
                'procedure',
                'work_instruction',
                'form',
                'certificate',
                'policy',
                'reference',
                'ci_event',
                'audit_report',
                'training_record'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "node_id",
            sa.Integer(),
            sa.ForeignKey("nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("original_filename", sa.String(length=512), nullable=False),
        sa.Column("file_url", sa.Text(), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("mime_type", sa.String(length=255), nullable=True),
        sa.Column("doc_type", doc_type_enum, nullable=False),
        sa.Column("tags", sa.Text(), nullable=True),
        sa.Column("owner", sa.String(length=255), nullable=True),
        sa.Column("review_frequency", review_frequency_enum, nullable=True),
        sa.Column("last_review_date", sa.Date(), nullable=True),
        sa.Column("next_review_date", sa.Date(), nullable=True),
        sa.Column("version", sa.String(length=64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "uploaded_at",
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
    op.create_index(
        "ix_documents_node_id", "documents", ["node_id"], if_not_exists=True
    )
    op.create_index(
        "ix_documents_id", "documents", ["id"], if_not_exists=True
    )


def downgrade() -> None:
    op.drop_index("ix_documents_id", table_name="documents", if_exists=True)
    op.drop_index("ix_documents_node_id", table_name="documents", if_exists=True)
    op.drop_table("documents", if_exists=True)
    op.execute("DROP TYPE IF EXISTS doc_type")
    # Don't drop review_frequency — it's still used by the nodes table and is
    # owned by 0001_initial's downgrade.
