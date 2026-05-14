import enum
from datetime import date
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Date,
    Enum,
    Float,
    ForeignKey,
    CheckConstraint,
    Index,
    UniqueConstraint,
    DateTime,
    func,
)
from sqlalchemy.orm import relationship
from database import Base


class ReviewFrequency(str, enum.Enum):
    monthly = "monthly"
    quarterly = "quarterly"
    annually = "annually"


class NodeStatus(str, enum.Enum):
    active = "active"
    under_review = "under_review"
    deprecated = "deprecated"


class DocType(str, enum.Enum):
    procedure = "procedure"
    work_instruction = "work_instruction"
    form = "form"
    certificate = "certificate"
    policy = "policy"
    reference = "reference"
    ci_event = "ci_event"
    audit_report = "audit_report"
    training_record = "training_record"


class ReportingFrequency(str, enum.Enum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    quarterly = "quarterly"
    annually = "annually"


class KpiDirection(str, enum.Enum):
    higher_is_better = "higher_is_better"
    lower_is_better = "lower_is_better"


class Node(Base):
    __tablename__ = "nodes"

    id = Column(Integer, primary_key=True, index=True)
    parent_id = Column(Integer, ForeignKey("nodes.id", ondelete="CASCADE"), nullable=True)
    level = Column(Integer, nullable=False)
    code = Column(String(64), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    owner = Column(String(255), nullable=True)
    review_frequency = Column(Enum(ReviewFrequency, name="review_frequency"), nullable=True)
    last_review_date = Column(Date, nullable=True)
    next_review_date = Column(Date, nullable=True)
    status = Column(
        Enum(NodeStatus, name="node_status"),
        nullable=False,
        default=NodeStatus.active,
        server_default=NodeStatus.active.value,
    )

    linked_procedure_url = Column(Text, nullable=True)
    kpi_name = Column(String(255), nullable=True)
    kpi_target = Column(String(255), nullable=True)
    kpi_current = Column(String(255), nullable=True)

    camunda_process_key = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    parent = relationship("Node", remote_side=[id], backref="children")
    document_links = relationship(
        "NodeDocument",
        back_populates="node",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        CheckConstraint("level >= 1 AND level <= 4", name="ck_nodes_level_range"),
        UniqueConstraint("code", name="uq_nodes_code"),
        Index("ix_nodes_parent_id", "parent_id"),
        Index("ix_nodes_level", "level"),
    )


class LibraryDocument(Base):
    """A document file held in the central library. May be linked to zero,
    one, or many nodes via the `node_documents` join table."""

    __tablename__ = "library_documents"

    id = Column(Integer, primary_key=True, index=True)

    # R2 object key (uuid-based) — internal identifier in the bucket.
    filename = Column(String(512), nullable=False)
    # User-facing filename preserved from the upload.
    original_filename = Column(String(512), nullable=False)
    file_url = Column(Text, nullable=True)
    file_size = Column(Integer, nullable=True)
    mime_type = Column(String(255), nullable=True)

    doc_type = Column(Enum(DocType, name="doc_type"), nullable=False)
    tags = Column(Text, nullable=True)  # comma-separated

    owner = Column(String(255), nullable=True)
    review_frequency = Column(
        Enum(ReviewFrequency, name="review_frequency"), nullable=True
    )
    last_review_date = Column(Date, nullable=True)
    next_review_date = Column(Date, nullable=True)

    version = Column(String(64), nullable=True)
    notes = Column(Text, nullable=True)
    description = Column(Text, nullable=True)

    uploaded_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    node_links = relationship(
        "NodeDocument",
        back_populates="library_document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class NodeDocument(Base):
    """Many-to-many link between a Node and a LibraryDocument."""

    __tablename__ = "node_documents"

    id = Column(Integer, primary_key=True, index=True)
    node_id = Column(
        Integer,
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    library_document_id = Column(
        Integer,
        ForeignKey("library_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    linked_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    linked_by = Column(String(255), nullable=True)

    library_document = relationship("LibraryDocument", back_populates="node_links")
    node = relationship("Node", back_populates="document_links")

    __table_args__ = (
        UniqueConstraint(
            "node_id", "library_document_id", name="uq_node_documents_node_doc"
        ),
    )


class Kpi(Base):
    __tablename__ = "kpis"

    id = Column(Integer, primary_key=True, index=True)
    node_id = Column(
        Integer,
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    calculation_method = Column(Text, nullable=True)
    unit = Column(String(64), nullable=True)
    target_value = Column(Float, nullable=True)
    warning_threshold = Column(Float, nullable=True)
    direction = Column(
        Enum(KpiDirection, name="kpi_direction"),
        nullable=False,
        default=KpiDirection.higher_is_better,
        server_default=KpiDirection.higher_is_better.value,
    )

    owner = Column(String(255), nullable=False)
    reporting_frequency = Column(
        Enum(ReportingFrequency, name="reporting_frequency"), nullable=True
    )
    data_source = Column(Text, nullable=True)
    # Reuses the existing node_status enum (active / under_review / deprecated).
    status = Column(
        Enum(NodeStatus, name="node_status"),
        nullable=False,
        default=NodeStatus.active,
        server_default=NodeStatus.active.value,
    )

    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    node = relationship("Node", backref="kpis")
    entries = relationship(
        "KpiEntry",
        back_populates="kpi",
        cascade="all, delete-orphan",
        order_by="desc(KpiEntry.entered_at)",
    )


class KpiEntry(Base):
    __tablename__ = "kpi_entries"

    id = Column(Integer, primary_key=True, index=True)
    kpi_id = Column(
        Integer,
        ForeignKey("kpis.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    period = Column(String(64), nullable=False)
    actual_value = Column(Float, nullable=False)
    notes = Column(Text, nullable=True)
    entered_by = Column(String(255), nullable=True)
    entered_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    kpi = relationship("Kpi", back_populates="entries")
