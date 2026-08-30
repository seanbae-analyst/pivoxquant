"""Feature 5 — AI Twin FX-consistency regression (Pattern 7).

Guards the bug where a KR (.KS/.KQ) paper buy booked the KRW quote straight
into the USD ledger: the buy allocated the right USD cash but received
~1/1380th the shares, leaving a near-worthless position that read as ~-100%
on the portfolio view. See ``twin_runner._price_to_usd``.
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest


_FX = 1380.0  # deterministic USD/KRW for the tests


def _patch_kr_engine_and_fetcher(monkeypatch, *, ticker, score, price_krw):
    """Stub engine.analyze + fetcher snapshot for a single KR ticker, quoting
    KRW and flagging is_korean (mirrors the real snapshot shape)."""
    from services import container as svc

    class _StubEngine:
        DISCOVER_POOL = [ticker]

        def analyze(self, t, capital_usd=10_000.0, **_kw):
            if t != ticker:
                return None
            return {"composite_score": score, "price": price_krw,
                    "currency": "KRW", "is_korean": True, "signal": "stub"}

    class _StubFetcher:
        def get_stock_snapshot(self, t):
            if t == ticker:
                return {"price": price_krw, "currency": "KRW", "is_korean": True}
            return None

    monkeypatch.setattr(svc, "engine", _StubEngine())
    monkeypatch.setattr(svc, "fetcher", _StubFetcher())


def test_kr_buy_books_usd_share_count_not_1380x_too_few(app, make_user, monkeypatch):
    """A ₩71,000 KR buy must hold ~USD-priced shares, and the position's USD
    market value must match the cash the buy spent (not 1/1380th of it)."""
    from services.twin import initialize_twin, run_twin_decisions
    from models import AITwinPortfolio, AITwinPosition, DEFAULT_STARTING_CASH

    user = make_user()
    with app.app_context():
        _patch_kr_engine_and_fetcher(monkeypatch, ticker="005930.KS", score=95.0, price_krw=71000.0)
        with patch("services.fx_service.spot_usdkrw", return_value=_FX), \
             patch("services.twin.twin_runner._resolve_persona", return_value="balanced"):
            initialize_twin(user["id"])
            run_twin_decisions(user["id"], universe=["005930.KS"])

        twin = AITwinPortfolio.query.filter_by(user_id=user["id"]).first()
        pos = AITwinPosition.query.filter_by(twin_id=twin.id, ticker="005930.KS").first()
        assert pos is not None

        # avg_cost must be the USD price (~$51.4), NOT the raw ₩71,000.
        avg_cost = float(pos.avg_cost)
        assert avg_cost == pytest.approx(71000.0 / _FX, rel=1e-3), avg_cost

        # The position's USD value must equal the cash spent by the buy —
        # i.e. no value silently vaporized into a 1380x-undersized holding.
        spent = float(DEFAULT_STARTING_CASH) - float(twin.current_cash)
        pos_value_usd = float(pos.shares) * avg_cost
        assert pos_value_usd == pytest.approx(spent, rel=1e-3), (pos_value_usd, spent)

        # Sanity: a $10k twin buying a $51 stock holds >1 share (the bug gave <0.1).
        assert float(pos.shares) > 1.0


def test_kr_close_check_values_live_price_in_usd(app, make_user, monkeypatch):
    """TP must fire on a real USD gain, and proceeds must be USD-scaled (so
    cash after a full round-trip returns near the starting balance)."""
    from services.twin import initialize_twin, run_twin_decisions
    from models import AITwinPortfolio, AITwinTrade, DEFAULT_STARTING_CASH

    user = make_user()
    with app.app_context():
        # Buy at ₩71,000.
        _patch_kr_engine_and_fetcher(monkeypatch, ticker="005930.KS", score=95.0, price_krw=71000.0)
        with patch("services.fx_service.spot_usdkrw", return_value=_FX), \
             patch("services.twin.twin_runner._resolve_persona", return_value="balanced"):
            initialize_twin(user["id"])
            run_twin_decisions(user["id"], universe=["005930.KS"])

            # Price jumps +20% → balanced TP (12%) should close it.
            _patch_kr_engine_and_fetcher(monkeypatch, ticker="005930.KS", score=10.0, price_krw=85200.0)
            run_twin_decisions(user["id"], universe=["005930.KS"])

        twin = AITwinPortfolio.query.filter_by(user_id=user["id"]).first()
        sell = AITwinTrade.query.filter_by(twin_id=twin.id, side="SELL").first()
        assert sell is not None, "TP should have closed the KR position"
        # Sell price booked in USD (~$61.7), not raw ₩85,200.
        assert float(sell.price) == pytest.approx(85200.0 / _FX, rel=1e-3)
        # Round-tripped a +20% move on ~8% of cash → ends slightly ABOVE start.
        assert float(twin.current_cash) > float(DEFAULT_STARTING_CASH)


def test_reconcile_legacy_krw_position_restores_usd_basis(app, make_user, monkeypatch):
    """A position stored in the old KRW basis (marker False) is moved onto USD
    without changing its USD cost, and the marker flips True; a second run is a
    no-op (idempotent via the marker, not a price floor)."""
    from services.twin import initialize_twin, reconcile_legacy_krw_positions
    from models import AITwinPortfolio, AITwinPosition

    user = make_user()
    with app.app_context():
        twin = initialize_twin(user["id"])
        # Simulate a legacy corrupted booking: 0.0135 shares @ ₩71,000, marked
        # NOT-usd (the state every pre-fix KR row has after the server_default
        # backfill).
        legacy = AITwinPosition(twin_id=twin.id, ticker="005930.KS",
                                shares=Decimal("0.0135"), avg_cost=Decimal("71000"),
                                avg_cost_is_usd=False)
        from extensions import db
        db.session.add(legacy)
        db.session.commit()

        with patch("services.fx_service.spot_usdkrw", return_value=_FX):
            res = reconcile_legacy_krw_positions(dry_run=False)
        assert res["count"] == 1

        from extensions import db as _db
        fixed = _db.session.get(AITwinPosition, legacy.id)
        assert float(fixed.avg_cost) == pytest.approx(71000.0 / _FX, rel=1e-3)
        assert float(fixed.shares) == pytest.approx(0.0135 * _FX, rel=1e-3)
        # USD cost basis (shares * avg_cost) is preserved by the repair.
        assert float(fixed.shares) * float(fixed.avg_cost) == pytest.approx(
            0.0135 * 71000.0, rel=1e-3)
        # The row is now marked USD, which is what makes the re-run a no-op.
        assert fixed.avg_cost_is_usd is True

        # Idempotent: marker is now True so a re-run changes nothing.
        with patch("services.fx_service.spot_usdkrw", return_value=_FX):
            res2 = reconcile_legacy_krw_positions(dry_run=False)
        assert res2["count"] == 0


def test_reconcile_dry_run_does_not_flip_marker_or_write(app, make_user, monkeypatch):
    """dry_run reports what would change but must NOT mutate the row or flip the
    marker — so a later real run still repairs it."""
    from services.twin import initialize_twin, reconcile_legacy_krw_positions
    from models import AITwinPosition
    from extensions import db

    user = make_user()
    with app.app_context():
        twin = initialize_twin(user["id"])
        legacy = AITwinPosition(twin_id=twin.id, ticker="005930.KS",
                                shares=Decimal("0.0135"), avg_cost=Decimal("71000"),
                                avg_cost_is_usd=False)
        db.session.add(legacy)
        db.session.commit()

        with patch("services.fx_service.spot_usdkrw", return_value=_FX):
            res = reconcile_legacy_krw_positions(dry_run=True)
        assert res["count"] == 1  # it WOULD change one row
        untouched = db.session.get(AITwinPosition, legacy.id)
        assert float(untouched.avg_cost) == pytest.approx(71000.0, rel=1e-9)
        assert untouched.avg_cost_is_usd is False  # marker NOT flipped


def test_reconcile_leaves_correct_high_priced_usd_kr_row_untouched(app, make_user, monkeypatch):
    """THE bug the audit reproduced: a correctly-USD-booked high-priced KR share
    (LG생활건강 @ ₩1.5M → avg_cost≈$1,087, marker True) must be a strict no-op —
    a flat magnitude floor would have misread it as legacy and re-divided it to
    ~$0.79. The per-row marker makes that impossible."""
    from services.twin import initialize_twin, reconcile_legacy_krw_positions
    from models import AITwinPosition
    from extensions import db

    user = make_user()
    with app.app_context():
        twin = initialize_twin(user["id"])
        # ₩1.5M / 1380 ≈ $1,086.96 — well ABOVE the old 900 floor, yet USD-correct.
        usd_avg = Decimal(str(round(1_500_000.0 / _FX, 4)))  # ≈ 1086.9565
        correct = AITwinPosition(twin_id=twin.id, ticker="051900.KS",
                                 shares=Decimal("0.5"), avg_cost=usd_avg,
                                 avg_cost_is_usd=True)
        db.session.add(correct)
        db.session.commit()

        with patch("services.fx_service.spot_usdkrw", return_value=_FX):
            res = reconcile_legacy_krw_positions(dry_run=False)
        assert res["count"] == 0, "a correct USD row must never be reconciled"

        fixed = db.session.get(AITwinPosition, correct.id)
        assert float(fixed.avg_cost) == pytest.approx(float(usd_avg), rel=1e-9)
        assert float(fixed.shares) == pytest.approx(0.5, rel=1e-9)
        assert fixed.avg_cost_is_usd is True


def test_reconcile_via_do_migrations_is_idempotent(app, make_user, monkeypatch):
    """Wiring: the startup self-heal (`_do_migrations`) runs the reconcile, and a
    second boot is a no-op — a legacy KRW position (marker False) is repaired
    exactly once, then skipped forever via the marker."""
    import app as app_module
    from services.twin import initialize_twin
    from models import AITwinPosition
    from extensions import db

    user = make_user()
    with app.app_context():
        twin = initialize_twin(user["id"])
        legacy = AITwinPosition(twin_id=twin.id, ticker="005930.KS",
                                shares=Decimal("0.0135"), avg_cost=Decimal("71000"),
                                avg_cost_is_usd=False)
        db.session.add(legacy)
        db.session.commit()

        with patch("services.fx_service.spot_usdkrw", return_value=_FX):
            # First boot: repairs the legacy row and flips its marker.
            app_module._do_migrations()
            first = db.session.get(AITwinPosition, legacy.id)
            assert float(first.avg_cost) == pytest.approx(71000.0 / _FX, rel=1e-3)
            assert first.avg_cost_is_usd is True
            repaired_avg = float(first.avg_cost)
            repaired_shares = float(first.shares)

            # Second boot: marker=True makes it a no-op — no further mutation.
            app_module._do_migrations()
            second = db.session.get(AITwinPosition, legacy.id)
            assert float(second.avg_cost) == pytest.approx(repaired_avg, rel=1e-9)
            assert float(second.shares) == pytest.approx(repaired_shares, rel=1e-9)


def test_fresh_kr_buy_is_usd_marked_and_survives_boot(app, make_user, monkeypatch):
    """A new ₩1.5M KR buy via the score/buy path must be booked in USD with
    avg_cost_is_usd=True, and must survive the next `_do_migrations()` boot
    UNCHANGED (the marker protects freshly-correct high-priced KR bookings)."""
    import app as app_module
    from services.twin import initialize_twin, run_twin_decisions
    from models import AITwinPortfolio, AITwinPosition
    from extensions import db

    user = make_user()
    with app.app_context():
        _patch_kr_engine_and_fetcher(monkeypatch, ticker="051900.KS", score=95.0,
                                     price_krw=1_500_000.0)
        with patch("services.fx_service.spot_usdkrw", return_value=_FX), \
             patch("services.twin.twin_runner._resolve_persona", return_value="balanced"):
            initialize_twin(user["id"])
            run_twin_decisions(user["id"], universe=["051900.KS"])

            twin = AITwinPortfolio.query.filter_by(user_id=user["id"]).first()
            pos = AITwinPosition.query.filter_by(twin_id=twin.id, ticker="051900.KS").first()
            assert pos is not None
            # Booked in USD (~$1,087) and flagged.
            assert float(pos.avg_cost) == pytest.approx(1_500_000.0 / _FX, rel=1e-3)
            assert pos.avg_cost_is_usd is True
            avg_before, shares_before = float(pos.avg_cost), float(pos.shares)

            # Next boot must NOT touch it (would have divided $1,087 → $0.79 under
            # the old flat floor).
            app_module._do_migrations()
            after = db.session.get(AITwinPosition, pos.id)
            assert float(after.avg_cost) == pytest.approx(avg_before, rel=1e-9)
            assert float(after.shares) == pytest.approx(shares_before, rel=1e-9)
            assert after.avg_cost_is_usd is True


def test_do_migrations_is_fail_open_when_reconcile_raises(app, make_user, monkeypatch):
    """Safety: if the twin reconcile blows up, `_do_migrations` must still
    complete (boot is never blocked) and swallow the error."""
    import app as app_module

    def _boom(*_a, **_kw):
        raise RuntimeError("simulated reconcile failure")

    with app.app_context():
        # Patch the symbol the lazy import inside _do_migrations resolves to.
        monkeypatch.setattr(
            "services.twin.reconcile_legacy_krw_positions", _boom, raising=True
        )
        # Must not raise — the surrounding silent-fallback try/except absorbs it.
        app_module._do_migrations()


def test_us_ticker_price_is_not_fx_converted(app, make_user, monkeypatch):
    """A USD ticker must pass through unchanged (guard against over-converting)."""
    from services.twin import initialize_twin, run_twin_decisions
    from models import AITwinPortfolio, AITwinPosition

    user = make_user()
    with app.app_context():
        from services import container as svc

        class _StubEngine:
            DISCOVER_POOL = ["AAPL"]

            def analyze(self, t, capital_usd=10_000.0, **_kw):
                if t != "AAPL":
                    return None
                return {"composite_score": 95.0, "price": 200.0,
                        "currency": "USD", "is_korean": False, "signal": "stub"}

        class _StubFetcher:
            def get_stock_snapshot(self, t):
                return {"price": 200.0, "currency": "USD", "is_korean": False} if t == "AAPL" else None

        monkeypatch.setattr(svc, "engine", _StubEngine())
        monkeypatch.setattr(svc, "fetcher", _StubFetcher())
        with patch("services.fx_service.spot_usdkrw", return_value=_FX), \
             patch("services.twin.twin_runner._resolve_persona", return_value="balanced"):
            initialize_twin(user["id"])
            run_twin_decisions(user["id"], universe=["AAPL"])

        twin = AITwinPortfolio.query.filter_by(user_id=user["id"]).first()
        pos = AITwinPosition.query.filter_by(twin_id=twin.id, ticker="AAPL").first()
        assert pos is not None
        assert float(pos.avg_cost) == pytest.approx(200.0, rel=1e-6)
