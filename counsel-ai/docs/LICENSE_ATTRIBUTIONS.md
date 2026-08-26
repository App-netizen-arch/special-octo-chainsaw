# License Attributions

Counsel AI extracts and adapts ideas and code patterns from the following open-source projects. Their licenses are preserved here; all adapted modules carry provenance header comments in source.

| Project | License | Extracted into |
|---|---|---|
| [gpt-researcher](https://github.com/assafelovic/gpt-researcher) | Apache-2.0 | `backend/app/services/research_agent.py`, `backend/app/utils/citation_normalizer.py`, `backend/app/utils/domain_whitelist.py` |
| Vane / Perplexica-style search (upstream: [Perplexica](https://github.com/ItzCrazyKns/Perplexica)) | MIT | `backend/app/services/search_client.py` |
| [llama.cpp](https://github.com/ggml-org/llama.cpp) + [llama-cpp-python](https://github.com/abetlen/llama-cpp-python) | MIT | `backend/app/services/llm.py` |
| [MDX](https://github.com/mdx-js/mdx) | MIT | `app/lib/widgets/mdx_preview.dart`, `backend/app/services/mdx_generator.py` |
| [Composio](https://github.com/ComposioHQ/composio) | Apache-2.0 | `backend/app/services/tools_stub.py` |

Full license texts of the upstream projects:

- **Apache License 2.0** — applies to gpt-researcher and composio derivations. A copy is available at https://www.apache.org/licenses/LICENSE-2.0. NOTICE: This product includes software developed by the respective upstream authors.
- **MIT License** — applies to Perplexica/Vane, llama.cpp, and MDX derivations. Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files, to deal in the Software without restriction, subject to the above copyright notice and this permission notice being included in all copies or substantial portions of the Software.

Runtime dependencies retain their own licenses (FastAPI/MIT, Starlette/BSD-3, httpx/BSD-3, pydantic/MIT, pypdf/BSD-3, python-docx/MIT, Flutter SDK/BSD-3, provider/MIT, flutter_markdown/BSD-3, pdf/Apache-2.0, archive/MIT-or-Apache-2.0, file_picker/MIT, flutter_secure_storage/BSD-3, shared_preferences/BSD-3, web_socket_channel/BSD-3).

SearXNG runs as an unmodified external container (AGPL-3.0) via Docker Compose and is not linked into this codebase.
