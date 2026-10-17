"""Weighted heuristic fraud rules (English + common Filipino/Taglish phrasing).

Each rule inspects the message text, the extracted entities, and (optionally) the
external check results, and contributes its weight to `rule_score` (capped at 100).
"""

import ipaddress
import re
from collections.abc import Callable
from dataclasses import dataclass

from app.schemas.analysis import ExternalCheckResult, ExtractedEntities, RuleFlag, RuleResult


def _rx(*patterns: str) -> re.Pattern[str]:
    return re.compile("|".join(patterns), re.IGNORECASE)


# --- Brand data -------------------------------------------------------------

# Brand keyword -> official registered domains. A link to anything else alongside the brand is suspicious.
BRAND_DOMAINS: dict[str, set[str]] = {
    "gcash": {"gcash.com"},
    "maya": {"maya.ph", "paymaya.com"},
    "paymaya": {"maya.ph", "paymaya.com"},
    "bdo": {"bdo.com.ph"},
    "bpi": {"bpi.com.ph"},
    "metrobank": {"metrobank.com.ph"},
    "landbank": {"landbank.com"},
    "unionbank": {"unionbankph.com"},
    "security bank": {"securitybank.com"},
    "rcbc": {"rcbc.com"},
    "pnb": {"pnb.com.ph"},
    "chinabank": {"chinabank.ph"},
    "sss": {"sss.gov.ph"},
    "philhealth": {"philhealth.gov.ph"},
    "pag-ibig": {"pagibigfund.gov.ph"},
    "lbc": {"lbcexpress.com"},
    "j&t": {"jtexpress.ph"},
    "lazada": {"lazada.com.ph"},
    "shopee": {"shopee.ph"},
    "paypal": {"paypal.com"},
    "netflix": {"netflix.com"},
    "meralco": {"meralco.com.ph"},
}
BRAND_RE = re.compile(r"\b(" + "|".join(re.escape(b) for b in BRAND_DOMAINS) + r")\b", re.IGNORECASE)
# Tokens that, inside a non-official domain name, indicate a lookalike (e.g. "gcash-verify.top").
LOOKALIKE_TOKENS = {"gcash", "paymaya", "bdo", "bpi", "metrobank", "landbank", "unionbank", "securitybank",
                    "rcbc", "chinabank", "philhealth", "pagibig", "lazada", "shopee", "paypal", "netflix", "meralco",
                    "maya", "lbc", "jnt", "jtexpress"}
OFFICIAL_DOMAINS = set().union(*BRAND_DOMAINS.values())

SUSPICIOUS_TLDS = {"top", "xyz", "icu", "click", "link", "live", "shop", "online", "site", "club", "vip", "buzz",
                   "rest", "cfd", "sbs", "monster", "work", "loan", "win", "bid", "tk", "ml", "ga", "cf", "gq",
                   "cyou", "zip", "mov", "lol", "fun", "store"}
URL_SHORTENERS = {"bit.ly", "tinyurl.com", "goo.gl", "is.gd", "cutt.ly", "rb.gy", "tiny.cc", "ow.ly",
                  "shorturl.at", "s.id", "rebrand.ly", "t.ly", "bitly.ws", "shorturl.asia", "v.gd"}

# --- Phrase patterns --------------------------------------------------------

OTP_TERM_RE = _rx(r"\botp\b", r"one[- ]time[- ](?:pin|password|code)", r"\bm-?pin\b", r"\bcvv\b",
                  r"\bpin\s*code\b", r"verification code", r"\bpassword\b", r"security code")
REQUEST_VERB_RE = _rx(r"\b(?:send|reply|share|provide|enter|re-?enter|give|confirm|verify|validate|update|type|"
                      r"input|submit|forward|tell)\b",
                      r"\bi-?(?:send|bigay|reply|type)\b", r"\bibigay\b", r"\bipadala\b", r"\bpakisend\b")
# A real OTP SMS *contains* the code ("Use OTP 482913 to verify your login"); a scam asks you for it.
OTP_DELIVERY_RE = _rx(r"(?:\botp\b|\bcode\b|\bpin\b|one[- ]time[- ](?:pin|password))\D{0,20}\b\d{4,8}\b")
NEGATION_RE = _rx(r"\bnever\b", r"\bdo not\b", r"\bdon'?t\b", r"\bwill not\b", r"\bwon'?t\b",
                  r"\bhuwag\b", r"\bwag\b", r"\bnot to\b")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?\n])\s+")

VERIFY_ACCOUNT_RE = _rx(
    r"\b(?:verify|confirm|update|validate|re-?activate|unlock|secure)\s+(?:your|the|ur)\s+"
    r"(?:billing\s+|payment\s+|personal\s+|delivery\s+)?"
    r"(?:account|identity|details|information|info|kyc|card|wallet|e-?wallet|address)",
    r"\bi-?verify\b",
)
URGENCY_RE = _rx(
    r"\burgent(?:ly)?\b", r"\bimmediately\b", r"\bwithin\s+\d+\s*(?:hours?|hrs?|minutes?|mins?)\b",
    r"\b(?:suspended|deactivated|locked|blocked|frozen|terminated|restricted)\b", r"\bfinal (?:notice|warning)\b",
    r"\b(?:will|shall) be (?:closed|suspended|deactivated|blocked)\b", r"\bexpires? (?:today|tonight|soon)\b",
    r"\btoday only\b", r"\bact now\b", r"\bagad\b", r"\bngayon din\b",
    r"\b(?:avoid|prevent)\s+(?:account\s+|permanent\s+)?(?:suspension|deactivation|closure|termination|lock(?:ing)?)\b",
)
PRIZE_RE = _rx(
    r"\byou(?:'ve| have)? won\b", r"\bcongratulations\b", r"\bwinner\b", r"\bprize\b", r"\braffle\b",
    r"\blottery\b", r"\bjackpot\b", r"\bclaim your\b", r"\bnanalo\b", r"\bpanalo\b", r"\bfree (?:iphone|gift|load)\b",
    r"\b(?:lucky|randomly) selected\b",
)
MESSAGING_APP_RE = _rx(r"\btelegram\b", r"\bwhats\s?app\b", r"\bviber\b", r"\bt\.me/", r"\bwa\.me/")
JOB_RE = _rx(
    r"\bpart[- ]?time\b", r"\bwork from home\b", r"\bwfh\b", r"\bcommission\b", r"\bdaily (?:income|salary|pay)\b",
    r"\bearn (?:up to|₱|php|p\d|\$|\d)", r"\b(?:like|follow|rate)\s+(?:and|&)\s+(?:like|follow|subscribe|rate)\b",
    r"\bsimple tasks?\b", r"\btask\b", r"\bhiring\b", r"\bsalary\b", r"\b(?:per|a) day\b", r"\bkikita\b",
    r"\brecruit(?:er|ment)?\b",
)
FEE_CRYPTO_RE = _rx(
    r"\b(?:processing|release|clearance|handling|customs|activation|registration|withdrawal|unlocking|"
    r"verification|insurance|tax|re-?delivery|re-?shipping) fee\b",
    r"\bpay (?:a |the )?(?:small |minimal )?fee\b", r"\b(?:usdt|bitcoin|btc|ethereum|eth|crypto|binance)\b",
    r"\bwallet address\b", r"\bgift cards?\b", r"\btop[- ]?up (?:first|to (?:withdraw|unlock|claim))\b",
    r"\bdeposit (?:first|to (?:withdraw|unlock|claim|activate))\b", r"\bbayad muna\b",
)
# Family/friend impersonation: a "new number"/lost-phone story or an emergency, *plus* a money ask.
# Family words alone ("Ma", "anak", "tita") aren't enough: "Ma, sent you 500 sa GCash" is a normal message.
IMPERSONATION_CUE_RE = _rx(
    r"\b(?:my|this is my|here'?s my|i have a|i got a) new (?:number|phone|sim)\b", r"\bnew (?:number|num|sim) ko\b",
    r"\bbagong (?:number|num|sim)\b", r"\blost my (?:phone|cellphone|sim)\b", r"\b(?:my|the) phone (?:is )?broke\b",
    r"\b(?:nawala|nasira|nanakaw|naiwan)\s+(?:ang|yung|'yung|ung)\s+(?:phone|cellphone|cp|sim)\b",
    r"\b(?:it'?s|this is|si)\s+(?:mom|mama|dad|papa|your (?:son|daughter|anak)|tita|tito|kuya|ate)\b(?:\s+(?:ito|to))?",
)
EMERGENCY_CUE_RE = _rx(
    r"\bemergency\b", r"\bhospital\b", r"\b(?:na-?)?ospital\b", r"\bnaaksidente\b", r"\baccident\b", r"\bnahuli\b",
    r"\bpolice\b", r"\bpulis\b", r"\bkailangan (?:ko )?(?:ng )?pera\b", r"\bnasa (?:presinto|er)\b",
)
MONEY_ASK_RE = _rx(
    r"\bpa-?load\b", r"\bpasaload\b", r"\bpadala(?:han)?\b", r"\bpautang\b", r"\bpahiram\b",
    r"\bsend (?:me|money|ng|mo|po)\b", r"\btransfer (?:me|mo|ng|po)\b", r"\bbank transfer\b",
    # Money-ask phrasing only; a bare "GCash"/"bank" mention appears in plenty of legit texts.
    r"\b(?:i|pa)-?gcash\b", r"\b(?:sa|via|through|thru) (?:gcash|maya)\b", r"\bgcash (?:mo|ko|number|num)\b",
    r"\bpera\b", r"\bmoney\b", r"\bload\b", r"(?:₱|\bphp|\bp)\s?\d",
)
# Text aimed at the AI/filter rather than the human reader. Trying to manipulate a fraud detector is itself a red flag.
PROMPT_INJECTION_RE = _rx(
    r"\b(?:ignore|disregard|forget|override)\s+(?:all\s+|any\s+)?(?:the\s+|your\s+)?(?:previous|prior|above|earlier|"
    r"preceding)?\s*(?:instructions?|prompts?|rules|guidelines|directives)\b",
    r"\bsystem prompt\b", r"\bdeveloper mode\b", r"\bjailbreak\b", r"\byou are now (?:a|an|in)\b",
    r"\b(?:rate|score|return|output|set|give|assign)\b[^.\n]{0,25}?\b(?:score|rating|risk)\b[^.\n]{0,12}?\b0\b",
    r"\b(?:rate|score)\s+this\s+(?:message\s+|sms\s+|text\s+|email\s+)?(?:as\s+)?0\b",
    r"\b(?:mark|classify|label|flag|rate|treat)\s+(?:this|it|the message|this message)\s+as\s+"
    r"(?:safe|low[- ]risk|legit(?:imate)?|not (?:a )?scam|harmless)\b",
)
PERSONAL_INFO_RE = _rx(
    r"\b(?:send|provide|submit|reply with|give)\b[^.\n]{0,40}\b(?:valid id|selfie|full name|birth ?(?:date|day)|"
    r"card number|account number|mother'?s maiden|home address)\b",
)


# --- Rule definitions -------------------------------------------------------


@dataclass(frozen=True)
class Context:
    text: str
    entities: ExtractedEntities
    external: ExternalCheckResult | None


@dataclass(frozen=True)
class Rule:
    rule_id: str
    description: str
    weight: int
    check: Callable[[Context], bool]


def asks_for_otp(ctx: Context) -> bool:
    """True if a sentence mentions an OTP/MPIN/password *and* asks for it, without warning against
    sharing it and without delivering the code itself."""
    for sentence in SENTENCE_SPLIT_RE.split(ctx.text):
        if (
            OTP_TERM_RE.search(sentence)
            and REQUEST_VERB_RE.search(sentence)
            and not NEGATION_RE.search(sentence)
            and not OTP_DELIVERY_RE.search(sentence)
        ):
            return True
    return False


def _brand_impersonation_with_link(ctx: Context) -> bool:
    brands = {m.group(1).lower() for m in BRAND_RE.finditer(ctx.text)}
    if not brands or not ctx.entities.domains:
        return False
    official = set().union(*(BRAND_DOMAINS[b] for b in brands))
    return any(d not in official for d in ctx.entities.domains)


def _lookalike_domain(ctx: Context) -> bool:
    for domain in ctx.entities.domains:
        if domain in OFFICIAL_DOMAINS:
            continue
        name = domain.split(".")[0].replace("-", "")
        if any(token in name for token in LOOKALIKE_TOKENS):
            return True
    return False


def _suspicious_tld(ctx: Context) -> bool:
    return any(d.rsplit(".", 1)[-1].lower() in SUSPICIOUS_TLDS for d in ctx.entities.domains)


def _url_shortener(ctx: Context) -> bool:
    return any(d.lower() in URL_SHORTENERS for d in ctx.entities.domains)


def is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def _ip_url(ctx: Context) -> bool:
    return any(is_ip(d) for d in ctx.entities.domains)


def _new_domain(ctx: Context) -> bool:
    days = ctx.external.youngest_domain_days if ctx.external else None
    return days is not None and days < 30


def _family_emergency(ctx: Context) -> bool:
    has_story = IMPERSONATION_CUE_RE.search(ctx.text) or EMERGENCY_CUE_RE.search(ctx.text)
    return bool(has_story and MONEY_ASK_RE.search(ctx.text))


RULES: list[Rule] = [
    Rule("prompt_injection", "Contains text trying to manipulate automated scam detection (prompt injection)", 55,
         lambda c: bool(PROMPT_INJECTION_RE.search(c.text))),
    Rule("family_emergency", "Family/friend impersonation: new number or emergency story asking for money or load", 45,
         _family_emergency),
    Rule("otp_request", "Asks you to share an OTP, MPIN, PIN, CVV, or password", 35, asks_for_otp),
    Rule("brand_impersonation_link", "Mentions a bank/e-wallet/agency but links to a non-official domain", 25,
         _brand_impersonation_with_link),
    Rule("lookalike_domain", "Link domain imitates a known brand (lookalike domain)", 20, _lookalike_domain),
    Rule("suspicious_tld", "Link uses a TLD commonly abused by scammers (e.g. .top, .xyz)", 20, _suspicious_tld),
    Rule("new_domain", "Linked domain was registered less than 30 days ago", 20, _new_domain),
    Rule("prize_lure", "Prize, raffle, or lottery lure", 20, lambda c: bool(PRIZE_RE.search(c.text))),
    Rule("task_job_scam", "Job/task offer pushing you to Telegram, WhatsApp, or Viber", 20,
         lambda c: bool(MESSAGING_APP_RE.search(c.text) and JOB_RE.search(c.text))),
    Rule("upfront_fee_crypto", "Requests an upfront fee, crypto, or gift card payment", 20,
         lambda c: bool(FEE_CRYPTO_RE.search(c.text))),
    Rule("ip_address_url","Link points to a raw IP address instead of a domain", 20, _ip_url),
    Rule("urgency_threat", "Urgency or account suspension/lockout threat", 15, lambda c: bool(URGENCY_RE.search(c.text))),
    Rule("account_verification", "Asks you to verify/update your account or identity", 15,
         lambda c: bool(VERIFY_ACCOUNT_RE.search(c.text))),
    Rule("url_shortener", "Uses a URL shortener that hides the real destination", 15, _url_shortener),
    Rule("personal_info_request", "Asks for personal data (ID, birthday, card or account number)", 15,
         lambda c: bool(PERSONAL_INFO_RE.search(c.text))),
]


def evaluate_rules(
    text: str, entities: ExtractedEntities, external: ExternalCheckResult | None = None
) -> RuleResult:
    ctx = Context(text=text, entities=entities, external=external)
    flags = [RuleFlag(rule_id=r.rule_id, description=r.description, weight=r.weight) for r in RULES if r.check(ctx)]
    return RuleResult(rule_score=min(100, sum(f.weight for f in flags)), flags=flags)
