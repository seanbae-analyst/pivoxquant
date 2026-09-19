"""Honest equity curve — real NAV snapshots, no fabrication.

The equity curve used to be *reconstructed* from the user's CURRENT share count
× historical prices, drawing months the user never actually held that book (CEO
flagged repeatedly as fake data; 표시광고법 fabrication risk). It now plots ONLY
NAV we actually observed and recorded.

These tests prove:
  1. the recorder stores real observed NAV (USD + KR→USD unified) and is
     idempotent per day;
  2. /portfolio/history returns ONLY recorded NAV — a position opened 200 days
     ago no longer yields a 200-day fabricated curve.
"""

# /api/portfolio/history serves a vendor-priced NAV series, so these tests
# take the `market_display_on` fixture — MARKET_DATA_DISPLAY_ENABLED defaults
# to OFF and the endpoint then returns an empty curve by design
# (tests/test_market_data_display_flag.py::TestHistoryOff).
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from extensions import db
from models import Position, PortfolioNavSnapshot


class _FakeRealtime:
    def __init__(self, prices):
        self._p = prices

    def get_prices_batch(self, tickers):
        return self._p


# ── Recorder (service layer) ─────────────────────────────────────────

def test_compute_current_nav_us(app, make_user, monkeypatch):
    user = make_user(email="nav_us@test.com")
    with app.app_context():
        db.session.add(Position(user_id=user["id"], ticker="AAPL", shares=10, avg_cost=100.0))
        db.session.commit()
        import services.portfolio.nav_snapshot as ns
        monkeypatch.setattr(ns, "realtime", _FakeRealtime({"AAPL": {"price": 150.0}}))
        monkeypatch.setattr(ns.fx_service, "get_rate", lambda: 1300.0)
        nav = ns.compute_current_nav(user["id"])
        assert nav is not None
        assert nav["nav_total_usd"] == 1500.0  # 10 × 150
        assert nav["nav_us_usd"] == 1500.0
        assert nav["nav_kr_krw"] == 0


def test_compute_current_nav_kr_unified_to_usd(app, make_user, monkeypatch):
    user = make_user(email="nav_kr@test.com")
    with app.app_context():
        db.session.add(Position(user_id=user["id"], ticker="005930.KS", shares=10, avg_cost=70000.0))
        db.session.commit()
        import services.portfolio.nav_snapshot as ns
        monkeypatch.setattr(ns, "realtime", _FakeRealtime({"005930.KS": {"price": 80000.0}}))
        monkeypatch.setattr(ns.fx_service, "get_rate", lambda: 1000.0)
        nav = ns.compute_current_nav(user["id"])
        assert nav["nav_kr_krw"] == 800000.0       # 10 × 80,000 KRW
        assert nav["nav_total_usd"] == 800.0       # 800,000 / 1,000


def test_record_today_snapshot_idempotent(app, make_user, monkeypatch):
    user = make_user(email="nav_rec@test.com")
    with app.app_context():
        db.session.add(Position(user_id=user["id"], ticker="AAPL", shares=10, avg_cost=100.0))
        db.session.commit()
        import services.portfolio.nav_snapshot as ns
        monkeypatch.setattr(ns, "realtime", _FakeRealtime({"AAPL": {"price": 150.0}}))
        monkeypatch.setattr(ns.fx_service, "get_rate", lambda: 1300.0)

        assert ns.record_today_snapshot(user["id"]) is True
        rows = PortfolioNavSnapshot.query.filter_by(user_id=user["id"]).all()
        assert len(rows) == 1
        assert float(rows[0].nav_total_usd) == 1500.0

        # Re-record the SAME day at a new price → UPDATE, not a second row.
        monkeypatch.setattr(ns, "realtime", _FakeRealtime({"AAPL": {"price": 160.0}}))
        assert ns.record_today_snapshot(user["id"]) is True
        rows = PortfolioNavSnapshot.query.filter_by(user_id=user["id"]).all()
        assert len(rows) == 1
        assert float(rows[0].nav_total_usd) == 1600.0


def test_record_no_positions_returns_false(app, make_user):
    user = make_user(email="nav_empty@test.com")
    with app.app_context():
        import services.portfolio.nav_snapshot as ns
        assert ns.record_today_snapshot(user["id"]) is False
        assert PortfolioNavSnapshot.query.filter_by(user_id=user["id"]).count() == 0


# ── /portfolio/history (route) ───────────────────────────────────────

def _silence_benchmark(monkeypatch):
    """Neutralise the benchmark FMP/KIS fetch so route tests stay offline."""
    import services.data.fmp as fmpmod
    monkeypatch.setattr(fmpmod, "get_history", lambda *a, **k: None)


def test_history_no_fabrication_for_old_position(
    app, client, auth_user, add_position, mock_realtime, monkeypatch,
    market_display_on,
):
    """A position opened 200 days ago must NOT produce a 200-day curve."""
    old = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=200)
    add_position(auth_user["id"], ticker="AAPL", shares=10, avg_cost=100.0, added_at=old)

    import services.portfolio.nav_snapshot as ns
    monkeypatch.setattr(ns, "realtime", _FakeRealtime({"AAPL": {"price": 150.0}}))
    _silence_benchmark(monkeypatch)

    resp = client.get("/api/portfolio/history?period=1y")
    assert resp.status_code == 200
    data = resp.get_json()["data"]

    # Only REAL recorded NAV — today's opportunistic snapshot. No 200-day series.
    assert 1 <= len(data) <= 2, data
    oldest_allowed = (date.today() - timedelta(days=5)).isoformat()
    assert all(pt["date"] >= oldest_allowed for pt in data), data


def test_history_returns_recorded_snapshots(
    app, client, auth_user, add_position, mock_realtime, monkeypatch,
    market_display_on,
):
    """Pre-recorded real snapshots ARE returned as the curve."""
    add_position(auth_user["id"], ticker="AAPL", shares=10, avg_cost=100.0)
    # Seed the historical rows by the SAME day the recorder keys on —
    # ``record_today_snapshot`` uses ``datetime.now(timezone.utc).date()``. The
    # read-path records today's NAV live on every load (1500 here), so using a
    # local ``date.today()`` basis here let "yesterday" collide with the
    # recorder's UTC "today" during the KST 00:00–09:00 window (local date is a
    # day ahead of UTC) and get overwritten by the live upsert. UTC throughout
    # keeps the seeded history strictly before the recorder's today.
    utc_today = datetime.now(timezone.utc).date()
    d2, d1 = utc_today - timedelta(days=2), utc_today - timedelta(days=1)
    with app.app_context():
        for d, v in ((d2, 1000.0), (d1, 1100.0)):
            db.session.add(PortfolioNavSnapshot(
                user_id=auth_user["id"], as_of_date=d,
                nav_total_usd=v, nav_us_usd=v, nav_kr_krw=0, fx_rate=1300,
            ))
        db.session.commit()

    import services.portfolio.nav_snapshot as ns
    monkeypatch.setattr(ns, "realtime", _FakeRealtime({"AAPL": {"price": 150.0}}))
    _silence_benchmark(monkeypatch)

    resp = client.get("/api/portfolio/history?period=1mo")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    dvals = {pt["date"]: pt["value"] for pt in data}
    assert dvals[d2.isoformat()] == 1000.0
    assert dvals[d1.isoformat()] == 1100.0
