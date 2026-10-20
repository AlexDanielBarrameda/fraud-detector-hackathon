"""warmup_demo.warm_presets and keep_alive.run against a fake server (httpx.MockTransport, no network)."""

import json

import httpx

import keep_alive
import warmup_demo

PRESET_COUNT = len(warmup_demo.load_presets())


def _client(handler) -> httpx.Client:
    return httpx.Client(base_url="https://api.test", transport=httpx.MockTransport(handler))


def _verdict(cached: bool, llm_used: bool = True) -> dict:
    return {"final_score": 90, "risk_level": "Critical", "cached": cached, "llm_used": llm_used, "llm_model": "m (Groq)"}


def test_warm_presets_all_cached_spends_no_waits():
    sleeps = []
    with _client(lambda r: httpx.Response(200, json=_verdict(cached=True))) as c:
        ready, failed, warmed = warmup_demo.warm_presets(c, log=lambda s: None, sleep=sleeps.append)
    assert (ready, failed, warmed) == (PRESET_COUNT, [], 0)
    assert sleeps == []  # cache hits cost no quota, so no spacing needed


def test_warm_presets_survives_429_network_errors_and_rules_only():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        n = calls["n"]
        if n == 1:
            return httpx.Response(429, headers={"Retry-After": "30"})
        if n == 2:
            raise httpx.ConnectError("wifi dropped", request=request)
        if n == 3:
            return httpx.Response(200, json=_verdict(cached=False, llm_used=False))  # rules-only: not cached
        return httpx.Response(200, json=_verdict(cached=False))  # freshly warmed

    lines = []
    with _client(handler) as c:
        ready, failed, warmed = warmup_demo.warm_presets(c, log=lines.append, sleep=lambda s: None)
    assert len(failed) == 3 and ready == PRESET_COUNT - 3 and warmed == PRESET_COUNT - 3
    assert any("rate limited" in l for l in lines) and any("request failed" in l for l in lines)


def test_keep_alive_cycle_rewarms_after_restart(monkeypatch, capsys):
    """Server answers /health fast but lost its cache (e.g. redeploy): the cycle still re-warms."""
    posted = []

    def handler(request):
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        posted.append(json.loads(request.content)["text"])
        return httpx.Response(200, json=_verdict(cached=False))

    real_client = httpx.Client
    monkeypatch.setattr(keep_alive.httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    keep_alive.run("https://api.test", interval=780, delay=0, once=True)
    out = capsys.readouterr().out
    assert "OK - /health responded 200" in out
    assert f"{PRESET_COUNT}/{PRESET_COUNT} presets ready ({PRESET_COUNT} re-warmed)" in out
    assert len(posted) == PRESET_COUNT


def test_keep_alive_cycle_never_raises_when_server_is_down(monkeypatch, capsys):
    def handler(request):
        raise httpx.ConnectError("no route", request=request)

    real_client = httpx.Client
    monkeypatch.setattr(keep_alive.httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    keep_alive.run("https://api.test", interval=780, delay=0, once=True)
    assert "DOWN - /health unreachable (ConnectError)" in capsys.readouterr().out
