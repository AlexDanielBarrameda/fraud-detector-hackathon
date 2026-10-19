"""AI analysis with a cross-provider fallback chain and a deterministic rules-only parachute.

Tier 1: Gemini (structured output via response_schema), several models.
Tier 2: Groq (OpenAI-compatible JSON mode over httpx), several models. Optional.
Tier 3: local Ollama (JSON format over httpx). Optional, for localhost demos.
Tier 4: rules-only fallback_analysis().

Every tier gets the same system prompt and the same payload: the scanned message only ever travels
inside the JSON data payload, never in the instructions. Every answer is validated against LLMAnalysis.
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import httpx
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from google.genai.client import AsyncClient
from pydantic import ValidationError

from app.config import is_configured, settings
from app.schemas.analysis import (
    ExternalCheckResult,
    ExtractedEntities,
    LLMAnalysis,
    RuleResult,
)
from app.services.scorer import risk_level_for

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "analyze_prompt.txt"
SYSTEM_PROMPT = PROMPT_PATH.read_text(encoding="utf-8")

# Gemini enforces the schema natively; the OpenAI-style providers get it spelled out in the prompt.
JSON_SYSTEM_PROMPT = SYSTEM_PROMPT + (
    "\nRespond with ONLY one JSON object (no prose, no markdown fences) with exactly these keys:\n"
    '{"llm_score": <integer 0-100>, "risk_level": "Low" | "Medium" | "High" | "Critical", '
    '"red_flags": [<string>, ...], "explanation": <string>, "recommended_actions": [<string>, ...]}\n'
)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Tests inject an httpx.MockTransport here; None means the real network.
HTTP_TRANSPORT: httpx.AsyncBaseTransport | None = None

# Errors that mean "this model can't serve us right now" -> try the next model in the chain.
# 404: model retired/unavailable for this key; 429: per-model quota; 5xx: overloaded after SDK retries.
NEXT_MODEL_CODES = {404, 429, 500, 503}


@dataclass
class LLMOutcome:
    analysis: LLMAnalysis
    llm_used: bool
    skipped_note: str | None = None
    model: str | None = None


def model_chain() -> list[str]:
    return list(
        dict.fromkeys([settings.gemini_model, *settings.gemini_fallback_models])
    )


def _thinking_config(model: str) -> types.ThinkingConfig:
    # Scoring doesn't benefit much from extended thinking; keep demo latency low.
    # Gemini 2.x takes a token budget; 3.x+ rejects thinking_budget and uses thinking_level.
    if model.startswith("gemini-2"):
        return types.ThinkingConfig(thinking_budget=0)
    return types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW)


# --- Deterministic fallback ---------------------------------------------------

ACTIONS_BY_RULE: dict[str, str] = {
    "prompt_injection": "Treat this message as hostile: it contains text designed to trick automated scam filters.",
    "family_emergency": "Call the person on their old, known number (or another relative) before sending any money or load.",
    "otp_request": "Never share your OTP, MPIN, PIN, or password with anyone, not even someone claiming to be from your bank or e-wallet.",
    "brand_impersonation_link": "Open the official app or type the official website yourself instead of using the link in the message.",
    "lookalike_domain": "Do not click the link; its domain imitates a real brand.",
    "suspicious_tld": "Do not click the link; it uses a domain ending commonly abused by scammers.",
    "new_domain": "Treat the link as unsafe; the website was registered only recently.",
    "url_shortener": "Do not open shortened links from unknown senders; they hide the real destination.",
    "ip_address_url": "Do not open links that point to a raw IP address.",
    "prize_lure": "Ignore unexpected prize or raffle claims; legitimate promos never ask for fees or OTPs to release prizes.",
    "task_job_scam": "Do not join Telegram/WhatsApp 'task' jobs; they end with requests to deposit money.",
    "upfront_fee_crypto": "Do not send any fee, crypto, or gift card payment to claim money or a job.",
    "account_verification": "Verify your account status only through the official app or hotline.",
    "personal_info_request": "Do not send IDs, selfies, birthdays, or card/account numbers to unverified senders.",
}
REPORT_ACTION = "Report the sender to the CICC hotline 1326 or your mobile network, then block the number."


def fallback_analysis(rule_result: RuleResult) -> LLMAnalysis:
    """Rule-derived stand-in for the LLM output, so the API always returns a full result."""
    score = rule_result.rule_score
    level = risk_level_for(score)
    flags = [f.description for f in rule_result.flags]

    actions = [
        ACTIONS_BY_RULE[f.rule_id]
        for f in rule_result.flags
        if f.rule_id in ACTIONS_BY_RULE
    ][:4]
    if level == "Low":
        actions = actions or [
            "No strong scam indicators were found, but stay cautious with unexpected messages."
        ]
        actions.append(
            "If in doubt, contact the sender through an official channel you already know."
        )
        found = (
            f"only {len(flags)} weak scam indicator(s)"
            if flags
            else "no strong scam indicators"
        )
        explanation = (
            f"Our rule engine found {found} in this message. "
            "AI analysis was unavailable, so this verdict is based on heuristic rules only."
        )
    else:
        actions.append(REPORT_ACTION)
        explanation = (
            f"Our rule engine flagged {len(flags)} scam indicator(s), giving a {level.lower()} risk rating. "
            "AI analysis was unavailable, so this verdict is based on heuristic rules only."
        )

    return LLMAnalysis(
        llm_score=score,
        risk_level=level,
        red_flags=flags,
        explanation=explanation,
        recommended_actions=actions,
    )


# --- Gemini call ----------------------------------------------------------------


def _build_payload(
    text: str,
    entities: ExtractedEntities,
    rule_result: RuleResult,
    external: ExternalCheckResult,
) -> str:
    return json.dumps(
        {
            "message": text,
            "extracted_entities": entities.model_dump(),
            "rule_engine": rule_result.model_dump(),
            "external_checks": external.model_dump(),
        },
        ensure_ascii=False,
        indent=2,
    )


async def _call_model(client: AsyncClient, model: str, payload: str) -> LLMAnalysis:
    response = await client.models.generate_content(
        model=model,
        contents=payload,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=LLMAnalysis,
            temperature=0.2,
            thinking_config=_thinking_config(model),
        ),
    )
    parsed = response.parsed
    result = (
        parsed
        if isinstance(parsed, LLMAnalysis)
        else LLMAnalysis.model_validate_json(response.text or "")
    )
    return _finalize(result)


def _finalize(result: LLMAnalysis) -> LLMAnalysis:
    """Clamp the score and keep the level consistent with it, whichever provider answered."""
    result.llm_score = max(0, min(100, result.llm_score))
    result.risk_level = risk_level_for(result.llm_score)
    return result


_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def parse_json_analysis(text: str) -> LLMAnalysis:
    """Validate a JSON answer from a non-Gemini model. Tolerates <think> blocks (Qwen) and code fences."""
    cleaned = _THINK_RE.sub("", text or "")
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in model output")
    data = json.loads(cleaned[start : end + 1])
    # The level is always derived from the score, so don't reject a good answer over "critical" vs "Critical".
    if isinstance(data, dict) and isinstance(data.get("llm_score"), (int, float)):
        data["risk_level"] = risk_level_for(max(0, min(100, int(data["llm_score"]))))
    return _finalize(LLMAnalysis.model_validate(data))


async def _call_gemini(payload: str) -> tuple[LLMAnalysis, str]:
    """Try each model in the chain; return (analysis, model_used). Raises the last error if all fail."""
    # No same-model retries (attempts counts the original request): an overloaded model tends to stay
    # overloaded, so failing over to the next model in the chain is the fastest recovery.
    http_options = types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1))
    last_error: Exception | None = None
    # A client per request: the async client's HTTP session is bound to the event loop it was created on.
    async with genai.Client(
        api_key=settings.gemini_api_key, http_options=http_options
    ).aio as client:
        for model in model_chain():
            try:
                analysis = await asyncio.wait_for(
                    _call_model(client, model, payload),
                    timeout=settings.per_model_timeout_seconds,
                )
                return analysis, model
            except asyncio.TimeoutError as exc:
                logger.warning(
                    "Gemini model %s timed out after %gs; trying next model",
                    model,
                    settings.per_model_timeout_seconds,
                )
                last_error = exc
            except genai_errors.APIError as exc:
                if exc.code not in NEXT_MODEL_CODES:
                    raise
                logger.warning(
                    "Gemini model %s unavailable (HTTP %s); trying next model",
                    model,
                    exc.code,
                )
                last_error = exc
    assert last_error is not None  # model_chain() is never empty
    raise last_error


# --- Groq / Ollama (httpx, no extra dependencies) -------------------------------


class ProviderError(Exception):
    """A provider tier failed; `reason` is short and safe to show (it never contains keys)."""

    def __init__(self, provider: str, reason: str, code: int | None = None):
        super().__init__(f"{provider}: {reason}")
        self.provider = provider
        self.reason = reason
        self.code = code


class AllProvidersFailed(Exception):
    def __init__(self, failures: list[ProviderError]):
        super().__init__("; ".join(str(f) for f in failures))
        self.failures = failures


def _messages(payload: str) -> list[dict]:
    # Instructions in the system message; the untrusted message only inside the user-side data payload.
    return [
        {"role": "system", "content": JSON_SYSTEM_PROMPT},
        {"role": "user", "content": payload},
    ]


def _http_reason(exc: Exception) -> tuple[str, int | None]:
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code}", exc.response.status_code
    if isinstance(exc, httpx.TimeoutException):
        return "timed out", None
    if isinstance(exc, httpx.ConnectError):
        return "not reachable", None
    if isinstance(exc, (ValueError, ValidationError, KeyError, IndexError, TypeError)):
        return "invalid JSON answer", None
    return type(exc).__name__, None


async def _call_groq(payload: str) -> tuple[LLMAnalysis, str]:
    """Try each Groq model in order; a rate limit, outage, retired model or bad JSON moves on."""
    headers = {"Authorization": f"Bearer {settings.groq_api_key}"}
    last: ProviderError | None = None
    async with httpx.AsyncClient(timeout=settings.groq_timeout_seconds, transport=HTTP_TRANSPORT) as client:
        for model in settings.groq_models:
            try:
                response = await client.post(
                    GROQ_URL,
                    headers=headers,
                    json={
                        "model": model,
                        "messages": _messages(payload),
                        "response_format": {"type": "json_object"},
                        "temperature": 0.2,
                    },
                )
                if response.status_code == 401:
                    # A bad key fails every model the same way: stop this tier.
                    raise ProviderError("Groq", "API key rejected (HTTP 401)", 401)
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                return parse_json_analysis(content), f"{model.split('/')[-1]} (Groq)"
            except ProviderError:
                raise
            except Exception as exc:  # noqa: BLE001 - try the next model on any failure
                reason, code = _http_reason(exc)
                logger.warning("Groq model %s failed (%s); trying next model", model, reason)
                last = ProviderError("Groq", reason, code)
    raise last or ProviderError("Groq", "no models configured")


async def _call_ollama(payload: str) -> tuple[LLMAnalysis, str]:
    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    try:
        async with httpx.AsyncClient(timeout=settings.ollama_timeout_seconds, transport=HTTP_TRANSPORT) as client:
            response = await client.post(
                url,
                json={
                    "model": settings.ollama_model,
                    "messages": _messages(payload),
                    "format": "json",
                    "stream": False,
                    "options": {"temperature": 0.2},
                },
            )
            response.raise_for_status()
            content = response.json()["message"]["content"]
            return parse_json_analysis(content), f"{settings.ollama_model} (Ollama)"
    except Exception as exc:  # noqa: BLE001
        reason, code = _http_reason(exc)
        logger.warning("Ollama failed (%s)", reason)
        raise ProviderError("Ollama", reason, code) from exc


# --- Orchestration -----------------------------------------------------------------


async def _gemini_tier(payload: str) -> tuple[LLMAnalysis, str]:
    # The whole Gemini tier has its own budget so an outage hands over to Groq quickly.
    try:
        return await asyncio.wait_for(_call_gemini(payload), timeout=settings.gemini_tier_timeout_seconds)
    except asyncio.TimeoutError as exc:
        raise ProviderError("Gemini", "timed out") from exc
    except genai_errors.APIError as exc:
        raise ProviderError("Gemini", f"HTTP {exc.code}", exc.code) from exc
    except Exception as exc:  # noqa: BLE001 - SDK / parse errors
        raise ProviderError("Gemini", type(exc).__name__) from exc


def _tiers():
    tiers = []
    if is_configured(settings.gemini_api_key):
        tiers.append(_gemini_tier)
    if is_configured(settings.groq_api_key):
        tiers.append(_call_groq)
    if settings.ollama_model:
        tiers.append(_call_ollama)
    return tiers


async def _run_chain(payload: str, tiers) -> tuple[LLMAnalysis, str]:
    failures: list[ProviderError] = []
    for call in tiers:
        try:
            return await call(payload)
        except ProviderError as exc:
            logger.warning("%s tier failed (%s); trying next provider", exc.provider, exc.reason)
            failures.append(exc)
    raise AllProvidersFailed(failures)


def _failure_note(failures: list[ProviderError]) -> str:
    if len(failures) == 1 and failures[0].provider == "Gemini":
        code = failures[0].code
        if code == 429:
            return "AI analysis skipped: Gemini rate limit reached on all models (rules-only fallback)"
        if code in (500, 503):
            return "AI analysis skipped: Gemini is overloaded right now (rules-only fallback)"
        if code == 404:
            return "AI analysis skipped: no configured Gemini model is available to this API key (rules-only fallback)"
        if code is not None:
            return f"AI analysis failed (HTTP {code}) (rules-only fallback)"
        return f"AI analysis failed ({failures[0].reason}) (rules-only fallback)"
    detail = "; ".join(f"{f.provider}: {f.reason}" for f in failures)
    return f"AI analysis skipped: all AI providers failed ({detail}) (rules-only fallback)"


async def analyze_with_llm(
    text: str,
    entities: ExtractedEntities,
    rule_result: RuleResult,
    external: ExternalCheckResult,
) -> LLMOutcome:
    tiers = _tiers()
    if not tiers:
        return LLMOutcome(
            fallback_analysis(rule_result),
            False,
            "AI analysis skipped: GEMINI_API_KEY not configured (rules-only fallback)",
        )
    payload = _build_payload(text, entities, rule_result, external)
    try:
        analysis, model = await asyncio.wait_for(_run_chain(payload, tiers), timeout=settings.llm_timeout_seconds)
        return LLMOutcome(analysis, True, model=model)
    except asyncio.TimeoutError:
        note = f"AI analysis timed out after {settings.llm_timeout_seconds:g}s (rules-only fallback)"
    except AllProvidersFailed as exc:
        logger.warning("All AI providers failed: %s", exc)
        note = _failure_note(exc.failures)
    except Exception as exc:  # noqa: BLE001 - must always degrade gracefully
        logger.warning("AI analysis failed: %s", type(exc).__name__)
        note = f"AI analysis failed ({type(exc).__name__}) (rules-only fallback)"
    return LLMOutcome(fallback_analysis(rule_result), False, note)
