"""Weekly Investor Memo — McKinsey-style 5p PDF, emailed Sunday 08:00 KST.

Entry points
------------
    WeeklyMemoService().generate_for_user(user_id)  → data dict
    WeeklyMemoService().render_pdf(data)            → bytes
    WeeklyMemoService().render_html(data)           → str (email body)
    WeeklyMemoService().send_email(user, pdf, html) → bool
    WeeklyMemoService().run_weekly(target_date=None) → summary dict

Design principles
-----------------
1. Pro+ only. Free users are skipped silently; the scheduler loops over
   `subscription_tier in {"pro", "premium"}` and defers Free users to
   the upsell cta on the dashboard.
2. Idempotent. (user_id, "weekly_memo", title) is UNIQUE at the DB
   level — re-running the Sunday job updates the existing row.
3. Graceful degradation. Every upstream failure (FRED missing, price
   history 500, PDF render error) is caught and the affected section
   is simply omitted. The memo ships with whatever sections are
   available.
4. Compliance. Prose is descriptive — no "buy/sell/추천". We reuse
   `legal_filter.is_compliant` as the final filter before
   any AI-generated text is persisted.
6. Optional deps. WeasyPrint and SendGrid are imported lazily so tests
   that don't need PDF/email can run without the system libs. A memo
   with no PDF renderer installed still generates the data + HTML and
   is saved — just skips `pdf_path`.

Storage
-------
Generated PDFs are written to `<PROJECT_ROOT>/artifacts/weekly_memo/
<user_id>/<title>.pdf` so dev works out of the box. In production, set
`WEEKLY_MEMO_STORAGE_DIR` to an S3-fuse mount or similar. The email
attachment is the raw bytes (not a link) so delivery is independent of
storage backend.
"""
from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from extensions import db
from models import Artifact, Position, User
from services.legal_filter import safe_scrub, scrub_signal

logger = logging.getLogger(__name__)


# ── paths / config ───────────────────────────────────────────────────────────

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_DEFAULT_STORAGE_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "weekly_memo"

# Users on these tiers get the Sunday memo. "free" is excluded.
_PAID_TIERS = frozenset({"pro", "premium", "elite"})


def _storage_dir() -> Path:
    override = os.environ.get("WEEKLY_MEMO_STORAGE_DIR")
    d = Path(override) if override else _DEFAULT_STORAGE_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── lazy optional deps ───────────────────────────────────────────────────────

def _try_import_weasyprint():
    """Return the WeasyPrint HTML class, or None if unavailable.

    WeasyPrint requires native libs (pango, cairo) that aren't always
    installed in CI / lightweight dev containers. Falling back to None
    lets the rest of the pipeline run — PDF attachment is simply
    skipped and the email ships with the HTML body only.
    """
    try:
        from weasyprint import HTML  # type: ignore
        return HTML
    except Exception as exc:  # pragma: no cover — depends on env
        # DIAG 2026-04-29: INFO → WARNING (Railway 로그 가시성 ↑)
        logger.warning("WeasyPrint unavailable (%s); PDF generation will be skipped.", exc)
        return None


def _try_import_jinja():
    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape
        return Environment, FileSystemLoader, select_autoescape
    except Exception as exc:  # pragma: no cover
        logger.warning("Jinja2 unavailable (%s); template rendering will fail.", exc)
        return None, None, None


# ── data assembly ────────────────────────────────────────────────────────────

@dataclass
class MemoContext:
    """Everything a template needs. Any field may be falsy → template hides
    the matching section, so partial failures still render."""
    user_id:           int
    user_name:         str
    week_number:       int
    period_start:      date
    period_end:        date
    generated_at:      datetime
    weekly_return_pct: Optional[float]
    benchmark_pct:     Optional[float]
    alpha_pct:         Optional[float]
    sector_alloc:      dict[str, float]
    sector_changes:    list[dict[str, Any]]
    top_movers_up:     list[dict[str, Any]]
    top_movers_down:   list[dict[str, Any]]
    earnings_calendar: list[dict[str, Any]]
    macro_checklist:   list[dict[str, Any]]
    risk_notes:        list[str]
    risk_kpi:          dict[str, Any]
    data_sources:      list[str]
    disclaimer:        str

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id":           self.user_id,
            "user_name":         self.user_name,
            "week_number":       self.week_number,
            "period_start":      self.period_start.isoformat(),
            "period_end":        self.period_end.isoformat(),
            "generated_at":      self.generated_at.isoformat() + "Z",
            "weekly_return_pct": self.weekly_return_pct,
            "benchmark_pct":     self.benchmark_pct,
            "alpha_pct":         self.alpha_pct,
            "sector_alloc":      self.sector_alloc,
            "sector_changes":    self.sector_changes,
            "top_movers_up":     self.top_movers_up,
            "top_movers_down":   self.top_movers_down,
            "earnings_calendar": self.earnings_calendar,
            "macro_checklist":   self.macro_checklist,
            "risk_notes":        self.risk_notes,
            "risk_kpi":          self.risk_kpi,
            "data_sources":      self.data_sources,
            "disclaimer":        self.disclaimer,
        }


# ── AI budget (module-level) ─────────────────────────────────────────────────
# Daily-counter pattern keeps us under Claude Haiku budget even when a large
# Pro cohort triggers the Sunday run at once.
_WEEKLY_AI_LIMIT = 200
_ai_usage = {"day": None, "count": 0}
_ai_lock = threading.Lock()


def _ai_budget_available() -> bool:
    today_utc = datetime.now(timezone.utc).replace(tzinfo=None).date()
    with _ai_lock:
        if _ai_usage["day"] != today_utc:
            _ai_usage["day"] = today_utc
            _ai_usage["count"] = 0
        return _ai_usage["count"] < _WEEKLY_AI_LIMIT


def _ai_budget_consume() -> None:
    today_utc = datetime.now(timezone.utc).replace(tzinfo=None).date()
    with _ai_lock:
        if _ai_usage["day"] != today_utc:
            _ai_usage["day"] = today_utc
            _ai_usage["count"] = 0
        _ai_usage["count"] += 1


# ── helpers ──────────────────────────────────────────────────────────────────

def _iso_week_number(d: date) -> int:
    """Week 1 = first week that contains a Thursday (ISO 8601).
    Used in titles so two Sundays don't collide on the unique index."""
    return d.isocalendar()[1]


def _safe_fetch_price_history(ticker: str, period: str = "1mo"):
    """Thin wrapper around services.container.fetcher — never raises."""
    try:
        from services.container import fetcher  # late import → test isolation
        return fetcher.get_price_history(ticker, period=period)
    except Exception as exc:
        logger.debug("price history fetch failed for %s: %s", ticker, exc)
        return None


def _weekly_return_for_ticker(ticker: str) -> Optional[float]:
    """% return over the last 7 trading days. None if insufficient data.

    Uses the last ≥5 closes from `1mo` history (handles holidays).
    """
    hist = _safe_fetch_price_history(ticker, "1mo")
    if hist is None:
        return None
    try:
        closes = hist["Close"] if "Close" in hist else None
        if closes is None or len(closes) < 5:
            return None
        tail = closes.tail(6)  # 5 trading days ~ 1 week
        first = float(tail.iloc[0])
        last = float(tail.iloc[-1])
        if first <= 0:
            return None
        return round((last / first - 1) * 100, 2)
    except Exception as exc:
        logger.debug("weekly return calc failed for %s: %s", ticker, exc)
        return None


def _position_snapshot(pos: Position) -> dict[str, Any]:
    """Hydrate a Position into a dict the template can iterate over."""
    weekly = _weekly_return_for_ticker(pos.ticker)
    return {
        "ticker":    pos.ticker,
        "shares":    float(pos.shares or 0),
        "avg_cost":  float(pos.avg_cost or 0),
        "weekly_return_pct": weekly,
    }


def _sector_for_ticker(ticker: str) -> str:
    """Best-effort sector lookup. Falls back to 'Unknown' on any error.

    Reads from SignalCache first (already populated by the 3-minute
    refresh job) and only hits the live fetcher as a last resort.
    """
    try:
        from models import SignalCache
        import json
        row = db.session.get(SignalCache, ticker)
        if row and row.data_json:
            try:
                payload = json.loads(row.data_json)
                sector = payload.get("sector")
                if sector:
                    return str(sector)
            except Exception:
                logger.debug("silent-fallback: _sector_for_ticker", exc_info=True)
                pass
    except Exception:
        logger.debug("silent-fallback: _sector_for_ticker", exc_info=True)
        pass
    return "Unknown"


def _sector_allocation(positions: list[Position]) -> dict[str, float]:
    """Percent of portfolio market-value per GICS sector.

    Uses avg_cost × shares as a proxy when live price is unavailable.
    Returns empty dict if total_mv == 0.
    """
    alloc: dict[str, float] = {}
    total = 0.0
    for p in positions:
        mv = float(p.shares or 0) * float(p.avg_cost or 0)
        total += mv
        sector = _sector_for_ticker(p.ticker)
        alloc[sector] = alloc.get(sector, 0.0) + mv
    if total <= 0:
        return {}
    return {k: round(v / total * 100, 1) for k, v in
            sorted(alloc.items(), key=lambda x: -x[1])}


def _sector_changes(current: dict[str, float], previous: dict[str, float]
                    ) -> list[dict[str, Any]]:
    """Per-sector delta (percentage points) vs previous week."""
    sectors = set(current.keys()) | set(previous.keys())
    out: list[dict[str, Any]] = []
    for s in sectors:
        c = current.get(s, 0.0)
        p = previous.get(s, 0.0)
        out.append({"sector": s, "current": c, "previous": p,
                    "delta_pp": round(c - p, 1)})
    out.sort(key=lambda x: -abs(x["delta_pp"]))
    return out


def _top_movers(positions: list[Position], k: int = 3
                ) -> tuple[list[dict], list[dict]]:
    """Top-k gainers and losers of the week by %."""
    enriched: list[dict[str, Any]] = []
    for p in positions:
        wr = _weekly_return_for_ticker(p.ticker)
        if wr is None:
            continue
        enriched.append({"ticker": p.ticker, "weekly_return_pct": wr})
    if not enriched:
        return [], []
    enriched.sort(key=lambda x: -x["weekly_return_pct"])
    up = [e for e in enriched if e["weekly_return_pct"] > 0][:k]
    down = [e for e in reversed(enriched) if e["weekly_return_pct"] < 0][:k]
    return up, down


def _next_week_earnings(positions: list[Position]) -> list[dict[str, Any]]:
    """FMP earnings calendar for the next 7 days, filtered to held tickers."""
    if not positions:
        return []
    try:
        from services.data import fmp as fmp  # type: ignore
    except Exception:
        return []

    today = date.today()
    end = today + timedelta(days=7)
    events: list[dict[str, Any]] = []
    for p in positions[:15]:  # protect FMP budget
        try:
            rows = fmp.get_earnings_calendar(ticker=p.ticker, days_ahead=7) or []
        except Exception as exc:
            logger.debug("earnings calendar failed for %s: %s", p.ticker, exc)
            continue
        for r in rows:
            if not isinstance(r, dict):
                continue
            d_str = str(r.get("date", ""))[:10]
            try:
                d = date.fromisoformat(d_str)
            except ValueError:
                logger.debug("silent-fallback: _next_week_earnings", exc_info=True)
                continue
            if not (today <= d <= end):
                continue
            events.append({
                "ticker": p.ticker,
                "date":   d_str,
                "time":   r.get("time") or "",
            })
    # Sort chronologically
    events.sort(key=lambda e: (e["date"], e["ticker"]))
    return events[:15]


def _macro_checklist() -> list[dict[str, Any]]:
    """FRED-based macro snapshot as a checklist. Empty if FRED unavailable."""
    try:
        from services.data.fred_service import get_fred_service
        svc = get_fred_service()
    except Exception:
        return []
    if not getattr(svc, "available", False):
        return []
    try:
        snap = svc.get_macro_snapshot()
    except Exception as exc:
        logger.debug("FRED snapshot failed: %s", exc)
        return []
    indicators = (snap or {}).get("indicators") or {}
    checklist: list[dict[str, Any]] = []
    # Only bubble up the headline series — full catalog would be visual clutter.
    priority = ["FEDFUNDS", "DGS10", "T10Y2Y", "CPIAUCSL",
                "UNRATE", "VIXCLS", "DEXKOUS"]
    for sid in priority:
        entry = indicators.get(sid)
        if not entry:
            continue
        checklist.append({
            "series_id": sid,
            "label":     entry.get("label", sid),
            "value":     entry.get("value"),
            "units":     entry.get("units", ""),
            "date":      entry.get("date"),
            "pct_change": entry.get("pct_change"),
        })
    return checklist


# ── portfolio value / YTD helpers (v3 PDF mapping) ───────────────────────────

def _ticker_last_price(ticker: str) -> Optional[float]:
    """Best-effort last-trade price. Re-uses the FMP cache + Alpaca fallback.

    Order:
      1. fmp_service.get_quote() — already has 30s TTL + sanity check
      2. last close from price history
      3. None → caller treats as missing-price (uses avg_cost proxy)
    """
    try:
        from services.data import fmp as fmp  # type: ignore
        q = fmp.get_quote(ticker)
        if isinstance(q, dict):
            for key in ("price", "last", "close", "previousClose"):
                v = q.get(key)
                if v is not None:
                    try:
                        fv = float(v)
                        if fv > 0:
                            return fv
                    except (TypeError, ValueError):
                        logger.debug("silent-fallback: _ticker_last_price", exc_info=True)
                        continue
    except Exception as exc:
        logger.debug("get_quote failed for %s: %s", ticker, exc)

    hist = _safe_fetch_price_history(ticker, "1mo")
    if hist is not None:
        try:
            closes = hist["Close"] if "Close" in hist else None
            if closes is not None and len(closes) >= 1:
                return float(closes.iloc[-1])
        except Exception as exc:
            logger.debug("history close fallback failed for %s: %s", ticker, exc)
    return None


def _is_kr_ticker(ticker: str) -> bool:
    """Mirror of fmp_service._is_us_ticker — KR tickers end in .KS / .KQ."""
    if not isinstance(ticker, str):
        return False
    return ticker.endswith(".KS") or ticker.endswith(".KQ")


def _portfolio_value_usd(positions: list[Position]) -> Optional[float]:
    """Sum (last_price × shares) across positions, USD-normalised.

    KR positions use services.fx_service.get_rate() to convert to USD. If
    last_price is unavailable we fall back to avg_cost so the headline still
    reflects scale (clearly labelled in template metadata if needed).

    Returns None when total is zero or positions list is empty.
    """
    if not positions:
        return None
    try:
        from services import fx_service
        krw_per_usd = fx_service.get_rate() or 1300.0
    except Exception:
        krw_per_usd = 1300.0
    total_usd = 0.0
    for p in positions:
        try:
            shares = float(p.shares or 0)
            if shares <= 0:
                continue
            price = _ticker_last_price(p.ticker) or float(p.avg_cost or 0)
            if price <= 0:
                continue
            mv = price * shares
            if _is_kr_ticker(p.ticker) and krw_per_usd > 0:
                mv = mv / krw_per_usd
            total_usd += mv
        except Exception as exc:
            logger.debug("position value calc failed for %s: %s", p.ticker, exc)
            continue
    return round(total_usd, 2) if total_usd > 0 else None


def _ytd_return_for_ticker(ticker: str) -> Optional[float]:
    """% return from first trading day of the calendar year → latest close.

    Pulls 1y history (covers the full YTD window even early in the year)
    and takes the first close >= Jan 1 vs the most-recent close.
    """
    hist = _safe_fetch_price_history(ticker, "1y")
    if hist is None:
        return None
    try:
        closes = hist["Close"] if "Close" in hist else None
        if closes is None or len(closes) < 2:
            return None
        year_start = date(date.today().year, 1, 1)
        # Index might be DatetimeIndex or RangeIndex — handle both.
        idx = closes.index
        try:
            mask = [d.date() >= year_start for d in idx]
            ytd_closes = closes[mask]
        except Exception:
            # RangeIndex — best-effort: take last ~252 bars (1y) and use first.
            ytd_closes = closes.tail(252)
        if len(ytd_closes) < 2:
            return None
        first = float(ytd_closes.iloc[0])
        last = float(ytd_closes.iloc[-1])
        if first <= 0:
            return None
        return round((last / first - 1) * 100, 2)
    except Exception as exc:
        logger.debug("YTD return calc failed for %s: %s", ticker, exc)
        return None


def _portfolio_ytd_return(positions: list[Position]) -> Optional[float]:
    """Equal-weighted YTD return across positions with available history.

    Equal-weight is consistent with the weekly_return_pct calc in
    generate_for_user() — keeps the two headline numbers comparable.
    """
    if not positions:
        return None
    rets: list[float] = []
    for p in positions:
        r = _ytd_return_for_ticker(p.ticker)
        if r is not None:
            rets.append(r)
    if not rets:
        return None
    return round(sum(rets) / len(rets), 2)


def _portfolio_sortino(positions: list[Position]) -> Optional[float]:
    """Annualised Sortino ratio for the equal-weighted equity curve.

    Re-uses risk_models.SortinoByPosition for consistency with the Risk
    Dashboard. Returns None on insufficient data — caller hides the field.
    """
    try:
        import numpy as np  # type: ignore  # noqa: F401  # gate for numpy presence
    except Exception:
        logger.debug("silent-fallback: _portfolio_sortino", exc_info=True)
        return None
    built = _build_returns_matrix(positions, lookback_days=90)
    if built is None:
        return None
    returns_matrix, weights, _tickers, _ohlc, _pv = built
    try:
        port_returns = (returns_matrix @ weights).tolist()
        from services.quant.risk_metrics import SortinoByPosition
        out = SortinoByPosition.calculate(port_returns)
        sr = out.get("sortino")
        if sr is None:
            return None
        return round(float(sr), 2)
    except Exception as exc:
        logger.debug("Sortino calc failed: %s", exc)
        return None


def _risk_notes(positions: list[Position],
                sector_alloc: dict[str, float],
                top_down: list[dict]) -> list[str]:
    """Rule-based descriptive risk notes — never action advice.

    Passes output through legal_filter.is_compliant regex before returning.
    """
    try:
        from services.legal_filter import is_compliant
    except Exception:
        def is_compliant(_: str) -> bool: return True  # pragma: no cover

    notes: list[str] = []

    # Concentration
    if sector_alloc:
        top_sector, top_pct = next(iter(sector_alloc.items()))
        if top_pct >= 40:
            notes.append(f"{top_sector} 섹터 비중 {top_pct:.0f}%로 집중도 높음 관찰")

    # Drawdown cluster
    if len(top_down) >= 2:
        tickers = ", ".join(d["ticker"] for d in top_down[:2])
        worst = top_down[-1]["weekly_return_pct"] if top_down else 0
        notes.append(f"{tickers} 주간 하락, 최저 {worst:.1f}% 기록")

    # Position count
    if len(positions) < 5:
        notes.append(f"보유 종목 {len(positions)}개 — 분산 부족 구간 관찰")

    return [n for n in notes if is_compliant(n)]


# ── Risk KPI helpers (Risk Dashboard — Part III) ─────────────────────────────

def _position_price_history(ticker: str, period: str = "6mo"):
    """Fetch full OHLC price history for a ticker. Returns pandas.DataFrame or None.

    We re-use the project's data fetcher container so KR/US routing is free.
    """
    try:
        from services.container import fetcher
        return fetcher.get_price_history(ticker, period=period)
    except Exception as exc:
        logger.debug("price history (6mo) fetch failed for %s: %s", ticker, exc)
        return None


def _build_returns_matrix(positions: list["Position"],
                          lookback_days: int = 90):
    """Assemble an (n_obs, n_assets) simple-return matrix + weights.

    Returns `(returns_matrix, weights, tickers, ohlc_map, portfolio_values)`
    or `None` when any precondition fails. All inputs are numpy arrays.

    - rows are aligned across tickers by trimming to the shortest common tail
    - weights are market-value proxies (shares × avg_cost), normalised to 1
    - `portfolio_values` is the equal-weighted cumulative equity curve used
      for the drawdown / trough calculations
    """
    try:
        import numpy as np  # type: ignore
    except Exception:
        logger.debug("silent-fallback: _build_returns_matrix", exc_info=True)
        return None

    if not positions:
        return None

    tickers: list[str] = []
    weights_raw: list[float] = []
    closes_map: dict[str, list[float]] = {}
    ohlc_map: dict[str, dict[str, list[float]]] = {}

    for p in positions:
        hist = _position_price_history(p.ticker, "6mo")
        if hist is None:
            continue
        try:
            closes = hist["Close"] if "Close" in hist else None
            if closes is None or len(closes) < lookback_days + 1:
                # Still accept what we have if it's at least 30 bars — short
                # lookbacks still give a KPI snapshot, just less stable.
                if closes is None or len(closes) < 30:
                    continue
            opens = hist["Open"] if "Open" in hist else None
            highs = hist["High"] if "High" in hist else None
            lows = hist["Low"] if "Low" in hist else None

            closes_list = [float(x) for x in closes.tail(lookback_days + 1)]
            closes_map[p.ticker] = closes_list
            if opens is not None and highs is not None and lows is not None:
                ohlc_map[p.ticker] = {
                    "open":  [float(x) for x in opens.tail(lookback_days + 1)],
                    "high":  [float(x) for x in highs.tail(lookback_days + 1)],
                    "low":   [float(x) for x in lows.tail(lookback_days + 1)],
                    "close": closes_list,
                }
            tickers.append(p.ticker)
            weights_raw.append(float(p.shares or 0) * float(p.avg_cost or 0))
        except Exception as exc:
            logger.debug("price-history parse failed for %s: %s", p.ticker, exc)
            continue

    if len(tickers) < 1:
        return None
    total_w = sum(weights_raw)
    if total_w <= 0:
        return None

    # Align to the shortest common tail so every column has the same length.
    shortest = min(len(closes_map[t]) for t in tickers)
    if shortest < 21:  # need at least 20 returns → 21 closes
        return None

    closes_matrix = np.array(
        [closes_map[t][-shortest:] for t in tickers], dtype=np.float64
    )  # shape: (n_assets, n_obs_closes)
    # Simple returns, aligned across tickers
    returns_matrix = np.diff(closes_matrix, axis=1) / closes_matrix[:, :-1]
    returns_matrix = returns_matrix.T  # (n_obs, n_assets)

    weights = np.array(weights_raw, dtype=np.float64) / total_w

    # Equal-weighted equity curve using portfolio returns (for drawdown).
    port_returns = returns_matrix @ weights
    portfolio_values = np.cumprod(1.0 + port_returns) * 100.0  # arbitrary base

    return returns_matrix, weights, tickers, ohlc_map, portfolio_values


def _risk_kpi(positions: list["Position"]) -> dict[str, Any]:
    """Compute Risk Dashboard KPIs using risk_models.py.

    Returns a dict with as many of the following keys as we can compute:
        var_1d_pct, es_1d_pct, mdd_pct, tail_ratio,
        trough_week, recovered_week, as_of, method_label, n_positions,
        window_days

    Returns `{}` on insufficient data — the template hides the section.
    Partial-success is allowed; individual template fields default safely.
    """
    try:
        import numpy as np  # type: ignore
    except Exception as exc:
        logger.debug("numpy unavailable for risk_kpi: %s", exc)
        return {}

    built = _build_returns_matrix(positions, lookback_days=90)
    if built is None:
        return {}

    returns_matrix, weights, tickers, ohlc_map, portfolio_values = built
    n_obs = returns_matrix.shape[0]

    kpi: dict[str, Any] = {
        "as_of": datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z",
        "method_label": "Historical simulation · 90d",
        "n_positions": len(tickers),
        "window_days": int(n_obs),
    }

    # 1. VaR + ES (Component ES returns both).
    try:
        from services.quant.risk_metrics import ComponentES
        es_out = ComponentES.decompose(returns_matrix, weights, alpha=0.05)
        if es_out.get("portfolio_var") is not None:
            kpi["var_1d_pct"] = round(float(es_out["portfolio_var"]), 2)
        if es_out.get("portfolio_es") is not None:
            kpi["es_1d_pct"] = round(float(es_out["portfolio_es"]), 2)
    except Exception as exc:
        logger.debug("ComponentES failed: %s", exc)

    # 2. Max Drawdown + trough / recovery weeks.
    try:
        from services.quant.risk_metrics import ConditionalDrawdown
        dd_out = ConditionalDrawdown.calculate(portfolio_values, alpha=0.05)
        if dd_out.get("max_dd") is not None:
            kpi["mdd_pct"] = round(float(dd_out["max_dd"]), 2)

        # Trough/recovered identification — on the equity curve we built.
        pv = np.asarray(portfolio_values, dtype=float)
        if pv.size >= 5:
            peak = np.maximum.accumulate(pv)
            dd = (pv - peak) / peak
            trough_idx = int(np.argmin(dd))
            # Convert index (days, newest at end) to W-X label.
            days_from_end_trough = int((pv.size - 1) - trough_idx)
            week_trough = max(1, (days_from_end_trough // 5) + 1)
            kpi["trough_week"] = f"W-{week_trough}"

            # "Recovered" = first bar after trough whose value ≥ peak-at-trough.
            target = peak[trough_idx]
            recovered_idx = None
            for i in range(trough_idx + 1, pv.size):
                if pv[i] >= target:
                    recovered_idx = i
                    break
            if recovered_idx is not None:
                days_from_end_rec = int((pv.size - 1) - recovered_idx)
                week_rec = max(1, (days_from_end_rec // 5) + 1)
                kpi["recovered_week"] = f"W-{week_rec}"
            else:
                # Still underwater at the end of the window.
                kpi["recovered_week"] = "ongoing"
    except Exception as exc:
        logger.debug("ConditionalDrawdown failed: %s", exc)

    # 3. Tail Ratio — on portfolio returns.
    try:
        from services.quant.risk_metrics import TailRatio
        port_returns = returns_matrix @ weights
        tr_out = TailRatio.calculate(port_returns)
        if tr_out.get("tail_ratio") is not None:
            kpi["tail_ratio"] = round(float(tr_out["tail_ratio"]), 2)
    except Exception as exc:
        logger.debug("TailRatio failed: %s", exc)

    # 4. GKYZ volatility — portfolio-weighted, only if every held ticker has OHLC.
    try:
        from services.quant.risk_metrics import GKYZVolatility
        gkyz_parts: list[tuple[float, float]] = []
        for t, w in zip(tickers, weights):
            ohlc = ohlc_map.get(t)
            if not ohlc:
                continue
            if (len(ohlc["close"]) < 21 or len(ohlc["open"]) < 21
                    or len(ohlc["high"]) < 21 or len(ohlc["low"]) < 21):
                continue
            r = GKYZVolatility.estimate(
                ohlc["open"], ohlc["high"], ohlc["low"], ohlc["close"],
                window=20,
            )
            vg = r.get("vol_gkyz")
            if vg is not None:
                gkyz_parts.append((float(w), float(vg)))
        if gkyz_parts:
            total_w = sum(w for w, _ in gkyz_parts)
            if total_w > 0:
                vol = sum(w * v for w, v in gkyz_parts) / total_w
                kpi["gkyz_vol_pct"] = round(vol, 2)
                kpi["method_label"] = "GKYZ · Historical simulation · 90d"
    except Exception as exc:
        logger.debug("GKYZVolatility failed: %s", exc)

    # Require at least one real KPI — an empty kpi dict hides the section.
    headline_fields = ("var_1d_pct", "es_1d_pct", "mdd_pct", "tail_ratio")
    if not any(k in kpi for k in headline_fields):
        return {}

    return kpi


# ── The service ──────────────────────────────────────────────────────────────

class WeeklyMemoService:
    """Coordinates data assembly, PDF rendering, email dispatch, persistence."""

    # ── data ────────────────────────────────────────────────────────────────

    def generate_for_user(self, user_id: int,
                          target_date: date | None = None) -> dict[str, Any]:
        """Assemble the memo payload for one user.

        Returns a dict shaped like `MemoContext.to_dict()`. Partial data
        is fine — missing sections simply come back empty, and the
        renderer hides them.
        """
        user = db.session.get(User, user_id)
        if not user:
            raise ValueError(f"user {user_id} not found")

        target_date = target_date or date.today()
        period_end = target_date
        period_start = target_date - timedelta(days=7)

        positions = Position.query.filter_by(user_id=user_id).all()

        sector_alloc = _sector_allocation(positions) if positions else {}
        top_up, top_down = _top_movers(positions) if positions else ([], [])

        # Previous week snapshot lives in the last memo row, if we have one.
        prev_alloc = self._previous_sector_alloc(user_id) or {}
        sector_changes = _sector_changes(sector_alloc, prev_alloc) if sector_alloc else []

        # Portfolio-level weekly return — equal-weight mean of tickers with data.
        rets = [e["weekly_return_pct"] for e in (top_up + top_down)]
        # Include middle performers too (those not in top/bottom) for fairness.
        for p in positions:
            wr = _weekly_return_for_ticker(p.ticker)
            if wr is not None and wr not in rets:
                rets.append(wr)
        weekly_return = round(sum(rets) / len(rets), 2) if rets else None

        benchmark = self._benchmark_weekly_return()
        alpha = None
        if weekly_return is not None and benchmark is not None:
            alpha = round(weekly_return - benchmark, 2)

        earnings = _next_week_earnings(positions)
        macro = _macro_checklist()
        risk = _risk_notes(positions, sector_alloc, top_down)
        try:
            risk_kpi = _risk_kpi(positions)
        except Exception as exc:
            logger.warning("risk_kpi computation failed for user %s: %s",
                           user_id, exc)
            risk_kpi = {}

        # Data-source provenance — Wave 5. `resolve_user_data_sources` never
        # raises and never invents a broker claim, so an empty result is
        # a trustworthy signal to the template ("say nothing" rather than
        # "claim Alpaca"). The weekly memo is descriptive of market-level
        # and broker-reported positions — no journal entries feed it.
        try:
            from services.artifacts.data_source_resolver import (
                resolve_user_data_sources,
            )
            data_sources = resolve_user_data_sources(user_id)
        except Exception as exc:
            logger.debug("data_source resolve failed for user %s: %s",
                         user_id, exc)
            data_sources = []

        ctx = MemoContext(
            user_id=user_id,
            user_name=user.name or user.email.split("@")[0],
            week_number=_iso_week_number(target_date),
            period_start=period_start,
            period_end=period_end,
            generated_at=datetime.now(timezone.utc).replace(tzinfo=None),
            weekly_return_pct=weekly_return,
            benchmark_pct=benchmark,
            alpha_pct=alpha,
            sector_alloc=sector_alloc,
            sector_changes=sector_changes,
            top_movers_up=top_up,
            top_movers_down=top_down,
            earnings_calendar=earnings,
            macro_checklist=macro,
            risk_notes=risk,
            risk_kpi=risk_kpi,
            data_sources=data_sources,
            disclaimer=("정보 제공 목적이며 투자 권유가 아닙니다. 투자 판단은 본인 책임입니다. / "
                        "Information only, not investment advice. Decisions are your own."),
        )
        # Legal scrub at user-facing boundary — risk_notes free-text and any
        # AI-derived prose. scrub_signal handles known free-text fields;
        # risk_notes (list[str]) is scrubbed item-by-item below.
        data = scrub_signal(ctx.to_dict())
        if isinstance(data.get("risk_notes"), list):
            data["risk_notes"] = [
                safe_scrub(n, context="weekly_memo.risk_notes") for n in data["risk_notes"]
            ]
        return data

    def _previous_sector_alloc(self, user_id: int) -> dict[str, float]:
        """Pull the most recent memo row's sector_alloc (if any)."""
        try:
            prev: Artifact | None = (
                Artifact.query
                .filter_by(user_id=user_id, type="weekly_memo")
                .order_by(Artifact.created_at.desc())
                .first()
            )
        except Exception:
            return {}
        if not prev or not prev.data_json:
            return {}
        raw = (prev.data_json or {}).get("sector_alloc") or {}
        try:
            return {k: float(v) for k, v in raw.items()}
        except Exception:
            return {}

    def _benchmark_weekly_return(self) -> Optional[float]:
        """S&P 500 (or KOSPI as fallback) weekly % — benchmark for alpha."""
        for ticker in ("SPY", "^GSPC"):
            wr = _weekly_return_for_ticker(ticker)
            if wr is not None:
                return wr
        return None

    # ── render ──────────────────────────────────────────────────────────────

    def render_html(self, data: dict[str, Any]) -> str:
        """Render the email body HTML (lightweight, inline-safe)."""
        env = self._jinja_env()
        if env is None:
            return self._fallback_html(data, email=True)
        try:
            tpl = env.get_template("weekly_memo_email.html")
            return tpl.render(**self._with_persona(data))
        except Exception as exc:
            logger.warning("email template render failed: %s", exc)
            return self._fallback_html(data, email=True)

    def render_pdf_html(self, data: dict[str, Any]) -> str:
        """Render the 1-page Free Weekly Memo PDF HTML (CEO design v3)."""
        env = self._jinja_env()
        if env is None:
            return self._fallback_html(data, email=False)
        try:
            tpl = env.get_template("weekly_memo.html")
            ctx = self._with_persona(data)
            from services.artifacts._name_enrich import enrich_v3_names
            ctx["v3"] = enrich_v3_names(self._to_v3_shape(data))
            return tpl.render(**ctx)
        except Exception as exc:
            logger.warning("pdf template render failed: %s", exc)
            return self._fallback_html(data, email=False)

    def _with_persona(self, data: dict[str, Any]) -> dict[str, Any]:
        """Inject `persona` field into the render context.

        Resolves from the user's `InvestmentProfile` when available; falls
        back to the default persona otherwise. Never raises — rendering
        must stay resilient to missing profile rows.
        """
        ctx = dict(data)
        if "persona" in ctx:
            # Already supplied by caller — validate and pass through.
            from services.artifacts.persona_resolver import (
                resolve_persona_from_code,
            )
            ctx["persona"] = resolve_persona_from_code(ctx.get("persona"))
            return ctx
        try:
            from services.artifacts.persona_resolver import (
                DEFAULT_PERSONA, resolve_persona,
            )
            user_id = ctx.get("user_id")
            profile = None
            if user_id is not None:
                try:
                    from models import InvestmentProfile
                    profile = (
                        InvestmentProfile.query
                        .filter_by(user_id=user_id)
                        .first()
                    )
                except Exception:
                    profile = None
            ctx["persona"] = resolve_persona(profile) if profile else DEFAULT_PERSONA
        except Exception as exc:
            logger.debug("persona resolution failed: %s", exc)
            ctx["persona"] = "balanced"
        return ctx

    # ── v3 shape mapping (CEO design 2026-04-29) ────────────────────────────

    def _to_v3_shape(self, data: dict[str, Any]) -> dict[str, Any]:
        """Map generate_for_user() result → the 1-page Free Weekly Memo v3
        data shape consumed by services/artifacts/templates/weekly_memo.html.

        Source of truth for the design:
          frontend/src/components/reports/templates/weekly-memo.tsx
          (interface WeeklyMemoData, 2026-04-29).

        Mapping summary
        ---------------
          as_of              ← period_end (str ISO date)
          week_tag           ← "WK-{year}-{week_number}"
          portfolio_return   ← formatted weekly_return_pct, e.g. "+2.4%"
          benchmark_return   ← formatted "vs S&P {benchmark_pct}"
          portfolio_value    ← positions × last_price, USD-normalised ($X,XXX)
          portfolio_delta    ← weekly_return_pct × portfolio_value approx
          ytd_return         ← equal-weighted YTD returns across positions
          ytd_detail         ← "Sortino X.XX" via risk_models.SortinoByPosition
          three_checks       ← AI-generated 3 weekly observations
          trajectory         ← daily-return path (rebuilt from weekly_return_pct)
          decision           ← AI-generated next-week single observation
          memo_to_self       ← AI-generated next-week review notes

        AI generation runs in a single Claude Haiku call (cost-controlled —
        ~1 call per Pro user per Sunday). Every output is run through
        legal_filter.safe_scrub + detect_prohibited; on filter rejection or
        any exception the field falls back to a neutral placeholder.

        Every placeholder is descriptive — no buy/sell/추천 verbs (자본시장법).
        """
        # ── headline returns ────────────────────────────────────────────────
        wr = data.get("weekly_return_pct")
        bm = data.get("benchmark_pct")

        if wr is None:
            portfolio_return = "—"
            portfolio_return_tone = "neutral"
        else:
            portfolio_return = f"{wr:+.1f}%"
            portfolio_return_tone = "pos" if wr >= 0 else "neg"

        if bm is None:
            benchmark_return = ""
        else:
            benchmark_return = f"vs S&P {bm:+.1f}%"

        # ── trajectory path (5 daily returns, rebased) ──────────────────────
        trajectory = self._build_trajectory(wr, bm)

        # ── portfolio value / delta / YTD (real data) ───────────────────────
        portfolio_value_str, portfolio_delta_str = self._compute_portfolio_value(
            data, wr,
        )
        ytd_return_str, ytd_detail_str, ytd_tone = self._compute_ytd_metrics(data)

        # ── AI generation: three_checks + decision + memo_to_self ───────────
        ai_block = self._generate_ai_v3_block(data)
        three_checks = ai_block["three_checks"]
        decision = ai_block["decision"]
        memo_to_self = ai_block["memo_to_self"]

        # ── week tag ────────────────────────────────────────────────────────
        week_number = data.get("week_number") or 0
        period_end = str(data.get("period_end") or "")
        try:
            year = period_end[:4] if period_end else ""
            week_tag = f"WK-{year}-{week_number:02d}" if year else f"WK-{week_number:02d}"
        except Exception:
            week_tag = f"WK-{week_number}"

        return {
            "as_of":              period_end or "—",
            "week_tag":           week_tag,
            "portfolio_return":   portfolio_return,
            "portfolio_return_tone": portfolio_return_tone,
            "benchmark_return":   benchmark_return,
            "portfolio_value":    portfolio_value_str,
            "portfolio_delta":    portfolio_delta_str,
            "ytd_return":         ytd_return_str,
            "ytd_detail":         ytd_detail_str,
            "ytd_tone":           ytd_tone,
            "three_checks":       three_checks,
            "trajectory":         trajectory,
            "decision":           decision,
            "memo_to_self":       memo_to_self,
        }

    # ── v3 helpers — real data computation ──────────────────────────────────

    def _compute_portfolio_value(self, data: dict[str, Any],
                                 weekly_return_pct: Optional[float]
                                 ) -> tuple[str, str]:
        """Return (portfolio_value_str, portfolio_delta_str) for the v3 KPI.

        portfolio_value: USD-normalised total market value, formatted as
                         "$1,234" or "$12,345". KR positions converted via fx.
        portfolio_delta: 7-day delta approximation = wr * value (no snapshot
                         history infra yet — clearly an approximation rather
                         than a fabricated number).

        Returns ("—", "") on missing data — caller still ships, template
        falls through to its default("—") filter.
        """
        user_id = data.get("user_id")
        if not user_id:
            return "—", ""
        try:
            positions = Position.query.filter_by(user_id=user_id).all()
        except Exception as exc:
            logger.debug("portfolio_value: positions query failed: %s", exc)
            return "—", ""

        value = _portfolio_value_usd(positions)
        if value is None or value <= 0:
            return "—", ""

        # Format: $1,234 (no cents — the headline KPI is scale, not precision).
        if value >= 1_000_000:
            value_str = f"${value/1_000_000:.2f}M"
        elif value >= 10_000:
            value_str = f"${value:,.0f}"
        else:
            value_str = f"${value:,.2f}"

        # 7-day delta approximation. Without a snapshot table, we use
        # weekly_return × current_value as the best descriptive proxy.
        if weekly_return_pct is None:
            delta_str = ""
        else:
            delta_usd = value * weekly_return_pct / 100.0
            sign = "+" if delta_usd >= 0 else "−"
            abs_delta = abs(delta_usd)
            if abs_delta >= 10_000:
                delta_str = f"{sign}${abs_delta:,.0f} 7d"
            else:
                delta_str = f"{sign}${abs_delta:,.2f} 7d"

        return value_str, delta_str

    def _compute_ytd_metrics(self, data: dict[str, Any]) -> tuple[str, str, str]:
        """Return (ytd_return_str, ytd_detail_str, ytd_tone) for the v3 KPI.

        ytd_return_str: "+12.4%" / "−3.1%" / "—"
        ytd_detail_str: "Sortino 1.42" or "" when insufficient history
        ytd_tone:       "pos" / "neg" / "neutral"
        """
        user_id = data.get("user_id")
        if not user_id:
            return "—", "", "neutral"
        try:
            positions = Position.query.filter_by(user_id=user_id).all()
        except Exception as exc:
            logger.debug("ytd: positions query failed: %s", exc)
            return "—", "", "neutral"

        ytd = _portfolio_ytd_return(positions)
        if ytd is None:
            ytd_return_str = "—"
            ytd_tone = "neutral"
        else:
            ytd_return_str = f"{ytd:+.1f}%"
            ytd_tone = "pos" if ytd >= 0 else "neg"

        sortino = _portfolio_sortino(positions)
        if sortino is None:
            ytd_detail_str = ""
        else:
            ytd_detail_str = f"Sortino {sortino:.2f}"

        return ytd_return_str, ytd_detail_str, ytd_tone

    # ── v3 helpers — AI generation (three_checks / decision / memo) ─────────

    def _placeholder_three_checks(self) -> list[dict[str, Any]]:
        return [
            {
                "body": "이번 주 점검 1 — 포트폴리오 섹터별 비중 변동 관찰",
                "meta": "—",
                "checked": False,
            },
            {
                "body": "이번 주 점검 2 — 보유 종목 주간 모멘텀 변화 점검",
                "meta": "—",
                "checked": False,
            },
            {
                "body": "이번 주 점검 3 — 다음 주 주요 이벤트 / 실적 일정 확인",
                "meta": "—",
                "checked": False,
            },
        ]

    _PLACEHOLDER_DECISION = (
        "이번 주 점검 항목을 검토하세요. "
        "다음 주 관찰을 위해 시장 조건과 포트폴리오 변동을 함께 살피세요."
    )
    _PLACEHOLDER_MEMO = (
        "다음 주 검토 사항을 기록하세요. "
        "관찰한 점, 주의할 부분, 확인이 필요한 데이터를 정리합니다."
    )

    def _ai_v3_fallback(self) -> dict[str, Any]:
        return {
            "three_checks": self._placeholder_three_checks(),
            "decision":     self._PLACEHOLDER_DECISION,
            "memo_to_self": self._PLACEHOLDER_MEMO,
        }

    def _build_ai_v3_prompt(self, data: dict[str, Any]) -> str:
        """Compose the user-side prompt for the single Claude Haiku call.

        Keeps the input compact — only fields that actually inform the three
        outputs. Earnings / sector / risk-kpi summaries are pre-formatted to
        stop the model fabricating numbers.
        """
        top_up = data.get("top_movers_up") or []
        top_down = data.get("top_movers_down") or []
        sector_changes = data.get("sector_changes") or []
        sector_alloc = data.get("sector_alloc") or {}
        macro = data.get("macro_checklist") or []
        earnings = data.get("earnings_calendar") or []
        risk_kpi = data.get("risk_kpi") or {}
        risk_notes = data.get("risk_notes") or []

        def _fmt_movers(rows: list[dict], limit: int = 3) -> str:
            if not rows:
                return "(none)"
            return ", ".join(
                f"{r.get('ticker','?')} {r.get('weekly_return_pct',0):+.1f}%"
                for r in rows[:limit]
            )

        def _fmt_sector_changes(rows: list[dict], limit: int = 3) -> str:
            if not rows:
                return "(none)"
            return ", ".join(
                f"{r.get('sector','?')} {r.get('delta_pp',0):+.1f}pp"
                for r in rows[:limit]
            )

        def _fmt_sector_alloc(d: dict[str, float], limit: int = 3) -> str:
            if not d:
                return "(none)"
            items = list(d.items())[:limit]
            return ", ".join(f"{k} {v:.0f}%" for k, v in items)

        def _fmt_earnings(rows: list[dict], limit: int = 5) -> str:
            if not rows:
                return "(none)"
            return ", ".join(
                f"{r.get('ticker','?')} {r.get('date','')}"
                for r in rows[:limit]
            )

        def _fmt_macro(rows: list[dict], limit: int = 3) -> str:
            if not rows:
                return "(none)"
            return ", ".join(
                f"{r.get('label', r.get('series_id','?'))} "
                f"{r.get('value','?')}{r.get('units','')}"
                for r in rows[:limit]
            )

        def _fmt_risk_kpi(d: dict[str, Any]) -> str:
            if not d:
                return "(none)"
            parts = []
            for k in ("var_1d_pct", "es_1d_pct", "mdd_pct", "tail_ratio"):
                if k in d:
                    parts.append(f"{k}={d[k]}")
            return ", ".join(parts) or "(none)"

        return (
            "Generate 3 short Korean observations for a Weekly Memo PDF.\n"
            "Tone: observational, descriptive only. NO advisory verbs.\n"
            "Forbidden words: 추천/조언/매수/매도/사세요/파세요/목표가/유망/"
            "buy/sell/recommend/advise/target.\n"
            "Use only past-tense or present observation verbs (관찰됩니다, "
            "기록되었습니다, 변동되었습니다).\n\n"
            "Data:\n"
            f"- top up: {_fmt_movers(top_up)}\n"
            f"- top down: {_fmt_movers(top_down)}\n"
            f"- sector changes: {_fmt_sector_changes(sector_changes)}\n"
            f"- sector alloc: {_fmt_sector_alloc(sector_alloc)}\n"
            f"- macro: {_fmt_macro(macro)}\n"
            f"- earnings next week: {_fmt_earnings(earnings)}\n"
            f"- risk kpi: {_fmt_risk_kpi(risk_kpi)}\n"
            f"- risk notes: {' / '.join(risk_notes[:3]) or '(none)'}\n\n"
            "Respond with EXACTLY this JSON shape (no markdown fence, no "
            "extra prose):\n"
            "{\n"
            '  "three_checks": [\n'
            '    {"body": "한국어 한 줄, 35자 이내, 관찰 톤", '
            '"meta": "+X.X% 또는 X.Xpp 또는 — 형식의 짧은 메타"},\n'
            '    {"body": "...", "meta": "..."},\n'
            '    {"body": "...", "meta": "..."}\n'
            "  ],\n"
            '  "decision": "다음 주 단 하나의 관찰 포인트를 한국어 1-2문장으로. '
            "관찰적/서술적 표현만 사용. 추천 어휘 금지.\",\n"
            '  "memo_to_self": "다음 주 검토 사항 3개를 한국어로 (1) ~ (3) '
            "번호와 함께 한 문장씩, 명령형 회피, 관찰 톤. 한 줄로 합쳐서 출력.\"\n"
            "}\n"
        )

    def _generate_ai_v3_block(self, data: dict[str, Any]) -> dict[str, Any]:
        """Single Claude Haiku call → {three_checks, decision, memo_to_self}.

        Failure paths (each returns the placeholder fallback for that field):
          - ANTHROPIC_API_KEY missing            → full fallback
          - daily AI budget exhausted            → full fallback
          - any exception during call/parse      → full fallback
          - JSON parse failure                   → full fallback
          - any field hits forbidden vocab       → that field → placeholder
        """
        if not _ai_budget_available():
            logger.info("weekly_memo: AI budget exhausted — using placeholders")
            return self._ai_v3_fallback()

        try:
            from services.ai.service import AIService  # late import — test isolation
            svc = AIService()
            if not svc.available or svc.client is None:
                return self._ai_v3_fallback()
        except Exception as exc:
            logger.debug("AIService import/init failed: %s", exc)
            return self._ai_v3_fallback()

        try:
            from services.ai.service import MODEL, SYSTEM_PROMPT
        except Exception:
            MODEL = "claude-haiku-4-5-20251001"
            SYSTEM_PROMPT = ""

        prompt = self._build_ai_v3_prompt(data)

        try:
            resp = svc.client.messages.create(
                model=MODEL,
                max_tokens=900,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            _ai_budget_consume()
            text = resp.content[0].text if resp.content else ""
        except Exception as exc:
            logger.warning("weekly_memo AI call failed: %s", exc)
            return self._ai_v3_fallback()

        return self._parse_ai_v3_response(text)

    def _parse_ai_v3_response(self, text: str) -> dict[str, Any]:
        """Parse Claude JSON output → validated v3 fields with legal scrubbing.

        Per-field fallback: if any field fails JSON parsing, scrub validation,
        or the prohibited-vocab check, that single field reverts to its
        placeholder. The other fields survive.
        """
        import json
        import re

        if not text or not isinstance(text, str):
            return self._ai_v3_fallback()

        # Strip optional markdown fences the model may add despite instructions.
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            payload = json.loads(cleaned)
        except Exception as exc:
            logger.warning("weekly_memo AI JSON parse failed: %s", exc)
            return self._ai_v3_fallback()

        from services.legal_filter import detect_prohibited

        def _safe_field(text_in: Any, fallback: str) -> str:
            if not isinstance(text_in, str) or not text_in.strip():
                return fallback
            scrubbed = safe_scrub(text_in.strip(),
                                  context="weekly_memo.v3.ai")
            if not scrubbed:
                return fallback
            # Hard reject if still has a structural violation post-scrub.
            if detect_prohibited(scrubbed):
                logger.warning(
                    "weekly_memo AI field rejected by legal filter (post-scrub)"
                )
                return fallback
            return scrubbed

        # ── three_checks (list of {body, meta}) ─────────────────────────────
        raw_checks = payload.get("three_checks")
        out_checks: list[dict[str, Any]] = []
        if isinstance(raw_checks, list):
            for item in raw_checks[:3]:
                if not isinstance(item, dict):
                    continue
                body_in = item.get("body")
                meta_in = item.get("meta") or "—"
                # body is required, meta best-effort
                body = _safe_field(body_in, "")
                if not body:
                    continue
                meta = _safe_field(str(meta_in), "—")
                out_checks.append({
                    "body":    body,
                    "meta":    meta or "—",
                    "checked": True,
                })
        if len(out_checks) < 3:
            # Pad with placeholders so the template always has 3 rows.
            placeholders = self._placeholder_three_checks()
            out_checks.extend(placeholders[len(out_checks):])
        out_checks = out_checks[:3]

        decision = _safe_field(payload.get("decision"), self._PLACEHOLDER_DECISION)
        memo = _safe_field(payload.get("memo_to_self"), self._PLACEHOLDER_MEMO)

        return {
            "three_checks": out_checks,
            "decision":     decision,
            "memo_to_self": memo,
        }

    @staticmethod
    def _build_trajectory(weekly_return_pct: Optional[float],
                          benchmark_pct: Optional[float]
                          ) -> dict[str, Any]:
        """Construct the 5-day trajectory SVG paths.

        Until daily snapshots surface in generate_for_user(), we approximate
        a smooth 5-day curve using a linear ramp ending at the weekly total
        return — descriptive, not predictive.

        Returns a dict containing both the raw 5-element series (for any
        future consumer) and three pre-built SVG path strings:
            path_port, path_port_fill, path_bench
        sized to the 600×120 viewBox the React component uses.
        """
        wr = float(weekly_return_pct) if weekly_return_pct is not None else 0.0
        bm = float(benchmark_pct) if benchmark_pct is not None else 0.0

        # 5-day linear ramp from 0 → final weekly return.
        port_series = [round(wr * i / 4.0, 4) for i in range(5)]
        bench_series = [round(bm * i / 4.0, 4) for i in range(5)]

        all_returns = port_series + bench_series
        port_path = WeeklyMemoService._path_from_returns(port_series, all_returns)
        bench_path = WeeklyMemoService._path_from_returns(bench_series, all_returns)

        # Closed area beneath the portfolio curve, anchored at y=120.
        port_fill_path = (
            f"{port_path} L600,120 L0,120 Z" if port_path else ""
        )

        return {
            "portfolio":      port_series,
            "benchmark":      bench_series,
            "path_port":      port_path,
            "path_port_fill": port_fill_path,
            "path_bench":     bench_path,
        }

    @staticmethod
    def _path_from_returns(values: list[float], all_values: list[float],
                           width: int = 600, height: int = 120) -> str:
        """Port of pathFromReturns() in weekly-memo.tsx (1:1).

        Rebases to a height-tall band — top=best, bottom=worst across both
        series. Pads 10% top/bottom so endpoints don't clip to the edge.
        """
        if not values:
            return ""
        if not all_values:
            all_values = values
        v_min = min(all_values)
        v_max = max(all_values)
        v_range = (v_max - v_min) or 1.0
        n = len(values)
        step = width / (n - 1) if n > 1 else width
        parts: list[str] = []
        for i, v in enumerate(values):
            x = i * step
            y = height * 0.95 - ((v - v_min) / v_range) * (height * 0.85)
            cmd = "M" if i == 0 else "L"
            parts.append(f"{cmd}{x:.0f},{y:.1f}")
        return " ".join(parts)

    # ── PDF render ──────────────────────────────────────────────────────────

    def render_pdf(self, data: dict[str, Any]) -> Optional[bytes]:
        """HTML → PDF via WeasyPrint. None when WeasyPrint is unavailable."""
        HTML = _try_import_weasyprint()
        if HTML is None:
            return None
        html_str = self.render_pdf_html(data)
        try:
            return HTML(string=html_str).write_pdf()
        except Exception as exc:  # pragma: no cover — native deps
            logger.error("WeasyPrint render failed: %s", exc)
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

    def _fallback_html(self, data: dict[str, Any], *, email: bool) -> str:
        """Template-free minimal HTML — keeps send_email working in broken envs."""
        from html import escape
        up = "".join(
            f"<li>{escape(m['ticker'])}: {m['weekly_return_pct']}%</li>"
            for m in data.get("top_movers_up", [])
        )
        dn = "".join(
            f"<li>{escape(m['ticker'])}: {m['weekly_return_pct']}%</li>"
            for m in data.get("top_movers_down", [])
        )
        wr = data.get("weekly_return_pct")
        wr_str = f"{wr}%" if wr is not None else "N/A"
        return f"""<!doctype html><html><body>
<h1>Week {data.get('week_number','?')} Investor Memo — {escape(data.get('user_name',''))}</h1>
<p>Weekly return: <strong>{wr_str}</strong></p>
<h2>Top movers (up)</h2><ul>{up}</ul>
<h2>Top movers (down)</h2><ul>{dn}</ul>
<p><em>{escape(data.get('disclaimer',''))}</em></p>
</body></html>"""

    # ── send ────────────────────────────────────────────────────────────────

    def send_email(self, user: User,
                   pdf_bytes: Optional[bytes],
                   html_body: str) -> bool:
        """Deliver the memo. Returns True on success, False on skip/failure.

        Phase 7 — delivery is delegated to :class:`EmailSender` which
        owns opt-out gating, unsubscribe URL+headers, SendGrid →
        SMTP fallback, and PDF attachment. We keep ownership of
        subject + filename here because both vary per artefact type.
        """
        from services.email import EmailSender

        _iso = datetime.now(timezone.utc).replace(tzinfo=None).isocalendar()
        subject = f"Week {_iso[1]}, {_iso[0]} Investor Memo"
        return EmailSender().send(
            user,
            subject=subject,
            html_body=html_body,
            from_env_var="WEEKLY_MEMO_FROM_EMAIL",
            from_default="reports@pivoxquant.com",
            pdf_bytes=pdf_bytes,
            pdf_filename=f"weekly_memo_{user.id}.pdf",
        )

    # ── persist + orchestrate ───────────────────────────────────────────────

    def _persist(self, user_id: int, data: dict[str, Any],
                 pdf_bytes: Optional[bytes], sent: bool) -> Artifact:
        """UPSERT on (user_id, type='weekly_memo', title)."""
        title = f"Week {data['week_number']} Investor Memo — {data['period_end']}"
        pdf_path: Optional[str] = None
        if pdf_bytes:
            try:
                base = _storage_dir() / str(user_id)
                base.mkdir(parents=True, exist_ok=True)
                path = base / f"week_{data['week_number']}_{data['period_end']}.pdf"
                path.write_bytes(pdf_bytes)
                pdf_path = str(path)
            except Exception as exc:
                logger.warning("PDF write failed for user %s: %s", user_id, exc)

        artefact = (
            Artifact.query
            .filter_by(user_id=user_id, type="weekly_memo", title=title)
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
                type="weekly_memo",
                title=title,
                data_json=data,
                pdf_path=pdf_path,
                sent_at=datetime.now(timezone.utc).replace(tzinfo=None) if sent else None,
            )
            db.session.add(artefact)
        db.session.commit()
        return artefact

    def run_for_user(self, user: User,
                     target_date: date | None = None,
                     *, send: bool = True) -> Optional[Artifact]:
        """End-to-end: generate → render → send → persist for one user.

        Returns the Artifact row, or None if the user had no positions.
        """
        positions = Position.query.filter_by(user_id=user.id).count()
        if positions == 0:
            logger.info("skipping user %s — empty portfolio", user.id)
            return None

        data = self.generate_for_user(user.id, target_date=target_date)
        pdf_bytes = self.render_pdf(data)
        html_body = self.render_html(data)

        # DIAG 2026-04-29: PDF 첨부 누락 추적
        if pdf_bytes is None:
            logger.warning("DIAG user=%s render_pdf returned None (WeasyPrint unavailable or fail)", user.id)
        elif len(pdf_bytes) == 0:
            logger.warning("DIAG user=%s render_pdf returned empty bytes", user.id)
        else:
            logger.info("DIAG user=%s render_pdf bytes=%d", user.id, len(pdf_bytes))

        sent = False
        if send:
            try:
                sent = self.send_email(user, pdf_bytes, html_body)
            except Exception as exc:
                logger.error("send_email raised for user %s: %s", user.id, exc)
                sent = False

        return self._persist(user.id, data, pdf_bytes, sent)

    def run_weekly(self, target_date: date | None = None) -> dict[str, Any]:
        """Cron target — Sunday 08:00 KST. Pro+ users only."""
        from services.artifacts import iter_users_chunked

        target_date = target_date or date.today()

        paid_users = (
            User.query
            .filter(User.subscription_tier.in_(list(_PAID_TIERS)))
            .all()
        )

        successes = 0
        failures = 0
        skipped = 0

        for user in iter_users_chunked(paid_users, label="weekly_memo.weekly"):
            try:
                result = self.run_for_user(user, target_date=target_date)
                if result is None:
                    skipped += 1
                else:
                    successes += 1
            except Exception as exc:
                db.session.rollback()
                failures += 1
                logger.error("weekly memo failed for user %s: %s", user.id, exc)

        summary = {
            "date":      target_date.isoformat(),
            "attempted": len(paid_users),
            "success":   successes,
            "failed":    failures,
            "skipped":   skipped,
        }
        logger.info("weekly memo run: %s", summary)
        return summary
