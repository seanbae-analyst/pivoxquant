"""Regression test — AIRiskSummary cache isolation (Pattern 6, B1 P0).

Bug: prior `cache_key = f"risk_summary:{int(value)}"` ignored user_id, so two
Pro users with identical portfolio value would share the SAME cache slot —
user B would receive user A's Claude-generated 3-sentence risk summary (PII
leakage of risk_level / top_risk_factor / Korean+English prose).

Fix (services/ai/models.py): cache_key now namespaces by user_id:
    f"risk_summary:{uid_part}:{int(value)}"

Mirrors v44.9 PR #488 (earnings_tone) + v45.2 d1867a74 follow-up.
"""
from __future__ import annotations

from unittest.mock import patch


def _fake_claude_response(user_marker: str):
    """Return a deterministic Claude-shaped dict whose summary embeds a
    per-user marker we can assert on. Bypasses real anthropic client."""
    return {
        "summary_en": f"USER_MARKER={user_marker} risk is moderate.",
        "summary_kr": f"USER_MARKER={user_marker} 리스크 보통.",
        "risk_level": "moderate",
        "top_risk_factor": f"concentration_for_{user_marker}",
    }


class TestRiskSummaryCacheIsolation:
    def test_two_users_same_portfolio_value_get_distinct_cache_slots(self):
        """Same `value` field, different user_id → independent cache entries.

        Without the fix the second call would return the first user's summary
        (cache hit on `risk_summary:1000000`), exposing user A's data to B.
        """
        from services.ai import models as ai_models

        # Wipe module-global cache so test ordering can't taint state.
        with ai_models._cache_lock:
            ai_models._cache.clear()

        portfolio = {"value": 1_000_000, "annual_vol": 18.0,
                     "var_95": 12000, "max_dd": -8.0, "sharpe": 0.9,
                     "top_pct": 22.0}

        calls = []

        def fake_claude(_system, _prompt, max_tokens=800):
            # Tag the response with the call index so we can prove each user
            # got their own fresh Claude invocation, not a shared cache hit.
            marker = f"call_{len(calls) + 1}"
            calls.append(marker)
            return _fake_claude_response(marker)

        with patch.object(ai_models, "_claude_json", side_effect=fake_claude):
            result_user_a, status_a = ai_models.AIRiskSummary.generate(
                portfolio, user_id=1,
            )
            result_user_b, status_b = ai_models.AIRiskSummary.generate(
                portfolio, user_id=2,
            )

        assert status_a == 200 and status_b == 200
        # Both users must trigger their own Claude call — no cross-user hit.
        assert len(calls) == 2, (
            f"Expected 2 distinct Claude calls (one per user), got {len(calls)}. "
            "Cache leaked across user_ids — Pattern 6 regression."
        )
        # Marker proves user B did NOT receive user A's summary.
        assert "USER_MARKER=call_1" in result_user_a["summary_en"]
        assert "USER_MARKER=call_2" in result_user_b["summary_en"]
        assert result_user_a["top_risk_factor"] != result_user_b["top_risk_factor"]

    def test_same_user_second_call_hits_cache(self):
        """Within one user, second call SHOULD hit cache (TTL behavior intact)."""
        from services.ai import models as ai_models

        with ai_models._cache_lock:
            ai_models._cache.clear()

        portfolio = {"value": 500_000, "annual_vol": 15.0,
                     "var_95": 6000, "max_dd": -5.0, "sharpe": 1.1,
                     "top_pct": 18.0}

        calls = []

        def fake_claude(_system, _prompt, max_tokens=800):
            calls.append(1)
            return _fake_claude_response("single")

        with patch.object(ai_models, "_claude_json", side_effect=fake_claude):
            r1, _ = ai_models.AIRiskSummary.generate(portfolio, user_id=42)
            r2, _ = ai_models.AIRiskSummary.generate(portfolio, user_id=42)

        # Only one Claude call should have fired — second was a cache hit.
        assert len(calls) == 1, (
            "Same user repeat call should hit cache, got "
            f"{len(calls)} Claude calls (cache_key may be over-keyed)."
        )
        assert r1["summary_en"] == r2["summary_en"]

    def test_user_id_none_uses_anon_namespace(self):
        """Backward-compat: legacy callers passing no user_id still work,
        but land in an 'anon' cache slot — isolated from real users."""
        from services.ai import models as ai_models

        with ai_models._cache_lock:
            ai_models._cache.clear()

        portfolio = {"value": 250_000, "annual_vol": 12.0,
                     "var_95": 3000, "max_dd": -3.0, "sharpe": 1.4,
                     "top_pct": 10.0}

        with patch.object(ai_models, "_claude_json",
                          return_value=_fake_claude_response("anon")):
            result, status = ai_models.AIRiskSummary.generate(portfolio)

        assert status == 200
        # Verify the anon namespace landed in the cache (not the bare int key).
        with ai_models._cache_lock:
            keys = list(ai_models._cache.keys())
        assert "risk_summary:anon:250000" in keys, (
            f"Expected 'risk_summary:anon:250000' cache key, got: {keys}"
        )
