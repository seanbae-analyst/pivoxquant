"""Regression — self-audit scrub must use the authoritative legal filter
(services.legal_filter.safe_scrub) instead of a home-rolled banned-list
re.sub loop, and the deterministic pattern-summary fallback must be compliant.

Pre-fix bug (services/artifacts/self_audit_service.py, old AI path):
    banned = ["추천", "매수", "매도", "조언", "buy", "sell", "recommend"]
    for w in banned:
        text = re.sub(w, "관찰", text, flags=re.IGNORECASE)
Two defects:
  (a) no lookbehind → corrupts legit quant terms: 과매수→과관찰, 매수세→관찰세
  (b) banned list far narrower than the authoritative filter (missing
      익절/손절/take profit/stop loss + 89 surgical patterns).

NOTE (2026-06-03 legal re-audit): the self_audit AI pattern-summary path was
retired — it was an orphaned ``import ai_service`` (module moved to
``services.ai.service`` in the services/ reorg) that always raised
ModuleNotFoundError and fell back. These tests previously patched
``sys.modules['ai_service']`` to exercise that path; they now guard the scrub
SoT (``safe_scrub``) directly + assert the deterministic fallback the function
returns is compliant (which also pins the '매수 결정'→'거래 결정' fix).
"""
from __future__ import annotations


def _scored_sample():
    return [{
        "ticker": "AAPL", "buy_date": "2026-01-02", "buy_price": 100.0,
        "outcome": "win", "return_pct": 12.3,
    }]


def test_quant_term_gwa_maesoo_not_corrupted():
    """'과매수'/'매수세' (legit quant terms) MUST survive safe_scrub verbatim —
    the old home-rolled re.sub loop turned 과매수→과관찰. The authoritative
    filter's (?<!과) lookbehind guard preserves them."""
    from services.legal_filter import safe_scrub

    benign = "이번 분기에는 RSI 과매수 구간과 매수세 증가가 관찰되었습니다."
    out = safe_scrub(benign, context="self_audit") or benign

    assert "과매수" in out, f"과매수 corrupted to: {out!r}"
    assert "매수세" in out, f"매수세 corrupted to: {out!r}"
    assert "과관찰" not in out and "관찰세" not in out, (
        f"home-rolled scrub regression — quant term mangled: {out!r}"
    )


def test_advisory_directive_blocked_by_filter():
    """A genuine advisory directive ('지금 매수하세요') must NOT survive the
    authoritative scrub intact, and is_compliant must reject the raw form."""
    from services.legal_filter import safe_scrub, is_compliant

    advisory = "지금 매수하세요. 이 종목을 추천합니다."
    scrubbed = safe_scrub(advisory, context="self_audit") or ""

    assert "지금 매수하세요" not in scrubbed, (
        f"advisory directive leaked through unscrubbed: {scrubbed!r}"
    )
    assert not is_compliant(advisory), (
        "is_compliant must reject a naked advisory directive"
    )


def test_pattern_summary_fallback_is_compliant():
    """The deterministic pattern-summary fallback (the only path after the
    2026-06-03 AI retirement) must itself be compliant — guards against the
    '매수 결정' phrasing that tripped is_compliant before the fix."""
    from services.artifacts import self_audit_service as sas
    from services.legal_filter import is_compliant

    out = sas._pattern_summary(_scored_sample(), win_rate=1.0, avg_ret=12.3)
    assert out, "pattern summary returned empty"
    assert is_compliant(out), f"non-compliant fallback reached caller: {out!r}"
