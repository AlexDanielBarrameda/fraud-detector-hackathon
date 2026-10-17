"""Hybrid scorer: blends rule and LLM scores, then applies critical floor overrides."""

from app.schemas.analysis import ExternalCheckResult, ExtractedEntities, RiskLevel, RuleResult

SAFE_BROWSING_FLOOR = 90
OTP_WITH_LINK_FLOOR = 85
NEW_DOMAIN_FLOOR = 70
NEW_DOMAIN_DAYS = 30


def risk_level_for(score: int) -> RiskLevel:
    if score >= 85:
        return "Critical"
    if score >= 60:
        return "High"
    if score >= 30:
        return "Medium"
    return "Low"


def compute_final_score(
    rule_result: RuleResult,
    llm_score: int,
    entities: ExtractedEntities,
    external: ExternalCheckResult,
    llm_used: bool = True,
) -> tuple[int, RiskLevel]:
    rule_score = rule_result.rule_score
    if llm_used:
        blended = round(0.4 * rule_score + 0.6 * llm_score)
        # Keep a strong signal from either side from being diluted by a weak one.
        final = max(blended, round(llm_score * 0.85), round(rule_score * 0.85))
    else:
        # Rules-only mode: there is no independent LLM score to blend with, so the rules are the verdict.
        final = rule_score

    if external.safe_browsing_threats:
        final = max(final, SAFE_BROWSING_FLOOR)
    if rule_result.has("otp_request") and entities.urls:
        final = max(final, OTP_WITH_LINK_FLOOR)
    if external.youngest_domain_days is not None and external.youngest_domain_days < NEW_DOMAIN_DAYS:
        final = max(final, NEW_DOMAIN_FLOOR)

    final = max(0, min(100, final))
    return final, risk_level_for(final)
