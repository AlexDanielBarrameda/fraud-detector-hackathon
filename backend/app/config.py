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

    # CORS. Local dev origins are always allowed (see main.py). Extra exact origins as a comma-separated
    # list, e.g. CORS_ORIGINS=https://fraud-analyzer.vercel.app. The regex covers Vercel production and
    # preview URLs; tighten it to your project (e.g. https://fraud-analyzer.*\.vercel\.app) once deployed.
    cors_origins: str = ""
    cors_origin_regex: str = r"https://.*\.vercel\.app"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()


def is_configured(key: str) -> bool:
    """False for empty keys and the `your_..._here` placeholders from .env.example."""
    return bool(key) and not key.startswith("your_")
