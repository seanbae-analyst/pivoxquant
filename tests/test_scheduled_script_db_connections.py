"""Scheduled scripts close their database connection, even when a query fails.

2026-09-11: production's Supabase session pooler (15 clients) rejected
connections about 200 times an hour, and new deploys died at boot with
EMAXCONNSESSION. These scripts run inside the web process on the in-process
scheduler, so every connection they open competes with the app for those 15
slots.

Two defects in ``signup_funnel_check`` (every 5 minutes):
- it opened a new connection per query (6 per tick)
- its payment queries named a table and column that do not exist, so every
  tick raised before ``conn.close()`` and discarded the other four metrics
"""
from __future__ import annotations

import sys
import types

import pytest


class _FakeCursor:
    def __init__(self, conn: "_FakeConn") -> None:
        self._conn = conn
        self._row = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self._conn.executed.append(sql)
        if self._conn.fail_on and self._conn.fail_on in sql:
            raise RuntimeError("relation does not exist")
        self._row = (7,)

    def fetchone(self):
        return self._row

    def fetchall(self):
        return []

    def close(self):
        pass


class _FakeConn:
    def __init__(self, fail_on: str | None) -> None:
        self.fail_on = fail_on
        self.executed: list[str] = []
        self.closed = False
        self.autocommit = False

    def cursor(self):
        return _FakeCursor(self)

    def close(self):
        self.closed = True


def _fake_psycopg2(monkeypatch, fail_on: str | None = None, connect_error: bool = False) -> list[_FakeConn]:
    connections: list[_FakeConn] = []

    def connect(*args, **kwargs):
        if connect_error:
            raise RuntimeError("max clients reached")
        conn = _FakeConn(fail_on)
        connections.append(conn)
        return conn

    monkeypatch.setitem(sys.modules, "psycopg2", types.SimpleNamespace(connect=connect))
    return connections


# ── signup_funnel_check ──────────────────────────────────────────────────────

def test_funnel_tick_uses_one_connection_and_closes_it(monkeypatch):
    from scripts.nightly.signup_funnel_check import fetch_funnel_metrics

    connections = _fake_psycopg2(monkeypatch)
    metrics = fetch_funnel_metrics("postgresql://fake")

    assert len(connections) == 1
    assert connections[0].closed
    assert len(connections[0].executed) == 6
    assert metrics["signup_5m"] == 7
    assert metrics["stripe_success_24h"] == 7


def test_funnel_failed_query_blanks_only_that_metric(monkeypatch):
    from scripts.nightly.signup_funnel_check import fetch_funnel_metrics

    connections = _fake_psycopg2(monkeypatch, fail_on="payment_intent.payment_failed")
    metrics = fetch_funnel_metrics("postgresql://fake")

    assert connections[0].closed
    assert metrics["stripe_fail_24h"] is None
    assert metrics["payment_fail_pct"] is None
    assert metrics["signup_5m"] == 7
    assert metrics["oauth_pct"] == 100.0


def test_funnel_connect_failure_returns_empty_metrics(monkeypatch):
    from scripts.nightly.signup_funnel_check import fetch_funnel_metrics

    _fake_psycopg2(monkeypatch, connect_error=True)
    metrics = fetch_funnel_metrics("postgresql://fake")

    assert metrics["signup_5m"] is None
    assert metrics["stripe_success_24h"] is None


def test_funnel_payment_queries_match_the_model(monkeypatch):
    """The table is plural and has processed_at, not created_at."""
    from models.processed_stripe_event import ProcessedStripeEvent
    from scripts.nightly.signup_funnel_check import fetch_funnel_metrics

    connections = _fake_psycopg2(monkeypatch)
    fetch_funnel_metrics("postgresql://fake")

    payment_sql = [s for s in connections[0].executed if "payment_intent" in s]
    assert len(payment_sql) == 2
    assert "processed_at" in ProcessedStripeEvent.__table__.columns
    for sql in payment_sql:
        assert f"FROM {ProcessedStripeEvent.__tablename__} " in sql
        assert "processed_at" in sql
        assert "created_at" not in sql


# ── the other scheduled scripts ──────────────────────────────────────────────

def test_ticker_name_audit_closes_on_query_error(monkeypatch):
    from scripts.nightly.ticker_name_audit import _run_psycopg2

    connections = _fake_psycopg2(monkeypatch, fail_on="signal_cache")
    with pytest.raises(RuntimeError):
        _run_psycopg2("postgresql://fake")
    assert connections[0].closed


def test_section101_artifact_check_closes_on_query_error(monkeypatch):
    from scripts.nightly.section101_compliance_check import _check_artifact_solicitation

    connections = _fake_psycopg2(monkeypatch, fail_on="FROM artifacts")
    assert _check_artifact_solicitation("postgresql://fake") == []
    assert connections[0].closed


def test_morning_brief_kpi_closes_on_query_error(monkeypatch):
    from scripts.morning_brief.build_brief_kpi import fetch_db_kpi

    monkeypatch.setenv("DATABASE_URL", "postgresql://fake")
    connections = _fake_psycopg2(monkeypatch, fail_on="FROM artifacts")
    with pytest.raises(RuntimeError):
        fetch_db_kpi()
    assert connections[0].closed
