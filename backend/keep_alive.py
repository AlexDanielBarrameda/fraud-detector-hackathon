"""Keep the deployed backend awake and its demo cache warm.

Render's free tier sleeps after 15 minutes without traffic, and a restart empties the in-memory
cache. This loop pings /health every 13 minutes (a 2-minute buffer before the idle cutoff) and
makes sure the 5 demo presets are cached:

  * on the first cycle,
  * whenever the server was asleep or unreachable (cold start), and
  * on every other cycle too, because a restart (redeploy, crash recovery) can empty the cache
    without a slow ping. Cached presets answer instantly and cost no AI quota or rate-limit budget,
    so this check is free unless something actually needs re-warming.

    python keep_alive.py https://fraud-analyzer-api-bmjf.onrender.com
    python keep_alive.py --base-url https://fraud-analyzer-api-bmjf.onrender.com --interval 600
    WARMUP_BASE_URL=https://fraud-analyzer-api-bmjf.onrender.com python keep_alive.py

Stop with Ctrl+C. Network drops are logged and retried next cycle; the loop never crashes.
"""

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from warmup_demo import DEFAULT_DELAY_SECONDS, warm_presets  # noqa: E402

DEFAULT_INTERVAL_SECONDS = 780  # 13 minutes
PING_TIMEOUT_SECONDS = 90  # long enough to ride out a cold start
COLD_START_SECONDS = 10.0  # a /health slower than this means the server was asleep


def log(message: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


def human(seconds: float) -> str:
    return f"{seconds / 60:g}m" if seconds >= 60 else f"{seconds:g}s"


def ping(client: httpx.Client) -> tuple[bool, float, str]:
    """GET /health. Returns (ok, seconds, detail). Never raises."""
    started = time.monotonic()
    try:
        r = client.get("/health", timeout=PING_TIMEOUT_SECONDS)
        elapsed = time.monotonic() - started
        return r.status_code == 200, elapsed, f"/health responded {r.status_code} in {elapsed:.2f}s"
    except httpx.TimeoutException:
        return False, time.monotonic() - started, f"/health timed out after {PING_TIMEOUT_SECONDS}s"
    except httpx.HTTPError as exc:
        return False, time.monotonic() - started, f"/health unreachable ({type(exc).__name__})"


def check_cache(client: httpx.Client, delay: float, reason: str) -> None:
    """Ensure every preset is cached; print details only when something had to be (re)warmed or failed."""
    lines: list[str] = []
    try:
        ready, failed, warmed = warm_presets(client, delay, log=lines.append)
    except Exception as exc:  # noqa: BLE001 - e.g. presets file missing; never kill the loop
        log(f"WARN - cache check failed ({type(exc).__name__}: {exc})")
        return
    total = ready + len(failed)
    if warmed or failed:
        log(f"Cache check ({reason}):")
        for line in lines:
            print(f"           {line}", flush=True)
    if failed:
        log(f"WARN - {ready}/{total} presets cached; will retry next cycle.")
    else:
        log(f"Cache - {ready}/{total} presets ready" + (f" ({warmed} re-warmed)." if warmed else "."))


def run(base_url: str, interval: float, delay: float, once: bool) -> None:
    log(f"Keep-alive started for {base_url} (every {human(interval)}). Ctrl+C to stop.")
    first, was_down = True, False
    with httpx.Client(base_url=base_url, headers={"User-Agent": "FraudAnalyzer-KeepAlive/1.0"}) as client:
        while True:
            ok, elapsed, detail = ping(client)
            if ok:
                asleep = elapsed > COLD_START_SECONDS
                log(f"OK - {detail}." + (" Server was asleep, so its cache is empty." if asleep else ""))
                reason = "first run" if first else "cold start" if (asleep or was_down) else "routine"
                check_cache(client, delay, reason)
                first, was_down = False, False
            else:
                log(f"DOWN - {detail}. Retrying next cycle.")
                was_down = True
            if once:
                return
            log(f"Next ping in {human(interval)}.")
            time.sleep(interval)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    default_url = os.environ.get("WARMUP_BASE_URL", "http://127.0.0.1:8000")
    parser.add_argument("url", nargs="?", help=f"backend base URL (default: {default_url})")
    parser.add_argument("--base-url", default=None, help="same as the positional URL")
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL_SECONDS, help="seconds between pings (default: 780 = 13 min)")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY_SECONDS, help="seconds between AI-consuming warmups (default: 13)")
    parser.add_argument("--once", action="store_true", help="run a single cycle and exit (for testing)")
    args = parser.parse_args()
    base_url = (args.url or args.base_url or default_url).rstrip("/")
    try:
        run(base_url, args.interval, args.delay, args.once)
    except KeyboardInterrupt:
        log("Keep-alive stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
