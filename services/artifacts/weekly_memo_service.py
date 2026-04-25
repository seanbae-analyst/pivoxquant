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
   `morning_brief_service.is_compliant` as the final filter before
   any AI-generated text is persisted.
5. No modifications to the Morning Brief pipeline. This service
   imports read-only helpers only.
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
        logger.info("WeasyPrint unavailable (%s); PDF generation will be skipped.", exc)
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
# Same shape as morning_brief_service — keeps us under Claude Haiku budget
# even when a large Pro cohort triggers the Sunday run at once.
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
                pass
    except Exception:
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
        import fmp_service as fmp  # type: ignore
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


def _risk_notes(positions: list[Position],
                sector_alloc: dict[str, float],
                top_down: list[dict]) -> list[str]:
    """Rule-based descriptive risk notes — never action advice.

    Passes output through morning_brief compliance regex before returning.
    """
    try:
        from services.morning_brief_service import is_compliant
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
        from risk_models import ComponentES
        es_out = ComponentES.decompose(returns_matrix, weights, alpha=0.05)
        if es_out.get("portfolio_var") is not None:
            kpi["var_1d_pct"] = round(float(es_out["portfolio_var"]), 2)
        if es_out.get("portfolio_es") is not None:
            kpi["es_1d_pct"] = round(float(es_out["portfolio_es"]), 2)
    except Exception as exc:
        logger.debug("ComponentES failed: %s", exc)

    # 2. Max Drawdown + trough / recovery weeks.
    try:
        from risk_models import ConditionalDrawdown
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
        from risk_models import TailRatio
        port_returns = returns_matrix @ weights
        tr_out = TailRatio.calculate(port_returns)
        if tr_out.get("tail_ratio") is not None:
            kpi["tail_ratio"] = round(float(tr_out["tail_ratio"]), 2)
    except Exception as exc:
        logger.debug("TailRatio failed: %s", exc)

    # 4. GKYZ volatility — portfolio-weighted, only if every held ticker has OHLC.
    try:
        from risk_models import GKYZVolatility
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
            disclaimer="정보 제공 목적이며 투자 권유가 아닙니다. 투자 판단은 본인 책임입니다.",
        )
        return ctx.to_dict()

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
        """Render the *full* 5-page PDF HTML (richer, print-oriented)."""
        env = self._jinja_env()
        if env is None:
            return self._fallback_html(data, email=False)
        try:
            tpl = env.get_template("weekly_memo.html")
            return tpl.render(**self._with_persona(data))
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

        Priority:
        1. SendGrid if `SENDGRID_API_KEY` is present.
        2. SMTP if `SMTP_HOST` is present.
        3. Otherwise → skip (dev environment); caller still persists the
           artefact row so the user can download from the history route.
        """
        if getattr(user, "email_opt_out", False):
            logger.info("user %s opted out of email", user.id)
            return False

        from_email = os.environ.get(
            "WEEKLY_MEMO_FROM_EMAIL", "reports@pivoxquant.com"
        )
        subject = f"Week {datetime.now(timezone.utc).replace(tzinfo=None).isocalendar()[1]} Investor Memo"

        # --- SendGrid ---
        sg_key = os.environ.get("SENDGRID_API_KEY")
        if sg_key:
            try:
                import base64
                from sendgrid import SendGridAPIClient  # type: ignore
                from sendgrid.helpers.mail import (  # type: ignore
                    Mail, Attachment, FileContent, FileName, FileType, Disposition,
                )
                mail = Mail(from_email=from_email, to_emails=user.email,
                            subject=subject, html_content=html_body)
                if pdf_bytes:
                    enc = base64.b64encode(pdf_bytes).decode()
                    att = Attachment(
                        FileContent(enc),
                        FileName(f"weekly_memo_{user.id}.pdf"),
                        FileType("application/pdf"),
                        Disposition("attachment"),
                    )
                    mail.attachment = att
                SendGridAPIClient(sg_key).send(mail)
                return True
            except Exception as exc:
                logger.error("SendGrid send failed for user %s: %s", user.id, exc)
                return False

        # --- SMTP fallback ---
        smtp_host = os.environ.get("SMTP_HOST")
        if smtp_host:
            try:
                import smtplib
                from email.message import EmailMessage
                msg = EmailMessage()
                msg["From"] = from_email
                msg["To"] = user.email
                msg["Subject"] = subject
                msg.set_content("HTML-only; view in an HTML-capable client.")
                msg.add_alternative(html_body, subtype="html")
                if pdf_bytes:
                    msg.add_attachment(pdf_bytes, maintype="application",
                                       subtype="pdf",
                                       filename=f"weekly_memo_{user.id}.pdf")
                port = int(os.environ.get("SMTP_PORT", "587"))
                user_ = os.environ.get("SMTP_USER")
                pw = os.environ.get("SMTP_PASSWORD")
                with smtplib.SMTP(smtp_host, port, timeout=10) as s:
                    s.starttls()
                    if user_ and pw:
                        s.login(user_, pw)
                    s.send_message(msg)
                return True
            except Exception as exc:
                logger.error("SMTP send failed for user %s: %s", user.id, exc)
                return False

        logger.info("no email provider configured — skipping send for user %s", user.id)
        return False

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
        target_date = target_date or date.today()

        paid_users = (
            User.query
            .filter(User.subscription_tier.in_(list(_PAID_TIERS)))
            .all()
        )

        successes = 0
        failures = 0
        skipped = 0

        for user in paid_users:
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
