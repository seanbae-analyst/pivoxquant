"""
Journal Companion — Server-Side Legal Output Gate.

Second line of defense after the system prompt. Every Agent response is
passed through this gate BEFORE being returned to the user. Any violation
discards the response and returns the T5 (Refusal) template.

Defense layers:
  1. Hardcoded system prompt (services/agents/prompts/companion_system.md)
  2. THIS MODULE — regex + advice-pattern filter (20 rules)
  3. Triple disclaimer (terms + session banner + per-response footer)
  4. Audit log (user_agent_audit table, 2-year retention)
  5. Admin kill switch (`settings.AGENT_ENABLED = False`)

References:
  - reports/legal/SAFE_FEATURE_SPECS_2026-04-23.md §6
  - services/legal_filter.py (89 regex — imported and extended here)

Iron rule: false positives (over-refuse) are recoverable, false negatives
(let advice through) are career-ending. Bias toward refusal.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from services.legal_filter import detect_prohibited  # 89-regex detector

logger = logging.getLogger(__name__)


# ── Advice patterns (20 new regex specific to Journal Companion) ─────────────

ADVICE_PATTERNS: tuple[tuple[str, str], ...] = (
    # Direct action words. Note: "hold" is deliberately omitted because
    # "holding period", "avg hold", "hold days" are legitimate neutral
    # factual terms in T2 Mirror output. "long/short" also omitted — they
    # overlap with duration adjectives ("long position" is fine in a mirror
    # summary) and the remaining imperatives below cover the risky surface.
    (r"\b(buy|sell|accumulate|trim)\b",
     "direct-action-verb"),
    (r"\b(take profit|cut loss|stop loss|exit|enter)\b",
     "trade-imperative"),
    (r"(매수|매도|매입|익절|손절|진입|청산)(하|하세|하시|할)",
     "kr-action-verb"),

    # Recommendation language. "advise" is handled separately because the
    # T5 refusal itself legitimately says "I can't advise" — we only flag
    # the POSITIVE assertion form ("I advise", "advise you to", "I'd advise").
    (r"\b(recommend|suggest|should|must|ought to)\b",
     "recommend-verb"),
    (r"\b(i(?:'m)?\s+advis\w+|i'?d\s+advise|advise\s+(?:you|that)|my advice\b)",
     "advise-assertion"),
    (r"(추천|권장|권유|조언|유망)",
     "kr-recommend-verb"),
    (r"\b(i think|i believe|in my opinion|my view)\b",
     "first-person-opinion"),

    # Evaluation language (forbidden for Agent — public AI handles this)
    (r"\b(good|bad|weak|strong|sound|flawed) (trade|decision|thesis|reasoning)\b",
     "thesis-evaluation"),
    (r"(좋은|나쁜|약한|강한|훌륭한|부실한) (거래|결정|논리|판단)",
     "kr-thesis-evaluation"),

    # Labels reserved for public AI
    (r"\b(POSITIVE|NEGATIVE|NEUTRAL)\b",
     "public-ai-label-leak"),

    # Prediction language
    (r"\b(will|going to|likely to) (rise|fall|rally|crash|drop|surge)\b",
     "prediction-verb"),
    (r"(오를 것|내릴 것|상승할|하락할|반등할)",
     "kr-prediction"),

    # Price targets (word presence alone is disqualifying — Agent must never
    # discuss valuation targets regardless of whether a number follows)
    (r"\b(target price|price target|fair value|intrinsic value)\b",
     "price-target"),
    (r"(목표가|적정가|목표주가|내재가치)",
     "kr-price-target"),

    # Stop/profit levels
    (r"(stop (loss|at)|take profit at|tp at|sl at)\s*[\$₩]?\d",
     "stop-profit-level"),

    # Outlook/forecast
    (r"\b(outlook|forecast|expected return|price forecast)\b",
     "outlook-forecast"),
    (r"(전망|예상 수익률|목표 수익률)",
     "kr-outlook"),

    # Sector/allocation suggestions
    (r"\b(overweight|underweight|allocation|rebalance to)\b",
     "allocation-suggestion"),
    (r"(비중 확대|비중 축소|리밸런싱 필요)",
     "kr-allocation-suggestion"),

    # Cross-user references (privacy violation)
    (r"\b(other users|other investors|users in your group|people like you)\b",
     "cross-user-reference"),
    (r"(다른 유저|비슷한 투자자들|네 그룹의 다른)",
     "kr-cross-user"),

    # Soft advisory vocabulary — 2026-04-23 legal sweep addition. These slip
    # past the stricter "recommend/should/must" set but are still advisory
    # in tone when referring to a security.
    (r"\b(promising|attractive|worth (?:a )?look|worth watching|keep an eye on)\b",
     "soft-advisory-en"),
    (r"(유망|가능성이 높|주목할|지켜볼|눈여겨볼)",
     "soft-advisory-kr"),
)


# ── Required output framing (must be present) ────────────────────────────────

REQUIRED_FOOTER_PATTERNS: tuple[str, ...] = (
    r"not investment advice",
    r"your record,? your decision",
    r"자문이 아님|자문 아님",
)


# ── Data types ───────────────────────────────────────────────────────────────

class GateVerdict(Enum):
    """Outcome of running agent output through the legal gate."""

    PASS = "pass"
    DENY_ADVICE_PATTERN = "deny_advice_pattern"
    DENY_LEGAL_REGEX = "deny_legal_regex"
    DENY_MISSING_FOOTER = "deny_missing_footer"
    DENY_LENGTH = "deny_length"


@dataclass(frozen=True)
class GateResult:
    verdict: GateVerdict
    reason: str
    matched_pattern: Optional[str]
    offending_span: Optional[str]
    safe_output: str  # always set — either the original or T5 fallback


# ── T5 Refusal fallback ──────────────────────────────────────────────────────

T5_REFUSAL = (
    "I can't advise. I can only help you check your record.\n"
    "Would you like me to surface:\n"
    "1. What you previously wrote about this?\n"
    "2. Your pattern across similar trades?\n"
    "3. Your IPS clause on this?\n"
    "\n"
    "— Not investment advice. Your record, your decision."
)


# ── Public API ───────────────────────────────────────────────────────────────

def run_gate(output: str, *, max_length: int = 2400) -> GateResult:
    """Run an Agent response through the legal gate.

    The gate is intentionally biased toward refusal. When in doubt, return
    T5. Callers MUST use ``result.safe_output`` — never the raw input.

    Args:
        output: raw text produced by the LLM.
        max_length: hard character cap. Beyond this = deny (prompt likely
                    hallucinated or escaped format).

    Returns:
        GateResult with verdict + safe_output always populated.
    """
    if not output or not output.strip():
        return GateResult(
            verdict=GateVerdict.DENY_LENGTH,
            reason="empty-output",
            matched_pattern=None,
            offending_span=None,
            safe_output=T5_REFUSAL,
        )

    stripped = output.strip()

    if len(stripped) > max_length:
        logger.warning("agent.gate.deny len=%d", len(stripped))
        return GateResult(
            verdict=GateVerdict.DENY_LENGTH,
            reason=f"exceeds-{max_length}",
            matched_pattern=None,
            offending_span=stripped[:120],
            safe_output=T5_REFUSAL,
        )

    # Bug #4 (Wave F-1) — T3 IPS Covenant Check renders the user's own IPS
    # text verbatim inside double quotes (companion_system.md T3 template),
    # e.g. `"Position sizes should not exceed 15%."`. The bare "should"/"must"
    # rule in ADVICE_PATTERNS fires on that quoted source even though the
    # Agent itself is not making the recommendation — it is mirroring the
    # user's own policy back to them, which is the entire point of T3.
    # Strip quoted spans before pattern detection so the Agent's own prose
    # is still gated, but IPS verbatim quotes are not. Original `stripped`
    # remains in use for length/footer checks and the safe_output.
    deadvice_input = _strip_quoted_spans(stripped)

    # Layer 1: advice-specific patterns (20 rules)
    for pattern, label in ADVICE_PATTERNS:
        m = re.search(pattern, deadvice_input, flags=re.IGNORECASE | re.MULTILINE)
        if m:
            logger.warning(
                "agent.gate.deny advice_pattern=%s matched=%r",
                label, m.group(0),
            )
            return GateResult(
                verdict=GateVerdict.DENY_ADVICE_PATTERN,
                reason=label,
                matched_pattern=pattern,
                offending_span=_context(stripped, m.start(), m.end()),
                safe_output=T5_REFUSAL,
            )

    # Layer 2: existing 89 legal regex (shared detector from legal_filter.py)
    prohibited_hits = detect_prohibited(stripped)
    if prohibited_hits:
        logger.warning(
            "agent.gate.deny legal_filter hits=%s", prohibited_hits[:5],
        )
        return GateResult(
            verdict=GateVerdict.DENY_LEGAL_REGEX,
            reason=f"shared-legal-filter:{prohibited_hits[0]}",
            matched_pattern=prohibited_hits[0],
            offending_span=stripped[:200],
            safe_output=T5_REFUSAL,
        )

    # Layer 3: required footer presence
    if not any(re.search(p, stripped, flags=re.IGNORECASE)
               for p in REQUIRED_FOOTER_PATTERNS):
        logger.info("agent.gate.deny missing-footer")
        return GateResult(
            verdict=GateVerdict.DENY_MISSING_FOOTER,
            reason="missing-footer",
            matched_pattern=None,
            offending_span=stripped[-120:],
            safe_output=T5_REFUSAL,
        )

    return GateResult(
        verdict=GateVerdict.PASS,
        reason="ok",
        matched_pattern=None,
        offending_span=None,
        safe_output=stripped,
    )


def _context(text: str, start: int, end: int, window: int = 40) -> str:
    """Return a short snippet around a regex match for audit logs."""
    lo = max(0, start - window)
    hi = min(len(text), end + window)
    return text[lo:hi]


# Quoted-span stripping — see Bug #4 note in run_gate(). Replaces matched
# `"..."` runs with whitespace of equal length so downstream regex match
# offsets stay aligned with the original `_context()` slice. Smart quotes
# (U+201C/U+201D) and Korean 「」 are also handled because the T3 template
# is rendered for KO users too. Single quotes are deliberately NOT stripped
# — they overlap with apostrophes ("I'd advise") and would create a hole
# the gate cannot recover from.
_QUOTED_SPAN_RE = re.compile(r'"[^"]*"|“[^”]*”|「[^」]*」')


def _strip_quoted_spans(text: str) -> str:
    """Return `text` with quoted spans replaced by equal-length whitespace.

    Used to keep regex match offsets stable for diagnostics while preventing
    IPS verbatim quotes inside T3 responses from tripping ADVICE_PATTERNS.
    """
    if not text or '"' not in text and '“' not in text and '「' not in text:
        return text
    return _QUOTED_SPAN_RE.sub(lambda m: " " * len(m.group(0)), text)
