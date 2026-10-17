"""Gemini structured-output analysis with a model fallback chain and a deterministic rules-only fallback."""

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from google.genai.client import AsyncClient

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
    # Clamp and keep the level consistent with the score.
    result.llm_score = max(0, min(100, result.llm_score))
    result.risk_level = risk_level_for(result.llm_score)
    return result


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


async def analyze_with_llm(
    text: str,
    entities: ExtractedEntities,
    rule_result: RuleResult,
    external: ExternalCheckResult,
) -> LLMOutcome:
    if not is_configured(settings.gemini_api_key):
        return LLMOutcome(
            fallback_analysis(rule_result),
            False,
            "AI analysis skipped: GEMINI_API_KEY not configured (rules-only fallback)",
        )
    try:
        payload = _build_payload(text, entities, rule_result, external)
        analysis, model = await asyncio.wait_for(
            _call_gemini(payload), timeout=settings.llm_timeout_seconds
        )
        return LLMOutcome(analysis, True, model=model)
    except asyncio.TimeoutError:
        note = f"AI analysis timed out after {settings.llm_timeout_seconds:g}s (rules-only fallback)"
    except genai_errors.APIError as exc:
        logger.warning("Gemini analysis failed: HTTP %s %s", exc.code, exc.status)
        if exc.code == 429:
            note = "AI analysis skipped: Gemini rate limit reached on all models (rules-only fallback)"
        elif exc.code in (500, 503):
            note = "AI analysis skipped: Gemini is overloaded right now (rules-only fallback)"
        elif exc.code == 404:
            note = "AI analysis skipped: no configured Gemini model is available to this API key (rules-only fallback)"
        else:
            note = f"AI analysis failed (HTTP {exc.code}) (rules-only fallback)"
    except (
        Exception
    ) as exc:  # noqa: BLE001 - any SDK/network/parse failure must degrade gracefully
        logger.warning("Gemini analysis failed: %s", type(exc).__name__)
        note = f"AI analysis failed ({type(exc).__name__}) (rules-only fallback)"
    return LLMOutcome(fallback_analysis(rule_result), False, note)
