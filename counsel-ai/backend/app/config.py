"""Counsel AI — application configuration.

All runtime configuration is read from environment variables (optionally via a
`.env` file at the repository root). Nothing here talks to the network.

Production notes
----------------
* Secrets never live in this file. API keys and OAuth tokens are stored in the
  OS keychain by the Flutter client and forwarded per-request; the env vars in
  ``API_KEY`` / ``TAVILY_API_KEY`` are server-side fallbacks for headless
  deployments only.
* In production set a strong ``COUNSEL_JWT_SECRET`` and change the bootstrap
  admin password immediately after first login.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

try:  # optional, keeps the backend runnable without python-dotenv
    from dotenv import load_dotenv

    _ROOT = Path(__file__).resolve().parents[2]
    load_dotenv(_ROOT / ".env")
except ImportError:  # pragma: no cover
    pass


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _env_int(key: str, default: int) -> int:
    try:
        return int(_env(key, str(default)))
    except ValueError:
        return default


def _env_float(key: str, default: float) -> float:
    try:
        return float(_env(key, str(default)))
    except ValueError:
        return default


def _env_bool(key: str, default: bool) -> bool:
    raw = _env(key, "true" if default else "false").strip().lower()
    return raw in {"1", "true", "yes", "on"}


class Settings:
    """Central settings object (singleton)."""

    def __init__(self) -> None:
        # --- server -------------------------------------------------------
        self.host: str = _env("COUNSEL_HOST", "127.0.0.1")
        self.port: int = _env_int("COUNSEL_PORT", 8000)
        self.environment: str = _env("COUNSEL_ENV", "production")  # dev|production
        self.cors_origins: list[str] = [
            o.strip() for o in _env("COUNSEL_CORS_ORIGINS", "*").split(",") if o.strip()
        ]
        self.log_level: str = _env("COUNSEL_LOG_LEVEL", "INFO")
        self.log_dir: Path | None = None  # set below alongside data_dir

        # --- authentication -------------------------------------------------
        # JWT secret. Generated once per install and persisted to the data dir
        # when not provided via env (single-user local installs).
        self.jwt_secret: str = _env("COUNSEL_JWT_SECRET", "")
        self.jwt_algorithm: str = "HS256"
        self.access_token_minutes: int = _env_int("COUNSEL_ACCESS_TOKEN_MINUTES", 30)
        self.refresh_token_days: int = _env_int("COUNSEL_REFRESH_TOKEN_DAYS", 30)
        # Legacy shared-token auth is kept ONLY for pre-login health checks.
        self.bootstrap_token: str = _env("COUNSEL_TOKEN", "")

        # --- storage --------------------------------------------------------
        data_dir = Path(
            _env("COUNSEL_DATA_DIR", str(Path(__file__).resolve().parents[2] / "data"))
        )
        data_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir: Path = data_dir
        self.db_path: Path = data_dir / "counsel.db"
        self.docs_dir: Path = data_dir / "uploads"
        self.outputs_dir: Path = data_dir / "outputs"
        self.index_dir: Path = data_dir / "index"
        self.logs_dir: Path = data_dir / "logs"
        self.keys_path: Path = data_dir / ".instance.key"
        for d in (self.docs_dir, self.outputs_dir, self.index_dir, self.logs_dir):
            d.mkdir(exist_ok=True)

        # --- encryption at rest ----------------------------------------------
        # AES-256-GCM key material lives in the instance key file (0600) or the
        # OS keychain when available; uploads/index/DB use it. SQLCipher is used
        # for the DB when the driver is installed, otherwise the SQLite file is
        # stored inside an encrypted container directory with tightened perms.
        self.encrypt_at_rest: bool = _env_bool("COUNSEL_ENCRYPT_AT_REST", True)

        # --- local LLM (llama.cpp via llama-cpp-python) ----------------------
        self.model_path: str = _env("LOCAL_MODEL_PATH", "")
        self.model_ctx_size: int = _env_int("LOCAL_CTX_SIZE", 8192)
        self.model_gpu_layers: int = _env_int("LOCAL_GPU_LAYERS", -1)  # -1 = auto-detect
        self.model_temperature: float = _env_float("LOCAL_TEMPERATURE", 0.3)
        self.model_batch_size: int = _env_int("LOCAL_BATCH_SIZE", 256)
        self.enforce_commercial_models: bool = _env_bool("COUNSEL_ENFORCE_COMMERCIAL_MODELS", False)

        # --- API LLM (OpenAI-compatible: DeepSeek, OpenAI, ...) ---------------
        self.api_base_url: str = _env("API_BASE_URL", "https://api.deepseek.com/v1")
        self.api_model: str = _env("API_MODEL", "deepseek-chat")
        self.api_key_fallback: str = _env("API_KEY", "")
        self.api_timeout_seconds: float = _env_float("API_TIMEOUT_SECONDS", 120.0)

        # --- search providers --------------------------------------------------
        self.search_provider: str = _env("SEARCH_PROVIDER", "auto")  # tavily|searxng|auto
        self.searxng_url: str = _env("SEARXNG_URL", "http://localhost:8888")
        self.tavily_api_key: str = _env("TAVILY_API_KEY", "")

        # --- research agent ----------------------------------------------------
        self.research_max_subqueries: int = _env_int("RESEARCH_MAX_SUBQUERIES", 3)
        self.research_max_results_per_query: int = _env_int("RESEARCH_MAX_RESULTS", 6)
        self.research_max_page_chars: int = _env_int("RESEARCH_MAX_PAGE_CHARS", 6000)
        self.research_max_context_chars: int = _env_int("RESEARCH_MAX_CONTEXT_CHARS", 24000)

        # --- verification layer -------------------------------------------------
        self.verify_source_http: bool = _env_bool("VERIFY_SOURCE_HTTP", True)
        self.source_check_timeout: float = _env_float("VERIFY_SOURCE_TIMEOUT", 12.0)
        self.quote_match_threshold: float = _env_float("VERIFY_QUOTE_THRESHOLD", 0.62)

        # --- legal update monitoring ---------------------------------------------
        self.updates_enabled: bool = _env_bool("UPDATES_ENABLED", True)
        self.updates_hour_utc: int = _env_int("UPDATES_HOUR_UTC", 6)
        self.updates_lookback_days: int = _env_int("UPDATES_LOOKBACK_DAYS", 7)
        self.updates_max_items: int = _env_int("UPDATES_MAX_ITEMS", 120)

        # --- tools ------------------------------------------------------------------
        self.tools_mode: str = _env("TOOLS_MODE", "simulate")  # simulate|live
        self.google_client_id: str = _env("GOOGLE_CLIENT_ID", "")
        self.google_client_secret: str = _env("GOOGLE_CLIENT_SECRET", "")
        self.microsoft_client_id: str = _env("MICROSOFT_CLIENT_ID", "")
        self.microsoft_client_secret: str = _env("MICROSOFT_CLIENT_SECRET", "")
        self.tools_redirect_uri: str = _env(
            "TOOLS_REDIRECT_URI", "http://127.0.0.1:8000/api/tools/oauth/callback"
        )

        # --- observability -------------------------------------------------------------
        self.sentry_dsn: str = _env("SENTRY_DSN", "")  # empty => disabled (self-hosted ok)
        self.metrics_enabled: bool = _env_bool("COUNSEL_METRICS_ENABLED", True)

        # --- caching ----------------------------------------------------------------------
        self.cache_embeddings: bool = _env_bool("CACHE_EMBEDDINGS", True)
        self.cache_research_ttl_hours: int = _env_int("CACHE_RESEARCH_TTL_HOURS", 24)

    # ------------------------------------------------------------------ helpers

    @property
    def jwt_secret_resolved(self) -> str:
        """JWT signing secret, generating + persisting one on first use."""
        if self.jwt_secret:
            return self.jwt_secret
        if self.keys_path.exists():
            self.jwt_secret = self.keys_path.read_text().strip()
            if self.jwt_secret:
                return self.jwt_secret
        self.jwt_secret = secrets.token_urlsafe(48)
        try:
            self.keys_path.write_text(self.jwt_secret)
            self.keys_path.chmod(0o600)
        except OSError:  # pragma: no cover
            pass
        return self.jwt_secret

    def llm_mode_available(self, mode: str) -> bool:
        if mode == "local":
            return bool(self.model_path) and Path(self.model_path).exists()
        if mode == "api":
            return bool(self.api_base_url)
        return True


settings = Settings()
