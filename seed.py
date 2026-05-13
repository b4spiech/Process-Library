"""Seed the BPR with common business domains (L1) and example L2 functions.

Run with:  python seed.py
Safe to re-run: rows are upserted by `code`.
"""
from __future__ import annotations

from typing import Optional

from database import SessionLocal, engine, Base
from models import Node, NodeStatus, ReviewFrequency
from utils import compute_next_review_date


SEED_DATA = [
    {
        "code": "OPS",
        "name": "Operations",
        "description": "Day-to-day operational execution across the business.",
        "owner": "COO Office",
        "children": [
            {"code": "OPS-WH", "name": "Warehousing", "owner": "Warehouse Director"},
            {"code": "OPS-PUR", "name": "Purchasing", "owner": "Director of Procurement"},
            {"code": "OPS-LOG", "name": "Logistics & Distribution", "owner": "Logistics Manager"},
        ],
    },
    {
        "code": "FIN",
        "name": "Finance",
        "description": "Financial planning, accounting, and controls.",
        "owner": "CFO Office",
        "children": [
            {"code": "FIN-AP", "name": "Accounts Payable", "owner": "AP Manager"},
            {"code": "FIN-AR", "name": "Accounts Receivable", "owner": "AR Manager"},
            {"code": "FIN-GL", "name": "General Ledger & Close", "owner": "Controller"},
        ],
    },
    {
        "code": "HR",
        "name": "Human Resources",
        "description": "Talent acquisition, development, and employee experience.",
        "owner": "CHRO Office",
        "children": [
            {"code": "HR-TA", "name": "Talent Acquisition", "owner": "Director of Recruiting"},
            {"code": "HR-LD", "name": "Learning & Development", "owner": "L&D Manager"},
            {"code": "HR-PAY", "name": "Payroll & Benefits", "owner": "Payroll Manager"},
        ],
    },
    {
        "code": "IT",
        "name": "Information Technology",
        "description": "Technology operations, applications, and infrastructure.",
        "owner": "CIO Office",
        "children": [
            {"code": "IT-INF", "name": "Infrastructure & Cloud", "owner": "Infrastructure Lead"},
            {"code": "IT-APP", "name": "Business Applications", "owner": "Applications Manager"},
            {"code": "IT-SEC", "name": "Security & Compliance", "owner": "CISO"},
        ],
    },
    {
        "code": "SAL",
        "name": "Sales",
        "description": "Customer acquisition and revenue generation.",
        "owner": "CRO Office",
        "children": [
            {"code": "SAL-INS", "name": "Inside Sales", "owner": "Inside Sales Manager"},
            {"code": "SAL-OUT", "name": "Outside Sales", "owner": "Field Sales Director"},
            {"code": "SAL-OPS", "name": "Sales Operations", "owner": "RevOps Lead"},
        ],
    },
    {
        "code": "CS",
        "name": "Customer Service",
        "description": "Post-sale customer support and success.",
        "owner": "VP Customer Experience",
        "children": [
            {"code": "CS-SUP", "name": "Customer Support", "owner": "Support Manager"},
            {"code": "CS-RET", "name": "Returns & Warranty", "owner": "Returns Manager"},
        ],
    },
]


def upsert_node(
    db,
    code: str,
    name: str,
    level: int,
    parent_id: Optional[int],
    description: Optional[str] = None,
    owner: Optional[str] = None,
) -> Node:
    node = db.query(Node).filter(Node.code == code).first()
    if node is None:
        node = Node(
            code=code,
            name=name,
            level=level,
            parent_id=parent_id,
            description=description,
            owner=owner,
            status=NodeStatus.active,
            review_frequency=ReviewFrequency.quarterly,
        )
        node.next_review_date = compute_next_review_date(
            node.last_review_date, node.review_frequency
        )
        db.add(node)
        db.flush()
    else:
        node.name = name
        node.level = level
        node.parent_id = parent_id
        if description is not None:
            node.description = description
        if owner is not None:
            node.owner = owner
    return node


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        for l1 in SEED_DATA:
            parent = upsert_node(
                db,
                code=l1["code"],
                name=l1["name"],
                level=1,
                parent_id=None,
                description=l1.get("description"),
                owner=l1.get("owner"),
            )
            for l2 in l1.get("children", []):
                upsert_node(
                    db,
                    code=l2["code"],
                    name=l2["name"],
                    level=2,
                    parent_id=parent.id,
                    description=l2.get("description"),
                    owner=l2.get("owner"),
                )
        db.commit()
        print(f"Seed complete. Nodes in DB: {db.query(Node).count()}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
