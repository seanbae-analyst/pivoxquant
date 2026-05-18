"""Deterministic User + Position + TradeHistory factory for Artifact-QA.

Given a ``VirtualUserProfile`` (see ``virtual_users.py``) this module
materialises a fully isolated database row set so the artefact services
can be exercised end-to-end (``generate_for_user`` → ``render_html`` →
``render_pdf``) against realistic data — with **zero** external API
calls.

Determinism
-----------
Every seeded run uses ``random.Random(profile.seed)``: a per-profile
PRNG instance.  We deliberately avoid ``Faker`` (not in
requirements.txt) and the module-level ``random`` (would couple
re-orderable tests).  The same ``seed`` always produces the same
ticker selection, share counts, and trade timestamps.

Ticker universe
---------------
Tickers are drawn from a curated KRX-listed (KR) / NYSE+NASDAQ-listed
(US) / Xetra/LSE (EU) / TSE (JP) set.  No yfinance, pykrx, or other
unofficial source is touched — these are static identifier lists only
(``feedback_official_data_only.md``).  Korean tickers carry their
hangul display name on ``TradeHistory.name`` per
``feedback_ticker_display.md``.

Currency / FX
-------------
``Position.buy_fx_rate`` is seeded with a per-currency anchor
(USD=1.0, KRW=1350.0, EUR=0.92, JPY=155.0) plus minor jitter; this
mirrors how the production add-position flow stores the FX at the
moment of purchase.

Idempotency
-----------
``seed_virtual_user`` deletes any pre-existing rows for the profile's
email before re-seeding, so calling it twice in one test process is
safe (the conftest ``_reset_db`` autouse already truncates between
tests, but we belt-and-brace against fixture mis-use).
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from extensions import db
from models import Position, TradeHistory, User

from .virtual_users import VirtualUserProfile


# ── Curated, license-clean ticker universe ────────────────────────────────────
# Static identifier lists ONLY — no quote data is fetched.
# (ticker, display_name, asset_class, currency)

_US_EQUITIES: tuple[tuple[str, str, str, str], ...] = (
    ("AAPL",  "Apple Inc.",                "EQUITY", "USD"),
    ("MSFT",  "Microsoft Corp.",           "EQUITY", "USD"),
    ("NVDA",  "NVIDIA Corp.",              "EQUITY", "USD"),
    ("GOOGL", "Alphabet Inc.",             "EQUITY", "USD"),
    ("META",  "Meta Platforms Inc.",       "EQUITY", "USD"),
    ("TSLA",  "Tesla Inc.",                "EQUITY", "USD"),
    ("AMZN",  "Amazon.com Inc.",           "EQUITY", "USD"),
    ("JPM",   "JPMorgan Chase & Co.",      "EQUITY", "USD"),
    ("V",     "Visa Inc.",                 "EQUITY", "USD"),
    ("UNH",   "UnitedHealth Group Inc.",   "EQUITY", "USD"),
)

_US_ETFS: tuple[tuple[str, str, str, str], ...] = (
    ("VOO",  "Vanguard S&P 500 ETF",       "ETF", "USD"),
    ("SCHD", "Schwab US Dividend Equity",  "ETF", "USD"),
    ("VTI",  "Vanguard Total Stock Market","ETF", "USD"),
    ("QQQ",  "Invesco QQQ Trust",          "ETF", "USD"),
    ("DGRO", "iShares Core Dividend Growth","ETF","USD"),
    ("HDV",  "iShares Core High Dividend", "ETF", "USD"),
    ("VYM",  "Vanguard High Dividend Yield","ETF","USD"),
    ("SPYD", "SPDR S&P 500 High Dividend", "ETF", "USD"),
)

_KR_EQUITIES: tuple[tuple[str, str, str, str], ...] = (
    ("005930.KS", "삼성전자",          "EQUITY", "KRW"),
    ("000660.KS", "SK하이닉스",         "EQUITY", "KRW"),
    ("035720.KS", "카카오",            "EQUITY", "KRW"),
    ("035420.KS", "NAVER",             "EQUITY", "KRW"),
    ("373220.KS", "LG에너지솔루션",     "EQUITY", "KRW"),
    ("207940.KS", "삼성바이오로직스",    "EQUITY", "KRW"),
    ("005380.KS", "현대차",            "EQUITY", "KRW"),
    ("068270.KS", "셀트리온",           "EQUITY", "KRW"),
    ("105560.KS", "KB금융",            "EQUITY", "KRW"),
    ("051910.KS", "LG화학",            "EQUITY", "KRW"),
)

_EU_EQUITIES: tuple[tuple[str, str, str, str], ...] = (
    ("ASML.AS",  "ASML Holding NV",          "EQUITY", "EUR"),
    ("SAP.DE",   "SAP SE",                   "EQUITY", "EUR"),
    ("MC.PA",    "LVMH Moet Hennessy",       "EQUITY", "EUR"),
    ("NESN.SW",  "Nestle SA",                "EQUITY", "EUR"),
    ("SIE.DE",   "Siemens AG",               "EQUITY", "EUR"),
)

_JP_EQUITIES: tuple[tuple[str, str, str, str], ...] = (
    ("7203.T", "Toyota Motor Corp.",         "EQUITY", "JPY"),
    ("6758.T", "Sony Group Corp.",           "EQUITY", "JPY"),
    ("9984.T", "SoftBank Group Corp.",       "EQUITY", "JPY"),
    ("8035.T", "Tokyo Electron Ltd.",        "EQUITY", "JPY"),
)


_FX_ANCHOR = {"USD": 1.0, "KRW": 1_350.0, "EUR": 0.92, "JPY": 155.0}


def _universe_for(mix: str, *, dividend_heavy: bool) -> list[tuple[str, str, str, str]]:
    """Return the candidate ticker pool for a given asset mix string."""
    if dividend_heavy:
        # Profile 6: pure dividend ETF basket.
        return list(_US_ETFS)
    pool: list[tuple[str, str, str, str]] = []
    if "US" in mix:
        pool.extend(_US_EQUITIES)
        pool.extend(_US_ETFS)
    if "KR" in mix:
        pool.extend(_KR_EQUITIES)
    if "EU" in mix:
        pool.extend(_EU_EQUITIES)
    if "JP" in mix:
        pool.extend(_JP_EQUITIES)
    if not pool:
        # Profile 8 ("new_signup") has mix="US" + portfolio_size=0; the
        # universe is unused but must be non-empty so .sample() can no-op.
        pool = list(_US_EQUITIES)
    return pool


# ── Seed price model (no live quotes) ─────────────────────────────────────────

def _anchor_price(currency: str, rng: random.Random) -> float:
    """Synthetic per-unit price in the position's listing currency.

    Anchored to plausible real-world magnitudes so artefact templates
    don't divide-by-zero on aggregated totals.  Not a live quote.
    """
    if currency == "KRW":
        return round(rng.uniform(40_000.0, 250_000.0), -1)
    if currency == "JPY":
        return round(rng.uniform(2_000.0, 20_000.0), -1)
    if currency == "EUR":
        return round(rng.uniform(80.0, 800.0), 2)
    return round(rng.uniform(50.0, 600.0), 2)


def _fx_for(currency: str, rng: random.Random) -> float:
    base = _FX_ANCHOR.get(currency, 1.0)
    # ±2% jitter so positions seeded in the same run don't share an
    # identical buy_fx_rate (kills the trivial PNG hash collisions in
    # visual-regression snapshotting).
    return round(base * (1.0 + rng.uniform(-0.02, 0.02)), 4)


# ── Public factory ────────────────────────────────────────────────────────────

@dataclass
class SeededUser:
    """Return value of ``seed_virtual_user`` — handy alias for callers."""
    user_id: int
    email:   str
    profile: VirtualUserProfile
    position_count: int
    trade_count:    int


def _delete_existing(email: str) -> None:
    existing = User.query.filter_by(email=email).one_or_none()
    if existing is None:
        return
    # Cascade=delete-orphan on User.positions handles Position; the trade
    # rows are cascaded by ondelete='CASCADE' at the DB level.
    db.session.delete(existing)
    db.session.commit()


def seed_virtual_user(profile: VirtualUserProfile) -> SeededUser:
    """Materialise a profile into the active SQLAlchemy session.

    Caller must be inside a Flask ``app_context``.  Commits before
    returning so subsequent ``Service().generate_for_user(uid)`` calls
    see the rows.
    """
    _delete_existing(profile.email)

    rng = random.Random(profile.seed)

    user = User(
        email=profile.email,
        name=f"VQA Profile {profile.profile_id:02d} - {profile.label}",
        oauth_provider=None,
        available_capital=profile.capital_usd,
        available_capital_krw=profile.capital_krw,
        risk_profile="balanced",
        subscription_tier=profile.tier,
        onboarding_completed=True,
    )
    user.set_pw(f"vqa-pw-{profile.seed}")
    db.session.add(user)
    db.session.flush()  # populate user.id without ending the transaction

    # ── Positions ────────────────────────────────────────────────────────────
    universe = _universe_for(profile.asset_mix, dividend_heavy="dividend_heavy" in profile.flags)
    take = min(profile.portfolio_size, len(universe))
    chosen = rng.sample(universe, take) if take > 0 else []

    seeded_positions: list[Position] = []
    for (ticker, _name, _cls, currency) in chosen:
        anchor = _anchor_price(currency, rng)
        # Concentration profile (#4): collapse all share weight into the
        # first slot so the artefact services exercise the
        # "single_position" branch.
        if "single_position" in profile.flags:
            shares = rng.uniform(20.0, 100.0) if len(seeded_positions) == 0 else rng.uniform(0.1, 1.0)
        else:
            shares = rng.uniform(1.0, 50.0) if currency != "KRW" else rng.uniform(5.0, 200.0)
        pos = Position(
            user_id=user.id,
            ticker=ticker,
            shares=round(shares, 4),
            avg_cost=anchor,
            buy_fx_rate=_fx_for(currency, rng),
        )
        db.session.add(pos)
        seeded_positions.append(pos)

    # ── Trade history ────────────────────────────────────────────────────────
    trade_total = profile.trade_count if profile.trade_count is not None else max(profile.portfolio_size * 2, 0)
    seeded_trades = 0
    if trade_total > 0 and seeded_positions:
        # Spread trades evenly across the period_days window.
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        for i in range(trade_total):
            (ticker, name, _cls, currency) = rng.choice(chosen)
            # Bias toward BUY; SELL ratio ~30%; if profile has dividends,
            # carve out 20% as DIV entries (artefact services accept
            # the row even though the dispatcher in models.py only
            # documents BUY/SELL — DIV is rendered by the dividend
            # artefact path).
            roll = rng.random()
            if profile.has_dividends and roll < 0.20:
                action = "DIV"
            elif roll < 0.55:
                action = "BUY"
            else:
                action = "SELL"
            day_offset = rng.randint(0, max(profile.period_days - 1, 0))
            traded_at = now_naive - timedelta(days=day_offset,
                                              hours=rng.randint(0, 23),
                                              minutes=rng.randint(0, 59))
            price = _anchor_price(currency, rng)
            shares = round(rng.uniform(0.5, 10.0), 4)
            total = round(price * shares, 4)
            pnl = round(rng.uniform(-300.0, 500.0), 2) if action == "SELL" else 0.0
            pnl_pct = round(rng.uniform(-25.0, 35.0), 2) if action == "SELL" else 0.0
            trade = TradeHistory(
                user_id=user.id,
                ticker=ticker,
                name=name,
                action=action,
                shares=shares,
                price_per_share=price,
                total_value=total,
                pnl=pnl,
                pnl_pct=pnl_pct,
                currency=currency,
                traded_at=traded_at,
            )
            db.session.add(trade)
            seeded_trades += 1
            # Periodic flush to keep the SQLAlchemy session memory bounded
            # for the high_load profile (200 trades + 75 positions).
            if i % 50 == 49:
                db.session.flush()

    db.session.commit()

    return SeededUser(
        user_id=user.id,
        email=user.email,
        profile=profile,
        position_count=len(seeded_positions),
        trade_count=seeded_trades,
    )


__all__: list[str] = ["seed_virtual_user", "SeededUser"]
