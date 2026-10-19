import pytest

from app.api import analyze as analyze_api
from app.config import settings
from app.security import limiter


@pytest.fixture(autouse=True)
def no_real_api_calls(monkeypatch):
    """Tests must never hit Gemini, Groq, Ollama, Safe Browsing, or RDAP; individual tests opt back in with mocks."""
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "safe_browsing_api_key", "")
    monkeypatch.setattr(settings, "groq_api_key", None)
    monkeypatch.setattr(settings, "ollama_model", None)

    async def no_rdap(urls):
        return None, [], []

    # RDAP needs no key, so stub it at the endpoint level. test_external.py exercises the real function.
    monkeypatch.setattr(analyze_api, "check_domains_age", no_rdap)
    analyze_api.clear_cache()
    limiter.reset()
    yield
    analyze_api.clear_cache()
    limiter.reset()
