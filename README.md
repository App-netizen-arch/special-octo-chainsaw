# Counsel AI — Workspace

This repository contains the **Counsel AI** product (`counsel-ai/`) together with the five open-source repositories whose logic was studied and extracted (not merged) to build it.

## The product

**`counsel-ai/`** — a local-first AI workbench for legal professionals:

- Private AI chat running on-device (llama.cpp GGUF) or via an OpenAI-compatible API
- Deep legal research restricted to legitimate sources (courts, governments, academia, bar associations) with full citations
- Document Q&A over uploaded PDFs with page-level citations
- Legal document drafting with live MDX split-view preview and .docx / .pdf export
- Consent-gated external tool actions

Full setup instructions, architecture and acceptance-criteria mapping: **[counsel-ai/README.md](counsel-ai/README.md)**

```
Flutter Desktop App  ──REST + WS──▶  FastAPI conductor
                                     ├── llama.cpp (local) / OpenAI-compatible API
                                     ├── research agent   (adapted gpt-researcher)
                                     ├── search + domain whitelist (adapted Perplexica/Vane)
                                     ├── RAG: FAISS + page-aware citations
                                     ├── tools stub       (composio-style)
                                     └── SQLite + vector index
```

## Reference repositories

| Directory | Upstream project | License | What was extracted |
|---|---|---|---|
| `gpt-researcher-main` | [gpt-researcher](https://github.com/assafelovic/gpt-researcher) | Apache-2.0 | research loop (plan → search → read → write), citation format |
| `Vane-master` | Perplexica-style engine ([Perplexica](https://github.com/ItzCrazyKns/Perplexica)) | MIT | SearXNG integration, result ranking/dedup thresholds |
| `llama.cpp-master` | [llama.cpp](https://github.com/ggml-org/llama.cpp) | MIT | GGUF inference & streaming patterns |
| `mdx-main` | [MDX](https://github.com/mdx-js/mdx) | MIT | frontmatter/component document model |
| `composio-next` | [Composio](https://github.com/ComposioHQ/composio) | Apache-2.0 | tool/action interface & consent patterns |

Attribution details: [`counsel-ai/docs/LICENSE_ATTRIBUTIONS.md`](counsel-ai/docs/LICENSE_ATTRIBUTIONS.md)

## Quick start

```bash
# Backend
cd counsel-ai/backend && pip install -r requirements.txt
uvicorn app.main:app --port 8000

# Desktop app (Linux; use the wrapper if conda is active in your shell)
cd counsel-ai/app
./flutter_linux.sh run -d linux

# Or everything containerized:
cd counsel-ai && docker compose up --build
```
