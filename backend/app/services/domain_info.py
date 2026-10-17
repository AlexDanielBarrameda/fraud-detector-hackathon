"""Domain age lookup via RDAP (https://rdap.org bootstrap redirector)."""

import asyncio
import logging
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.services.extractor import registered_domain
from app.services.rules import OFFICIAL_DOMAINS, URL_SHORTENERS, is_ip

logger = logging.getLogger(__name__)

RDAP_URL = "https://rdap.org/domain/{domain}"
NEW_DOMAIN_DAYS = 30
MAX_DOMAINS = 5

# Long-established platforms: no need to spend a lookup (or show a skip note) on them.
# Shorteners are skipped too: their age says nothing about where the link really goes.
KNOWN_PLATFORMS = OFFICIAL_DOMAINS | URL_SHORTENERS | {
    "google.com", "facebook.com", "fb.com", "messenger.com", "youtube.com", "instagram.com", "tiktok.com",
    "x.com", "twitter.com", "whatsapp.com", "telegram.org", "t.me", "wa.me", "viber.com", "microsoft.com",
    "apple.com", "amazon.com", "github.com",
}
# Government suffixes only registrable by the government itself.
KNOWN_SUFFIXES = (".gov.ph", ".gov")


def _needs_lookup(domain: str) -> bool:
    d = domain.lower()
    return bool(d) and not is_ip(d) and d not in KNOWN_PLATFORMS and not d.endswith(KNOWN_SUFFIXES)


class _LookupSkipped(Exception):
    def __init__(self, note: str):
        super().__init__(note)
        self.note = note


def _registration_date(rdap: dict) -> datetime | None:
    for event in rdap.get("events", []):
        if event.get("eventAction") == "registration" and event.get("eventDate"):
            date = datetime.fromisoformat(event["eventDate"].replace("Z", "+00:00"))
            return date if date.tzinfo else date.replace(tzinfo=timezone.utc)
    return None


async def _domain_age_days(client: httpx.AsyncClient, domain: str) -> int:
    try:
        response = await client.get(RDAP_URL.format(domain=domain), headers={"Accept": "application/rdap+json"})
    except httpx.TimeoutException:
        raise _LookupSkipped(f"Domain age for '{domain}' (RDAP lookup timed out)")
    except httpx.HTTPError as exc:
        logger.warning("RDAP lookup for %s failed: %s", domain, type(exc).__name__)
        raise _LookupSkipped(f"Domain age for '{domain}' (RDAP lookup failed)")

    if response.status_code == 404:
        raise _LookupSkipped(
            f"Domain age for '{domain}' (no RDAP record: domain may be unregistered, or its registry, e.g. .ph, has no RDAP service)"
        )
    if response.status_code != 200:
        raise _LookupSkipped(f"Domain age for '{domain}' (RDAP returned HTTP {response.status_code})")
    try:
        registered = _registration_date(response.json())
    except ValueError:
        raise _LookupSkipped(f"Domain age for '{domain}' (unreadable RDAP response)")
    if registered is None:
        raise _LookupSkipped(f"Domain age for '{domain}' (no registration date in RDAP record)")
    return max(0, (datetime.now(timezone.utc) - registered).days)


async def check_domains_age(
    urls: list[str], client: httpx.AsyncClient | None = None
) -> tuple[int | None, list[str], list[str]]:
    """Return (youngest_domain_days, domain_flags, skipped_notes). Never raises."""
    domains = list(dict.fromkeys(registered_domain(u) for u in urls))
    domains = [d for d in domains if _needs_lookup(d)][:MAX_DOMAINS]
    if not domains:
        return None, [], []

    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=settings.external_check_timeout_seconds, follow_redirects=True)
    try:
        results = await asyncio.gather(*(_domain_age_days(client, d) for d in domains), return_exceptions=True)
    finally:
        if owns_client:
            await client.aclose()

    ages: dict[str, int] = {}
    notes: list[str] = []
    for domain, result in zip(domains, results):
        if isinstance(result, _LookupSkipped):
            notes.append(result.note)
        elif isinstance(result, BaseException):
            logger.warning("RDAP lookup for %s crashed: %s", domain, type(result).__name__)
            notes.append(f"Domain age for '{domain}' (RDAP lookup failed)")
        else:
            ages[domain] = result

    flags = [
        f"Domain '{d}' was registered only {days} days ago (newly registered domains are heavily used in phishing)"
        for d, days in ages.items()
        if days < NEW_DOMAIN_DAYS
    ]
    return (min(ages.values()) if ages else None), flags, notes
