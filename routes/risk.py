"""Risk Observation endpoints — 7-Layer Risk Defense + VaR/ES/DD/Correlation.

All language is observational and neutral:
  - no BUY/SELL/recommend/advice/bullish/bearish/forecast
  - layer status values are GREEN / YELLOW / RED (mapped from defense_score)

Endpoints:
  GET /api/risk/summary        → {var_1d_pct, es_1d_pct, max_dd_90d_pct, corr_risk_index}
  GET /api/risk/layers         → [{no, name, status, metric, observation}] x7
  GET /api/risk/correlation    → {labels:[...tickers], matrix:[[...]]} up to 10x10
  GET /api/risk/rolling-var    → [{date, var_pct}] last 30 trading days
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

import numpy as np
from flask import Blueprint, jsonify
from flask_login import current_user

from models import Position
from services.container import fetcher
from risk_defense import RiskDefenseSystem
from .decorators import api_auth, legal_scrub_response

logger = logging.getLogger(__name__)

risk_bp = Blueprint("risk_observation", __name__, url_prefix="/api/risk")


# ── Helpers ────────────────────────────────────────────────────────

def _user_positions() -> list[Position]:
    try:
        return Position.query.filter_by(user_id=current_user.id).all()
    except Exception as e:
        logger.warning(f"risk._user_positions failed: {e}")
        return []


def _build_returns_matrix(tickers: list[str], days: int = 90):
    """Fetch daily returns for each ticker. Returns (matrix, valid_tickers, closes).

    matrix shape: (days, n_tickers). Rows are aligned by calendar day; missing
    days are forward-filled. Returns (None, [], None) on any failure.
    """
    if not tickers:
        return None, [], None
    try:
        import pandas as pd
    except Exception:
        return None, [], None

    series: dict[str, "pd.Series"] = {}
    for t in tickers:
        try:
            h = fetcher.get_price_history(t, period="3mo")
            if h is None or h.empty or "Close" not in h.columns:
                continue
            s = h["Close"].astype(float)
            if len(s) < 20:
                continue
            series[t] = s
        except Exception as e:
            logger.debug(f"risk: price history skip {t}: {e}")

    if not series:
        return None, [], None

    df = pd.DataFrame(series).sort_index().ffill().dropna(how="all")
    if df.empty or df.shape[0] < 20:
        return None, [], None

    rets = df.pct_change().dropna()
    if rets.empty:
        return None, [], None

    tail = rets.tail(days)
    return tail.values, list(tail.columns), df


def _portfolio_snapshot():
    """Build a portfolio_state dict for RiskDefenseSystem.check_all(). Also
    returns auxiliary pieces (tickers, returns_matrix, value series) that
    other endpoints can reuse without re-fetching."""
    positions = _user_positions()
    if not positions:
        return None, [], None, None

    tickers = [p.ticker for p in positions]
    matrix, valid, df_close = _build_returns_matrix(tickers)

    # Mark-to-market position values — best-effort.
    try:
        from services.container import realtime
        prices = realtime.get_prices_batch(tickers)
    except Exception:
        prices = {}

    pos_list: list[dict] = []
    total_value = 0.0
    for p in positions:
        price = (prices.get(p.ticker) or {}).get("price") or p.avg_cost or 0.0
        value = float(price) * float(p.shares or 0)
        total_value += value
        pos_list.append({
            "ticker": p.ticker,
            "value":  value,
            "sector": "Unknown",
            "returns_20d": 0.0,
            "weight": 0.0,  # normalized below
        })

    if total_value > 0:
        for pos in pos_list:
            pos["weight"] = pos["value"] / total_value

    # VIX (best-effort from macro)
    vix = None
    try:
        macro = fetcher.get_macro_data()
        vix = macro.get("vix")
    except Exception:
        pass

    state = {
        "positions":       pos_list,
        "portfolio_value": total_value,
        "daily_return":    0.0,
        "vix":             vix,
        "regime":          "TRANSITION",
        "returns_matrix":  matrix,
    }
    return state, valid, matrix, df_close


def _score_to_status(score: int) -> str:
    if score >= 80:
        return "GREEN"
    if score >= 50:
        return "YELLOW"
    return "RED"


def _demo_summary_response() -> dict:
    """Neutral fallback for /summary when upstream data is unavailable."""
    return {
        "var_1d_pct":       0.0,
        "es_1d_pct":        0.0,
        "max_dd_90d_pct":   0.0,
        "corr_risk_index":  0.0,
        "is_demo":          True,
        "message":          "Risk data temporarily unavailable",
    }


def _demo_layers_response() -> dict:
    """Neutral fallback for /layers — 7 GREEN placeholder entries."""
    layers = [
        {"no": 1, "name": "VaR Layer",          "metric_label": "Daily 1-day 95% VaR",
         "metric_value": "—", "status": "GREEN",
         "observation": "Risk data temporarily unavailable."},
        {"no": 2, "name": "Correlation Layer",  "metric_label": "Avg pairwise correlation",
         "metric_value": "—", "status": "GREEN",
         "observation": "Risk data temporarily unavailable."},
        {"no": 3, "name": "VIX Regime",         "metric_label": "VIX",
         "metric_value": "—", "status": "GREEN",
         "observation": "Risk data temporarily unavailable."},
        {"no": 4, "name": "Tail Risk",          "metric_label": "Tail imbalance",
         "metric_value": "—", "status": "GREEN",
         "observation": "Risk data temporarily unavailable."},
        {"no": 5, "name": "Daily Loss Guard",   "metric_label": "Today's P&L",
         "metric_value": "0.00%", "status": "GREEN",
         "observation": "Risk data temporarily unavailable."},
        {"no": 6, "name": "Sector Exposure",    "metric_label": "Max sector weight",
         "metric_value": "—", "status": "GREEN",
         "observation": "Risk data temporarily unavailable."},
        {"no": 7, "name": "Cash Buffer",        "metric_label": "Cash weight",
         "metric_value": "—", "status": "GREEN",
         "observation": "Risk data temporarily unavailable."},
    ]
    return {
        "layers":         layers,
        "defense_score":  100,
        "overall_status": "GREEN",
        "is_demo":        True,
        "message":        "Risk data temporarily unavailable",
    }


# ── Endpoints ──────────────────────────────────────────────────────

@risk_bp.route("/summary")
@api_auth
@legal_scrub_response
def risk_summary():
    """Return top-line risk metrics. Zeros on empty portfolio, demo fallback on failure.

    Pipeline-level diagnostics (2026-04-23): when the outer `except` swallows an
    exception we now log position count, matrix shape, and the failure stage so
    repro-less bugs like "always is_demo:true" can be localized from prod logs.
    Degraded-but-partial data (fewer than 20 rows but at least 10) is surfaced
    as a neutral zero payload instead of demo fallback so the UI doesn't show
    "SAMPLE PREVIEW" whenever one ticker lacks KIS history.
    """
    stage = "init"
    try:
        stage = "snapshot"
        state, valid_tickers, matrix, df_close = _portfolio_snapshot()
        payload = {
            "var_1d_pct":       0.0,
            "es_1d_pct":        0.0,
            "max_dd_90d_pct":   0.0,
            "corr_risk_index":  0.0,
        }

        n_pos = 0 if state is None else len(state.get("positions") or [])
        mshape = None if matrix is None else tuple(matrix.shape)
        logger.info(
            "risk.summary: positions=%s valid=%s matrix=%s",
            n_pos, len(valid_tickers or []), mshape,
        )

        if state is None:
            # Truly empty portfolio — honest zeros, not demo.
            return jsonify(payload)

        if matrix is None or matrix.shape[0] < 20 or matrix.shape[1] == 0:
            # History too short or missing for risk math. Return zeros with a
            # soft message so the UI can distinguish from a hard-failure demo.
            payload["message"] = "Insufficient price history for risk metrics"
            return jsonify(payload)

        stage = "weights"
        weights = np.array([p["weight"] or (1.0 / max(len(state["positions"]), 1))
                            for p in state["positions"]], dtype=float)
        # Align weights to matrix columns when some tickers were dropped
        if weights.shape[0] != matrix.shape[1]:
            n = matrix.shape[1]
            weights = np.ones(n, dtype=float) / n
        else:
            s = weights.sum()
            if s > 0:
                weights = weights / s

        stage = "var"
        port_rets = matrix @ weights
        var_1d_pct = -float(np.percentile(port_rets, 5)) * 100
        tail = port_rets[port_rets <= np.percentile(port_rets, 5)]
        es_1d_pct = -float(np.mean(tail)) * 100 if tail.size else 0.0

        # Max drawdown over the same 90-day window using portfolio equity curve
        stage = "drawdown"
        eq = np.cumprod(1.0 + port_rets)
        peak = np.maximum.accumulate(eq)
        dd = (eq / peak) - 1.0
        max_dd_pct = -float(np.min(dd)) * 100 if dd.size else 0.0

        # Correlation risk index — avg pairwise correlation on 20-day window
        stage = "correlation"
        corr_idx = 0.0
        if matrix.shape[1] >= 2 and matrix.shape[0] >= 20:
            recent = matrix[-20:]
            c = np.corrcoef(recent.T)
            mask = ~np.eye(c.shape[0], dtype=bool)
            corr_idx = float(np.nanmean(c[mask]))

        payload["var_1d_pct"]      = round(var_1d_pct, 2)
        payload["es_1d_pct"]       = round(es_1d_pct, 2)
        payload["max_dd_90d_pct"]  = round(max_dd_pct, 2)
        payload["corr_risk_index"] = round(corr_idx, 2)
        return jsonify(payload)
    except Exception as e:
        logger.warning(
            "risk.summary failed at stage=%s: %s", stage, e, exc_info=True,
        )
        return jsonify(_demo_summary_response())


@risk_bp.route("/layers")
@api_auth
@legal_scrub_response
def risk_layers():
    """7-Layer observation ladder. Always returns 7 entries, even when
    portfolio empty (all GREEN with placeholder metrics). Demo fallback on failure."""
    try:
        return _risk_layers_impl()
    except Exception as e:
        logger.warning(f"risk.layers failed: {e}", exc_info=True)
        return jsonify(_demo_layers_response())


def _risk_layers_impl():
    state, _, matrix, _ = _portfolio_snapshot()

    # Default layers when portfolio is empty
    default_layers = [
        {"no": 1, "name": "VaR Layer",          "metric_label": "Daily 1-day 95% VaR",
         "metric_value": "—", "status": "GREEN",
         "observation": "No positions under observation."},
        {"no": 2, "name": "Correlation Layer",  "metric_label": "Avg pairwise correlation",
         "metric_value": "—", "status": "GREEN",
         "observation": "No positions under observation."},
        {"no": 3, "name": "VIX Regime",         "metric_label": "VIX",
         "metric_value": "—", "status": "GREEN",
         "observation": "No VIX signal attached."},
        {"no": 4, "name": "Tail Risk",          "metric_label": "Tail imbalance",
         "metric_value": "—", "status": "GREEN",
         "observation": "No positions under observation."},
        {"no": 5, "name": "Daily Loss Guard",   "metric_label": "Today's P&L",
         "metric_value": "0.00%", "status": "GREEN",
         "observation": "Within band."},
        {"no": 6, "name": "Sector Exposure",    "metric_label": "Max sector weight",
         "metric_value": "—", "status": "GREEN",
         "observation": "No positions under observation."},
        {"no": 7, "name": "Cash Buffer",        "metric_label": "Cash weight",
         "metric_value": "—", "status": "GREEN",
         "observation": "No positions under observation."},
    ]

    if state is None:
        return jsonify(default_layers)

    rds = RiskDefenseSystem.from_profile(
        getattr(current_user, "investor_profile", "steady_accumulator")
        or "steady_accumulator"
    )
    try:
        actions = rds.check_all(state)
    except Exception as e:
        logger.warning(f"risk_layers check_all failed: {e}")
        return jsonify(default_layers)

    triggered = set(actions.get("layers_triggered", []))

    # ── Compute per-layer metric values from the snapshot ──
    n_pos = len(state["positions"])
    weights = np.array([p["weight"] or (1.0 / max(n_pos, 1))
                        for p in state["positions"]], dtype=float)
    if matrix is not None and weights.shape[0] != matrix.shape[1]:
        weights = np.ones(matrix.shape[1], dtype=float) / matrix.shape[1]
    s = weights.sum()
    if s > 0:
        weights = weights / s

    var_pct_str = "—"
    corr_str = "—"
    if matrix is not None and matrix.shape[0] >= 20:
        pr = matrix @ weights
        var_pct_str = f"{-float(np.percentile(pr, 5)) * 100:.2f}%"
        if matrix.shape[1] >= 2:
            recent = matrix[-20:]
            c = np.corrcoef(recent.T)
            mask = ~np.eye(c.shape[0], dtype=bool)
            corr_str = f"{float(np.nanmean(c[mask])):.2f}"

    vix = state.get("vix")
    vix_str = f"{vix:.1f}" if isinstance(vix, (int, float)) else "—"

    daily_ret = state.get("daily_return", 0.0)

    # Sector concentration — all sectors currently "Unknown" (no sector data),
    # so we fall back to showing the largest single position weight.
    max_w = max((p["weight"] for p in state["positions"]), default=0.0)
    sector_str = f"{max_w * 100:.0f}% max position"

    cash_w_pct = 0.0  # portfolio model has no explicit cash sleeve yet

    layers = [
        {
            "no": 1, "name": "VaR Layer",
            "metric_label": "Daily 1-day 95% VaR",
            "metric_value": var_pct_str,
            "status": "RED" if "L1_VAR" in triggered else "GREEN",
            "observation": "VaR observed above soft limit." if "L1_VAR" in triggered
                            else "Within historical band.",
        },
        {
            "no": 2, "name": "Correlation Layer",
            "metric_label": "Avg pairwise correlation",
            "metric_value": corr_str,
            "status": "YELLOW" if "L2_CORRELATION" in triggered else "GREEN",
            "observation": "Observed elevated pairwise correlation."
                           if "L2_CORRELATION" in triggered
                           else "Diversification within expected band.",
        },
        {
            "no": 3, "name": "VIX Regime",
            "metric_label": "VIX",
            "metric_value": vix_str,
            "status": "RED" if "L3_VIX_PANIC" in triggered
                      else ("YELLOW" if "L3_VIX_CAUTION" in triggered else "GREEN"),
            "observation": ("Panic-level volatility observed."
                            if "L3_VIX_PANIC" in triggered
                            else ("Elevated volatility observed."
                                  if "L3_VIX_CAUTION" in triggered
                                  else "Low-volatility regime noted.")),
        },
        {
            "no": 4, "name": "Tail Risk",
            "metric_label": "Tail imbalance",
            "metric_value": "balanced" if "L4_TAIL_RISK" not in triggered else "imbalanced",
            "status": "YELLOW" if "L4_TAIL_RISK" in triggered else "GREEN",
            "observation": "Left-tail concentration observed."
                           if "L4_TAIL_RISK" in triggered
                           else "Balanced right/left tail.",
        },
        {
            "no": 5, "name": "Daily Loss Guard",
            "metric_label": "Today's P&L",
            "metric_value": f"{daily_ret:.2f}%",
            "status": "RED" if "L5_DAILY_LOSS" in triggered else "GREEN",
            "observation": "Today's loss above soft limit."
                           if "L5_DAILY_LOSS" in triggered
                           else "Within daily loss band.",
        },
        {
            "no": 6, "name": "Sector Exposure",
            "metric_label": "Max position weight",
            "metric_value": sector_str,
            "status": "YELLOW" if "L6_SECTOR_CONCENTRATION" in triggered else "GREEN",
            "observation": "Position concentration above soft-limit band."
                           if "L6_SECTOR_CONCENTRATION" in triggered
                           else "Concentration within band.",
        },
        {
            "no": 7, "name": "Cash Buffer",
            "metric_label": "Cash weight",
            "metric_value": f"{cash_w_pct:.0f}%",
            "status": "GREEN",
            "observation": "Cash buffer observed.",
        },
    ]

    # Provide the rolled-up score too (some clients display it).
    score = int(actions.get("defense_score", 100))
    return jsonify({
        "layers":         layers,
        "defense_score":  score,
        "overall_status": _score_to_status(score),
    })


@risk_bp.route("/correlation")
@api_auth
@legal_scrub_response
def risk_correlation():
    """Return a <= 10x10 correlation matrix over the last 20 trading days."""
    try:
        _, tickers, matrix, _ = _portfolio_snapshot()
        if matrix is None or matrix.shape[1] < 2:
            return jsonify({"labels": [], "matrix": []})

        labels = tickers[:10]
        sub = matrix[-20:, :len(labels)]
        try:
            c = np.corrcoef(sub.T)
        except Exception as e:
            logger.warning(f"corr compute failed: {e}")
            return jsonify({"labels": [], "matrix": []})

        matrix_out = [[round(float(v), 2) if np.isfinite(v) else 0.0 for v in row]
                      for row in c]
        return jsonify({"labels": labels, "matrix": matrix_out})
    except Exception as e:
        logger.warning(f"risk.correlation failed: {e}", exc_info=True)
        return jsonify({"labels": [], "matrix": [], "is_demo": True,
                        "message": "Risk data temporarily unavailable"})


@risk_bp.route("/rolling-var")
@api_auth
@legal_scrub_response
def rolling_var():
    """Return rolling 20-day historical 95% VaR for the portfolio, last ~30 days."""
    try:
        state, _, matrix, df_close = _portfolio_snapshot()
        if state is None or matrix is None or matrix.shape[0] < 25 or df_close is None:
            return jsonify([])

        n_pos = len(state["positions"])
        weights = np.array([p["weight"] or (1.0 / max(n_pos, 1))
                            for p in state["positions"]], dtype=float)
        if weights.shape[0] != matrix.shape[1]:
            weights = np.ones(matrix.shape[1], dtype=float) / matrix.shape[1]
        s = weights.sum()
        if s > 0:
            weights = weights / s

        port_rets = matrix @ weights
        window = 20
        if len(port_rets) < window + 5:
            return jsonify([])

        # Match back to the tail of df_close index for dates
        try:
            dates = list(df_close.index[-len(port_rets):])
        except Exception:
            dates = [datetime.now(timezone.utc) - timedelta(days=i)
                     for i in range(len(port_rets) - 1, -1, -1)]

        out = []
        for i in range(window, len(port_rets)):
            w = port_rets[i - window:i]
            var_pct = -float(np.percentile(w, 5)) * 100
            d = dates[i]
            try:
                date_str = d.strftime("%Y-%m-%d")
            except Exception:
                date_str = str(d)[:10]
            out.append({"date": date_str, "var_pct": round(var_pct, 2)})

        return jsonify(out[-30:])
    except Exception as e:
        logger.warning(f"risk.rolling_var failed: {e}", exc_info=True)
        return jsonify([])
