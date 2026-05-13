from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import Node
from schemas import NodeCreate, NodeRead, NodeTree, NodeUpdate
from utils import compute_next_review_date

router = APIRouter(prefix="/nodes", tags=["nodes"])


def _build_tree(nodes: List[Node]) -> List[Dict[str, Any]]:
    by_id: Dict[int, Dict[str, Any]] = {}
    for n in nodes:
        by_id[n.id] = NodeRead.model_validate(n).model_dump(mode="json")
        by_id[n.id]["children"] = []

    roots: List[Dict[str, Any]] = []
    for n in nodes:
        node_dict = by_id[n.id]
        if n.parent_id is None:
            roots.append(node_dict)
        else:
            parent = by_id.get(n.parent_id)
            if parent is not None:
                parent["children"].append(node_dict)
            else:
                roots.append(node_dict)

    def sort_children(items: List[Dict[str, Any]]):
        items.sort(key=lambda x: (x["level"], x["code"]))
        for item in items:
            sort_children(item["children"])

    sort_children(roots)
    return roots


def _validate_parent(db: Session, parent_id: int | None, level: int) -> None:
    if parent_id is None:
        if level != 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Root nodes must be level 1",
            )
        return
    parent = db.get(Node, parent_id)
    if parent is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Parent node {parent_id} not found",
        )
    if parent.level + 1 != level:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Child level must be parent level + 1 (parent level={parent.level})",
        )


@router.get("", response_model=List[NodeTree])
def list_tree(db: Session = Depends(get_db)):
    nodes = db.query(Node).all()
    return _build_tree(nodes)


@router.get("/level/{level}", response_model=List[NodeRead])
def list_by_level(level: int, db: Session = Depends(get_db)):
    if level < 1 or level > 4:
        raise HTTPException(status_code=400, detail="level must be 1..4")
    nodes = db.query(Node).filter(Node.level == level).order_by(Node.code).all()
    return nodes


@router.get("/{node_id}", response_model=NodeRead)
def get_node(node_id: int, db: Session = Depends(get_db)):
    node = db.get(Node, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return node


@router.post("", response_model=NodeRead, status_code=status.HTTP_201_CREATED)
def create_node(payload: NodeCreate, db: Session = Depends(get_db)):
    _validate_parent(db, payload.parent_id, payload.level)

    existing = db.query(Node).filter(Node.code == payload.code).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"code '{payload.code}' already exists")

    data = payload.model_dump()
    data["next_review_date"] = compute_next_review_date(
        data.get("last_review_date"), data.get("review_frequency")
    )

    node = Node(**data)
    db.add(node)
    db.commit()
    db.refresh(node)
    return node


@router.put("/{node_id}", response_model=NodeRead)
def update_node(node_id: int, payload: NodeUpdate, db: Session = Depends(get_db)):
    node = db.get(Node, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")

    data = payload.model_dump(exclude_unset=True)

    new_level = data.get("level", node.level)
    new_parent_id = data["parent_id"] if "parent_id" in data else node.parent_id
    if "level" in data or "parent_id" in data:
        _validate_parent(db, new_parent_id, new_level)

    if "code" in data and data["code"] != node.code:
        existing = db.query(Node).filter(Node.code == data["code"]).first()
        if existing is not None and existing.id != node.id:
            raise HTTPException(status_code=409, detail=f"code '{data['code']}' already exists")

    for key, value in data.items():
        setattr(node, key, value)

    node.next_review_date = compute_next_review_date(
        node.last_review_date, node.review_frequency
    )

    db.commit()
    db.refresh(node)
    return node


@router.delete("/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_node(node_id: int, db: Session = Depends(get_db)):
    node = db.get(Node, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")
    db.delete(node)
    db.commit()
    return None
