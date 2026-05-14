"""Document Library — central many-to-many document store.

LibraryDocument rows hold the file + metadata. NodeDocument rows are
many-to-many links between a node and a library doc. The same document
file can be linked to any number of nodes; unlinking removes the link
only, while DELETE /library/documents/{id} purges the file from R2 and
removes every link.
"""
from __future__ import annotations

import uuid
from datetime import date
from pathlib import Path
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

import r2_storage
from database import get_db
from models import (
    DocType,
    LibraryDocument,
    Node,
    NodeDocument,
    ReviewFrequency,
)
from schemas import (
    DocumentDownloadUrl,
    LibraryDocumentRead,
    LibraryDocumentReadWithNodes,
    LibraryDocumentUpdate,
    NodeRef,
)
from utils import compute_next_review_date


router = APIRouter(tags=["library"])


REQUIRED_FIELDS_TYPES = {DocType.procedure, DocType.work_instruction}


# ---------- Helpers ----------


def _require_node(db: Session, node_id: int) -> Node:
    node = db.get(Node, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
    return node


def _require_doc(db: Session, doc_id: int) -> LibraryDocument:
    doc = db.get(LibraryDocument, doc_id)
    if doc is None:
        raise HTTPException(
            status_code=404, detail=f"Library document {doc_id} not found"
        )
    return doc


def _validate_required_fields(
    doc_type: DocType,
    owner: Optional[str],
    review_frequency: Optional[ReviewFrequency],
) -> None:
    if doc_type in REQUIRED_FIELDS_TYPES:
        missing = []
        if not owner:
            missing.append("owner")
        if not review_frequency:
            missing.append("review_frequency")
        if missing:
            raise HTTPException(
                status_code=422,
                detail=f"{doc_type.value} documents require: {', '.join(missing)}",
            )


def _r2_key_for(original_filename: str) -> str:
    suffix = Path(original_filename or "").suffix
    return f"documents/{uuid.uuid4().hex}{suffix}"


def _link_count(db: Session, doc_id: int) -> int:
    return (
        db.query(func.count(NodeDocument.id))
        .filter(NodeDocument.library_document_id == doc_id)
        .scalar()
        or 0
    )


def _attach_count(db: Session, doc: LibraryDocument) -> LibraryDocument:
    doc.linked_nodes_count = _link_count(db, doc.id)
    return doc


# ---------- Library document CRUD ----------


@router.post(
    "/library/documents",
    response_model=LibraryDocumentRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_to_library(
    file: UploadFile = File(...),
    doc_type: DocType = Form(...),
    tags: Optional[str] = Form(None),
    owner: Optional[str] = Form(None),
    review_frequency: Optional[ReviewFrequency] = Form(None),
    last_review_date: Optional[date] = Form(None),
    next_review_date: Optional[date] = Form(None),
    version: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    # Drain the upload into memory before any other async/sync hop.
    contents = await file.read()
    size = len(contents)
    original_filename = file.filename or ""
    content_type = file.content_type

    _validate_required_fields(doc_type, owner, review_frequency)

    if not r2_storage.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Document storage is not configured (R2 env vars missing).",
        )

    key = _r2_key_for(original_filename)
    try:
        r2_storage.put_bytes(contents, key, content_type=content_type)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    computed_next = next_review_date or compute_next_review_date(
        last_review_date, review_frequency
    )

    doc = LibraryDocument(
        filename=key,
        original_filename=original_filename or key,
        file_url=key,
        file_size=size,
        mime_type=content_type,
        doc_type=doc_type,
        tags=tags,
        owner=owner,
        review_frequency=review_frequency,
        last_review_date=last_review_date,
        next_review_date=computed_next,
        version=version,
        notes=notes,
        description=description,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return _attach_count(db, doc)


@router.get("/library/documents", response_model=List[LibraryDocumentRead])
def list_library(
    doc_type: Optional[DocType] = Query(None),
    search: Optional[str] = Query(None),
    tags: Optional[str] = Query(
        None, description="Comma-separated tags; matches any (OR semantics)."
    ),
    db: Session = Depends(get_db),
):
    q = db.query(LibraryDocument)

    if doc_type is not None:
        q = q.filter(LibraryDocument.doc_type == doc_type)

    if search:
        like = f"%{search}%"
        q = q.filter(
            or_(
                LibraryDocument.original_filename.ilike(like),
                LibraryDocument.description.ilike(like),
                LibraryDocument.owner.ilike(like),
                LibraryDocument.tags.ilike(like),
            )
        )

    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        if tag_list:
            q = q.filter(
                or_(*[LibraryDocument.tags.ilike(f"%{t}%") for t in tag_list])
            )

    docs = q.order_by(LibraryDocument.uploaded_at.desc()).all()
    for d in docs:
        _attach_count(db, d)
    return docs


@router.get(
    "/library/documents/{doc_id}", response_model=LibraryDocumentReadWithNodes
)
def get_library_doc(doc_id: int, db: Session = Depends(get_db)):
    doc = _require_doc(db, doc_id)
    nodes = [link.node for link in doc.node_links]
    doc.linked_nodes_count = len(nodes)
    doc.linked_nodes = [NodeRef.model_validate(n) for n in nodes]
    return doc


@router.put("/library/documents/{doc_id}", response_model=LibraryDocumentRead)
def update_library_doc(
    doc_id: int, payload: LibraryDocumentUpdate, db: Session = Depends(get_db)
):
    doc = _require_doc(db, doc_id)
    data = payload.model_dump(exclude_unset=True)

    new_doc_type = data.get("doc_type", doc.doc_type)
    new_owner = data["owner"] if "owner" in data else doc.owner
    new_freq = (
        data["review_frequency"]
        if "review_frequency" in data
        else doc.review_frequency
    )
    _validate_required_fields(new_doc_type, new_owner, new_freq)

    for k, v in data.items():
        setattr(doc, k, v)

    if "next_review_date" not in data:
        doc.next_review_date = compute_next_review_date(
            doc.last_review_date, doc.review_frequency
        )

    db.commit()
    db.refresh(doc)
    return _attach_count(db, doc)


@router.delete(
    "/library/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_library_doc(doc_id: int, db: Session = Depends(get_db)):
    doc = _require_doc(db, doc_id)
    key = doc.filename
    if r2_storage.is_configured() and key:
        try:
            r2_storage.delete_object(key)
        except RuntimeError as e:
            raise HTTPException(status_code=502, detail=str(e))
    # NodeDocument rows cascade via ORM relationship + FK ondelete=CASCADE.
    db.delete(doc)
    db.commit()
    return None


@router.get(
    "/library/documents/{doc_id}/view", response_model=DocumentDownloadUrl
)
def view_library_doc(doc_id: int, db: Session = Depends(get_db)):
    doc = _require_doc(db, doc_id)
    if not r2_storage.is_configured():
        raise HTTPException(
            status_code=503, detail="Document storage is not configured."
        )
    expires_in = 3600
    try:
        url = r2_storage.generate_view_url(
            doc.filename, expires_in=expires_in, filename=doc.original_filename
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return DocumentDownloadUrl(url=url, expires_in=expires_in)


@router.get(
    "/library/documents/{doc_id}/download", response_model=DocumentDownloadUrl
)
def download_library_doc(doc_id: int, db: Session = Depends(get_db)):
    doc = _require_doc(db, doc_id)
    if not r2_storage.is_configured():
        raise HTTPException(
            status_code=503, detail="Document storage is not configured."
        )
    expires_in = 3600
    try:
        url = r2_storage.generate_download_url(
            doc.filename,
            expires_in=expires_in,
            download_filename=doc.original_filename,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return DocumentDownloadUrl(url=url, expires_in=expires_in)


# ---------- Node-document linking ----------


@router.post(
    "/nodes/{node_id}/link-document/{doc_id}",
    response_model=LibraryDocumentRead,
    status_code=status.HTTP_201_CREATED,
)
def link_document(
    node_id: int,
    doc_id: int,
    linked_by: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    _require_node(db, node_id)
    doc = _require_doc(db, doc_id)

    existing = (
        db.query(NodeDocument)
        .filter(
            NodeDocument.node_id == node_id,
            NodeDocument.library_document_id == doc_id,
        )
        .first()
    )
    if existing is None:
        link = NodeDocument(
            node_id=node_id,
            library_document_id=doc_id,
            linked_by=linked_by,
        )
        db.add(link)
        db.commit()
    return _attach_count(db, doc)


@router.delete(
    "/nodes/{node_id}/unlink-document/{doc_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def unlink_document(node_id: int, doc_id: int, db: Session = Depends(get_db)):
    link = (
        db.query(NodeDocument)
        .filter(
            NodeDocument.node_id == node_id,
            NodeDocument.library_document_id == doc_id,
        )
        .first()
    )
    if link is None:
        raise HTTPException(
            status_code=404,
            detail=f"No link between node {node_id} and document {doc_id}",
        )
    db.delete(link)
    db.commit()
    return None


@router.get(
    "/nodes/{node_id}/documents", response_model=List[LibraryDocumentRead]
)
def list_node_documents(node_id: int, db: Session = Depends(get_db)):
    _require_node(db, node_id)
    docs = (
        db.query(LibraryDocument)
        .join(NodeDocument, NodeDocument.library_document_id == LibraryDocument.id)
        .filter(NodeDocument.node_id == node_id)
        .order_by(NodeDocument.linked_at.desc())
        .all()
    )
    for d in docs:
        _attach_count(db, d)
    return docs
