"""Sample data for admin Artifact preview — CEO-only.

All dicts here are *fictional* portfolios for CEO (배상현) internal QA of
the PDF/email templates. Never uses real user data. The shapes match each
artifact service's `to_dict()` / `render_html(data)` contract 1:1 so we
can feed `render_html` / `render_pdf` / `render_email_html` directly
without touching the database.

Rules
-----
- No real tickers backed by user positions — pure fiction
- No DB writes, no external API calls
- Safe to regenerate on every request
- Korean + US blend (AAPL, NVDA, 삼성전자, SK하이닉스 …) — CEO's actual
  mental model of a mixed KR/US portfolio
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable


DISCLAIMER = "정보 제공 목적이며 투자 권유가 아닙니다. 투자 판단은 본인 책임입니다."

SAMPLE_USER_NAME = "배상현"
SAMPLE_USER_ID = 0  # fictional — never matches a real user.id

# ── shared helpers ───────────────────────────────────────────────────────────


def _today() -> date:
    return date.today()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z"


def _sample_positions() -> list[dict[str, Any]]:
    """Fictional mixed KR/US portfolio."""
    return [
        {"ticker": "AAPL",       "name": "Apple Inc.",        "shares": 12,  "avg_cost": 172.40},
        {"ticker": "NVDA",       "name": "NVIDIA Corp.",      "shares": 5,   "avg_cost": 610.00},
        {"ticker": "MSFT",       "name": "Microsoft Corp.",   "shares": 8,   "avg_cost": 335.20},
        {"ticker": "GOOGL",      "name": "Alphabet Inc.",     "shares": 10,  "avg_cost": 148.50},
        {"ticker": "005930.KS",  "name": "삼성전자",           "shares": 50,  "avg_cost": 72000},
        {"ticker": "000660.KS",  "name": "SK하이닉스",          "shares": 15,  "avg_cost": 145000},
        {"ticker": "035420.KS",  "name": "NAVER",              "shares": 8,   "avg_cost": 210000},
    ]


# ── per-artifact sample builders ─────────────────────────────────────────────


def sample_weekly_memo() -> dict[str, Any]:
    today = _today()
    return {
        "user_id":            SAMPLE_USER_ID,
        "user_name":          SAMPLE_USER_NAME,
        "week_number":        today.isocalendar()[1],
        "period_start":       (today - timedelta(days=7)).isoformat(),
        "period_end":         today.isoformat(),
        "generated_at":       _now_iso(),
        "weekly_return_pct":  2.14,
        "benchmark_pct":      1.37,
        "alpha_pct":          0.77,
        "sector_alloc": {
            "Information Technology": 42.3,
            "Semiconductors":         27.8,
            "Communication Services": 14.1,
            "Consumer Discretionary":  9.5,
            "Financials":              6.3,
        },
        "sector_changes": [
            {"sector": "Semiconductors",         "current": 27.8, "previous": 24.2, "delta_pp":  3.6},
            {"sector": "Consumer Discretionary", "current":  9.5, "previous": 11.9, "delta_pp": -2.4},
            {"sector": "Information Technology", "current": 42.3, "previous": 41.6, "delta_pp":  0.7},
        ],
        "top_movers_up": [
            {"ticker": "NVDA",      "weekly_return_pct":  6.82},
            {"ticker": "000660.KS", "weekly_return_pct":  4.11},
            {"ticker": "AAPL",      "weekly_return_pct":  1.94},
        ],
        "top_movers_down": [
            {"ticker": "GOOGL",     "weekly_return_pct": -1.72},
            {"ticker": "035420.KS", "weekly_return_pct": -2.85},
        ],
        "earnings_calendar": [
            {"ticker": "AAPL",      "date": (today + timedelta(days=3)).isoformat(), "time": "amc"},
            {"ticker": "005930.KS", "date": (today + timedelta(days=5)).isoformat(), "time": "bmo"},
        ],
        "macro_checklist": [
            {"series_id": "FEDFUNDS", "label": "Fed Funds Rate", "value": 5.33, "units": "%",   "date": today.isoformat(), "pct_change": 0.0},
            {"series_id": "DGS10",    "label": "10Y Treasury",    "value": 4.22, "units": "%",   "date": today.isoformat(), "pct_change": -1.2},
            {"series_id": "VIXCLS",   "label": "VIX",             "value": 14.8, "units": "idx", "date": today.isoformat(), "pct_change":  3.1},
            {"series_id": "DEXKOUS",  "label": "KRW/USD",         "value": 1356.2, "units": "KRW", "date": today.isoformat(), "pct_change": -0.4},
        ],
        "risk_notes": [
            "Information Technology 섹터 비중 42%로 집중도 높음 관찰",
            "GOOGL, 035420.KS 주간 하락, 최저 -2.85% 기록",
        ],
        # Flagship narrative fields (optional, empty-safe).
        "narrative_exec_line": (
            "A week where the Korean semis quietly carried the book, and the "
            "S&P drift politely cooperated — a pattern the desk has observed "
            "three weeks running."
        ),
        "narrative_week_summary": [
            (
                "The book advanced 2.14% against the S&P 500's 1.37%, "
                "settling alpha at +0.77 percentage points. Read "
                "descriptively, this is the third consecutive week the spread "
                "has landed in the positive half of its ninety-day "
                "distribution."
            ),
            (
                "Semiconductor exposure did the heavy lifting. NVDA and "
                "SK하이닉스 together contributed the majority of the weekly "
                "delta, consistent with their combined weight in the book. "
                "GOOGL and NAVER moved in sympathy with platform-cohort "
                "softness."
            ),
            (
                "The observation worth naming is concentration: Information "
                "Technology carries 42% of invested capital — above the "
                "forty-percent guideline the desk tracks."
            ),
        ],
        "narrative_what_next": (
            "Two scheduled earnings prints sit inside the held book this week "
            "— AAPL on day three and 005930.KS on day five. Macro prints on "
            "the calendar are the FOMC statement mid-week and the Korean KRW "
            "/ USD fix. The desk tracks these against the same tail bands, "
            "not against a projection."
        ),
        "equity_series": [
            {"x": "Mon", "y":  0.00},
            {"x": "Tue", "y":  0.41},
            {"x": "Wed", "y":  0.92},
            {"x": "Thu", "y":  1.52},
            {"x": "Fri", "y":  1.88},
            {"x": "Mon", "y":  2.04},
            {"x": "Tue", "y":  2.14},
        ],
        "benchmark_series": [
            {"x": "Mon", "y":  0.00},
            {"x": "Tue", "y":  0.22},
            {"x": "Wed", "y":  0.58},
            {"x": "Thu", "y":  0.91},
            {"x": "Fri", "y":  1.12},
            {"x": "Mon", "y":  1.24},
            {"x": "Tue", "y":  1.37},
        ],
        "equity_x_labels": ["Mon", "Tue", "Wed", "Thu", "Fri", "Mon", "Tue"],
        "daily_walk_rows": [
            {"label": "Mon", "value":  0.28, "tone": "pos"},
            {"label": "Tue", "value":  0.41, "tone": "pos"},
            {"label": "Wed", "value":  0.60, "tone": "pos"},
            {"label": "Thu", "value": -0.24, "tone": "neg"},
            {"label": "Fri", "value":  0.36, "tone": "pos"},
            {"label": "Mon", "value":  0.16, "tone": "pos"},
            {"label": "Tue", "value":  0.57, "tone": "pos"},
        ],
        "risk_metrics": [
            {"label": "VaR 95%",                    "value": "-2.14%",
             "gloss": "The loss the book was historically exceeded by on only 5% of daily sessions, based on the last 90 trading days of close-to-close returns."},
            {"label": "Expected Shortfall (ES 95%)", "value": "-3.12%",
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
        "corr_labels": ["NVDA", "000660", "AAPL", "GOOGL", "035420"],
        # Flagship v2 editorial fields (optional, additive — empty-safe)
        "issue_number": 12,
        "hero_headline": [
            "A week",
            "where the index",
            "restrained itself.",
        ],
        "equity_annotation": {
            "day_label": "Thu 14:30 KST",
            "delta_text": "+0.82%",
            "anchor_index": 3,
        },
        "pull_quote": (
            "A quiet week is not a boring one. It is a disciplined one."
        ),
        "pull_quote_attribution": "The Editorial Voice",
        "what_to_watch": [
            {"category": "Earnings", "detail": "AAPL · Tue after the close."},
            {"category": "Earnings", "detail": "005930.KS · Thu before the open."},
            {"category": "Macro",    "detail": "FOMC minutes · Wed 21:00 KST."},
            {"category": "Macro",    "detail": "US CPI · Fri 22:30 KST."},
            {"category": "Observation","detail": "0.62 correlation between the top-2 semis remains the week's structural read."},
        ],
        "data_sources": ["KIS", "Alpaca", "FMP v4", "SEC EDGAR", "FRED"],
        "typeset_in":   "Source Serif 4 · Geist · JetBrains Mono · Noto Sans KR",
        "engine_note":  "58 quant models · 7-Layer Risk Defense",
        "doc_ref":      None,  # computed in template if missing
        "disclaimer": DISCLAIMER,
    }


def sample_earnings_prebrief() -> dict[str, Any]:
    """Earnings Pre-Brief — Goldman IC v2 editorial — 6-page pre-read.

    Returns every field the redesigned `earnings_prebrief.html` template reads.
    Tone: 24-hour pre-read before the earnings call. Observation only, no
    predictions, no advice. Historical record + calendar.
    """
    return {
        # ── meta ────────────────────────────────────────────────────────
        "user_id":       SAMPLE_USER_ID,
        "user_name":     SAMPLE_USER_NAME,
        "ticker":        "AAPL",
        "company_name":  "Apple Inc.",
        "fiscal_period": "Q2 FY26",
        "reporting_date":  "2026-04-30",
        "reporting_time":  "After the close (AMC)",
        "issue_number":  1,
        "doc_ref":       "PQ-EB-01 · v2026.04.21",
        "generated_at":  _now_iso(),
        "typeset_in":    "Source Serif 4 · Geist · JetBrains Mono",
        "engine_note":   "58 quant models · 7-Layer Risk Defense",
        "LICENSE_NUMBER": None,

        # ── P1 cover KPIs ───────────────────────────────────────────────
        "consensus_eps":     1.62,
        "consensus_eps_low": 1.48,
        "consensus_eps_high": 1.76,
        "implied_move_pct":  4.2,
        "consensus_as_of":   "2026-04-19",
        "option_as_of":      "2026-04-20",
        "hero_headline": [
            "A quiet hour before the call.",
            "Facts observed. Calendar noted.",
            "The company will speak \u2014 we listen.",
        ],

        # ── P2 company snapshot — 8-quarter revenue history ─────────────
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
            "The company's revenue pace has held between roughly $93B and $125B across the observed eight-quarter window, with the familiar fourth-quarter seasonal peak appearing in both FY24 Q4 and FY25 Q4. YoY change has moved from mid-single-digit negative at the start of the window to low-single-digit positive by its end. These are observed print readings \u2014 not a shape claim about the quarter to come.",
            "Across the four most recent reports, the surprise magnitude \u2014 reported EPS against the consensus observed on the day of each report \u2014 has averaged near the low-single-digit positive range, with one quarter sitting close to flat and none of the four landing below the consensus by more than a narrow margin. Three of four reports printed a positive surprise; one printed within a tenth of a cent of consensus. Record, not a pattern claim.",
            "The analyst estimate range for the quarter now approaching is a factual band. The low end of the sampled observations sits at $1.48; the high end at $1.76; the median at $1.62. The band is a reading of analyst observations \u2014 informational only, and not a target of any kind.",
        ],

        # ── P3 historical surprise ladder (8 quarters) ──────────────────
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
            {"range": "\u22124 to \u22122", "count": 0},
            {"range": "\u22122 to  0",       "count": 0},
            {"range": " 0 to  2",             "count": 3},
            {"range": " 2 to  4",             "count": 3},
            {"range": " 4 to  6",             "count": 1},
            {"range": " 6 to  8",             "count": 1},
        ],

        # ── P4 observation quad ─────────────────────────────────────────
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
            {"term": "Consensus is a sampling",      "def": "Consensus is a sampling of analyst observations \u2014 historical record only, not a collective target."},
            {"term": "Implied move",                 "def": "Option-market pricing of uncertainty around the print. It is market-implied, not market-determined."},
            {"term": "Past surprise pattern",        "def": "The surprise history is a historical record only. It does not speak to the current quarter."},
            {"term": "Post-earnings drift",          "def": "The drift bars record observed reactions. Causation is not claimed."},
            {"term": "Brief is informational only",  "def": "Nothing on these pages constitutes investment guidance. The document is for pre-read reference only."},
        ],

        # ── P5 editorial ────────────────────────────────────────────────
        "pull_quote":      "The market rehearses every call. The call tells us only how well the market listened.",
        "pull_quote_attr": "PivoxQuant \u00b7 Earnings Desk",
        "cannot_tell": [
            "Which way the print will land.",
            "What to do before or after the call.",
            "Management's unspoken intent on the call.",
            "Private order flow around the event.",
            "Tax or personal timing of any action.",
        ],

        # ── P6 colophon ─────────────────────────────────────────────────
        "data_sources": [
            {"key": "Consensus EPS",       "note": "FMP v4 Stable."},
            {"key": "Option chain",        "note": "CBOE via Alpaca."},
            {"key": "Historical EPS",      "note": "SEC EDGAR."},
            {"key": "Reporting calendar",  "note": "Company Investor Relations."},
        ],

        "disclaimer": DISCLAIMER,
    }


def sample_monthly_finance() -> dict[str, Any]:
    """Monthly Finance — Goldman IC v2 editorial — 6-page personal ledger.

    Returns every field the redesigned `monthly_finance.html` template reads.
    Tone: a private-bank monthly statement. Observation only; no directives,
    no targets, no forecasts.
    """
    today = _today()
    return {
        "user_id":      SAMPLE_USER_ID,
        "user_name":    SAMPLE_USER_NAME,
        "month_label":  "April 2026",
        "generated_at": _now_iso(),
        "issue_number": 4,
        "doc_ref":      "PQ-MF-04 · v2026.04.21",
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
        "disclaimer": DISCLAIMER,
        # unused by template but kept for any legacy callers:
        "period_start": today.replace(day=1).isoformat(),
        "period_end":   today.isoformat(),
    }


def sample_risk_board() -> dict[str, Any]:
    """Goldman Risk Committee v2 editorial — 6-page Risk Board deck.

    Returns every field the redesigned `risk_board.html` template reads.
    All numbers are descriptive observations; no recommendations or targets.
    """
    _today()
    return {
        # ── meta ─────────────────────────────────────────────────────────
        "user_id":       SAMPLE_USER_ID,
        "user_name":     SAMPLE_USER_NAME,
        "period_label":  "April 2026",
        "generated_at":  _now_iso(),
        "issue_number":  4,
        "doc_ref":       "PQ-RB-04 · v2026.04.21",
        "trigger":       "monthly",

        # ── P1 · cover KPIs ──────────────────────────────────────────────
        "kpi_var_1d":     -2.14,
        "kpi_es_1d":      -3.42,
        "kpi_maxdd_90d":  -8.70,
        "kpi_corr_index":  0.58,
        "hero_headline": [
            "Risk is observed, not eliminated.",
            "Numbers are companions, not captains.",
            "This is a record — not a route.",
        ],

        # ── P2 · 10×10 correlation heatmap ───────────────────────────────
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

        # ── P3 · risk ladder (10 positions) ──────────────────────────────
        # Each position's 1D VaR is a single-asset historical observation;
        # the portfolio-level number on the cover reflects diversification.
        "positions_ladder": [
            # ticker,    weight, var_1d, es_1d, maxdd_90d, beta, vol_ann, spark
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

        # ── P4 · tail / drawdown quad ────────────────────────────────────
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
        "tail_ratio":        1.08,
        "liquidity_label":   "1.2x avg",
        "liquidity_heat": [
            [0.08, 0.09, 0.11, 0.09, 0.10],  # AAPL
            [0.12, 0.14, 0.13, 0.15, 0.12],  # MSFT
            [0.22, 0.28, 0.31, 0.26, 0.24],  # NVDA
            [0.06, 0.07, 0.06, 0.08, 0.07],  # GOOG
            [0.18, 0.21, 0.19, 0.20, 0.22],  # META
            [0.09, 0.10, 0.12, 0.09, 0.11],  # AMZN
            [0.34, 0.38, 0.32, 0.36, 0.40],  # TSLA
            [0.14, 0.16, 0.15, 0.13, 0.14],  # JPM
            [0.05, 0.06, 0.05, 0.07, 0.05],  # XOM
            [0.11, 0.13, 0.12, 0.10, 0.14],  # UNH
        ],

        # ── P5 · editorial ───────────────────────────────────────────────
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

        # ── P6 · colophon ────────────────────────────────────────────────
        "data_sources": [
            {"key": "Price",             "value": "Alpaca Market Data (IEX consolidated)"},
            {"key": "Corporate actions", "value": "FMP v4 Stable"},
            {"key": "Risk-free",         "value": "3-Month T-Bill (FRED DGS3MO)"},
            {"key": "Window",            "value": "252 trading days, rolling"},
        ],
        "typeset_in":  "Source Serif 4 · Geist · JetBrains Mono",
        "engine_note": "58 quant models · 7-Layer Risk Defense",
        "disclaimer":  DISCLAIMER,
        "LICENSE_NUMBER": None,
    }


def sample_quarterly_self_report() -> dict[str, Any]:
    """Quarterly Self-Report — Goldman IC v2 editorial — 6-page PM self-review.

    Returns every field the redesigned `quarterly_self_report.html` template reads.
    Tone: Buffett's quarterly partner letter — self-observation only, no advice.
    """
    today = _today()
    quarter_label = f"{today.year} Q{(today.month - 1) // 3 + 1}"
    return {
        # ── meta ────────────────────────────────────────────────────────
        "user_id":       SAMPLE_USER_ID,
        "user_name":     SAMPLE_USER_NAME,
        "quarter_label": quarter_label,
        "issue_number":  1,
        "doc_ref":       "PQ-QSR-01 · v2026.04.21",
        "period_start":  (today - timedelta(days=90)).isoformat(),
        "period_end":    today.isoformat(),
        "generated_at":  _now_iso(),
        "typeset_in":    "Source Serif 4 · Geist · JetBrains Mono",
        "engine_note":   "58 quant models · 7-Layer Risk Defense",
        "LICENSE_NUMBER": None,

        # ── P1 cover KPIs (4-up) ────────────────────────────────────────
        "quarterly_return_pct": 6.40,
        "kpi_benchmark":        4.20,
        "kpi_alpha":            2.20,
        "kpi_hit_rate":        58,
        "hero_headline": [
            "Three months observed.",
            "One hand, ten decisions.",
            "A self-review \u2014 not a verdict.",
        ],

        # ── P2 self-review letter (6 paragraphs) ────────────────────────
        "signoff_line": "In observation,",
        "review_paragraphs": [
            "Three months, in the hand. The quarter opened with the market reading its own quiet \u2014 a stretched week of thin prints, a calmer second week, and then the sort of mid-quarter acceleration that looks, in the book, like momentum and, on the tape, like catching up. I watched. I did little. The doing, when it came, came later.",
            "Position changes were fewer than the quarter before. Semiconductor weight held at a little over a quarter of the book through the period. Consumer discretionary was trimmed in February \u2014 a small reduction, not a closure \u2014 on a reading that exit pace was outrunning the thesis I had written down. The adjustment was clean; the reasoning was dated; the execution took ninety seconds. That is not a strategy. It is a habit.",
            "The largest single-day drawdown of the quarter printed on the Thursday in mid-March. It was 2.1% on the book. I remember the morning because I had slept poorly the night before and opened the screen later than usual. The book recovered by the following Tuesday. The note I wrote to myself on the Thursday afternoon \u2014 two sentences in the running file \u2014 is the record that no Sharpe ratio preserves. I keep the note.",
            "What I misread, I misread at the edges. I read one small position as a story of operating leverage and the thesis I had written, three lines long, required a footnote on customer concentration that I had read in October and then, quietly, stopped reading. The position is still in the book, at a smaller weight. I have not closed it. I have reread the footnote. These are the decisions that do not appear in a P&L column. The P&L is where the decision lives. The decision is not where the P&L lives.",
            "The habits held, with one exception. Monthly rebalance on the last trading day \u2014 kept. Reading on Saturday mornings \u2014 kept, except for the one Sunday evening in February I chose instead to finish a book, and the Tuesday that followed it was my least clean trading day of the quarter. The reading is not superstition. The reading is the shelter. I note the exception. I do not punish the Sunday.",
            "Quarters end. Observation continues. There is nothing to claim here, and no conclusion I would put in italics if I were writing for anyone else. I am writing for the person who has to make the next ten decisions. That person will be, again, me.",
        ],
        "margin_notes": [
            {"eyebrow": "Sharpe \u00b7 quarter", "note": "Observed at 1.08 over the window. Not annualised into the future."},
            {"eyebrow": "Beta \u00b7 90D",        "note": "Book-to-SPY beta 0.92 over trailing 90 sessions. Quietly below one."},
            {"eyebrow": "Turnover",               "note": "28% in the quarter. Monthly rebalance on the last trading day, held without exception."},
        ],

        # ── P3 decision ladder (10 rows) ────────────────────────────────
        "decision_ladder": [
            {"date": "2026-01-08", "action": "Open",    "ticker": "NVDA", "weight_delta":  4.2, "rationale": "Sizing per plan",                  "pnl_pct":  12.4, "spark": [0, 0.6, 1.8, 3.2, 4.8, 7.6, 12.4]},
            {"date": "2026-01-14", "action": "Trim",    "ticker": "TSLA", "weight_delta": -1.8, "rationale": "Position size reduction",          "pnl_pct":  -2.1, "spark": [0, 0.3, -0.4, -1.2, -1.8, -2.0, -2.1]},
            {"date": "2026-01-22", "action": "Add",     "ticker": "AAPL", "weight_delta":  2.0, "rationale": "Rebalance per plan",               "pnl_pct":   5.8, "spark": [0, 0.4, 1.2, 2.4, 3.8, 5.0, 5.8]},
            {"date": "2026-02-04", "action": "Open",    "ticker": "AVGO", "weight_delta":  3.0, "rationale": "New thesis entry",                 "pnl_pct":   9.1, "spark": [0, 0.8, 2.2, 4.1, 6.2, 8.0, 9.1]},
            {"date": "2026-02-11", "action": "Trim",    "ticker": "XLY",  "weight_delta": -2.4, "rationale": "Sector weight reduction",          "pnl_pct":   1.2, "spark": [0, 0.2, 0.5, 0.8, 1.0, 1.1, 1.2]},
            {"date": "2026-02-19", "action": "Cash",    "ticker": "CASH", "weight_delta":  2.4, "rationale": "Cash buffer increase",             "pnl_pct":   0.4, "spark": [0, 0.1, 0.1, 0.2, 0.3, 0.3, 0.4]},
            {"date": "2026-02-27", "action": "Add",     "ticker": "MSFT", "weight_delta":  1.5, "rationale": "Rebalance per plan",               "pnl_pct":   3.2, "spark": [0, 0.3, 0.8, 1.6, 2.4, 2.9, 3.2]},
            {"date": "2026-03-06", "action": "Close",   "ticker": "NKE",  "weight_delta": -2.2, "rationale": "Thesis marked stale",              "pnl_pct":  -5.8, "spark": [0, -0.4, -1.2, -2.4, -3.8, -4.9, -5.8]},
            {"date": "2026-03-14", "action": "Observe", "ticker": "BOOK", "weight_delta":  0.0, "rationale": "Drawdown day (\u22122.1% print)",  "pnl_pct":  -2.1, "spark": [0, -0.2, -0.8, -1.6, -2.0, -2.1, -2.1]},
            {"date": "2026-03-27", "action": "Rebal",   "ticker": "BOOK", "weight_delta":  0.0, "rationale": "Monthly rebalance (per plan)",     "pnl_pct":   0.6, "spark": [0, 0.1, 0.2, 0.3, 0.5, 0.6, 0.6]},
        ],

        # ── P4 diagnostic quad ──────────────────────────────────────────
        "sharpe_rolling":  1.08,
        "sharpe_series":   [0.42, 0.58, 0.68, 0.74, 0.82, 0.91, 0.95, 1.02, 1.08, 1.12, 1.08, 1.04],
        "hit_rate_overall": 58,
        "hit_rate_by_action": [
            {"action": "Open",  "rate": 62, "count": 4},
            {"action": "Add",   "rate": 67, "count": 3},
            {"action": "Trim",  "rate": 50, "count": 2},
            {"action": "Close", "rate": 50, "count": 2},
        ],
        "holding_median_days": 14,
        "holding_hist": [2, 4, 6, 7, 5, 3, 2, 1, 0, 1],
        "top_sector": "Semiconductors",
        "sector_attribution": [
            {"sector": "Semis",    "pnl":  3.8},
            {"sector": "Platform", "pnl":  1.6},
            {"sector": "Consumer", "pnl": -0.4},
            {"sector": "Fin",      "pnl":  0.8},
            {"sector": "Cash",     "pnl":  0.6},
        ],
        "self_review_notes": [
            {"term": "Sharpe \u00b7 rolling",   "def": "Excess-of-cash return per unit of realised volatility, computed on a rolling 90-session window. A historical record only."},
            {"term": "Hit Rate",                "def": "Closed decisions with a positive print, divided by closed decisions. Counts events, not conviction."},
            {"term": "Holding period",          "def": "Calendar days from entry to last change or close. The mode sits at the monthly rebalance rhythm, by design."},
            {"term": "Sector attribution",      "def": "Share of quarter P&L observed in each sector cohort. Not a causal claim about sector rotation."},
            {"term": "Not predictive",          "def": "None of the four readings is predictive. They are artefacts of the quarter already lived, kept for review."},
        ],

        # ── P5 editorial ────────────────────────────────────────────────
        "pull_quote": "Self-review is the small hinge on which large habits turn.",
        "pull_quote_attr": "PivoxQuant \u00b7 Quarterly Desk",
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
            "Three margin notes \u2014 Sharpe, beta, turnover.",
            "One largest single-day drawdown, with its date.",
            "One written sign-off, to the person who made the quarter.",
        ],

        # ── P6 colophon ─────────────────────────────────────────────────
        "data_sources": [
            {"key": "Price observations", "note": "Alpaca Market Data (IEX consolidated)."},
            {"key": "Corporate actions",  "note": "FMP v4 Stable."},
            {"key": "Risk-free",          "note": "3-Month T-Bill via FRED (DGS3MO)."},
            {"key": "Benchmark",          "note": "S&P 500 total return, with dividends."},
        ],

        "disclaimer": DISCLAIMER,
    }


def sample_year_end_letter() -> dict[str, Any]:
    today = _today()
    year = today.year - 1
    return {
        "user_id":      SAMPLE_USER_ID,
        "user_name":    SAMPLE_USER_NAME,
        "year":         year,
        "issue_number": 1,
        "doc_ref":      "PQ-YEL-01 · v2026.04.21",
        "period_start": date(year, 1, 1).isoformat(),
        "period_end":   date(year, 12, 31).isoformat(),
        "generated_at": _now_iso(),
        # ── P1 cover KPIs (Buffett letter — 4 plain metrics)
        "kpi_pnl":       16.8,
        "kpi_benchmark": 11.2,
        "kpi_alpha":      5.6,
        "kpi_mdd":      -12.4,
        "hero_headline": [
            "A letter written at year's end.",
            "Twelve months, six hundred prints, one quiet hand.",
            "A record, not a verdict.",
        ],
        # ── P2 letter body (7 paragraphs, first-person reflective)
        "letter_paragraphs": [
            "This letter is not a forecast. It is a record of what happened, and — where I can manage it — a record of what I noticed while it happened. The numbers on the cover are what they are. The question worth a letter is what the numbers were made of.",
            "The market in question moved, on the whole, as markets do — in a stretched summer, a frightened autumn, and a quiet close. The benchmark drifted upward through a corridor of minor shocks, none of which proved durable enough to name. I have nothing useful to say about the shocks. I have a little to say about what the book did in their company.",
            "The book carried a weight in the semiconductor cohort through the first three quarters, and in the platform cohort through the fourth. The communications-and-consumer pair lagged the others by a wide margin in the second quarter, and the small adjustment made in July — a reduction of exposure, not a closure — was the cleanest single decision of the year. Two positions that had been noisy for months simply calmed. I take no credit for this. I kept the names. The names did the work.",
            "The largest single-day drawdown arrived on March 14, a Friday, and it was 3.2%. I remember it because I was writing another letter — an unrelated one, to someone unrelated — when it printed, and the text I had been composing on a different subject became harder to finish. This is the human record that no Sharpe ratio preserves. The book was back at prior high by the following Wednesday. The other letter, I finished the next week, poorly.",
            "What I misread, I misread with some confidence. I read one mid-cap as a story of operating leverage and missed that the story required a customer-concentration footnote I had read and promptly forgotten. The position was closed in June at a small loss. I keep the position sheet in a folder, dated, as a note to myself. Not to punish. To remember the texture of being wrong.",
            "The habits held. Monthly rebalance on the last trading day. Reading on weekends, not weekdays. Sleep before midnight, market-side screens dark by 10pm KST. A single quiet Sunday in September I skipped the reading and paid for it on Tuesday with a decision I would not have made rested. These are not strategies. They are shelters.",
            "Markets are weather. Portfolios are shelters. Neither makes promises. Records are all we keep.",
        ],
        "margin_notes": [
            {"eyebrow": "Sharpe",           "note": "Observed at 0.91 over the window. Not annualised into the future."},
            {"eyebrow": "Turnover",         "note": "41%. Monthly rebalance on the last trading day, without exception."},
            {"eyebrow": "Worst Day",        "note": "Largest single-day drawdown −3.2%, March 14. Book back at prior high by the following Wednesday."},
            {"eyebrow": "Book composition", "note": "Seven positions held through the full year. Three entered mid-year. Two closed in June."},
        ],
        # ── P3 equity ribbon + 12-row monthly ladder (annual sum ≈ +16.8%)
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
        # ── P4 reflections quad (2×2 editorial)
        "reflection_blocks": [
            {
                "roman": "I",
                "title": "What I held onto",
                "paragraph": "The positions I held through the year were held not because I was confident, but because the theses I had written down for them continued to describe the world I was in. Conviction is a noun that does poorly in public. Written theses age better.",
                "bullets": [
                    "The semiconductor cohort — held on the operating-leverage thesis, which stayed intact.",
                    "The platform cohort — trimmed once in July, otherwise left alone.",
                    "Cash at a steady 9–11% through the year — not strategy, a shelter.",
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
                "paragraph": "I read one position as a story of operating leverage and missed a footnote that was not hidden — only, I had read it once and not reread it. The position was closed at a small loss. The error worth naming is not the loss. It is the confidence. I had been sure.",
                "bullets": [
                    "Over-weighting a thesis I had read once and treated as digested.",
                    "Reading weekend research on Sunday evening rather than Saturday morning.",
                    "Confusing a quiet six weeks with a constructive six weeks.",
                ],
            },
            {
                "roman": "IV",
                "title": "What I will keep watching",
                "paragraph": "Nothing here is a plan for the coming year. The items below are things I mean to keep observing — not because observing them will produce a return, but because not observing them has, in the past, produced regret.",
                "bullets": [
                    "Whether the semiconductor operating-leverage story survives a demand normalisation.",
                    "Whether the quiet stretches of August–September recur and how I spend them.",
                    "Whether the monthly-rebalance discipline survives a January without a print.",
                ],
            },
        ],
        # ── P5 editorial
        "pull_quote": (
            "The year did not arrive. It was made, decision by small decision — "
            "most of them unremarkable, a few regrettable, none forecast."
        ),
        "pull_quote_attr": f"PivoxQuant · Year {year}",
        "not_claimed": [
            "A thesis for the coming year.",
            "A blueprint for replication.",
            "A professional service or advisory.",
            "A guarantee of future observation quality.",
            "Tax or legal guidance.",
        ],
        # ── P6 colophon
        "data_sources": [
            {"key": "Price observations", "note": "Alpaca Market Data (IEX consolidated)."},
            {"key": "Corporate actions",  "note": "FMP v4 Stable."},
            {"key": "Risk-free",          "note": "3-Month T-Bill via FRED (DGS3MO)."},
            {"key": "Benchmark",          "note": "SPY total return, with dividends."},
        ],
        "typeset_in": "Source Serif 4 · Geist · JetBrains Mono",
        "disclaimer": DISCLAIMER,
        "LICENSE_NUMBER": None,
    }


def sample_capital_allocation() -> dict[str, Any]:
    return {
        "user_id":       SAMPLE_USER_ID,
        "user_name":     SAMPLE_USER_NAME,
        "generated_at":  _now_iso(),
        "issue_number":  1,
        "doc_ref":       "PQ-CA-01 \u00b7 v2026.04.22",
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
            "Weights are month-end marks.",
            "The 60/40 benchmark uses SPY/AGG, total return.",
            "Real assets combine REIT index and a 2% gold sleeve.",
            "Alternatives held for diversification.",
            "Rebalance events are observed, not prescribed by the document.",
        ],
        "pull_quote": "An allocation is not a verdict on the future \u2014 it is the shelter you choose before the weather changes.",
        "pull_quote_attribution": "PivoxQuant Allocation Desk",
        "disclaimer": DISCLAIMER,
    }


def sample_insider_mirror() -> dict[str, Any]:
    return {
        "user_id":      SAMPLE_USER_ID,
        "user_name":    SAMPLE_USER_NAME,
        "period_label": "April 2026",
        "period_end":   "2026-04-22",
        "generated_at": _now_iso(),
        "issue_number": 4,
        "doc_ref":      "PQ-IM-04 \u00b7 v2026.04.22",
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
            {"f":"Form 144", "v": 10, "c":"#B8956A"},
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
        "disclaimer":  DISCLAIMER,
    }


def sample_self_audit() -> dict[str, Any]:
    today = _today()
    return {
        "user_id":       SAMPLE_USER_ID,
        "user_name":     SAMPLE_USER_NAME,
        "quarter_label": f"{today.year} Q{(today.month - 1) // 3 + 1}",
        "period_start":  (today - timedelta(days=90)).isoformat(),
        "period_end":    today.isoformat(),
        "generated_at":  _now_iso(),
        "issue_number":  5,
        "doc_ref":       "PQ-SA-05 · v2026.04.21",
        "review_date":   today.isoformat(),
        "audit_score":   8.2,
        "red_flags":     0,
        "yellow_flags":  2,
        "positions_reviewed": 14,
        "journal_entries":    28,
        "audit_duration_min": 38,
        "prior_audit_score":  "7.8",
        "hero_headline": [
            "Ten questions.",
            "Ten answers, honest",
            "or otherwise.",
        ],
        "trades_total":   28,
        "wins":           18,
        "losses":         10,
        "win_rate_pct":   64.3,
        "avg_return_pct":  3.7,
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
                "1.8 closes per week, near the trailing four-quarter "
                "baseline. The observation journal carries an entry for every "
                "closed lot, with one gap of two sessions noted in early March."
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
                "were structural."
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
        "pull_quote": (
            "An audit is a mirror held quietly — not a judge's bench."
        ),
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
        "LICENSE_NUMBER": None,
        "best_decisions": [
            {"ticker": "NVDA",       "buy_date": (today - timedelta(days=68)).isoformat(), "buy_price": 612.00, "sell_price": 728.40, "return_pct":  19.0},
            {"ticker": "005930.KS",  "buy_date": (today - timedelta(days=52)).isoformat(), "buy_price": 72_000, "sell_price": None,    "return_pct":  11.2},
            {"ticker": "AAPL",       "buy_date": (today - timedelta(days=41)).isoformat(), "buy_price": 168.20, "sell_price": None,    "return_pct":  12.6},
        ],
        "worst_decisions": [
            {"ticker": "TSLA",       "buy_date": (today - timedelta(days=58)).isoformat(), "buy_price": 214.00, "sell_price": 188.20, "return_pct": -12.1},
            {"ticker": "035420.KS",  "buy_date": (today - timedelta(days=20)).isoformat(), "buy_price": 210_000, "sell_price": None,    "return_pct":  -6.1},
        ],
        "pattern_summary": (
            "실적 직후 48시간 이내 매매의 승률은 72%로 관찰됩니다. 뉴스 단독 "
            "근거 매매는 41%로 체계적으로 낮았습니다. 손절선 이탈 후에도 홀딩한 "
            "포지션의 평균 손실이 -8.2%로 기록되었습니다."
        ),
        "disclaimer": DISCLAIMER,
    }


def sample_burn_rate() -> dict[str, Any]:
    today = _today()
    return {
        "user_id":        SAMPLE_USER_ID,
        "user_name":      SAMPLE_USER_NAME,
        "period_label":   today.strftime("%Y-%m"),
        "period_label_long": today.strftime("%B %Y"),
        "period_start":   today.replace(day=1).isoformat(),
        "period_end":     today.isoformat(),
        "generated_at":   _now_iso(),
        "issue_number":   12,
        "doc_ref":        "PQ-BR-12 · v2026.04.21",
        "hero_headline": [
            "A slow arithmetic.",
            "Money walks out,",
            "seldom in crowds.",
        ],
        # Personal household burn (new v2 editorial ledger)
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
        # Legacy trading-burn fields retained for back-compat callers.
        "trades_total":   18,
        "notional_total": 32_500_000,
        "commission_total":  82_000,
        "tx_tax_total":      45_000,
        "cgt_est_total":    420_000,
        "fx_spread_total":   28_000,
        "slippage_total":    64_000,
        "burn_total":       639_000,
        "portfolio_value": 51_000_000,
        "burn_pct":         1.25,
        "by_market": [
            {"market": "US", "trades": 11, "notional": 21_000_000, "burn": 542_000},
            {"market": "KR", "trades":  7, "notional": 11_500_000, "burn":  97_000},
        ],
        "disclaimer": DISCLAIMER,
    }


def sample_credit_rating() -> dict[str, Any]:
    today = _today()
    return {
        "user_id":      SAMPLE_USER_ID,
        "user_name":    SAMPLE_USER_NAME,
        "as_of":        today.isoformat(),
        "generated_at": _now_iso(),
        "issue_number": 2,
        "doc_ref":      "PQ-CR-02 \u00b7 v2026.04.22",
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
            "The book clusters tightly around the A and BBB rungs.",
            "Below the dashed divider, the BB rung carries 12%.",
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
            {"k":"Stable",    "v": 9, "c":"#B8956A"},
            {"k":"Upgraded",  "v": 3, "c":"#B8956A"},
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
            "Ratings are observations from Moody's, S&P, and Fitch.",
            "OAS values from FINRA TRACE tape, end-of-day mid marks.",
            "Duration computed on modified basis.",
            "IG/HY line at BBB-/Baa3 per agency convention.",
            "Migrations are counted per issuer.",
        ],
        "pull_quote": "A credit rating is a letter the market writes about itself \u2014 read with interest, never as instruction.",
        "pull_quote_attribution": "PivoxQuant Credit Desk",
        "position_count": 10,
        "disclaimer":     DISCLAIMER,
    }


def sample_dividend_income() -> dict[str, Any]:
    _today()
    return {
        "user_id":      SAMPLE_USER_ID,
        "user_name":    SAMPLE_USER_NAME,
        "month_label":  "April 2026",
        "generated_at": _now_iso(),
        "issue_number": 4,
        "doc_ref":      "PQ-DI-04 \u00b7 v2026.04.22",
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
        "pull_quote": "A dividend is a kindness from a company to its owners \u2014 unremarkable until counted, cumulative once you do.",
        "pull_quote_attribution": "PivoxQuant Dividend Desk",
        "disclaimer": DISCLAIMER,
    }


def sample_portfolio_segment() -> dict[str, Any]:
    """Portfolio Segment — Goldman IC v2 6-page observational report.

    Rewritten for template contract: treemap on P2, 10-row segment ladder on
    P3, 2×2 quad (style box / region donut / sector rotation / corr heatmap)
    on P4, editorial quote on P5, colophon on P6.
    """
    today = _today()
    return {
        "user_id":        SAMPLE_USER_ID,
        "user_name":      SAMPLE_USER_NAME,
        "period_label":   f"{today.strftime('%B %Y')}",
        "issue_number":   4,
        "doc_ref":        "PQ-PS-04",
        "generated_at":   _now_iso(),
        "typeset_in":     "Source Serif 4 · Geist · JetBrains Mono",
        "LICENSE_NUMBER": None,

        "hero_headline": [
            "A portfolio is a choir.",
            "Each voice a sector, style, or region.",
            "We listen, then write down what we hear.",
        ],

        # Cover KPIs
        "kpi_sectors":        8,
        "kpi_styles_label":   "Growth · Value · Core",
        "kpi_regions_label":  "US · International",
        "kpi_hhi":            1840,

        # P2 — Treemap segments (sector -> % weight, size of rectangle)
        "treemap_segments": [
            {"name": "Technology",        "weight": 32.5, "ret": 11.8},
            {"name": "Healthcare",        "weight": 14.2, "ret":  3.5},
            {"name": "Financials",        "weight": 12.8, "ret":  4.8},
            {"name": "Consumer Disc.",    "weight":  9.5, "ret": -2.1},
            {"name": "Consumer Staples",  "weight":  8.1, "ret":  1.4},
            {"name": "Industrials",       "weight":  7.2, "ret":  5.2},
            {"name": "Energy",            "weight":  5.6, "ret":  8.2},
            {"name": "REITs",             "weight":  4.8, "ret": -0.8},
            {"name": "Cash",              "weight":  3.1, "ret":  0.2},
            {"name": "International",     "weight":  2.2, "ret":  3.1},
        ],

        # P3 — 10-row segment ladder
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

        # P4 quad — style box 3×3 (large/mid/small × growth/core/value)
        "style_box": [
            [0.08, 0.12, 0.04],
            [0.06, 0.14, 0.06],
            [0.24, 0.18, 0.08],
        ],
        "style_box_labels": {
            "rows": ["Small", "Mid", "Large"],
            "cols": ["Value", "Core", "Growth"],
        },

        # P4 — region donut (bar representation)
        "region_split": [
            {"name": "US",         "v": 72.5},
            {"name": "Intl Dev.",  "v": 18.4},
            {"name": "EM",         "v":  6.0},
            {"name": "Cash",       "v":  3.1},
        ],

        # P4 — sector rotation 12M (top 4 sectors)
        "sector_rotation": [
            {"name": "Technology",  "series": [0, 1.2, 2.8, 3.4, 4.1, 5.2, 6.1, 7.4, 8.8, 9.6, 10.8, 11.8]},
            {"name": "Energy",      "series": [0, 0.8, 1.4, 2.2, 2.8, 3.6, 4.4, 5.2, 6.1, 6.8, 7.6, 8.2]},
            {"name": "Financials",  "series": [0, 0.4, 0.8, 1.2, 1.8, 2.2, 2.8, 3.2, 3.8, 4.2, 4.6, 4.8]},
            {"name": "Healthcare",  "series": [0, 0.2, 0.6, 0.9, 1.3, 1.6, 2.1, 2.4, 2.8, 3.1, 3.3, 3.5]},
        ],

        # P4 — correlation among segments 5x5
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
        "disclaimer":  DISCLAIMER,
    }


def sample_kpi_dashboard() -> dict[str, Any]:
    """KPI Dashboard — Goldman IC v2 6-page monthly portfolio KPI report."""
    today = _today()
    return {
        "user_id":     SAMPLE_USER_ID,
        "user_name":   SAMPLE_USER_NAME,
        "period_label": f"{today.strftime('%B %Y')}",
        "issue_number": 4,
        "doc_ref":     "PQ-KPI-04",
        "generated_at": _now_iso(),
        "typeset_in":  "Source Serif 4 · Geist · JetBrains Mono",
        "LICENSE_NUMBER": None,

        "hero_headline": [
            "Numbers are the vocabulary.",
            "Observation is the grammar.",
            "This is a month's sentence.",
        ],

        # Cover KPIs
        "kpi_nav_label":     "$127,450",
        "kpi_mtd_pct":        2.4,
        "kpi_ytd_pct":        8.7,
        "kpi_sharpe":         0.94,

        # P2 — NAV equity curve (MTD daily)
        "nav_curve": [
            124440, 124680, 124920, 125110, 124880, 124940, 125220,
            125480, 125710, 125940, 126220, 126040, 125810, 126110,
            126480, 126820, 127110, 127380, 127210, 127450,
        ],
        "nav_best_day_index":  15,
        "nav_worst_day_index":  4,
        "nav_best_day_delta":  "+0.81%",
        "nav_worst_day_delta": "-0.24%",

        # P3 — 10-row KPI table
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

        # P4 quad
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
        # win/loss distribution histogram (returns in %)
        "winloss_bins":   [-6, -4, -2, 0, 2, 4, 6],
        "winloss_counts": [2, 4, 8, 14, 18, 10, 4],
        # holding-period distribution (days bins)
        "hold_bins":   ["0-7", "8-14", "15-30", "31-60", "61+"],
        "hold_counts": [6, 10, 22, 14, 8],
        # rolling 30D Sharpe
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
        "disclaimer":  DISCLAIMER,
    }


def sample_dd_checklist() -> dict[str, Any]:
    """DD Checklist — Pro 2-page · T+3 multi-position self-review prompt (v3).

    Mirrors `DDChecklistService.run_for_user()` output shape: pending list of
    positions (T+3 or older, unchecked) + as_of + disclaimer. The v3 template
    derives KPIs (count, oldest, avg age) from `pending` via `_to_v3_shape`.
    """
    today = _today()
    return {
        "user_id":      SAMPLE_USER_ID,
        "user_name":    SAMPLE_USER_NAME,
        "as_of":        today.isoformat(),
        "generated_at": _now_iso(),
        "pending": [
            {
                "position_id": 1001,
                "ticker":      "AAPL",
                "shares":      12.0,
                "avg_cost":    178.40,
                "added_at":    (today - timedelta(days=5)).isoformat() + "T09:30:00Z",
                "days_since":  5,
            },
            {
                "position_id": 1002,
                "ticker":      "MSFT",
                "shares":      6.0,
                "avg_cost":    412.85,
                "added_at":    (today - timedelta(days=4)).isoformat() + "T10:05:00Z",
                "days_since":  4,
            },
            {
                "position_id": 1003,
                "ticker":      "NVDA",
                "shares":      4.0,
                "avg_cost":    895.20,
                "added_at":    (today - timedelta(days=3)).isoformat() + "T14:20:00Z",
                "days_since":  3,
            },
        ],
        "disclaimer":   "정보 제공 목적이며 투자 권유가 아닙니다. 투자 판단은 본인 책임입니다.",
    }


def _sample_dd_checklist_legacy_unused() -> dict[str, Any]:
    """OLD 6-page IC pack sample — retained as reference only.

    Preserved per CLAUDE.md `rollback 가능하도록 보존` (autotrader.py 동일 정책).
    Not registered in artifact_samples mapping; safe to delete in a future cleanup
    sprint after the v3 template ships and stabilises.
    """
    _today()
    return {
        "user_id":     SAMPLE_USER_ID,
        "user_name":   SAMPLE_USER_NAME,
        "ticker":      "AAPL",
        "period_label": "Q2 2026",
        "issue_number": 2,
        "doc_ref":     "PQ-DD-AAPL-Q2",
        "generated_at": _now_iso(),
        "typeset_in":  "Source Serif 4 · Geist · JetBrains Mono",
        "LICENSE_NUMBER": None,

        "hero_headline": [
            "Questions, patiently asked.",
            "Answers, honestly recorded.",
            "A checklist is not a verdict.",
        ],

        # Cover KPIs
        "completeness_text": "24 / 30",
        "red_flags":         0,
        "review_date":       "2026-04-21",

        # P2 — 5-axis fundamentals pentagon (normalised 0..1 against sector median)
        "fundamentals_axes": [
            {"label": "Revenue Growth",   "value": 0.78, "raw": "+6.1% · 5Y CAGR"},
            {"label": "Operating Margin", "value": 0.88, "raw": "30.2% · TTM"},
            {"label": "Return on Equity", "value": 0.92, "raw": "154% · TTM"},
            {"label": "FCF Yield",        "value": 0.62, "raw": "3.4% · TTM"},
            {"label": "Debt Ratio",       "value": 0.55, "raw": "1.97× · D/E"},
        ],

        # P3 — 10-row checklist ladder
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

        # P4 quad
        "quarterly_label":  "$94.9B · Q4 FY25",
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
        "disclaimer":  DISCLAIMER,
    }


def sample_brag_card() -> dict[str, Any]:
    today = _today()
    month_start = today.replace(day=1) - timedelta(days=1)
    month_start = month_start.replace(day=1)
    month_end = today.replace(day=1) - timedelta(days=1)
    return {
        "user_id":         SAMPLE_USER_ID,
        "user_name":       SAMPLE_USER_NAME,
        "referral_code":   "PIVOX-DEMO",
        "month_label":     month_start.strftime("%Y-%m"),
        "month_label_long": month_start.strftime("%B %Y"),
        "month_start":     month_start.isoformat(),
        "month_end":       month_end.isoformat(),
        "generated_at":    _now_iso(),
        "issue_number":    4,
        "doc_ref":         "PQ-BC-04 · v2026.04.21",
        "return_pct":       8.9,
        "trade_count":     18,
        "best_ticker":     "NVDA",
        "best_return_pct":  22.4,
        "best_pnl_usd":    1240,
        "win_rate_pct":    67.0,
        "hold_days":        8,
        "entry_date":      "April 3",
        "exit_date":       "April 11",
        "entry_price":     "842",
        "exit_price":      "879",
        "position_size_pct": "3.2",
        "worst_ticker":    "TSLA",
        "worst_return_pct": -6.1,
        "anonymous":       False,
        "is_empty":        False,
        "share_token":     "demo-share-token",
        "hero_headline":   [
            "A small note to self.",
            "One month, one",
            "observation.",
        ],
        "hero_narrative": [
            (
                "Entered NVDA on April 3 at $842. Closed April 11 at $879. "
                "The thesis held three sessions, then handed off to the market's "
                "own weather. The gain was observed; the decision, imperfect as "
                "always, was your own."
            ),
            (
                "This is a record — not a pattern, not a plan, not a claim about "
                "tomorrow."
            ),
        ],
        "top_lots": [
            {"ticker": "NVDA",      "days":  8, "entry":  842.00, "exit":  879.00, "pnl": 1240, "spark": [0.20, 0.34, 0.46, 0.52, 0.60, 0.70, 0.82, 0.92]},
            {"ticker": "MSFT",      "days": 12, "entry":  412.00, "exit":  428.40, "pnl":  656, "spark": [0.30, 0.36, 0.42, 0.44, 0.52, 0.58, 0.62, 0.66]},
            {"ticker": "AAPL",      "days": 10, "entry":  172.50, "exit":  178.20, "pnl":  342, "spark": [0.40, 0.42, 0.48, 0.52, 0.58, 0.60, 0.64, 0.66]},
            {"ticker": "AVGO",      "days":  6, "entry": 1280.00, "exit": 1304.00, "pnl":  192, "spark": [0.40, 0.44, 0.48, 0.54, 0.56, 0.60, 0.62, 0.66]},
            {"ticker": "005930.KS", "days": 14, "entry":72000,    "exit":73400,    "pnl":  112, "spark": [0.50, 0.52, 0.56, 0.58, 0.62, 0.64, 0.66, 0.70]},
        ],
        "ledger_narrative": [
            (
                "Five lots cleared the month's realised-P&L threshold. The top two "
                "together contributed the majority of the monthly record — a "
                "concentration noted here for transparency rather than as a "
                "pattern to lean on. Hold windows clustered between six and "
                "fourteen sessions; none ran longer than a month."
            ),
            (
                "The bronze end-dot on each sparkline is the mark at exit "
                "relative to the row's own in-hold range. A single month is a "
                "small sample; this is a record, not a pattern."
            ),
        ],
        "data_sources": ["Broker statements", "Alpaca", "KIS", "Observation journal"],
        "typeset_in": "Source Serif 4 · Geist · JetBrains Mono · Noto Sans KR",
        "engine_note": "Historical record only. No directive, no target, no promise",
        "LICENSE_NUMBER": None,
        "disclaimer":      DISCLAIMER,
    }


def sample_monthly_brag() -> dict[str, Any]:
    b = sample_brag_card()
    # monthly_brag is the PNG 1080×1920 card — same keys minus share_token,
    # plus hold_days_avg which the 1080 PNG uses.
    return {
        "user_id":         b["user_id"],
        "user_name":       b["user_name"],
        "referral_code":   b["referral_code"],
        "month_label":     b["month_label"],
        "month_start":     b["month_start"],
        "month_end":       b["month_end"],
        "generated_at":    b["generated_at"],
        "return_pct":      b["return_pct"],
        "trade_count":     b["trade_count"],
        "hold_days_avg":   12.4,
        "best_ticker":     b["best_ticker"],
        "best_return_pct": b["best_return_pct"],
        "worst_ticker":    b["worst_ticker"],
        "worst_return_pct": b["worst_return_pct"],
        "anonymous":       False,
        "is_empty":        False,
        "disclaimer":      b["disclaimer"],
    }


# ── dispatch table ───────────────────────────────────────────────────────────

def sample_sp500_backtest() -> dict[str, Any]:
    """Ten-Year Observation backtest record — Strategy C (TSMOM + MeanReversion).

    All headline numbers come from docs/BACKTEST_RESULTS.md (2021-12-01 →
    2026-04-17 observation window). Monthly anchors simulated so they roll up
    to the published annual totals, never around them.
    """
    return {
        "issue_number": 1,
        "doc_ref": "PQ-BT-01 · v2026.04.21",
        "generated_at": "2026-04-21",
        "period_start": "2021-12-01",
        "period_end": "2026-04-17",
        "typeset_in": "Source Serif 4 · Geist · JetBrains Mono",
        "LICENSE_NUMBER": None,

        # Cover — hero KPIs (all numbers from BACKTEST_RESULTS.md)
        "hero_headline": [
            "Four years, four hundred names.",
            "One rule, measured in the open.",
            "Observations — historical, not forward-looking.",
        ],
        "hero_cagr": 21.19,
        "hero_sharpe": 0.94,
        "hero_alpha": 9.66,
        "hero_2022_spread": 23.2,

        # P2 — equity walk. Monthly marks; end values match Strategy C CAGR
        # compounded on $100K seed through 4.38 years → $218,240. SPY end
        # compounds from CAGR 12.55% → $151,100.
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

        # P3 — annual ladder
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

        # P3 — 6×6 correlation heatmap (observed)
        "corr_labels": ["Strategy C", "SPY", "QQQ", "TLT", "Gold", "VIX"],
        "corr_matrix": [
            [ 1.00,  0.78,  0.74, -0.12,  0.18, -0.42],
            [ 0.78,  1.00,  0.92, -0.32,  0.08, -0.68],
            [ 0.74,  0.92,  1.00, -0.28,  0.04, -0.62],
            [-0.12, -0.32, -0.28,  1.00,  0.22,  0.14],
            [ 0.18,  0.08,  0.04,  0.22,  1.00, -0.08],
            [-0.42, -0.68, -0.62,  0.14, -0.08,  1.00],
        ],

        # P4 — rolling 12M Sharpe, stepped through window
        "rolling_sharpe": [0.42, 0.58, 0.71, 0.68, 0.82, 0.94, 1.12, 1.24, 1.18, 1.02, 0.98, 0.88, 0.94],

        # P4 — underwater series (MDD reading −23.82% occurs in 2022 bear)
        "underwater": [
            0, -2.1, -8.4, -14.2, -19.6, -23.82, -18.4, -11.2, -4.8, 0,
            -3.2, -8.1, -4.4, 0, -2.8, -6.1, -9.4, -4.8, 0, -5.2,
            -11.4, -13.2, -6.8, 0, -3.4, -6.4,
        ],

        # P4 — monthly return histogram (53 months)
        "histogram_bins": [
            {"edge": -15, "count":  0},
            {"edge": -12, "count":  1},
            {"edge":  -9, "count":  2},
            {"edge":  -6, "count":  4},
            {"edge":  -3, "count":  6},
            {"edge":   0, "count":  8},
            {"edge":   3, "count": 12},
            {"edge":   6, "count": 10},
            {"edge":   9, "count":  6},
            {"edge":  12, "count":  3},
            {"edge":  15, "count":  1},
        ],

        # P4 — empirical vs normal distribution overlay
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

        # P5 — editorial pull quote + limits
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



_BUILDERS: dict[str, Callable[[], dict[str, Any]]] = {
    "weekly_memo":            sample_weekly_memo,
    "sp500_backtest":         sample_sp500_backtest,
    "earnings_prebrief":      sample_earnings_prebrief,
    "monthly_finance":        sample_monthly_finance,
    "risk_board":             sample_risk_board,
    "quarterly_self_report":  sample_quarterly_self_report,
    "year_end_letter":        sample_year_end_letter,
    "capital_allocation":     sample_capital_allocation,
    "insider_mirror":         sample_insider_mirror,
    "self_audit":             sample_self_audit,
    "burn_rate":              sample_burn_rate,
    "credit_rating":          sample_credit_rating,
    "dividend_income":        sample_dividend_income,
    "portfolio_segment":      sample_portfolio_segment,
    "kpi_dashboard":          sample_kpi_dashboard,
    "dd_checklist":           sample_dd_checklist,
    "brag_card":              sample_brag_card,
    "monthly_brag":           sample_monthly_brag,
}


def get_sample_data(artifact_type: str) -> dict[str, Any]:
    """Return the sample data dict for an artifact type. Raises KeyError
    when the type is unknown so callers get a clear 404."""
    builder = _BUILDERS.get(artifact_type)
    if builder is None:
        raise KeyError(artifact_type)
    return builder()


# ── catalog metadata (for the admin UI grid) ─────────────────────────────────

CATALOG: list[dict[str, Any]] = [
    {
        "type": "weekly_memo",
        "title_ko": "Weekly Investor Memo",
        "title_en": "Weekly Investor Memo",
        "description": "맥킨지 스타일 5페이지 주간 투자 메모. 일요일 08:00 KST 발송.",
        "tier": "pro",
        "formats": ["html", "pdf", "email"],
        "cadence": "weekly",
    },
    {
        "type": "earnings_prebrief",
        "title_ko": "Earnings Pre-Brief",
        "title_en": "Earnings Pre-Brief",
        "description": "실적 발표 30분 전 자동 발송되는 종목별 프리브리프.",
        "tier": "pro",
        "formats": ["html", "pdf", "email"],
        "cadence": "event",
    },
    {
        "type": "monthly_finance",
        "title_ko": "Monthly Finance Report",
        "title_en": "Monthly Finance Report",
        "description": "월간 현금흐름/세금 추정/비용 내역 종합 리포트.",
        "tier": "premium",
        "formats": ["html", "pdf"],
        "cadence": "monthly",
    },
    {
        "type": "risk_board",
        "title_ko": "Risk Board Deck",
        "title_en": "Risk Board Deck",
        "description": "VaR / Sharpe / 7-Layer Defense Score 리스크 임원 요약.",
        "tier": "premium",
        "formats": ["html", "pdf"],
        "cadence": "weekly",
    },
    {
        "type": "quarterly_self_report",
        "title_ko": "Quarterly Self Report",
        "title_en": "Quarterly Self Report",
        "description": "10-Q 스타일 분기 자기보고서. MDNA + 세그먼트 + 리스크.",
        "tier": "premium",
        "formats": ["html", "pdf"],
        "cadence": "quarterly",
    },
    {
        "type": "year_end_letter",
        "title_ko": "Year-End Shareholder Letter",
        "title_en": "Year-End Shareholder Letter",
        "description": "버핏 연례 서한 스타일. 연말 회고 + 내년 목표.",
        "tier": "premium",
        "formats": ["html", "pdf"],
        "cadence": "annual",
    },
    {
        "type": "capital_allocation",
        "title_ko": "Capital Allocation Memo",
        "title_en": "Capital Allocation Memo",
        "description": "HRP / Tail Risk Parity / ERC 후보 배분 비교.",
        "tier": "premium",
        "formats": ["html", "pdf"],
        "cadence": "on_demand",
    },
    {
        "type": "insider_mirror",
        "title_ko": "Insider Mirror",
        "title_en": "Insider Mirror",
        "description": "보유 종목과 겹치는 내부자 매매 주간 요약.",
        "tier": "premium",
        "formats": ["html", "pdf"],
        "cadence": "weekly",
    },
    {
        "type": "self_audit",
        "title_ko": "Self-Audit Report",
        "title_en": "Self-Audit Report",
        "description": "분기 의사결정 품질 감사 — 최고/최악 결정, 패턴.",
        "tier": "premium",
        "formats": ["html", "pdf"],
        "cadence": "quarterly",
    },
    {
        "type": "burn_rate",
        "title_ko": "Burn Rate Report",
        "title_en": "Burn Rate Report",
        "description": "수수료 / 거래세 / 세금 / FX 스프레드 총비용 내역.",
        "tier": "pro",
        "formats": ["html", "pdf"],
        "cadence": "monthly",
    },
    {
        "type": "credit_rating",
        "title_ko": "Portfolio Credit Rating",
        "title_en": "Portfolio Credit Rating",
        "description": "분산 / 유동성 / 리스크조정수익 5축 포트폴리오 등급.",
        "tier": "pro",
        "formats": ["html"],
        "cadence": "monthly",
    },
    {
        "type": "dividend_income",
        "title_ko": "Dividend Income Report",
        "title_en": "Dividend Income Report",
        "description": "배당 수령 / 향후 예상 / YoY 성장 리포트.",
        "tier": "premium",
        "formats": ["html", "pdf"],
        "cadence": "monthly",
    },
    {
        "type": "portfolio_segment",
        "title_ko": "Portfolio Segment Report",
        "title_en": "Portfolio Segment Report",
        "description": "전략 / 지역 / 섹터 세그먼트별 기여도 분해.",
        "tier": "premium",
        "formats": ["html", "pdf"],
        "cadence": "monthly",
    },
    {
        "type": "kpi_dashboard",
        "title_ko": "KPI Dashboard",
        "title_en": "KPI Dashboard",
        "description": "YTD / Sharpe / MDD / Turnover / Cash KPI 요약.",
        "tier": "pro",
        "formats": ["html"],
        "cadence": "monthly",
    },
    {
        "type": "dd_checklist",
        "title_ko": "Due-Diligence Checklist",
        "title_en": "Due-Diligence Checklist",
        "description": "매수 T+3 체크리스트 (재무 / 해자 / 경영진 / 밸류 / 리스크).",
        "tier": "pro",
        "formats": ["html"],
        "cadence": "event",
    },
    {
        "type": "brag_card",
        "title_ko": "Brag Card (Web)",
        "title_en": "Brag Card (Web)",
        "description": "월간 성과 공유용 카드 (웹/이메일).",
        "tier": "free",
        "formats": ["html", "email"],
        "cadence": "monthly",
    },
    {
        "type": "monthly_brag",
        "title_ko": "Monthly Brag Card (PNG)",
        "title_en": "Monthly Brag Card (PNG)",
        "description": "Instagram-Story 1080×1920 PNG 카드.",
        "tier": "free",
        "formats": ["png"],
        "cadence": "monthly",
    },
]
