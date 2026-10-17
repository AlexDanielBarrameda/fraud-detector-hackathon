from fastapi.testclient import TestClient

from app.api import analyze as analyze_api
from app.config import settings
from app.main import app
from app.schemas.analysis import LLMAnalysis
from app.services import llm

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_analyze_scam_message_rules_only():
    payload = {
        "text": "GCash: Your account is suspended. Verify your account at https://gcash-verify.top and send your OTP."
    }
    response = client.post("/api/analyze", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["llm_used"] is False
    assert data["risk_level"] == "Critical"
    assert data["final_score"] >= 85
    assert data["extracted_entities"]["urls"] == ["https://gcash-verify.top"]
    assert data["external_checks"]["urls_found"] == ["https://gcash-verify.top"]
    assert any("GEMINI_API_KEY" in s for s in data["external_checks"]["skipped_checks"])
    assert {f["rule_id"] for f in data["rule_flags"]} >= {
        "otp_request",
        "urgency_threat",
    }
    assert data["red_flags"] and data["recommended_actions"] and data["explanation"]


def test_analyze_legit_message_is_low():
    payload = {
        "text": "Your BDO OTP is 482913. It expires in 5 minutes. Never share this code with anyone."
    }
    data = client.post("/api/analyze", json=payload).json()
    assert data["risk_level"] == "Low"
    assert data["final_score"] < 30


def test_analyze_rejects_empty_text():
    assert client.post("/api/analyze", json={"text": ""}).status_code == 422


def _fake_gemini(monkeypatch) -> list[str]:
    calls: list[str] = []

    async def fake_call_model(client, model, payload):
        calls.append(model)
        return LLMAnalysis(
            llm_score=80,
            risk_level="High",
            red_flags=["LLM flag"],
            explanation="e",
            recommended_actions=["a"],
        )

    monkeypatch.setattr(settings, "gemini_api_key", "fake-key")
    monkeypatch.setattr(llm, "_call_model", fake_call_model)
    return calls


def test_successful_llm_results_are_cached(monkeypatch):
    calls = _fake_gemini(monkeypatch)
    first = client.post(
        "/api/analyze", json={"text": "Hi Ma, bagong number ko to. Pa-load naman."}
    ).json()
    # Same text with surrounding whitespace hits the same cache entry.
    second = client.post(
        "/api/analyze", json={"text": "  Hi Ma, bagong number ko to. Pa-load naman.\n"}
    ).json()
    assert (
        first["llm_used"] is True
        and first["cached"] is False
        and first["llm_model"] == settings.gemini_model
    )
    assert second["cached"] is True
    assert {k: v for k, v in second.items() if k != "cached"} == {
        k: v for k, v in first.items() if k != "cached"
    }
    assert len(calls) == 1  # second request consumed 0 Gemini calls


def test_rules_only_fallbacks_are_not_cached():
    payload = {"text": "GCash: verify your account at gcash-ph.top"}
    client.post("/api/analyze", json=payload)
    assert client.post("/api/analyze", json=payload).json()["cached"] is False


def test_external_evidence_drives_score_and_red_flags(monkeypatch):
    async def fake_sb(urls):
        return [
            f"{urls[0]} flagged as SOCIAL_ENGINEERING by Google Safe Browsing"
        ], None

    async def fake_rdap(urls):
        return (
            2,
            [
                "Domain 'promo-deals.com' was registered only 2 days ago (newly registered domains are "
                "heavily used in phishing)"
            ],
            [],
        )

    monkeypatch.setattr(analyze_api, "check_urls_safe_browsing", fake_sb)
    monkeypatch.setattr(analyze_api, "check_domains_age", fake_rdap)
    data = client.post(
        "/api/analyze", json={"text": "See our deals at https://promo-deals.com"}
    ).json()

    ext = data["external_checks"]
    assert ext["youngest_domain_days"] == 2 and ext["safe_browsing_threats"]
    assert "new_domain" in {f["rule_id"] for f in data["rule_flags"]}
    assert (
        data["final_score"] >= 90 and data["risk_level"] == "Critical"
    )  # Safe Browsing floor
    # Verified evidence leads the red flags.
    assert data["red_flags"][:2] == ext["safe_browsing_threats"] + ext["domain_flags"]


def test_skipped_external_checks_are_reported(monkeypatch):
    async def rdap_404(urls):
        return None, [], ["Domain age for 'x.ph' (no RDAP record)"]

    monkeypatch.setattr(analyze_api, "check_domains_age", rdap_404)
    data = client.post("/api/analyze", json={"text": "Visit x.ph today"}).json()
    skipped = data["external_checks"]["skipped_checks"]
    assert "Google Safe Browsing (API key not configured)" in skipped
    assert "Domain age for 'x.ph' (no RDAP record)" in skipped
