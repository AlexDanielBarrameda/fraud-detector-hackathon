import importlib

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.config import settings
from app.main import app
from app.security import SlidingWindowLimiter, limiter

client = TestClient(app)
ANALYZE = "/api/analyze"


# --- Limiter unit tests -------------------------------------------------------


@pytest.fixture
def small_limits(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_window_seconds", 60)
    monkeypatch.setattr(settings, "rate_limit_per_client", 2)
    monkeypatch.setattr(settings, "rate_limit_global", 3)


def test_per_client_limit_and_window_expiry(small_limits):
    lim = SlidingWindowLimiter()
    assert lim.check("a", now=0) is None
    assert lim.check("a", now=1) is None
    assert lim.check("a", now=2) == pytest.approx(58)  # oldest hit (t=0) expires at t=60
    assert lim.check("a", now=60.5) is None  # window slid past the first hit


def test_global_cap_bounds_spoofed_clients(small_limits):
    lim = SlidingWindowLimiter()
    assert [lim.check(ip, now=0) for ip in ("a", "b", "c")] == [None, None, None]
    assert lim.check("d", now=1) is not None  # a fresh "IP" is still refused once the global cap is hit


def test_limits_can_be_disabled(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_per_client", 0)
    monkeypatch.setattr(settings, "rate_limit_global", 0)
    lim = SlidingWindowLimiter()
    assert all(lim.check("a", now=i) is None for i in range(100))


# --- Rate limit through the API ---------------------------------------------------


def test_api_returns_429_with_retry_after(small_limits):
    for i in range(2):
        assert client.post(ANALYZE, json={"text": f"message {i}"}).status_code == 200
    r = client.post(ANALYZE, json={"text": "message 3"})
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) >= 1
    assert "wait" in r.json()["detail"]


def test_cached_results_are_not_rate_limited(small_limits, monkeypatch):
    # Seed the cache with an AI-backed result for one text, then exhaust the limit with others.
    from app.api import analyze as analyze_api
    from app.schemas.analysis import LLMAnalysis
    from app.services import llm

    async def fake_call_model(c, model, payload):
        return LLMAnalysis(llm_score=80, risk_level="High", red_flags=["x"], explanation="e", recommended_actions=["a"])

    monkeypatch.setattr(settings, "gemini_api_key", "fake-key")
    monkeypatch.setattr(llm, "_call_model", fake_call_model)
    assert client.post(ANALYZE, json={"text": "cached one"}).status_code == 200
    assert client.post(ANALYZE, json={"text": "other"}).status_code == 200
    assert client.post(ANALYZE, json={"text": "blocked"}).status_code == 429
    # The cached text still answers instantly, limit or not.
    r = client.post(ANALYZE, json={"text": "cached one"})
    assert r.status_code == 200 and r.json()["cached"] is True
    analyze_api.clear_cache()


def test_forwarded_for_only_trusted_when_enabled(small_limits, monkeypatch):
    spoof = {"X-Forwarded-For": "203.0.113.9"}
    # Untrusted: every request counts against the real peer, whatever the header says.
    for i in range(2):
        client.post(ANALYZE, json={"text": f"u{i}"}, headers={"X-Forwarded-For": f"198.51.100.{i}"})
    assert client.post(ANALYZE, json={"text": "u3"}, headers=spoof).status_code == 429
    # Trusted (behind Render): the forwarded client gets its own bucket.
    limiter.reset()
    monkeypatch.setattr(settings, "trust_proxy_headers", True)
    for i in range(2):
        assert client.post(ANALYZE, json={"text": f"t{i}"}, headers={"X-Forwarded-For": "198.51.100.1"}).status_code == 200
    assert client.post(ANALYZE, json={"text": "t3"}, headers={"X-Forwarded-For": "198.51.100.2"}).status_code == 200


# --- Input validation ----------------------------------------------------------------


@pytest.mark.parametrize("body", [{"text": ""}, {"text": "   \n\t "}, {"text": "x" * 5001}, {"text": 123}, {}, {"msg": "hi"}])
def test_invalid_input_is_rejected_without_leaking_internals(body):
    r = client.post(ANALYZE, json=body)
    assert r.status_code == 422
    assert "Traceback" not in r.text and "File \"" not in r.text


def test_oversized_body_is_refused_before_parsing(monkeypatch):
    monkeypatch.setattr(settings, "max_body_bytes", 1024)
    r = client.post(ANALYZE, content=b'{"text": "' + b"a" * 4096 + b'"}', headers={"Content-Type": "application/json"})
    assert r.status_code == 413


# --- Docs, CORS, headers --------------------------------------------------------------


def test_docs_hidden_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "enable_docs", False)
    prod_app = importlib.reload(main_module).app
    try:
        prod = TestClient(prod_app)
        for path in ("/docs", "/redoc", "/openapi.json"):
            assert prod.get(path).status_code == 404
        assert prod.get("/health").status_code == 200
    finally:
        monkeypatch.setattr(settings, "enable_docs", True)
        importlib.reload(main_module)


def _preflight(origin: str):
    return client.options(
        ANALYZE,
        headers={"Origin": origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"},
    )


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://127.0.0.1:5173", "https://fraud-detector-hackathon.vercel.app"])
def test_cors_allows_exact_origins(origin):
    r = _preflight(origin)
    assert r.status_code == 200 and r.headers["access-control-allow-origin"] == origin


@pytest.mark.parametrize("origin", [
    "https://evil.vercel.app",                                   # used to pass the old *.vercel.app wildcard
    "https://fraud-detector-hackathon.vercel.app.evil.com",      # suffix trick
    "https://fraud-detector-hackathon-git-x-attacker.vercel.app",
    "http://fraud-detector-hackathon.vercel.app",                # wrong scheme
    "null",
    "https://evil.example.com",
])
def test_cors_rejects_everything_else(origin):
    r = _preflight(origin)
    assert "access-control-allow-origin" not in r.headers


def test_security_headers_on_api_responses():
    r = client.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert "strict-transport-security" not in r.headers  # plain http locally


def test_hsts_sent_behind_https_proxy():
    r = client.get("/health", headers={"X-Forwarded-Proto": "https"})
    assert r.headers["strict-transport-security"].startswith("max-age=")
