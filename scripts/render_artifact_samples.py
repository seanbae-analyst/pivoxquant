#!/usr/bin/env python3
"""Render all 17 PivoxQuant Artifact templates with mock data for CEO review.

Produces both the rendered HTML under `samples/artifacts/` and, when
WeasyPrint is available, a companion PDF under `samples/pdf/`. The PDF
suite is the canonical output for the Goldman Sachs CFO-grade visual QA.

Run from repo root (venv with weasyprint installed):
    venv/bin/python scripts/render_artifact_samples.py
"""
from __future__ import annotations

import datetime as _dt
import sys as _sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


REPO_ROOT = Path(__file__).resolve().parents[1]
# Running `python scripts/render_artifact_samples.py` puts scripts/ (not the
# repo root) on sys.path, so `import services.*` fails. Add the repo root so the
# harness can reuse the real sample_data SoT + service shapers + name enrichment
# (without this, the enrich/reshape steps silently no-op and samples drift).
if str(REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(REPO_ROOT))
TEMPLATE_DIR = REPO_ROOT / "services" / "artifacts" / "templates"
OUT_DIR = REPO_ROOT / "samples" / "artifacts"
PDF_DIR = REPO_ROOT / "samples" / "pdf"
OUT_DIR.mkdir(parents=True, exist_ok=True)
PDF_DIR.mkdir(parents=True, exist_ok=True)


import shutil as _shutil
import subprocess as _subprocess


def _try_import_weasyprint():
    try:
        from weasyprint import HTML  # type: ignore
        return HTML
    except Exception as exc:  # pragma: no cover
        print(f"[info] WeasyPrint unavailable ({exc}); trying Chrome headless fallback.")
        return None


def _find_chrome() -> str | None:
    """Locate Chrome/Chromium for headless PDF print. WeasyPrint stand-in."""
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        _shutil.which("google-chrome"),
        _shutil.which("chromium"),
        _shutil.which("chromium-browser"),
    ]
    for c in candidates:
        if c and Path(c).exists():
            return c
    return None


def _render_pdf_chrome(chrome_bin: str, html_path: Path, pdf_path: Path) -> None:
    """Print an HTML file to PDF via headless Chrome.

    Uses --no-pdf-header-footer so the template's own @page headers/footers
    (the Goldman-grade masthead, page counter, masthead rule) are rendered
    without Chrome overlaying its own URL/title.
    """
    # Flags tuned for deterministic font embedding:
    #   --font-render-hinting=none  → subpixel-stable glyphs
    #   --disable-web-security      → allow file:// + data: URLs without CORS
    #   --run-all-compositor-stages-before-draw + --virtual-time-budget
    #                               → wait for @font-face data: URLs to parse
    #   --no-pdf-header-footer      → keep template header/footer only
    cmd = [
        chrome_bin,
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        "--no-sandbox",
        "--disable-web-security",
        "--font-render-hinting=none",
        "--run-all-compositor-stages-before-draw",
        "--virtual-time-budget=15000",
        f"--print-to-pdf={pdf_path}",
        f"file://{html_path.resolve()}",
    ]
    _subprocess.run(cmd, check=True, capture_output=True, timeout=120)


# ─── Mock data pool ──────────────────────────────────────────────────────────

USER_NAME = "배상현"
GENERATED_AT = "2026-04-19 07:32 KST"
PERIOD_START = "2026-04-13"
PERIOD_END = "2026-04-19"

MOVERS_UP = [
    {"ticker": "NVDA", "weekly_return_pct": 8.24},
    {"ticker": "AVGO", "weekly_return_pct": 5.11},
    {"ticker": "TSM",  "weekly_return_pct": 3.92},
]
MOVERS_DOWN = [
    {"ticker": "TSLA", "weekly_return_pct": -4.87},
    {"ticker": "NKE",  "weekly_return_pct": -3.14},
    {"ticker": "KO",   "weekly_return_pct": -1.22},
]

SECTOR_ALLOC = {
    "Information Technology": 32.5,
    "Consumer Discretionary": 18.1,
    "Financials": 14.0,
    "Health Care": 11.8,
    "Communication Services": 9.4,
    "Energy": 5.1,
    "Industrials": 4.8,
    "Consumer Staples": 2.3,
    "Real Estate": 1.4,
    "Utilities": 0.6,
}
SECTOR_CHANGES = [
    {"sector": s, "current": v, "previous": round(v * 0.95, 1),
     "delta_pp": round(v * 0.05, 2)}
    for s, v in list(SECTOR_ALLOC.items())[:6]
]

MACRO_CHECKLIST = [
    {"label": "CPI YoY", "value": 3.12, "units": "%",  "pct_change": -0.08, "date": "2026-04-10"},
    {"label": "Fed Funds Upper", "value": 5.50, "units": "%", "pct_change": 0.00, "date": "2026-04-15"},
    {"label": "UST 10Y", "value": 4.41, "units": "%", "pct_change": 0.12, "date": "2026-04-19"},
    {"label": "DXY", "value": 105.22, "units": "idx", "pct_change": -0.22, "date": "2026-04-19"},
]

EARNINGS_CALENDAR = [
    {"date": "2026-04-22", "ticker": "MSFT", "time": "AMC"},
    {"date": "2026-04-23", "ticker": "META", "time": "AMC"},
    {"date": "2026-04-24", "ticker": "AMZN", "time": "AMC"},
]


# ─── Sample context per template ─────────────────────────────────────────────

_SP500_BACKTEST_CTX = {
    "issue_number": 1,
    "doc_ref": "PQ-BT-01 · v2026.04.21",
    "generated_at": "2026-04-21",
    "period_start": "2021-12-01",
    "period_end": "2026-04-17",
    "typeset_in": "Source Serif 4 · Geist · JetBrains Mono",
    "LICENSE_NUMBER": None,
    "hero_headline": [
        "Four years, four hundred names.",
        "One rule, measured in the open.",
        "Observations — historical, not forward-looking.",
    ],
    "hero_cagr": 21.19,
    "hero_sharpe": 0.94,
    "hero_alpha": 9.66,
    "hero_2022_spread": 23.2,
    "equity_series": [
        {"x": "2021-12", "y": 100000},
        {"x": "2022-04", "y": 103200},
        {"x": "2022-10", "y": 104600},
        {"x": "2023-04", "y": 115100},
        {"x": "2023-10", "y": 132200},
        {"x": "2024-04", "y": 151800},
        {"x": "2024-10", "y": 169600},
        {"x": "2025-04", "y": 188900},
        {"x": "2025-10", "y": 205100},
        {"x": "2026-04", "y": 218240},
    ],
    "benchmark_series": [
        {"x": "2021-12", "y": 100000},
        {"x": "2022-04", "y":  92400},
        {"x": "2022-10", "y":  81400},
        {"x": "2023-04", "y":  92100},
        {"x": "2023-10", "y": 101100},
        {"x": "2024-04", "y": 119800},
        {"x": "2024-10", "y": 131200},
        {"x": "2025-04", "y": 143600},
        {"x": "2025-10", "y": 147900},
        {"x": "2026-04", "y": 151100},
    ],
    "bear_band_start": 1,
    "bear_band_end":   2,
    "annual_rows": [
        {"year": "2022",     "strategy":  4.6, "spy": -18.6, "alpha": 23.2, "mdd": -19.8, "sharpe": 0.72,
         "spark": [0, -1.2, -2.8, -1.1, 1.4, 2.1, 3.2, 4.0, 4.6]},
        {"year": "2023",     "strategy": 26.4, "spy":  24.2, "alpha":  2.2, "mdd":  -8.1, "sharpe": 1.24,
         "spark": [0, 2.8, 5.1, 9.4, 12.2, 16.8, 19.1, 22.4, 26.4]},
        {"year": "2024",     "strategy": 28.1, "spy":  23.3, "alpha":  4.8, "mdd":  -9.4, "sharpe": 1.18,
         "spark": [0, 3.4, 7.8, 11.2, 14.8, 18.2, 21.8, 24.9, 28.1]},
        {"year": "2025",     "strategy": 22.7, "spy":  12.8, "alpha":  9.9, "mdd": -13.2, "sharpe": 0.98,
         "spark": [0, 1.8, 4.4, 7.1, 10.8, 14.2, 17.8, 20.4, 22.7]},
        {"year": "YTD 2026", "strategy":  6.3, "spy":   2.1, "alpha":  4.2, "mdd":  -6.4, "sharpe": 0.88,
         "spark": [0, 1.2, 2.4, 3.8, 4.9, 5.6, 6.0, 6.2, 6.3]},
    ],
    "corr_labels": ["Strategy C", "SPY", "QQQ", "TLT", "Gold", "VIX"],
    "corr_matrix": [
        [ 1.00,  0.78,  0.74, -0.12,  0.18, -0.42],
        [ 0.78,  1.00,  0.92, -0.32,  0.08, -0.68],
        [ 0.74,  0.92,  1.00, -0.28,  0.04, -0.62],
        [-0.12, -0.32, -0.28,  1.00,  0.22,  0.14],
        [ 0.18,  0.08,  0.04,  0.22,  1.00, -0.08],
        [-0.42, -0.68, -0.62,  0.14, -0.08,  1.00],
    ],
    "rolling_sharpe": [0.42, 0.58, 0.71, 0.68, 0.82, 0.94, 1.12, 1.24, 1.18, 1.02, 0.98, 0.88, 0.94],
    "underwater": [
        0, -2.1, -8.4, -14.2, -19.6, -23.82, -18.4, -11.2, -4.8, 0,
        -3.2, -8.1, -4.4, 0, -2.8, -6.1, -9.4, -4.8, 0, -5.2,
        -11.4, -13.2, -6.8, 0, -3.4, -6.4,
    ],
    "histogram_bins": [
        {"edge": -15, "count":  0}, {"edge": -12, "count":  1}, {"edge":  -9, "count":  2},
        {"edge":  -6, "count":  4}, {"edge":  -3, "count":  6}, {"edge":   0, "count":  8},
        {"edge":   3, "count": 12}, {"edge":   6, "count": 10}, {"edge":   9, "count":  6},
        {"edge":  12, "count":  3}, {"edge":  15, "count":  1},
    ],
    "empirical_dist": [
        {"x": -15, "y":  0.1}, {"x": -12, "y":  0.4}, {"x":  -9, "y":  1.2},
        {"x":  -6, "y":  3.4}, {"x":  -3, "y":  6.8}, {"x":   0, "y":  9.2},
        {"x":   3, "y": 11.8}, {"x":   6, "y":  9.4}, {"x":   9, "y":  5.8},
        {"x":  12, "y":  2.8}, {"x":  15, "y":  0.9},
    ],
    "normal_dist": [
        {"x": -15, "y":  0.3}, {"x": -12, "y":  0.9}, {"x":  -9, "y":  2.4},
        {"x":  -6, "y":  4.6}, {"x":  -3, "y":  7.4}, {"x":   0, "y":  9.6},
        {"x":   3, "y": 10.1}, {"x":   6, "y":  8.2}, {"x":   9, "y":  4.9},
        {"x":  12, "y":  2.1}, {"x":  15, "y":  0.6},
    ],
    "pull_quote": "A backtest is a memoir of markets past — not a map of markets to come.",
    "pull_quote_attribution": "PivoxQuant Research Desk",
    "limits_left": [
        {"n": "01", "text": "Tax drag on realised gains — the record is pre-tax."},
        {"n": "02", "text": "Personal withdrawals or deposits that alter the compounding path."},
        {"n": "03", "text": "Slippage in thinly-traded constituents beyond the 10 bps assumption."},
    ],
    "limits_right": [
        {"n": "04", "text": "Regime shifts not present in the observation window — the next four years are not the last four."},
        {"n": "05", "text": "Live execution latency and partial fills, which the monthly-close record cannot see."},
    ],
}


SAMPLES: dict[str, dict] = {
    "sp500_backtest.html": _SP500_BACKTEST_CTX,
    "weekly_memo.html": {
        "week_number": 16, "year": "2026",
        "user_name": USER_NAME,
        "period_start": PERIOD_START, "period_end": PERIOD_END,
        "generated_at": GENERATED_AT,
        "weekly_return_pct": 2.41,
        "benchmark_pct": 1.12, "alpha_pct": 1.29,
        "top_movers_up": [
            {"ticker": "NVDA", "weekly_return_pct": 8.24,
             "trend_7d": [0.0, 1.1, 2.8, 3.4, 5.6, 7.0, 8.24]},
            {"ticker": "AVGO", "weekly_return_pct": 5.11,
             "trend_7d": [0.0, 0.6, 1.8, 2.4, 3.1, 4.2, 5.11]},
            {"ticker": "TSM",  "weekly_return_pct": 3.92,
             "trend_7d": [0.0, 0.3, 1.0, 1.9, 2.3, 3.1, 3.92]},
        ],
        "top_movers_down": [
            {"ticker": "TSLA", "weekly_return_pct": -4.87,
             "trend_7d": [0.0, -0.4, -1.2, -2.1, -3.0, -4.1, -4.87]},
            {"ticker": "NKE",  "weekly_return_pct": -3.14,
             "trend_7d": [0.0, -0.2, -0.9, -1.4, -2.2, -2.7, -3.14]},
        ],
        "sector_alloc": SECTOR_ALLOC,
        "sector_changes": SECTOR_CHANGES,
        "macro_checklist": MACRO_CHECKLIST,
        "risk_notes": [
            "포트폴리오 섹터 1위(IT)의 비중이 32.5% → 단일 섹터 집중도 관찰 구간 진입.",
            "VIX 주간 고점 18.4로 3주 연속 상승 — 변동성 관찰 구간 유지.",
            "KO 3주 연속 하락(-1.2% · -2.1% · -3.3%) — 개별 종목 관찰 플래그.",
        ],
        "earnings_calendar": EARNINGS_CALENDAR,
        "disclaimer": "참고용 자료입니다. 매매 권유가 아닙니다.",
        "LICENSE_NUMBER": None,
        # Flagship narrative & chart inputs (empty-safe fallbacks in template).
        "narrative_exec_line": (
            "A week where US semis carried the book, and the S&P drift "
            "politely cooperated — the spread landed in the positive half of "
            "its ninety-day distribution for the third week running."
        ),
        "narrative_week_summary": [
            (
                "The book advanced 2.41% against the S&P 500's 1.12%, "
                "settling alpha at +1.29 percentage points. Read "
                "descriptively, this is the third consecutive week the "
                "spread has landed in the positive half of its ninety-day "
                "distribution."
            ),
            (
                "The heavy lifting came from NVDA (+8.24%) and AVGO (+5.11%). "
                "The laggards — TSLA and NKE — declined in sympathy with "
                "cohort softness rather than name-specific catalysts on the "
                "calendar."
            ),
            (
                "The observation worth naming is concentration: Information "
                "Technology sits at 32.5% of invested capital — above the "
                "thirty-percent guide for the fourth straight week."
            ),
        ],
        "narrative_what_next": (
            "The next seven days carry three scheduled earnings prints from "
            "the held book — MSFT on day two, META on day three, AMZN on day "
            "four. The desk tracks these against the same tail bands that "
            "framed this week, not against a projection."
        ),
        "equity_series": [
            {"x": "D1", "y":  0.00},
            {"x": "D2", "y":  0.48},
            {"x": "D3", "y":  1.10},
            {"x": "D4", "y":  1.68},
            {"x": "D5", "y":  2.02},
            {"x": "D6", "y":  2.24},
            {"x": "D7", "y":  2.41},
        ],
        "benchmark_series": [
            {"x": "D1", "y":  0.00},
            {"x": "D2", "y":  0.18},
            {"x": "D3", "y":  0.46},
            {"x": "D4", "y":  0.74},
            {"x": "D5", "y":  0.91},
            {"x": "D6", "y":  1.02},
            {"x": "D7", "y":  1.12},
        ],
        "equity_x_labels": ["Mon", "Tue", "Wed", "Thu", "Fri", "Mon", "Tue"],
        "daily_walk_rows": [
            {"label": "Mon", "value":  0.48, "tone": "pos"},
            {"label": "Tue", "value":  0.62, "tone": "pos"},
            {"label": "Wed", "value":  0.58, "tone": "pos"},
            {"label": "Thu", "value":  0.34, "tone": "pos"},
            {"label": "Fri", "value": -0.22, "tone": "neg"},
            {"label": "Mon", "value":  0.22, "tone": "pos"},
            {"label": "Tue", "value":  0.39, "tone": "pos"},
        ],
        "risk_metrics": [
            {"label": "VaR 95%",                    "value": "-2.12%",
             "gloss": "The loss the book was historically exceeded by on only 5% of daily sessions, based on the last 90 trading days of close-to-close returns."},
            {"label": "Expected Shortfall (ES 95%)", "value": "-3.48%",
             "gloss": "The mean loss on the worst 5% of historical days — the tail the VaR line does not see."},
            {"label": "Tail Ratio",                  "value": "1.08",
             "gloss": "Ratio of the 95th to the 5th return percentile. Above one suggests the right tail is doing more work than the left."},
            {"label": "Sortino · annualised",        "value": "1.96",
             "gloss": "Return per unit of downside deviation. Higher readings indicate the book asymmetrically tolerates upside volatility."},
            {"label": "Max Drawdown · 12-week",      "value": "-8.14%",
             "gloss": "Largest peak-to-trough decline in the last twelve weeks of marked prices."},
        ],
        "corr_matrix": [
            [1.00, 0.62, 0.41, 0.28, 0.18],
            [0.62, 1.00, 0.58, 0.22, 0.14],
            [0.41, 0.58, 1.00, 0.33, 0.20],
            [0.28, 0.22, 0.33, 1.00, 0.51],
            [0.18, 0.14, 0.20, 0.51, 1.00],
        ],
        "corr_labels": ["NVDA", "AVGO", "TSM", "TSLA", "NKE"],
    },

    "earnings_prebrief.html": {
        # Goldman IC v2 editorial — 6-page pre-read brief.
        # Source of truth: services.artifacts.sample_data.sample_earnings_prebrief().
        "user_name":     USER_NAME,
        "ticker":        "AAPL",
        "company_name":  "Apple Inc.",
        "fiscal_period": "Q2 FY26",
        "reporting_date":  "2026-04-30",
        "reporting_time":  "After the close (AMC)",
        "issue_number":  1,
        "doc_ref":       "PQ-EB-01 · v2026.04.21",
        "generated_at":  GENERATED_AT,
        "typeset_in":    "Source Serif 4 · Geist · JetBrains Mono",
        "engine_note":   "58 quant models · 7-Layer Risk Defense",
        "LICENSE_NUMBER": None,

        # P1 cover KPIs
        "consensus_eps":      1.62,
        "consensus_eps_low":  1.48,
        "consensus_eps_high": 1.76,
        "implied_move_pct":   4.2,
        "consensus_as_of":    "2026-04-19",
        "option_as_of":       "2026-04-20",
        "hero_headline": [
            "A quiet hour before the call.",
            "Facts observed. Calendar noted.",
            "The company will speak — we listen.",
        ],

        # P2 company snapshot
        "revenue_history": [
            {"q": "Q1 FY24", "rev":  97.3, "yoy": -5.2},
            {"q": "Q2 FY24", "rev":  94.8, "yoy": -4.1},
            {"q": "Q3 FY24", "rev":  93.2, "yoy": -1.9},
            {"q": "Q4 FY24", "rev": 119.6, "yoy":  2.1},
            {"q": "Q1 FY25", "rev": 124.3, "yoy":  2.8},
            {"q": "Q2 FY25", "rev":  95.4, "yoy":  0.6},
            {"q": "Q3 FY25", "rev":  94.9, "yoy":  1.8},
            {"q": "Q4 FY25", "rev": 124.3, "yoy":  3.9},
        ],
        "company_prose": [
            "The company's revenue pace has held between roughly $93B and $125B across the observed eight-quarter window, with the familiar fourth-quarter seasonal peak appearing in both FY24 Q4 and FY25 Q4. YoY change has moved from mid-single-digit negative at the start of the window to low-single-digit positive by its end. These are observed print readings — not a shape claim about the quarter to come.",
            "Across the four most recent reports, the surprise magnitude — reported EPS against the consensus observed on the day of each report — has averaged near the low-single-digit positive range, with one quarter sitting close to flat and none of the four landing below the consensus by more than a narrow margin. Three of four reports printed a positive surprise; one printed within a tenth of a cent of consensus. Record, not a pattern claim.",
            "The analyst estimate range for the quarter now approaching is a factual band. The low end of the sampled observations sits at $1.48; the high end at $1.76; the median at $1.62. The band is a reading of analyst observations — informational only, and not a target of any kind.",
        ],

        # P3 historical surprise ladder (8 quarters)
        "surprise_history": [
            {"quarter": "Q1 FY24", "consensus": 1.42, "actual": 1.52, "surprise_pct":  7.04, "reaction_pct":  2.1, "spark": [0, 0.4, 1.0, 1.6, 2.0, 2.1, 2.1]},
            {"quarter": "Q2 FY24", "consensus": 1.50, "actual": 1.53, "surprise_pct":  2.00, "reaction_pct":  0.8, "spark": [0, 0.2, 0.4, 0.5, 0.7, 0.8, 0.8]},
            {"quarter": "Q3 FY24", "consensus": 1.35, "actual": 1.40, "surprise_pct":  3.70, "reaction_pct": -0.6, "spark": [0, -0.1, -0.3, -0.5, -0.6, -0.6, -0.6]},
            {"quarter": "Q4 FY24", "consensus": 2.10, "actual": 2.18, "surprise_pct":  3.81, "reaction_pct":  1.6, "spark": [0, 0.3, 0.8, 1.2, 1.5, 1.6, 1.6]},
            {"quarter": "Q1 FY25", "consensus": 2.34, "actual": 2.40, "surprise_pct":  2.56, "reaction_pct": -1.2, "spark": [0, -0.3, -0.7, -1.0, -1.1, -1.2, -1.2]},
            {"quarter": "Q2 FY25", "consensus": 1.54, "actual": 1.55, "surprise_pct":  0.65, "reaction_pct":  0.2, "spark": [0, 0.05, 0.1, 0.15, 0.18, 0.2, 0.2]},
            {"quarter": "Q3 FY25", "consensus": 1.47, "actual": 1.48, "surprise_pct":  0.68, "reaction_pct": -0.4, "spark": [0, -0.1, -0.2, -0.3, -0.35, -0.4, -0.4]},
            {"quarter": "Q4 FY25", "consensus": 2.22, "actual": 2.28, "surprise_pct":  2.70, "reaction_pct":  1.8, "spark": [0, 0.4, 0.9, 1.3, 1.6, 1.8, 1.8]},
        ],
        "surprise_bins": [
            {"range": "−4 to −2", "count": 0},
            {"range": "−2 to  0", "count": 0},
            {"range": " 0 to  2", "count": 3},
            {"range": " 2 to  4", "count": 3},
            {"range": " 4 to  6", "count": 1},
            {"range": " 6 to  8", "count": 1},
        ],

        # P4 observation quad
        "beat_rate_pct":   88,
        "beat_timeline":   [1, 1, 1, 1, 1, 1, 1, 1],
        "drift_bars": [
            {"window": "1D",  "avg":  0.5},
            {"window": "5D",  "avg":  0.8},
            {"window": "21D", "avg":  1.4},
        ],
        "implied_realised_r": 0.82,
        "implied_vs_realised": [
            {"implied": 4.0, "realised": 2.1},
            {"implied": 3.5, "realised": 0.8},
            {"implied": 3.8, "realised": 0.6},
            {"implied": 4.6, "realised": 1.6},
            {"implied": 4.2, "realised": 1.2},
            {"implied": 3.2, "realised": 0.2},
            {"implied": 3.0, "realised": 0.4},
            {"implied": 4.4, "realised": 1.8},
        ],
        "peer_group": "Megacap Tech",
        "peer_eps_comp": [
            {"ticker": "AAPL", "eps": 1.62},
            {"ticker": "MSFT", "eps": 3.34},
            {"ticker": "GOOG", "eps": 1.81},
            {"ticker": "META", "eps": 5.12},
        ],
        "reading_notes": [
            {"term": "Consensus is a sampling",      "def": "Consensus is a sampling of analyst observations — historical record only, not a collective target."},
            {"term": "Implied move",                 "def": "Option-market pricing of uncertainty around the print. It is market-implied, not market-determined."},
            {"term": "Past surprise pattern",        "def": "The surprise history is a historical record only. It does not speak to the current quarter."},
            {"term": "Post-earnings drift",          "def": "The drift bars record observed reactions. Causation is not claimed."},
            {"term": "Brief is informational only",  "def": "Nothing on these pages constitutes investment guidance. The document is for pre-read reference only."},
        ],

        # P5 editorial
        "pull_quote":      "The market rehearses every call. The call tells us only how well the market listened.",
        "pull_quote_attr": "PivoxQuant · Earnings Desk",
        "cannot_tell": [
            "Which way the print will land.",
            "What to do before or after the call.",
            "Management's unspoken intent on the call.",
            "Private order flow around the event.",
            "Tax or personal timing of any action.",
        ],

        # P6 colophon
        "data_sources": [
            {"key": "Consensus EPS",       "note": "FMP v4 Stable."},
            {"key": "Option chain",        "note": "CBOE via Alpaca."},
            {"key": "Historical EPS",      "note": "SEC EDGAR."},
            {"key": "Reporting calendar",  "note": "Company Investor Relations."},
        ],
    },

    "brag_card.html": {
        # Goldman IC v2 editorial — 4-page postcard, monthly private self-note.
        "user_name": USER_NAME,
        "month_label": "Mar 2026", "month_label_long": "March 2026",
        "generated_at": GENERATED_AT,
        "issue_number": 4,
        "doc_ref": "PQ-BC-04 · v2026.04.21",
        "hero_headline": [
            "A small note to self.",
            "One month, one",
            "observation.",
        ],
        "return_pct": 12.3,
        "trade_count": 18,
        "best_ticker": "NVDA", "best_return_pct": 18.2,
        "best_pnl_usd": 1240,
        "win_rate_pct": 67.0,
        "hold_days": 8,
        "entry_date": "March 3",
        "exit_date":  "March 11",
        "entry_price": "842",
        "exit_price":  "879",
        "position_size_pct": "3.2",
        "hero_narrative": [
            (
                "Entered NVDA on March 3 at $842. Closed March 11 at $879. "
                "The thesis held three sessions, then handed off to the "
                "market's own weather. The gain was observed; the decision, "
                "imperfect as always, was your own."
            ),
            (
                "This is a record — not a pattern, not a plan, not a claim "
                "about tomorrow."
            ),
        ],
        "top_lots": [
            {"ticker": "NVDA",      "days":  8, "entry":  842.00, "exit":  879.00, "pnl": 1240, "spark": [0.20, 0.34, 0.46, 0.52, 0.60, 0.70, 0.82, 0.92]},
            {"ticker": "MSFT",      "days": 12, "entry":  412.00, "exit":  428.40, "pnl":  656, "spark": [0.30, 0.36, 0.42, 0.44, 0.52, 0.58, 0.62, 0.66]},
            {"ticker": "AAPL",      "days": 10, "entry":  172.50, "exit":  178.20, "pnl":  342, "spark": [0.40, 0.42, 0.48, 0.52, 0.58, 0.60, 0.64, 0.66]},
            {"ticker": "AVGO",      "days":  6, "entry": 1280.00, "exit": 1304.00, "pnl":  192, "spark": [0.40, 0.44, 0.48, 0.54, 0.56, 0.60, 0.62, 0.66]},
            {"ticker": "005930.KS", "days": 14, "entry": 72000,   "exit": 73400,   "pnl":  112, "spark": [0.50, 0.52, 0.56, 0.58, 0.62, 0.64, 0.66, 0.70]},
        ],
        "ledger_narrative": [
            (
                "Five lots cleared the month's realised-P&L threshold. The top "
                "two together contributed the majority of the monthly record — "
                "a concentration noted here for transparency rather than as a "
                "pattern to lean on. Hold windows clustered between six and "
                "fourteen sessions; none ran longer than a month."
            ),
            (
                "The bronze end-dot on each sparkline is the mark at exit "
                "relative to the row's own in-hold range. A single month is "
                "a small sample; this is a record, not a pattern."
            ),
        ],
        "data_sources": ["Broker statements", "Alpaca", "KIS", "Observation journal"],
        "typeset_in": "Source Serif 4 · Geist · JetBrains Mono · Noto Sans KR",
        "engine_note": "Historical record only. No directive, no target, no promise",
        "LICENSE_NUMBER": None,
        "anonymous": False, "is_empty": False,
        "disclaimer": "참고용 자료입니다. 투자 판단이 아닙니다.",
    },

    "brag_card_email.html": {
        "user_name": USER_NAME,
        "month_label": "Mar 2026", "month_label_long": "March 2026",
        "return_pct": 12.3,
        "best_ticker": "NVDA", "best_return_pct": 18.2,
        "best_pnl_usd": 1240,
        "win_rate_pct": 67.0,
        "hold_days": 8,
        "entry_date": "March 3",
        "exit_date":  "March 11",
        "entry_price": "842",
        "exit_price":  "879",
        "trade_count": 8,
        "share_url": "https://pivoxquant.com/share/abc123",
        "png_url": None,
        "disclaimer": "참고용 자료입니다. 투자 판단이 아닙니다.",
    },

    "monthly_finance.html": {
        # Goldman IC v2 editorial — 6-page personal monthly finance ledger.
        "user_name": USER_NAME,
        "month_label": "April 2026",
        "generated_at": GENERATED_AT,
        "issue_number": 4,
        "doc_ref": "PQ-MF-04 · v2026.04.21",
        "hero_headline": [
            "A month ends.",
            "Ledgers settle their",
            "quiet arithmetic.",
        ],
        "kpis_cover": {
            "month_pnl_pct":   2.4,
            "ytd_pnl_pct":     8.7,
            "realized_usd":    3420,
            "unrealized_usd":  8210,
        },
        "equity_walk": [
            0.00, 0.12, 0.31, 0.22, 0.45, 0.68, 0.81, 0.92, 1.10,
            1.28, -0.20, 1.14, 1.33, 1.52, 1.71, 1.84, 1.92, 1.88,
            2.04, 2.21, 2.38, 2.30, 2.40,
        ],
        "ledger_prose": [
            (
                "April recorded a net gain of 2.4% on invested capital, "
                "against a month that ran cool through the first week and "
                "accelerated through the middle ten sessions. The drawdown "
                "trough on Day 11 of -0.20% was shallow relative to the "
                "ninety-day envelope and recovered inside two sessions."
            ),
            (
                "Of the month gain, realised P&L from closed lots contributed "
                "$3,420 across ten exits; unrealised P&L on open positions "
                "carries $8,210 at the month-end mark. Eight dividend events "
                "posted during the month for a combined $264 gross receipt. "
                "Fees and costs totalled $58, FIFO lot-matched."
            ),
        ],
        "ledger_margin": {
            "cash_on_hand":  18450,
            "margin_used":   0,
            "net_deposits":  2000,
            "account_nav":   51820,
        },
        "closed_lots": [
            {"ticker": "NVDA",      "entry": "2026-02-14", "exit": "2026-04-08", "qty": 4,  "cost":  2540.00, "proceeds":  3180.00, "pnl":  640.00, "spark": [0.20, 0.30, 0.40, 0.55, 0.65, 0.72, 0.80, 0.88]},
            {"ticker": "MSFT",      "entry": "2026-03-12", "exit": "2026-04-11", "qty": 8,  "cost":  2682.00, "proceeds":  2940.00, "pnl":  258.00, "spark": [0.30, 0.36, 0.42, 0.44, 0.52, 0.58, 0.62, 0.66]},
            {"ticker": "AAPL",      "entry": "2026-01-28", "exit": "2026-04-14", "qty": 6,  "cost":  1034.40, "proceeds":  1182.00, "pnl":  147.60, "spark": [0.40, 0.42, 0.48, 0.52, 0.58, 0.60, 0.64, 0.66]},
            {"ticker": "005930.KS", "entry": "2026-03-03", "exit": "2026-04-16", "qty": 20, "cost":  1440.00, "proceeds":  1596.00, "pnl":  156.00, "spark": [0.50, 0.52, 0.56, 0.58, 0.62, 0.64, 0.68, 0.72]},
            {"ticker": "GOOGL",     "entry": "2026-02-20", "exit": "2026-04-03", "qty": 5,  "cost":   745.00, "proceeds":   812.00, "pnl":   67.00, "spark": [0.30, 0.28, 0.34, 0.38, 0.42, 0.46, 0.48, 0.52]},
            {"ticker": "AVGO",      "entry": "2026-03-20", "exit": "2026-04-18", "qty": 2,  "cost":  2560.00, "proceeds":  2748.00, "pnl":  188.00, "spark": [0.40, 0.42, 0.48, 0.52, 0.58, 0.62, 0.66, 0.72]},
            {"ticker": "NFLX",      "entry": "2026-02-05", "exit": "2026-04-09", "qty": 3,  "cost":  1890.00, "proceeds":  2022.00, "pnl":  132.00, "spark": [0.40, 0.44, 0.48, 0.50, 0.54, 0.58, 0.60, 0.64]},
            {"ticker": "QCOM",      "entry": "2026-03-18", "exit": "2026-04-12", "qty": 10, "cost":  1580.00, "proceeds":  1492.00, "pnl":  -88.00, "spark": [0.50, 0.48, 0.46, 0.44, 0.42, 0.40, 0.38, 0.36]},
            {"ticker": "INTC",      "entry": "2026-02-22", "exit": "2026-04-05", "qty": 15, "cost":   585.00, "proceeds":   536.25, "pnl":  -48.75, "spark": [0.50, 0.48, 0.46, 0.44, 0.42, 0.40, 0.38, 0.38]},
            {"ticker": "000660.KS", "entry": "2026-03-28", "exit": "2026-04-19", "qty": 5,  "cost":   725.00, "proceeds":   831.00, "pnl":  106.00, "spark": [0.50, 0.52, 0.54, 0.58, 0.62, 0.66, 0.70, 0.74]},
        ],
        "cash_flow": {
            "deposits":           2000.00,
            "withdrawals":           0.00,
            "dividends_received":  264.00,
            "interest_received":    24.50,
            "fees_paid":           -58.00,
            "taxes_withheld":      -39.60,
            "net_cash_change":    2190.90,
        },
        "sector_attribution": [
            {"n": "Tech",     "v":  1850},
            {"n": "Semis",    "v":  1380},
            {"n": "Comms",    "v":   420},
            {"n": "Cons.D",   "v":  -180},
            {"n": "Cons.S",   "v":   140},
            {"n": "Health",   "v":   210},
            {"n": "Indus",    "v":   380},
            {"n": "Fin",      "v":    92},
            {"n": "Util",     "v":   -48},
            {"n": "Energy",   "v":   560},
            {"n": "Real Est", "v":  -120},
        ],
        "contrib_detract": [
            {"t": "NVDA",      "v":  1420},
            {"t": "MSFT",      "v":   860},
            {"t": "AAPL",      "v":   540},
            {"t": "005930.KS", "v":   380},
            {"t": "AVGO",      "v":   320},
            {"t": "QCOM",      "v":   -88},
            {"t": "INTC",      "v":   -49},
            {"t": "BABA",      "v":   -68},
            {"t": "META",      "v":  -112},
            {"t": "TSLA",      "v":  -190},
        ],
        "dividend_events": [
            {"day":  3, "t": "AAPL",      "amt":  12.00},
            {"day":  8, "t": "MSFT",      "amt":  48.00},
            {"day": 12, "t": "AVGO",      "amt":  42.00},
            {"day": 15, "t": "KO",        "amt":  18.00},
            {"day": 18, "t": "005930.KS", "amt":  68.00},
            {"day": 21, "t": "JNJ",       "amt":  22.00},
            {"day": 24, "t": "PG",        "amt":  16.00},
            {"day": 28, "t": "XOM",       "amt":  38.00},
        ],
        "cost_breakdown_q": [
            {"n": "Commission",  "v": 22.40},
            {"n": "Spread",      "v": 18.60},
            {"n": "Borrow",      "v":  0.00},
            {"n": "FX spread",   "v":  9.20},
            {"n": "Reg. fees",   "v":  4.80},
            {"n": "SEC fee",     "v":  3.00},
        ],
        "reconciliation_notes": [
            "Figures are observed from broker statements, month-end close.",
            "Dividends are gross of withholding tax.",
            "Realised P&L uses FIFO lot matching.",
            "Unrealised P&L uses month-end mark.",
            "Not tax guidance — consult a professional for your own filing.",
        ],
        "pull_quote": (
            "A ledger is not a verdict. It is the month's handwriting — "
            "plain, careful, indifferent to meaning."
        ),
        "pull_quote_attribution": "PivoxQuant Finance Desk",
        "typeset_in": "Source Serif 4 · Geist · JetBrains Mono · Noto Sans KR",
        "engine_note": "Historical record only. Monthly ledger pipeline.",
        "LICENSE_NUMBER": None,
    },

    "risk_board.html": {
        # Goldman Risk Committee v2 editorial — 6-page deck.
        # Source of truth: services.artifacts.sample_data.sample_risk_board().
        "user_name":     USER_NAME,
        "period_label":  "April 2026",
        "generated_at":  "2026-04-21",
        "issue_number":  4,
        "doc_ref":       "PQ-RB-04 · v2026.04.21",
        "typeset_in":    "Source Serif 4 · Geist · JetBrains Mono",
        "engine_note":   "58 quant models · 7-Layer Risk Defense",
        "LICENSE_NUMBER": None,

        # P1 · cover KPIs
        "kpi_var_1d":     -2.14,
        "kpi_es_1d":      -3.42,
        "kpi_maxdd_90d":  -8.70,
        "kpi_corr_index":  0.58,
        "hero_headline": [
            "Risk is observed, not eliminated.",
            "Numbers are companions, not captains.",
            "This is a record — not a route.",
        ],

        # P2 · 10×10 correlation
        "corr_matrix": {
            "labels": ["AAPL", "MSFT", "NVDA", "GOOG", "META",
                       "AMZN", "TSLA", "JPM",  "XOM",  "UNH"],
            "values": [
                [1.00, 0.82, 0.68, 0.71, 0.64, 0.66, 0.47, 0.32, 0.18, 0.24],
                [0.82, 1.00, 0.72, 0.74, 0.68, 0.69, 0.44, 0.35, 0.21, 0.26],
                [0.68, 0.72, 1.00, 0.62, 0.58, 0.60, 0.52, 0.28, 0.11, 0.19],
                [0.71, 0.74, 0.62, 1.00, 0.67, 0.65, 0.41, 0.30, 0.17, 0.22],
                [0.64, 0.68, 0.58, 0.67, 1.00, 0.61, 0.39, 0.27, 0.15, 0.20],
                [0.66, 0.69, 0.60, 0.65, 0.61, 1.00, 0.43, 0.29, 0.16, 0.21],
                [0.47, 0.44, 0.52, 0.41, 0.39, 0.43, 1.00, 0.22, 0.14, 0.17],
                [0.32, 0.35, 0.28, 0.30, 0.27, 0.29, 0.22, 1.00, 0.34, 0.28],
                [0.18, 0.21, 0.11, 0.17, 0.15, 0.16, 0.14, 0.34, 1.00, 0.19],
                [0.24, 0.26, 0.19, 0.22, 0.20, 0.21, 0.17, 0.28, 0.19, 1.00],
            ],
        },

        # P3 · risk ladder (10 positions)
        "positions_ladder": [
            {"ticker": "AAPL", "weight": 12.8, "var_1d": -1.84, "es_1d": -2.71,
             "maxdd_90d": -6.42, "beta": 1.08, "vol_ann": 22.4,
             "spark": [0, -0.4, -0.9, -1.4, -0.8, -1.6, -1.84]},
            {"ticker": "MSFT", "weight": 11.2, "var_1d": -1.72, "es_1d": -2.58,
             "maxdd_90d": -5.88, "beta": 1.02, "vol_ann": 21.1,
             "spark": [0, -0.3, -0.8, -1.2, -0.7, -1.4, -1.72]},
            {"ticker": "NVDA", "weight": 14.4, "var_1d": -3.41, "es_1d": -5.12,
             "maxdd_90d": -14.2, "beta": 1.68, "vol_ann": 42.6,
             "spark": [0, -0.8, -1.9, -2.8, -1.4, -2.9, -3.41]},
            {"ticker": "GOOG", "weight": 9.6,  "var_1d": -1.92, "es_1d": -2.84,
             "maxdd_90d": -7.11, "beta": 1.12, "vol_ann": 23.8,
             "spark": [0, -0.4, -0.9, -1.5, -0.9, -1.7, -1.92]},
            {"ticker": "META", "weight": 8.4,  "var_1d": -2.44, "es_1d": -3.62,
             "maxdd_90d": -9.88, "beta": 1.28, "vol_ann": 28.9,
             "spark": [0, -0.6, -1.2, -2.0, -1.1, -2.1, -2.44]},
            {"ticker": "AMZN", "weight": 8.8,  "var_1d": -2.08, "es_1d": -3.11,
             "maxdd_90d": -8.24, "beta": 1.18, "vol_ann": 25.4,
             "spark": [0, -0.5, -1.1, -1.7, -0.9, -1.8, -2.08]},
            {"ticker": "TSLA", "weight": 7.2,  "var_1d": -4.12, "es_1d": -6.04,
             "maxdd_90d": -18.6, "beta": 1.84, "vol_ann": 48.2,
             "spark": [0, -1.0, -2.4, -3.2, -1.8, -3.4, -4.12]},
            {"ticker": "JPM",  "weight": 6.4,  "var_1d": -1.28, "es_1d": -1.94,
             "maxdd_90d": -4.12, "beta": 0.88, "vol_ann": 16.8,
             "spark": [0, -0.3, -0.6, -1.0, -0.6, -1.1, -1.28]},
            {"ticker": "XOM",  "weight": 4.8,  "var_1d": -1.04, "es_1d": -1.56,
             "maxdd_90d": -3.82, "beta": 0.74, "vol_ann": 18.2,
             "spark": [0, -0.2, -0.5, -0.8, -0.5, -0.9, -1.04]},
            {"ticker": "UNH",  "weight": 5.4,  "var_1d": -1.18, "es_1d": -1.78,
             "maxdd_90d": -4.48, "beta": 0.82, "vol_ann": 17.6,
             "spark": [0, -0.3, -0.6, -0.9, -0.6, -1.0, -1.18]},
        ],

        # P4 · tail / drawdown quad
        "var_histogram": {
            "bins":   [-5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5],
            "counts": [ 1,  3,  8, 18, 42, 68, 52, 32, 14,  6,  2],
        },
        "underwater": [
            0.0, -0.4, -1.2, -2.8, -4.4, -6.2, -7.8, -8.7,
            -8.2, -7.1, -5.4, -3.1, -1.6, -0.8, -0.4, 0.0,
        ],
        "tail_dist": {
            "empirical": [0.4, 1.2, 3.4, 6.8, 9.2, 11.8, 9.4, 5.8, 2.8, 0.9],
            "normal":    [0.9, 2.4, 4.6, 7.4, 9.6, 10.1, 8.2, 4.9, 2.1, 0.6],
        },
        "tail_ratio":      1.08,
        "liquidity_label": "1.2x avg",
        "liquidity_heat": [
            [0.08, 0.09, 0.11, 0.09, 0.10],
            [0.12, 0.14, 0.13, 0.15, 0.12],
            [0.22, 0.28, 0.31, 0.26, 0.24],
            [0.06, 0.07, 0.06, 0.08, 0.07],
            [0.18, 0.21, 0.19, 0.20, 0.22],
            [0.09, 0.10, 0.12, 0.09, 0.11],
            [0.34, 0.38, 0.32, 0.36, 0.40],
            [0.14, 0.16, 0.15, 0.13, 0.14],
            [0.05, 0.06, 0.05, 0.07, 0.05],
            [0.11, 0.13, 0.12, 0.10, 0.14],
        ],

        # P5 · editorial
        "pull_quote": (
            "Observations of risk do not subtract it. "
            "They shape the room we stand in while the weather turns."
        ),
        "pull_quote_attribution": "PivoxQuant Risk Desk",
        "not_answered": [
            "Tax consequences of rebalancing.",
            "Individual liquidity events.",
            "Regime shifts not in the 252D window.",
            "Correlated news shocks not priced in.",
            "Personal cash-flow timing.",
        ],

        # P6 · colophon
        "data_sources": [
            {"key": "Price",             "value": "Alpaca Market Data (IEX consolidated)"},
            {"key": "Corporate actions", "value": "FMP v4 Stable"},
            {"key": "Risk-free",         "value": "3-Month T-Bill (FRED DGS3MO)"},
            {"key": "Window",            "value": "252 trading days, rolling"},
        ],
    },

    "quarterly_self_report.html": {
        # Goldman IC v2 editorial — 6-page self-review letter.
        # Source of truth: services.artifacts.sample_data.sample_quarterly_self_report().
        "user_name":     USER_NAME,
        "quarter_label": "Q1 2026",
        "issue_number":  1,
        "doc_ref":       "PQ-QSR-01 · v2026.04.21",
        "period_start":  "2026-01-01",
        "period_end":    "2026-03-31",
        "generated_at":  GENERATED_AT,
        "typeset_in":    "Source Serif 4 · Geist · JetBrains Mono",
        "engine_note":   "58 quant models · 7-Layer Risk Defense",
        "LICENSE_NUMBER": None,

        # P1 cover KPIs
        "quarterly_return_pct": 6.40,
        "kpi_benchmark":        4.20,
        "kpi_alpha":            2.20,
        "kpi_hit_rate":         58,
        "hero_headline": [
            "Three months observed.",
            "One hand, ten decisions.",
            "A self-review — not a verdict.",
        ],

        # P2 self-review letter (6 paragraphs) — defaults in template are fine,
        # but we pass explicit copy for CEO review.
        "signoff_line": "In observation,",
        "review_paragraphs": [
            "Three months, in the hand. The quarter opened with the market reading its own quiet — a stretched week of thin prints, a calmer second week, and then the sort of mid-quarter acceleration that looks, in the book, like momentum and, on the tape, like catching up. I watched. I did little. The doing, when it came, came later.",
            "Position changes were fewer than the quarter before. Semiconductor weight held at a little over a quarter of the book through the period. Consumer discretionary was trimmed in February — a small reduction, not a closure — on a reading that exit pace was outrunning the thesis I had written down. The adjustment was clean; the reasoning was dated; the execution took ninety seconds. That is not a strategy. It is a habit.",
            "The largest single-day drawdown of the quarter printed on the Thursday in mid-March. It was 2.1% on the book. I remember the morning because I had slept poorly the night before and opened the screen later than usual. The book recovered by the following Tuesday. The note I wrote to myself on the Thursday afternoon — two sentences in the running file — is the record that no Sharpe ratio preserves. I keep the note.",
            "What I misread, I misread at the edges. I read one small position as a story of operating leverage and the thesis I had written, three lines long, required a footnote on customer concentration that I had read in October and then, quietly, stopped reading. The position is still in the book, at a smaller weight. I have not closed it. I have reread the footnote. These are the decisions that do not appear in a P&L column. The P&L is where the decision lives. The decision is not where the P&L lives.",
            "The habits held, with one exception. Monthly rebalance on the last trading day — kept. Reading on Saturday mornings — kept, except for the one Sunday evening in February I chose instead to finish a book, and the Tuesday that followed it was my least clean trading day of the quarter. The reading is not superstition. The reading is the shelter. I note the exception. I do not punish the Sunday.",
            "Quarters end. Observation continues. There is nothing to claim here, and no conclusion I would put in italics if I were writing for anyone else. I am writing for the person who has to make the next ten decisions. That person will be, again, me.",
        ],
        "margin_notes": [
            {"eyebrow": "Sharpe · quarter", "note": "Observed at 1.08 over the window. Not annualised into the future."},
            {"eyebrow": "Beta · 90D",        "note": "Book-to-SPY beta 0.92 over trailing 90 sessions. Quietly below one."},
            {"eyebrow": "Turnover",          "note": "28% in the quarter. Monthly rebalance on the last trading day, held without exception."},
        ],

        # P3 decision ladder — 10 rows
        "decision_ladder": [
            {"date": "2026-01-08", "action": "Open",    "ticker": "NVDA", "weight_delta":  4.2, "rationale": "Sizing per plan",                  "pnl_pct":  12.4, "spark": [0, 0.6, 1.8, 3.2, 4.8, 7.6, 12.4]},
            {"date": "2026-01-14", "action": "Trim",    "ticker": "TSLA", "weight_delta": -1.8, "rationale": "Position size reduction",          "pnl_pct":  -2.1, "spark": [0, 0.3, -0.4, -1.2, -1.8, -2.0, -2.1]},
            {"date": "2026-01-22", "action": "Add",     "ticker": "AAPL", "weight_delta":  2.0, "rationale": "Rebalance per plan",               "pnl_pct":   5.8, "spark": [0, 0.4, 1.2, 2.4, 3.8, 5.0, 5.8]},
            {"date": "2026-02-04", "action": "Open",    "ticker": "AVGO", "weight_delta":  3.0, "rationale": "New thesis entry",                 "pnl_pct":   9.1, "spark": [0, 0.8, 2.2, 4.1, 6.2, 8.0, 9.1]},
            {"date": "2026-02-11", "action": "Trim",    "ticker": "XLY",  "weight_delta": -2.4, "rationale": "Sector weight reduction",          "pnl_pct":   1.2, "spark": [0, 0.2, 0.5, 0.8, 1.0, 1.1, 1.2]},
            {"date": "2026-02-19", "action": "Cash",    "ticker": "CASH", "weight_delta":  2.4, "rationale": "Cash buffer increase",             "pnl_pct":   0.4, "spark": [0, 0.1, 0.1, 0.2, 0.3, 0.3, 0.4]},
            {"date": "2026-02-27", "action": "Add",     "ticker": "MSFT", "weight_delta":  1.5, "rationale": "Rebalance per plan",               "pnl_pct":   3.2, "spark": [0, 0.3, 0.8, 1.6, 2.4, 2.9, 3.2]},
            {"date": "2026-03-06", "action": "Close",   "ticker": "NKE",  "weight_delta": -2.2, "rationale": "Thesis marked stale",              "pnl_pct":  -5.8, "spark": [0, -0.4, -1.2, -2.4, -3.8, -4.9, -5.8]},
            {"date": "2026-03-14", "action": "Observe", "ticker": "BOOK", "weight_delta":  0.0, "rationale": "Drawdown day (−2.1% print)",       "pnl_pct":  -2.1, "spark": [0, -0.2, -0.8, -1.6, -2.0, -2.1, -2.1]},
            {"date": "2026-03-27", "action": "Rebal",   "ticker": "BOOK", "weight_delta":  0.0, "rationale": "Monthly rebalance (per plan)",     "pnl_pct":   0.6, "spark": [0, 0.1, 0.2, 0.3, 0.5, 0.6, 0.6]},
        ],

        # P4 diagnostic quad
        "sharpe_rolling":     1.08,
        "sharpe_series":      [0.42, 0.58, 0.68, 0.74, 0.82, 0.91, 0.95, 1.02, 1.08, 1.12, 1.08, 1.04],
        "hit_rate_overall":   58,
        "hit_rate_by_action": [
            {"action": "Open",  "rate": 62, "count": 4},
            {"action": "Add",   "rate": 67, "count": 3},
            {"action": "Trim",  "rate": 50, "count": 2},
            {"action": "Close", "rate": 50, "count": 2},
        ],
        "holding_median_days": 14,
        "holding_hist":        [2, 4, 6, 7, 5, 3, 2, 1, 0, 1],
        "top_sector":          "Semiconductors",
        "sector_attribution": [
            {"sector": "Semis",    "pnl":  3.8},
            {"sector": "Platform", "pnl":  1.6},
            {"sector": "Consumer", "pnl": -0.4},
            {"sector": "Fin",      "pnl":  0.8},
            {"sector": "Cash",     "pnl":  0.6},
        ],
        "self_review_notes": [
            {"term": "Sharpe · rolling",   "def": "Excess-of-cash return per unit of realised volatility, computed on a rolling 90-session window. A historical record only."},
            {"term": "Hit Rate",           "def": "Closed decisions with a positive print, divided by closed decisions. Counts events, not conviction."},
            {"term": "Holding period",     "def": "Calendar days from entry to last change or close. The mode sits at the monthly rebalance rhythm, by design."},
            {"term": "Sector attribution", "def": "Share of quarter P&L observed in each sector cohort. Not a causal claim about sector rotation."},
            {"term": "Not predictive",     "def": "None of the four readings is predictive. They are artefacts of the quarter already lived, kept for review."},
        ],

        # P5 editorial
        "pull_quote":      "Self-review is the small hinge on which large habits turn.",
        "pull_quote_attr": "PivoxQuant · Quarterly Desk",
        "cannot_settle": [
            "Tax consequences of the quarter's closed positions.",
            "Personal liquidity events not visible in the book.",
            "A regime shift that falls outside the 90-session sample.",
            "Private decisions made for reasons not written down.",
            "Any outcome of decisions not yet made.",
        ],
        "does_record": [
            "Ten decisions, in the order they were made.",
            "Four diagnostic readings over the 90-session window.",
            "Three margin notes — Sharpe, beta, turnover.",
            "One largest single-day drawdown, with its date.",
            "One written sign-off, to the person who made the quarter.",
        ],

        # P6 colophon
        "data_sources": [
            {"key": "Price observations", "note": "Alpaca Market Data (IEX consolidated)."},
            {"key": "Corporate actions",  "note": "FMP v4 Stable."},
            {"key": "Risk-free",          "note": "3-Month T-Bill via FRED (DGS3MO)."},
            {"key": "Benchmark",          "note": "S&P 500 total return, with dividends."},
        ],
    },

    "year_end_letter.html": {
        "year": "2025",
        "issue_number": 1,
        "doc_ref": "PQ-YEL-01 · v2026.04.21",
        "user_name": USER_NAME,
        "period_start": "2025-01-01", "period_end": "2025-12-31",
        "generated_at": GENERATED_AT,
        "kpi_pnl":       16.8,
        "kpi_benchmark": 11.2,
        "kpi_alpha":      5.6,
        "kpi_mdd":      -12.4,
        "hero_headline": [
            "A letter written at year's end.",
            "Twelve months, six hundred prints, one quiet hand.",
            "A record, not a verdict.",
        ],
        "letter_paragraphs": [
            "This letter is not a forecast. It is a record of what happened, and \u2014 where I can manage it \u2014 a record of what I noticed while it happened. The numbers on the cover are what they are. The question worth a letter is what the numbers were made of.",
            "The market in question moved, on the whole, as markets do \u2014 in a stretched summer, a frightened autumn, and a quiet close. The benchmark drifted upward through a corridor of minor shocks, none of which proved durable enough to name. I have nothing useful to say about the shocks. I have a little to say about what the book did in their company.",
            "The book carried a weight in the semiconductor cohort through the first three quarters, and in the platform cohort through the fourth. The communications-and-consumer pair lagged the others by a wide margin in the second quarter, and the small adjustment made in July \u2014 a reduction of exposure, not a closure \u2014 was the cleanest single decision of the year. Two positions that had been noisy for months simply calmed. I take no credit for this. I kept the names. The names did the work.",
            "The largest single-day drawdown arrived on March 14, a Friday, and it was 3.2%. I remember it because I was writing another letter \u2014 an unrelated one, to someone unrelated \u2014 when it printed, and the text I had been composing on a different subject became harder to finish. This is the human record that no Sharpe ratio preserves. The book was back at prior high by the following Wednesday. The other letter, I finished the next week, poorly.",
            "What I misread, I misread with some confidence. I read one mid-cap as a story of operating leverage and missed that the story required a customer-concentration footnote I had read and promptly forgotten. The position was closed in June at a small loss. I keep the position sheet in a folder, dated, as a note to myself. Not to punish. To remember the texture of being wrong.",
            "The habits held. Monthly rebalance on the last trading day. Reading on weekends, not weekdays. Sleep before midnight, market-side screens dark by 10pm KST. A single quiet Sunday in September I skipped the reading and paid for it on Tuesday with a decision I would not have made rested. These are not strategies. They are shelters.",
            "Markets are weather. Portfolios are shelters. Neither makes promises. Records are all we keep.",
        ],
        "margin_notes": [
            {"eyebrow": "Sharpe",           "note": "Observed at 0.91 over the window. Not annualised into the future."},
            {"eyebrow": "Turnover",         "note": "41%. Monthly rebalance on the last trading day, without exception."},
            {"eyebrow": "Worst Day",        "note": "Largest single-day drawdown \u22123.2%, March 14. Book back at prior high by the following Wednesday."},
            {"eyebrow": "Book composition", "note": "Seven positions held through the full year. Three entered mid-year. Two closed in June."},
        ],
        "equity_ribbon_pts": [
            {"m": "Jan", "v": 100_000}, {"m": "Feb", "v": 101_800}, {"m": "Mar", "v":  98_600},
            {"m": "Apr", "v": 103_400}, {"m": "May", "v": 106_200}, {"m": "Jun", "v": 108_900},
            {"m": "Jul", "v": 110_400}, {"m": "Aug", "v": 112_800}, {"m": "Sep", "v": 111_900},
            {"m": "Oct", "v": 114_600}, {"m": "Nov", "v": 116_200}, {"m": "Dec", "v": 116_800},
        ],
        "monthly_rows": [
            {"month": "Jan", "pnl":  1.8, "spy":  0.9, "alpha":  0.9, "dd": -1.2, "trades": 5,
             "sparkline_pts": [0, 0.4, 0.8, 1.2, 1.6, 1.8]},
            {"month": "Feb", "pnl":  1.8, "spy":  1.4, "alpha":  0.4, "dd": -0.9, "trades": 4,
             "sparkline_pts": [0, 0.5, 0.9, 1.3, 1.6, 1.8]},
            {"month": "Mar", "pnl": -3.1, "spy": -1.8, "alpha": -1.3, "dd": -3.2, "trades": 7,
             "sparkline_pts": [0, -0.6, -1.4, -2.2, -2.8, -3.1]},
            {"month": "Apr", "pnl":  4.8, "spy":  2.6, "alpha":  2.2, "dd": -1.1, "trades": 3,
             "sparkline_pts": [0, 0.8, 1.9, 3.2, 4.1, 4.8]},
            {"month": "May", "pnl":  2.7, "spy":  1.8, "alpha":  0.9, "dd": -0.8, "trades": 4,
             "sparkline_pts": [0, 0.6, 1.2, 1.8, 2.3, 2.7]},
            {"month": "Jun", "pnl":  2.5, "spy":  1.4, "alpha":  1.1, "dd": -1.4, "trades": 6,
             "sparkline_pts": [0, 0.4, 1.0, 1.6, 2.1, 2.5]},
            {"month": "Jul", "pnl":  1.4, "spy":  1.2, "alpha":  0.2, "dd": -0.6, "trades": 2,
             "sparkline_pts": [0, 0.3, 0.7, 1.0, 1.2, 1.4]},
            {"month": "Aug", "pnl":  2.2, "spy":  0.8, "alpha":  1.4, "dd": -0.9, "trades": 3,
             "sparkline_pts": [0, 0.5, 1.0, 1.5, 1.9, 2.2]},
            {"month": "Sep", "pnl": -0.8, "spy": -1.4, "alpha":  0.6, "dd": -1.8, "trades": 5,
             "sparkline_pts": [0, -0.2, -0.5, -0.7, -0.8, -0.8]},
            {"month": "Oct", "pnl":  2.4, "spy":  1.4, "alpha":  1.0, "dd": -1.1, "trades": 4,
             "sparkline_pts": [0, 0.6, 1.1, 1.7, 2.1, 2.4]},
            {"month": "Nov", "pnl":  1.4, "spy":  1.1, "alpha":  0.3, "dd": -0.5, "trades": 2,
             "sparkline_pts": [0, 0.4, 0.7, 1.0, 1.2, 1.4]},
            {"month": "Dec", "pnl":  0.5, "spy":  0.8, "alpha": -0.3, "dd": -0.4, "trades": 1,
             "sparkline_pts": [0, 0.2, 0.3, 0.4, 0.5, 0.5]},
        ],
        "reflection_blocks": [
            {
                "roman": "I",
                "title": "What I held onto",
                "paragraph": "The positions I held through the year were held not because I was confident, but because the theses I had written down for them continued to describe the world I was in. Conviction is a noun that does poorly in public. Written theses age better.",
                "bullets": [
                    "The semiconductor cohort \u2014 held on the operating-leverage thesis, which stayed intact.",
                    "The platform cohort \u2014 trimmed once in July, otherwise left alone.",
                    "Cash at a steady 9\u201311% through the year \u2014 not strategy, a shelter.",
                ],
            },
            {
                "roman": "II",
                "title": "What I let go of",
                "paragraph": "Two positions were closed in June, both at small losses. Neither had produced a single print that surprised me on the upside for four months. I had kept them on the theory that quiet is a prelude. Quiet was just quiet.",
                "bullets": [
                    "A mid-cap industrial whose customer-concentration note I had read and forgotten.",
                    "A consumer name whose thesis required a margin expansion that never arrived.",
                    "Two commentary subscriptions that, on review, added no signal beyond the news.",
                ],
            },
            {
                "roman": "III",
                "title": "What I got wrong",
                "paragraph": "I read one position as a story of operating leverage and missed a footnote that was not hidden \u2014 only, I had read it once and not reread it. The position was closed at a small loss. The error worth naming is not the loss. It is the confidence. I had been sure.",
                "bullets": [
                    "Over-weighting a thesis I had read once and treated as digested.",
                    "Reading weekend research on Sunday evening rather than Saturday morning.",
                    "Confusing a quiet six weeks with a constructive six weeks.",
                ],
            },
            {
                "roman": "IV",
                "title": "What I will keep watching",
                "paragraph": "Nothing here is a plan for the coming year. The items below are things I mean to keep observing \u2014 not because observing them will produce a return, but because not observing them has, in the past, produced regret.",
                "bullets": [
                    "Whether the semiconductor operating-leverage story survives a demand normalisation.",
                    "Whether the quiet stretches of August\u2013September recur and how I spend them.",
                    "Whether the monthly-rebalance discipline survives a January without a print.",
                ],
            },
        ],
        "pull_quote": (
            "The year did not arrive. It was made, decision by small decision \u2014 "
            "most of them unremarkable, a few regrettable, none forecast."
        ),
        "pull_quote_attr": "PivoxQuant \u00b7 Year 2025",
        "not_claimed": [
            "A thesis for the coming year.",
            "A blueprint for replication.",
            "A professional service or advisory.",
            "A guarantee of future observation quality.",
            "Tax or legal guidance.",
        ],
        "data_sources": [
            {"key": "Price observations", "note": "Alpaca Market Data (IEX consolidated)."},
            {"key": "Corporate actions",  "note": "FMP v4 Stable."},
            {"key": "Risk-free",          "note": "3-Month T-Bill via FRED (DGS3MO)."},
            {"key": "Benchmark",          "note": "SPY total return, with dividends."},
        ],
        "typeset_in": "Source Serif 4 \u00b7 Geist \u00b7 JetBrains Mono",
        "LICENSE_NUMBER": None,
    },

    "capital_allocation.html": {
        "user_name": USER_NAME,
        "generated_at": GENERATED_AT,
        "issue_number": 1,
        "doc_ref": "PQ-CA-01 \u00b7 v2026.04.22",
        "hero_headline": [
            "Capital is attention",
            "made durable. Every line",
            "is a quiet sentence.",
        ],
        "kpis_cover": {
            "equity_pct": 58.0, "bonds_pct": 24.0,
            "cash_pct": 12.0,   "alt_pct": 6.0,
        },
        "months_labels": ["May","Jun","Jul","Aug","Sep","Oct","Nov","Dec","Jan","Feb","Mar","Apr"],
        "allocation_stack": {
            "equity": [54,55,56,57,57,58,58,59,60,59,58,58],
            "bonds":  [26,26,26,25,25,25,25,24,23,24,24,24],
            "cash":   [14,13,12,12,12,12,12,11,11,11,12,12],
            "alt":    [ 6, 6, 6, 6, 6, 5, 5, 6, 6, 6, 6, 6],
        },
        "allocation_margin": {
            "rebalances_ytd": 2, "largest_drift_pp": 3.4,
            "target_band_pp": 5.0, "tracking_err": 1.12,
        },
        "spread_prose": [
            "The equity line drifted four points through the year.",
            "Bond weight moved in the opposite direction.",
        ],
        "ladder_rows": [
            {"sleeve":"US Equity",       "target":35.0, "current":38.0, "drift": 3.0, "delta3m": 1.2, "delta12m": 4.8, "note":"Large-cap index + factor tilt.",  "spark":[0.50,0.52,0.54,0.56,0.58,0.60,0.61,0.63]},
            {"sleeve":"International Eq.","target":18.0, "current":16.5, "drift":-1.5, "delta3m":-0.6, "delta12m":-1.8, "note":"Developed-market index.",          "spark":[0.50,0.52,0.52,0.51,0.50,0.49,0.48,0.48]},
            {"sleeve":"Emerging Eq.",    "target": 5.0, "current": 3.5, "drift":-1.5, "delta3m":-0.4, "delta12m":-1.4, "note":"Broad EM index.",                 "spark":[0.50,0.50,0.49,0.48,0.47,0.46,0.45,0.44]},
            {"sleeve":"US IG Bonds",     "target":15.0, "current":14.2, "drift":-0.8, "delta3m":-0.2, "delta12m":-1.1, "note":"Aggregate index, intermediate.",  "spark":[0.50,0.51,0.52,0.52,0.52,0.52,0.51,0.50]},
            {"sleeve":"US HY Bonds",     "target": 5.0, "current": 5.8, "drift": 0.8, "delta3m": 0.3, "delta12m": 1.0, "note":"HY index, ex-energy.",            "spark":[0.50,0.51,0.53,0.55,0.57,0.58,0.59,0.60]},
            {"sleeve":"TIPS",            "target": 4.0, "current": 4.1, "drift": 0.1, "delta3m": 0.0, "delta12m": 0.2, "note":"Short-duration TIPS.",            "spark":[0.50,0.50,0.50,0.51,0.51,0.51,0.51,0.52]},
            {"sleeve":"Cash",            "target":10.0, "current":12.0, "drift": 2.0, "delta3m": 0.4, "delta12m": 1.2, "note":"Money market + short T-bills.",   "spark":[0.50,0.52,0.54,0.56,0.57,0.58,0.59,0.60]},
            {"sleeve":"Real Assets",     "target": 6.0, "current": 5.9, "drift":-0.1, "delta3m": 0.0, "delta12m":-0.3, "note":"REIT index + gold sleeve.",       "spark":[0.50,0.50,0.49,0.48,0.48,0.48,0.49,0.49]},
        ],
        "contribution_bars": [
            {"n":"US Eq.",       "v": 6.2},
            {"n":"Intl Eq.",     "v": 1.1},
            {"n":"EM Eq.",       "v":-0.3},
            {"n":"US IG",        "v": 0.6},
            {"n":"US HY",        "v": 0.9},
            {"n":"TIPS",         "v": 0.2},
            {"n":"Cash",         "v": 0.4},
            {"n":"Real Assets",  "v": 0.8},
        ],
        "drift_lines": {
            "equity": [0.0,0.2,0.6,0.8,1.2,1.6,2.0,2.4,2.8,2.6,2.4,3.0],
            "bonds":  [0.0,-0.2,-0.4,-0.4,-0.6,-0.8,-1.0,-1.2,-1.4,-1.2,-1.0,-0.8],
            "cash":   [0.0,0.0,-0.2,-0.4,-0.6,-0.8,-1.0,-1.2,-1.4,-1.4,-1.4,-1.2],
            "alt":    [0.0,0.0,0.0,0.0,0.0,-0.2,-0.2,0.0,0.0,0.0,0.0,-0.1],
        },
        "rebalance_events": [
            {"m": 2, "sl":"US Eq.",  "dir":"trim", "amt":1.2},
            {"m": 5, "sl":"US HY",   "dir":"add",  "amt":0.8},
            {"m": 8, "sl":"Cash",    "dir":"add",  "amt":1.4},
            {"m":10, "sl":"Intl Eq.","dir":"trim", "amt":0.6},
            {"m":11, "sl":"Bonds",   "dir":"add",  "amt":0.9},
        ],
        "portfolio_vs_6040_p": [0.0,0.4,0.9,1.2,1.8,2.2,2.6,3.0,3.6,4.1,4.6,5.2],
        "portfolio_vs_6040_b": [0.0,0.5,1.1,1.4,1.9,2.2,2.5,2.8,3.4,3.8,4.2,4.6],
        "allocation_notes": [
            "Weights are month-end marks; intraday variations are smoothed.",
            "The 60/40 benchmark uses SPY/AGG, total return.",
            "Real assets combine REIT index and a 2% gold sleeve.",
            "Alternatives held for diversification, not for return alone.",
            "Rebalance events are observed, not prescribed by the document.",
        ],
        "pull_quote": "An allocation is not a verdict on the future \u2014 it is the shelter you choose before the weather changes.",
        "pull_quote_attribution": "PivoxQuant Allocation Desk",
        "typeset_in": "Source Serif 4 \u00b7 Geist \u00b7 JetBrains Mono \u00b7 Noto Sans KR",
        "engine_note": "Historical record only. Allocation observation pipeline.",
        "LICENSE_NUMBER": None,
    },

    "insider_mirror.html": {
        "period_label": "April 2026",
        "user_name": USER_NAME,
        "period_end": "2026-04-22",
        "generated_at": GENERATED_AT,
        "issue_number": 4,
        "doc_ref": "PQ-IM-04 \u00b7 v2026.04.22",
        "hero_headline": [
            "Insiders leave paperwork.",
            "The market reads it",
            "after the fact.",
        ],
        "kpis_cover": {
            "filings_observed": 142,
            "net_buy_companies": 38,
            "net_sell_companies": 54,
            "top_sector": "Technology",
        },
        "filings_timeline": [
            {"d":1,"buy":2,"sell":1},{"d":2,"buy":1,"sell":3},{"d":3,"buy":4,"sell":2},
            {"d":4,"buy":2,"sell":4},{"d":5,"buy":1,"sell":6},{"d":6,"buy":3,"sell":2},
            {"d":7,"buy":5,"sell":3},{"d":8,"buy":2,"sell":7},{"d":9,"buy":1,"sell":5},
            {"d":10,"buy":4,"sell":3},{"d":11,"buy":2,"sell":4},{"d":12,"buy":6,"sell":2},
            {"d":13,"buy":3,"sell":5},{"d":14,"buy":1,"sell":8},{"d":15,"buy":4,"sell":3},
            {"d":16,"buy":2,"sell":4},{"d":17,"buy":5,"sell":2},{"d":18,"buy":3,"sell":6},
            {"d":19,"buy":1,"sell":5},{"d":20,"buy":4,"sell":3},{"d":21,"buy":2,"sell":7},
            {"d":22,"buy":6,"sell":2},{"d":23,"buy":3,"sell":4},{"d":24,"buy":1,"sell":5},
            {"d":25,"buy":4,"sell":3},{"d":26,"buy":2,"sell":6},{"d":27,"buy":5,"sell":3},
            {"d":28,"buy":3,"sell":7},{"d":29,"buy":2,"sell":4},{"d":30,"buy":4,"sell":2},
        ],
        "filings_margin": {
            "rule_10b5_1_share": 62.4,
            "avg_filing_lag_d":  1.8,
            "form4_pct":         88.0,
            "krx_share_pct":      4.2,
        },
        "spread_prose": [
            "Across the thirty-day window, 142 filings were observed on the EDGAR tape.",
            "The higher disposition count is the ordinary pattern of the tape, not a signal. No causal inference is claimed by this page.",
        ],
        "filings": [
            {"tkr":"NVDA",  "filer":"Huang, Jen-Hsun",     "role":"CEO / Director", "form":"Form 4",   "action":"sell", "shares": 120000, "value":137774400, "date":"2026-04-18", "spark":[0.50,0.48,0.47,0.46,0.44,0.43,0.41,0.40]},
            {"tkr":"META",  "filer":"Zuckerberg, Mark",    "role":"CEO / 10% Owner","form":"Form 4",   "action":"sell", "shares": 200000, "value":124200000, "date":"2026-04-15", "spark":[0.50,0.49,0.48,0.47,0.46,0.45,0.43,0.42]},
            {"tkr":"MSFT",  "filer":"Nadella, Satya",      "role":"CEO",            "form":"Form 4",   "action":"sell", "shares":  40000, "value": 17641200, "date":"2026-04-17", "spark":[0.50,0.49,0.48,0.48,0.47,0.46,0.46,0.45]},
            {"tkr":"TSLA",  "filer":"Taneja, Vaibhav",     "role":"CFO",            "form":"Form 4",   "action":"sell", "shares":  15000, "value":  3492000, "date":"2026-04-16", "spark":[0.50,0.48,0.47,0.45,0.44,0.42,0.41,0.40]},
            {"tkr":"AAPL",  "filer":"Maestri, Luca",       "role":"CFO",            "form":"Form 4",   "action":"buy",  "shares":   5000, "value":  1074400, "date":"2026-04-14", "spark":[0.50,0.51,0.52,0.54,0.56,0.58,0.60,0.62]},
            {"tkr":"AMZN",  "filer":"Olsavsky, Brian",     "role":"CFO",            "form":"Form 4",   "action":"sell", "shares":   8000, "value":  1580000, "date":"2026-04-13", "spark":[0.50,0.50,0.49,0.49,0.48,0.47,0.47,0.46]},
            {"tkr":"GOOGL", "filer":"Porat, Ruth",         "role":"President",      "form":"Form 4",   "action":"sell", "shares":  12000, "value":  2014800, "date":"2026-04-11", "spark":[0.50,0.49,0.48,0.48,0.47,0.47,0.46,0.46]},
            {"tkr":"AVGO",  "filer":"Tan, Hock E.",        "role":"CEO",            "form":"Form 144", "action":"sell", "shares":   4000, "value":  5496000, "date":"2026-04-10", "spark":[0.50,0.49,0.49,0.48,0.47,0.47,0.46,0.45]},
            {"tkr":"BRK.B", "filer":"Buffett, Warren",     "role":"CEO / Chair",    "form":"Form 4",   "action":"buy",  "shares":   2500, "value":  1092500, "date":"2026-04-09", "spark":[0.50,0.51,0.52,0.53,0.54,0.55,0.56,0.57]},
            {"tkr":"005930","filer":"Lee, Jae-Yong",       "role":"Chair",          "form":"DART",     "action":"buy",  "shares": 100000, "value":  5680000, "date":"2026-04-07", "spark":[0.50,0.50,0.51,0.52,0.53,0.54,0.55,0.56]},
        ],
        "sector_filings": [
            {"s":"Technology",   "v":42},{"s":"Financials",   "v":24},
            {"s":"Healthcare",   "v":18},{"s":"Cons. Disc.",  "v":16},
            {"s":"Industrials",  "v":14},{"s":"Comm.",        "v":10},
            {"s":"Staples",      "v": 8},{"s":"Energy",       "v": 6},
            {"s":"Materials",    "v": 2},{"s":"Real Estate",  "v": 1},
            {"s":"Utilities",    "v": 1},
        ],
        "net_buy_top": [
            {"t":"AAPL",  "v": 1074400},{"t":"BRK.B", "v": 1092500},
            {"t":"005930","v": 5680000},{"t":"HD",    "v":  840000},
            {"t":"UNH",   "v":  620000},{"t":"JPM",   "v":  540000},
            {"t":"KO",    "v":  420000},{"t":"PG",    "v":  380000},
            {"t":"COST",  "v":  312000},{"t":"LLY",   "v":  282000},
        ],
        "net_sell_top": [
            {"t":"NVDA",  "v":137774400},{"t":"META",  "v":124200000},
            {"t":"MSFT",  "v": 17641200},{"t":"AVGO",  "v":  5496000},
            {"t":"TSLA",  "v":  3492000},{"t":"GOOGL", "v":  2014800},
            {"t":"AMZN",  "v":  1580000},{"t":"ORCL",  "v":  1220000},
            {"t":"CRM",   "v":   960000},{"t":"NFLX",  "v":   780000},
        ],
        "form_types": [
            {"f":"Form 4",   "v":125, "c":"#0A0A0A"},
            {"f":"Form 144", "v": 10, "c":"#8B6F47"},
            {"f":"Form 5",   "v":  4, "c":"#A84C4C"},
            {"f":"DART",     "v":  3, "c":"#6B6B6B"},
        ],
        "reading_notes": [
            "Filings are public record; no action is advised.",
            "Insiders may file for many reasons \u2014 liquidity, diversification, option expiry.",
            "Causation is not claimed by this document.",
            "Rule 10b5-1 plans are pre-arranged; the tape does not separate them in the headline count.",
            "Form 4 requires filing within two business days of the transaction.",
            "KRX DART filings are merged in where available.",
        ],
        "pull_quote": "Insider activity is a confession made in public \u2014 legible, late, and only ever partial.",
        "pull_quote_attribution": "PivoxQuant Research Desk",
        "typeset_in": "Source Serif 4 \u00b7 Geist \u00b7 JetBrains Mono \u00b7 Noto Sans KR",
        "engine_note": "Historical record only. Public filing observation pipeline.",
    },

    "self_audit.html": {
        # Goldman IC v2 editorial — 6-page quarterly self-audit.
        "quarter_label": "Q1 2026",
        "user_name": USER_NAME,
        "period_start": "2026-01-01", "period_end": "2026-03-31",
        "generated_at": GENERATED_AT,
        "issue_number": 5,
        "doc_ref": "PQ-SA-05 · v2026.04.21",
        "review_date": "2026-04-21",
        "audit_score": 8.2,
        "red_flags": 0,
        "yellow_flags": 2,
        "positions_reviewed": 14,
        "journal_entries": 28,
        "audit_duration_min": 38,
        "prior_audit_score": "7.8",
        "hero_headline": [
            "Ten questions.",
            "Ten answers, honest",
            "or otherwise.",
        ],
        "trades_total": 22, "win_rate_pct": 64.0, "avg_return_pct": 4.8,
        "audit_letter": [
            (
                "This is the fifth quarterly audit of the book, and the first "
                "to open with no red flag. Position sizing held inside the "
                "self-set bound on every day of the quarter; the largest "
                "single name peaked at 9.2% of NAV on one session, still "
                "below the 10% ceiling."
            ),
            (
                "Cash reserve sat between 14% and 22% throughout, comfortably "
                "above the self-set floor of 10%. Trading frequency ran at "
                "1.8 closes per week, near the trailing four-quarter baseline. "
                "The observation journal carries an entry for every closed "
                "lot, with one gap of two sessions noted in early March."
            ),
            (
                "Two yellow flags are opened this quarter. First, the "
                "watchlist has grown to 41 names without a pruning pass. "
                "Second, dividend receipts were posted to the ledger within "
                "two weeks rather than the standard three sessions."
            ),
            (
                "The book's pattern this quarter is one of quiet composure. "
                "Mistakes were of omission, not of commission; none of them "
                "were structural. The audit closes with the observation that "
                "the habits most worth keeping are the ones least easily seen."
            ),
            (
                "This letter is a self-reading of the account's surface. It "
                "names no future and claims no insight beyond what the "
                "statements already quietly confirm."
            ),
        ],
        "checklist": [
            {"q": "Is position sizing within observed bounds?",
             "a": "Yes — largest single position peaked at 9.2% of NAV.",
             "flag": "green", "note": "Inside the 10% self-set ceiling on every session."},
            {"q": "Has any single position exceeded 10% of NAV?",
             "a": "No exceedance recorded.",
             "flag": "green", "note": "Concentration stayed below the self-set bound."},
            {"q": "Are stop-observation levels documented?",
             "a": "Documented for all 14 open positions.",
             "flag": "green", "note": "Journal entries tagged with level and rationale."},
            {"q": "Is cash reserve above the self-set threshold?",
             "a": "Yes — between 14% and 22% across the quarter.",
             "flag": "green", "note": "Floor of 10% held comfortably."},
            {"q": "Has trading frequency increased beyond baseline?",
             "a": "1.8 closes per week, near trailing 4Q baseline of 1.7.",
             "flag": "green", "note": "No meaningful acceleration observed."},
            {"q": "Are observed losses documented with context?",
             "a": "Eight closed lots at a loss; each with a journal note.",
             "flag": "green", "note": "Context includes thesis, exit reason, lesson field."},
            {"q": "Has the watchlist been pruned this quarter?",
             "a": "Watchlist at 41 names; last pruning pass 140 days ago.",
             "flag": "yellow", "note": "Pass overdue — schedule in the next fortnight."},
            {"q": "Are broker statements reconciled?",
             "a": "Reconciled to the cent through the quarter-end cutoff.",
             "flag": "green", "note": "Alpaca and KIS statements matched to the ledger."},
            {"q": "Are dividend receipts recorded?",
             "a": "Eight events recorded, two with posting lag beyond three sessions.",
             "flag": "yellow", "note": "Recording lag is a small process hygiene item."},
            {"q": "Has the observation journal been updated?",
             "a": "28 entries this quarter; one two-session gap in early March.",
             "flag": "green", "note": "Gap noted and closed with a retrospective entry."},
        ],
        "flag_dist": {"green": 8, "yellow": 2, "red": 0},
        "score_trend": [7.0, 7.4, 7.8, 8.2],
        "cat_flags": [
            {"cat": "Process",     "count": 2},
            {"cat": "Sizing",      "count": 1},
            {"cat": "Recording",   "count": 1},
            {"cat": "Watchlist",   "count": 1},
            {"cat": "Reconcile",   "count": 0},
        ],
        "audit_duration": [
            {"cat": "Review",   "min": 12},
            {"cat": "Ledger",   "min":  8},
            {"cat": "Letter",   "min": 10},
            {"cat": "Flagging", "min":  8},
        ],
        "pull_quote": "An audit is a mirror held quietly — not a judge's bench.",
        "pull_quote_attribution": "The Audit Voice",
        "not_verified": [
            {"category": "Tax correctness",       "detail": "Filings, withholding, and allowable deductions sit outside this ladder."},
            {"category": "Regulatory compliance", "detail": "Broker-side rule compliance is assumed, not checked row by row."},
            {"category": "Future conduct",        "detail": "A self-audit records the quarter past, never the one ahead."},
            {"category": "Personal integrity",    "detail": "Honesty is a prerequisite of the exercise, not its output."},
            {"category": "Market outcomes",       "detail": "The account owns the decisions; the market owns the weather."},
        ],
        "data_sources": ["Broker statements", "Observation journal", "Rebalance log"],
        "typeset_in": "Source Serif 4 · Geist · JetBrains Mono · Noto Sans KR",
        "engine_note": "Historical record only. Quarterly self-observation ladder",
        "pattern_summary": "관찰 — 지난 분기 매수 결정 22건 중 14건이 양(+)의 결과를 기록했습니다.",
        "best_decisions": [
            {"ticker": "NVDA", "buy_date": "2026-01-14", "buy_price": 712.45, "sell_price": None,   "return_pct": 61.13},
            {"ticker": "AVGO", "buy_date": "2026-02-03", "buy_price": 1280.0, "sell_price": 1540.0, "return_pct": 20.31},
            {"ticker": "META", "buy_date": "2026-03-22", "buy_price":  478.0, "sell_price":  621.0, "return_pct": 29.92},
        ],
        "worst_decisions": [
            {"ticker": "TSLA", "buy_date": "2026-02-12", "buy_price": 218.5, "sell_price": 188.4, "return_pct": -13.77},
            {"ticker": "NKE",  "buy_date": "2026-03-01", "buy_price":  78.4, "sell_price":  71.2, "return_pct":  -9.18},
            {"ticker": "KO",   "buy_date": "2026-03-14", "buy_price":  62.1, "sell_price":  59.8, "return_pct":  -3.70},
        ],
        "LICENSE_NUMBER": None,
    },

    "burn_rate.html": {
        # Goldman IC v2 editorial — 6-page personal household burn ledger.
        "period_label": "Apr 2026",
        "period_label_long": "April 2026",
        "user_name": USER_NAME,
        "period_start": "2026-04-01", "period_end": "2026-04-30",
        "generated_at": GENERATED_AT,
        "issue_number": 12,
        "doc_ref": "PQ-BR-12 · v2026.04.21",
        "hero_headline": [
            "A slow arithmetic.",
            "Money walks out,",
            "seldom in crowds.",
        ],
        "monthly_burn_usd":     2480,
        "runway_months":          32,
        "savings_rate_pct":     62.0,
        "fixed_cost_ratio_pct": 41.0,
        "housing_share_pct":    48,
        "yoy_burn_pct":       "+3.2",
        "variance_usd":       "180",
        "burn_series": [
            {"m": "May", "housing": 1180, "food": 420, "transport": 210, "leisure": 310, "other": 240},
            {"m": "Jun", "housing": 1180, "food": 380, "transport": 240, "leisure": 360, "other": 210},
            {"m": "Jul", "housing": 1180, "food": 460, "transport": 220, "leisure": 520, "other": 180},
            {"m": "Aug", "housing": 1180, "food": 470, "transport": 200, "leisure": 480, "other": 220},
            {"m": "Sep", "housing": 1180, "food": 390, "transport": 230, "leisure": 290, "other": 260},
            {"m": "Oct", "housing": 1180, "food": 420, "transport": 250, "leisure": 310, "other": 240},
            {"m": "Nov", "housing": 1180, "food": 450, "transport": 270, "leisure": 380, "other": 280},
            {"m": "Dec", "housing": 1180, "food": 520, "transport": 320, "leisure": 480, "other": 340},
            {"m": "Jan", "housing": 1180, "food": 440, "transport": 280, "leisure": 220, "other": 240},
            {"m": "Feb", "housing": 1180, "food": 410, "transport": 230, "leisure": 240, "other": 220},
            {"m": "Mar", "housing": 1180, "food": 430, "transport": 260, "leisure": 280, "other": 230},
            {"m": "Apr", "housing": 1180, "food": 420, "transport": 240, "leisure": 360, "other": 280},
        ],
        "burn_prose": [
            (
                "Twelve months of burn sit between $2,260 and $3,100, with the "
                "median close to $2,480. Housing runs as the invariant base — "
                "unchanged over the year, so a flat bronze band at the bottom "
                "of the stack."
            ),
            (
                "Seasonality arrives in leisure and, to a lesser extent, food. "
                "The December lift is familiar and benign; January's quiet "
                "close is equally familiar. The shape of the year is a rhythm, "
                "not a trend."
            ),
        ],
        "cat_rows": [
            {"cat": "Housing",       "this": 1180, "last": 1180, "avg3": 1180, "yoy":  0.0, "spark": [0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50, 0.50]},
            {"cat": "Food",          "this":  420, "last":  430, "avg3":  420, "yoy":  4.2, "spark": [0.38, 0.42, 0.40, 0.44, 0.48, 0.46, 0.50, 0.42]},
            {"cat": "Transport",     "this":  240, "last":  260, "avg3":  243, "yoy": -2.1, "spark": [0.40, 0.48, 0.50, 0.52, 0.46, 0.44, 0.42, 0.40]},
            {"cat": "Leisure",       "this":  360, "last":  280, "avg3":  293, "yoy":  8.4, "spark": [0.28, 0.32, 0.36, 0.40, 0.44, 0.48, 0.54, 0.62]},
            {"cat": "Other",         "this":  280, "last":  230, "avg3":  250, "yoy":  6.2, "spark": [0.40, 0.42, 0.46, 0.44, 0.48, 0.50, 0.54, 0.56]},
            {"cat": "Subscriptions", "this":   84, "last":   78, "avg3":   80, "yoy": 12.0, "spark": [0.30, 0.34, 0.36, 0.38, 0.40, 0.42, 0.46, 0.52]},
            {"cat": "Utilities",     "this":  152, "last":  148, "avg3":  150, "yoy":  1.3, "spark": [0.45, 0.46, 0.48, 0.50, 0.48, 0.50, 0.52, 0.50]},
            {"cat": "Health",        "this":  118, "last":   84, "avg3":  102, "yoy":  4.0, "spark": [0.30, 0.32, 0.34, 0.40, 0.42, 0.46, 0.50, 0.54]},
        ],
        "share_quad": [
            {"n": "Housing",   "v": 1180},
            {"n": "Food",      "v":  420},
            {"n": "Transport", "v":  240},
            {"n": "Leisure",   "v":  360},
            {"n": "Other",     "v":  280},
        ],
        "fixed_variable": [
            {"m": "May", "fix": 1332, "var":  958},
            {"m": "Jun", "fix": 1332, "var":  958},
            {"m": "Jul", "fix": 1332, "var": 1288},
            {"m": "Aug", "fix": 1332, "var": 1218},
            {"m": "Sep", "fix": 1332, "var":  828},
            {"m": "Oct", "fix": 1332, "var":  868},
            {"m": "Nov", "fix": 1332, "var": 1078},
            {"m": "Dec", "fix": 1332, "var": 1328},
            {"m": "Jan", "fix": 1332, "var":  848},
            {"m": "Feb", "fix": 1332, "var":  768},
            {"m": "Mar", "fix": 1332, "var":  868},
            {"m": "Apr", "fix": 1332, "var": 1088},
        ],
        "runway_scenarios": {
            "base":  [32, 32, 31, 31, 30, 30, 29, 28, 28, 27, 27, 26],
            "plus":  [32, 31, 30, 29, 28, 27, 26, 25, 24, 23, 22, 21],
            "minus": [32, 32, 32, 32, 32, 32, 33, 33, 33, 34, 34, 34],
        },
        "save_rate_series": [58, 61, 63, 62, 65, 64, 60, 55, 62, 64, 63, 62],
        "pull_quote": "Frugality is not a strategy. It is the floor on which every strategy stands.",
        "pull_quote_attribution": "The Ledger Voice",
        "not_verified": [
            {"category": "Tax deductibility",       "detail": "Allowability of line items under local tax code sits outside this ledger."},
            {"category": "Insurance coverage",      "detail": "Protection against unrecorded contingencies is a separate conversation."},
            {"category": "Lifestyle inflation",     "detail": "Upward drift in baseline spending is a year-over-year reading, not a monthly one."},
            {"category": "Debt servicing",          "detail": "Obligations held outside the household ledger are not included here."},
            {"category": "Life events",             "detail": "Planned or unplanned events will redraw the stack overnight."},
        ],
        "data_sources": ["Bank statements", "Credit card statements", "Manual ledger", "Budget app export"],
        "typeset_in": "Source Serif 4 · Geist · JetBrains Mono · Noto Sans KR",
        "engine_note": "Historical record only. Household burn ledger",
        "LICENSE_NUMBER": None,
        # Legacy trading-burn back-compat
        "trades_total": 24,
        "burn_total": 184_200.0, "burn_pct": 0.186,
        "notional_total": 98_800_000.0,
        "commission_total":     44_100.0,
        "tx_tax_total":         44_800.0,
        "cgt_est_total":        14_400.0,
        "fx_spread_total":      41_200.0,
        "slippage_total":       39_700.0,
        "by_market": [
            {"market": "US (NYSE/NASDAQ)", "trades": 18, "notional": 76_400_000, "burn": 142_100},
            {"market": "KR (KOSPI/KOSDAQ)", "trades":  6, "notional": 22_400_000, "burn":  42_100},
        ],
    },

    "credit_rating.html": {
        "as_of": "2026-04-22",
        "user_name": USER_NAME,
        "generated_at": GENERATED_AT,
        "issue_number": 2,
        "doc_ref": "PQ-CR-02 \u00b7 v2026.04.22",
        "hero_headline": [
            "Credit is an obligation",
            "to repay. Ratings are",
            "the weather around it.",
        ],
        "kpis_cover": {
            "avg_rating": "A-",
            "ig_share_pct": 78.0,
            "hy_share_pct": 22.0,
            "weighted_spread_bps": 185,
        },
        "rating_distribution": [
            {"g": "AAA", "w":  4.0},
            {"g": "AA",  "w": 10.0},
            {"g": "A",   "w": 28.0},
            {"g": "BBB", "w": 36.0},
            {"g": "BB",  "w": 12.0},
            {"g": "B",   "w":  6.0},
            {"g": "CCC", "w":  3.0},
            {"g": "CC",  "w":  0.6},
            {"g": "C",   "w":  0.3},
            {"g": "D",   "w":  0.1},
        ],
        "rating_margin": {
            "upgrades_24m": 3, "downgrades_24m": 1,
            "watch_neg": 2, "watch_pos": 1,
        },
        "spread_prose": [
            "The book clusters tightly around the A and BBB rungs, a reading that accounts for 64% of the weighted exposure and keeps the average composite rating at A-. The weight held above the IG/HY line sits at 78%, a figure that has drifted two points lower over the trailing ninety days as the high-yield cohort absorbed more capital through the rebalance cycle.",
            "Below the dashed divider, the BB rung carries 12% \u2014 a benign-looking figure once paired with the sector notes on page three. The deeper-stress buckets (CCC and below) remain at 4.0% combined, a reading held by two credits and not added to since the previous audit window.",
        ],
        "positions": [
            {"sym":"US-TSY-10Y",     "issuer":"U.S. Treasury",      "rating":"AAA", "weight":12.0, "ytm":4.20, "dur":8.4, "spread":  0, "spark":[0.50,0.52,0.54,0.56,0.58,0.60,0.62,0.64]},
            {"sym":"MSFT 2.52 2031", "issuer":"Microsoft",          "rating":"AAA", "weight": 8.0, "ytm":4.65, "dur":6.2, "spread": 45, "spark":[0.50,0.51,0.53,0.55,0.57,0.58,0.60,0.61]},
            {"sym":"AAPL 3.35 2029", "issuer":"Apple",              "rating":"AA",  "weight": 7.2, "ytm":4.78, "dur":4.9, "spread": 58, "spark":[0.50,0.52,0.54,0.55,0.57,0.59,0.60,0.62]},
            {"sym":"JNJ 2.90 2028",  "issuer":"Johnson & J.",       "rating":"AA",  "weight": 6.8, "ytm":4.82, "dur":4.1, "spread": 62, "spark":[0.50,0.51,0.53,0.55,0.56,0.58,0.60,0.61]},
            {"sym":"GS 4.25 2030",   "issuer":"Goldman Sachs",      "rating":"A",   "weight":10.4, "ytm":5.12, "dur":5.6, "spread": 92, "spark":[0.50,0.52,0.55,0.57,0.60,0.62,0.64,0.65]},
            {"sym":"F 5.40 2029",    "issuer":"Ford Motor Co.",     "rating":"BBB", "weight":11.2, "ytm":5.88, "dur":4.3, "spread":168, "spark":[0.50,0.52,0.54,0.57,0.60,0.64,0.66,0.69]},
            {"sym":"T 4.90 2030",    "issuer":"AT&T",               "rating":"BBB", "weight": 9.6, "ytm":5.64, "dur":5.2, "spread":144, "spark":[0.50,0.51,0.53,0.55,0.58,0.60,0.62,0.63]},
            {"sym":"CCL 6.00 2029",  "issuer":"Carnival",           "rating":"BB",  "weight": 6.4, "ytm":7.20, "dur":3.8, "spread":300, "spark":[0.50,0.52,0.54,0.56,0.59,0.62,0.66,0.68]},
            {"sym":"RIG 7.50 2031",  "issuer":"Transocean",         "rating":"B",   "weight": 4.2, "ytm":9.12, "dur":4.4, "spread":492, "spark":[0.50,0.53,0.55,0.58,0.62,0.66,0.70,0.73]},
            {"sym":"UHC 8.00 2028",  "issuer":"Utility Holdings",   "rating":"CCC", "weight": 2.4, "ytm":11.40,"dur":3.2, "spread":720, "spark":[0.50,0.52,0.56,0.60,0.65,0.70,0.74,0.78]},
        ],
        "credit_curve": [
            {"r":"AAA","s": 22},{"r":"AA","s": 48},{"r":"A","s": 92},{"r":"BBB","s":164},
            {"r":"BB","s":310},{"r":"B","s":492},{"r":"CCC","s":720},
        ],
        "duration_histogram": [
            {"b":"0-2", "w": 8.0},{"b":"2-4", "w":22.0},{"b":"4-6", "w":32.0},
            {"b":"6-8", "w":18.0},{"b":"8-10","w":12.0},{"b":"10+", "w": 8.0},
        ],
        "rating_migration": [
            {"k":"Stable",    "v": 9, "c":"#8B6F47"},
            {"k":"Upgraded",  "v": 3, "c":"#8B6F47"},
            {"k":"Downgraded","v": 1, "c":"#A84C4C"},
            {"k":"Withdrawn", "v": 1, "c":"#8a8a8a"},
        ],
        "sector_concentration": [
            {"s":"Financials",   "w":24.0},{"s":"Treasury",     "w":18.0},
            {"s":"Technology",   "w":14.0},{"s":"Healthcare",   "w":12.0},
            {"s":"Industrials",  "w":10.0},{"s":"Energy",       "w": 8.0},
            {"s":"Cons. Disc.",  "w": 6.0},{"s":"Other",        "w": 8.0},
        ],
        "reading_notes": [
            "Ratings are observations from Moody's, S&P, and Fitch \u2014 composite weighted by notch.",
            "OAS values from FINRA TRACE tape, end-of-day mid marks.",
            "Duration computed on modified basis, including embedded optionality.",
            "IG/HY line at BBB-/Baa3 per agency convention.",
            "Migrations are counted per issuer, not per CUSIP line.",
        ],
        "pull_quote": "A credit rating is a letter the market writes about itself \u2014 read with interest, never as instruction.",
        "pull_quote_attribution": "PivoxQuant Credit Desk",
        "typeset_in": "Source Serif 4 \u00b7 Geist \u00b7 JetBrains Mono \u00b7 Noto Sans KR",
        "engine_note": "Historical record only. Rating observation pipeline.",
        "LICENSE_NUMBER": None,
    },

    "dividend_income.html": {
        "month_label": "April 2026",
        "user_name": USER_NAME,
        "generated_at": GENERATED_AT,
        "issue_number": 4,
        "doc_ref": "PQ-DI-04 \u00b7 v2026.04.22",
        "hero_headline": [
            "Dividends are slow letters.",
            "Written quarterly,",
            "opened monthly.",
        ],
        "kpis_cover": {
            "ytd_usd": 3240, "monthly_usd": 412,
            "yield_pct": 2.8, "yoy_growth_pct": 6.4,
        },
        "monthly_bars": [
            {"m":"May","v":172},{"m":"Jun","v":318},{"m":"Jul","v":164},
            {"m":"Aug","v":242},{"m":"Sep","v":188},{"m":"Oct","v":272},
            {"m":"Nov","v":196},{"m":"Dec","v":412},{"m":"Jan","v":214},
            {"m":"Feb","v":324},{"m":"Mar","v":226},{"m":"Apr","v":412},
        ],
        "dividend_margin": {
            "positions_paying": 14, "positions_total": 22,
            "largest_payer_pct": 18.4, "withholding_pct": 11.2,
        },
        "spread_prose": [
            "The April receipt ties December as the year's highest month.",
            "Year-to-date dividends run 6.4% above the same period last year.",
        ],
        "dividend_rows": [
            {"sym":"MSFT","shares": 18, "per_sh":0.83, "freq":"Q", "ex":"2026-04-10", "pay":"2026-04-14", "total":14.94, "spark":[0.50,0.52,0.54,0.56,0.58,0.60,0.62,0.64]},
            {"sym":"AAPL","shares": 35, "per_sh":0.24, "freq":"Q", "ex":"2026-04-08", "pay":"2026-04-12", "total":8.40,  "spark":[0.50,0.51,0.52,0.53,0.54,0.55,0.56,0.58]},
            {"sym":"KO",  "shares": 60, "per_sh":0.49, "freq":"Q", "ex":"2026-04-22", "pay":"2026-04-26", "total":29.40, "spark":[0.50,0.51,0.52,0.53,0.54,0.55,0.56,0.57]},
            {"sym":"JNJ", "shares": 22, "per_sh":1.19, "freq":"Q", "ex":"2026-04-18", "pay":"2026-04-22", "total":26.18, "spark":[0.50,0.51,0.53,0.54,0.55,0.56,0.58,0.60]},
            {"sym":"PG",  "shares": 25, "per_sh":0.94, "freq":"Q", "ex":"2026-04-15", "pay":"2026-04-19", "total":23.50, "spark":[0.50,0.52,0.53,0.54,0.56,0.57,0.58,0.60]},
            {"sym":"XOM", "shares": 40, "per_sh":0.95, "freq":"Q", "ex":"2026-04-24", "pay":"2026-04-28", "total":38.00, "spark":[0.50,0.52,0.54,0.56,0.58,0.60,0.62,0.64]},
            {"sym":"VZ",  "shares": 30, "per_sh":0.66, "freq":"Q", "ex":"2026-04-09", "pay":"2026-04-13", "total":19.80, "spark":[0.50,0.50,0.51,0.51,0.52,0.52,0.53,0.54]},
            {"sym":"JPM", "shares": 12, "per_sh":1.15, "freq":"Q", "ex":"2026-04-11", "pay":"2026-04-15", "total":13.80, "spark":[0.50,0.51,0.53,0.54,0.56,0.58,0.60,0.62]},
            {"sym":"T",   "shares": 50, "per_sh":0.28, "freq":"Q", "ex":"2026-04-10", "pay":"2026-04-14", "total":14.00, "spark":[0.50,0.50,0.50,0.49,0.49,0.49,0.48,0.48]},
            {"sym":"MCD", "shares":  8, "per_sh":1.67, "freq":"Q", "ex":"2026-04-02", "pay":"2026-04-08", "total":13.36, "spark":[0.50,0.51,0.52,0.53,0.54,0.55,0.57,0.59]},
        ],
        "sector_mix": [
            {"s":"Staples",    "w":28.0},{"s":"Financials", "w":19.0},
            {"s":"Energy",     "w":14.0},{"s":"Healthcare", "w":12.0},
            {"s":"Comm.",      "w": 9.0},{"s":"Industrials","w": 8.0},
            {"s":"Tech",       "w": 6.0},{"s":"Other",      "w": 4.0},
        ],
        "yoy_growth": [
            {"t":"MCD", "v":  9.8},{"t":"JPM", "v":  8.4},
            {"t":"JNJ", "v":  6.2},{"t":"MSFT","v": 10.2},
            {"t":"PG",  "v":  4.9},{"t":"KO",  "v":  4.1},
            {"t":"XOM", "v":  3.2},{"t":"AAPL","v":  4.0},
            {"t":"VZ",  "v":  1.8},{"t":"T",   "v": -0.6},
        ],
        "yield_scatter": [
            {"t":"KO",   "y":3.0, "p": 64, "sz":60},
            {"t":"JNJ",  "y":3.2, "p":152, "sz":26},
            {"t":"VZ",   "y":6.2, "p": 42, "sz":30},
            {"t":"T",    "y":6.6, "p": 17, "sz":50},
            {"t":"XOM",  "y":3.4, "p":112, "sz":40},
            {"t":"PG",   "y":2.6, "p":146, "sz":25},
            {"t":"MSFT", "y":0.7, "p":412, "sz":18},
            {"t":"AAPL", "y":0.5, "p":188, "sz":35},
            {"t":"JPM",  "y":2.8, "p":206, "sz":12},
            {"t":"MCD",  "y":2.4, "p":278, "sz": 8},
        ],
        "reading_notes": [
            "Dividends are gross of withholding unless stated.",
            "Ex-date is the first day without the right to the payment.",
            "Frequencies follow issuer convention, not fiscal calendar.",
            "Yield is trailing-twelve-month sum / current price.",
            "DRIP (automatic reinvestment) is not enabled on this book.",
        ],
        "pull_quote": "A dividend is a kindness from a company to its owners \u2014 unremarkable until counted, cumulative once you do.",
        "pull_quote_attribution": "PivoxQuant Dividend Desk",
        "typeset_in": "Source Serif 4 \u00b7 Geist \u00b7 JetBrains Mono \u00b7 Noto Sans KR",
        "engine_note": "Historical record only. Dividend observation pipeline.",
    },

    "portfolio_segment.html": {
        # Goldman IC v2 editorial — 6-page portfolio segment observation.
        "user_name": USER_NAME,
        "period_label": "April 2026",
        "issue_number": 4,
        "doc_ref": "PQ-PS-04",
        "generated_at": GENERATED_AT,
        "typeset_in": "Source Serif 4 · Geist · JetBrains Mono",
        "LICENSE_NUMBER": None,
        "hero_headline": [
            "A portfolio is a choir.",
            "Each voice a sector, style, or region.",
            "We listen, then write down what we hear.",
        ],
        "kpi_sectors":       8,
        "kpi_styles_label":  "Growth · Value · Core",
        "kpi_regions_label": "US · International",
        "kpi_hhi":           1840,
        "treemap_segments": [
            {"name": "Technology",       "weight": 32.5, "ret": 11.8},
            {"name": "Healthcare",       "weight": 14.2, "ret":  3.5},
            {"name": "Financials",       "weight": 12.8, "ret":  4.8},
            {"name": "Consumer Disc.",   "weight":  9.5, "ret": -2.1},
            {"name": "Consumer Staples", "weight":  8.1, "ret":  1.4},
            {"name": "Industrials",      "weight":  7.2, "ret":  5.2},
            {"name": "Energy",           "weight":  5.6, "ret":  8.2},
            {"name": "REITs",            "weight":  4.8, "ret": -0.8},
            {"name": "Cash",             "weight":  3.1, "ret":  0.2},
            {"name": "International",    "weight":  2.2, "ret":  3.1},
        ],
        "segment_ladder": [
            {"segment": "Technology",       "weight": 32.5, "target": 30.0, "drift": "+2.5", "ret_contrib": "+3.84", "vol_contrib": "42%", "beta": 1.28, "spark": [0, 2.1, 4.2, 6.8, 8.1, 10.2, 11.4, 11.8]},
            {"segment": "Healthcare",       "weight": 14.2, "target": 15.0, "drift": "-0.8", "ret_contrib": "+0.50", "vol_contrib": "10%", "beta": 0.74, "spark": [0, 0.4, 1.2, 1.8, 2.4, 2.9, 3.2, 3.5]},
            {"segment": "Financials",       "weight": 12.8, "target": 12.0, "drift": "+0.8", "ret_contrib": "+0.61", "vol_contrib": "12%", "beta": 1.14, "spark": [0, 0.8, 1.6, 2.1, 2.9, 3.8, 4.4, 4.8]},
            {"segment": "Consumer Disc.",   "weight":  9.5, "target": 10.0, "drift": "-0.5", "ret_contrib": "-0.20", "vol_contrib":  "9%", "beta": 1.22, "spark": [0, -0.2, -0.8, -1.1, -1.5, -1.8, -1.9, -2.1]},
            {"segment": "Consumer Staples", "weight":  8.1, "target":  8.0, "drift": "+0.1", "ret_contrib": "+0.11", "vol_contrib":  "4%", "beta": 0.58, "spark": [0, 0.2, 0.4, 0.6, 0.9, 1.1, 1.2, 1.4]},
            {"segment": "Industrials",      "weight":  7.2, "target":  7.0, "drift": "+0.2", "ret_contrib": "+0.37", "vol_contrib":  "7%", "beta": 1.05, "spark": [0, 1.1, 2.0, 2.8, 3.4, 4.2, 4.8, 5.2]},
            {"segment": "Energy",           "weight":  5.6, "target":  6.0, "drift": "-0.4", "ret_contrib": "+0.46", "vol_contrib":  "6%", "beta": 0.92, "spark": [0, 1.4, 3.2, 4.8, 5.9, 7.1, 7.8, 8.2]},
            {"segment": "REITs",            "weight":  4.8, "target":  5.0, "drift": "-0.2", "ret_contrib": "-0.04", "vol_contrib":  "3%", "beta": 0.81, "spark": [0, -0.1, -0.3, -0.5, -0.6, -0.7, -0.8, -0.8]},
            {"segment": "Cash",             "weight":  3.1, "target":  5.0, "drift": "-1.9", "ret_contrib": "+0.01", "vol_contrib":  "0%", "beta": 0.00, "spark": [0, 0.05, 0.08, 0.12, 0.15, 0.18, 0.20, 0.20]},
            {"segment": "International",    "weight":  2.2, "target":  2.0, "drift": "+0.2", "ret_contrib": "+0.07", "vol_contrib":  "7%", "beta": 0.88, "spark": [0, 0.6, 1.2, 1.8, 2.2, 2.6, 2.9, 3.1]},
        ],
        "style_box": [
            [0.08, 0.12, 0.04],
            [0.06, 0.14, 0.06],
            [0.24, 0.18, 0.08],
        ],
        "style_box_labels": {
            "rows": ["Small", "Mid", "Large"],
            "cols": ["Value", "Core", "Growth"],
        },
        "region_split": [
            {"name": "US",        "v": 72.5},
            {"name": "Intl Dev.", "v": 18.4},
            {"name": "EM",        "v":  6.0},
            {"name": "Cash",      "v":  3.1},
        ],
        "sector_rotation": [
            {"name": "Technology", "series": [0, 1.2, 2.8, 3.4, 4.1, 5.2, 6.1, 7.4, 8.8, 9.6, 10.8, 11.8]},
            {"name": "Energy",     "series": [0, 0.8, 1.4, 2.2, 2.8, 3.6, 4.4, 5.2, 6.1, 6.8, 7.6, 8.2]},
            {"name": "Financials", "series": [0, 0.4, 0.8, 1.2, 1.8, 2.2, 2.8, 3.2, 3.8, 4.2, 4.6, 4.8]},
            {"name": "Healthcare", "series": [0, 0.2, 0.6, 0.9, 1.3, 1.6, 2.1, 2.4, 2.8, 3.1, 3.3, 3.5]},
        ],
        "segment_corr_labels": ["Tech", "Fin", "Health", "Energy", "REITs"],
        "segment_corr_matrix": [
            [1.00, 0.54, 0.38, 0.22, 0.41],
            [0.54, 1.00, 0.32, 0.28, 0.48],
            [0.38, 0.32, 1.00, 0.18, 0.36],
            [0.22, 0.28, 0.18, 1.00, 0.24],
            [0.41, 0.48, 0.36, 0.24, 1.00],
        ],
        "pull_quote": (
            "Segments are not strategies — they are the chairs your decisions "
            "happened to sit in."
        ),
        "pull_quote_attribution": "PivoxQuant Research Desk",
        "right_rail_notes": [
            "Segmentation is a lens, not a prescription.",
            "Boundaries are conventions — GICS, MSCI, or style-box.",
            "Weights are observed month-end, not intra-month.",
            "Concentration is surfaced for transparency.",
            "Informational only — not a portfolio instruction.",
        ],
        "not_answered": [
            "Whether any single weight is appropriate for a given household.",
            "Tax consequences of rebalancing between segments.",
            "Forward-looking style or sector rotation.",
            "Correlated news shocks outside the observation window.",
            "Personal liquidity needs by segment.",
        ],
        "data_sources": [
            {"key": "Holdings",         "value": "Broker statements · month-end"},
            {"key": "Style taxonomy",   "value": "FactSet / MSCI style classification"},
            {"key": "Region taxonomy",  "value": "MSCI region · developed / emerging"},
            {"key": "Fundamentals",     "value": "FMP v4 Stable · sector ratios"},
        ],
        "engine_note": "Historical record only. Portfolio segmentation pipeline.",
    },

    "kpi_dashboard.html": {
        # Goldman IC v2 editorial — 6-page monthly KPI observation.
        "user_name": USER_NAME,
        "period_label": "April 2026",
        "issue_number": 4,
        "doc_ref": "PQ-KPI-04",
        "generated_at": GENERATED_AT,
        "typeset_in": "Source Serif 4 · Geist · JetBrains Mono",
        "LICENSE_NUMBER": None,
        "hero_headline": [
            "Numbers are the vocabulary.",
            "Observation is the grammar.",
            "This is a month's sentence.",
        ],
        "kpi_nav_label": "$127,450",
        "kpi_mtd_pct":    2.4,
        "kpi_ytd_pct":    8.7,
        "kpi_sharpe":     0.94,
        "nav_curve": [
            124440, 124680, 124920, 125110, 124880, 124940, 125220,
            125480, 125710, 125940, 126220, 126040, 125810, 126110,
            126480, 126820, 127110, 127380, 127210, 127450,
        ],
        "nav_best_day_index":  15,
        "nav_worst_day_index":  4,
        "nav_best_day_delta":  "+0.81%",
        "nav_worst_day_delta": "-0.24%",
        "kpi_ladder": [
            {"metric": "NAV",              "current": "$127,450", "last_mo": "$124,440", "avg_3m": "$122,900", "ytd": "+8.7%",  "range": "$115k — $127k", "spark": [0, 0.4, 0.9, 1.3, 1.8, 2.2, 2.4]},
            {"metric": "Cash Ratio",       "current": "8.1%",     "last_mo": "9.4%",     "avg_3m": "10.2%",    "ytd": "-2.1pp", "range": "6.4 — 12.8%",   "spark": [10.2, 10.0, 9.7, 9.4, 9.1, 8.6, 8.1]},
            {"metric": "Avg Position Size","current": "4.2%",     "last_mo": "4.0%",     "avg_3m": "3.9%",     "ytd": "+0.3pp", "range": "3.4 — 4.6%",    "spark": [3.9, 3.9, 4.0, 4.0, 4.1, 4.1, 4.2]},
            {"metric": "Win Rate",         "current": "58%",      "last_mo": "54%",      "avg_3m": "56%",      "ytd": "+4pp",   "range": "48 — 62%",      "spark": [54, 55, 55, 56, 57, 57, 58]},
            {"metric": "Avg Holding Days", "current": "24",       "last_mo": "22",       "avg_3m": "23",       "ytd": "+2",     "range": "18 — 28",       "spark": [22, 22, 23, 23, 23, 24, 24]},
            {"metric": "Turnover",         "current": "28%",      "last_mo": "34%",      "avg_3m": "31%",      "ytd": "-6pp",   "range": "24 — 42%",      "spark": [34, 33, 31, 30, 29, 28, 28]},
            {"metric": "Beta",             "current": "0.94",     "last_mo": "0.98",     "avg_3m": "0.96",     "ytd": "-0.04",  "range": "0.88 — 1.04",   "spark": [0.98, 0.97, 0.96, 0.95, 0.95, 0.94, 0.94]},
            {"metric": "Vol · Ann.",       "current": "14.2%",    "last_mo": "15.1%",    "avg_3m": "14.8%",    "ytd": "-0.9pp", "range": "12.4 — 17.1%",  "spark": [15.1, 14.9, 14.7, 14.5, 14.4, 14.3, 14.2]},
            {"metric": "Sharpe · Ann.",    "current": "0.94",     "last_mo": "0.81",     "avg_3m": "0.86",     "ytd": "+0.13",  "range": "0.62 — 1.04",   "spark": [0.81, 0.82, 0.84, 0.88, 0.91, 0.93, 0.94]},
            {"metric": "Max Drawdown",     "current": "-6.2%",    "last_mo": "-7.1%",    "avg_3m": "-7.8%",    "ytd": "-8.7%",  "range": "-9.4 — -4.1%",  "spark": [-7.1, -6.9, -6.6, -6.4, -6.3, -6.2, -6.2]},
        ],
        "return_attribution": [
            {"name": "Technology",  "v":  3.84},
            {"name": "Healthcare",  "v":  0.50},
            {"name": "Financials",  "v":  0.61},
            {"name": "Energy",      "v":  0.46},
            {"name": "Industrials", "v":  0.37},
            {"name": "Staples",     "v":  0.11},
            {"name": "Cons. Disc.", "v": -0.20},
            {"name": "REITs",       "v": -0.04},
        ],
        "winloss_bins":   [-6, -4, -2, 0, 2, 4, 6],
        "winloss_counts": [2, 4, 8, 14, 18, 10, 4],
        "hold_bins":   ["0-7", "8-14", "15-30", "31-60", "61+"],
        "hold_counts": [6, 10, 22, 14, 8],
        "rolling_sharpe": [0.52, 0.58, 0.61, 0.68, 0.72, 0.78, 0.82, 0.86, 0.88, 0.91, 0.93, 0.94],
        "pull_quote": (
            "A dashboard is a room's mirror — it shows the shape you've "
            "taken today, not the shape you intend."
        ),
        "pull_quote_attribution": "PivoxQuant Research Desk",
        "right_rail_notes": [
            "All metrics are observed ex-post, from realised statements.",
            "Thresholds are self-set, not universal.",
            "Metrics describe behaviour; they do not direct it.",
            "Rolling windows are 30 trading days.",
            "Informational only — not a portfolio instruction.",
        ],
        "not_answered": [
            "Whether any metric is appropriate for a given objective.",
            "Forward-looking projections of NAV or Sharpe.",
            "Tax consequences of realised trades.",
            "Regime shifts outside the observation window.",
            "Personal cash-flow timing.",
        ],
        "data_sources": [
            {"key": "Broker",     "value": "Alpaca · Paper account statements"},
            {"key": "Engine",     "value": "Portfolio observation pipeline"},
            {"key": "Risk-free",  "value": "3-Month T-Bill (FRED DGS3MO)"},
            {"key": "Window",     "value": "Monthly marks · trailing 12 months"},
        ],
        "engine_note": "Historical record only. Monthly KPI observation pipeline.",
    },

    "dd_checklist.html": {
        # Goldman IC v2 editorial — 6-page single-ticker DD observation.
        "user_name": USER_NAME,
        "ticker":    "AAPL",
        "period_label": "Q2 2026",
        "issue_number": 2,
        "doc_ref":   "PQ-DD-AAPL-Q2",
        "generated_at": GENERATED_AT,
        "typeset_in": "Source Serif 4 · Geist · JetBrains Mono",
        "LICENSE_NUMBER": None,
        "hero_headline": [
            "Questions, patiently asked.",
            "Answers, honestly recorded.",
            "A checklist is not a verdict.",
        ],
        "completeness_text": "24 / 30",
        "red_flags":         0,
        "review_date":       "2026-04-21",
        "fundamentals_axes": [
            {"label": "Revenue Growth",   "value": 0.78, "raw": "+6.1% · 5Y CAGR"},
            {"label": "Operating Margin", "value": 0.88, "raw": "30.2% · TTM"},
            {"label": "Return on Equity", "value": 0.92, "raw": "154% · TTM"},
            {"label": "FCF Yield",        "value": 0.62, "raw": "3.4% · TTM"},
            {"label": "Debt Ratio",       "value": 0.55, "raw": "1.97× · D/E"},
        ],
        "checklist_items": [
            {"no": "01", "q": "Is revenue growth consistent over 5 years?",
             "a": "5Y revenue CAGR 6.1%. Positive in 4 of 5 years.",
             "flag": "green",  "src": "10-K FY25 · Item 7"},
            {"no": "02", "q": "Is operating margin above industry median?",
             "a": "TTM op. margin 30.2% vs sector median 22.4%.",
             "flag": "green",  "src": "10-K FY25 · MD&A"},
            {"no": "03", "q": "Is free cash flow positive in each of the last 3 years?",
             "a": "FY23 · FY24 · FY25 all positive FCF.",
             "flag": "green",  "src": "10-K cash-flow statement"},
            {"no": "04", "q": "Is debt-to-equity below 2×?",
             "a": "D/E 1.97×, at threshold.",
             "flag": "yellow", "src": "10-K balance sheet"},
            {"no": "05", "q": "Has senior management changed in last 12 months?",
             "a": "CFO transition disclosed 2025-11.",
             "flag": "yellow", "src": "8-K 2025-11-12"},
            {"no": "06", "q": "Are SEC filings current (10-K / 10-Q)?",
             "a": "Last 10-Q filed 2026-02-01. Current.",
             "flag": "green",  "src": "SEC EDGAR"},
            {"no": "07", "q": "Is insider activity disclosed in Form 4?",
             "a": "6 Form 4 filings in last 90 days. Net sales.",
             "flag": "yellow", "src": "SEC EDGAR · Form 4"},
            {"no": "08", "q": "Is dividend history consistent?",
             "a": "13 consecutive years of dividend payments.",
             "flag": "green",  "src": "IR dividend history"},
            {"no": "09", "q": "Is total liquidity (cash + ST) adequate?",
             "a": "Cash + ST investments cover 1.9× current liabilities.",
             "flag": "green",  "src": "10-K balance sheet"},
            {"no": "10", "q": "Are segment revenues disclosed by geography & product?",
             "a": "5 geographic · 5 product segments disclosed.",
             "flag": "green",  "src": "10-K segment footnote"},
        ],
        "quarterly_label":   "$94.9B · Q4 FY25",
        "quarterly_revenue": [78.4, 81.2, 85.5, 89.5, 82.9, 90.8, 94.9, 119.6],
        "margin_label":  "46.2% · 30.2% · 24.4%",
        "margin_gross": [38.2, 39.8, 41.1, 43.4, 46.2],
        "margin_op":    [24.1, 25.4, 26.8, 28.1, 30.2],
        "margin_net":   [20.1, 21.2, 22.4, 23.1, 24.4],
        "fcf_label":    "$99.8B · FY25",
        "fcf_history": [73.4, 80.2, 92.9, 96.4, 99.8],
        "peer_label":   "28.4 · 32.1 · 24.8 · 26.2",
        "peer_bars": [
            {"name": "AAPL", "v": 28.4},
            {"name": "MSFT", "v": 32.1},
            {"name": "GOOG", "v": 24.8},
            {"name": "META", "v": 26.2},
        ],
        "pull_quote": (
            "Due diligence is the act of asking questions patient enough to "
            "wait for answers."
        ),
        "pull_quote_attribution": "PivoxQuant Research Desk",
        "not_answered": [
            "Future revenue trajectory beyond filings.",
            "Qualitative management quality beyond disclosures.",
            "Competitive dynamics observed after the filing date.",
            "Regulatory or litigation outcomes not yet recorded.",
            "Individual investor tax or liquidity constraints.",
            "Appropriate position sizing for any portfolio.",
        ],
        "data_sources": [
            {"key": "Filings",         "value": "SEC EDGAR · 10-K, 10-Q, 8-K, Form 4"},
            {"key": "Fundamentals",    "value": "FMP v4 Stable · ratios, peer medians"},
            {"key": "Company IR",      "value": "Investor Relations pages · dividend history"},
            {"key": "Macro reference", "value": "FRED · sector & rates context"},
        ],
        "engine_note": "Checklist observation pipeline · public filings only",
    },

    "weekly_memo_email.html": {
        "week_number": 16,
        "user_name": USER_NAME,
        "period_end": "2026-04-19",
        "weekly_return_pct": 2.41,
        "benchmark_pct": 1.12, "alpha_pct": 1.29,
        "top_movers_up": MOVERS_UP,
        "top_movers_down": MOVERS_DOWN,
        "earnings_calendar": EARNINGS_CALENDAR,
        "download_url": "https://pivoxquant.com/artifacts/weekly-W16.pdf",
        "disclaimer": "참고용 자료입니다. 투자 권유가 아닙니다.",
    },

    "earnings_prebrief_email.html": {
        "ticker": "NVDA", "company_name": "NVIDIA Corporation",
        "fiscal_period": "Q1 FY26",
        "earnings_datetime": "2026-05-21 21:00",
        "consensus_eps": 5.92, "consensus_revenue": 42_300.0,
        "current_price": 1148.12,
        "expected_questions": [
            "Blackwell 생산 증설 이후 AI GPU 공급 타이트니스는 Q2~Q3 내에 어느 정도 완화되는가?",
            "CoWoS capacity 확보 현황과 TSMC 4nm/3nm 마진 영향은 어떻게 전망되는가?",
            "Data Center 비중이 85% 이상으로 상승한 상황에서, 게이밍/오토모티브의 regression 위험은?",
        ],
        "pdf_url": "https://pivoxquant.com/artifacts/prebrief-NVDA-Q1FY26.pdf",
        "disclaimer": "참고용 자료입니다. 투자 권유가 아닙니다.",
    },
}


# ─── Render loop ────────────────────────────────────────────────────────────

PDF_TEMPLATES = {
    "weekly_memo.html", "earnings_prebrief.html", "brag_card.html",
    "monthly_finance.html", "risk_board.html", "quarterly_self_report.html",
    "year_end_letter.html", "capital_allocation.html", "insider_mirror.html",
    "self_audit.html", "burn_rate.html", "credit_rating.html",
    "dividend_income.html", "portfolio_segment.html",
    "kpi_dashboard.html", "dd_checklist.html",
    "sp500_backtest.html",
}


def main() -> None:
    import sys as _sys
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    # Optional positional filter: e.g. `… sp500_backtest` restricts to one target.
    targets = _sys.argv[1:]
    if targets:
        selected: dict[str, dict] = {}
        for t in targets:
            key = t if t.endswith(".html") else f"{t}.html"
            if key in SAMPLES:
                selected[key] = SAMPLES[key]
            else:
                print(f"[warn] Unknown sample target: {t}")
        samples_to_run = selected or SAMPLES
    else:
        samples_to_run = SAMPLES

    # These 5 templates were redesigned but their inline SAMPLES blocks drifted
    # (missing v3.nav / cluster_buys / this_month), so they failed to render and
    # left STALE samples that showed old naked ticker codes. Render them through
    # the real service exactly the way the admin preview route does
    # (X_service.render_html(sample_data.sample_X())) so the HTML comes from the
    # production _to_v3_shape + enrich_v3_names pipeline and can never silently
    # drift from the templates again. SoT: routes/admin_preview.py::_render_standard
    # + [[티커번호 대신 종목이름 표시]].
    _render_via_service: dict = {}
    try:
        from services.artifacts import sample_data as _sd
        from services.artifacts.monthly_finance_service import MonthlyFinanceService as _MFS
        from services.artifacts.insider_mirror_service import InsiderMirrorService as _IMS
        from services.artifacts.dividend_income_service import DividendIncomeService as _DIS
        from services.artifacts.portfolio_segment_service import PortfolioSegmentService as _PSS
        from services.artifacts.burn_rate_service import BurnRateService as _BRS
        _render_via_service = {
            "monthly_finance.html":   (_MFS, _sd.sample_monthly_finance),
            "insider_mirror.html":    (_IMS, _sd.sample_insider_mirror),
            "dividend_income.html":   (_DIS, _sd.sample_dividend_income),
            "portfolio_segment.html": (_PSS, _sd.sample_portfolio_segment),
            "burn_rate.html":         (_BRS, _sd.sample_burn_rate),
        }
    except Exception as _e:  # noqa: BLE001 — keep harness running on any drift
        print(f"[warn] service-render wiring skipped: {_e}")

    rendered = []
    failed = []
    pdf_rendered = []
    pdf_failed = []
    HTML = _try_import_weasyprint()
    chrome_bin = None if HTML is not None else _find_chrome()
    engine = "weasyprint" if HTML else ("chrome-headless" if chrome_bin else None)
    if engine:
        print(f"[info] PDF engine: {engine}")
    else:
        print("[warn] Neither WeasyPrint nor Chrome available; PDFs will be skipped.")

    # Backfill company names from tickers so these previews match the real
    # service output. The production path runs enrich_v3_names() before render;
    # this QA harness historically skipped it, so KR tickers surfaced as naked
    # numeric codes (035760 / 005930) in the CEO-reviewed samples even though
    # generated artifacts resolve them. See [[티커번호 대신 종목이름 표시]].
    try:
        from services.artifacts._name_enrich import enrich_v3_names
    except Exception:  # noqa: BLE001 — harness must run even if services absent
        enrich_v3_names = None

    for tpl_name, ctx in samples_to_run.items():
        if enrich_v3_names is not None:
            try:
                enrich_v3_names(ctx)
            except Exception:  # noqa: BLE001 — never let enrich break a render
                pass
        try:
            if tpl_name in _render_via_service:
                # Canonical production path (mirrors admin_preview): the service
                # runs _to_v3_shape + enrich_v3_names + template render itself.
                _Svc, _sample_fn = _render_via_service[tpl_name]
                html = _Svc().render_html(_sample_fn())
            else:
                tpl = env.get_template(tpl_name)
                html = tpl.render(**ctx)
        except Exception as e:  # noqa: BLE001
            failed.append((tpl_name, str(e)))
            continue

        out = OUT_DIR / tpl_name
        out.write_text(html, encoding="utf-8")
        rendered.append(tpl_name)

        # Emit PDF for the 17 canonical artifact templates.
        if tpl_name not in PDF_TEMPLATES:
            continue
        pdf_path = PDF_DIR / tpl_name.replace(".html", ".pdf")
        try:
            if HTML is not None:
                HTML(string=html, base_url=str(TEMPLATE_DIR)).write_pdf(str(pdf_path))
            elif chrome_bin is not None:
                _render_pdf_chrome(chrome_bin, out, pdf_path)
            else:
                continue
            pdf_rendered.append((tpl_name, pdf_path))
        except Exception as exc:  # noqa: BLE001
            pdf_failed.append((tpl_name, f"{type(exc).__name__}: {exc}"))

    # Write an index page linking to every sample.
    idx = [
        "<!doctype html><html lang='ko'><head><meta charset='utf-8'>",
        "<title>PivoxQuant — Artifact Sample Gallery</title>",
        "<link href='https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,wght@0,400;0,500;0,600;1,400&family=Geist:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap' rel='stylesheet'>",
        "<style>",
        "body { background: #fafaf7; color: #0a0a0a; font-family: Geist, -apple-system, sans-serif;",
        "  margin: 0; padding: 60px 40px; max-width: 920px; margin-left: auto; margin-right: auto; }",
        "h1 { font-family: 'Source Serif 4', serif; font-size: 36pt; font-weight: 500; letter-spacing: -0.015em; margin: 0 0 8pt 0; }",
        "p.sub { font-family: 'Source Serif 4', serif; font-style: italic; color: #4a4a4a; font-size: 14pt; margin: 0 0 32pt 0; }",
        ".eyebrow { font-size: 9pt; letter-spacing: 0.32em; text-transform: uppercase; color: #8b6f47; font-weight: 600; margin-bottom: 6pt; }",
        ".rule { border: none; border-top: 0.75pt solid #0a0a0a; width: 60pt; margin: 28pt 0; }",
        "h2 { font-family: 'Geist', sans-serif; font-size: 10pt; letter-spacing: 0.14em; text-transform: uppercase; color: #0a0a0a;",
        "  border-bottom: 0.5pt solid #0a0a0a; padding-bottom: 6pt; margin: 28pt 0 14pt; font-weight: 600; }",
        "ul { list-style: none; padding: 0; margin: 0; }",
        "li { padding: 10pt 0; border-bottom: 0.25pt solid #e8e5dc; display: flex; align-items: baseline; gap: 12pt; }",
        "li .num { font-family: 'JetBrains Mono', monospace; font-size: 9pt; color: #8a8a8a; min-width: 28pt; }",
        "li a { color: #0a0a0a; text-decoration: none; font-weight: 500; font-size: 12pt; }",
        "li a:hover { color: #8b6f47; }",
        "li .tag { font-family: 'JetBrains Mono', monospace; font-size: 8pt; color: #8a8a8a; margin-left: auto; letter-spacing: 0.04em; }",
        "footer { margin-top: 48pt; padding-top: 14pt; border-top: 0.5pt solid #e8e5dc; font-size: 9pt; color: #8a8a8a; font-style: italic; }",
        "</style></head><body>",
        "<div class='eyebrow'>PivoxQuant · Research Desk</div>",
        "<h1>Artifact Sample Gallery</h1>",
        "<p class='sub'>Goldman Sachs CFO-grade redesign &mdash; review set for CEO approval.</p>",
        "<div class='rule'></div>",
        "<h2>PDF Templates</h2>",
        "<ul>",
    ]

    pdf_order = [
        "weekly_memo.html", "earnings_prebrief.html", "brag_card.html",
        "monthly_finance.html", "risk_board.html", "quarterly_self_report.html",
        "year_end_letter.html", "capital_allocation.html", "insider_mirror.html",
        "self_audit.html", "burn_rate.html", "credit_rating.html",
        "dividend_income.html", "portfolio_segment.html",
    ]
    email_order = [
        "weekly_memo_email.html", "earnings_prebrief_email.html",
        "brag_card_email.html",
        "kpi_dashboard.html", "dd_checklist.html",
    ]

    for i, name in enumerate(pdf_order, start=1):
        if name in rendered:
            idx.append(f"<li><span class='num'>{i:02d}</span><a href='{name}'>{name.replace('.html','').replace('_',' ').title()}</a><span class='tag'>{name}</span></li>")

    idx.append("</ul><h2>Email Templates</h2><ul>")
    for i, name in enumerate(email_order, start=1):
        if name in rendered:
            idx.append(f"<li><span class='num'>{i:02d}</span><a href='{name}'>{name.replace('.html','').replace('_',' ').title()}</a><span class='tag'>{name}</span></li>")

    idx.append("</ul>")

    if failed:
        idx.append("<h2>Render Errors</h2><ul>")
        for n, err in failed:
            idx.append(f"<li><strong>{n}</strong><br><small>{err}</small></li>")
        idx.append("</ul>")

    idx.append(
        f"<footer>Generated {_dt.datetime.now().strftime('%Y-%m-%d %H:%M')} &middot; "
        f"Open any file in Chrome and use <code>Cmd+P</code> &rarr; Save as PDF to "
        f"preview final render. Production PDFs use WeasyPrint for pixel-identical output.</footer>"
    )
    idx.append("</body></html>")

    (OUT_DIR / "index.html").write_text("\n".join(idx), encoding="utf-8")

    print(f"Rendered {len(rendered)} HTML templates → {OUT_DIR}")
    if failed:
        print(f"\nHTML failures ({len(failed)}):")
        for n, err in failed:
            print(f"  - {n}: {err}")

    print(f"\nRendered {len(pdf_rendered)} / {len(PDF_TEMPLATES)} PDFs → {PDF_DIR}")
    for n, p in pdf_rendered:
        kb = p.stat().st_size / 1024
        print(f"  [OK]   {n:32s} → {p.name:34s} {kb:7.1f} KB")
    if pdf_failed:
        print(f"\nPDF failures ({len(pdf_failed)}):")
        for n, err in pdf_failed:
            print(f"  [FAIL] {n}: {err}")


if __name__ == "__main__":
    main()
