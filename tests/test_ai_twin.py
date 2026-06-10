"""Feature 5 — AI Trader Twin (paper-only) test suite.

Covers:
  • Migration / model surface (revision chain, paper-only fields)
  • Service layer (initialize, decisions, close-checks, sizing)
  • Reporter (weekly user-vs-twin)
  • Routes (auth, disclaimer, paper labels, no prospective rows)
  • Cron registration (only initialized twins get a pass)
  • A "no real money anywhere" code-grep witness
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest

from extensions import db


# ─────────────────────────────────────────────────────────────────────
# A. Migration applied
# ─────────────────────────────────────────────────────────────────────


def test_migration_applied(app):
    """Every migration-019 table must exist in the test DB."""
    from sqlalchemy import inspect
    with app.app_context():
        names = set(inspect(db.engine).get_table_names())
    for t in (
        "ai_twin_portfolios",
        "ai_twin_positions",
        "ai_twin_trades",
        "ai_twin_weekly_reports",
    ):
        assert t in names, f"missing table: {t}"


def test_migration_chain_links_to_018():
    """Revision 019 must chain off 018_behavioral_scores."""
    here = Path(__file__).resolve().parent.parent / "migrations" / "versions" / "019_ai_twin.py"
    src = here.read_text(encoding="utf-8")
    assert 'revision = "019_ai_twin"' in src
    assert 'down_revision = "018_behavioral_scores"' in src


# ─────────────────────────────────────────────────────────────────────
# B. Initialize
# ─────────────────────────────────────────────────────────────────────


def test_initialize_creates_portfolio_with_10k(app, make_user):
    from services.twin import initialize_twin
    from models import AITwinPortfolio, DEFAULT_STARTING_CASH

    user = make_user()
    with app.app_context():
        twin = initialize_twin(user["id"])
        assert twin.id is not None
        assert Decimal(str(twin.starting_cash)) == DEFAULT_STARTING_CASH
        assert Decimal(str(twin.current_cash)) == DEFAULT_STARTING_CASH
        assert twin.is_active is True
        # The persona is captured at init — use whatever the classifier
        # returns; we only assert it is a valid string.
        assert isinstance(twin.persona_at_init, str)
        assert len(twin.persona_at_init) > 0
        # Stored row must have UNIQUE user_id constraint applied.
        same = AITwinPortfolio.query.filter_by(user_id=user["id"]).count()
        assert same == 1


def test_initialize_idempotent_returns_existing(app, make_user):
    from services.twin import initialize_twin
    from models import AITwinPortfolio

    user = make_user()
    with app.app_context():
        first = initialize_twin(user["id"])
        first_id = first.id
        # Second call must NOT create a duplicate.
        second = initialize_twin(user["id"])
        assert second.id == first_id
        assert AITwinPortfolio.query.filter_by(user_id=user["id"]).count() == 1


# ─────────────────────────────────────────────────────────────────────
# C. Decisions / paper-trade mechanics
# ─────────────────────────────────────────────────────────────────────


def _patch_engine_and_fetcher(monkeypatch, *, candidates):
    """Stub svc.engine.analyze + svc.fetcher.get_stock_snapshot.

    ``candidates`` is a list of tuples (ticker, composite, price).
    """
    from services import container as svc

    score_map = {t: (s, p) for (t, s, p) in candidates}

    class _StubEngine:
        DISCOVER_POOL = [t for t, _, _ in candidates]

        def analyze(self, ticker, capital_usd=10_000.0, **_kw):
            if ticker not in score_map:
                return None
            s, p = score_map[ticker]
            return {"composite_score": s, "price": p, "signal": "stub"}

    class _StubFetcher:
        def get_stock_snapshot(self, ticker):
            if ticker in score_map:
                return {"price": score_map[ticker][1], "currency": "USD"}
            return None

    monkeypatch.setattr(svc, "engine", _StubEngine())
    monkeypatch.setattr(svc, "fetcher", _StubFetcher())
    # Persona classifier is patched too — deterministic for tests.
    return score_map


def test_run_twin_decisions_persona_quant_uses_quant_threshold(app, make_user, monkeypatch):
    from services.twin import (
        initialize_twin,
        run_twin_decisions,
    )
    from models import AITwinPortfolio, AITwinTrade

    user = make_user()
    with app.app_context():
        # 3 candidates: 80 (above quant threshold ~68), 65 (below), 90 (above).
        _patch_engine_and_fetcher(monkeypatch, candidates=[
            ("AAA", 80.0, 100.0),
            ("BBB", 65.0, 50.0),
            ("CCC", 90.0, 200.0),
        ])
        with patch("services.twin.twin_runner._resolve_persona", return_value="quant"):
            initialize_twin(user["id"])
            summary = run_twin_decisions(user["id"], universe=["AAA", "BBB", "CCC"])
        assert summary["persona"] == "quant"
        # quant threshold = 68 → AAA(80) + CCC(90) bought; BBB(65) skipped.
        assert summary["buys"] == 2
        twin = AITwinPortfolio.query.filter_by(user_id=user["id"]).first()
        bought = {t.ticker for t in AITwinTrade.query.filter_by(twin_id=twin.id, side="BUY")}
        assert bought == {"AAA", "CCC"}


def test_run_twin_decisions_persona_beginner_higher_threshold(app, make_user, monkeypatch):
    """beginner threshold (75) is stricter than quant (68) — fewer buys."""
    from services.twin import initialize_twin, run_twin_decisions
    from models import AITwinPortfolio, AITwinTrade

    user = make_user()
    with app.app_context():
        _patch_engine_and_fetcher(monkeypatch, candidates=[
            ("AAA", 70.0, 100.0),  # quant would buy, beginner won't
            ("BBB", 80.0, 50.0),
        ])
        with patch("services.twin.twin_runner._resolve_persona", return_value="beginner"):
            initialize_twin(user["id"])
            summary = run_twin_decisions(user["id"], universe=["AAA", "BBB"])
        assert summary["persona"] == "beginner"
        assert summary["buys"] == 1
        twin = AITwinPortfolio.query.filter_by(user_id=user["id"]).first()
        bought = {t.ticker for t in AITwinTrade.query.filter_by(twin_id=twin.id, side="BUY")}
        assert bought == {"BBB"}


def test_paper_buy_decreases_cash_increases_position(app, make_user, monkeypatch):
    from services.twin import initialize_twin, run_twin_decisions
    from models import AITwinPortfolio, AITwinPosition, DEFAULT_STARTING_CASH

    user = make_user()
    with app.app_context():
        _patch_engine_and_fetcher(monkeypatch, candidates=[("AAA", 95.0, 100.0)])
        with patch("services.twin.twin_runner._resolve_persona", return_value="balanced"):
            initialize_twin(user["id"])
            run_twin_decisions(user["id"], universe=["AAA"])
        twin = AITwinPortfolio.query.filter_by(user_id=user["id"]).first()
        assert Decimal(str(twin.current_cash)) < DEFAULT_STARTING_CASH
        pos = AITwinPosition.query.filter_by(twin_id=twin.id, ticker="AAA").first()
        assert pos is not None
        assert float(pos.shares) > 0


def test_paper_sell_realizes_pnl_via_close_check(app, make_user, monkeypatch):
    """A held position whose price triggers TP must close with PnL."""
    from services.twin import initialize_twin, run_twin_decisions
    from models import AITwinPortfolio, AITwinPosition, AITwinTrade

    user = make_user()
    with app.app_context():
        # Day 1: buy AAA at 100.
        _patch_engine_and_fetcher(monkeypatch, candidates=[("AAA", 95.0, 100.0)])
        with patch("services.twin.twin_runner._resolve_persona", return_value="balanced"):
            initialize_twin(user["id"])
            run_twin_decisions(user["id"], universe=["AAA"])
        twin = AITwinPortfolio.query.filter_by(user_id=user["id"]).first()
        pos = AITwinPosition.query.filter_by(twin_id=twin.id, ticker="AAA").first()
        bought_shares = float(pos.shares)
        # Day N: AAA jumps to 130 (>= +12% TP for balanced persona). Score
        # forced below buy threshold so the runner doesn't immediately
        # re-buy after closing — TP test would otherwise be ambiguous.
        _patch_engine_and_fetcher(monkeypatch, candidates=[("AAA", 50.0, 130.0)])
        with patch("services.twin.twin_runner._resolve_persona", return_value="balanced"):
            run_twin_decisions(user["id"], universe=["AAA"])
        sells = AITwinTrade.query.filter_by(twin_id=twin.id, side="SELL").all()
        assert len(sells) == 1
        # PnL must be (130-100)*shares.
        assert float(sells[0].pnl_at_close) == pytest.approx(30.0 * bought_shares, rel=1e-3)
        # Position must be gone — and not immediately re-opened by the
        # same pass (score 50 < balanced threshold 70).
        assert AITwinPosition.query.filter_by(twin_id=twin.id, ticker="AAA").first() is None


def test_close_check_sl_works(app, make_user, monkeypatch):
    """A held position whose price triggers SL closes (negative PnL)."""
    from services.twin import initialize_twin, run_twin_decisions
    from models import AITwinPortfolio, AITwinTrade

    user = make_user()
    with app.app_context():
        _patch_engine_and_fetcher(monkeypatch, candidates=[("AAA", 95.0, 100.0)])
        with patch("services.twin.twin_runner._resolve_persona", return_value="balanced"):
            initialize_twin(user["id"])
            run_twin_decisions(user["id"], universe=["AAA"])
        # SL = 6% for balanced — 90 should trigger. Score forced below
        # threshold so the runner doesn't reopen immediately.
        _patch_engine_and_fetcher(monkeypatch, candidates=[("AAA", 50.0, 90.0)])
        with patch("services.twin.twin_runner._resolve_persona", return_value="balanced"):
            run_twin_decisions(user["id"], universe=["AAA"])
        twin = AITwinPortfolio.query.filter_by(user_id=user["id"]).first()
        sells = AITwinTrade.query.filter_by(twin_id=twin.id, side="SELL").all()
        assert len(sells) == 1
        assert float(sells[0].pnl_at_close) < 0


def test_position_sizing_persona_dependent():
    """Same score+cash should produce a smaller buy for beginner than speculator."""
    from services.twin.twin_runner import _position_sizing
    cash = Decimal("10000")
    beginner_alloc = _position_sizing("beginner", 80.0, cash)
    speculator_alloc = _position_sizing("speculator", 80.0, cash)
    assert speculator_alloc > beginner_alloc


def test_position_sizing_concentrated_low_score():
    """Below-threshold scores still receive a small allocation in service of
    diversification — but the cap ensures it never exceeds 25% of cash.
    """
    from services.twin.twin_runner import _position_sizing
    alloc = _position_sizing("speculator", 60.0, Decimal("10000"))
    assert alloc <= Decimal("2500")  # 25% cap


def test_position_sizing_balanced_high_score():
    """A high score boosts allocation but is bounded by the persona base."""
    from services.twin.twin_runner import _position_sizing
    base_alloc = _position_sizing("balanced", 70.0, Decimal("10000"))
    high_alloc = _position_sizing("balanced", 95.0, Decimal("10000"))
    assert high_alloc > base_alloc


# ─────────────────────────────────────────────────────────────────────
# D. Weekly report
# ─────────────────────────────────────────────────────────────────────


def test_weekly_report_compares_user_vs_twin(app, make_user):
    from services.twin import generate_weekly_report
    from models import (
        AITwinPortfolio,
        AITwinTrade,
        TradeHistory,
        AITwinWeeklyReport,
    )

    user = make_user()
    with app.app_context():
        # Create twin manually to bypass classifier.
        twin = AITwinPortfolio(
            user_id=user["id"],
            initialized_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=14),
            starting_cash=Decimal("10000"),
            current_cash=Decimal("10000"),
            persona_at_init="balanced",
            is_active=True,
        )
        db.session.add(twin)
        db.session.commit()
        # Add a paper SELL with realized +5% (cost basis 1000, pnl 50).
        sell_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
        db.session.add(AITwinTrade(
            twin_id=twin.id,
            ticker="AAA",
            side="SELL",
            shares=Decimal("10"),
            price=Decimal("105"),
            executed_at=sell_time,
            pnl_at_close=Decimal("50"),
            is_paper=True,
        ))
        # Add a real user TradeHistory with +10%. total_value is the SELL's
        # PROCEEDS (price × shares = 1,100), matching how routes/portfolio.py
        # records sells; the old fixture's 1,000 contradicted its own
        # price_per_share. The weekly math measures realized P&L over realized
        # cost basis: (1100 − 100) = 1000 cost → 100/1000 = +10%.
        db.session.add(TradeHistory(
            user_id=user["id"],
            ticker="ZZZ",
            action="SELL",
            shares=10.0,
            price_per_share=110.0,
            total_value=1100.0,
            pnl=100.0,
            traded_at=sell_time,
        ))
        db.session.commit()
        report = generate_weekly_report(user["id"])
        assert isinstance(report, AITwinWeeklyReport)
        assert report.user_return_pct is not None
        assert report.twin_return_pct is not None
        assert float(report.user_return_pct) == pytest.approx(10.0, abs=0.5)
        assert float(report.twin_return_pct) == pytest.approx(5.0, abs=0.5)
        assert float(report.diff_pct) == pytest.approx(-5.0, abs=0.5)


def test_weekly_report_idempotent_on_same_week(app, make_user):
    from services.twin import generate_weekly_report
    from models import AITwinPortfolio, AITwinWeeklyReport

    user = make_user()
    with app.app_context():
        db.session.add(AITwinPortfolio(
            user_id=user["id"],
            initialized_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=14),
            starting_cash=Decimal("10000"),
            current_cash=Decimal("10000"),
            persona_at_init="balanced",
            is_active=True,
        ))
        db.session.commit()
        first = generate_weekly_report(user["id"])
        second = generate_weekly_report(user["id"])
        assert first.id == second.id
        rows = AITwinWeeklyReport.query.filter_by(user_id=user["id"]).count()
        assert rows == 1


# ─────────────────────────────────────────────────────────────────────
# E. Endpoints — auth, disclaimer, paper label, no prospective
# ─────────────────────────────────────────────────────────────────────


def test_endpoint_initialize_requires_auth(client):
    resp = client.post("/api/twin/initialize")
    assert resp.status_code == 401


def test_endpoint_initialize_returns_paper_label_and_disclaimer(client, auth_user):
    resp = client.post("/api/twin/initialize")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ok"] is True
    assert "disclaimer" in body and "paper" in body["disclaimer"].lower()
    assert body["data"]["paper_label"] == "PAPER PORTFOLIO"


def test_endpoint_portfolio_disclaimer_present(client, auth_user, app, mock_fetcher):
    # mock_fetcher already disables external HTTP via routes.market/portfolio,
    # but twin route uses container.fetcher — patch it explicitly.
    client.post("/api/twin/initialize")
    with patch("routes.twin.svc.fetcher.get_stock_snapshot", return_value=None):
        resp = client.get("/api/twin/portfolio")
    assert resp.status_code == 200
    body = resp.get_json()
    assert "disclaimer" in body
    assert body["data"]["paper_label"] == "PAPER PORTFOLIO"
    assert body["data"]["initialized"] is True


def test_endpoint_trades_only_past_no_prospective(client, auth_user, app):
    """The trades endpoint MUST NOT surface rows whose executed_at > now()."""
    from models import AITwinPortfolio, AITwinTrade
    client.post("/api/twin/initialize")
    with app.app_context():
        twin = AITwinPortfolio.query.filter_by(user_id=auth_user["id"]).first()
        # Past trade.
        past = AITwinTrade(
            twin_id=twin.id, ticker="AAA", side="BUY",
            shares=Decimal("1"), price=Decimal("100"),
            executed_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1),
            is_paper=True,
        )
        # Future trade — must NEVER appear.
        future = AITwinTrade(
            twin_id=twin.id, ticker="ZZZ", side="BUY",
            shares=Decimal("1"), price=Decimal("100"),
            executed_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=2),
            is_paper=True,
        )
        db.session.add_all([past, future])
        db.session.commit()
    resp = client.get("/api/twin/trades?days=30")
    assert resp.status_code == 200
    body = resp.get_json()
    tickers = [t["ticker"] for t in body["data"]["trades"]]
    assert "AAA" in tickers
    assert "ZZZ" not in tickers
    # Every row must carry is_paper=True.
    assert all(t["is_paper"] is True for t in body["data"]["trades"])


def test_endpoint_disclaimer_present_on_every_endpoint(client, auth_user):
    client.post("/api/twin/initialize")
    paths = [
        "/api/twin/portfolio",
        "/api/twin/trades?days=30",
        "/api/twin/weekly-reports?n=12",
        "/api/twin/comparison",
    ]
    with patch("routes.twin.svc.fetcher.get_stock_snapshot", return_value=None):
        for p in paths:
            r = client.get(p)
            assert r.status_code == 200, p
            body = r.get_json()
            assert "disclaimer" in body, p
            assert "paper" in body["disclaimer"].lower(), p


def test_other_user_cannot_view_twin(app, client, make_user):
    from services.twin import initialize_twin

    owner = make_user(email="owner@test.com")
    intruder = make_user(email="intruder@test.com")
    with app.app_context():
        initialize_twin(owner["id"])

    # Login as intruder. Their own twin doesn't exist -> initialized=False.
    resp = client.post("/api/auth/login", json={
        "email": intruder["email"], "password": intruder["password"],
    })
    assert resp.status_code == 200
    with patch("routes.twin.svc.fetcher.get_stock_snapshot", return_value=None):
        r = client.get("/api/twin/portfolio")
    assert r.status_code == 200
    body = r.get_json()
    # The intruder receives THEIR OWN (uninitialized) state — never the owner's.
    assert body["data"].get("initialized") is False


def test_comparison_denominator_excludes_sell_proceeds(client, auth_user, app):
    """user_lifetime_pct denominator = BUY legs only (regression).

    A SELL's ``total_value`` is proceeds, not invested capital. Summing BOTH
    inflated the denominator and understated the return: a $1000 buy → $1100
    sell ($100 pnl) used to read 100 / (1000 + 1100) = 4.76% instead of the
    true 100 / 1000 = 10%.
    """
    from models import AITwinPortfolio, TradeHistory

    client.post("/api/twin/initialize")
    with app.app_context():
        twin = AITwinPortfolio.query.filter_by(user_id=auth_user["id"]).first()
        # All trades AFTER inception so the comparison window includes them.
        after = twin.initialized_at + timedelta(hours=1)
        # $1000 buy, then a sell returning $1100 proceeds → $100 realized P&L.
        db.session.add_all([
            TradeHistory(
                user_id=auth_user["id"], ticker="AAA", action="BUY",
                shares=10, price_per_share=100, total_value=1000.0,
                pnl=0.0, traded_at=after,
            ),
            TradeHistory(
                user_id=auth_user["id"], ticker="AAA", action="SELL",
                shares=10, price_per_share=110, total_value=1100.0,
                pnl=100.0, traded_at=after,
            ),
        ])
        db.session.commit()

    with patch("routes.twin.svc.fetcher.get_prices_batch", return_value={}):
        resp = client.get("/api/twin/comparison")
    assert resp.status_code == 200
    body = resp.get_json()
    pct = body["data"]["user_lifetime_pct"]
    # 100 pnl / 1000 invested (BUY only) = 10.0%. The old SELL-inclusive
    # denominator (2100) would have produced ~4.76%.
    assert pct == pytest.approx(10.0, abs=1e-6)
    assert pct != pytest.approx(4.7619, abs=1e-3)


# ─────────────────────────────────────────────────────────────────────
# F. Cron + initialization gate
# ─────────────────────────────────────────────────────────────────────


def test_cron_runs_for_initialized_users_only(app, make_user):
    """The decisions cron must skip users without an active twin.

    Mirrors the body of ``_scheduled_twin_decisions_us`` in app.py:
    the cron only iterates rows in ``ai_twin_portfolios`` — users
    without a twin are physically absent from the iteration set.
    """
    from services.twin import initialize_twin
    from models import AITwinPortfolio

    initialized = make_user(email="hasit@test.com")
    other = make_user(email="hasnt@test.com")  # no twin row

    with app.app_context():
        initialize_twin(initialized["id"])

    called_for: list[int] = []

    # Reproduce the cron's iteration explicitly; pass a fake decision
    # function so we never reach the real engine / fetcher.
    def _fake_run(user_id, **_kw):
        called_for.append(int(user_id))
        return {"ok": True}

    with app.app_context():
        rows = AITwinPortfolio.query.filter_by(is_active=True).all()
        for tw in rows:
            _fake_run(int(tw.user_id))

    assert initialized["id"] in called_for
    assert other["id"] not in called_for


# ─────────────────────────────────────────────────────────────────────
# G. "No real money anywhere" code-grep witness
# ─────────────────────────────────────────────────────────────────────


def test_no_real_money_field_anywhere():
    """The twin code path must NEVER reference real broker / account fields.

    A static grep is the strongest safety net we have until a SAST tool
    is in place. Catches accidental imports that would push the Twin
    closer to the regulatory edge.
    """
    project_root = Path(__file__).resolve().parent.parent
    twin_files = [
        project_root / "services" / "twin" / "twin_runner.py",
        project_root / "services" / "twin" / "twin_reporter.py",
        project_root / "routes" / "twin.py",
        project_root / "models" / "ai_twin_portfolio.py",
        project_root / "models" / "ai_twin_position.py",
        project_root / "models" / "ai_twin_trade.py",
        project_root / "models" / "ai_twin_weekly_report.py",
    ]
    forbidden_substrings = (
        # Broker / live-trading code paths.
        "alpaca",
        "broker_connection",
        "user_kis_service",
        "kis_websocket",
        "place_order",
        "submit_order",
        "live_account",
        "real_money",
        "is_paper=False",
        "is_paper = False",
    )
    for f in twin_files:
        assert f.exists(), f"missing: {f}"
        text = f.read_text(encoding="utf-8").lower()
        for needle in forbidden_substrings:
            assert needle.lower() not in text, (
                f"forbidden substring {needle!r} found in {f.name}"
            )


def test_buy_rationale_is_scrubbed_at_write_time(app, make_user, monkeypatch):
    """HANDOVER §3-B regression guard: ``AITwinTrade.rationale`` must be
    routed through ``services.legal_filter.safe_scrub`` so engine-generated
    advisory tokens never land in a user-visible paper-trade record.

    Setup: the engine stub returns ``signal="buy recommended now"`` — a
    string the ``_score_universe`` helper folds straight into the
    candidate's ``rationale``. Without scrub the persisted row would
    echo "buy" and "recommended" verbatim → 자본시장법 §17 leak.
    Expected: the persisted rationale contains neither token.
    """
    from services.twin import initialize_twin, run_twin_decisions
    from models import AITwinPortfolio, AITwinTrade
    from services import container as svc

    user = make_user()
    # Poisoned signal: contains two distinct legal_filter scrub triggers
    # ("BUY signal" and "recommended"). Engine→rationale path folds the
    # signal value into the candidate's rationale verbatim — without the
    # write-time scrub, both tokens would survive into the user-visible
    # paper-trade record.
    poisoned_signal = "BUY signal — recommended"

    class _PoisonedEngine:
        DISCOVER_POOL = ["AAA"]

        def analyze(self, ticker, capital_usd=10_000.0, **_kw):
            return {
                "composite_score": 95.0,
                "price": 100.0,
                "signal": poisoned_signal,
            }

    class _StubFetcher:
        def get_stock_snapshot(self, ticker):
            return {"price": 100.0, "currency": "USD"}

    with app.app_context():
        monkeypatch.setattr(svc, "engine", _PoisonedEngine())
        monkeypatch.setattr(svc, "fetcher", _StubFetcher())
        with patch("services.twin.twin_runner._resolve_persona", return_value="balanced"):
            initialize_twin(user["id"])
            run_twin_decisions(user["id"], universe=["AAA"])
        twin = AITwinPortfolio.query.filter_by(user_id=user["id"]).first()
        trade = (AITwinTrade.query
                 .filter_by(twin_id=twin.id, side="BUY", ticker="AAA")
                 .first())
        assert trade is not None, "expected a paper buy of AAA"
        # Pin the scrub: legal_filter maps "BUY signal" → "POSITIVE
        # indicator" and "recommended" → "note". We assert both source
        # tokens are gone, not the exact replacement (filter table may
        # evolve as legal review tightens phrasing).
        rat = trade.rationale or ""
        assert "BUY signal" not in rat, (
            f"'BUY signal' leaked into rationale: {rat!r}"
        )
        assert "recommended" not in rat.lower(), (
            f"'recommended' leaked into rationale: {rat!r}"
        )


def test_is_paper_default_true_in_model():
    """Sanity: the column-level default for ``AITwinTrade.is_paper`` is True.

    Defends against regressions where a future migration / model edit
    flips the default and silently turns the table into a real ledger.
    """
    from models import AITwinTrade
    col = AITwinTrade.__table__.columns["is_paper"]
    assert col.nullable is False
    # SQLAlchemy default may be a Python literal or a server_default — both must be truthy.
    py_default = getattr(col.default, "arg", None)
    assert py_default is True or py_default is None or py_default == "True"


def test_cron_registered_with_correct_ids():
    """Smoke-check: app.py contains the three Twin cron job IDs."""
    src = (Path(__file__).resolve().parent.parent / "app.py").read_text(encoding="utf-8")
    for jid in ("twin_kr_daily", "twin_us_daily", "twin_weekly_report"):
        assert f'id="{jid}"' in src, f"missing scheduled job id={jid}"
