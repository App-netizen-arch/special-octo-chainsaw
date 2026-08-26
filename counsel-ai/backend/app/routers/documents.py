"""Documents router: upload (PDF/DOCX/TXT), list, delete, RAG query."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from ..database import list_documents
from ..models.schemas import DocumentOut, DocumentQueryRequest, Source
from ..services.rag import ingest_file, query_documents, remove_document, restore_index

router = APIRouter(prefix="/api/documents", tags=["documents"])

ALLOWED_SUFFIXES = {".pdf", ".docx", ".txt"}


@router.on_event("startup")
def _restore() -> None:
    restore_index()


@router.get("", response_model=list[DocumentOut])
async def get_documents() -> list[DocumentOut]:
    return [DocumentOut(**d) for d in list_documents()]


@router.post("", response_model=DocumentOut)
async def upload_document(file: UploadFile) -> DocumentOut:
    name = file.filename or "document"
    suffix = Path(name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(400, f"Unsupported file type '{suffix}'. Use PDF, DOCX or TXT.")
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)
    try:
        doc = await ingest_file(tmp_path, name)
    except RuntimeError as exc:
        raise HTTPException(422, str(exc)) from exc
    finally:
        # persist a copy in the managed uploads dir
        dest = Path(__import__("app.config", fromlist=["settings"]).settings.docs_dir) / name
        try:
            shutil.move(str(tmp_path), dest)
        except OSError:
            pass
    return DocumentOut(**doc)


@router.delete("/{doc_id}")
async def delete_doc(doc_id: str) -> dict:
    remove_document(doc_id)
    return {"ok": True}


@router.post("/query", response_model=list[Source])
async def query_docs(req: DocumentQueryRequest) -> list[Source]:
    hits = query_documents(req.query, top_k=req.top_k, document_ids=req.document_ids or None)
    return [Source(**h) for h in hits]
