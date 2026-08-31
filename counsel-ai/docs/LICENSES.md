# Counsel AI - Licenses and Attributions

This document lists all third-party libraries, models, and code used in Counsel AI with their respective licenses and attributions.

## Table of Contents

1. [Core Application](#core-application)
2. [Backend Dependencies](#backend-dependencies)
3. [Frontend Dependencies](#frontend-dependencies)
4. [AI Models](#ai-models)
5. [Extracted/Adapted Code](#extractedadapted-code)
6. [Icons and Assets](#icons-and-assets)
7. [License Compliance Summary](#license-compliance-summary)

---

## Core Application

### Counsel AI (This Project)

**License:** MIT License  
**Copyright:** © 2024 Counsel AI Contributors

```
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## Backend Dependencies

| Package | Version | License | URL |
|---------|---------|---------|-----|
| FastAPI | 0.109+ | MIT | https://github.com/tiangolo/fastapi |
| SQLAlchemy | 2.0+ | MIT | https://www.sqlalchemy.org |
| Pydantic | 2.0+ | MIT | https://docs.pydantic.dev |
| Uvicorn | 0.27+ | BSD-3 | https://www.uvicorn.org |
| httpx | 0.27+ | BSD-3 | https://www.python-httpx.org |
| bcrypt | 4.0+ | Apache-2.0 | https://github.com/pyca/bcrypt |
| PyJWT | 2.8+ | MIT | https://pyjwt.readthedocs.io |
| APScheduler | 3.10+ | MIT | https://apscheduler.readthedocs.io |
| cryptography | 42.0+ | Apache-2.0/BSD-3 | https://cryptography.io |
| keyring | 24.0+ | MIT | https://github.com/jaraco/keyring |
| sqlcipher3 | 4.5+ | Public Domain/Zlib | https://github.com/rigglemania/sqlcipher3 |
| llama-cpp-python | 0.2+ | MIT | https://github.com/abetlen/llama-cpp-python |
| sentence-transformers | 2.3+ | Apache-2.0 | https://www.sbert.net |
| faiss-cpu | 1.7+ | MIT | https://github.com/facebookresearch/faiss |
| rank-bm25 | 0.2+ | Apache-2.0 | https://github.com/dorianbrown/rank_bm25 |
| spacy (optional) | 3.7+ | MIT | https://spacy.io |
| feedparser | 6.0+ | MIT | https://github.com/kurtmckee/feedparser |

### License Texts

**MIT License** (FastAPI, SQLAlchemy, Pydantic, etc.):
```
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files...
```

**Apache License 2.0** (bcrypt, cryptography, sentence-transformers):
```
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://www.apache.org/licenses/LICENSE-2.0
```

**BSD 3-Clause License** (Uvicorn, httpx):
```
Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:
1. Redistributions of source code must retain the above copyright notice...
```

---

## Frontend Dependencies (Flutter)

| Package | Version | License | URL |
|---------|---------|---------|-----|
| Flutter SDK | 3.19+ | BSD-3 | https://flutter.dev |
| provider | 6.1+ | MIT | https://pub.dev/packages/provider |
| http | 1.2+ | BSD-3 | https://pub.dev/packages/http |
| web_socket_channel | 3.0+ | BSD-3 | https://pub.dev/packages/web_socket_channel |
| flutter_markdown | 0.7+ | BSD-3 | https://pub.dev/packages/flutter_markdown |
| file_picker | 8.1+ | MIT | https://pub.dev/packages/file_picker |
| flutter_secure_storage | 9.2+ | MIT | https://pub.dev/packages/flutter_secure_storage |
| pdf | 3.11+ | Apache-2.0 | https://pub.dev/packages/pdf |
| archive | 3.6+ | MIT | https://pub.dev/packages/archive |
| shared_preferences | 2.3+ | BSD-3 | https://pub.dev/packages/shared_preferences |
| package_info_plus | 8.1+ | BSD-3 | https://pub.dev/packages/package_info_plus |
| url_launcher | 6.3+ | BSD-3 | https://pub.dev/packages/url_launcher |
| intl | 0.19+ | BSD-3 | https://pub.dev/packages/intl |

### Typography (Optional)

| Font | License | URL |
|------|---------|-----|
| Inter | SIL Open Font License 1.1 | https://rsms.me/inter |
| Source Serif Pro | SIL Open Font License 1.1 | https://github.com/adobe-fonts/source-serif |

---

## AI Models

Counsel AI supports multiple commercially-licensed models. Users must comply with each model's license terms.

| Model | Provider | License | Commercial Use | Attribution Required |
|-------|----------|---------|----------------|---------------------|
| DeepSeek Coder | DeepSeek AI | MIT | ✅ Yes | Yes |
| Mistral 7B | Mistral AI | Apache 2.0 | ✅ Yes | Yes |
| Gemma 2B/7B | Google | Gemma Terms | ✅ Yes (with restrictions) | Yes |
| Phi-2 | Microsoft | MIT | ✅ Yes | Yes |
| Llama 2/3 | Meta | Llama Community License | ⚠️ Restricted | Yes |

### Model-Specific Notes

**DeepSeek Coder:**
- License: MIT
- Commercial use: Allowed
- Attribution: "Powered by DeepSeek" recommended

**Mistral 7B:**
- License: Apache 2.0
- Commercial use: Allowed
- No specific attribution requirements

**Gemma (Google):**
- License: Gemma Terms of Use
- Commercial use: Allowed with restrictions
- Must not use for certain prohibited purposes
- See: https://ai.google.dev/gemma/terms

**Llama 2/3 (Meta):**
- License: Llama Community License
- Commercial use: Allowed with <700M MAU restriction
- Must request license from Meta for commercial deployment
- Not recommended for commercial products without explicit licensing

⚠️ **Important:** Always verify current model licenses before deployment. Model licenses may change.

---

## Extracted/Adapted Code

### gpt-researcher

**Source:** https://github.com/assafelovic/gpt-researcher  
**License:** MIT License  
**Usage:** Research agent logic adapted into backend `services/research_agent.py`

```
MIT License
Copyright (c) 2023 Assaf Elovic

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files...
```

### Perplexica

**Source:** https://github.com/ItzCrazyKns/Perplexica  
**License:** MIT License  
**Usage:** Search ranking and citation logic adapted

```
MIT License
Copyright (c) 2024 ItzCrazyKns
```

### llama.cpp

**Source:** https://github.com/ggerganov/llama.cpp  
**License:** MIT License  
**Usage:** Local inference via llama-cpp-python wrapper

```
MIT License
Copyright (c) 2023 Georgi Gerganov
```

### MDX Compiler Concepts

**Source:** MDX specification (https://mdxjs.com)  
**License:** MIT License  
**Usage:** MDX parsing concepts adapted for Dart implementation

```
MIT License
Copyright (c) 2023 Vercel, Inc.
```

### Composio

**Source:** https://github.com/ComposioHQ/composio  
**License:** Apache 2.0  
**Usage:** Tool connector architecture patterns

```
Apache License
Version 2.0, January 2004
```

---

## Icons and Assets

| Asset | Source | License |
|-------|--------|---------|
| Material Icons | Google | Apache 2.0 |
| App Icon | Custom | © Counsel AI |
| UI Sounds | Custom | © Counsel AI |

---

## License Compliance Summary

### License Distribution

| License Type | Count | Percentage |
|--------------|-------|------------|
| MIT | 25+ | ~60% |
| Apache 2.0 | 10+ | ~25% |
| BSD-3 | 8+ | ~10% |
| Other | 2+ | ~5% |

### Compliance Checklist

✅ **MIT Licensed Components:**
- Include copyright notice in LICENSES.md
- Include license text in distribution

✅ **Apache 2.0 Licensed Components:**
- Include license text
- Note significant changes if any
- Include NOTICE file if present in original

✅ **BSD Licensed Components:**
- Retain copyright notices
- Include license text

✅ **SIL Open Font License:**
- Include font license with distributions containing fonts
- Fonts are optional; app works without them

✅ **Model Licenses:**
- Users responsible for model license compliance
- Documentation includes license guidance
- Non-commercial models blocked by default

### Notices

**No GPL/LGPL Dependencies:** This project intentionally avoids GPL-licensed dependencies to allow commercial use.

**No Copyleft Requirements:** All dependencies use permissive licenses; derivative works may be proprietary.

---

## Third-Party Services

Counsel AI can integrate with these external services (optional):

| Service | Purpose | Terms |
|---------|---------|-------|
| HuggingFace | Model downloads | Apache 2.0 / Model-specific |
| Tavily API | Web search | Commercial terms apply |
| SearXNG | Self-hosted search | AGPL-3.0 (if self-hosted) |
| OpenAI API | LLM inference | OpenAI Terms of Service |
| DeepSeek API | LLM inference | DeepSeek Terms |

⚠️ **Note:** Using external APIs subjects users to those services' terms and privacy policies. Local mode avoids external dependencies.

---

## Security Dependencies

| Package | Purpose | License |
|---------|---------|---------|
| SQLCipher | Database encryption | Public Domain / OpenSSL License |
| cryptography | File encryption | Apache 2.0 / BSD-3 |
| bcrypt | Password hashing | Apache 2.0 |

---

## Development Dependencies (Not Distributed)

These packages are used only during development/testing:

| Package | License |
|---------|---------|
| pytest | MIT |
| pytest-asyncio | Apache 2.0 |
| pytest-cov | MIT |
| black | MIT |
| ruff | MIT |
| flutter_test | BSD-3 |
| flutter_lints | BSD-3 |

---

## Contact for Licensing Questions

For questions about licensing or attribution requirements:
- Email: legal@counsel-ai.example.com
- GitHub: Create an issue labeled "licensing"

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2024-01-01 | Initial license documentation |

---

*Last updated: January 2024*

**Disclaimer:** This document is for informational purposes only and does not constitute legal advice. Consult with legal counsel for specific licensing questions.
