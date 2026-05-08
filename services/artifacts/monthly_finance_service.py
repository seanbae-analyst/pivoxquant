"""Monthly Finance Report — 6-page PDF (Premium).

Combines Cash Runway + Cost/Tax Ledger + Watch Items into one consolidated
"CFO dashboard" style artifact. Fires monthly at 11:00 KST on the 1st.

Legal framing (legal_risk_audit compliant)
------------------------------------------
The report is strictly **descriptive** of the user's own numbers:

  * Cash Runway  — "유휴 현금 ₩X → 이 상태로 N개월 유지 가능" (math only)
  * Cost/Tax     — "지난달 수수료/거래세/환전료 합계" (observed facts)
  * Watch Items  — "다음 달 ex-dividend/실적 발표 캘린더" (calendar only)

The report NEVER:
  * suggests reallocations (directive prose is forbidden)
  * recommends positions (directive prose is forbidden)
  * predicts price movement

All prose passes through `legal_filter.safe_scrub` and the shared
`_disclaimer.html` partial is embedded in the final page.

Entry points
------------
    MonthlyFinanceService().generate_for_user(user_id, as_of=None) → data dict
    MonthlyFinanceService().render_html(data)                      → str
    MonthlyFinanceService().render_pdf(data)                       → bytes | None
    MonthlyFinanceService().run_for_user(user, ...)                → Artifact
    MonthlyFinanceService().run_monthly(target_month=None)         → summary

Data sources (read-only, no new DB models)
------------------------------------------
  * `TradeHistory` — last-month fills; commission proxy + volume sums.
  * `Position`     — current book for market value / exposure.
  * `User.available_capital` + `.available_capital_krw` — cash.
  * `services.fx_service.get_rate()` — spot USD/KRW.
"""
from __future__ import annotations

import calendar
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from extensions import db
from models import Artifact, Position, TradeHistory, User

logger = logging.getLogger(__name__)


_TEMPLATE_DIR = Path(__file__).parent / "templates"
_DEFAULT_STORAGE_DIR = (
    Path(__file__).resolve().parents[2] / "artifacts" / "monthly_finance"
)
_PAID_TIERS = frozenset({"premium", "elite"})

# Rough cost heuristics (informational only — defensible because actual
# broker fees aren't available in the user's book; these are industry defaults
# clearly marked as "estimates" in the template).
_US_COMMISSION_BPS = 5.0          # Alpaca is ~0 but typical retail broker
_KR_BROKERAGE_BPS  = 15.0         # KIS 일반 0.015%
_KR_TRANSACTION_TAX_BPS = 20.0    # 증권거래세 0.2% (KOSPI 매도분)
_FX_SPREAD_BPS     = 100.0        # 은행 환전 스프레드 약 1.0%

# Tax rates (informational only; user needs a real tax advisor).
_US_CAPITAL_GAINS_PCT = 22.0      # 해외주식 양도세 22% (지방세 포함 기본)
_KR_DIVIDEND_WITHHOLDING_PCT = 15.4


def _storage_dir() -> Path:
    override = os.environ.get("MONTHLY_FINANCE_STORAGE_DIR")
    d = Path(override) if override else _DEFAULT_STORAGE_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── lazy deps ────────────────────────────────────────────────────────────────

def _try_import_weasyprint():
    try:
        from weasyprint import HTML  # type: ignore
        return HTML
    except Exception as exc:  # pragma: no cover
        logger.info("WeasyPrint unavailable (%s); skipping PDF.", exc)
        return None


def _try_import_jinja():
    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape
        return Environment, FileSystemLoader, select_autoescape
    except Exception as exc:  # pragma: no cover
        logger.warning("Jinja2 unavailable (%s).", exc)
        return None, None, None


def _fx_rate() -> float:
    try:
        from services import fx_service
        rate = float(fx_service.get_rate() or 0)
        if rate >= 900:
            return rate
    except Exception as exc:
        logger.debug("fx lookup failed: %s", exc)
    return 1380.0


def _safe_scrub(text: str) -> str:
    try:
        from services.legal_filter import safe_scrub
        scrubbed = safe_scrub(text, context="monthly_finance")
        return scrubbed or text
    except Exception:
        return text


def _safe_price(ticker: str) -> Optional[float]:
    try:
        from services.container import fetcher
        hist = fetcher.get_price_history(ticker, period="5d")
        if hist is None or "Close" not in hist or len(hist["Close"]) == 0:
            return None
        return float(hist["Close"].iloc[-1])
    except Exception as exc:
        logger.debug("price fetch failed for %s: %s", ticker, exc)
        return None


def _safe_dividends(ticker: str) -> list[dict[str, Any]]:
    try:
        from services.data import fmp as fmp_service
        rows = fmp_service.get_dividends(ticker) or []
    except Exception as exc:
        logger.debug("dividends lookup failed for %s: %s", ticker, exc)
        return []
    out: list[dict[str, Any]] = []
    for r in rows:
        try:
            ex_raw = r.get("date") or r.get("recordDate") or r.get("exDividendDate")
            if not ex_raw:
                continue
            ex_date = date.fromisoformat(str(ex_raw)[:10])
            amt = float(r.get("dividend") or r.get("adjDividend") or 0)
            out.append({"ticker": ticker, "ex_date": ex_date, "amount": amt})
        except Exception:
            logger.debug("silent-fallback: _safe_dividends", exc_info=True)
            continue
    return out


def _safe_earnings_calendar(ticker: str) -> Optional[date]:
    """Next earnings date for a ticker. Uses FMP's earnings calendar when
    available; returns None on any failure."""
    try:
        from services.data import fmp as fmp_service
        fn = getattr(fmp_service, "get_earnings_calendar", None)
        if fn is None:
            return None
        rows = fn(ticker) or []
        now = date.today()
        for r in rows:
            try:
                d = date.fromisoformat(str(r.get("date"))[:10])
                if d >= now:
                    return d
            except Exception:
                logger.debug("silent-fallback: _safe_earnings_calendar", exc_info=True)
                continue
    except Exception as exc:
        logger.debug("earnings calendar failed for %s: %s", ticker, exc)
    return None


# ── helpers ──────────────────────────────────────────────────────────────────

def _month_bounds(any_day: date) -> tuple[date, date]:
    start = any_day.replace(day=1)
    _, last = calendar.monthrange(any_day.year, any_day.month)
    end = date(any_day.year, any_day.month, last)
    return start, end


def _prev_month(any_day: date) -> date:
    return any_day.replace(day=1) - timedelta(days=1)


def _next_month(any_day: date) -> date:
    first = any_day.replace(day=1)
    return (first + timedelta(days=32)).replace(day=1)


def _month_label(any_day: date) -> str:
    return f"{any_day.year}-{any_day.month:02d}"


# ── cash & positions ────────────────────────────────────────────────────────

def _cash_position(user: User, fx: float) -> dict[str, Any]:
    """Normalise cash across USD/KRW and return both currencies + KRW total."""
    cash_usd = float(getattr(user, "available_capital", 0) or 0)
    cash_krw = float(getattr(user, "available_capital_krw", 0) or 0)
    total_krw = cash_usd * fx + cash_krw
    total_usd = total_krw / fx if fx > 0 else cash_usd
    return {
        "cash_usd":   round(cash_usd, 2),
        "cash_krw":   round(cash_krw, 0),
        "total_krw":  round(total_krw, 0),
        "total_usd":  round(total_usd, 2),
    }


def _positions_mv(positions: list[Position], fx: float) -> dict[str, Any]:
    """Market value of the book in both USD and KRW."""
    mv_usd = 0.0
    mv_krw = 0.0
    for p in positions:
        shares = float(p.shares or 0)
        if shares <= 0:
            continue
        price = _safe_price(p.ticker) or float(p.avg_cost or 0)
        if price <= 0:
            continue
        notional = shares * price
        if p.ticker.endswith((".KS", ".KQ")):
            mv_krw += notional
        else:
            mv_usd += notional
    total_krw = mv_usd * fx + mv_krw
    return {
        "mv_usd":   round(mv_usd, 2),
        "mv_krw":   round(mv_krw, 0),
        "total_krw": round(total_krw, 0),
    }


def _liquidity_ratio(cash: dict[str, Any], mv: dict[str, Any]
                     ) -> Optional[float]:
    """cash / (cash + MV). Higher = more liquid. None on div-by-zero."""
    num = cash["total_krw"]
    denom = num + mv["total_krw"]
    if denom <= 0:
        return None
    return round(num / denom, 4)


# ── cost & tax ──────────────────────────────────────────────────────────────

def _last_month_trades(user_id: int, period_start: date, period_end: date
                       ) -> list[TradeHistory]:
    ps = datetime.combine(period_start, datetime.min.time())
    pe = datetime.combine(period_end, datetime.max.time())
    try:
        return (
            TradeHistory.query
            .filter(TradeHistory.user_id == user_id,
                    TradeHistory.traded_at >= ps,
                    TradeHistory.traded_at <= pe)
            .all()
        )
    except Exception as exc:
        logger.debug("last-month trades query failed for user %s: %s",
                     user_id, exc)
        return []


def _cost_breakdown(trades: list[TradeHistory], fx: float
                    ) -> dict[str, Any]:
    """Estimate commissions / taxes / FX spread / slippage on last-month fills.

    All figures are rough heuristics clearly framed as estimates in the
    template — retail brokerages don't expose line-item fees uniformly,
    so this is the defensible upper-bound approach.
    """
    total_us_notional_usd = 0.0
    total_kr_notional_krw = 0.0
    us_sell_notional_usd = 0.0
    kr_sell_notional_krw = 0.0
    fx_notional_usd = 0.0   # notional that crosses USD/KRW boundary

    for t in trades:
        notional = abs(float(t.total_value or 0))
        if notional <= 0:
            continue
        is_kr = (t.ticker or "").endswith((".KS", ".KQ"))
        action = (t.action or "").upper()
        if is_kr:
            total_kr_notional_krw += notional
            if action == "SELL":
                kr_sell_notional_krw += notional
        else:
            total_us_notional_usd += notional
            if action == "SELL":
                us_sell_notional_usd += notional
            # Every USD fill we assume required an FX round trip at some
            # point (buy used KRW→USD; sell will eventually need USD→KRW).
            fx_notional_usd += notional

    us_comm_usd = total_us_notional_usd * (_US_COMMISSION_BPS / 10_000.0)
    kr_comm_krw = total_kr_notional_krw * (_KR_BROKERAGE_BPS / 10_000.0)
    kr_tax_krw = kr_sell_notional_krw * (_KR_TRANSACTION_TAX_BPS / 10_000.0)
    fx_cost_usd = fx_notional_usd * (_FX_SPREAD_BPS / 10_000.0)

    commissions_krw = us_comm_usd * fx + kr_comm_krw
    fx_spread_krw = fx_cost_usd * fx
    total_krw = commissions_krw + kr_tax_krw + fx_spread_krw

    return {
        "us_commission_usd":  round(us_comm_usd, 2),
        "kr_commission_krw":  round(kr_comm_krw, 0),
        "kr_transaction_tax_krw": round(kr_tax_krw, 0),
        "fx_spread_usd":      round(fx_cost_usd, 2),
        "commissions_krw":    round(commissions_krw, 0),
        "fx_spread_krw":      round(fx_spread_krw, 0),
        "total_krw":          round(total_krw, 0),
        "us_notional_usd":    round(total_us_notional_usd, 2),
        "kr_notional_krw":    round(total_kr_notional_krw, 0),
        "trade_count":        len(trades),
    }


def _tax_estimate(trades: list[TradeHistory], positions: list[Position],
                  fx: float) -> dict[str, Any]:
    """Rough tax drag: realised US gains × 22% + KR sell transaction tax
    + estimated KR dividend withholding on the current book.
    """
    realised_gain_usd = 0.0
    realised_gain_krw = 0.0
    for t in trades:
        if (t.action or "").upper() != "SELL":
            continue
        pnl = float(t.pnl or 0)
        if pnl <= 0:
            continue
        if (t.ticker or "").endswith((".KS", ".KQ")):
            realised_gain_krw += pnl
        else:
            realised_gain_usd += pnl

    us_capgains_krw = realised_gain_usd * fx * (_US_CAPITAL_GAINS_PCT / 100.0)

    # Forward-12m dividend withholding estimate on current book.
    est_div_krw = 0.0
    for p in positions:
        shares = float(p.shares or 0)
        if shares <= 0:
            continue
        divs = _safe_dividends(p.ticker)
        if not divs:
            continue
        # Sum any dividend with ex-date in the last 365d → proxy for forward
        cutoff = date.today() - timedelta(days=365)
        amt = sum(d["amount"] for d in divs if d["ex_date"] >= cutoff)
        gross = amt * shares
        if p.ticker.endswith((".KS", ".KQ")):
            est_div_krw += gross
        else:
            est_div_krw += gross * fx
    withholding_krw = est_div_krw * (_KR_DIVIDEND_WITHHOLDING_PCT / 100.0)

    total_krw = us_capgains_krw + withholding_krw
    return {
        "realised_us_gain_usd":     round(realised_gain_usd, 2),
        "realised_kr_gain_krw":     round(realised_gain_krw, 0),
        "us_capital_gains_krw":     round(us_capgains_krw, 0),
        "forward_12m_dividend_krw": round(est_div_krw, 0),
        "dividend_withholding_krw": round(withholding_krw, 0),
        "total_estimated_krw":      round(total_krw, 0),
    }


# ── runway ──────────────────────────────────────────────────────────────────

def _burn_rate(user_id: int, months_back: int = 3, fx: float = 1380.0
               ) -> Optional[float]:
    """Average monthly NET cash OUTFLOW (KRW) over last `months_back` months.

    Positive number = cash leaving the account on average. We approximate
    "outflow" as net-buy (buys − sells) because the system doesn't see
    deposits/withdrawals explicitly. Returns None if no trades.
    """
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30 * months_back)
    try:
        rows = (
            TradeHistory.query
            .filter(TradeHistory.user_id == user_id,
                    TradeHistory.traded_at >= cutoff)
            .all()
        )
    except Exception as exc:
        logger.debug("burn-rate query failed for user %s: %s", user_id, exc)
        return None
    if not rows:
        return None

    net_krw = 0.0
    for t in rows:
        notional = float(t.total_value or 0)
        if notional <= 0:
            continue
        is_kr = (t.ticker or "").endswith((".KS", ".KQ"))
        krw_notional = notional if is_kr else notional * fx
        if (t.action or "").upper() == "BUY":
            net_krw += krw_notional
        else:
            net_krw -= krw_notional

    # If net is negative (net seller), there's no burn — return 0 so runway
    # becomes "∞" in the template.
    avg = net_krw / months_back
    return round(max(avg, 0.0), 0)


def _runway_months(cash_krw: float, burn_krw_per_mo: Optional[float]
                   ) -> Optional[float]:
    if burn_krw_per_mo is None:
        return None
    if burn_krw_per_mo <= 0:
        return None
    if cash_krw <= 0:
        return 0.0
    return round(cash_krw / burn_krw_per_mo, 1)


# ── watch items ─────────────────────────────────────────────────────────────

def _watch_items(positions: list[Position], month_start: date, month_end: date
                 ) -> dict[str, Any]:
    """Next month's ex-dividend and earnings dates for held tickers."""
    ex_divs: list[dict[str, Any]] = []
    earnings: list[dict[str, Any]] = []
    for p in positions:
        # Ex-dividends within next month
        for d in _safe_dividends(p.ticker):
            if month_start <= d["ex_date"] <= month_end:
                ex_divs.append({
                    "ticker":  p.ticker,
                    "date":    d["ex_date"].isoformat(),
                    "amount":  d["amount"],
                })
        # Next earnings date
        ed = _safe_earnings_calendar(p.ticker)
        if ed and month_start <= ed <= month_end:
            earnings.append({"ticker": p.ticker, "date": ed.isoformat()})
    ex_divs.sort(key=lambda x: x["date"])
    earnings.sort(key=lambda x: x["date"])
    return {"ex_dividends": ex_divs, "earnings": earnings}


# ── data ─────────────────────────────────────────────────────────────────────

@dataclass
class MonthlyFinanceContext:
    user_id:           int
    user_name:         str
    month_label:       str          # prior month: "2026-03"
    period_start:      date
    period_end:        date
    next_month_label:  str          # "2026-04"
    generated_at:      datetime
    fx_rate:           float
    # P2 Cash
    cash:              dict[str, Any]
    positions_mv:      dict[str, Any]
    liquidity_ratio:   Optional[float]
    position_count:    int
    # P3 Runway
    burn_rate_krw:     Optional[float]
    runway_months:     Optional[float]
    # P4 Costs
    cost_breakdown:    dict[str, Any]
    # P5 Tax
    tax_estimate:      dict[str, Any]
    # P6 Watch
    watch:             dict[str, Any]
    disclaimer:        str
    # Wave 6 — colophon provenance scalars. Positions/trade lineage
    # only named when the user actually has an Alpaca connection (KIS
    # orders are disabled so KIS positions don't qualify here either —
    # resolver returns an empty phrase). Currency source likewise.
    positions_source:  Optional[str]
    currencies_source: Optional[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id":         self.user_id,
            "user_name":       self.user_name,
            "month_label":     self.month_label,
            "period_start":    self.period_start.isoformat(),
            "period_end":      self.period_end.isoformat(),
            "next_month_label": self.next_month_label,
            "generated_at":    self.generated_at.isoformat() + "Z",
            "fx_rate":         round(self.fx_rate, 2),
            "cash":            self.cash,
            "positions_mv":    self.positions_mv,
            "liquidity_ratio": self.liquidity_ratio,
            "position_count":  self.position_count,
            "burn_rate_krw":   self.burn_rate_krw,
            "runway_months":   self.runway_months,
            "cost_breakdown":  self.cost_breakdown,
            "tax_estimate":    self.tax_estimate,
            "watch":           self.watch,
            "disclaimer":      self.disclaimer,
            "positions_source":  self.positions_source,
            "currencies_source": self.currencies_source,
        }


# ── service ──────────────────────────────────────────────────────────────────

class MonthlyFinanceService:
    """Monthly Cash Runway + Cost/Tax + Watch items PDF. Premium only."""

    def generate_for_user(self, user_id: int,
                          as_of: date | None = None) -> dict[str, Any]:
        user = db.session.get(User, user_id)
        if not user:
            raise ValueError(f"user {user_id} not found")

        today = as_of or date.today()
        report_day = _prev_month(today)
        period_start, period_end = _month_bounds(report_day)
        next_day = today.replace(day=1)
        next_start, next_end = _month_bounds(next_day)

        positions = Position.query.filter_by(user_id=user_id).all()
        fx = _fx_rate()

        cash = _cash_position(user, fx)
        mv = _positions_mv(positions, fx)
        liq = _liquidity_ratio(cash, mv)

        burn = _burn_rate(user_id, months_back=3, fx=fx)
        runway = _runway_months(cash["total_krw"], burn)

        trades = _last_month_trades(user_id, period_start, period_end)
        costs = _cost_breakdown(trades, fx)
        taxes = _tax_estimate(trades, positions, fx)

        watch = _watch_items(positions, next_start, next_end)

        # Wave 6 — provenance scalars. Only name Alpaca for users with a
        # live Alpaca connection; leave blank otherwise so the template
        # elides the section rather than claiming Alpaca as theirs.
        try:
            from services.artifacts.data_source_resolver import _has_active_alpaca
            alpaca_on = _has_active_alpaca(user_id)
        except Exception as exc:
            logger.debug("monthly_finance alpaca check failed for user %s: %s",
                         user_id, exc)
            alpaca_on = False
        positions_source = (
            "Alpaca Broker API (read-only)." if alpaca_on else None
        )
        currencies_source = (
            "FX rate observation via Alpaca FX for KRW-denominated accounts."
            if alpaca_on else None
        )

        ctx = MonthlyFinanceContext(
            user_id=user_id,
            user_name=user.name or user.email.split("@")[0],
            month_label=_month_label(report_day),
            period_start=period_start,
            period_end=period_end,
            next_month_label=_month_label(next_day),
            generated_at=datetime.now(timezone.utc).replace(tzinfo=None),
            fx_rate=fx,
            cash=cash,
            positions_mv=mv,
            liquidity_ratio=liq,
            position_count=len(positions),
            burn_rate_krw=burn,
            runway_months=runway,
            cost_breakdown=costs,
            tax_estimate=taxes,
            watch=watch,
            disclaimer=_safe_scrub(
                "본 리포트는 이용자 본인의 거래/보유 데이터를 기반으로 한 참고용 "
                "집계이며, 투자자문·세무자문이 아닙니다. 수수료·세금·환전료 "
                "추정치는 업계 표준치에 기반한 근사값이며 실제 금액과 다를 수 있습니다."
            ),
            positions_source=positions_source,
            currencies_source=currencies_source,
        )
        return ctx.to_dict()

    # ── v3 design shape (CEO redesign 2026-04-30) ──────────────────────────

    def _to_v3_shape(self, data: dict[str, Any]) -> dict[str, Any]:
        """Map MonthlyFinanceContext (cash/cost/runway) onto v3 1-page Premium.

        Backend produces personal cash/cost statement; frontend tsx covers
        4-page CFO statement. v3 layout adapted to backend semantics with
        the critical KPIs surfaced.
        """
        cash = data.get("cash") or {}
        positions_mv = data.get("positions_mv") or {}
        cost_breakdown = data.get("cost_breakdown") or {}
        tax_estimate = data.get("tax_estimate") or {}
        liquidity_ratio = data.get("liquidity_ratio")
        runway_months = data.get("runway_months")

        def _money(v) -> str:
            try:
                n = float(v)
            except (TypeError, ValueError):
                return "—"
            an = abs(n)
            sign = "−" if n < 0 else ""
            if an >= 1_000_000:
                return f"{sign}${an/1_000_000:.2f}M"
            if an >= 1_000:
                return f"{sign}${an/1_000:.1f}k"
            return f"{sign}${an:,.0f}"

        try:
            nav_total = float(cash.get("total_usd") or 0) + float(positions_mv.get("total_usd") or 0)
        except (TypeError, ValueError):
            nav_total = 0.0
        try:
            cash_total = float(cash.get("total_usd") or 0)
        except (TypeError, ValueError):
            cash_total = 0
        try:
            burn_total = sum(
                float(cost_breakdown.get(k) or 0)
                for k in ("commission", "tx_tax", "cgt_est", "fx_spread", "slippage")
            )
        except (TypeError, ValueError):
            burn_total = 0

        cost_rows = []
        for label, key, note in [
            ("Commission", "commission", "거래 수수료"),
            ("Tax (Tx)", "tx_tax", "거래세"),
            ("Tax (CGT est)", "cgt_est", "양도세 추정"),
            ("FX Spread", "fx_spread", "환전 스프레드"),
            ("Slippage", "slippage", "체결가 차이"),
        ]:
            try:
                amt = float(cost_breakdown.get(key) or 0)
            except (TypeError, ValueError):
                amt = 0
            if amt or burn_total:
                pct_str = f"{(amt/burn_total)*100:.1f}%" if burn_total else "—"
                cost_rows.append({
                    "category": label,
                    "amount":   _money(amt) if amt else "—",
                    "pct":      pct_str,
                    "detail":   note,
                })

        tax_rows = []
        for label, key, note in [
            ("이번 달 양도세 추정", "cgt_estimate_month", "월간 누적"),
            ("연간 양도세 추정", "cgt_estimate_year", "연간 누적"),
            ("배당세 추정", "dividend_tax", "원천징수"),
        ]:
            try:
                amt_f = float(tax_estimate.get(key) or 0)
            except (TypeError, ValueError):
                amt_f = 0
            if amt_f:
                tax_rows.append({
                    "category": label,
                    "amount":   _money(amt_f),
                    "detail":   note,
                })

        cash_alloc = []
        if cash:
            try:
                usd = float(cash.get("usd") or 0)
                krw = float(cash.get("krw_usd_eq") or cash.get("krw") or 0)
            except (TypeError, ValueError):
                usd = krw = 0
            tot = usd + krw
            if tot > 0:
                cash_alloc = [
                    {"name": "USD", "pct": round((usd/tot)*100, 1),
                     "pct_display": f"{(usd/tot)*100:.1f}%",
                     "flat": (usd/tot)*100 < 35},
                    {"name": "KRW", "pct": round((krw/tot)*100, 1),
                     "pct_display": f"{(krw/tot)*100:.1f}%",
                     "flat": (krw/tot)*100 < 35},
                ]

        ml = data.get("month_label") or "—"
        return {
            "month_label": ml,
            "report_tag":  f"MF-{ml.replace(' ', '-')}",
            "nav":         {"value": _money(nav_total) if nav_total else "—",
                             "detail": "EOM 합산"},
            "cash":        {"value": _money(cash_total) if cash_total else "—",
                             "detail": "USD 환산"},
            "liquidity_ratio": {
                "value":  f"{liquidity_ratio:.2f}" if liquidity_ratio is not None else "—",
                "detail": "Cash / Burn",
            },
            "runway":      {"value": f"{runway_months:.1f}" if runway_months is not None else "—",
                             "detail": "현재 burn 기준"},
            "cost_rows":   cost_rows,
            "tax_rows":    tax_rows,
            "cash_alloc":  cash_alloc,
            "cfo_note":    None,
        }

    # ── render ──────────────────────────────────────────────────────────────

    def _resolve_persona(self, data: dict[str, Any]) -> str:
        """Same persona contract as weekly_memo / quarterly_self_report."""
        if "persona" in data and data["persona"]:
            try:
                from services.artifacts.persona_resolver import resolve_persona_from_code
                return resolve_persona_from_code(data["persona"])
            except Exception:
                return "balanced"
        user_id = data.get("user_id")
        if user_id is None:
            return "balanced"
        try:
            from services.artifacts.persona_resolver import (
                DEFAULT_PERSONA, resolve_persona,
            )
            from models import InvestmentProfile
            profile = InvestmentProfile.query.filter_by(user_id=user_id).first()
            return resolve_persona(profile) if profile else DEFAULT_PERSONA
        except Exception as exc:
            logger.debug("monthly_finance persona resolution failed: %s", exc)
            return "balanced"

    def render_pdf_html(self, data: dict[str, Any]) -> str:
        env = self._jinja_env()
        if env is None:
            return self._fallback_html(data)
        try:
            ctx = dict(data)
            from services.artifacts._name_enrich import enrich_v3_names
            ctx["v3"] = enrich_v3_names(self._to_v3_shape(data))
            ctx["persona"] = self._resolve_persona(data)
            tpl = env.get_template("monthly_finance.html")
            return tpl.render(**ctx)
        except Exception as exc:
            logger.warning("monthly_finance v3 render failed: %s", exc)
            return self._fallback_html(data)

    def render_html(self, data: dict[str, Any]) -> str:
        return self.render_pdf_html(data)

    def render_pdf(self, data: dict[str, Any]) -> Optional[bytes]:
        HTML = _try_import_weasyprint()
        if HTML is None:
            return None
        html_str = self.render_pdf_html(data)
        try:
            return HTML(string=html_str).write_pdf()
        except Exception as exc:  # pragma: no cover
            logger.error("WeasyPrint monthly_finance failed: %s", exc)
            return None

    def _jinja_env(self):
        Environment, FileSystemLoader, select_autoescape = _try_import_jinja()
        if Environment is None:
            return None
        try:
            return Environment(
                loader=FileSystemLoader(str(_TEMPLATE_DIR)),
                autoescape=select_autoescape(["html", "xml"]),
                trim_blocks=True,
                lstrip_blocks=True,
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("Jinja env build failed: %s", exc)
            return None

    def _fallback_html(self, data: dict[str, Any]) -> str:
        from html import escape
        cash = data.get("cash") or {}
        return f"""<!doctype html><html><body>
<h1>Monthly Finance — {escape(data.get('month_label',''))}</h1>
<p>{escape(data.get('user_name',''))}'s finance report</p>
<p>Cash (KRW): {cash.get('total_krw','—'):,} · Runway: {data.get('runway_months','—')} months</p>
<p><em>{escape(data.get('disclaimer',''))}</em></p>
</body></html>"""

    # ── send ────────────────────────────────────────────────────────────────

    def send_email(self, user: User, pdf_bytes: Optional[bytes],
                   html_body: str, month_label: str) -> bool:
        """Phase 7 — delegate to :class:`EmailSender`."""
        from services.email import EmailSender

        return EmailSender().send(
            user,
            subject=f"PivoxQuant Finance Report — {month_label}",
            html_body=html_body,
            from_env_var="WEEKLY_MEMO_FROM_EMAIL",
            from_default="reports@pivoxquant.com",
            pdf_bytes=pdf_bytes,
            pdf_filename=f"finance_{month_label}.pdf",
        )

    # ── persist + orchestrate ───────────────────────────────────────────────

    def _persist(self, user_id: int, data: dict[str, Any],
                 pdf_bytes: Optional[bytes], sent: bool) -> Artifact:
        title = f"Finance Report — {data['month_label']}"
        pdf_path: Optional[str] = None
        if pdf_bytes:
            try:
                base = _storage_dir() / str(user_id)
                base.mkdir(parents=True, exist_ok=True)
                path = base / f"{data['month_label']}.pdf"
                path.write_bytes(pdf_bytes)
                pdf_path = str(path)
            except Exception as exc:
                logger.warning("monthly_finance PDF write failed for user %s: %s",
                               user_id, exc)

        artefact = (
            Artifact.query
            .filter_by(user_id=user_id, type="monthly_finance", title=title)
            .first()
        )
        if artefact:
            artefact.data_json = data
            if pdf_path:
                artefact.pdf_path = pdf_path
            if sent and not artefact.sent_at:
                artefact.sent_at = datetime.now(timezone.utc).replace(tzinfo=None)
        else:
            artefact = Artifact(
                user_id=user_id,
                type="monthly_finance",
                title=title,
                data_json=data,
                pdf_path=pdf_path,
                sent_at=datetime.now(timezone.utc).replace(tzinfo=None) if sent else None,
            )
            db.session.add(artefact)
        db.session.commit()
        return artefact

    def run_for_user(self, user: User,
                     as_of: date | None = None,
                     *, send: bool = True) -> Optional[Artifact]:
        n_pos = Position.query.filter_by(user_id=user.id).count()
        n_cash = (
            float(getattr(user, "available_capital", 0) or 0)
            + float(getattr(user, "available_capital_krw", 0) or 0)
        )
        if n_pos == 0 and n_cash <= 0:
            logger.info("skipping monthly_finance for user %s — no book & no cash",
                        user.id)
            return None

        data = self.generate_for_user(user.id, as_of=as_of)
        pdf_bytes = self.render_pdf(data)
        html_body = self.render_html(data)

        sent = False
        if send:
            try:
                sent = self.send_email(user, pdf_bytes, html_body,
                                       data["month_label"])
            except Exception as exc:
                logger.error("monthly_finance send raised for user %s: %s",
                             user.id, exc)
                sent = False
        return self._persist(user.id, data, pdf_bytes, sent)

    def run_monthly(self, target_month: date | None = None) -> dict[str, Any]:
        """Cron — 1st of month 11:00 KST. Premium only."""
        from services.artifacts import iter_users_chunked

        today = target_month or date.today()

        users = (
            User.query
            .filter(User.subscription_tier.in_(list(_PAID_TIERS)))
            .all()
        )

        successes = failures = skipped = 0
        for user in iter_users_chunked(users, label="monthly_finance.monthly"):
            try:
                result = self.run_for_user(user, as_of=today)
                if result is None:
                    skipped += 1
                else:
                    successes += 1
            except Exception as exc:
                db.session.rollback()
                failures += 1
                logger.error("monthly_finance failed for user %s: %s",
                             user.id, exc)

        summary = {
            "month":     _month_label(_prev_month(today)),
            "attempted": len(users),
            "success":   successes,
            "failed":    failures,
            "skipped":   skipped,
        }
        logger.info("monthly_finance monthly run: %s", summary)
        return summary
