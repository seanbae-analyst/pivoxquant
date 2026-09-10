"""Regression guard: an underivable daily change must serialize as null, not 0.0.

Bug (AUTOPILOT_BACKLOG 2026-07-12 P1): `_etf_snapshot` initialised
`change_pct = 0.0` and only overwrote it when the price history had >=2 closes.
When the live quote succeeded but history came back empty (or was discarded by
the 30% staleness guard), the snapshot still returned — carrying a fabricated
`change_1d_pct: 0.0`. QQQ/DIA/IWM/VIXY rendered a confident "+0.00%" that was
never observed, while SPY (whose history worked) showed a real number.

Same contract as `range_52w`, which already nulls out when it cannot be
trusted: the frontend maps null to "—" (lib/format.ts::fmtPct).
"""

import pytest

import services.data.indices as market       # _etf_snapshot lives here
import routes.market as market_routes        # the view function does not


class _StubFetcher:
    """Live quote succeeds, history is unavailable — the exact failing shape."""

    def __init__(self, price=None, history=None):
        self._price = price
        self._history = history

    def quick_lookup(self, ticker):
        return {"price": self._price} if self._price is not None else None

    def get_price_history(self, ticker, period="1y"):
        return self._history


@pytest.fixture
def stub_fetcher(monkeypatch):
    def _install(price=None, history=None):
        f = _StubFetcher(price, history)
        monkeypatch.setattr(market, "fetcher", f, raising=False)
        return f
    return _install


def test_etf_snapshot_nulls_change_when_history_missing(stub_fetcher):
    stub_fetcher(price=725.51, history=None)
    snap = market._etf_snapshot("QQQ", "^IXIC", "NASDAQ 100")
    assert snap is not None, "a live level alone should still render a row"
    assert snap["level"] == 725.51
    assert snap["change_1d_pct"] is None, (
        "history was unavailable — the daily change is unknown and must not "
        "be fabricated as 0.0"
    )


def test_etf_snapshot_nulls_change_on_single_close(stub_fetcher):
    pd = pytest.importorskip("pandas")
    stub_fetcher(price=754.95, history=pd.DataFrame({"Close": [754.95]}))
    snap = market._etf_snapshot("SPY", "^GSPC", "S&P 500")
    assert snap is not None
    assert snap["change_1d_pct"] is None, "one close cannot yield a d/d change"


def test_etf_snapshot_reports_a_real_change(stub_fetcher):
    pd = pytest.importorskip("pandas")
    stub_fetcher(price=101.0, history=pd.DataFrame({"Close": [100.0, 101.0]}))
    snap = market._etf_snapshot("SPY", "^GSPC", "S&P 500")
    assert snap is not None
    assert snap["change_1d_pct"] == pytest.approx(1.0)


def test_genuine_zero_change_is_preserved(stub_fetcher):
    """A real flat session stays 0.0 — only *unknown* becomes null."""
    pd = pytest.importorskip("pandas")
    stub_fetcher(price=100.0, history=pd.DataFrame({"Close": [100.0, 100.0]}))
    snap = market._etf_snapshot("SPY", "^GSPC", "S&P 500")
    assert snap is not None
    assert snap["change_1d_pct"] == 0.0


def test_no_level_still_returns_none(stub_fetcher):
    stub_fetcher(price=None, history=None)
    assert market._etf_snapshot("QQQ", "^IXIC", "NASDAQ 100") is None


def test_direction_helper_tolerates_null():
    """`_direction` runs on the possibly-null change in the public snapshot."""
    import inspect
    src = inspect.getsource(market_routes.public_market_snapshot)
    assert 'snap.get("change_1d_pct", 0.0) or 0.0' not in src, (
        "the public snapshot must not coerce an unknown change back to 0.0"
    )
