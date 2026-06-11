"""
tests/test_risk_board_force_fire_tiers.py — VIX force-fire fan-out tier set
==========================================================================
FIX 2 (2026-05-22): the manual Risk Board trigger's force-fire (`vix_spike`)
path used a hardcoded literal `subscription_tier.in_(["premium", "elite"])`:

  * "elite" is NOT a real tier (routes/decorators._TIER_RANK) → matched nobody.
  * premium_plus (rank 3) + founding_lifetime (rank 4) — the highest-paying
    cohorts incl. the owner — were excluded → they missed the force-fired deck.

The fix routes selection through the canonical shared set in
`services.artifacts._tiers`, the same set `RiskBoardService.run_monthly()`
filters on. 2026-06-10 (B2 tier alignment): Risk Board is sold as a PRO
artifact on the pricing page, so both the cron service and this force-fire
fan-out moved to PAID_TIERS_PRO_AND_UP — the test now asserts pro IS
included, free still excluded, and the ghost "elite" literal stays gone.
"""
from unittest.mock import patch

import pytest


@pytest.fixture
def admin_secret(monkeypatch):
    # `_check_cron_admin_secret` resolves `expected = ARTIFACT_TRIGGER_SECRET or
    # DEV_LOGIN_SECRET`. Pin BOTH so a stray ARTIFACT_TRIGGER_SECRET from a real
    # .env can't shadow our value.
    monkeypatch.setenv("ARTIFACT_TRIGGER_SECRET", "test-admin-secret")
    monkeypatch.setenv("DEV_LOGIN_SECRET", "test-admin-secret")
    return "test-admin-secret"


def _make_tiered_user(app, make_user, tier):
    return make_user(email=f"force-{tier}@test.com", tier=tier)


class TestVixForceFireTierSelection:
    def test_fans_out_to_premium_and_up_only(self, raw_client, app, make_user, admin_secret):
        from services.artifacts._tiers import PAID_TIERS_PRO_AND_UP

        # Create one user per tier (incl. the previously-excluded top tiers).
        for tier in ("free", "pro", "premium", "premium_plus", "founding_lifetime"):
            _make_tiered_user(app, make_user, tier)

        called_for_tiers = []

        def _fake_run_for_user(self, u, trigger=None):
            called_for_tiers.append(u.subscription_tier)
            return {"ok": True}  # non-None → counts as notified

        with patch(
            "services.artifacts.risk_board_service.RiskBoardService.run_for_user",
            _fake_run_for_user,
        ):
            r = raw_client.post(
                "/api/artifacts/risk-board/trigger",
                json={"trigger": "vix_spike"},
                headers={"X-Admin-Secret": admin_secret},
            )

        assert r.status_code == 200, (r.status_code, r.get_json())
        summary = r.get_json()["summary"]
        assert summary["trigger"] == "vix_spike"

        selected = set(called_for_tiers)
        # Top-paying cohorts are now included (the bug being fixed).
        assert "premium_plus" in selected
        assert "founding_lifetime" in selected
        assert "premium" in selected
        # B2 tier alignment (2026-06-10): Risk Board is a PRO artifact on the
        # pricing page — pro is now INCLUDED in the fan-out.
        assert "pro" in selected
        # Non-paying tier still excluded.
        assert "free" not in selected
        # Every selected tier belongs to the canonical shared set.
        assert selected <= set(PAID_TIERS_PRO_AND_UP)
        assert summary["attempted"] == len(called_for_tiers)
        assert summary["notified"] == len(called_for_tiers)

    def test_elite_ghost_literal_removed_from_source(self):
        """Guard against the ghost-tier literal regressing back into the route."""
        import inspect
        from routes import artifacts as artifacts_mod

        src = inspect.getsource(artifacts_mod.risk_board_trigger)
        # Inspect only executable code lines (drop comments) so the explanatory
        # comment naming the old literal doesn't trip the guard.
        code_lines = [
            ln for ln in src.splitlines()
            if not ln.lstrip().startswith("#")
        ]
        code = "\n".join(code_lines)
        assert '"elite"' not in code and "'elite'" not in code, (
            "ghost-tier literal 'elite' must not reappear in the force-fire path"
        )
        # B2 alignment (2026-06-10): Risk Board is a PRO artifact, so the
        # force-fire fan-out uses the PRO_AND_UP canonical set.
        assert "PAID_TIERS_PRO_AND_UP" in code
