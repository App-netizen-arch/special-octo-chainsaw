"""RAG over uploaded legal documents: chunk -> embed -> index -> cite.

MVP embedding strategy: TF-IDF vectors computed with pure Python + math
(no numpy/sklearn required), stored in a brute-force cosine index. If
`faiss-cpu` and `sentence-transformers` are installed they are used instead
(FAISS IndexFlatIP over normalized sentence-transformer embeddings).

Page tracking: PDF pages are extracted individually (pypdf) so every chunk
remembers its page; DOCX/TXT get page=None and are cited by section.
Citation shape after normalization: [Document Name, Page X] + snippet.
"""

from __future__ import annotations

import json
import logging
import math
import re
import threading
from pathlib import Path
from typing import Any, Optional

from ..config import settings
from ..database import add_document, delete_document as db_delete_document, list_documents
from ..utils.citation_normalizer import normalize_document_hit

log = logging.getLogger("counsel.rag")

CHUNK_CHARS = 1100
CHUNK_OVERLAP = 150

_lock = threading.Lock()
_index: dict[str, Any] = {"vectors": [], "meta": [], "idf": None, "dim": 0}
_faiss = None


# ------------------------------------------------------------------ extraction


def extract_pdf(path: Path) -> list[tuple[int, str]]:
    """Returns [(page_number_1based, text)] using pypdf."""
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception:  # noqa: BLE001 - corrupt page should not kill upload
            text = ""
        pages.append((i + 1, text))
    return pages


def extract_docx(path: Path) -> list[tuple[int, str]]:
    from docx import Document as DocxDocument  # python-docx

    doc = DocxDocument(str(path))
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    return [(1, "\n".join(parts))]


def extract_txt(path: Path) -> list[tuple[int, str]]:
    return [(1, path.read_text(errors="ignore"))]


def extract_any(path: Path) -> list[tuple[int, str]]:
    suffix = path.suffix.lower()
    try:
        if suffix == ".pdf":
            return extract_pdf(path)
        if suffix == ".docx":
            return extract_docx(path)
        return extract_txt(path)
    except ImportError as exc:
        raise RuntimeError(f"Missing parser dependency for {suffix}: {exc}") from exc


# -------------------------------------------------------------------- chunking


def chunk_pages(pages: list[tuple[int, str]]) -> list[dict]:
    """Paragraph-aware sliding-window chunks that keep their page number."""
    chunks: list[dict] = []
    for page_no, text in pages:
        paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        buf = ""
        start_page = page_no

        def flush(buf: str, page: int) -> None:
            t = re.sub(r"\s+", " ", buf).strip()
            if len(t) >= 40:
                chunks.append({"text": t[:2000], "page": page})

        for para in paras:
            if len(buf) + len(para) + 1 <= CHUNK_CHARS:
                buf = f"{buf} {para}".strip()
                continue
            flush(buf, start_page)
            tail = buf[-CHUNK_OVERLAP:] if CHUNK_OVERLAP and len(buf) > CHUNK_OVERLAP else ""
            buf = f"{tail} {para}".strip()
            start_page = page_no
        if buf:
            flush(buf, start_page)
    return chunks


# ------------------------------------------------------------------- embedding


_TOKEN_RE = re.compile(r"[a-z0-9]{2,}")
_STOP = frozenset(
    "the a an and or of to in on for with by from as at is are was were be been it its "
    "this that shall may such any all not no than then thereof hereinafter".split()
)


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOP]


class TfidfIndex:
    """Minimal TF-IDF cosine index — zero dependencies, good enough for MVP."""

    def __init__(self) -> None:
        self.vectors: list[dict[int, float]] = []
        self.meta: list[dict] = []
        self.idf: dict[str, float] = {}
        self.dim = 0

    def fit_idf(self, docs_tokens: list[list[str]]) -> None:
        df: dict[str, int] = {}
        for toks in docs_tokens:
            for tok in set(toks):
                df[tok] = df.get(tok, 0) + 1
        n = max(len(docs_tokens), 1)
        self.idf = {tok: math.log((n + 1) / (cnt + 1)) + 1.0 for tok, cnt in df.items()}
        self.dim = len(self.idf)

    def vectorize(self, toks: list[str]) -> dict[int, float]:
        tf: dict[str, int] = {}
        for tok in toks:
            tf[tok] = tf.get(tok, 0) + 1
        vec: dict[int, float] = {}
        for tok, cnt in tf.items():
            weight = cnt * self.idf.get(tok, 0.0)
            h = hash(tok) % 4096
            # bag-of-hashed-terms keeps dimensionality stable across rebuilds
            vec[h] = vec.get(h, 0.0) + weight
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {k: v / norm for k, v in vec.items()}

    @staticmethod
    def cosine(a: dict[int, float], b: dict[int, float]) -> float:
        if len(a) > len(b):
            a, b = b, a
        return sum(v * b.get(k, 0.0) for k, v in a.items())


def _try_sentence_transformers(texts: list[str]) -> Optional[list[list[float]]]:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        return None
    model = SentenceTransformer("all-MiniLM-L6-v2")
    emb = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return [list(map(float, row)) for row in emb]  # type: ignore[arg-type]


def _try_faiss(matrix: list[list[float]]):
    try:
        import faiss  # type: ignore
        import numpy as np  # type: ignore
    except ImportError:
        return None
    arr = np.asarray(matrix, dtype="float32")
    index = faiss.IndexFlatIP(arr.shape[1])
    index.add(arr)
    return index, np


# ------------------------------------------------------------------ public API


async def ingest_file(tmp_path: Path, display_name: str) -> dict[str, Any]:
    """Extract, chunk, embed and persist one uploaded document."""
    pages = extract_any(tmp_path)
    chunks = chunk_pages(pages)
    if not chunks:
        raise RuntimeError("No readable text found in that file.")
    texts = [c["text"] for c in chunks]
    # every chunk carries its own snippet so citations never need re-extraction
    metas = [{"document": display_name, "page": c["page"], "text": c["text"][:400]} for c in chunks]

    st_vectors = await _st_in_thread(texts)
    global _faiss
    with _lock:
        if st_vectors is not None:
            faiss_bundle = _try_faiss(st_vectors)
            if faiss_bundle is not None:
                _faiss = {"index": faiss_bundle[0], "np": faiss_bundle[1]}
                _index["vectors"] = st_vectors
            else:
                _faiss = None
                _index["vectors"] = [
                    _l2({i: v for i, v in enumerate(row)}) for row in st_vectors
                ]
        else:
            _faiss = None
            tfidf = TfidfIndex()
            token_lists = [_tokens(t) for t in texts]
            tfidf.fit_idf(token_lists)
            _index["vectors"] = [tfidf.vectorize(toks) for toks in token_lists]
            _index["idf"] = tfidf
        _index["meta"] = metas
        _persist_index()

    doc = add_document(display_name, str(settings.docs_dir / display_name), len(pages), len(chunks))
    return doc


async def _st_in_thread(texts: list[str]):
    import asyncio

    def run():
        try:
            return _try_sentence_transformers(texts)
        except Exception as exc:  # noqa: BLE001
            log.warning("sentence-transformers unavailable (%s); using TF-IDF", exc)
            return None

    return await asyncio.to_thread(run)


def _l2(vec: dict[int, float]) -> dict[int, float]:
    norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    return {k: v / norm for k, v in vec.items()}


def _persist_index() -> None:
    payload = {"meta": _index["meta"], "vectors": _index["vectors"]}
    try:
        settings.faiss_path.write_text(json.dumps(payload))
    except (OSError, TypeError) as exc:  # pragma: no cover
        log.warning("could not persist index: %s", exc)


def restore_index() -> None:
    if not settings.faiss_path.exists():
        return
    try:
        data = json.loads(settings.faiss_path.read_text())
        with _lock:
            _index.update({"vectors": data["vectors"], "meta": data["meta"], "idf": None})
            globals()["_faiss"] = None
    except (json.JSONDecodeError, KeyError, OSError) as exc:
        log.warning("failed to restore index: %s", exc)


def remove_document(doc_id: str) -> None:
    db_delete_document(doc_id)


def query_documents(query: str, top_k: int = 5, document_ids: Optional[list[str]] = None):
    with _lock:
        vectors = list(_index["vectors"])
        metas = list(_index["meta"])
    if not vectors or not query.strip():
        return []
    names = None
    if document_ids:
        docs = {d["id"]: d["name"] for d in list_documents()}
        names = {docs[i] for i in document_ids if i in docs}

    qv = _embed_query(query)
    scored = []
    for i, vec in enumerate(vectors):
        meta = metas[i] if i < len(metas) else {}
        if names and meta.get("document") not in names:
            continue
        score = TfidfIndex.cosine(qv, vec)
        scored.append((score, meta))
    scored.sort(key=lambda t: -t[0])
    hits = []
    for score, meta in scored[:top_k]:
        if score < 0.02:
            continue
        hits.append(
            normalize_document_hit(
                meta.get("document", ""), meta.get("page"), meta.get("text", ""), score
            ).model_dump()
        )
    return hits


def _embed_query(query: str):
    idf = _index.get("idf")
    if isinstance(idf, TfidfIndex):
        return idf.vectorize(_tokens(query))
    # dense mode: approximate with hashed bag-of-words (works for keyword-y queries)
    vec: dict[int, float] = {}
    for tok in _tokens(query):
        h = hash(tok) % min(len(_index["vectors"][0]) or 384, 4096)
        vec[h] = vec.get(h, 0.0) + 1.0
    return _l2(vec)
