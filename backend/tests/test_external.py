import asyncio
import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.config import settings
from app.services.domain_info import check_domains_age
from app.services.link_checker import check_urls_safe_browsing


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)


def _run(coro):
    return asyncio.run(coro)


# --- Safe Browsing ------------------------------------------------------------


@pytest.fixture
def sb_key(monkeypatch):
    monkeypatch.setattr(settings, "safe_browsing_api_key", "test-key")


def test_safe_browsing_no_urls_is_noop():
    assert _run(check_urls_safe_browsing([])) == ([], None)


def test_safe_browsing_missing_key_is_skipped():
    threats, note = _run(check_urls_safe_browsing(["evil.top"]))
    assert threats == [] and note == "Google Safe Browsing (API key not configured)"


def test_safe_browsing_reports_matches(sb_key):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["key"] = request.url.params["key"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"matches": [
            {"threatType": "SOCIAL_ENGINEERING", "threat": {"url": "http://evil.top/login"}},
        ]})

    threats, note = _run(check_urls_safe_browsing(["evil.top/login", "https://ok.com"], client=_client(handler)))
    assert note is None
    # Reported with the URL as the user saw it (no scheme added).
    assert threats == ["evil.top/login flagged as SOCIAL_ENGINEERING by Google Safe Browsing"]
    assert seen["key"] == "test-key"
    info = seen["body"]["threatInfo"]
    assert set(info["threatTypes"]) == {"MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE",
                                        "POTENTIALLY_HARMFUL_APPLICATION"}
    assert info["threatEntries"] == [{"url": "http://evil.top/login"}, {"url": "https://ok.com"}]


def test_safe_browsing_clean_response(sb_key):
    threats, note = _run(check_urls_safe_browsing(["https://ok.com"], client=_client(lambda r: httpx.Response(200, json={}))))
    assert threats == [] and note is None


def test_safe_browsing_http_error_is_skipped(sb_key):
    threats, note = _run(check_urls_safe_browsing(["https://ok.com"], client=_client(lambda r: httpx.Response(403))))
    assert threats == [] and note == "Google Safe Browsing (request failed: HTTP 403)"


def test_safe_browsing_timeout_is_skipped(sb_key):
    def handler(request):
        raise httpx.ConnectTimeout("timed out", request=request)

    threats, note = _run(check_urls_safe_browsing(["https://ok.com"], client=_client(handler)))
    assert threats == [] and note == "Google Safe Browsing (request failed or timed out)"


# --- RDAP domain age ----------------------------------------------------------


def _rdap(days_old: int) -> dict:
    registered = datetime.now(timezone.utc) - timedelta(days=days_old)
    return {"events": [
        {"eventAction": "last changed", "eventDate": "2026-01-01T00:00:00Z"},
        {"eventAction": "registration", "eventDate": registered.strftime("%Y-%m-%dT%H:%M:%SZ")},
    ]}


def test_domain_age_flags_new_domains():
    ages = {"gcash-verify.top": 3, "oldshop.com": 4000}

    def handler(request: httpx.Request) -> httpx.Response:
        domain = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(200, json=_rdap(ages[domain]))

    youngest, flags, notes = _run(check_domains_age(
        ["https://login.gcash-verify.top/x", "oldshop.com/sale"], client=_client(handler)))
    assert youngest == 3
    assert flags == ["Domain 'gcash-verify.top' was registered only 3 days ago "
                     "(newly registered domains are heavily used in phishing)"]
    assert notes == []


def test_domain_age_follows_rdap_redirect():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "rdap.org":
            return httpx.Response(302, headers={"Location": "https://rdap.registry.example/domain/example-shop.com"})
        return httpx.Response(200, json=_rdap(10))

    assert _run(check_domains_age(["example-shop.com"], client=_client(handler)))[0] == 10


def test_domain_age_skips_known_platforms_and_ips():
    def handler(request):  # pragma: no cover - must not be called
        raise AssertionError(f"unexpected lookup {request.url}")

    result = _run(check_domains_age(
        ["https://www.gcash.com", "bdo.com.ph", "google.com/maps", "bit.ly/x", "http://1.2.3.4/a", "sss.gov.ph"],
        client=_client(handler)))
    assert result == (None, [], [])


def test_domain_age_404_and_timeout_are_skipped_cleanly():
    def handler(request: httpx.Request) -> httpx.Response:
        if "shop.ph" in request.url.path:
            return httpx.Response(404)
        raise httpx.ReadTimeout("slow", request=request)

    youngest, flags, notes = _run(check_domains_age(["myshop.ph", "slow.xyz"], client=_client(handler)))
    assert youngest is None and flags == []
    assert notes[0].startswith("Domain age for 'myshop.ph' (no RDAP record")
    assert notes[1] == "Domain age for 'slow.xyz' (RDAP lookup timed out)"


def test_domain_age_missing_registration_event():
    youngest, _, notes = _run(check_domains_age(
        ["example-shop.com"], client=_client(lambda r: httpx.Response(200, json={"events": []}))))
    assert youngest is None and "no registration date" in notes[0]
