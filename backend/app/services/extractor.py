"""Regex-based extraction of URLs, emails, and phone numbers from a message."""

import re

import tldextract

from app.schemas.analysis import ExtractedEntities

# Offline extractor: uses tldextract's bundled public-suffix snapshot, never hits the network.
_tld = tldextract.TLDExtract(suffix_list_urls=())

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

# Explicit URLs (scheme or www.) plus bare domains like "gcash-verify.top/login",
# which scammers use to dodge link previews. Bare matches are validated against the PSL below.
URL_RE = re.compile(
    r"(?:https?://|www\.)[^\s<>\"']+"
    r"|\b(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,24}(?::\d{2,5})?(?:/[^\s<>\"']*)?",
    re.IGNORECASE,
)
TRAILING_PUNCT = ".,;:!?)]}'\""

# PH mobile: 09XXXXXXXXX, +639XXXXXXXXX, 639XXXXXXXXX, with optional spaces/dashes.
PH_MOBILE_RE = re.compile(r"(?<![\d+])(?:\+?63|0)[\s-]?9\d{2}[\s-]?\d{3}[\s-]?\d{4}(?!\d)")
# Other international numbers written with a leading "+".
INTL_PHONE_RE = re.compile(r"(?<![\d+])\+\d{1,3}[\s-]?\d(?:[\s-]?\d){6,12}(?!\d)")


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def registered_domain(url: str) -> str:
    """Return the registrable domain (e.g. 'bdo.com.ph') or the IP for a URL, '' if none."""
    result = _tld(url)
    return result.top_domain_under_public_suffix or result.ipv4 or result.ipv6


def _normalize_ph_mobile(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    return "+63" + digits[-10:]


def extract_urls(text: str) -> list[str]:
    urls = []
    for match in URL_RE.finditer(text):
        url = match.group(0).rstrip(TRAILING_PUNCT)
        explicit = url.lower().startswith(("http://", "https://", "www."))
        # Bare-domain candidates must end in a real public suffix ("hello.txt" is not a URL).
        if not explicit and not _tld(url).suffix:
            continue
        if registered_domain(url):
            urls.append(url)
    return _dedupe(urls)


def extract_phone_numbers(text: str) -> list[str]:
    phones = [_normalize_ph_mobile(m.group(0)) for m in PH_MOBILE_RE.finditer(text)]
    remaining = PH_MOBILE_RE.sub(" ", text)
    phones += [re.sub(r"[\s-]", "", m.group(0)) for m in INTL_PHONE_RE.finditer(remaining)]
    return _dedupe(phones)


def extract_entities(text: str) -> ExtractedEntities:
    emails = _dedupe(EMAIL_RE.findall(text))
    # Blank out emails so their domains aren't re-detected as bare URLs.
    text_without_emails = EMAIL_RE.sub(" ", text)
    urls = extract_urls(text_without_emails)
    domains = _dedupe([d for d in (registered_domain(u) for u in urls) if d])
    return ExtractedEntities(
        urls=urls,
        domains=domains,
        emails=emails,
        phone_numbers=extract_phone_numbers(text),
    )
