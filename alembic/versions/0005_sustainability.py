"""sustainability_topics + node_sustainability_topics (+ seed EcoVadis criteria)

Revision ID: 0005_sustainability
Revises: 0004_library_documents
Create Date: 2026-05-14 00:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0005_sustainability"
down_revision: Union[str, None] = "0004_library_documents"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


sustainability_theme_enum = postgresql.ENUM(
    "environment",
    "labor_human_rights",
    "ethics",
    "sustainable_procurement",
    name="sustainability_theme",
    create_type=False,
)
sustainability_status_enum = postgresql.ENUM(
    "active",
    "under_review",
    "not_applicable",
    name="sustainability_status",
    create_type=False,
)


# 21 EcoVadis criteria. Reference data, idempotent via ON CONFLICT (name).
TOPICS = [
    # Environment ------------------------------------------------------
    {
        "theme": "environment",
        "name": "Energy & GHG Emissions",
        "description": "Energy consumption management and greenhouse gas emissions reduction.",
        "ecovadis_criterion": "Energy & GHG Emissions",
        "why_it_matters": "Energy use and greenhouse gas emissions drive climate risk, regulatory exposure, and operating cost. Customers and investors increasingly require credible carbon data.",
        "evidence_examples": "Energy audits, Scope 1/2/3 emissions inventory, reduction targets, utility consumption records, renewable energy contracts.",
    },
    {
        "theme": "environment",
        "name": "Water",
        "description": "Water consumption and wastewater management.",
        "ecovadis_criterion": "Water",
        "why_it_matters": "Water scarcity affects operations in drought-prone regions and is a growing factor in supplier and customer decisions.",
        "evidence_examples": "Water-use baselines, wastewater treatment records, leak-detection procedures, recycling / reuse initiatives.",
    },
    {
        "theme": "environment",
        "name": "Biodiversity",
        "description": "Protection of ecosystems and biodiversity.",
        "ecovadis_criterion": "Biodiversity",
        "why_it_matters": "Operations can impact local ecosystems through land use, runoff, and habitat disturbance — regulators and customers care.",
        "evidence_examples": "Site environmental impact assessments, biodiversity action plans, land-use surveys, restoration projects.",
    },
    {
        "theme": "environment",
        "name": "Pollution & Waste",
        "description": "Prevention of pollution and waste management.",
        "ecovadis_criterion": "Pollution & Waste",
        "why_it_matters": "Pollution and waste generation create regulatory exposure, fines, and reputational risk. Waste reduction also lowers operating cost.",
        "evidence_examples": "Waste-stream inventories, recycling programs, hazardous-waste manifests, air-emissions permits, spill response plans.",
    },
    {
        "theme": "environment",
        "name": "Hazardous Materials",
        "description": "Management of hazardous substances and chemicals.",
        "ecovadis_criterion": "Hazardous Materials",
        "why_it_matters": "Improper handling of hazardous chemicals causes worker injury, environmental contamination, and regulatory action.",
        "evidence_examples": "SDS (Safety Data Sheets) library, chemical inventory, storage and handling procedures, training records, REACH / RoHS compliance.",
    },
    {
        "theme": "environment",
        "name": "Product Use Impact",
        "description": "Environmental impact of products during customer use.",
        "ecovadis_criterion": "Product Use Impact",
        "why_it_matters": "Products that consume energy, water, or materials during use have environmental footprints customers increasingly evaluate.",
        "evidence_examples": "Energy-efficiency ratings, product life-cycle assessments, eco-design specifications, customer education materials.",
    },
    {
        "theme": "environment",
        "name": "Product End-of-Life",
        "description": "Environmental impact at end of product lifecycle.",
        "ecovadis_criterion": "Product End-of-Life",
        "why_it_matters": "End-of-life recovery is regulated in many jurisdictions and is a key differentiator for sustainability-minded customers.",
        "evidence_examples": "Take-back programs, recycling instructions, material disclosures, WEEE / EPR compliance records.",
    },
    # Labor & Human Rights --------------------------------------------
    {
        "theme": "labor_human_rights",
        "name": "Health & Safety",
        "description": "Accident prevention and employee safety programs.",
        "ecovadis_criterion": "Health & Safety",
        "why_it_matters": "Accident prevention protects workers, reduces lost-time injuries and insurance cost, and is a customer expectation.",
        "evidence_examples": "OSHA logs, safety procedures, training records, near-miss tracking, safety committee minutes, PPE inventories.",
    },
    {
        "theme": "labor_human_rights",
        "name": "Working Conditions",
        "description": "Fair working hours, compensation, and conditions.",
        "ecovadis_criterion": "Working Conditions",
        "why_it_matters": "Fair pay, reasonable hours, and humane conditions are baseline expectations for employees, customers, and regulators.",
        "evidence_examples": "Compensation policies, timekeeping records, employee handbooks, exit interview summaries.",
    },
    {
        "theme": "labor_human_rights",
        "name": "Social Dialogue",
        "description": "Freedom of association and collective bargaining.",
        "ecovadis_criterion": "Social Dialogue",
        "why_it_matters": "Open communication channels and the right to collectively organize are core labor-rights principles.",
        "evidence_examples": "Union recognition records, works-council minutes, employee surveys, grievance procedures.",
    },
    {
        "theme": "labor_human_rights",
        "name": "Diversity & Inclusion",
        "description": "Equal opportunity and non-discrimination policies.",
        "ecovadis_criterion": "Diversity & Inclusion",
        "why_it_matters": "Equal opportunity employment is both a legal requirement and a measurable performance driver.",
        "evidence_examples": "EEO policies, diversity metrics, recruitment programs, ERG (employee resource group) charters, training records.",
    },
    {
        "theme": "labor_human_rights",
        "name": "Training & Development",
        "description": "Employee skills development and career growth.",
        "ecovadis_criterion": "Training & Development",
        "why_it_matters": "Investment in employee skills supports retention, productivity, and succession planning.",
        "evidence_examples": "Training plans, individual development plans, training hours per FTE, certification records, performance reviews.",
    },
    {
        "theme": "labor_human_rights",
        "name": "Human Rights",
        "description": "Prevention of forced labor, child labor, and discrimination.",
        "ecovadis_criterion": "Human Rights",
        "why_it_matters": "Prevention of forced labor, child labor, and discrimination is a baseline expectation across all customers and regulators.",
        "evidence_examples": "Code of Conduct, supplier due-diligence records, Modern Slavery Act statements, grievance mechanisms.",
    },
    # Ethics -----------------------------------------------------------
    {
        "theme": "ethics",
        "name": "Anti-Corruption & Bribery",
        "description": "Prevention of corruption and bribery practices.",
        "ecovadis_criterion": "Anti-Corruption & Bribery",
        "why_it_matters": "Bribery exposes the company to criminal liability under FCPA / UK Bribery Act and devastates reputation.",
        "evidence_examples": "Anti-bribery policy, gifts and hospitality register, due-diligence on third parties, training records.",
    },
    {
        "theme": "ethics",
        "name": "Anti-Competitive Practices",
        "description": "Fair competition and antitrust compliance.",
        "ecovadis_criterion": "Anti-Competitive Practices",
        "why_it_matters": "Antitrust violations carry severe penalties and can shut down operations in regulated markets.",
        "evidence_examples": "Antitrust policy, training records, competitive-intelligence guidelines, communication protocols.",
    },
    {
        "theme": "ethics",
        "name": "Responsible Information Management",
        "description": "Data privacy and information security.",
        "ecovadis_criterion": "Responsible Information Management",
        "why_it_matters": "Customer and employee data must be protected under GDPR, CCPA, and similar regulations; breaches are costly.",
        "evidence_examples": "Privacy policies, data-classification standards, access controls, breach response plans, DPA agreements.",
    },
    {
        "theme": "ethics",
        "name": "Whistleblower Protection",
        "description": "Mechanisms for reporting misconduct safely.",
        "ecovadis_criterion": "Whistleblower Protection",
        "why_it_matters": "Confidential reporting channels surface issues early before they escalate and demonstrate ethical commitment.",
        "evidence_examples": "Whistleblower policy, hotline records, investigation procedures, non-retaliation commitments.",
    },
    # Sustainable Procurement -----------------------------------------
    {
        "theme": "sustainable_procurement",
        "name": "Supplier Environmental Practices",
        "description": "Environmental requirements in supplier selection.",
        "ecovadis_criterion": "Supplier Environmental Practices",
        "why_it_matters": "Most of a company's footprint sits in its supply chain — managing supplier environmental practices is the highest-leverage move.",
        "evidence_examples": "Supplier sustainability surveys, environmental clauses in contracts, audit results, capacity-building programs.",
    },
    {
        "theme": "sustainable_procurement",
        "name": "Supplier Social Practices",
        "description": "Social and labor requirements for suppliers.",
        "ecovadis_criterion": "Supplier Social Practices",
        "why_it_matters": "Suppliers are an extension of the company — their labor practices reflect on the brand.",
        "evidence_examples": "Supplier labor-practice surveys, social audits, remediation plans, ethical sourcing certifications.",
    },
    {
        "theme": "sustainable_procurement",
        "name": "Supplier Code of Conduct",
        "description": "Formal supplier code of conduct and communication.",
        "ecovadis_criterion": "Supplier Code of Conduct",
        "why_it_matters": "A documented Supplier Code makes expectations explicit and is the foundation for enforcement.",
        "evidence_examples": "Supplier Code of Conduct, signed acknowledgments, communication records, contract clauses.",
    },
    {
        "theme": "sustainable_procurement",
        "name": "Supplier Assessment & Monitoring",
        "description": "Ongoing supplier sustainability audits and monitoring.",
        "ecovadis_criterion": "Supplier Assessment & Monitoring",
        "why_it_matters": "Without ongoing monitoring, supplier commitments don't translate into actual practice.",
        "evidence_examples": "Supplier risk assessments, audit schedules, scorecards, non-conformance reports, corrective-action plans.",
    },
]


def upgrade() -> None:
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
        DO $$ BEGIN
            CREATE TYPE sustainability_status AS ENUM (
                'active', 'under_review', 'not_applicable'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )

    op.create_table(
        "sustainability_topics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("theme", sustainability_theme_enum, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("ecovadis_criterion", sa.String(length=255), nullable=True),
        sa.Column("why_it_matters", sa.Text(), nullable=True),
        sa.Column("evidence_examples", sa.Text(), nullable=True),
        sa.Column(
            "weight", sa.Float(), nullable=False, server_default="1.0"
        ),
        sa.Column(
            "is_activated",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("owner", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            sustainability_status_enum,
            nullable=False,
            server_default="active",
        ),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.UniqueConstraint("name", name="uq_sustainability_topics_name"),
        if_not_exists=True,
    )
    op.create_index(
        "ix_sustainability_topics_id",
        "sustainability_topics",
        ["id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_sustainability_topics_theme",
        "sustainability_topics",
        ["theme"],
        if_not_exists=True,
    )

    op.create_table(
        "node_sustainability_topics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "node_id",
            sa.Integer(),
            sa.ForeignKey("nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "topic_id",
            sa.Integer(),
            sa.ForeignKey("sustainability_topics.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "linked_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("linked_by", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint(
            "node_id",
            "topic_id",
            name="uq_node_sustainability_topics_node_topic",
        ),
        if_not_exists=True,
    )
    op.create_index(
        "ix_node_sustainability_topics_node_id",
        "node_sustainability_topics",
        ["node_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_node_sustainability_topics_topic_id",
        "node_sustainability_topics",
        ["topic_id"],
        if_not_exists=True,
    )
    op.create_index(
        "ix_node_sustainability_topics_id",
        "node_sustainability_topics",
        ["id"],
        if_not_exists=True,
    )

    # Seed the 21 EcoVadis criteria. Idempotent via ON CONFLICT (name).
    conn = op.get_bind()
    insert_sql = sa.text(
        """
        INSERT INTO sustainability_topics
            (theme, name, description, ecovadis_criterion,
             why_it_matters, evidence_examples)
        VALUES
            (CAST(:theme AS sustainability_theme),
             :name, :description, :ecovadis_criterion,
             :why_it_matters, :evidence_examples)
        ON CONFLICT (name) DO NOTHING
        """
    )
    for t in TOPICS:
        conn.execute(insert_sql, t)


def downgrade() -> None:
    op.drop_index(
        "ix_node_sustainability_topics_id",
        table_name="node_sustainability_topics",
        if_exists=True,
    )
    op.drop_index(
        "ix_node_sustainability_topics_topic_id",
        table_name="node_sustainability_topics",
        if_exists=True,
    )
    op.drop_index(
        "ix_node_sustainability_topics_node_id",
        table_name="node_sustainability_topics",
        if_exists=True,
    )
    op.drop_table("node_sustainability_topics", if_exists=True)

    op.drop_index(
        "ix_sustainability_topics_theme",
        table_name="sustainability_topics",
        if_exists=True,
    )
    op.drop_index(
        "ix_sustainability_topics_id",
        table_name="sustainability_topics",
        if_exists=True,
    )
    op.drop_table("sustainability_topics", if_exists=True)

    op.execute("DROP TYPE IF EXISTS sustainability_status")
    op.execute("DROP TYPE IF EXISTS sustainability_theme")
