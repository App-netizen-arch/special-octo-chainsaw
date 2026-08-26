<div align="center">

# Counsel AI — Workspace

**A local-first AI workbench for legal professionals, built by extracting the best of five open-source systems.**

[![Product](https://img.shields.io/badge/product-counsel--ai-1B4965)](counsel-ai/README.md)
[![Backend](https://img.shields.io/badge/backend-FastAPI-009485)](counsel-ai/backend)
[![Frontend](https://img.shields.io/badge/frontend-Flutter%20Desktop-02569B)](counsel-ai/app)
[![License](https://img.shields.io/badge/license-MIT%20%2B%20Apache--2.0%20derivatives-blue)](counsel-ai/docs/LICENSE_ATTRIBUTIONS.md)

</div>

---

## Overview

This repository contains two things:

1. **[`counsel-ai/`](counsel-ai/)** — the product. A complete, runnable MVP combining:
   - **Private chat** on-device via llama.cpp (GGUF) or through an OpenAI-compatible API, with a persistent privacy indicator
   - **Legal research** restricted server-side to legitimate sources only — courts, governments, academia, bar associations, official publishers — every claim cited
   - **Document Q&A** over uploaded PDFs/DOCX/TXT with page-level citations (`[Document Name, Page X]`)
   - **Document drafting** as MDX with a live split-view preview and `.docx` / `.pdf` / clipboard export
   - **Tool actions** (email, calendar) simulated behind an explicit consent modal

2. **Five reference repositories** (directories at the repo root) whose ideas were studied, extracted, and rewritten into `counsel-ai/`. They are vendored unmodified for provenance; their licenses are preserved verbatim.

```
Flutter Desktop App ── REST + WebSocket ──▶ FastAPI conductor (single entry point)
                                             ├── llama.cpp GGUF  |  OpenAI-compatible API
                                             ├── research agent      (from gpt-researcher)
                                             ├── whitelisted search  (from Perplexica/Vane)
                                             ├── RAG + FAISS         (page-aware citations)
                                             ├── tool stubs          (from composio)
                                             └── SQLite + vector index
```

## Reference repositories

| Directory | Upstream | License | Extracted into Counsel AI |
|---|---|---|---|
| `gpt-researcher-main` | [gpt-researcher](https://github.com/assafelovic/gpt-researcher) | Apache-2.0 | research loop (plan → search → read → write), citation format |
| `Vane-master` | [Vane / Perplexica](https://github.com/ItzCrazyKns/Vane) | MIT | SearXNG integration, ranking & dedup thresholds |
| `llama.cpp-master` | [llama.cpp](https://github.com/ggml-org/llama.cpp) | MIT | GGUF inference & streaming patterns |
| `mdx-main` | [MDX](https://github.com/mdx-js/mdx) | MIT | frontmatter/component document model |
| `composio-next` | [Composio](https://github.com/ComposioHQ/composio) | Apache-2.0 | action interface & consent envelope |

Each vendored README carries a provenance banner pointing back to this product; full attribution in [`counsel-ai/docs/LICENSE_ATTRIBUTIONS.md`](counsel-ai/docs/LICENSE_ATTRIBUTIONS.md).

## Documentation

| Document | Contents |
|---|---|
| [`counsel-ai/README.md`](counsel-ai/README.md) | Setup, feature map, security model |
| [`counsel-ai/docs/ARCHITECTURE.md`](counsel-ai/docs/ARCHITECTURE.md) | Module provenance map, WS protocol, data flow |
| [`counsel-ai/docs/LICENSE_ATTRIBUTIONS.md`](counsel-ai/docs/LICENSE_ATTRIBUTIONS.md) | License obligations for extracted code |
| [`counsel-ai/docs/PORTFOLIO_PITCH.md`](counsel-ai/docs/PORTFOLIO_PITCH.md) | Design decisions worth discussing |
| [Wiki](../../wiki) | Guides: getting started, research pipeline, security, roadmap |

## Quick start

```bash
# Backend
cd counsel-ai/backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000

# Desktop app (Linux — wrapper sanitizes conda environments)
cd ../app
./flutter_linux.sh run -d linux

# Or containerized (backend + SearXNG):
cd .. && docker compose up --build
```

## Status

MVP complete and verified: backend smoke tests, WebSocket flow, RAG end-to-end,
Docker stack, Flutter analyzer (0 issues) and widget tests all pass.
See the [Wiki roadmap](../../wiki/Roadmap) for what is intentionally out of scope.

> **Disclaimer:** Counsel AI produces drafts for review by qualified professionals. It is not legal advice.
