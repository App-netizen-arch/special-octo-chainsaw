"""Documents router: upload (PDF/DOCX/TXT), list, delete, RAG query.

Uploads are encrypted at rest; indexing runs as a background task so the UI
stays responsive — the document row is created with status="indexing" and
flips to "ready" when the vector index has been updated.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile

from ..database import list_documents, get_document, set_document_status, uid
from ..deps import current_user
from ..models.db import User
from ..models.schemas import DocumentOut, DocumentQueryRequest, Source
from ..services.rag import ingest_file, query_documents

log = logging.getLogger("counsel.documents")
router = APIRouter(prefix="/api/documents", tags=["documents"])

ALLOWED_SUFFIXES = {".pdf", ".docx", ".txt"}


@router.get("", response_model=list[DocumentOut])
async def get_documents(user: User = Depends(current_user)) -> list[DocumentOut]:
    return [DocumentOut(**d) for d in list_documents(user.id)]


async def _index_document(tmp_path: Path, name: str, doc_id: str, user_id: str) -> None:
    """Background indexing: heavy parsing/embedding off the request path."""
    try:
        doc = await ingest_file(tmp_path, name, user_id)
        set_document_status(doc_id, "ready", pages=doc["pages"], chunks=doc["chunks"])
    except Exception as exc:  # noqa: BLE001
        log.exception("background indexing failed for %s", name)
        set_document_status(doc_id, "failed")
        raise


@router.post("", response_model=DocumentOut)
async def upload_document(background: BackgroundTasks, file: UploadFile,
                          user: User = Depends(current_user)) -> DocumentOut:
    name = Path(file.filename or "document").name
    suffix = Path(name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(400, f"Unsupported file type '{suffix}'. Use PDF, DOCX or TXT.")
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    # placeholder row so the UI can track the background job
    from ..database import add_document

    doc = add_document(user.id, name, "", 0, 0, status="indexing")
    background.add_task(_index_document, tmp_path, name, doc["id"], user.id)
    return DocumentOut(**doc)


@router.delete("/{doc_id}")
async def delete_doc(doc_id: str, user: User = Depends(current_user)) -> dict:
    from ..services.rag import remove_document

    if not remove_document(doc_id, user.id):
        raise HTTPException(404, "document not found")
    return {"ok": True}


@router.get("/{doc_id}", response_model=DocumentOut)
async def get_doc(doc_id: str, user: User = Depends(current_user)) -> DocumentOut:
    d = get_document(doc_id, user.id)
    if d is None:
        raise HTTPException(404, "document not found")
    return DocumentOut(**d)


@router.post("/query", response_model=list[Source])
async def query_docs(req: DocumentQueryRequest,
                     user: User = Depends(current_user)) -> list[Source]:
    hits = query_documents(req.query, top_k=req.top_k,
                           document_ids=req.document_ids or None, user_id=user.id)
    return [Source(**h) for h in hits]
