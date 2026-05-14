"""KPI definitions and KPI data entry endpoints."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import Kpi, KpiEntry, Node
from schemas import (
    KpiCreate,
    KpiEntryCreate,
    KpiEntryRead,
    KpiEntryUpdate,
    KpiRead,
    KpiUpdate,
)


router = APIRouter(tags=["kpis"])


def _require_node(db: Session, node_id: int) -> Node:
    node = db.get(Node, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
    return node


def _require_kpi(db: Session, kpi_id: int) -> Kpi:
    kpi = db.get(Kpi, kpi_id)
    if kpi is None:
        raise HTTPException(status_code=404, detail=f"KPI {kpi_id} not found")
    return kpi


def _require_entry(db: Session, entry_id: int) -> KpiEntry:
    entry = db.get(KpiEntry, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"KPI entry {entry_id} not found")
    return entry


def _attach_latest(db: Session, kpi: Kpi) -> Kpi:
    """Attach the most recent KpiEntry as a transient `latest_entry` attribute.
    Pydantic's from_attributes mode picks it up so the API response shape matches
    schemas.KpiRead.latest_entry."""
    kpi.latest_entry = (
        db.query(KpiEntry)
        .filter(KpiEntry.kpi_id == kpi.id)
        .order_by(KpiEntry.entered_at.desc())
        .first()
    )
    return kpi


# ---------- KPI definitions ----------


@router.post(
    "/nodes/{node_id}/kpis",
    response_model=KpiRead,
    status_code=status.HTTP_201_CREATED,
)
def create_kpi(node_id: int, payload: KpiCreate, db: Session = Depends(get_db)):
    _require_node(db, node_id)
    kpi = Kpi(node_id=node_id, **payload.model_dump())
    db.add(kpi)
    db.commit()
    db.refresh(kpi)
    return _attach_latest(db, kpi)


@router.get("/nodes/{node_id}/kpis", response_model=List[KpiRead])
def list_node_kpis(node_id: int, db: Session = Depends(get_db)):
    _require_node(db, node_id)
    kpis = (
        db.query(Kpi)
        .filter(Kpi.node_id == node_id)
        .order_by(Kpi.created_at)
        .all()
    )
    for k in kpis:
        _attach_latest(db, k)
    return kpis


@router.get("/kpis/{kpi_id}", response_model=KpiRead)
def get_kpi(kpi_id: int, db: Session = Depends(get_db)):
    return _attach_latest(db, _require_kpi(db, kpi_id))


@router.put("/kpis/{kpi_id}", response_model=KpiRead)
def update_kpi(
    kpi_id: int, payload: KpiUpdate, db: Session = Depends(get_db)
):
    kpi = _require_kpi(db, kpi_id)
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(kpi, k, v)
    db.commit()
    db.refresh(kpi)
    return _attach_latest(db, kpi)


@router.delete("/kpis/{kpi_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_kpi(kpi_id: int, db: Session = Depends(get_db)):
    kpi = _require_kpi(db, kpi_id)
    db.delete(kpi)  # ORM cascade removes KpiEntry rows
    db.commit()
    return None


# ---------- KPI data entries ----------


@router.post(
    "/kpis/{kpi_id}/entries",
    response_model=KpiEntryRead,
    status_code=status.HTTP_201_CREATED,
)
def create_entry(
    kpi_id: int, payload: KpiEntryCreate, db: Session = Depends(get_db)
):
    _require_kpi(db, kpi_id)
    entry = KpiEntry(kpi_id=kpi_id, **payload.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/kpis/{kpi_id}/entries", response_model=List[KpiEntryRead])
def list_entries(kpi_id: int, db: Session = Depends(get_db)):
    _require_kpi(db, kpi_id)
    return (
        db.query(KpiEntry)
        .filter(KpiEntry.kpi_id == kpi_id)
        .order_by(KpiEntry.entered_at.desc())
        .all()
    )


@router.put("/kpi-entries/{entry_id}", response_model=KpiEntryRead)
def update_entry(
    entry_id: int, payload: KpiEntryUpdate, db: Session = Depends(get_db)
):
    entry = _require_entry(db, entry_id)
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(entry, k, v)
    db.commit()
    db.refresh(entry)
    return entry


@router.delete(
    "/kpi-entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_entry(entry_id: int, db: Session = Depends(get_db)):
    entry = _require_entry(db, entry_id)
    db.delete(entry)
    db.commit()
    return None
