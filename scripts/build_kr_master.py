"""Build KRX stock master JSON for offline search.

Downloads the full KOSPI + KOSDAQ ticker list (~2,500 names) via pykrx
and writes services/kr_stocks_data.json. Run once at build time; the
runtime registry loads the JSON.
"""
import json
import os
import sys
import time
from datetime import datetime, timedelta

from pykrx import stock


def _try_dates():
    """Try today, then walk back up to 7 days for a valid trading day."""
    base = datetime.now()
    return [(base - timedelta(days=i)).strftime("%Y%m%d") for i in range(8)]


def fetch_market(market: str, suffix: str) -> dict:
    """Return {f'{code}{suffix}': {name, market}} for given market."""
    out = {}
    codes = []
    used_date = None
    for d in _try_dates():
        try:
            codes = stock.get_market_ticker_list(d, market=market)
            if codes:
                used_date = d
                break
        except Exception as e:
            print(f"  {market} @ {d}: {e}")
            continue
    print(f"  {market}: {len(codes)} tickers (date={used_date})")

    for code in codes:
        try:
            name = stock.get_market_ticker_name(code)
            if not name:
                continue
            ticker = f"{code}{suffix}"
            out[ticker] = {"name": name, "market": market}
        except Exception as e:
            print(f"  Skip {code}: {e}")
            continue
    return out


def main():
    t0 = time.time()
    result = {}

    for market, suffix in [("KOSPI", ".KS"), ("KOSDAQ", ".KQ")]:
        print(f"Fetching {market}...")
        result.update(fetch_market(market, suffix))

    print(f"Total: {len(result)} tickers")

    out_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "services",
        "kr_stocks_data.json",
    )
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    size_kb = os.path.getsize(out_path) / 1024.0
    print(f"Saved to {out_path} ({size_kb:.1f} KB)")
    print(f"Elapsed: {time.time() - t0:.1f}s")

    if len(result) < 1500:
        print("WARN: ticker count below 1500, possible failure")
        sys.exit(2)


if __name__ == "__main__":
    main()
