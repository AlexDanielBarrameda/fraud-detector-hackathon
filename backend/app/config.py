from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/.env, resolved relative to this file so it works from any cwd
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    """Runtime configuration. Missing keys default to "" so the app never crashes when unconfigured."""

    model_config = SettingsConfigDict(env_file=ENV_PATH, env_file_encoding="utf-8", extra="ignore")

    gemini_api_key: str = ""
    # 3.5-flash leads: 3.8-flash is frequently congested (503) and slow to fail.
    gemini_model: str = "gemini-3.5-flash"
    # Tried in order when the primary model is rate-limited, overloaded, slow, or unavailable.
    # Free-tier quotas are per model, so each fallback has its own RPM bucket.
    # Override in .env as JSON, e.g. GEMINI_FALLBACK_MODELS=["gemini-3.8-flash"]
    gemini_fallback_models: list[str] = ["gemini-3.8-flash", "gemini-3.1-flash-lite"]
    # A hanging Gemini model gets this long before we fail over to the next one; the whole Gemini tier
    # gets gemini_tier_timeout_seconds before we move on to Groq, so an outage fails over fast.
    per_model_timeout_seconds: float = 6.0
    gemini_tier_timeout_seconds: float = 12.0

    # Tier 2: Groq (OpenAI-compatible JSON mode). Optional; skipped when no key is set.
    groq_api_key: str | None = None
    # Chat models this key can use on Groq (checked via GET /openai/v1/models). Llama 3.x / qwen3-32b are retired.
    groq_models: list[str] = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]
    groq_timeout_seconds: float = 6.0

    # Tier 3: local Ollama (localhost demos). Optional; skipped unless OLLAMA_MODEL is set, e.g. "qwen2.5:7b".
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str | None = None
    ollama_timeout_seconds: float = 8.0

    # Cap for the whole AI step across all tiers; past this we answer rules-only.
    llm_timeout_seconds: float = 30.0

    safe_browsing_api_key: str = ""
    external_check_timeout_seconds: float = 4.0

    # CORS: exact origins only. Local dev origins are always allowed (see main.py); the deployed frontend is
    # added here, comma-separated. No wildcard by default: "*.vercel.app" would let ANY site hosted on Vercel
    # call this API from a browser. CORS_ORIGIN_REGEX stays available as an explicit opt-in.
    cors_origins: str = "https://fraud-detector-hackathon.vercel.app"
    cors_origin_regex: str = ""

    # Interactive API docs (/docs, /redoc, /openapi.json). Handy locally; set ENABLE_DOCS=false in production.
    enable_docs: bool = True

    # Rate limit on NEW analyses (cache hits are free and never counted), per sliding window.
    # Per-client limit, plus a global cap that still bounds quota burn if a client spoofs its IP.
    # 0 disables a limit.
    rate_limit_window_seconds: int = 60
    rate_limit_per_client: int = 12
    rate_limit_global: int = 40
    # Behind a reverse proxy (Render), the client IP is in X-Forwarded-For; only trust it when deployed there.
    trust_proxy_headers: bool = False

    # Reject request bodies larger than this before parsing (the text itself is capped at 5,000 chars).
    max_body_bytes: int = 65_536

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()


def is_configured(key: str) -> bool:
    """False for empty keys and the `your_..._here` placeholders from .env.example."""
    return bool(key) and not key.startswith("your_")
