"""10 virtual user profiles for the Artifact-QA render matrix.

Spec source: ``.claude/agents/artifact-qa.md`` §"유저 프로파일 (필수 커버)".
Each profile is paired with all 17 artefact services in
``tests/test_artifact_rendering.py`` to produce a 170-case parametrize
matrix.  The fields here are the *intent declarations*;
``sample_data_factory.seed_virtual_user`` materialises them into actual
``User`` / ``Position`` / ``TradeHistory`` rows.

Determinism
-----------
Every profile pins a ``seed`` so re-running the suite produces byte-
identical SQLite content (and therefore byte-identical rendered PDFs
under WeasyPrint).  The ``period_days`` window combined with the seed
fully determines the synthetic trade history; nothing reads the wall
clock during seeding.

Ticker policy
-------------
Korean tickers are stored on ``Position.ticker`` in KRX form
(``005930.KS``) because the rest of the codebase keys off that suffix
to route currency / quote-source decisions.  The accompanying *display
name* (``삼성전자``) is materialised onto ``TradeHistory.name`` and into
``Position`` rows via the factory so artefact templates can honour the
"종목이름 우선" rule (``feedback_ticker_display.md``) without re-resolving
the ticker.

No external API calls happen at fixture-load time — the only data here
is the static profile registry.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


AssetMix = Literal["US", "KR", "US+KR", "US+KR+EU", "US+KR+JP+EU"]
Tier     = Literal["free", "pro", "premium", "founding_lifetime"]


@dataclass(frozen=True)
class VirtualUserProfile:
    """Static description of one synthetic user.

    Attributes
    ----------
    profile_id     : 1-based slot in the QA matrix.
    label          : short human-readable name (matches the QA spec table).
    email          : seeded login — must be unique across the registry.
    tier           : Stripe-equivalent subscription tier.
    portfolio_size : target number of distinct ``Position`` rows.
    asset_mix      : which markets to draw tickers from.
    period_days    : age of the oldest synthetic trade, in days.
    trade_count    : optional override for total ``TradeHistory`` rows;
                     when ``None`` the factory derives it from
                     ``portfolio_size`` (≈ 2x).
    has_dividends  : seed dividend-style trades (``action='DIV'``).
    capital_usd    : initial cash for the User row.
    capital_krw    : initial KRW cash for the User row.
    seed           : RNG seed; must be unique per profile.
    flags          : free-form tags consumed by individual artefact tests
                     for edge-case branching (e.g. "empty_state",
                     "high_load", "concentration", "tier_boundary").
    """
    profile_id:     int
    label:          str
    email:          str
    tier:           Tier
    portfolio_size: int
    asset_mix:      AssetMix
    period_days:    int
    trade_count:    int | None
    has_dividends:  bool
    capital_usd:    float
    capital_krw:    float
    seed:           int
    flags:          tuple[str, ...] = field(default_factory=tuple)


# ── Registry — order matches artifact-qa.md:96-107 exactly ────────────────────

USER_PROFILES: tuple[VirtualUserProfile, ...] = (
    VirtualUserProfile(
        profile_id=1, label="beginner_us",
        email="vqa01-beginner-us@artifact-qa.local",
        tier="free", portfolio_size=4, asset_mix="US",
        period_days=30, trade_count=6, has_dividends=False,
        capital_usd=2_500.0, capital_krw=0.0, seed=101,
        flags=("loss_period",),
    ),
    VirtualUserProfile(
        profile_id=2, label="kr_only",
        email="vqa02-kr-only@artifact-qa.local",
        tier="pro", portfolio_size=7, asset_mix="KR",
        period_days=90, trade_count=14, has_dividends=False,
        capital_usd=0.0, capital_krw=20_000_000.0, seed=202,
        flags=("hangul_names", "krw_only"),
    ),
    VirtualUserProfile(
        profile_id=3, label="mixed_intermediate",
        email="vqa03-mixed@artifact-qa.local",
        tier="pro", portfolio_size=15, asset_mix="US+KR",
        period_days=180, trade_count=30, has_dividends=True,
        capital_usd=8_000.0, capital_krw=5_000_000.0, seed=303,
        flags=("mixed_currency",),
    ),
    VirtualUserProfile(
        profile_id=4, label="concentrated",
        email="vqa04-concentrated@artifact-qa.local",
        tier="free", portfolio_size=2, asset_mix="US",
        period_days=7, trade_count=3, has_dividends=False,
        capital_usd=1_000.0, capital_krw=0.0, seed=404,
        flags=("single_position", "min_data"),
    ),
    VirtualUserProfile(
        profile_id=5, label="hyper_diversified",
        email="vqa05-diversified@artifact-qa.local",
        tier="premium", portfolio_size=75, asset_mix="US+KR+EU",
        period_days=365, trade_count=200, has_dividends=True,
        capital_usd=120_000.0, capital_krw=30_000_000.0, seed=505,
        flags=("high_load", "page_break_stress"),
    ),
    VirtualUserProfile(
        profile_id=6, label="dividend_etf",
        email="vqa06-dividend@artifact-qa.local",
        tier="premium", portfolio_size=25, asset_mix="US",
        period_days=730, trade_count=80, has_dividends=True,
        capital_usd=50_000.0, capital_krw=0.0, seed=606,
        flags=("dividend_heavy", "etf_only"),
    ),
    VirtualUserProfile(
        profile_id=7, label="day_trader",
        email="vqa07-daytrader@artifact-qa.local",
        tier="pro", portfolio_size=5, asset_mix="US",
        period_days=365, trade_count=250, has_dividends=False,
        capital_usd=15_000.0, capital_krw=0.0, seed=707,
        flags=("high_turnover", "self_audit_stress"),
    ),
    VirtualUserProfile(
        profile_id=8, label="new_signup",
        email="vqa08-newuser@artifact-qa.local",
        tier="free", portfolio_size=0, asset_mix="US",
        period_days=1, trade_count=0, has_dividends=False,
        capital_usd=0.0, capital_krw=0.0, seed=808,
        flags=("empty_state", "fallback_ui"),
    ),
    VirtualUserProfile(
        profile_id=9, label="cancellation_edge",
        email="vqa09-cancel-edge@artifact-qa.local",
        tier="pro", portfolio_size=10, asset_mix="US",
        period_days=90, trade_count=18, has_dividends=False,
        capital_usd=5_000.0, capital_krw=0.0, seed=909,
        flags=("tier_boundary", "near_cancel"),
    ),
    VirtualUserProfile(
        profile_id=10, label="international",
        email="vqa10-international@artifact-qa.local",
        tier="premium", portfolio_size=30, asset_mix="US+KR+JP+EU",
        period_days=1825, trade_count=120, has_dividends=True,
        capital_usd=75_000.0, capital_krw=20_000_000.0, seed=1010,
        flags=("multi_currency", "fx_complex", "tax_complex"),
    ),
)


def profile_by_label(label: str) -> VirtualUserProfile:
    """Lookup helper for tests that target a single named profile."""
    for p in USER_PROFILES:
        if p.label == label:
            return p
    raise KeyError(f"Unknown virtual-user profile: {label!r}")


def profile_ids() -> list[str]:
    """pytest ``ids`` callable — uses the human label, not the dataclass repr."""
    return [p.label for p in USER_PROFILES]
