import pytest

from app.api import analyze as analyze_api
from app.config import settings


@pytest.fixture(autouse=True)
def no_real_api_calls(monkeypatch):
    """Tests must never hit Gemini, Safe Browsing, or RDAP; individual tests opt back in with mocks."""
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "safe_browsing_api_key", "")

    async def no_rdap(urls):
        return None, [], []

    # RDAP needs no key, so stub it at the endpoint level. test_external.py exercises the real function.
    monkeypatch.setattr(analyze_api, "check_domains_age", no_rdap)
    analyze_api.clear_cache()
    yield
    analyze_api.clear_cache()
