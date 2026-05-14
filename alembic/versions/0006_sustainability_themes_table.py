"""Move sustainability theme from enum to first-class table

Revision ID: 0006_sustainability_themes_table
Revises: 0005_sustainability
Create Date: 2026-05-14 00:00:00

Refactors the `sustainability_theme` PG enum into a proper
`sustainability_themes` table so themes are CRUD-able. The four EcoVadis
themes are seeded as `is_builtin=true` with their original colors, the
existing `sustainability_topics.theme` enum column is migrated to a
`theme_id` FK, then the old column + enum are dropped. The whole data
move is wrapped in a DO block that runs only if the old column still
exists, so the migration is safe to retry.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006_sustainability_themes_table"
down_revision: Union[str, None] = "0005_sustainability"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


BUILTIN_THEMES = [
    # id, slug, name, description, color
    (1, "environment",             "Environment",             "Environmental impacts of operations and products.", "#15803d"),
    (2, "labor_human_rights",      "Labor & Human Rights",    "Workforce conditions, safety, and human-rights protections.", "#1d4ed8"),
    (3, "ethics",                  "Ethics",                  "Business ethics, anti-corruption, and compliance.", "#7e22ce"),
    (4, "sustainable_procurement", "Sustainable Procurement", "Sustainability requirements and oversight in the supply chain.", "#c2410c"),
]


def upgrade() -> None:
    op.create_table(
        "sustainability_themes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("color", sa.String(length=32), nullable=True),
        sa.Column(
            "is_builtin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
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
        sa.UniqueConstraint("slug", name="uq_sustainability_themes_slug"),
        if_not_exists=True,
    )
    op.create_index(
        "ix_sustainability_themes_id",
        "sustainability_themes",
        ["id"],
        if_not_exists=True,
    )

    # Seed the four builtin themes with predictable ids matching the
    # historical enum ordering. ON CONFLICT keeps this idempotent.
    conn = op.get_bind()
    insert_sql = sa.text(
        """
        INSERT INTO sustainability_themes (id, slug, name, description, color, is_builtin)
        VALUES (:id, :slug, :name, :description, :color, true)
        ON CONFLICT (slug) DO NOTHING
        """
    )
    for tid, slug, name, desc, color in BUILTIN_THEMES:
        conn.execute(
            insert_sql,
            {"id": tid, "slug": slug, "name": name, "description": desc, "color": color},
        )

    # Keep the sequence ahead of the seeded ids so future inserts don't collide.
    conn.execute(
        sa.text(
            """
            SELECT setval(
                pg_get_serial_sequence('sustainability_themes', 'id'),
                COALESCE((SELECT MAX(id) FROM sustainability_themes), 1),
                true
            )
            """
        )
    )

    # Migrate topic rows: enum theme -> theme_id FK.
    op.execute(
        """
        DO $$
        BEGIN
            -- Only run the migration if the old enum column still exists.
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'sustainability_topics'
                  AND column_name = 'theme'
            ) THEN
                ALTER TABLE sustainability_topics
                    ADD COLUMN IF NOT EXISTS theme_id INTEGER;

                UPDATE sustainability_topics t
                SET theme_id = th.id
                FROM sustainability_themes th
                WHERE th.slug = t.theme::text
                  AND t.theme_id IS NULL;

                ALTER TABLE sustainability_topics
                    ALTER COLUMN theme_id SET NOT NULL;

                ALTER TABLE sustainability_topics
                    ADD CONSTRAINT fk_sustainability_topics_theme_id
                    FOREIGN KEY (theme_id)
                    REFERENCES sustainability_themes(id)
                    ON DELETE CASCADE;

                CREATE INDEX IF NOT EXISTS ix_sustainability_topics_theme_id
                    ON sustainability_topics (theme_id);

                ALTER TABLE sustainability_topics DROP COLUMN theme;
            END IF;
        END $$;
        """
    )

    # The old enum is no longer referenced anywhere; drop it.
    op.execute("DROP TYPE IF EXISTS sustainability_theme")


def downgrade() -> None:
    # Recreate the enum and the old column populated from theme_id->slug.
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE sustainability_theme AS ENUM (
                'environment', 'labor_human_rights', 'ethics',
                'sustainable_procurement'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'sustainability_topics'
                  AND column_name = 'theme'
            ) THEN
                ALTER TABLE sustainability_topics
                    ADD COLUMN theme sustainability_theme;

                UPDATE sustainability_topics t
                SET theme = th.slug::sustainability_theme
                FROM sustainability_themes th
                WHERE th.id = t.theme_id;

                ALTER TABLE sustainability_topics
                    ALTER COLUMN theme SET NOT NULL;

                ALTER TABLE sustainability_topics
                    DROP CONSTRAINT IF EXISTS fk_sustainability_topics_theme_id;

                DROP INDEX IF EXISTS ix_sustainability_topics_theme_id;

                ALTER TABLE sustainability_topics DROP COLUMN theme_id;
            END IF;
        END $$;
        """
    )
    op.drop_index(
        "ix_sustainability_themes_id",
        table_name="sustainability_themes",
        if_exists=True,
    )
    op.drop_table("sustainability_themes", if_exists=True)
