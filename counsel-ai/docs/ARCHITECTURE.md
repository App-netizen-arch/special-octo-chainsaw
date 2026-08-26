# Architecture

## Principles

1. **Single entry point.** The Flutter app speaks only to the FastAPI backend
   (REST + one WebSocket endpoint). No service is ever exposed to the client.
2. **Extract, don't merge.** Logic adapted from the five upstream repositories
   was rewritten into focused Python/Dart modules; nothing is imported wholesale.
3. **Degrade gracefully.** Every optional dependency (GGUF model, Tavily key,
   SearXNG container, FAISS, sentence-transformers) has a working fallback and a
   plain-language error path surfaced in the UI.

## Module provenance map

| Backend module | Adapted from | What was kept |
|---|---|---|
| `services/research_agent.py` | **gpt-researcher** (Apache-2.0) | plan→search→read→write loop, sub-query prompt style ("Write N search queries…"), context compression before writing, deterministic `## References` appendix, `([title](url))` in-text citation convention |
| `services/search_client.py` | **Vane/Perplexica** (MIT) + gpt-researcher retriever contract | SearXNG `?format=json` call shape, result normalization (`content = snippet or title`), cosine-sim ranking (>0.5 keep), greedy dedup (>0.75 drop), cap 20; whitelist filtering replaces gpt-researcher's `query_domains` |
| `services/llm.py` | **llama.cpp / llama-cpp-python** (MIT) | GGUF loading, OpenAI-style chat completions with token streaming, chat template handling; worker-thread pump keeps the event loop responsive |
| `widgets/mdx_preview.dart` | **MDX compiler** (MIT) | Component-model idea: frontmatter exports are metadata (hidden from render) while markdown content renders; simplified to a Dart-side parser over the same document model |
| `services/tools_stub.py` | **composio** (Apache-2.0) | Tool = {slug, name, description, JSON-Schema input, execute}; execution envelope `{successful, data, error}`; consent gate stands in for OAuth connection flow |

## Data flow: one research turn

```
Flutter (Research mode)
  └─ WS {type:"chat", mode:"research"}
       backend:
         1. generate sub-queries        (LLM, JSON array — falls back to heuristics)
         2. web_search per sub-query    (Tavily/SearXNG → domain whitelist → rank+dedupe)
         3. read top pages              (httpx fetch, HTML→text, per-page char cap)
         4. compress context            (cap total chars; summarize if >12k)
         5. write memo                  (LLM, citations required per claim)
         6. normalize citations         (one Source schema) + References appendix
       WS ▸ research_progress{planning|searching|reading|writing}
       WS ▸ sources[] · token(report) · done
```

## WebSocket frame protocol

Client → `{type:"chat", message, conversation_id?, mode, api_key?, document_ids?, mdx?, template?}`
Server → sequence of:

| Frame | Meaning |
|---|---|
| `conversation` | new conversation id/title created |
| `status` / `research_progress` | thinking indicator / pipeline stage |
| `token` / `mdx_token` | streamed text (mdx_token routes to the split-view editor) |
| `sources` | normalized citations for the current turn |
| `mdx_template` | full skeleton (template chips bypass the LLM) |
| `done` / `error` | turn complete / friendly failure |

## Storage

- SQLite (`data/counsel.db`, WAL): `conversations`, `messages` (with sources JSON),
  `documents`, `settings` (jurisdiction, onboarding, extra whitelist hosts).
- Vector index (`data/faiss.index`): chunk metadata incl. page numbers + snippet,
  vectors as TF-IDF hashed dicts or dense lists when sentence-transformers present.
  FAISS `IndexFlatIP` used opportunistically in-process.

## Scaling notes

Adding a capability = new module under `app/services/` + router + optional
container in compose. The conductor pattern keeps Flutter untouched.
