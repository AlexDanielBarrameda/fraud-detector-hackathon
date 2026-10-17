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
    # A hanging model gets this long before we fail over; the whole chain is capped by llm_timeout_seconds.
    per_model_timeout_seconds: float = 8.0
    llm_timeout_seconds: float = 20.0

    safe_browsing_api_key: str = ""
    external_check_timeout_seconds: float = 4.0


settings = Settings()


def is_configured(key: str) -> bool:
    """False for empty keys and the `your_..._here` placeholders from .env.example."""
    return bool(key) and not key.startswith("your_")
