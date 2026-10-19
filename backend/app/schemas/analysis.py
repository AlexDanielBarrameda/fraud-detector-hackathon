from typing import Literal

from pydantic import BaseModel, Field, field_validator

RiskLevel = Literal["Low", "Medium", "High", "Critical"]


class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000, description="The message or text to analyze for scam indicators")

    @field_validator("text")
    @classmethod
    def not_blank(cls, value: str) -> str:
        # Whitespace-only input would otherwise reach (and spend) the AI providers.
        if not value.strip():
            raise ValueError("text must contain at least one non-whitespace character")
        return value


class ExtractedEntities(BaseModel):
    urls: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list, description="Registered domains of the extracted URLs")
    emails: list[str] = Field(default_factory=list)
    phone_numbers: list[str] = Field(default_factory=list)


class RuleFlag(BaseModel):
    rule_id: str
    description: str
    weight: int


class RuleResult(BaseModel):
    rule_score: int = Field(ge=0, le=100)
    flags: list[RuleFlag] = Field(default_factory=list)

    def has(self, rule_id: str) -> bool:
        return any(f.rule_id == rule_id for f in self.flags)


class ExternalCheckResult(BaseModel):
    urls_found: list[str] = Field(default_factory=list)
    safe_browsing_threats: list[str] = Field(default_factory=list)
    youngest_domain_days: int | None = None
    domain_flags: list[str] = Field(default_factory=list, description="Red flags from RDAP domain-age lookups")
    skipped_checks: list[str] = Field(default_factory=list)

    @property
    def evidence_flags(self) -> list[str]:
        """Verified external findings, shown to the user ahead of the heuristic/LLM red flags."""
        return self.safe_browsing_threats + self.domain_flags


class LLMAnalysis(BaseModel):
    """Structured output schema sent to Gemini as `response_schema`.

    No numeric bounds here on purpose: score is clamped in code so the JSON
    schema stays within what the Gemini API accepts.
    """

    llm_score: int
    risk_level: RiskLevel
    red_flags: list[str]
    explanation: str
    recommended_actions: list[str]


class AnalyzeResponse(BaseModel):
    final_score: int
    risk_level: RiskLevel
    rule_score: int
    llm_score: int
    llm_used: bool = Field(description="False when the deterministic rules-only fallback produced the LLM fields")
    llm_model: str | None = Field(default=None, description="Gemini model that produced the analysis, if any")
    cached: bool = Field(default=False, description="True when served from the in-memory demo cache")
    red_flags: list[str]
    explanation: str
    recommended_actions: list[str]
    rule_flags: list[RuleFlag] = Field(default_factory=list)
    extracted_entities: ExtractedEntities
    external_checks: ExternalCheckResult
