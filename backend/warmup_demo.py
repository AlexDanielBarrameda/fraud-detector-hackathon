"""Pre-demo cache warmer.

Sends the 5 UI preset messages to the running backend so their AI analyses sit in the
in-memory cache before judges arrive: preset clicks then return instantly and cost 0 Gemini
requests, leaving the full free-tier quota for messages judges type themselves.

Run AFTER the final backend start (the cache lives in server memory; a restart empties it):

    python warmup_demo.py                                    # local backend (http://127.0.0.1:8000)
    python warmup_demo.py https://your-backend.onrender.com  # deployed backend
    WARMUP_BASE_URL=https://your-backend.onrender.com python warmup_demo.py
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx

PRESETS_PATH = Path(__file__).resolve().parent.parent / "frontend" / "src" / "data" / "presets.json"
DEFAULT_DELAY_SECONDS = 13.0  # 5 requests/minute free tier -> one every 12s, plus margin


# A sleeping Render free instance takes roughly a minute to boot; keep retrying /health until then.
HEALTH_WAIT_SECONDS = 120


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    # 127.0.0.1, not "localhost": on Windows, localhost tries IPv6 first and stalls ~2s per new connection.
    default_url = os.environ.get("WARMUP_BASE_URL", "http://127.0.0.1:8000")
    parser.add_argument("url", nargs="?", help=f"backend base URL (default: {default_url})")
    parser.add_argument("--base-url", default=None, help="same as the positional URL")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY_SECONDS,
                        help="seconds to wait between Gemini-consuming requests (default: 13)")
    args = parser.parse_args()
    base_url = (args.url or args.base_url or default_url).rstrip("/")

    presets = json.loads(PRESETS_PATH.read_text(encoding="utf-8"))
    with httpx.Client(base_url=base_url, timeout=60) as client:
        if not wait_for_health(client, base_url):
            print(f"Backend not reachable at {base_url}. Start it first (see README).")
            return 1

        failed = []
        for i, preset in enumerate(presets, 1):
            started = time.monotonic()
            data = client.post("/api/analyze", json={"text": preset["text"]}).json()
            elapsed = time.monotonic() - started

            if data.get("cached"):
                status = "already cached"
            elif data.get("llm_used"):
                status = f"warmed via {data.get('llm_model')}"
            else:
                status = "NOT cached (AI unavailable, got rules-only fallback)"
                failed.append(preset["label"])
            print(f"[{i}/{len(presets)}] {preset['label']:<26} {data['final_score']:>3} "
                  f"{data['risk_level']:<8} {elapsed:5.1f}s  {status}")

            # Only requests that actually hit Gemini count against the per-minute quota.
            if i < len(presets) and not data.get("cached"):
                time.sleep(args.delay)

    if failed:
        print(f"\n{len(failed)} preset(s) not cached: {', '.join(failed)}. Wait a minute and re-run; "
              "already-cached presets are skipped instantly.")
        return 1
    print("\nAll presets cached. Preset clicks are now instant and use 0 Gemini quota.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
