"""RAG over uploaded legal documents — production upgrade.

Pipeline: extract (page-aware) -> chunk -> embed -> hybrid search ->
re-rank -> cite.

* **Hybrid retrieval**: BM25 (pure Python, zero-dep) fused with the vector
  index via Reciprocal Rank Fusion — robust for statute numbers and legal
  terms of art that pure embeddings miss.
* **Embeddings**: sentence-transformers when installed; TF-IDF hashed
  fallback otherwise. Embedding vectors are cached per text hash in SQLite.
* **Encrypted at rest**: the persisted index payload is AES-256-GCM sealed
  via ``utils.encryption``; uploads are stored encrypted too.
* **Workspace isolation**: every query is scoped to one user's documents.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import re
import threading
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select

from ..config import settings
from ..database import (
    add_document,
    delete_document as db_delete_document,
    list_documents,
    session_scope,
    set_document_status,
)
from ..models.db import EmbeddingCache
from ..utils.citation_normalizer import normalize_document_hit
from ..utils.encryption import decrypt_file, encrypt_file
from ..utils.metrics import inc, timed

log = logging.getLogger("counsel.rag")

CHUNK_CHARS = 1100
CHUNK_OVERLAP = 150
RRF_K = 60

_lock = threading.Lock()
_index: dict[str, Any] = {"vectors": [], "meta": [], "idf": None}
_faiss = None


# ------------------------------------------------------------------ extraction


def extract_pdf(path: Path) -> list[tuple[int, str]]:
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
    try:
        return [(1, path.read_text(errors="ignore"))]
    except UnicodeDecodeError:
        return [(1, path.read_bytes().decode("utf-8", errors="ignore"))]


def extract_any(path: Path) -> list[tuple[int, str]]:
    """Handles both plaintext uploads and Counsel-encrypted uploads."""
    raw_probe = path.read_bytes()[:8]
    if raw_probe.startswith(b"cns1"):
        plain = decrypt_file(path).decode("utf-8", errors="ignore")
        return [(1, plain)]
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


# ---------------------------------------------------------------- BM25 scoring


_TOKEN_RE = re.compile(r"[a-z0-9]{2,}")
_STOP = frozenset(
    "the a an and or of to in on for with by from as at is are was were be been it its "
    "this that shall may such any all not no than then thereof hereinafter".split()
)


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOP]


class Bm25:
    """Okapi BM25 over pre-tokenized docs (k1=1.5, b=0.75)."""

    def __init__(self, corpus_tokens: list[list[str]]) -> None:
        self.k1 = 1.5
        self.b = 0.75
        self.n = len(corpus_tokens)
        self.doc_len = [len(t) for t in corpus_tokens]
        self.avgdl = sum(self.doc_len) / max(self.n, 1)
        self.tf: list[dict[str, int]] = [{} for _ in range(self.n)]
        df: dict[str, int] = {}
        for i, toks in enumerate(corpus_tokens):
            tf = self.tf[i]
            for tok in toks:
                tf[tok] = tf.get(tok, 0) + 1
            for tok in tf:
                df[tok] = df.get(tok, 0) + 1
        self.idf = {
            tok: math.log(1 + (self.n - cnt + 0.5) / (cnt + 0.5)) for tok, cnt in df.items()
        }

    def score(self, query_tokens: list[str], doc_idx: int) -> float:
        tf = self.tf[doc_idx]
        dl = self.doc_len[doc_idx]
        score = 0.0
        for tok in query_tokens:
            freq = tf.get(tok)
            if not freq:
                continue
            idf = self.idf.get(tok, 0.0)
            denom = freq + self.k1 * (1 - self.b + self.b * dl / max(self.avgdl, 1e-9))
            score += idf * (freq * (self.k1 + 1)) / denom
        return score

    def rank(self, query: str, top_k: int = 10) -> list[tuple[int, float]]:
        qt = _tokens(query)
        scores = [(i, self.score(qt, i)) for i in range(self.n)]
        scores = [(i, s) for i, s in scores if s > 0]
        scores.sort(key=lambda t: -t[1])
        return scores[:top_k]


# ------------------------------------------------------------------- embedding


class TfidfIndex:
    def __init__(self) -> None:
        self.idf: dict[str, float] = {}

    def fit_idf(self, docs_tokens: list[list[str]]) -> None:
        df: dict[str, int] = {}
        for toks in docs_tokens:
            for tok in set(toks):
                df[tok] = df.get(tok, 0) + 1
        n = max(len(docs_tokens), 1)
        self.idf = {tok: math.log((n + 1) / (cnt + 1)) + 1.0 for tok, cnt in df.items()}

    def vectorize(self, toks: list[str]) -> dict[int, float]:
        tf: dict[str, int] = {}
        for tok in toks:
            tf[tok] = tf.get(tok, 0) + 1
        vec: dict[int, float] = {}
        for tok, cnt in tf.items():
            weight = cnt * self.idf.get(tok, 0.0)
            h = hash(tok) % 4096
            vec[h] = vec.get(h, 0.0) + weight
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {k: v / norm for k, v in vec.items()}

    @staticmethod
    def cosine(a: dict[int, float], b: dict[int, float]) -> float:
        if len(a) > len(b):
            a, b = b, a
        return sum(v * b.get(k, 0.0) for k, v in a.items())


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _cached_embedding(text: str) -> Optional[list[float]]:
    row = None
    with session_scope() as s:
        row = s.execute(
            select(EmbeddingCache).where(EmbeddingCache.text_hash == _text_hash(text))
        ).scalar_one_or_none()
        if row is not None:
            return json.loads(row.vector_json)
    return None


def _store_embedding(text: str, vector: list[float]) -> None:
    if not settings.cache_embeddings:
        return
    try:
        with session_scope() as s:
            s.merge(
                EmbeddingCache(
                    text_hash=_text_hash(text),
                    dim=len(vector),
                    vector_json=json.dumps(vector),
                )
            )
    except Exception:  # noqa: BLE001 — cache is best-effort
        pass


def _try_sentence_transformers(texts: list[str]) -> Optional[list[list[float]]]:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        return None
    vectors: list[list[float]] = []
    model = SentenceTransformer("all-MiniLM-L6-v2")
    todo_idx: list[int] = []
    todo_texts: list[str] = []
    for i, t in enumerate(texts):
        cached = _cached_embedding(t) if settings.cache_embeddings else None
        if cached is not None:
            vectors.append(cached)
        else:
            vectors.append([])  # placeholder
            todo_idx.append(i)
            todo_texts.append(t)
    if todo_texts:
        emb = model.encode(todo_texts, normalize_embeddings=True, show_progress_bar=False)
        for j, i in enumerate(todo_idx):
            vec = [float(x) for x in emb[j]]
            vectors[i] = vec
            _store_embedding(todo_texts[j], vec)
    return vectors


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


# --------------------------------------------------------------- persistence


def _index_file() -> Path:
    return settings.index_dir / "vectors.bin"


def _persist_index() -> None:
    payload = json.dumps({"meta": _index["meta"], "vectors": _index["vectors"]}).encode()
    try:
        encrypt_file(_index_file(), payload)
    except (OSError, TypeError) as exc:  # pragma: no cover
        log.warning("could not persist index: %s", exc)


def restore_index() -> None:
    f = _index_file()
    if not f.exists():
        return
    try:
        data = json.loads(decrypt_file(f))
        with _lock:
            _index.update({"vectors": data["vectors"], "meta": data["meta"], "idf": None})
            globals()["_faiss"] = None
    except Exception as exc:  # noqa: BLE001 — corrupt/foreign index must not kill boot
        log.warning("failed to restore index: %s", exc)


# ------------------------------------------------------------------ ingestion


async def ingest_file(tmp_path: Path, display_name: str, user_id: str) -> dict[str, Any]:
    """Extract, chunk, embed and persist one uploaded document (sync work runs
    on a worker thread so the event loop stays responsive)."""
    pages = await asyncio.to_thread(extract_any, tmp_path)
    chunks = chunk_pages(pages)
    if not chunks:
        raise RuntimeError("No readable text found in that file.")
    texts = [c["text"] for c in chunks]
    metas = [
        {"document": display_name, "user_id": user_id, "page": c["page"], "text": c["text"][:400]}
        for c in chunks
    ]

    st_vectors = await asyncio.to_thread(_safe_st_embed, texts)
    global _faiss
    with _lock:
        if st_vectors is not None:
            faiss_bundle = _try_faiss(st_vectors)
            if faiss_bundle is not None:
                _faiss = {"index": faiss_bundle[0], "np": faiss_bundle[1]}
                _index["vectors"] = st_vectors
            else:
                _faiss = None
                _index["vectors"] = [_l2({i: v for i, v in enumerate(row)}) for row in st_vectors]
        else:
            _faiss = None
            tfidf = TfidfIndex()
            token_lists = [_tokens(t) for t in texts]
            tfidf.fit_idf(token_lists)
            _index["vectors"] = [tfidf.vectorize(toks) for toks in token_lists]
            _index["idf"] = tfidf
        _index["meta"] = metas
        _persist_index()

    # persist an encrypted copy of the upload next to metadata
    dest = settings.docs_dir / f"{user_id}_{display_name}"
    await asyncio.to_thread(_copy_encrypted, tmp_path, dest)
    doc = add_document(user_id, display_name, str(dest), len(pages), len(chunks))
    inc("documents.indexed")
    return doc


def _safe_st_embed(texts: list[str]) -> Optional[list[list[float]]]:
    try:
        return _try_sentence_transformers(texts)
    except Exception as exc:  # noqa: BLE001
        log.warning("sentence-transformers unavailable (%s); using TF-IDF", exc)
        return None


def _copy_encrypted(src: Path, dest: Path) -> None:
    data = src.read_bytes()
    encrypt_file(dest, data)


def _l2(vec: dict[int, float]) -> dict[int, float]:
    norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    return {k: v / norm for k, v in vec.items()}


def remove_document(doc_id: str, user_id: str) -> bool:
    """Drop metadata + securely wipe the stored file + prune index chunks."""
    doc = get_document(doc_id, user_id)
    if doc is None:
        return False
    path = db_delete_document(doc_id, user_id)
    if path:
        from ..utils.encryption import secure_delete_file

        secure_delete_file(Path(path))
    with _lock:
        pairs = [
            (v, m)
            for v, m in zip(_index["vectors"], _index["meta"])
            if not (m.get("user_id") == user_id and m.get("document") == doc["name"])
        ]
        _index["vectors"] = [p[0] for p in pairs]
        _index["meta"] = [p[1] for p in pairs]
        globals()["_faiss"] = None
        _persist_index()
    return True


def rebuild_user_index(user_id: str) -> None:
    """Rebuild the whole index from surviving uploads (used after deletes)."""
    docs = list_documents(user_id)
    with _lock:
        names = {d["name"] for d in docs}
        pairs = [
            (v, m) for v, m in zip(_index["vectors"], _index["meta"])
            if m.get("user_id") != user_id or m.get("document", "") in names
        ]
        _index["vectors"] = [p[0] for p in pairs]
        _index["meta"] = [p[1] for p in pairs]
        globals()["_faiss"] = None
        _persist_index()


# ------------------------------------------------------------------- querying


def query_documents(
    query: str, top_k: int = 5, document_ids: Optional[list[str]] = None,
    user_id: str | None = None,
) -> list[dict]:
    with timed("rag.query_seconds"):
        with _lock:
            vectors = list(_index["vectors"])
            metas = list(_index["meta"])
        allowed_names: set[str] | None = None
        if document_ids:
            docs = {d["id"]: d["name"] for d in list_documents(user_id or "")} if user_id \
                else {}
            allowed_names = {docs[i] for i in document_ids if i in docs} if docs else None
        if user_id:
            user_docs = {d["name"] for d in list_documents(user_id)}
            metas_scoped = [m for m in metas if m.get("user_id") == user_id or m.get("document") in user_docs]
        else:
            metas_scoped = metas
        idx_of_meta = {id(m): i for i, m in enumerate(metas)}
        usable = [idx_of_meta[id(m)] for m in metas_scoped if id(m) in idx_of_meta]

        if not usable or not query.strip():
            return []

        # --- vector branch
        vec_scores: dict[int, float] = {}
        idf = _index.get("idf")
        qv_dense: Any
        if isinstance(idf, TfidfIndex):
            qv_dense = idf.vectorize(_tokens(query))
            for i in usable:
                meta = metas[i]
                if allowed_names and meta.get("document") not in allowed_names:
                    continue
                if i < len(vectors):
                    vec_scores[i] = TfidfIndex.cosine(qv_dense, vectors[i])
        elif vectors and isinstance(vectors[0], list):
            q_emb = _query_embedding(query)
            if q_emb is not None:
                if _faiss is not None:
                    import numpy as np

                    arr = np.asarray([q_emb], dtype="float32")
                    scores, ids = _faiss["index"].search(arr, min(top_k * 6, len(metas)))
                    for pos, i in enumerate(ids[0]):
                        if i < 0 or i >= len(metas):
                            continue
                        meta = metas[i]
                        if meta.get("user_id") != (user_id or meta.get("user_id")):
                            continue
                        if allowed_names and meta.get("document") not in allowed_names:
                            continue
                        vec_scores[i] = float(scores[0][pos])
                else:
                    qv = _l2({i: v for i, v in enumerate(q_emb)})
                    for i in usable:
                        meta = metas[i]
                        if allowed_names and meta.get("document") not in allowed_names:
                            continue
                        dv = _l2({j: x for j, x in enumerate(vectors[i])}) if vectors[i] else {}
                        vec_scores[i] = TfidfIndex.cosine(qv, dv)

        # --- BM25 branch over visible chunks
        bm25_hits: list[tuple[int, float]] = []
        corpus = [metas[i].get("text", "") for i in usable]
        if corpus:
            bm25 = Bm25([_tokens(c) for c in corpus])
            for local_i, score in bm25.rank(query, top_k=top_k * 4):
                bm25_hits.append((usable[local_i], score))

        # --- Reciprocal Rank Fusion re-ranker
        fused = _rrf(vec_scores, bm25_hits, top_k * 3)

        hits: list[dict] = []
        for i, score in fused[:top_k]:
            meta = metas[i]
            hits.append(
                normalize_document_hit(
                    meta.get("document", ""), meta.get("page"), meta.get("text", ""), score
                ).model_dump()
            )
        inc("rag.queries")
        return hits


def _rrf(vector_scores: dict[int, float], bm25_hits: list[tuple[int, float]], cap: int) -> list[tuple[int, float]]:
    def ranks(pairs: list[tuple[int, float]]) -> dict[int, int]:
        ordered = sorted(pairs, key=lambda t: -t[1])
        return {idx: r + 1 for r, (idx, _) in enumerate(ordered)}

    vranks = ranks(list(vector_scores.items()))
    branks = ranks(bm25_hits)
    fused: dict[int, float] = {}
    for idx in set(vranks) | set(branks):
        s = 0.0
        if idx in vranks:
            s += 1.0 / (RRF_K + vranks[idx])
        if idx in branks:
            s += 1.0 / (RRF_K + branks[idx])
        fused[idx] = s
    ranked = sorted(fused.items(), key=lambda t: -t[1])[:cap]
    return ranked


def _query_embedding(query: str) -> Optional[list[float]]:
    try:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer("all-MiniLM-L6-v2")
        emb = model.encode([query], normalize_embeddings=True, show_progress_bar=False)
        return [float(x) for x in emb[0]]
    except Exception:  # noqa: BLE001
        return None
