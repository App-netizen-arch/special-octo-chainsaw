# Portfolio Pitch — Counsel AI

## The 30-second version

Counsel AI is a local-first AI workbench for lawyers: private chat that can run
entirely on a GGUF model, legal research restricted to courts, governments and
official publishers, document drafting with a live MDX split view, and tool
actions gated behind explicit consent. One FastAPI conductor, one Flutter
desktop app, zero data leakage in Local mode.

## Why it's interesting to talk about

**1. Architecture discipline.**
Five open-source systems (gpt-researcher, Perplexica/Vane, llama.cpp, MDX,
composio) were *extracted, not merged*: each contributed its best ~20% which was
rewritten into focused modules with provenance comments and license
attribution. The interview story: how do you take an Apache-2.0 research agent,
an MIT metasearch frontend, and a JS markdown compiler, and produce one clean
monorepo without vendoring any of them?

**2. Privacy as a product feature, not a checkbox.**
- API keys live in the OS keychain (flutter_secure_storage), forwarded per-request only.
- A localhost token guards every REST route and the WebSocket.
- Local mode is genuinely local: no message or document content leaves the machine.
- API mode shows a persistent amber banner; tool actions show a red consent modal
  and are refused server-side unless `confirmed=true`.

**3. Trustworthy research.**
Search results pass a server-side whitelist (gov/edu/courts/bar associations/
official publishers; social, forums, blogs hard-denied) *before* any model sees
them, then get cosine-similarity ranked (>0.5 keep / >0.75 dedup, Perplexica's
tuned thresholds). Every claim carries `([title](url))` citations plus a
deterministic References appendix — the LLM cannot cite what wasn't retrieved.

**4. Engineering pragmatism.**
- Optional heavy deps (llama-cpp-python, sentence-transformers, faiss-cpu) all
  have pure-Python fallbacks: TF-IDF + hashed cosine index keeps RAG working on
  any laptop with zero native builds.
- Streaming everywhere: llama.cpp tokens pumped from worker threads through an
  asyncio queue so the WebSocket stays responsive during inference.
- Page-level citations come free because PDF chunks remember their page.

## Numbers worth quoting

- Backend smoke suite covers auth, whitelist policy, citation normalization,
  consent enforcement, and full REST surface — runs in seconds, no network.
- Flutter analyzer: 0 issues; widget tests exercise onboarding boot + wizard.
- Research pipeline emits progress frames (`planning → searching → reading →
  writing`) over WebSocket in real time.

## Roadmap hooks (deliberately out of MVP scope)

Real composio OAuth connections, SearXNG engine profiles per jurisdiction,
multi-document comparison views, citation graph export (Bluebook formatting),
team-shared matter workspaces with per-matter encryption keys.
