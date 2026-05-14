import enum
from datetime import date
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Date,
    Enum,
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

    __table_args__ = (
        CheckConstraint("level >= 1 AND level <= 4", name="ck_nodes_level_range"),
        UniqueConstraint("code", name="uq_nodes_code"),
        Index("ix_nodes_parent_id", "parent_id"),
        Index("ix_nodes_level", "level"),
    )


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    node_id = Column(
        Integer,
        ForeignKey("nodes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # R2 object key (uuid-based) — internal identifier in the bucket.
    filename = Column(String(512), nullable=False)
    # User-facing filename preserved from the upload.
    original_filename = Column(String(512), nullable=False)
    # Stored R2 URL or key path. We presign on demand via the download endpoint.
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

    uploaded_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    node = relationship("Node", backref="documents")
