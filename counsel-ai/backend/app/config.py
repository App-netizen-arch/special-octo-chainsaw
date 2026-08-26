"""Application configuration.

All runtime configuration is read from environment variables (optionally via a
`.env` file at the repository root). Nothing here talks to the network.
"""

from __future__ import annotations

import os
from pathlib import Path

try:  # optional, keeps the backend runnable without python-dotenv
    from dotenv import load_dotenv

    _ROOT = Path(__file__).resolve().parents[2]
    load_dotenv(_ROOT / ".env")
except ImportError:  # pragma: no cover
    pass


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


class Settings:
    """Central settings object (singleton in app.state)."""

    def __init__(self) -> None:
        # --- server ---
        self.host: str = _env("COUNSEL_HOST", "127.0.0.1")
        self.port: int = int(_env("COUNSEL_PORT", "8000"))
        # Localhost token auth. The Flutter app sends this in X-API-Token
        # (or ?token= for websockets). Change it for anything non-dev.
        self.auth_token: str = _env("COUNSEL_TOKEN", "counsel-dev-token")
        self.cors_origins: list[str] = [
            o.strip() for o in _env("COUNSEL_CORS_ORIGINS", "*").split(",") if o.strip()
        ]

        # --- storage ---
        data_dir = Path(_env("COUNSEL_DATA_DIR", str(Path(__file__).resolve().parents[2] / "data")))
        data_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir: Path = data_dir
        self.db_path: Path = data_dir / "counsel.db"
        self.docs_dir: Path = data_dir / "uploads"
        self.outputs_dir: Path = data_dir / "outputs"
        self.faiss_path: Path = data_dir / "faiss.index"
        self.docs_dir.mkdir(exist_ok=True)
        self.outputs_dir.mkdir(exist_ok=True)

        # --- local LLM (llama.cpp via llama-cpp-python) ---
        self.model_path: str = _env("LOCAL_MODEL_PATH", "")
        self.model_ctx_size: int = int(_env("LOCAL_CTX_SIZE", "8192"))
        self.model_gpu_layers: int = int(_env("LOCAL_GPU_LAYERS", "0"))
        self.model_temperature: float = float(_env("LOCAL_TEMPERATURE", "0.3"))

        # --- API LLM (OpenAI-compatible: DeepSeek, OpenAI, LM Studio...) ---
        self.api_base_url: str = _env("API_BASE_URL", "https://api.deepseek.com/v1")
        self.api_model: str = _env("API_MODEL", "deepseek-chat")
        # NOTE: the key is normally supplied per-request by the Flutter client
        # (stored in the OS keychain there). This env var is a server fallback.
        self.api_key_fallback: str = _env("API_KEY", "")

        # --- search providers ---
        self.search_provider: str = _env("SEARCH_PROVIDER", "tavily")  # tavily | searxng | auto
        self.searxng_url: str = _env("SEARXNG_URL", "http://localhost:8888")
        self.tavily_api_key: str = _env("TAVILY_API_KEY", "")

        # --- research agent ---
        self.research_max_subqueries: int = int(_env("RESEARCH_MAX_SUBQUERIES", "3"))
        self.research_max_results_per_query: int = int(_env("RESEARCH_MAX_RESULTS", "6"))
        self.research_max_page_chars: int = int(_env("RESEARCH_MAX_PAGE_CHARS", "6000"))
        self.research_max_context_chars: int = int(_env("RESEARCH_MAX_CONTEXT_CHARS", "24000"))

    def llm_mode_available(self, mode: str) -> bool:
        if mode == "local":
            return bool(self.model_path) and Path(self.model_path).exists()
        if mode == "api":
            return bool(self.api_base_url)
        return True


settings = Settings()
