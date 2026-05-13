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
