"""Unit tests for services.artifacts.data_source_resolver.

Covers both public helpers:
* `resolve_user_data_sources(user_id, ...)` — Wave 5, returns list[str].
* `resolve_user_data_lineage(user_id, ...)`  — Wave 6, returns list[dict].

The resolver is the single source of truth for "which data providers
may we legitimately name on this user's artifact?". Incorrect output
is a 표시광고법 §3 기만표시 exposure, so this file exercises every
branch (connected/disconnected Alpaca/KIS, legacy rows, DB failure,
opt-in journal / manual ledger flags) in isolation.

Import-time safety
------------------
The resolver lazy-imports `models.BrokerConnection` inside each
connection check so pytest can patch it with a stub without booting
the Flask app / SQLAlchemy session. Tests monkeypatch
`data_source_resolver._has_active_alpaca` / `_has_active_kis` directly
— that keeps the surface-level public contract under test without
pulling in the ORM.
"""
from __future__ import annotations


from services.artifacts import data_source_resolver as dsr


# ---------------------------------------------------------------------------
# resolve_user_data_sources — Wave 5 list[str] contract
# ---------------------------------------------------------------------------


class TestResolveUserDataSources:
    """Wave-5 helper: list of provider-name strings for the colophon."""

    def test_none_user_returns_system_only(self) -> None:
        """`user_id=None` — no user context, only public aggregators."""
        out = dsr.resolve_user_data_sources(None)
        assert out == ["FMP v4", "SEC EDGAR", "FRED"]

    def test_include_system_false_returns_empty_for_none_user(self) -> None:
        """No user + no system — empty list signals 'unknown'."""
        out = dsr.resolve_user_data_sources(None, include_system=False)
        assert out == []

    def test_connected_alpaca_adds_broker_row(self, monkeypatch) -> None:
        monkeypatch.setattr(dsr, "_has_active_alpaca", lambda uid: True)
        monkeypatch.setattr(dsr, "_has_active_kis", lambda uid: False)
        out = dsr.resolve_user_data_sources(123)
        assert "Alpaca" in out
        assert "KIS" not in out
        # System sources still lead.
        assert out[0] == "FMP v4"

    def test_connected_kis_adds_broker_row(self, monkeypatch) -> None:
        monkeypatch.setattr(dsr, "_has_active_alpaca", lambda uid: False)
        monkeypatch.setattr(dsr, "_has_active_kis", lambda uid: True)
        out = dsr.resolve_user_data_sources(456)
        assert "KIS" in out
        assert "Alpaca" not in out

    def test_both_brokers_connected(self, monkeypatch) -> None:
        monkeypatch.setattr(dsr, "_has_active_alpaca", lambda uid: True)
        monkeypatch.setattr(dsr, "_has_active_kis", lambda uid: True)
        out = dsr.resolve_user_data_sources(789)
        assert "Alpaca" in out
        assert "KIS" in out

    def test_no_brokers_connected_returns_system_only(self, monkeypatch) -> None:
        """A disconnected user — never claim Alpaca/KIS."""
        monkeypatch.setattr(dsr, "_has_active_alpaca", lambda uid: False)
        monkeypatch.setattr(dsr, "_has_active_kis", lambda uid: False)
        out = dsr.resolve_user_data_sources(42)
        assert out == ["FMP v4", "SEC EDGAR", "FRED"]

    def test_include_journal_appends_observation_journal(self, monkeypatch) -> None:
        monkeypatch.setattr(dsr, "_has_active_alpaca", lambda uid: False)
        monkeypatch.setattr(dsr, "_has_active_kis", lambda uid: False)
        out = dsr.resolve_user_data_sources(42, include_journal=True)
        assert "Observation journal" in out

    def test_include_manual_ledger_appends_row(self, monkeypatch) -> None:
        monkeypatch.setattr(dsr, "_has_active_alpaca", lambda uid: False)
        monkeypatch.setattr(dsr, "_has_active_kis", lambda uid: False)
        out = dsr.resolve_user_data_sources(42, include_manual_ledger=True)
        assert "Manual ledger" in out

    def test_has_active_alpaca_db_failure_returns_false(self, monkeypatch) -> None:
        """Any exception inside the connection check falls back to False.

        The invariant is "refuse to invent a provenance claim". A broken
        DB session must not flip the user's Alpaca status to True.
        """
        def _boom(*_args, **_kwargs):
            raise RuntimeError("simulated DB outage")

        # Patch the module-level `BrokerConnection` import path by
        # replacing `models` with a stub that raises on attribute access.
        class _StubModels:
            def __getattr__(self, name: str):
                raise RuntimeError("simulated import failure")

        monkeypatch.setitem(__import__("sys").modules, "models", _StubModels())
        assert dsr._has_active_alpaca(999) is False
        assert dsr._has_active_kis(999) is False


# ---------------------------------------------------------------------------
# resolve_user_data_lineage — Wave 6 list[dict] contract
# ---------------------------------------------------------------------------


class TestResolveUserDataLineage:
    """Wave-6 helper: structured lineage rows for the richer colophons
    (KPI dashboard, Risk Board, Portfolio Segment, etc.).
    """

    def test_none_user_returns_system_lineage_only(self) -> None:
        out = dsr.resolve_user_data_lineage(None)
        names = [row["source"] for row in out]
        assert names == ["FMP v4", "SEC EDGAR", "FRED"]
        # Shape contract — every row has source/description/coverage.
        for row in out:
            assert set(row.keys()) >= {"source", "description", "coverage"}

    def test_no_system_and_no_user_returns_empty(self) -> None:
        out = dsr.resolve_user_data_lineage(None, include_system=False)
        assert out == []

    def test_alpaca_connection_adds_alpaca_lineage_row(self, monkeypatch) -> None:
        monkeypatch.setattr(dsr, "_has_active_alpaca", lambda uid: True)
        monkeypatch.setattr(dsr, "_has_active_kis", lambda uid: False)
        out = dsr.resolve_user_data_lineage(7)
        sources = [row["source"] for row in out]
        assert "Alpaca" in sources
        assert "KIS" not in sources

    def test_disconnected_user_never_claims_broker(self, monkeypatch) -> None:
        """Wave 6 core invariant — empty broker status = no broker row."""
        monkeypatch.setattr(dsr, "_has_active_alpaca", lambda uid: False)
        monkeypatch.setattr(dsr, "_has_active_kis", lambda uid: False)
        out = dsr.resolve_user_data_lineage(7)
        sources = [row["source"] for row in out]
        assert "Alpaca" not in sources
        assert "KIS" not in sources

    def test_include_journal_adds_journal_row(self, monkeypatch) -> None:
        monkeypatch.setattr(dsr, "_has_active_alpaca", lambda uid: False)
        monkeypatch.setattr(dsr, "_has_active_kis", lambda uid: False)
        out = dsr.resolve_user_data_lineage(7, include_journal=True)
        sources = [row["source"] for row in out]
        assert "Observation journal" in sources

    def test_lineage_rows_are_copies_not_shared_refs(self) -> None:
        """Mutating one caller's lineage must not leak into another's.

        The resolver returns fresh dicts per call so a caller that adds
        a row to the returned list can't poison the next caller.
        """
        a = dsr.resolve_user_data_lineage(None)
        b = dsr.resolve_user_data_lineage(None)
        assert a is not b
        a[0]["coverage"] = "mutated"
        assert b[0]["coverage"] != "mutated"

    def test_kis_connection_row_is_read_only(self, monkeypatch) -> None:
        """KIS is read-only — the description must say so."""
        monkeypatch.setattr(dsr, "_has_active_alpaca", lambda uid: False)
        monkeypatch.setattr(dsr, "_has_active_kis", lambda uid: True)
        out = dsr.resolve_user_data_lineage(7)
        kis_row = next(r for r in out if r["source"] == "KIS")
        assert "read-only" in kis_row["description"].lower()

    def test_include_manual_ledger_appends_row(self, monkeypatch) -> None:
        monkeypatch.setattr(dsr, "_has_active_alpaca", lambda uid: False)
        monkeypatch.setattr(dsr, "_has_active_kis", lambda uid: False)
        out = dsr.resolve_user_data_lineage(
            7, include_manual_ledger=True,
        )
        sources = [row["source"] for row in out]
        assert "Manual ledger" in sources
