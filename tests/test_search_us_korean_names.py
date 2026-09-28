"""/api/search — US stocks by their Korean name, and without FMP.

Korean broker apps print US stocks in Korean ("뉴스케일파워"); a user fixing an
unresolved capture row types what they see. And with FMP down, the search
must still find any US symbol, not only the 40 popular ones.
"""
from __future__ import annotations


def _tickers(client, q):
    r = client.get(f"/api/search?q={q}")
    assert r.status_code == 200, r.get_json()
    return [h["ticker"] for h in r.get_json()["results"]]


def test_korean_name_finds_us_stock(client, auth_user, monkeypatch):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    assert "SMR" in _tickers(client, "뉴스케일파워")
    assert "SMR" in _tickers(client, "뉴스케일")
    assert "JOBY" in _tickers(client, "조비 에비에이션")


def test_us_symbol_and_english_name_without_fmp(client, auth_user, monkeypatch):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    assert "SMR" in _tickers(client, "SMR")
    assert "SMR" in _tickers(client, "nuscale")
    assert "ABTC" in _tickers(client, "ABTC")


def test_korean_stock_search_unchanged(client, auth_user, monkeypatch):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    assert _tickers(client, "삼성전자")[0] == "005930.KS"
