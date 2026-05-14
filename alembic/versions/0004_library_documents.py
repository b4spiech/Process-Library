"""library_documents + node_documents (replaces one-to-one documents)

Revision ID: 0004_library_documents
Revises: 0003_kpis
Create Date: 2026-05-14 00:00:00

Replaces the one-to-one `documents` table with a central
`library_documents` table plus a `node_documents` many-to-many join.
Existing data is migrated row-for-row, preserving ids and creating a
single link per original row so the historical node association is
kept. The old `documents` table is then dropped.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0004_library_documents"
down_revision: Union[str, None] = "0003_kpis"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Reuse existing PG enums; create_type=False so SQLAlchemy doesn't try to
# emit CREATE TYPE again.
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
review_frequency_enum = postgresql.ENUM(
    "monthly",
    "quarterly",
    "annually",
    name="review_frequency",
    create_type=False,
)


def upgrade() -> None:
    op.create_table(
        "library_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
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
        sa.Column("description", sa.Text(), nullable=True),
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
        "ix_library_documents_id", "library_documents", ["id"], if_not_exists=True
    )

    op.create_table(
        "node_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "node_id",
            sa.Integer(),
            sa.ForeignKey("nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "library_document_id",
            sa.Integer(),
            sa.ForeignKey("library_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "linked_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("linked_by", sa.String(length=255), nullable=True),
        sa.UniqueConstraint(
            "node_id", "library_document_id", name="uq_node_documents_node_doc"
        ),
        if_not_exists=True,
    )
    op.create_index(
        "ix_node_documents_node_id",
        "node_documents",
        ["node_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_node_documents_library_document_id",
        "node_documents",
        ["library_document_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_node_documents_id", "node_documents", ["id"], if_not_exists=True
    )

    # Idempotent data migration: only runs if the old `documents` table is
    # still present. Re-running the migration after a partial failure is safe
    # because the two INSERTs use ON CONFLICT DO NOTHING.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'documents'
            ) THEN
                INSERT INTO library_documents (
                    id, filename, original_filename, file_url, file_size,
                    mime_type, doc_type, tags, owner, review_frequency,
                    last_review_date, next_review_date, version, notes,
                    description, uploaded_at, updated_at
                )
                SELECT
                    id, filename, original_filename, file_url, file_size,
                    mime_type, doc_type, tags, owner, review_frequency,
                    last_review_date, next_review_date, version, notes,
                    NULL, uploaded_at, updated_at
                FROM documents
                ON CONFLICT (id) DO NOTHING;

                INSERT INTO node_documents (
                    node_id, library_document_id, linked_at, linked_by
                )
                SELECT
                    node_id, id, uploaded_at, NULL
                FROM documents
                ON CONFLICT (node_id, library_document_id) DO NOTHING;

                -- Keep the library_documents id sequence in sync with the
                -- highest id we just inserted so future inserts don't collide.
                PERFORM setval(
                    pg_get_serial_sequence('library_documents', 'id'),
                    COALESCE((SELECT MAX(id) FROM library_documents), 1),
                    true
                );

                DROP TABLE documents;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    # We don't restore the old `documents` table on downgrade — the
    # many-to-many model can't be losslessly collapsed back to one-to-one.
    op.drop_index(
        "ix_node_documents_id", table_name="node_documents", if_exists=True
    )
    op.drop_index(
        "ix_node_documents_library_document_id",
        table_name="node_documents",
        if_exists=True,
    )
    op.drop_index(
        "ix_node_documents_node_id", table_name="node_documents", if_exists=True
    )
    op.drop_table("node_documents", if_exists=True)

    op.drop_index(
        "ix_library_documents_id",
        table_name="library_documents",
        if_exists=True,
    )
    op.drop_table("library_documents", if_exists=True)
