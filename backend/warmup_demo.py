"""Pre-demo cache warmer.

Sends the 5 UI preset messages to the running backend so their AI analyses sit in the
in-memory cache before judges arrive: preset clicks then return instantly and cost 0 AI
requests, leaving the full free-tier quota for messages judges type themselves.

Run AFTER the final backend start (the cache lives in server memory; a restart empties it):

    python warmup_demo.py                                    # local backend (http://127.0.0.1:8000)
    python warmup_demo.py https://your-backend.onrender.com  # deployed backend
    WARMUP_BASE_URL=https://your-backend.onrender.com python warmup_demo.py

Already-cached presets answer instantly and cost nothing, so re-running is always safe.
Exit codes: 0 all presets cached, 1 server up but some presets not cached yet, 2 server unreachable.
"""

import argparse
import json
import os
import sys
import time
from collections.abc import Callable
from pathlib import Path

import httpx

PRESETS_PATH = Path(__file__).resolve().parent.parent / "frontend" / "src" / "data" / "presets.json"
DEFAULT_DELAY_SECONDS = 13.0  # 5 requests/minute free tier -> one every 12s, plus margin

# A sleeping Render free instance takes roughly a minute to boot; keep retrying /health until then.
HEALTH_WAIT_SECONDS = 120


def load_presets() -> list[dict]:
    return json.loads(PRESETS_PATH.read_text(encoding="utf-8"))


def wait_for_health(client: httpx.Client, base_url: str) -> bool:
    deadline = time.monotonic() + HEALTH_WAIT_SECONDS
    announced = False
    while True:
        try:
            client.get("/health", timeout=15).raise_for_status()
            return True
        except httpx.HTTPError:
            if time.monotonic() >= deadline or base_url.startswith(("http://127.0.0.1", "http://localhost")):
                return False
            if not announced:
                print(f"Waiting for {base_url} to wake up (free instances sleep when idle)...")
                announced = True
            time.sleep(5)


def warm_presets(
    client: httpx.Client,
    delay: float = DEFAULT_DELAY_SECONDS,
    log: Callable[[str], None] = print,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[int, list[str], int]:
    """POST every preset once. Returns (ready, not_ready_labels, newly_warmed). Never raises.

    "ready" = served from cache or freshly AI-analyzed (now cached). Network errors, rate limits and
    rules-only fallbacks are reported as not ready, so a caller can simply retry later.
    """
    presets = load_presets()
    ready, warmed, failed = 0, 0, []
    for i, preset in enumerate(presets, 1):
        label = preset["label"]
        started = time.monotonic()
        spent_quota = False
        try:
            r = client.post("/api/analyze", json={"text": preset["text"]}, timeout=90)
        except httpx.HTTPError as exc:
            failed.append(label)
            log(f"[{i}/{len(presets)}] {label:<26} request failed ({type(exc).__name__})")
            continue
        elapsed = time.monotonic() - started

        if r.status_code == 429:
            failed.append(label)
            log(f"[{i}/{len(presets)}] {label:<26} rate limited (retry in {r.headers.get('retry-after', '?')}s)")
            continue
        if r.status_code != 200:
            failed.append(label)
            log(f"[{i}/{len(presets)}] {label:<26} HTTP {r.status_code}")
            continue

        data = r.json()
        if data.get("cached"):
            ready += 1
            status = "already cached"
        elif data.get("llm_used"):
            ready += 1
            warmed += 1
            spent_quota = True
            status = f"warmed via {data.get('llm_model')}"
        else:
            failed.append(label)
            spent_quota = True
            status = "NOT cached (AI unavailable, got rules-only fallback)"
        log(f"[{i}/{len(presets)}] {label:<26} {data['final_score']:>3} {data['risk_level']:<8} {elapsed:5.1f}s  {status}")

        # Only requests that actually reached an AI provider count against its per-minute quota.
        if i < len(presets) and spent_quota:
            sleep(delay)
    return ready, failed, warmed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    # 127.0.0.1, not "localhost": on Windows, localhost tries IPv6 first and stalls ~2s per new connection.
    default_url = os.environ.get("WARMUP_BASE_URL", "http://127.0.0.1:8000")
    parser.add_argument("url", nargs="?", help=f"backend base URL (default: {default_url})")
    parser.add_argument("--base-url", default=None, help="same as the positional URL")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY_SECONDS,
                        help="seconds to wait between AI-consuming requests (default: 13)")
    args = parser.parse_args()
    base_url = (args.url or args.base_url or default_url).rstrip("/")

    with httpx.Client(base_url=base_url, timeout=60) as client:
        if not wait_for_health(client, base_url):
            print(f"Backend not reachable at {base_url}. Start it first (see README).")
            return 2
        ready, failed, _ = warm_presets(client, args.delay)

    if failed:
        print(f"\n{len(failed)} preset(s) not cached: {', '.join(failed)}. Wait a minute and re-run; "
              "already-cached presets are skipped instantly.")
        return 1
    print(f"\nAll {ready} presets cached. Preset clicks are now instant and use 0 AI quota.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
