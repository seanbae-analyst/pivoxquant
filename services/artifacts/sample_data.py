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
        "disclaimer": DISCLAIMER,
    }


def sample_earnings_prebrief() -> dict[str, Any]:
    today = _today()
    earnings_dt = datetime.combine(today + timedelta(days=2), datetime.min.time()).replace(hour=21, minute=0)
    mv = 12 * 189.42
    return {
        "user_id":         SAMPLE_USER_ID,
        "user_name":       SAMPLE_USER_NAME,
        "ticker":          "AAPL",
        "company_name":    "Apple Inc.",
        "earnings_datetime": earnings_dt.isoformat() + "Z",
        "fiscal_period":   "FY25 Q2",
        "generated_at":    _now_iso(),
        "consensus_eps":   1.54,
        "consensus_eps_low":  1.48,
        "consensus_eps_high": 1.61,
        "consensus_revenue":  94.3,  # $M in template display
        "current_price":      189.42,
        "surprise_history": [
            {"date": "2026-01-28", "actual_eps": 2.18, "estimate_eps": 2.10, "surprise_pct":  3.8},
            {"date": "2025-10-30", "actual_eps": 1.64, "estimate_eps": 1.60, "surprise_pct":  2.5},
            {"date": "2025-07-31", "actual_eps": 1.40, "estimate_eps": 1.35, "surprise_pct":  3.7},
            {"date": "2025-05-02", "actual_eps": 1.53, "estimate_eps": 1.50, "surprise_pct":  2.0},
        ],
        "expected_questions": [
            "iPhone 16 선주문 추이와 중국 시장 수요 회복 여부",
            "Services 매출 성장률이 15%대를 유지할 수 있는가",
            "Apple Intelligence 도입 효과가 ASP 인상에 기여하는가",
            "Mac/iPad 사이클 전망과 재고 수준",
            "자사주 매입 + 배당 확대 가이던스",
        ],
        "position_shares":   12,
        "position_avg_cost": 172.40,
        "position_mv":       mv,
        "sensitivity_beat":  round(mv * 0.03, 2),
        "sensitivity_miss": -round(mv * 0.03, 2),
        "risk_notes": [
            "변동성 ±4% 구간 관찰",
            "해당 포지션이 포트폴리오의 16.3% 비중",
        ],
        "disclaimer": DISCLAIMER,
    }


def sample_monthly_finance() -> dict[str, Any]:
    today = _today()
    month_start = today.replace(day=1) - timedelta(days=1)
    month_start = month_start.replace(day=1)
    fx_rate = 1356.2
    cash_usd = 2_400.00
    cash_krw = 5_000_000
    mv_usd  = 21_800.00
    mv_krw  = 13_200_000
    return {
        "user_id":        SAMPLE_USER_ID,
        "user_name":      SAMPLE_USER_NAME,
        "month_label":    month_start.strftime("%Y-%m"),
        "period_start":   month_start.isoformat(),
        "period_end":     (today.replace(day=1) - timedelta(days=1)).isoformat(),
        "next_month_label": today.strftime("%Y-%m"),
        "generated_at":   _now_iso(),
        "fx_rate":        fx_rate,
        "cash": {
            "cash_usd":   cash_usd,
            "cash_krw":   cash_krw,
            "total_krw":  cash_krw + cash_usd * fx_rate,
        },
        "positions_mv": {
            "mv_usd":    mv_usd,
            "mv_krw":    mv_krw,
            "total_krw": mv_krw + mv_usd * fx_rate,
        },
        "liquidity_ratio": 16.1,
        "position_count": 7,
        "burn_rate_krw":  214_000,
        "runway_months":  38.3,
        "cost_breakdown": {
            "trade_count":            18,
            "us_notional_usd":        21_000.00,
            "us_commission_usd":         52.00,
            "kr_notional_krw":        11_500_000,
            "kr_commission_krw":          30_000,
            "kr_transaction_tax_krw":     45_000,
            "fx_spread_krw":              28_000,
            "total_krw":                 174_000,
        },
        "tax_estimate": {
            "realised_us_gain_usd":       1_908.00,
            "us_capital_gains_krw":         569_640,
            "realised_kr_gain_krw":         420_000,
            "forward_12m_dividend_krw":   1_100_000,
            "dividend_withholding_krw":     169_400,
            "total_estimated_krw":          739_040,
        },
        "watch": {
            "ex_dividends": [
                {"date": (today + timedelta(days=4)).isoformat(),  "ticker": "AAPL",  "amount": 0.25},
                {"date": (today + timedelta(days=12)).isoformat(), "ticker": "MSFT",  "amount": 0.75},
            ],
            "earnings": [
                {"date": (today + timedelta(days=3)).isoformat(),  "ticker": "AAPL"},
                {"date": (today + timedelta(days=9)).isoformat(),  "ticker": "005930.KS"},
            ],
        },
        "disclaimer": DISCLAIMER,
    }


def sample_risk_board() -> dict[str, Any]:
    today = _today()
    return {
        "user_id":       SAMPLE_USER_ID,
        "user_name":     SAMPLE_USER_NAME,
        "period_label":  today.strftime("%Y-%m-%d"),
        "trigger":       "scheduled",
        "generated_at":  _now_iso(),
        "portfolio_value":  51_000_000,
        "portfolio_ccy":   "KRW",
        "position_count":   7,
        "var95_pct":       -2.3,
        "var99_pct":       -3.8,
        "sharpe_annual":    1.42,
        "sortino_annual":   1.88,
        "calmar":           1.10,
        "max_drawdown_pct": -11.6,
        "sector_breakdown": [
            {"sector": "Information Technology", "weight_pct": 42.3},
            {"sector": "Semiconductors",          "weight_pct": 27.8},
            {"sector": "Communication Services",  "weight_pct": 14.1},
            {"sector": "Consumer Discretionary",  "weight_pct":  9.5},
            {"sector": "Financials",              "weight_pct":  6.3},
        ],
        "tail_ratio":     1.63,
        "component_es": [
            {"ticker": "NVDA",       "sector": "Semiconductors",          "es_contrib": -1.842},
            {"ticker": "AAPL",       "sector": "Information Technology",  "es_contrib": -1.104},
            {"ticker": "005930.KS",  "sector": "Semiconductors",          "es_contrib": -0.891},
        ],
        "vix_current":   14.8,
        "defense_score": 78,
        "defense_status": "GREEN",
        "layer_status": [
            {"label": "VaR 95",        "passed": True,  "note": "일일 VaR -2.3% — 임계 -3% 이내"},
            {"label": "Correlation",   "passed": True,  "note": "평균 상관 0.42"},
            {"label": "VIX Filter",    "passed": True,  "note": "VIX 14.8 — 정상 구간"},
            {"label": "Tail Ratio",    "passed": True,  "note": "1.63 — 상방 꼬리 우세"},
            {"label": "Daily Loss",    "passed": True,  "note": "당일 -0.4%"},
            {"label": "Sector Concentration", "passed": False, "note": "IT 섹터 42% — 40% 기준 초과 관찰"},
            {"label": "Cash Buffer",   "passed": True,  "note": "현금 12.3%"},
        ],
        "top_risks": (
            "IT 섹터 비중 42%로 단일 이벤트 리스크가 확대된 구간으로 관찰됩니다. "
            "VIX 14.8로 저변동성 구간이나 Tail Ratio 1.63은 과거 평균 대비 다소 "
            "낮은 수준입니다. 유동성과 현금 버퍼는 임계 이내로 관찰됩니다."
        ),
        "disclaimer": DISCLAIMER,
    }


def sample_quarterly_self_report() -> dict[str, Any]:
    today = _today()
    quarter_label = f"{today.year} Q{(today.month - 1) // 3 + 1}"
    return {
        "user_id":       SAMPLE_USER_ID,
        "user_name":     SAMPLE_USER_NAME,
        "quarter_label": quarter_label,
        "period_start":  (today - timedelta(days=90)).isoformat(),
        "period_end":    today.isoformat(),
        "generated_at":  _now_iso(),
        "opening_value":  45_000_000,
        "closing_value":  51_000_000,
        "net_cash_flow":   2_000_000,
        "quarterly_return_pct": 8.9,
        "mdna": (
            "분기 전반에 걸쳐 반도체 섹터 리드. NVIDIA 추가 매수가 기여도 1위 "
            "였으며, 삼성전자는 HBM 기대감으로 리레이팅. 분산이 부족하다는 "
            "사전 식별에도 불구 IT 비중 40%를 유지한 것은 기록용으로 남김."
        ),
        "segments": [
            {"sector": "Information Technology", "trade_count": 11, "pnl":  2_180_000},
            {"sector": "Semiconductors",          "trade_count":  7, "pnl":  1_420_000},
            {"sector": "Communication Services",  "trade_count":  5, "pnl":    180_000},
            {"sector": "Consumer Discretionary",  "trade_count":  3, "pnl":   -120_000},
            {"sector": "Financials",              "trade_count":  2, "pnl":     62_000},
        ],
        "risk_factors": [
            {"factor": "IT 섹터 집중",  "note": "42% 유지 — 단일 이벤트 리스크 확대 관찰"},
            {"factor": "단일 종목",      "note": "NVDA 11.2% 비중 — 변동성 노출 확대"},
            {"factor": "현금 버퍼",      "note": "12.3% — 임계 10% 이상"},
        ],
        "internal_controls": [
            {"layer": "Weekly Checklist", "label": "주간 자기 점검",   "status": "3건 누락"},
            {"layer": "Stop Loss",         "label": "손절선 재설정",    "status": "1건 미이행 (GOOGL)"},
            {"layer": "MDNA",              "label": "분기 MDNA 작성",   "status": "OK"},
        ],
        "legal_matters": [],
        "principal_positions": [
            {"ticker": "NVDA",       "sector": "Semiconductors",          "shares":  5,  "avg_cost": 610.00, "last": 728.40,  "mv":  3_642.00,  "weight_pct": 11.2, "return_pct": 22.4},
            {"ticker": "AAPL",       "sector": "Information Technology",  "shares": 12,  "avg_cost": 172.40, "last": 189.42,  "mv":  2_273.04,  "weight_pct": 10.8, "return_pct":  6.3},
            {"ticker": "005930.KS",  "sector": "Semiconductors",          "shares": 50,  "avg_cost": 72_000, "last": 79_000,  "mv": 3_950_000,  "weight_pct":  9.4, "return_pct": 10.1},
        ],
        "thesis_entries": [
            {"ticker": "NVDA",       "thesis": "AI 인프라 수요 지속",  "created_at": "2025-12-10"},
            {"ticker": "005930.KS",  "thesis": "HBM 점유율 회복",      "created_at": "2026-01-22"},
        ],
        "thesis_checks": [
            {"ticker": "NVDA",       "verdict": "on_track",  "note": "수요 가이던스 상향"},
            {"ticker": "005930.KS",  "verdict": "watch",     "note": "HBM3E 램프업 지연 관찰"},
        ],
        "decision_quality": {
            "trades_total":     28,
            "wins":             18,
            "losses":           10,
            "win_rate_pct":     64.3,
            "avg_return_pct":    3.7,
            "pattern_summary":  "실적 직후 48시간 이내 매매의 승률이 체계적으로 높게 관찰됩니다. 뉴스 단독 근거 매매는 승률이 크게 하락한 구간입니다.",
            "best_decisions": [
                {"ticker": "NVDA",      "buy_date": "2026-02-05", "buy_price": 612.00, "sell_price": 728.40, "return_pct": 19.0},
                {"ticker": "005930.KS", "buy_date": "2026-02-18", "buy_price": 72_000, "sell_price": None,    "return_pct": 11.2},
            ],
            "worst_decisions": [
                {"ticker": "TSLA",       "buy_date": "2026-01-11", "buy_price": 214.00, "sell_price": 188.20, "return_pct": -12.1},
                {"ticker": "035420.KS",  "buy_date": "2026-03-02", "buy_price": 210_000, "sell_price": None,    "return_pct":  -6.1},
            ],
        },
        "thesis_checklist": [
            {"ticker": "NVDA",       "question": "AI 자본지출 서프라이즈 지속?"},
            {"ticker": "005930.KS",  "question": "HBM3E 양산 가이던스?"},
            {"ticker": "AAPL",       "question": "iPhone 16 선주문 가이드?"},
        ],
        "watch_items": [
            {"date": (today + timedelta(days=14)).isoformat(), "label": "Fed FOMC 결정"},
            {"date": (today + timedelta(days=21)).isoformat(), "label": "NVDA 실적 컨퍼런스콜"},
        ],
        "disclaimer": DISCLAIMER,
    }


def sample_year_end_letter() -> dict[str, Any]:
    today = _today()
    return {
        "user_id":      SAMPLE_USER_ID,
        "user_name":    SAMPLE_USER_NAME,
        "year":         today.year - 1,
        "period_start": date(today.year - 1, 1, 1).isoformat(),
        "period_end":   date(today.year - 1, 12, 31).isoformat(),
        "generated_at": _now_iso(),
        "opening_value": 32_000_000,
        "closing_value": 48_500_000,
        "ytd_return_pct":  18.7,
        "benchmark_pct":   13.2,
        "alpha_pct":        5.5,
        "total_trades":    47,
        "win_rate_pct":    63.8,
        "sector_contribution": [
            {"sector": "Information Technology", "trade_count": 22, "avg_return_pct":  9.1},
            {"sector": "Semiconductors",          "trade_count": 14, "avg_return_pct": 11.4},
            {"sector": "Communication Services",  "trade_count":  6, "avg_return_pct":  1.8},
            {"sector": "Consumer Discretionary",  "trade_count":  3, "avg_return_pct":  0.9},
            {"sector": "Financials",              "trade_count":  2, "avg_return_pct":  0.5},
        ],
        "best_decisions": [
            {"ticker": "NVDA",       "buy_date": "2025-03-15", "buy_price": 450.00, "sell_price": 758.10, "return_pct": 68.4},
            {"ticker": "005930.KS",  "buy_date": "2025-07-22", "buy_price": 62_000, "sell_price": 76_900, "return_pct": 24.1},
            {"ticker": "AAPL",       "buy_date": "2025-11-04", "buy_price": 168.20, "sell_price": None,    "return_pct": 12.6},
        ],
        "worst_decisions": [
            {"ticker": "TSLA",       "buy_date": "2025-05-18", "buy_price": 254.00, "sell_price": 207.80, "return_pct": -18.2},
            {"ticker": "PYPL",       "buy_date": "2025-08-04", "buy_price":  72.40, "sell_price":  64.10, "return_pct": -11.5},
        ],
        "risk_profile":    "Moderate-Aggressive",
        "realized_style":  "Growth-tilted with Quant overlay",
        "consistency_score": 74,
        "consistency_notes": (
            "월별 수익률 표준편차 3.8%, 최대 낙폭 -11.6%. 온보딩 시 선택하신 "
            "Moderate-Aggressive 성향과 실제 거래 패턴이 대체로 일치합니다. "
            "다만 IT 섹터 비중이 의도보다 10%p 높았던 월이 3개월 관찰되었습니다."
        ),
        "watch_items": [
            {"date": (today + timedelta(days=30)).isoformat(),  "label": "Fed 3월 FOMC 점도표 발표"},
            {"date": (today + timedelta(days=45)).isoformat(),  "label": "한국 실적 시즌 개시 — 5월 공시"},
            {"date": (today + timedelta(days=80)).isoformat(),  "label": "NVDA 실적"},
        ],
        "shareholder_letter": (
            f"친애하는 {SAMPLE_USER_NAME}님, 올해 한 해 포트폴리오는 벤치마크를 "
            "5.5%p 상회했습니다. 다만 IT 섹터 의존도가 높다는 점은 분산 관점에서 "
            "보완할 필요가 있습니다. 내년에는 규율 기반 리밸런싱과 현금 비중 10% "
            "하한을 유지하는 것을 목표로 합니다."
        ),
        "disclaimer": DISCLAIMER,
    }


def sample_capital_allocation() -> dict[str, Any]:
    return {
        "calc_token":    "demo-allocation-abc123",
        "user_id":       SAMPLE_USER_ID,
        "user_name":     SAMPLE_USER_NAME,
        "cash_amount":   5_000_000.0,
        "portfolio_ccy": "KRW",
        "generated_at":  _now_iso(),
        "scenarios": [
            {
                "label":       "Scenario 1 — Diversify Existing",
                "type":        "diversify_existing",
                "tickers":     ["AAPL", "NVDA", "MSFT", "GOOGL", "005930.KS", "000660.KS", "035420.KS"],
                "weights":     [0.143, 0.143, 0.143, 0.143, 0.143, 0.143, 0.142],
                "return_cagr": 15.4,
                "volatility":  19.8,
                "max_dd":      -11.2,
                "sharpe":       0.78,
                "note":        "과거 5년 관찰 · 기존 7종목 균등 분배",
            },
            {
                "label":       "Scenario 2 — New Ticker (NVDA 집중)",
                "type":        "new_ticker",
                "tickers":     ["NVDA"],
                "weights":     [1.0],
                "return_cagr": 68.4,
                "volatility":  42.1,
                "max_dd":      -28.3,
                "sharpe":       1.62,
                "note":        "과거 5년 관찰 · 단일 종목 집중",
            },
            {
                "label":       "Scenario 3 — Hold Cash",
                "type":        "cash",
                "tickers":     [],
                "weights":     [],
                "return_cagr":  0.0,
                "volatility":   0.0,
                "max_dd":       0.0,
                "sharpe":       None,
                "note":        "현금 보유 · 수익률/변동성 0 가정",
            },
            {
                "label":       "Scenario 4 — Dividend ETF (SCHD)",
                "type":        "dividend_etf",
                "tickers":     ["SCHD"],
                "weights":     [1.0],
                "return_cagr": 11.2,
                "volatility":  14.6,
                "max_dd":      -14.8,
                "sharpe":       0.77,
                "note":        "과거 5년 관찰 · 배당 ETF",
            },
        ],
        "etf_whitelist": {
            "SCHD": "Schwab U.S. Dividend Equity ETF",
            "VYM":  "Vanguard High Dividend Yield ETF",
        },
        "disclaimer": (
            "본 결과는 과거 5년 가격 데이터에 기반한 통계적 관찰이며, 향후 수익률을 "
            "보장하지 않습니다. PivoxQuant은 어떠한 배분도 권유·추천하지 않으며, "
            "본 계산은 이용자가 직접 입력한 시나리오의 과거 사실만 요약합니다. "
            "투자 판단과 그 결과는 전적으로 이용자 본인의 책임입니다."
        ),
    }


def sample_insider_mirror() -> dict[str, Any]:
    today = _today()
    return {
        "user_id":      SAMPLE_USER_ID,
        "user_name":    SAMPLE_USER_NAME,
        "period_label": f"{(today - timedelta(days=7)).isoformat()} — {today.isoformat()}",
        "generated_at": _now_iso(),
        "transactions": [
            {
                "transaction_date": (today - timedelta(days=2)).isoformat(),
                "ticker":       "NVDA",
                "company":      "NVIDIA Corp.",
                "insider":      "Jensen Huang",
                "relationship": "CEO",
                "direction":    "sell",
                "transaction_code": "S",
                "shares":       120_000,
                "price":        910.42,
                "value":        109_250_400,
                "currency":     "USD",
                "region":       "US",
                "source":       "SEC Form 4",
                "disclosure_url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001045810",
            },
            {
                "transaction_date": (today - timedelta(days=5)).isoformat(),
                "ticker":       "005930.KS",
                "company":      "삼성전자",
                "insider":      "이재용",
                "relationship": "Chairman",
                "direction":    "buy",
                "transaction_code": "P",
                "shares":       300_000,
                "price":        74_500,
                "value":        22_350_000_000,
                "currency":     "KRW",
                "region":       "KR",
                "source":       "DART",
                "disclosure_url": "https://dart.fss.or.kr/dsaf001/main.do",
            },
        ],
        "held_overlap": ["NVDA", "005930.KS"],
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
        "trades_total":   28,
        "wins":           18,
        "losses":         10,
        "win_rate_pct":   64.3,
        "avg_return_pct":  3.7,
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
            "실적 직후 48시간 이내 매매의 승률은 72%로 관찰됩니다. 반면 뉴스 단독 "
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
        "period_start":   today.replace(day=1).isoformat(),
        "period_end":     today.isoformat(),
        "generated_at":   _now_iso(),
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
        "diversification":       {"score": 72, "weight": 0.25, "note": "7종목 / 5섹터"},
        "liquidity":             {"score": 88, "weight": 0.15, "note": "대형주 비중 94%"},
        "risk_adjusted_return":  {"score": 81, "weight": 0.30, "note": "Sharpe 1.42"},
        "drawdown_discipline":   {"score": 68, "weight": 0.20, "note": "MDD -11.6%"},
        "cash_buffer":           {"score": 62, "weight": 0.10, "note": "현금 12.3%"},
        "composite_score":       76,
        "grade":                 "A",
        "prev_grade":            "BBB",
        "change":                "upgrade",
        "factor_details": [
            {"name": "분산",           "weight": 0.25, "score": 72, "note": "섹터 5개, 상위 비중 42%"},
            {"name": "유동성",          "weight": 0.15, "score": 88, "note": "평균 거래대금 $1.2B"},
            {"name": "리스크 조정 수익", "weight": 0.30, "score": 81, "note": "Sharpe 1.42 / Sortino 1.88"},
            {"name": "낙폭 규율",        "weight": 0.20, "score": 68, "note": "MDD -11.6% 재진입 시간 24일"},
            {"name": "현금 버퍼",        "weight": 0.10, "score": 62, "note": "현금 12.3% 유지"},
        ],
        "position_count": 7,
        "disclaimer":     DISCLAIMER,
    }


def sample_dividend_income() -> dict[str, Any]:
    today = _today()
    month_start = today.replace(day=1)
    return {
        "user_id":      SAMPLE_USER_ID,
        "user_name":    SAMPLE_USER_NAME,
        "month_label":  month_start.strftime("%Y-%m"),
        "period_start": month_start.isoformat(),
        "period_end":   today.isoformat(),
        "next_month_label": (month_start.replace(day=28) + timedelta(days=4)).strftime("%Y-%m"),
        "generated_at": _now_iso(),
        "fx_rate":      1356.2,
        "received_rows": [
            {"ticker": "AAPL",       "shares": 12, "per_share": 0.2400,   "ex_dates": [(today - timedelta(days=10)).isoformat()], "ccy": "USD", "gross":   2.88},
            {"ticker": "MSFT",       "shares":  8, "per_share": 0.7500,   "ex_dates": [(today - timedelta(days=18)).isoformat()], "ccy": "USD", "gross":   6.00},
            {"ticker": "005930.KS",  "shares": 50, "per_share": 361.0000, "ex_dates": [(today - timedelta(days=22)).isoformat()], "ccy": "KRW", "gross": 18_050},
        ],
        "received_totals": {"gross_usd": 8.88, "gross_krw": 30_100},
        "position_count": 7,
        "monthly_series": [
            {"label": "2025-05", "gross_usd":  4.10, "gross_krw":  5_400},
            {"label": "2025-06", "gross_usd":  5.40, "gross_krw":  7_300},
            {"label": "2025-07", "gross_usd":  6.20, "gross_krw":  8_300},
            {"label": "2025-08", "gross_usd":  5.80, "gross_krw":  7_900},
            {"label": "2025-09", "gross_usd":  6.50, "gross_krw":  8_800},
            {"label": "2025-10", "gross_usd":  7.20, "gross_krw":  9_700},
            {"label": "2025-11", "gross_usd":  6.90, "gross_krw":  9_300},
            {"label": "2025-12", "gross_usd":  7.80, "gross_krw": 10_500},
            {"label": "2026-01", "gross_usd":  7.20, "gross_krw":  9_700},
            {"label": "2026-02", "gross_usd":  8.10, "gross_krw": 10_900},
            {"label": "2026-03", "gross_usd":  8.40, "gross_krw": 11_400},
            {"label": "2026-04", "gross_usd":  8.88, "gross_krw": 12_040},
        ],
        "yoy_growth_pct": 22.4,
        "forward_rows": [
            {"ticker": "AAPL",  "shares": 12, "per_share": 0.2500,  "ccy": "USD", "gross":  3.00},
            {"ticker": "MSFT",  "shares":  8, "per_share": 0.7700,  "ccy": "USD", "gross":  6.16},
        ],
        "forward_totals": {"gross_krw": 12_430, "net_krw": 10_515},
        "annual_yield_est": 1.18,
        "disclaimer": DISCLAIMER,
    }


def sample_portfolio_segment() -> dict[str, Any]:
    today = _today()
    sector_rows = [
        {"label": "Information Technology", "weight_pct": 42.3, "return_pct": 11.8, "pnl":  4_100_000},
        {"label": "Semiconductors",          "weight_pct": 27.8, "return_pct":  9.2, "pnl":  2_160_000},
        {"label": "Communication Services",  "weight_pct": 14.1, "return_pct":  1.4, "pnl":    280_000},
        {"label": "Consumer Discretionary",  "weight_pct":  9.5, "return_pct": -0.8, "pnl":    -60_000},
        {"label": "Financials",              "weight_pct":  6.3, "return_pct":  1.2, "pnl":     62_000},
    ]
    region_rows = [
        {"label": "US",    "weight_pct": 62.5, "return_pct": 11.3, "pnl":  5_080_000},
        {"label": "KR",    "weight_pct": 27.8, "return_pct":  9.2, "pnl":  2_160_000},
        {"label": "Cash",  "weight_pct":  9.7, "return_pct":  0.2, "pnl":     14_000},
    ]
    style_rows = [
        {"label": "Growth",    "weight_pct": 58.2, "return_pct": 12.8, "pnl":  4_900_000},
        {"label": "Dividend",   "weight_pct": 18.4, "return_pct":  2.1, "pnl":    380_000},
        {"label": "Cyclical",   "weight_pct": 13.6, "return_pct":  0.5, "pnl":     60_000},
        {"label": "Value",      "weight_pct":  9.8, "return_pct":  3.2, "pnl":    180_000},
    ]
    best = [
        {"dim": "Sector", "label": "Information Technology", "weight_pct": 42.3, "return_pct": 11.8},
        {"dim": "Region", "label": "US",                       "weight_pct": 62.5, "return_pct": 11.3},
        {"dim": "Style",  "label": "Growth",                   "weight_pct": 58.2, "return_pct": 12.8},
    ]
    worst = [
        {"dim": "Sector", "label": "Consumer Discretionary",   "weight_pct":  9.5, "return_pct": -0.8},
        {"dim": "Style",  "label": "Cyclical",                  "weight_pct": 13.6, "return_pct":  0.5},
        {"dim": "Region", "label": "Cash",                      "weight_pct":  9.7, "return_pct":  0.2},
    ]
    return {
        "user_id":        SAMPLE_USER_ID,
        "user_name":      SAMPLE_USER_NAME,
        "quarter_label":  f"{today.year} Q{(today.month - 1) // 3 + 1}",
        "period_start":   (today - timedelta(days=90)).isoformat(),
        "period_end":     today.isoformat(),
        "generated_at":   _now_iso(),
        "portfolio_value": 51_000_000,
        "portfolio_ccy":  "KRW",
        "sector_rows":    sector_rows,
        "region_rows":    region_rows,
        "style_rows":     style_rows,
        "best_segments":  best,
        "worst_segments": worst,
        "narrative": (
            "분기 전반에 걸쳐 Growth 스타일과 US 지역 비중이 수익 기여도 상위를 "
            "차지했습니다. Sector 레벨에서는 IT가 +11.8%로 주도적이었습니다. "
            "Consumer Discretionary는 -0.8%로 유일한 마이너스 기여 섹터입니다."
        ),
        "disclaimer":     DISCLAIMER,
    }


def sample_kpi_dashboard() -> dict[str, Any]:
    today = _today()
    return {
        "user_id":     SAMPLE_USER_ID,
        "user_name":   SAMPLE_USER_NAME,
        "as_of":       today.isoformat(),
        "generated_at": _now_iso(),
        "portfolio_value": 51_000_000,
        "portfolio_ccy":   "KRW",
        "ytd_return_pct":   8.9,
        "sharpe_annual":    1.42,
        "max_drawdown_pct": -11.6,
        "turnover_ratio":    0.82,
        "cash_pct":         12.3,
        "position_count":    7,
        "disclaimer":       DISCLAIMER,
    }


def sample_dd_checklist() -> dict[str, Any]:
    today = _today()
    return {
        "user_id":     SAMPLE_USER_ID,
        "user_name":   SAMPLE_USER_NAME,
        "as_of":       today.isoformat(),
        "generated_at": _now_iso(),
        "pending": [
            {
                "position_id": 10001,
                "ticker":      "NVDA",
                "shares":      5,
                "avg_cost":    610.00,
                "added_at":   (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=5)).isoformat() + "Z",
                "days_since":  5,
            },
            {
                "position_id": 10002,
                "ticker":      "035420.KS",
                "shares":      8,
                "avg_cost":    210_000,
                "added_at":   (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=4)).isoformat() + "Z",
                "days_since":  4,
            },
        ],
        "disclaimer": DISCLAIMER,
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
        "return_pct":       8.9,
        "trade_count":     18,
        "best_ticker":     "NVDA",
        "best_return_pct":  22.4,
        "worst_ticker":    "TSLA",
        "worst_return_pct": -6.1,
        "anonymous":       False,
        "is_empty":        False,
        "share_token":     "demo-share-token",
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

_BUILDERS: dict[str, Callable[[], dict[str, Any]]] = {
    "weekly_memo":            sample_weekly_memo,
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
