"""Document management endpoints.

Files are stored in Cloudflare R2 (S3-compatible) via boto3.
The DB row holds metadata; the bucket object key is `filename`.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import List, Optional
from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

import r2_storage
from database import get_db
from models import Document, DocType, Node, ReviewFrequency
from schemas import DocumentDownloadUrl, DocumentRead, DocumentUpdate
from utils import compute_next_review_date


router = APIRouter(tags=["documents"])


# Doc types whose owner + review_frequency are required by policy.
REQUIRED_FIELDS_TYPES = {DocType.procedure, DocType.work_instruction}


def _require_node(db: Session, node_id: int) -> Node:
    node = db.get(Node, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"Node {node_id} not found")
    return node


def _require_document(db: Session, doc_id: int) -> Document:
    doc = db.get(Document, doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
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
                detail=(
                    f"{doc_type.value} documents require: {', '.join(missing)}"
                ),
            )


def _r2_key_for(original_filename: str) -> str:
    suffix = Path(original_filename or "").suffix
    return f"documents/{uuid.uuid4().hex}{suffix}"


@router.post(
    "/nodes/{node_id}/documents",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    node_id: int,
    file: UploadFile = File(...),
    doc_type: DocType = Form(...),
    tags: Optional[str] = Form(None),
    owner: Optional[str] = Form(None),
    review_frequency: Optional[ReviewFrequency] = Form(None),
    last_review_date: Optional[date] = Form(None),
    next_review_date: Optional[date] = Form(None),
    version: Optional[str] = Form(None),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    _require_node(db, node_id)
    _validate_required_fields(doc_type, owner, review_frequency)

    if not r2_storage.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Document storage is not configured (R2 env vars missing).",
        )

    key = _r2_key_for(file.filename or "")
    # Stream the upload into R2 directly. boto3 handles multipart for large files.
    try:
        r2_storage.upload_fileobj(
            file.file,
            key,
            content_type=file.content_type,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    # Compute file size by seek/tell (UploadFile is a SpooledTemporaryFile-backed).
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)

    # If client didn't pass next_review_date, derive it from cadence.
    computed_next = next_review_date or compute_next_review_date(
        last_review_date, review_frequency
    )

    doc = Document(
        node_id=node_id,
        filename=key,
        original_filename=file.filename or key,
        file_url=key,
        file_size=size,
        mime_type=file.content_type,
        doc_type=doc_type,
        tags=tags,
        owner=owner,
        review_frequency=review_frequency,
        last_review_date=last_review_date,
        next_review_date=computed_next,
        version=version,
        notes=notes,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@router.get("/nodes/{node_id}/documents", response_model=List[DocumentRead])
def list_node_documents(node_id: int, db: Session = Depends(get_db)):
    _require_node(db, node_id)
    return (
        db.query(Document)
        .filter(Document.node_id == node_id)
        .order_by(Document.uploaded_at.desc())
        .all()
    )


@router.get("/documents/{doc_id}", response_model=DocumentRead)
def get_document(doc_id: int, db: Session = Depends(get_db)):
    return _require_document(db, doc_id)


@router.put("/documents/{doc_id}", response_model=DocumentRead)
def update_document(
    doc_id: int,
    payload: DocumentUpdate,
    db: Session = Depends(get_db),
):
    doc = _require_document(db, doc_id)
    data = payload.model_dump(exclude_unset=True)

    new_doc_type = data.get("doc_type", doc.doc_type)
    new_owner = data["owner"] if "owner" in data else doc.owner
    new_freq = (
        data["review_frequency"]
        if "review_frequency" in data
        else doc.review_frequency
    )
    _validate_required_fields(new_doc_type, new_owner, new_freq)

    for key, value in data.items():
        setattr(doc, key, value)

    # Recompute next_review_date unless client explicitly set it.
    if "next_review_date" not in data:
        doc.next_review_date = compute_next_review_date(
            doc.last_review_date, doc.review_frequency
        )

    db.commit()
    db.refresh(doc)
    return doc


@router.delete("/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(doc_id: int, db: Session = Depends(get_db)):
    doc = _require_document(db, doc_id)
    key = doc.filename
    # Delete from R2 first; if it fails we leave the DB row so admins can retry.
    if r2_storage.is_configured() and key:
        try:
            r2_storage.delete_object(key)
        except RuntimeError as e:
            raise HTTPException(status_code=502, detail=str(e))

    db.delete(doc)
    db.commit()
    return None


@router.get("/documents/{doc_id}/download", response_model=DocumentDownloadUrl)
def download_document(doc_id: int, db: Session = Depends(get_db)):
    doc = _require_document(db, doc_id)
    if not r2_storage.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Document storage is not configured (R2 env vars missing).",
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
