"""Request hardening: rate limiting, body-size cap, and security headers. Standard library only."""

import math
import time
from collections import OrderedDict, deque
from threading import Lock

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

MAX_TRACKED_CLIENTS = 10_000  # memory bound: oldest clients are forgotten first


class SlidingWindowLimiter:
    """Per-client + global sliding-window limiter, in memory (one server process)."""

    def __init__(self) -> None:
        self._clients: OrderedDict[str, deque[float]] = OrderedDict()
        self._global: deque[float] = deque()
        self._lock = Lock()

    def reset(self) -> None:
        with self._lock:
            self._clients.clear()
            self._global.clear()

    @staticmethod
    def _prune(hits: deque[float], cutoff: float) -> None:
        while hits and hits[0] <= cutoff:
            hits.popleft()

    def check(self, client: str, now: float | None = None) -> float | None:
        """Record a hit and return None if allowed, or the seconds to wait if limited (hit not recorded)."""
        window = settings.rate_limit_window_seconds
        per_client, global_cap = settings.rate_limit_per_client, settings.rate_limit_global
        now = time.monotonic() if now is None else now
        cutoff = now - window
        with self._lock:
            hits = self._clients.get(client)
            if hits is None:
                hits = self._clients[client] = deque()
                if len(self._clients) > MAX_TRACKED_CLIENTS:
                    self._clients.popitem(last=False)
            self._clients.move_to_end(client)
            self._prune(hits, cutoff)
            self._prune(self._global, cutoff)

            waits = []
            if per_client and len(hits) >= per_client:
                waits.append(hits[0] + window - now)
            if global_cap and len(self._global) >= global_cap:
                waits.append(self._global[0] + window - now)
            if waits:
                return max(waits)
            hits.append(now)
            self._global.append(now)
            return None


limiter = SlidingWindowLimiter()


def client_ip(request: Request) -> str:
    """Client address. Behind Render's proxy the real client is the first X-Forwarded-For entry.

    That header can be prefixed by the client, so a determined caller can rotate fake IPs to dodge the
    per-client limit; the global cap still bounds total quota use in that case.
    """
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "")
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"


def rate_limited_response(retry_after: float) -> JSONResponse:
    seconds = max(1, math.ceil(retry_after))
    return JSONResponse(
        status_code=429,
        content={"detail": f"Too many new scans right now. Please wait {seconds} seconds and try again."},
        headers={"Retry-After": str(seconds)},
    )


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Refuse oversized bodies before they are read and parsed."""

    async def dispatch(self, request: Request, call_next):
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > settings.max_body_bytes:
            return JSONResponse(status_code=413, content={"detail": "Request body too large."})
        return await call_next(request)


SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        # HSTS only on HTTPS (Render terminates TLS and reports it via X-Forwarded-Proto); local http is untouched.
        if request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response
