"""Regression — self-audit pattern summary scrub must use the authoritative
legal filter (services.legal_filter.safe_scrub) instead of a home-rolled
banned-list re.sub loop.

Pre-fix bug (services/artifacts/self_audit_service.py ~339-345):
    banned = ["추천", "매수", "매도", "조언", "buy", "sell", "recommend"]
    for w in banned:
        text = re.sub(w, "관찰", text, flags=re.IGNORECASE)
Two defects:
  (a) no lookbehind → corrupts legit quant terms: 과매수→과관찰, 매수세→관찰세
  (b) banned list far narrower than the authoritative filter (missing
      익절/손절/take profit/stop loss + 89 surgical patterns).

Fix: route AI output through safe_scrub(text, context="self_audit"), which has
(?<!과) lookbehind guards so 과매수 survives, while genuine advisory directives
("지금 매수하세요") are scrubbed/blocked by is_compliant.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch


def _fake_resp(text: str):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)]
    )


def _scored_sample():
    return [{
        "ticker": "AAPL", "buy_date": "2026-01-02", "buy_price": 100.0,
        "outcome": "win", "return_pct": 12.3,
    }]


def test_quant_term_gwa_maesoo_not_corrupted():
    """'과매수 신호' (overbought signal) is a legit quant term and MUST be
    preserved verbatim — the old re.sub loop turned it into '과관찰 신호'."""
    from services.artifacts import self_audit_service as sas

    # 'RSI 과매수 구간' and '매수세' are legit quant terms with no advisory
    # intent. The authoritative filter's (?<!과) detection guard lets them pass,
    # and no _REPLACEMENTS rule should corrupt the bare 과매수 token.
    benign = "이번 분기에는 RSI 과매수 구간과 매수세 증가가 관찰되었습니다."

    fake_ai = SimpleNamespace(
        available=True,
        client=SimpleNamespace(
            messages=SimpleNamespace(create=lambda **kw: _fake_resp(benign))
        ),
    )
    fake_module = SimpleNamespace(
        ai_service=fake_ai, AIService=lambda: fake_ai, MODEL="haiku",
    )

    with patch.dict("sys.modules", {"ai_service": fake_module}):
        out = sas._pattern_summary(_scored_sample(), win_rate=1.0, avg_ret=12.3)

    assert "과매수" in out, f"과매수 corrupted to: {out!r}"
    assert "매수세" in out, f"매수세 corrupted to: {out!r}"
    assert "과관찰" not in out and "관찰세" not in out, (
        f"home-rolled scrub regression — quant term mangled: {out!r}"
    )


def test_advisory_directive_blocked_or_scrubbed():
    """A genuine advisory directive ('지금 매수하세요') must NOT pass through
    verbatim — it should be scrubbed or fall back to the deterministic prose."""
    from services.artifacts import self_audit_service as sas

    advisory = "지금 매수하세요. 이 종목을 추천합니다."

    fake_ai = SimpleNamespace(
        available=True,
        client=SimpleNamespace(
            messages=SimpleNamespace(create=lambda **kw: _fake_resp(advisory))
        ),
    )
    fake_module = SimpleNamespace(
        ai_service=fake_ai, AIService=lambda: fake_ai, MODEL="haiku",
    )

    with patch.dict("sys.modules", {"ai_service": fake_module}):
        out = sas._pattern_summary(_scored_sample(), win_rate=1.0, avg_ret=12.3)

    # The naked advisory directive must not survive intact.
    assert "지금 매수하세요" not in out, (
        f"advisory directive leaked through unscrubbed: {out!r}"
    )
    # And the result must itself be compliant.
    from services.legal_filter import is_compliant
    assert is_compliant(out), f"non-compliant output reached caller: {out!r}"
