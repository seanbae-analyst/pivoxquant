"""
/api/alerts/price-check — N+1 query elimination (Perf P1-1, 2026-05-10).

Proves:
  1. Dedup lookup uses a SINGLE Alert.query.filter call regardless of how
     many positions / generated alerts exist (was N before fix).
  2. Existing recent rows still suppress duplicate alert creation
     (semantic equivalence to the old per-alert .first() check).
  3. Different alert types (TAKE_PROFIT vs STOP_LOSS) on the same ticker
     are deduped independently — recent TP must not block a new SL row.
  4. The endpoint still returns the alerts payload unchanged.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest


def _make_signal_cache(app, ticker: str, sd: dict):
    """Direct-write a SignalCache row so price_check has data to read."""
    from extensions import db
    from models import SignalCache
    with app.app_context():
        row = SignalCache(
            ticker=ticker,
            data_json=json.dumps(sd, ensure_ascii=False),
            updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.session.add(row)
        db.session.commit()


def _add_alert_row(app, user_id: int, ticker: str, message: str,
                   minutes_ago: int = 1):
    from extensions import db
    from models import Alert
    with app.app_context():
        row = Alert(
            user_id=user_id, ticker=ticker, message=message,
            signal="POSITIVE", score=0, kind="price_take_profit",
            created_at=datetime.now(timezone.utc).replace(tzinfo=None)
                       - timedelta(minutes=minutes_ago),
        )
        db.session.add(row)
        db.session.commit()


# ─── Test 1: single batch query for dedup ──────────────────────────────────


def test_price_check_uses_single_batch_dedup_query(
    client, auth_user, add_position, app
):
    """N positions trip TP/SL → exactly ONE Alert.query.filter_by(...)
    .filter(Alert.ticker.in_(...)).filter(Alert.created_at > ...).all()
    call, not N. We assert this by counting how many `.all()` invocations
    happen against an Alert IN-clause query.
    """
    # Three positions, all with TP-trip signals cached.
    add_position(auth_user["id"], ticker="AAPL", shares=10, avg_cost=100)
    add_position(auth_user["id"], ticker="MSFT", shares=5,  avg_cost=200)
    add_position(auth_user["id"], ticker="NVDA", shares=2,  avg_cost=300)

    for t, name in [("AAPL", "Apple"), ("MSFT", "Microsoft"), ("NVDA", "NVIDIA")]:
        _make_signal_cache(app, t, {
            "price": 200.0, "take_profit": 150.0, "stop_loss": 50.0,
            "name": name, "is_korean": False,
        })

    # Spy on Query.all so we can count the dedup batch query against the
    # `alerts` table specifically (NOT the SignalCache batch).
    from sqlalchemy.orm import Query as _Query
    real_all = _Query.all
    alert_in_clause_calls = {"count": 0}

    seen_sql: list[str] = []

    def counting_all(self):
        try:
            sql = str(self).lower()
            seen_sql.append(sql)
            # Dedup query targets the `alerts` table with an IN (...) on
            # ticker. Distinguish from the signal_cache batch by table name.
            if (
                "alerts" in sql
                and "in (" in sql
                and "ticker" in sql
            ):
                alert_in_clause_calls["count"] += 1
        except Exception:
            pass
        return real_all(self)

    with patch.object(_Query, "all", counting_all):
        r = client.get("/api/alerts/price-check")

    assert r.status_code == 200
    body = r.get_json()
    assert "alerts" in body
    assert len(body["alerts"]) == 3, (
        f"All three positions trip TP — expected 3 alerts, got "
        f"{len(body['alerts'])}"
    )
    # The fix-target invariant: exactly one batched IN-query for dedup,
    # not N (one per generated alert).
    assert alert_in_clause_calls["count"] == 1, (
        "Expected exactly 1 batched Alert IN-clause query for dedup, got "
        f"{alert_in_clause_calls['count']} — N+1 regression. SQL seen:\n"
        + "\n---\n".join(seen_sql)
    )


# ─── Test 2: dedup still suppresses on existing recent row ────────────────


def test_price_check_dedup_suppresses_existing_recent_alert(
    client, auth_user, add_position, app
):
    """If a TAKE_PROFIT alert already exists within the 4-hour window,
    no duplicate should be persisted (only one Alert row in DB at the end).
    """
    add_position(auth_user["id"], ticker="AAPL", shares=10, avg_cost=100)
    _make_signal_cache(app, "AAPL", {
        "price": 200.0, "take_profit": 150.0, "stop_loss": 50.0,
        "name": "Apple", "is_korean": False,
    })
    # Pre-existing recent TP alert.
    _add_alert_row(
        app, auth_user["id"], "AAPL",
        "Apple 사전 설정 TP 레벨 도달 — 정보 고지 (TAKE_PROFIT marker)",
        minutes_ago=10,
    )

    r = client.get("/api/alerts/price-check")
    assert r.status_code == 200

    from models import Alert
    with app.app_context():
        rows = Alert.query.filter_by(
            user_id=auth_user["id"], ticker="AAPL"
        ).all()
        # Pre-existing 1 + 0 new = 1 (dedup suppressed).
        assert len(rows) == 1, (
            f"Dedup must suppress; expected 1 row, got {len(rows)}"
        )


# ─── Test 3: TP and SL dedup independently per ticker ──────────────────────


def test_price_check_tp_and_sl_dedup_independently(
    client, auth_user, add_position, app
):
    """A recent TAKE_PROFIT alert must NOT suppress a brand-new STOP_LOSS
    alert on the same ticker — they're different `type` keys.
    """
    add_position(auth_user["id"], ticker="AAPL", shares=10, avg_cost=100)
    # Cached signal trips STOP_LOSS only (price below SL).
    _make_signal_cache(app, "AAPL", {
        "price": 40.0, "take_profit": 999.0, "stop_loss": 50.0,
        "name": "Apple", "is_korean": False,
    })
    # Pre-existing TP alert — should NOT block a new SL alert.
    _add_alert_row(
        app, auth_user["id"], "AAPL",
        "Apple TAKE_PROFIT marker — old",
        minutes_ago=20,
    )

    r = client.get("/api/alerts/price-check")
    assert r.status_code == 200

    from models import Alert
    with app.app_context():
        all_rows = Alert.query.filter_by(
            user_id=auth_user["id"], ticker="AAPL"
        ).all()
        # 1 existing TP + 1 new SL = 2.
        assert len(all_rows) == 2, (
            "Independent (ticker, type) dedup expected — old TP must not "
            f"block new SL. Got {len(all_rows)} rows."
        )
        kinds = sorted(r.kind or "" for r in all_rows)
        assert "price_stop_loss" in kinds, (
            f"New SL row missing — kinds={kinds}"
        )


# ─── Test 4: empty portfolio short-circuits ────────────────────────────────


def test_price_check_empty_portfolio_returns_empty(client, auth_user):
    r = client.get("/api/alerts/price-check")
    assert r.status_code == 200
    assert r.get_json() == {"alerts": []}
