"""Static fallback data for /api/discover/* endpoints.

Used when FMP/KIS upstream returns 402/5xx. Observation language only —
no BUY/SELL/recommend/advice/bullish/bearish/forecast.
"""

# Market overview — 5 headline indices
MARKET_OVERVIEW = [
    {"name": "S&P 500",  "symbol": "^GSPC", "level": 5218.42, "change_pct":  0.31},
    {"name": "Nasdaq",   "symbol": "^IXIC", "level": 16342.18, "change_pct":  0.58},
    {"name": "Dow",      "symbol": "^DJI",  "level": 38912.55, "change_pct": -0.12},
    {"name": "KOSPI",    "symbol": "^KS11", "level":  2612.34, "change_pct":  0.42},
    {"name": "KOSDAQ",   "symbol": "^KQ11", "level":   847.91, "change_pct": -0.18},
]

# US Movers — top 10 gainers / losers
US_GAINERS = [
    {"ticker": "NVDA", "name": "NVIDIA",          "price":  918.42, "change_pct":  4.62},
    {"ticker": "AVGO", "name": "Broadcom",        "price": 1312.10, "change_pct":  3.84},
    {"ticker": "AMD",  "name": "AMD",             "price":  162.35, "change_pct":  3.15},
    {"ticker": "MU",   "name": "Micron",          "price":  118.70, "change_pct":  2.91},
    {"ticker": "ASML", "name": "ASML",            "price": 1024.50, "change_pct":  2.76},
    {"ticker": "TSM",  "name": "TSMC",            "price":  142.85, "change_pct":  2.41},
    {"ticker": "SMCI", "name": "Super Micro",     "price":  842.10, "change_pct":  2.18},
    {"ticker": "ARM",  "name": "Arm Holdings",    "price":  108.24, "change_pct":  2.04},
    {"ticker": "PLTR", "name": "Palantir",        "price":   24.80, "change_pct":  1.92},
    {"ticker": "CRWD", "name": "CrowdStrike",     "price":  312.40, "change_pct":  1.81},
]

US_LOSERS = [
    {"ticker": "BA",   "name": "Boeing",          "price":  184.20, "change_pct": -3.84},
    {"ticker": "LUV",  "name": "Southwest Air",   "price":   28.14, "change_pct": -2.92},
    {"ticker": "F",    "name": "Ford",            "price":   12.48, "change_pct": -2.64},
    {"ticker": "GM",   "name": "GM",              "price":   42.30, "change_pct": -2.41},
    {"ticker": "WBA",  "name": "Walgreens",       "price":   18.92, "change_pct": -2.18},
    {"ticker": "TGT",  "name": "Target",          "price":  162.40, "change_pct": -1.95},
    {"ticker": "INTC", "name": "Intel",           "price":   34.20, "change_pct": -1.82},
    {"ticker": "PFE",  "name": "Pfizer",          "price":   26.18, "change_pct": -1.74},
    {"ticker": "VZ",   "name": "Verizon",         "price":   40.12, "change_pct": -1.62},
    {"ticker": "T",    "name": "AT&T",            "price":   17.48, "change_pct": -1.41},
]

# KR Movers — format .KS
KR_GAINERS = [
    {"ticker": "005930.KS", "name": "Samsung Electronics",  "price":  78400, "change_pct": 2.35},
    {"ticker": "000660.KS", "name": "SK Hynix",              "price": 184500, "change_pct": 1.92},
    {"ticker": "035420.KS", "name": "NAVER",                 "price": 218000, "change_pct": 1.64},
    {"ticker": "207940.KS", "name": "Samsung Biologics",     "price": 812000, "change_pct": 1.28},
    {"ticker": "051910.KS", "name": "LG Chem",               "price": 382500, "change_pct": 1.04},
    {"ticker": "005380.KS", "name": "Hyundai Motor",         "price": 248000, "change_pct": 0.92},
    {"ticker": "006400.KS", "name": "Samsung SDI",           "price": 418500, "change_pct": 0.78},
    {"ticker": "028260.KS", "name": "Samsung C&T",           "price": 142000, "change_pct": 0.64},
    {"ticker": "035720.KS", "name": "Kakao",                 "price":  48200, "change_pct": 0.52},
    {"ticker": "105560.KS", "name": "KB Financial",          "price":  74200, "change_pct": 0.38},
]

KR_LOSERS = [
    {"ticker": "373220.KS", "name": "LG Energy Solution",    "price": 342500, "change_pct": -2.18},
    {"ticker": "068270.KS", "name": "Celltrion",             "price": 186500, "change_pct": -1.42},
    {"ticker": "012330.KS", "name": "Hyundai Mobis",         "price": 224500, "change_pct": -1.18},
    {"ticker": "055550.KS", "name": "Shinhan Financial",     "price":  48600, "change_pct": -0.98},
    {"ticker": "096770.KS", "name": "SK Innovation",         "price": 108200, "change_pct": -0.84},
    {"ticker": "032830.KS", "name": "Samsung Life",          "price":  82400, "change_pct": -0.72},
    {"ticker": "017670.KS", "name": "SK Telecom",            "price":  52100, "change_pct": -0.64},
    {"ticker": "086790.KS", "name": "Hana Financial",        "price":  62800, "change_pct": -0.52},
    {"ticker": "066570.KS", "name": "LG Electronics",        "price":  92400, "change_pct": -0.38},
    {"ticker": "015760.KS", "name": "KEPCO",                 "price":  22850, "change_pct": -0.24},
]

# 11 GICS sectors — 1D / 5D / 1M % change
SECTORS = [
    {"sector": "Information Technology",    "d1":  0.84, "d5":  2.41, "m1":  4.62},
    {"sector": "Communication Services",    "d1":  0.62, "d5":  1.82, "m1":  3.14},
    {"sector": "Consumer Discretionary",    "d1":  0.38, "d5":  1.24, "m1":  2.18},
    {"sector": "Financials",                "d1":  0.21, "d5":  0.84, "m1":  1.62},
    {"sector": "Industrials",               "d1":  0.14, "d5":  0.42, "m1":  0.94},
    {"sector": "Health Care",               "d1": -0.08, "d5": -0.12, "m1":  0.32},
    {"sector": "Consumer Staples",          "d1": -0.12, "d5": -0.34, "m1": -0.18},
    {"sector": "Materials",                 "d1": -0.24, "d5": -0.62, "m1": -0.84},
    {"sector": "Real Estate",               "d1": -0.38, "d5": -0.92, "m1": -1.42},
    {"sector": "Utilities",                 "d1": -0.42, "d5": -1.14, "m1": -1.82},
    {"sector": "Energy",                    "d1": -0.62, "d5": -1.84, "m1": -2.41},
]

# Thematic screeners
OVERSOLD_RSI = [
    {"ticker": "PFE",  "name": "Pfizer",      "metric": "RSI",   "metric_value": "27.4"},
    {"ticker": "T",    "name": "AT&T",        "metric": "RSI",   "metric_value": "28.8"},
    {"ticker": "VZ",   "name": "Verizon",     "metric": "RSI",   "metric_value": "29.1"},
    {"ticker": "WBA",  "name": "Walgreens",   "metric": "RSI",   "metric_value": "29.6"},
    {"ticker": "INTC", "name": "Intel",       "metric": "RSI",   "metric_value": "30.2"},
    {"ticker": "NKE",  "name": "Nike",        "metric": "RSI",   "metric_value": "30.8"},
    {"ticker": "MMM",  "name": "3M",          "metric": "RSI",   "metric_value": "31.4"},
    {"ticker": "TGT",  "name": "Target",      "metric": "RSI",   "metric_value": "31.9"},
]

HIGHS_52W = [
    {"ticker": "NVDA", "name": "NVIDIA",      "metric": "52W High", "metric_value": "$918.42"},
    {"ticker": "MSFT", "name": "Microsoft",   "metric": "52W High", "metric_value": "$428.15"},
    {"ticker": "META", "name": "Meta",        "metric": "52W High", "metric_value": "$512.80"},
    {"ticker": "AVGO", "name": "Broadcom",    "metric": "52W High", "metric_value": "$1,312.10"},
    {"ticker": "GOOG", "name": "Alphabet",    "metric": "52W High", "metric_value": "$172.40"},
    {"ticker": "LLY",  "name": "Eli Lilly",   "metric": "52W High", "metric_value": "$784.20"},
    {"ticker": "JPM",  "name": "JPMorgan",    "metric": "52W High", "metric_value": "$201.34"},
    {"ticker": "V",    "name": "Visa",        "metric": "52W High", "metric_value": "$284.60"},
]

EARNINGS_BEATS = [
    {"ticker": "NFLX", "name": "Netflix",          "metric": "EPS surprise", "metric_value": "+14.2%"},
    {"ticker": "UNH",  "name": "UnitedHealth",     "metric": "EPS surprise", "metric_value":  "+8.4%"},
    {"ticker": "BAC",  "name": "Bank of America",  "metric": "EPS surprise", "metric_value":  "+6.8%"},
    {"ticker": "JNJ",  "name": "Johnson & Johnson","metric": "EPS surprise", "metric_value":  "+5.2%"},
    {"ticker": "UAL",  "name": "United Airlines",  "metric": "EPS surprise", "metric_value":  "+4.6%"},
    {"ticker": "MS",   "name": "Morgan Stanley",   "metric": "EPS surprise", "metric_value":  "+3.8%"},
]


# ── Market indices (for /api/market/indices) ──

def _sparkline(base: float, amp: float, seed: int) -> list[float]:
    """Deterministic 30-point wobble anchored at base."""
    import math
    return [
        round(base + math.sin((i + seed) / 3.1) * amp
                   + math.cos((i + seed) / 4.7) * amp * 0.6, 4)
        for i in range(30)
    ]


# NOTE: These snapshots are no longer consumed by /api/market/indices as of
# 2026-04-22 — that route now uses Alpaca ETF proxies (SPY/QQQ/DIA/IWM/VIXY)
# with the failing-ticker-skip strategy. Kept only as a schema reference and
# for potential future consumers; values are ETF-native (not raw index
# levels) and flagged is_mock=True so callers know not to trust them.
US_MARKET_INDICES = [
    {"ticker": "^GSPC", "proxy_ticker": "SPY", "name": "S&P 500",      "level":  708.53, "change_1d_pct":  0.00,
     "range_52w": [480.00, 715.00], "sparkline_30d": _sparkline(700, 4, 1),  "is_mock": True},
    {"ticker": "^IXIC", "proxy_ticker": "QQQ", "name": "Nasdaq 100",   "level":  649.30, "change_1d_pct":  0.00,
     "range_52w": [420.00, 660.00], "sparkline_30d": _sparkline(645, 5, 2),  "is_mock": True},
    {"ticker": "^DJI",  "proxy_ticker": "DIA", "name": "Dow Jones",    "level":  494.50, "change_1d_pct":  0.00,
     "range_52w": [360.00, 500.00], "sparkline_30d": _sparkline(490, 3, 3),  "is_mock": True},
    {"ticker": "^RUT",  "proxy_ticker": "IWM", "name": "Russell 2000", "level":  277.00, "change_1d_pct":  0.00,
     "range_52w": [185.00, 285.00], "sparkline_30d": _sparkline(275, 2, 4),  "is_mock": True},
    {"ticker": "^VIX",  "proxy_ticker": "VIXY","name": "Volatility (VIXY)", "level": 27.98, "change_1d_pct": 0.00,
     "range_52w": [22.00, 48.00], "sparkline_30d": _sparkline(28, 1, 5),     "is_mock": True},
]

KR_MARKET_INDICES = [
    {"ticker": "^KS11",    "name": "KOSPI",       "level":  6417.93, "change_1d_pct": 0.00,
     "range_52w": [0.0, 0.0], "sparkline_30d": [], "is_mock": True},
    {"ticker": "^KQ11",    "name": "KOSDAQ",      "level":  1181.12, "change_1d_pct": 0.00,
     "range_52w": [0.0, 0.0], "sparkline_30d": [], "is_mock": True},
    {"ticker": "USDKRW",   "name": "USD / KRW",   "level":  1350.00, "change_1d_pct": 0.00,
     "range_52w": [0.0, 0.0], "sparkline_30d": [], "is_mock": True},
]

KR_DERIVATIVES = [
    {"label": "KOSPI 200 Futures (front month)", "value":  "356.45", "note": "basis +1.25 vs spot"},
    {"label": "KOSPI 200 Call OI (ATM)",         "value":  "42,184", "note": "strike 355"},
    {"label": "KOSPI 200 Put OI (ATM)",          "value":  "38,902", "note": "strike 355"},
    {"label": "V-KOSPI (implied vol)",           "value":   "14.62", "note": "-0.18 vs yesterday"},
]
