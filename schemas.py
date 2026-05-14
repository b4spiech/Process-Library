from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from models import ReviewFrequency, NodeStatus, DocType


class NodeBase(BaseModel):
    parent_id: Optional[int] = None
    level: int = Field(..., ge=1, le=4)
    code: str = Field(..., max_length=64)
    name: str = Field(..., max_length=255)
    description: Optional[str] = None

    owner: Optional[str] = None
    review_frequency: Optional[ReviewFrequency] = None
    last_review_date: Optional[date] = None
    status: NodeStatus = NodeStatus.active

    linked_procedure_url: Optional[str] = None
    kpi_name: Optional[str] = None
    kpi_target: Optional[str] = None
    kpi_current: Optional[str] = None

    camunda_process_key: Optional[str] = None


class NodeCreate(NodeBase):
    pass


class NodeUpdate(BaseModel):
    parent_id: Optional[int] = None
    level: Optional[int] = Field(None, ge=1, le=4)
    code: Optional[str] = Field(None, max_length=64)
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None

    owner: Optional[str] = None
    review_frequency: Optional[ReviewFrequency] = None
    last_review_date: Optional[date] = None
    status: Optional[NodeStatus] = None

    linked_procedure_url: Optional[str] = None
    kpi_name: Optional[str] = None
    kpi_target: Optional[str] = None
    kpi_current: Optional[str] = None

    camunda_process_key: Optional[str] = None


class NodeRead(NodeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    next_review_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime


class NodeTree(NodeRead):
    children: List["NodeTree"] = []


NodeTree.model_rebuild()


# ---------- Documents ----------


class DocumentBase(BaseModel):
    doc_type: DocType
    tags: Optional[str] = None
    owner: Optional[str] = None
    review_frequency: Optional[ReviewFrequency] = None
    last_review_date: Optional[date] = None
    next_review_date: Optional[date] = None
    version: Optional[str] = None
    notes: Optional[str] = None


class DocumentUpdate(BaseModel):
    doc_type: Optional[DocType] = None
    tags: Optional[str] = None
    owner: Optional[str] = None
    review_frequency: Optional[ReviewFrequency] = None
    last_review_date: Optional[date] = None
    next_review_date: Optional[date] = None
    version: Optional[str] = None
    notes: Optional[str] = None


class DocumentRead(DocumentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    node_id: int
    filename: str
    original_filename: str
    file_url: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    uploaded_at: datetime
    updated_at: datetime


class DocumentDownloadUrl(BaseModel):
    url: str
    expires_in: int
