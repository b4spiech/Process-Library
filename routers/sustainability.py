"""Sustainability topics (EcoVadis criteria) + node link endpoints."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models import (
    Node,
    NodeSustainabilityTopic,
    SustainabilityTheme,
    SustainabilityTopic,
)
from schemas import SustainabilityTopicRead, SustainabilityTopicUpdate


router = APIRouter(tags=["sustainability"])


def _require_node(db: Session, node_id: int) -> Node:
    node = db.get(Node, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
    return node


def _require_topic(db: Session, topic_id: int) -> SustainabilityTopic:
    topic = db.get(SustainabilityTopic, topic_id)
    if topic is None:
        raise HTTPException(
            status_code=404, detail=f"Sustainability topic {topic_id} not found"
        )
    return topic


def _attach_count(db: Session, topic: SustainabilityTopic) -> SustainabilityTopic:
    topic.linked_nodes_count = (
        db.query(func.count(NodeSustainabilityTopic.id))
        .filter(NodeSustainabilityTopic.topic_id == topic.id)
        .scalar()
        or 0
    )
    return topic


# ---------- Topic management ----------


@router.get(
    "/sustainability/topics", response_model=List[SustainabilityTopicRead]
)
def list_topics(
    theme: Optional[SustainabilityTheme] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(SustainabilityTopic)
    if theme is not None:
        q = q.filter(SustainabilityTopic.theme == theme)
    topics = q.order_by(
        SustainabilityTopic.theme, SustainabilityTopic.name
    ).all()
    for t in topics:
        _attach_count(db, t)
    return topics


@router.get(
    "/sustainability/topics/{topic_id}",
    response_model=SustainabilityTopicRead,
)
def get_topic(topic_id: int, db: Session = Depends(get_db)):
    return _attach_count(db, _require_topic(db, topic_id))


@router.put(
    "/sustainability/topics/{topic_id}",
    response_model=SustainabilityTopicRead,
)
def update_topic(
    topic_id: int,
    payload: SustainabilityTopicUpdate,
    db: Session = Depends(get_db),
):
    topic = _require_topic(db, topic_id)
    # Spec restricts mutable fields — only these four are accepted.
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(topic, k, v)
    db.commit()
    db.refresh(topic)
    return _attach_count(db, topic)


# ---------- Node-topic linking ----------


@router.post(
    "/nodes/{node_id}/sustainability-topics/{topic_id}",
    response_model=SustainabilityTopicRead,
    status_code=status.HTTP_201_CREATED,
)
def link_topic(
    node_id: int,
    topic_id: int,
    linked_by: Optional[str] = Query(None),
    notes: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    _require_node(db, node_id)
    topic = _require_topic(db, topic_id)

    existing = (
        db.query(NodeSustainabilityTopic)
        .filter(
            NodeSustainabilityTopic.node_id == node_id,
            NodeSustainabilityTopic.topic_id == topic_id,
        )
        .first()
    )
    if existing is None:
        link = NodeSustainabilityTopic(
            node_id=node_id,
            topic_id=topic_id,
            linked_by=linked_by,
            notes=notes,
        )
        db.add(link)
        db.commit()
    return _attach_count(db, topic)


@router.delete(
    "/nodes/{node_id}/sustainability-topics/{topic_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def unlink_topic(node_id: int, topic_id: int, db: Session = Depends(get_db)):
    link = (
        db.query(NodeSustainabilityTopic)
        .filter(
            NodeSustainabilityTopic.node_id == node_id,
            NodeSustainabilityTopic.topic_id == topic_id,
        )
        .first()
    )
    if link is None:
        raise HTTPException(
            status_code=404,
            detail=f"No link between node {node_id} and topic {topic_id}",
        )
    db.delete(link)
    db.commit()
    return None


@router.get(
    "/nodes/{node_id}/sustainability-topics",
    response_model=List[SustainabilityTopicRead],
)
def list_node_topics(node_id: int, db: Session = Depends(get_db)):
    _require_node(db, node_id)
    topics = (
        db.query(SustainabilityTopic)
        .join(
            NodeSustainabilityTopic,
            NodeSustainabilityTopic.topic_id == SustainabilityTopic.id,
        )
        .filter(NodeSustainabilityTopic.node_id == node_id)
        .order_by(SustainabilityTopic.theme, SustainabilityTopic.name)
        .all()
    )
    for t in topics:
        _attach_count(db, t)
    return topics
