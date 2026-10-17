import asyncio
import hashlib
from collections import OrderedDict

from fastapi import APIRouter

from app.schemas.analysis import AnalyzeRequest, AnalyzeResponse, ExternalCheckResult
from app.services.domain_info import check_domains_age
from app.services.extractor import extract_entities
from app.services.link_checker import check_urls_safe_browsing
from app.services.llm import analyze_with_llm
from app.services.rules import evaluate_rules
from app.services.scorer import compute_final_score

router = APIRouter()

# In-memory LRU cache of successful (LLM-backed) analyses. Re-clicking a demo example
# returns instantly and costs 0 Gemini requests. Rules-only fallbacks are never cached,
# so a message retried after a rate-limit gets a real AI analysis once quota frees up.
CACHE_MAX_ENTRIES = 256
_cache: OrderedDict[str, AnalyzeResponse] = OrderedDict()


def _cache_key(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def clear_cache() -> None:
    _cache.clear()


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    text = request.text
    key = _cache_key(text)
    if key in _cache:
        _cache.move_to_end(key)
        return _cache[key].model_copy(update={"cached": True}, deep=True)

    entities = extract_entities(text)

    # External evidence first (each check has its own 4s timeout and never raises),
    # so rules, the LLM prompt, and the scorer all see it.
    (threats, sb_note), (youngest_days, domain_flags, rdap_notes) = await asyncio.gather(
        check_urls_safe_browsing(entities.urls),
        check_domains_age(entities.urls),
    )
    external = ExternalCheckResult(
        urls_found=entities.urls,
        safe_browsing_threats=threats,
        youngest_domain_days=youngest_days,
        domain_flags=domain_flags,
        skipped_checks=[n for n in [sb_note, *rdap_notes] if n],
    )

    rule_result = evaluate_rules(text, entities, external)
    outcome = await analyze_with_llm(text, entities, rule_result, external)
    if outcome.skipped_note:
        external.skipped_checks.append(outcome.skipped_note)

    final_score, risk_level = compute_final_score(
        rule_result, outcome.analysis.llm_score, entities, external, llm_used=outcome.llm_used
    )

    response = AnalyzeResponse(
        final_score=final_score,
        risk_level=risk_level,
        rule_score=rule_result.rule_score,
        llm_score=outcome.analysis.llm_score,
        llm_used=outcome.llm_used,
        llm_model=outcome.model,
        # Verified external findings lead; then the LLM's (or rules') red flags.
        red_flags=list(dict.fromkeys([*external.evidence_flags, *outcome.analysis.red_flags])),
        explanation=outcome.analysis.explanation,
        recommended_actions=outcome.analysis.recommended_actions,
        rule_flags=rule_result.flags,
        extracted_entities=entities,
        external_checks=external,
    )

    if outcome.llm_used:
        _cache[key] = response.model_copy(deep=True)
        if len(_cache) > CACHE_MAX_ENTRIES:
            _cache.popitem(last=False)
    return response
