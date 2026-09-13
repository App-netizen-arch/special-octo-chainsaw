# Workspace Documentation
## `/home/amanoy/Freelancing /special-octo-chainsaw`

---

## 1. Workspace Overview

| Property | Value |
|---|---|
| Root | `/home/amanoy/Freelancing /special-octo-chainsaw` |
| VCS | Git |
| Total size | ~7.3 GB |
| Projects | 6 repositories + shared scripts |
| Primary language | TypeScript, Python, C++, Dart |
| License mix | MIT, Apache-2.0 |

**Note:** The workspace path contains a space (`Freelancing /special-octo-chainsaw`), which caused build-tool resolution issues in pnpm/turbo/vitest paths. These were fixed by replacing `new URL(import.meta.url).pathname` with `fileURLToPath(import.meta.url)` in affected configs.

---

## 2. Root-Level Files

| Path | Purpose |
|---|---|
| `README.md` | Workspace overview, quickstart, provenance table |
| `.gitignore` | Git ignore rules |
| `opencode.json` | OpenCode configuration |
| `scripts/` | Shared workspace scripts |

---

## 3. Project Inventory

### 3.1 `counsel-ai/` — Primary Product (2.2 MB)
**Stack:** Flutter Desktop (frontend) + FastAPI/Python (backend) + SQLite + FAISS + llama.cpp GGUF

**Purpose:** Local-first AI workbench for legal professionals. Combines private on-device chat, legal research, document Q&A, and MDX-based document drafting.

```
counsel-ai/
├── app/                          # Flutter Desktop app
│   ├── lib/
│   │   ├── models/               # Dart data models
│   │   ├── screens/              # UI screens
│   │   ├── services/             # Business logic / API clients
│   │   ├── state/                # State management
│   │   └── widgets/              # Reusable UI components
│   ├── linux/                    # Linux desktop runner
│   ├── macos/                    # macOS desktop runner
│   ├── windows/                  # Windows desktop runner
│   └── test/                     # Flutter widget tests
├── backend/                      # FastAPI backend
│   ├── app/
│   │   ├── models/               # SQLAlchemy / Pydantic models
│   │   ├── routers/              # FastAPI route handlers
│   │   ├── services/             # Business logic
│   │   └── utils/                # Helpers
│   ├── alembic/                  # Database migrations
│   ├── tests/                    # pytest tests (74 passing)
│   └── requirements.txt
├── docs/
│   ├── ARCHITECTURE.md           # Module provenance, WS protocol
│   ├── LICENSE_ATTRIBUTIONS.md   # License obligations
│   └── PORTFOLIO_PITCH.md        # Design decisions
├── infra/
│   └── searxng/                  # SearXNG infra config
└── scripts/
```

**Key features extracted from reference projects:**
- Research loop (plan → search → read → write) from `gpt-researcher-main`
- SearXNG integration + ranking/dedup from `Vane-master`
- GGUF inference/streaming patterns from `llama.cpp-master`
- MDX document model from `mdx-main`
- Action interface/consent envelope from `composio-next`

---

### 3.2 `composio-next/` — TypeScript SDK Monorepo (2.5 GB)
**Stack:** pnpm workspaces, Turbo, Vitest, TypeScript, Effect.ts, Bun

**Purpose:** Composio SDK v3 — AI tool-use orchestration layer. Provides `@composio/core`, provider adapters, CLI, and the experimental Eve/π integrations.

```
composio-next/
├── ts/                                    # TypeScript workspace root
│   ├── packages/
│   │   ├── core/                         # @composio/core
│   │   │   ├── src/                      # Core SDK source
│   │   │   ├── test/                     # Unit tests (1111 passing)
│   │   │   ├── generated/                # Auto-generated SDK surfaces
│   │   │   ├── pack/                     # Pack templates
│   │   │   ├── docs/                     # Package docs
│   │   │   ├── dist/                     # Built output
│   │   │   ├── vitest.config.ts          # Test config with #platform aliases
│   │   │   └── tsdown.config.ts          # Build config
│   │   ├── experimental/                 # @composio/experimental
│   │   │   ├── src/                      # Eve/π integrations
│   │   │   ├── test/                     # Tests (36 passing)
│   │   │   └── vitest.config.ts          # Clean config (aliases removed)
│   │   ├── json-schema-to-zod/           # @composio/json-schema-to-zod
│   │   │   ├── src/
│   │   │   ├── test/                     # Tests (118 passing)
│   │   │   └── vitest.config.ts
│   │   ├── json-schema-to-effect-schema/ # @composio/json-schema-to-effect-schema
│   │   │   ├── src/
│   │   │   ├── test/                     # Tests (65 passing)
│   │   │   └── vitest.config.ts          # Uses @composio/json-schema-to-zod alias
│   │   ├── ts-builders/                  # @composio/ts-builders
│   │   │   ├── src/                      # AST builder utilities
│   │   │   └── test/                     # Tests (91 passing)
│   │   ├── cli/                          # @composio/cli (Effect-based)
│   │   │   ├── src/                      # CLI source
│   │   │   ├── test/                     # Tests (1274 passing)
│   │   │   └── vitest.config.ts          # Complex aliases for workspace deps
│   │   ├── cli-keyring/                  # @composio/cli-keyring
│   │   ├── cli-local-tools/              # @composio/cli-local-tools
│   │   ├── slim/                         # @composio/slim
│   │   ├── providers/                    # Provider adapters
│   │   │   ├── openai/
│   │   │   ├── anthropic/
│   │   │   ├── google/
│   │   │   ├── cloudflare/
│   │   │   └── ...
│   │   └── e2e-tests/                    # Docker runtime E2E tests
│   ├── vendor/                           # Vendored Effect/Clack (read-only)
│   └── scripts/                          # Build/release scripts
├── python/                               # Python SDK
│   ├── composio/                         # Python package
│   ├── providers/                        # Python providers
│   └── pyproject.toml
├── docs/                                 # Fumadocs documentation site
├── skills/                               # Repo-local agent skills
├── test/                                 # Release workflow + install tests
├── .agents/                              # Canonical agent skills
├── .changeset/                           # Changeset config
├── .github/                              # GitHub Actions workflows
├── package.json                          # pnpm workspace root
├── pnpm-workspace.yaml                   # Workspace package globs
└── pnpm-lock.yaml                        # Lockfile
```

**Test results:** 26 packages tested via turbo; all pass.

---

### 3.3 `gpt-researcher-main/` — Research Agent (32 MB)
**Stack:** Python, FastAPI, LangChain/LangGraph, Tavily/Serper

**Purpose:** Autonomous AI research agent that plans, searches, reads, and writes research reports. Used as the research-loop backbone in `counsel-ai`.

```
gpt-researcher-main/
├── gpt_researcher/                       # Main Python package
│   ├── retrievers/                       # Search retrievers
│   │   └── __init__.py                   # Exports get_all_retriever_names
│   ├── backend/                          # Backend logic
│   ├── deep_agents/                      # Deep research agents
│   ├── multi_agents/                     # Multi-agent orchestration
│   └── ...
├── backend/                              # FastAPI server
│   ├── chat/                             # Chat endpoints
│   ├── memory/                           # Memory management
│   ├── report_type/                      # Report generators
│   └── server/                           # Server startup
├── frontend/                             # Web frontend
├── mcp-server/                           # MCP server integration
├── evals/                                # Evaluation scripts
├── tests/                                # pytest tests (274+ passing)
├── docs/                                 # Documentation
├── terraform/                            # Infrastructure as code
├── skills/                               # Agent skills
├── logs/                                 # Runtime logs
├── outputs/                              # Generated reports
├── pyproject.toml                        # Project config (--forked added)
└── requirements.txt
```

**Key concept:** Plan → Search → Read → Write pipeline with source-cited outputs.

---

### 3.4 `llama.cpp-master/` — LLM Inference Engine (1.7 GB)
**Stack:** C++, CMake, CUDA/OpenCL/Metal, Python bindings, Android NDK

**Purpose:** GGUF-format LLM inference. Provides on-device model execution for `counsel-ai` and the Android example app.

```
llama.cpp-master/
├── src/                   # Core C++ inference engine
├── include/               # Public headers
├── ggml/                  # GGML tensor library
├── common/                # Shared utilities (sampling, quantization)
├── examples/
│   ├── llama.android/     # Android example app (Gradle/Kotlin)
│   │   ├── app/           # Android app module
│   │   ├── lib/           # Native JNI library
│   │   ├── build.gradle.kts
│   │   └── settings.gradle.kts
│   ├── llama.swiftui/     # SwiftUI example
│   ├── batched/           # Batched inference
│   └── ...
├── tools/                 # Model conversion/quantization tools
├── tests/                 # Unit tests (60 passing)
├── build/                 # CMake build directory (pre-built)
├── cmake/                 # CMake modules
├── docs/                  # Documentation
├── scripts/               # Utility scripts
├── conversion/            # Model format converters
├── grammars/              # Grammar-constrained generation
├── vendor/                # Vendored dependencies
└── CMakeLists.txt         # Root CMake config
```

---

### 3.5 `Vane-master/` — Perplexica-Inspired Search (3.1 GB)
**Stack:** Next.js, React, TypeScript, Drizzle ORM, Tailwind CSS, Vitest

**Purpose:** AI-powered search engine with SearXNG integration, ranking, and dedup. Provides the whitelisted-search component for `counsel-ai`.

```
Vane-master/
├── src/
│   ├── app/               # Next.js App Router pages
│   ├── components/        # React components
│   ├── actions/           # Server actions
│   ├── providers/         # Search providers
│   ├── hooks/             # React hooks
│   ├── lib/               # Utilities
│   └── types/             # TypeScript types
├── drizzle/               # Drizzle ORM schema/migrations
├── data/                  # Static data
├── docs/
│   ├── API/
│   ├── architecture/
│   └── installation/
├── public/                # Static assets
├── .next/                 # Next.js build output
├── node_modules/          # Dependencies
├── package.json           # Next.js + vitest + testing-library
├── vitest.config.ts       # Test config
├── vitest.setup.ts        # Test setup
└── next-env.d.ts
```

---

### 3.6 `mdx-main/` — MDX Documentation Framework (428 MB)
**Stack:** TypeScript, MDX, Remark/Rehype, Vitest

**Purpose:** MDX document processing framework. Provides the frontmatter/component document model for `counsel-ai`'s document drafting feature.

```
mdx-main/
├── packages/
│   └── mdx/               # Core MDX package
│       ├── src/           # MDX compiler/processor
│       ├── test/          # Tests (40+ passing)
│       │   └── context/
│       │       └── sourcemap.js
│       └── ...
├── docs/                  # Documentation site
│   ├── blog/
│   ├── guides/
│   ├── packages/
│   └── ...
├── website/               # Documentation website
├── script/                # Build/utility scripts
├── node_modules/
├── package.json
└── readme.md
```

---

## 4. Cross-Cutting Concerns

### 4.1 Test Infrastructure
| Project | Framework | Test Count | Status |
|---|---|---|---|
| counsel-ai backend | pytest | 74 | Passing |
| gpt-researcher-main | pytest | 274+ | Passing (--forked) |
| llama.cpp | CTest/catch2 | 60 | Passing |
| mdx-main | Vitest | 40+ | Passing |
| Vane-master | Vitest | 1+ | Passing |
| composio-next core | Vitest | 1111 | Passing |
| composio-next openai | Vitest | 34 | Passing |
| composio-next json-schema-to-zod | Vitest | 118 | Passing |
| composio-next experimental | Vitest | 36 | Passing |
| composio-next cli | Vitest | 1274 | Passing |
| composio-next ts-builders | Vitest | 91 | Passing |
| composio-next json-schema-to-effect-schema | Vitest | 65 | Passing |

### 4.2 Known Issues Fixed
| Issue | Root Cause | Fix |
|---|---|---|
| pnpm/turbo fails with spaces in path | URL-encoded `%20` in `import.meta.url` | Use `fileURLToPath()` |
| `@composio/core` workspace linking in experimental | Missing dev deps at workspace root | Installed `@composio/client`, `eve`, `safe-stable-stringify`, `typebox`, `@earendil-works/pi-coding-agent` |
| `@composio/json-schema-to-zod` resolution | Broken vitest alias paths | Fixed alias calculation |
| CLI stack trace tests fail with spaces | `path.resolve('.')` differs in test sandbox | Fixed `stripCwdPath` regex, stack parsing |
| counsel-ai audit-log test | Wrong endpoint + datetime conversion | Fixed endpoint path + `datetime.now()` |
| gpt-researcher pytest module caching | Test isolation | Added `--forked` flag |

### 4.3 Path-Space Caveat
The workspace root `/home/amanoy/Freelancing /special-octo-chainsaw` contains a space. Any new tooling must handle this correctly. Prefer `fileURLToPath(import.meta.url)` over `new URL(import.meta.url).pathname` in ESM configs.

---

## 5. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    counsel-ai/ (Product)                         │
│  ┌──────────────┐    WebSocket/REST    ┌────────────────────┐  │
│  │ Flutter App  │ ◄──────────────────► │ FastAPI Backend    │  │
│  │ (Desktop)    │                      │ - RAG + FAISS      │  │
│  └──────────────┘                      │ - Research agent   │  │
│                                        │ - SearXNG search   │  │
│                                        │ - Tool stubs       │  │
│                                        │ - SQLite + vectors │  │
│                                        └────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ extracts from
         ┌────────────────────┼────────────────────┐
         │                    │                    │
┌────────┴────────┐  ┌────────┴────────┐  ┌───────┴──────────┐
│ gpt-researcher  │  │    Vane-master  │  │  llama.cpp       │
│ (Python)        │  │ (Next.js/TS)    │  │  (C++/Android)   │
│ - Research loop │  │ - SearXNG       │  │ - GGUF inference │
│ - Citations     │  │ - Ranking/dedup │  │ - Android example│
└─────────────────┘  └─────────────────┘  └──────────────────┘
         │                    │                    │
         └────────────────────┼────────────────────┘
                              │
                    ┌─────────┴──────────┐
                    │   mdx-main         │
                    │ (MDX framework)    │
                    │ - Document model   │
                    │ - Frontmatter      │
                    └────────────────────┘
                              │
                    ┌─────────┴──────────┐
                    │  composio-next     │
                    │ (TypeScript SDK)   │
                    │ - @composio/core   │
                    │ - CLI (Effect.ts)  │
                    │ - Providers        │
                    │ - Experimental     │
                    └────────────────────┘
```

---

## 6. Quick Reference

| Task | Command |
|---|---|
| Run all composio-next tests | `cd ts && CI=true BYPASS_TOOLCHAIN_CHECK=1 pnpm exec turbo test --filter=./packages/**` |
| Run experimental tests | `cd ts/packages/experimental && CI=true BYPASS_TOOLCHAIN_CHECK=1 pnpm test` |
| Run counsel-ai backend tests | `cd counsel-ai/backend && pytest` |
| Run gpt-researcher tests | `cd gpt-researcher-main && pytest --forked` |
| Run Vane tests | `cd Vane-master && npx vitest run` |
| Run mdx tests | `cd mdx-main/packages/mdx && pnpm test` |
| Run llama.cpp tests | `cd llama.cpp-master/build && ctest --output-on-failure` |
| Build composio-next packages | `cd composio-next/ts && CI=true BYPASS_TOOLCHAIN_CHECK=1 pnpm build:packages` |
| Build llama.cpp | `cd llama.cpp-master && cmake -B build && cmake --build build` |

---

*Generated: 2026-09-11*
