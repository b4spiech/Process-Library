"""Sustainability themes + criteria + node-link endpoints.

Themes are now first-class rows (not an enum) so users can add, rename,
recolor, and delete them. Each criterion (`SustainabilityTopic`) belongs
to exactly one theme via `theme_id`; deleting a theme cascades to its
criteria and node-links.
"""
from __future__ import annotations

import re
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import (
    Node,
    NodeSustainabilityTopic,
    SustainabilityTheme,
    SustainabilityTopic,
)
from schemas import (
    SustainabilityThemeCreate,
    SustainabilityThemeRead,
    SustainabilityThemeUpdate,
    SustainabilityTopicCreate,
    SustainabilityTopicRead,
    SustainabilityTopicUpdate,
)


router = APIRouter(tags=["sustainability"])


# ---------- helpers ----------


def _require_node(db: Session, node_id: int) -> Node:
    node = db.get(Node, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
    return node


def _require_topic(db: Session, topic_id: int) -> SustainabilityTopic:
    topic = (
        db.query(SustainabilityTopic)
        .options(joinedload(SustainabilityTopic.theme))
        .filter(SustainabilityTopic.id == topic_id)
        .first()
    )
    if topic is None:
        raise HTTPException(
            status_code=404, detail=f"Sustainability topic {topic_id} not found"
        )
    return topic


def _require_theme(db: Session, theme_id: int) -> SustainabilityTheme:
    theme = db.get(SustainabilityTheme, theme_id)
    if theme is None:
        raise HTTPException(
            status_code=404, detail=f"Sustainability theme {theme_id} not found"
        )
    return theme


def _attach_topic_count(
    db: Session, topic: SustainabilityTopic
) -> SustainabilityTopic:
    topic.linked_nodes_count = (
        db.query(func.count(NodeSustainabilityTopic.id))
        .filter(NodeSustainabilityTopic.topic_id == topic.id)
        .scalar()
        or 0
    )
    return topic


def _attach_theme_count(
    db: Session, theme: SustainabilityTheme
) -> SustainabilityTheme:
    theme.topics_count = (
        db.query(func.count(SustainabilityTopic.id))
        .filter(SustainabilityTopic.theme_id == theme.id)
        .scalar()
        or 0
    )
    return theme


def _slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")
    return base or f"theme_{uuid.uuid4().hex[:8]}"


# ---------- Theme CRUD ----------


@router.get(
    "/sustainability/themes", response_model=List[SustainabilityThemeRead]
)
def list_themes(db: Session = Depends(get_db)):
    themes = (
        db.query(SustainabilityTheme)
        .order_by(SustainabilityTheme.id)
        .all()
    )
    for t in themes:
        _attach_theme_count(db, t)
    return themes


@router.post(
    "/sustainability/themes",
    response_model=SustainabilityThemeRead,
    status_code=status.HTTP_201_CREATED,
)
def create_theme(
    payload: SustainabilityThemeCreate, db: Session = Depends(get_db)
):
    # Generate a unique slug from the name; fall back to random if collisions.
    base = _slugify(payload.name)
    slug = base
    n = 2
    while db.query(SustainabilityTheme).filter_by(slug=slug).first() is not None:
        slug = f"{base}_{n}"
        n += 1

    theme = SustainabilityTheme(
        slug=slug,
        name=payload.name,
        description=payload.description,
        color=payload.color,
        is_builtin=False,
    )
    db.add(theme)
    db.commit()
    db.refresh(theme)
    return _attach_theme_count(db, theme)


@router.put(
    "/sustainability/themes/{theme_id}",
    response_model=SustainabilityThemeRead,
)
def update_theme(
    theme_id: int,
    payload: SustainabilityThemeUpdate,
    db: Session = Depends(get_db),
):
    theme = _require_theme(db, theme_id)
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(theme, k, v)
    db.commit()
    db.refresh(theme)
    return _attach_theme_count(db, theme)


@router.delete(
    "/sustainability/themes/{theme_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_theme(theme_id: int, db: Session = Depends(get_db)):
    theme = _require_theme(db, theme_id)
    # ORM cascade removes topics + the join rows under them.
    db.delete(theme)
    db.commit()
    return None


# ---------- Topic CRUD ----------


@router.get(
    "/sustainability/topics", response_model=List[SustainabilityTopicRead]
)
def list_topics(
    theme_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(SustainabilityTopic).options(
        joinedload(SustainabilityTopic.theme)
    )
    if theme_id is not None:
        q = q.filter(SustainabilityTopic.theme_id == theme_id)
    topics = q.order_by(
        SustainabilityTopic.theme_id, SustainabilityTopic.name
    ).all()
    for t in topics:
        _attach_topic_count(db, t)
    return topics


@router.post(
    "/sustainability/topics",
    response_model=SustainabilityTopicRead,
    status_code=status.HTTP_201_CREATED,
)
def create_topic(
    payload: SustainabilityTopicCreate, db: Session = Depends(get_db)
):
    _require_theme(db, payload.theme_id)
    topic = SustainabilityTopic(**payload.model_dump())
    db.add(topic)
    db.commit()
    db.refresh(topic)
    # Reload with theme joined for the response.
    return _attach_topic_count(db, _require_topic(db, topic.id))


@router.get(
    "/sustainability/topics/{topic_id}",
    response_model=SustainabilityTopicRead,
)
def get_topic(topic_id: int, db: Session = Depends(get_db)):
    return _attach_topic_count(db, _require_topic(db, topic_id))


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
    data = payload.model_dump(exclude_unset=True)
    if "theme_id" in data:
        _require_theme(db, data["theme_id"])
    for k, v in data.items():
        setattr(topic, k, v)
    db.commit()
    db.refresh(topic)
    return _attach_topic_count(db, _require_topic(db, topic.id))


@router.delete(
    "/sustainability/topics/{topic_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_topic(topic_id: int, db: Session = Depends(get_db)):
    topic = _require_topic(db, topic_id)
    # ORM cascade removes node-link rows under this topic.
    db.delete(topic)
    db.commit()
    return None


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
    return _attach_topic_count(db, topic)


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
        .options(joinedload(SustainabilityTopic.theme))
        .join(
            NodeSustainabilityTopic,
            NodeSustainabilityTopic.topic_id == SustainabilityTopic.id,
        )
        .filter(NodeSustainabilityTopic.node_id == node_id)
        .order_by(SustainabilityTopic.theme_id, SustainabilityTopic.name)
        .all()
    )
    for t in topics:
        _attach_topic_count(db, t)
    return topics
