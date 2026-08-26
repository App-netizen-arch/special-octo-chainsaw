# Counsel AI

**Local-first AI workbench for legal professionals.** Private chat (on-device GGUF or API), deep research restricted to legitimate sources, document drafting with live MDX preview, and consent-gated tool actions — all behind a single FastAPI conductor and a clean Flutter desktop app.

```
Flutter Desktop App  (Windows / macOS / Linux)
        │  REST + WebSocket   ← the app talks ONLY to this process
        ▼
FastAPI Backend ("unified conductor")
 ├── llm.py             → llama.cpp GGUF (local)  |  OpenAI-compatible API
 ├── research_agent.py  → plan ▸ search ▸ read ▸ write  (adapted gpt-researcher)
 ├── search_client.py   → Tavily / SearXNG + domain whitelist (adapted Vane/Perplexica)
 ├── rag.py             → chunk ▸ embed ▸ FAISS/TF-IDF ▸ page-level citations
 ├── tools_stub.py      → composio-style action stubs with consent envelope
 ├── SQLite             → conversations · messages · settings · documents
 └── FAISS              → vector index for uploaded PDFs/DOCX/TXT
```

## Quick start

### 1. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example ../.env                           # edit LOCAL_MODEL_PATH etc.
uvicorn app.main:app --port 8000
```

Health check: `curl http://127.0.0.1:8000/api/health`

For **Local mode**, download any GGUF model (e.g. `Llama-3.2-3B-Instruct.Q4_K_M.gguf`)
and set `LOCAL_MODEL_PATH` in `.env`. Without a model the app degrades gracefully:
Local mode shows setup guidance instead of failing.

Optional accelerators (auto-detected): `llama-cpp-python`, `sentence-transformers`, `faiss-cpu`.
Without them the backend still runs — TF-IDF embeddings + pure-Python cosine index.

### 2. Flutter desktop app

Requires the GTK dev packages on Linux (`libgtk-3-dev libsecret-1-dev libjsoncpp-dev ninja-build clang cmake pkg-config`),
Xcode on macOS, Visual Studio C++ workload on Windows.

```bash
cd app
flutter pub get

# Linux: use the wrapper if you have conda/miniforge in your shell
# (it sanitizes conda toolchain vars that break CMake's GTK discovery):
./flutter_linux.sh build linux --debug
./flutter_linux.sh run -d linux

# macOS / Windows, or Linux without conda:
flutter run -d macos     # or -d windows
```

The app ships platform folders pre-generated for this repo; run `flutter create`
only if you add platforms.

### 3. Docker (backend + SearXNG)

```bash
cp .env.example .env
docker compose up --build
# backend      → http://localhost:8000
# searxng      → http://localhost:8888  (JSON API enabled)
```

### 4. Tests

```bash
cd backend && python tests/test_smoke.py     # auth, whitelist, citations, tools, REST
cd app && flutter test                       # widget smoke tests
```

## Feature map (acceptance criteria)

| # | Requirement | Where |
|---|-------------|-------|
| 1 | `docker compose up` starts everything | `docker-compose.yml` |
| 2 | Onboarding wizard → chat | `screens/onboarding_screen.dart`, "Skip for demo" defaults to US/California |
| 3 | Local mode offline responses | `services/llm.py::stream_local` + `.env LOCAL_MODEL_PATH` |
| 4 | Research with legitimate sources | `services/research_agent.py` + `utils/domain_whitelist.py`; progress stages streamed over WS |
| 5 | PDF upload → page-cited answers | `services/rag.py` (chunks keep page numbers) |
| 6 | "Draft an NDA" → MDX split view | `screens/document_screen.dart` + template chips + live streaming render |
| 7 | Tool consent modal | `widgets/consent_dialog.dart`; backend refuses unconfirmed external-send actions |
| 8 | Privacy indicator reflects mode | `widgets/privacy_indicator.dart` (green local / amber API / red tool) |

Keyboard shortcuts: `Ctrl+K` command palette · `Ctrl+N` new chat · `Ctrl+Shift+D` documents.

## Security model

- API keys are entered in the app, stored via `flutter_secure_storage` (OS keychain),
  and forwarded per-request only — never persisted server-side by default.
- All `/api/*` routes require the `COUNSEL_TOKEN` header; WebSockets require `?token=`.
- Local mode never transmits message or document content off the machine.
- Research results are filtered against a court/gov/edu/bar-association/publisher
  whitelist *server-side*, before any LLM sees them; social/forums/blogs are hard-denied.

## Repository layout

```
counsel-ai/
├── app/            Flutter desktop app (screens, widgets, services, models, state)
├── backend/app/    FastAPI conductor (routers, services, models, utils) + tests
├── docs/           ARCHITECTURE.md · LICENSE_ATTRIBUTIONS.md · PORTFOLIO_PITCH.md
├── infra/searxng/  SearXNG settings (JSON format enabled)
├── docker-compose.yml · .env.example · README.md
```

## Design language

Perplexity-inspired widescreen desktop UI (see the deployed reference at
`counsel-ai-eosin.vercel.app`): white background `#FFFFFF`, surface `#F7F7F8`,
navy accent `#1B4965`, Inter-style UI type, Source-Serif document preview,
citations always visible in 12px monospace, no gradients, no glassmorphism.

> **Disclaimer:** Counsel AI is an MVP workbench. Outputs are drafts for review
> by qualified professionals — not legal advice.
