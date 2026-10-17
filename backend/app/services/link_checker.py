"""Google Safe Browsing v4 Lookup API (threatMatches:find)."""

import logging

import httpx

from app.config import is_configured, settings

logger = logging.getLogger(__name__)

SAFE_BROWSING_URL = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
THREAT_TYPES = ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE", "POTENTIALLY_HARMFUL_APPLICATION"]
MAX_URLS = 50  # well under the API's per-request limit


def _with_scheme(url: str) -> str:
    return url if url.lower().startswith(("http://", "https://")) else f"http://{url}"


async def check_urls_safe_browsing(
    urls: list[str], client: httpx.AsyncClient | None = None
) -> tuple[list[str], str | None]:
    """Return (threat descriptions, skipped note). Never raises."""
    if not urls:
        return [], None
    if not is_configured(settings.safe_browsing_api_key):
        return [], "Google Safe Browsing (API key not configured)"

    # Safe Browsing needs a scheme; map the normalized form back to what the user actually saw.
    originals = {_with_scheme(u): u for u in urls[:MAX_URLS]}
    body = {
        "client": {"clientId": "scam-analyzer", "clientVersion": "0.1.0"},
        "threatInfo": {
            "threatTypes": THREAT_TYPES,
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": u} for u in originals],
        },
    }
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=settings.external_check_timeout_seconds)
    try:
        response = await client.post(SAFE_BROWSING_URL, params={"key": settings.safe_browsing_api_key}, json=body)
        response.raise_for_status()
        matches = response.json().get("matches", [])
    except httpx.HTTPStatusError as exc:
        # Don't log the exception itself: its message includes the request URL, which carries the API key.
        logger.warning("Safe Browsing returned HTTP %s", exc.response.status_code)
        return [], f"Google Safe Browsing (request failed: HTTP {exc.response.status_code})"
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Safe Browsing request failed: %s", type(exc).__name__)
        return [], "Google Safe Browsing (request failed or timed out)"
    finally:
        if owns_client:
            await client.aclose()

    threats = []
    for match in matches:
        url = match.get("threat", {}).get("url", "")
        threats.append(f"{originals.get(url, url)} flagged as {match.get('threatType', 'THREAT')} by Google Safe Browsing")
    return list(dict.fromkeys(threats)), None
