from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from models import (
    ReviewFrequency,
    NodeStatus,
    DocType,
    ReportingFrequency,
    KpiDirection,
    SustainabilityStatus,
)


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


# ---------- Library documents & node links ----------


class NodeRef(BaseModel):
    """Minimal node reference used inside LibraryDocumentReadWithNodes."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    level: int


class LibraryDocumentBase(BaseModel):
    doc_type: DocType
    tags: Optional[str] = None
    owner: Optional[str] = None
    review_frequency: Optional[ReviewFrequency] = None
    last_review_date: Optional[date] = None
    next_review_date: Optional[date] = None
    version: Optional[str] = None
    notes: Optional[str] = None
    description: Optional[str] = None


class LibraryDocumentUpdate(BaseModel):
    doc_type: Optional[DocType] = None
    tags: Optional[str] = None
    owner: Optional[str] = None
    review_frequency: Optional[ReviewFrequency] = None
    last_review_date: Optional[date] = None
    next_review_date: Optional[date] = None
    version: Optional[str] = None
    notes: Optional[str] = None
    description: Optional[str] = None


class LibraryDocumentRead(LibraryDocumentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    original_filename: str
    file_url: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    uploaded_at: datetime
    updated_at: datetime
    # Populated by list/get endpoints so the UI can render counts cheaply.
    linked_nodes_count: int = 0


class LibraryDocumentReadWithNodes(LibraryDocumentRead):
    linked_nodes: List[NodeRef] = []


class DocumentDownloadUrl(BaseModel):
    url: str
    expires_in: int


# ---------- KPIs ----------


class KpiEntryBase(BaseModel):
    period: str = Field(..., max_length=64)
    actual_value: float
    notes: Optional[str] = None
    entered_by: Optional[str] = None


class KpiEntryCreate(KpiEntryBase):
    pass


class KpiEntryUpdate(BaseModel):
    period: Optional[str] = Field(None, max_length=64)
    actual_value: Optional[float] = None
    notes: Optional[str] = None
    entered_by: Optional[str] = None


class KpiEntryRead(KpiEntryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kpi_id: int
    entered_at: datetime


class KpiBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    calculation_method: Optional[str] = None
    unit: Optional[str] = Field(None, max_length=64)
    target_value: Optional[float] = None
    warning_threshold: Optional[float] = None
    direction: KpiDirection = KpiDirection.higher_is_better
    owner: str = Field(..., max_length=255)
    reporting_frequency: Optional[ReportingFrequency] = None
    data_source: Optional[str] = None
    status: NodeStatus = NodeStatus.active


class KpiCreate(KpiBase):
    pass


class KpiUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    calculation_method: Optional[str] = None
    unit: Optional[str] = Field(None, max_length=64)
    target_value: Optional[float] = None
    warning_threshold: Optional[float] = None
    direction: Optional[KpiDirection] = None
    owner: Optional[str] = Field(None, max_length=255)
    reporting_frequency: Optional[ReportingFrequency] = None
    data_source: Optional[str] = None
    status: Optional[NodeStatus] = None


class KpiRead(KpiBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    node_id: int
    created_at: datetime
    updated_at: datetime
    # Populated by the list endpoint so tile summaries can compute status
    # without an extra round trip per KPI. May be None when no entries exist.
    latest_entry: Optional[KpiEntryRead] = None


# ---------- Sustainability themes & topics ----------


class SustainabilityThemeBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    color: Optional[str] = Field(None, max_length=32)


class SustainabilityThemeCreate(SustainabilityThemeBase):
    pass


class SustainabilityThemeUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    color: Optional[str] = Field(None, max_length=32)


class SustainabilityThemeRead(SustainabilityThemeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    is_builtin: bool
    created_at: datetime
    updated_at: datetime
    topics_count: int = 0


class SustainabilityTopicBase(BaseModel):
    theme_id: int
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    ecovadis_criterion: Optional[str] = None
    why_it_matters: Optional[str] = None
    evidence_examples: Optional[str] = None
    weight: float = 1.0
    is_activated: bool = True
    owner: Optional[str] = None
    status: SustainabilityStatus = SustainabilityStatus.active
    notes: Optional[str] = None


class SustainabilityTopicCreate(SustainabilityTopicBase):
    pass


class SustainabilityTopicUpdate(BaseModel):
    # All fields editable now that themes/criteria are user-managed.
    theme_id: Optional[int] = None
    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    ecovadis_criterion: Optional[str] = None
    why_it_matters: Optional[str] = None
    evidence_examples: Optional[str] = None
    weight: Optional[float] = None
    is_activated: Optional[bool] = None
    owner: Optional[str] = None
    status: Optional[SustainabilityStatus] = None
    notes: Optional[str] = None


class SustainabilityTopicRead(SustainabilityTopicBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    # Nested theme so the UI can paint pills with theme.color directly.
    theme: Optional[SustainabilityThemeRead] = None
    # Computed by list/get endpoints so the UI can show per-topic node counts.
    linked_nodes_count: int = 0
