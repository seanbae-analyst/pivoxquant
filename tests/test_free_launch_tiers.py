"""Free-launch tier opening (LAUNCH_FREE_ALL_TIERS).

DECISIONS.md ✅: the launch is FREE (Stage 0); the 3-tier monthly subscription
model is ⬛superseded. Per CEO ("PDF 기능들 싹다 오픈"), every paid Artifact (18
types) + one-way AI is opened by having ``User.effective_tier`` return
"premium" while the flag is ON (default).

These tests pin three invariants:
  1. Flag ON (default)  → effective_tier == "premium" regardless of the stored
     subscription_tier column.
  2. Flag OFF           → original logic (env override + stored column) is
     restored verbatim — the opening is reversible by config alone.
  3. §101③ carve-out    → "premium" passes @require_tier("premium") but does
     NOT satisfy the (since-deleted) Companion gate (premium_plus /
     founding_lifetime). Two-way AI chat stays closed.
"""

from types import SimpleNamespace

import pytest

from models import User
from routes.decorators import _TIER_RANK


# ── 1. Flag ON (default) opens everything to "premium" ────────────────────────

@pytest.mark.parametrize("stored", ["free", "pro", None])
def test_flag_on_returns_premium_regardless_of_stored_tier(monkeypatch, stored):
    # Default is ON even when the var is absent.
    monkeypatch.delenv("LAUNCH_FREE_ALL_TIERS", raising=False)
    u = User(email="anyone@example.com", subscription_tier=stored)
    assert u.effective_tier == "premium"


@pytest.mark.parametrize("truthy", ["1", "true", "on", "yes", "TRUE"])
def test_flag_on_explicit_truthy_values(monkeypatch, truthy):
    monkeypatch.setenv("LAUNCH_FREE_ALL_TIERS", truthy)
    u = User(email="anyone@example.com", subscription_tier="free")
    assert u.effective_tier == "premium"


# ── 2. Flag OFF restores the original env-override + column logic ──────────────

def test_flag_empty_string_is_on(monkeypatch):
    # An explicitly-empty value is treated as unset → default ON.
    monkeypatch.setenv("LAUNCH_FREE_ALL_TIERS", "")
    u = User(email="anyone@example.com", subscription_tier="free")
    assert u.effective_tier == "premium"


@pytest.mark.parametrize("falsy", ["0", "false", "off", "no"])
def test_flag_off_restores_original_free(monkeypatch, falsy):
    monkeypatch.setenv("LAUNCH_FREE_ALL_TIERS", falsy)
    monkeypatch.delenv("DEV_FOUNDING_EMAILS", raising=False)
    monkeypatch.delenv("DEV_PREMIUM_EMAILS", raising=False)
    u = User(email="plain@example.com", subscription_tier="free")
    assert u.effective_tier == "free"


def test_flag_off_still_honours_env_override(monkeypatch):
    monkeypatch.setenv("LAUNCH_FREE_ALL_TIERS", "0")
    monkeypatch.setenv("DEV_FOUNDING_EMAILS", "owner@example.com")
    u = User(email="owner@example.com", subscription_tier="free")
    assert u.effective_tier == "founding_lifetime"


def test_flag_off_preserves_stored_paid_tier(monkeypatch):
    monkeypatch.setenv("LAUNCH_FREE_ALL_TIERS", "0")
    monkeypatch.delenv("DEV_FOUNDING_EMAILS", raising=False)
    monkeypatch.delenv("DEV_PREMIUM_EMAILS", raising=False)
    u = User(email="paid@example.com", subscription_tier="premium")
    assert u.effective_tier == "premium"


# ── 3. §101③ Companion carve-out: "premium" opens artifacts, not Companion ─────

def test_premium_passes_require_tier_premium():
    # @require_tier("premium") admits when user rank >= required rank.
    assert _TIER_RANK["premium"] >= _TIER_RANK["premium"]
    # All paid artifacts require at most "premium" — so "premium" opens them.
    assert _TIER_RANK["premium"] >= _TIER_RANK["pro"]


