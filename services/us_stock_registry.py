"""
PivoxQuant — US Stock Registry (Alpaca asset master)

Loads all tradable US stocks (~12,700) from us_stocks_data.json,
generated via Alpaca get_all_assets() at build time.
Schema: {symbol: {"name": str, "exchange": str}}.

Usage:
  - search(query): fuzzy match against symbol + company name
  - get_name(symbol): company name lookup
"""

import json as _json
import os as _os

_DATA_PATH = _os.path.join(_os.path.dirname(__file__), "us_stocks_data.json")

try:
    with open(_DATA_PATH, "r", encoding="utf-8") as _f:
        US_STOCKS: dict[str, dict] = _json.load(_f)
except FileNotFoundError:
    US_STOCKS = {}


def search(query: str, limit: int = 15) -> list[dict]:
    """Return matching US stocks for a query string.

    Matches against symbol (case-insensitive) and company name (substring).
    Symbol exact match has highest priority, then symbol prefix, then name.
    """
    q = (query or "").strip()
    if not q:
        return []
    qu = q.upper()
    ql = q.lower()

    exact: list[dict] = []
    prefix: list[dict] = []
    name_match: list[dict] = []

    for symbol, info in US_STOCKS.items():
        name = info.get("name", "")
        rec = {
            "ticker":   symbol,
            "name":     name,
            "exchange": info.get("exchange", ""),
            "currency": "USD",
            "is_korean": False,
        }
        if symbol == qu:
            exact.append(rec)
        elif symbol.startswith(qu):
            prefix.append(rec)
        elif ql in name.lower():
            name_match.append(rec)

    results = exact + prefix + name_match
    return results[:limit]


def get_name(symbol: str) -> "str | None":
    """Return company name for a symbol, else None."""
    entry = US_STOCKS.get(symbol.upper())
    return entry.get("name") if entry else None
