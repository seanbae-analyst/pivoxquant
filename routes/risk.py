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
from zoneinfo import ZoneInfo

import numpy as np
from flask import Blueprint, jsonify, request
from flask_login import current_user

from models import Position
from services.container import fetcher
from services.quant.risk_defense import RiskDefenseSystem
from .decorators import api_auth, legal_scrub_response

_KST = ZoneInfo("Asia/Seoul")


def _kst_now_str() -> str:
    """Current Korea-Standard time as 'YYYY-MM-DD HH:MM KST'.

    Risk Board v2 surfaces an 'observed_at_kst' badge per layer; KST is the
    project's default display timezone (memory: design_v3 / KR convention).
    """
    return datetime.now(_KST).strftime("%Y-%m-%d %H:%M KST")

logger = logging.getLogger(__name__)

risk_bp = Blueprint("risk_observation", __name__, url_prefix="/api/risk")


# ── Helpers ────────────────────────────────────────────────────────

def _user_positions() -> list[Position]:
    try:
        return Position.query.filter_by(user_id=current_user.id).all()
    except Exception as e:
        logger.warning("risk._user_positions failed: %s", e)
        return []


def _build_returns_matrix(tickers: list[str], days: int = 90):
    """Fetch daily returns for each ticker. Returns (matrix, valid_tickers, closes).

    matrix shape: (days, n_tickers). Rows are aligned by calendar day; missing
    days are forward-filled. Returns (None, [], None) on any failure.

    Bug A (2026-04-24): previously any ticker with <20 rows was silently
    dropped, and the whole call returned None if the intersected frame had
    <20 rows. That nuked Layer-1/2/4 metrics whenever ANY single position
    had a short history. We now accept tickers with ≥10 rows individually
    and return a partial matrix (with logged drop list) instead of None.
    """
    if not tickers:
        return None, [], None
    try:
        import pandas as pd
    except Exception:
        return None, [], None

    series: dict[str, "pd.Series"] = {}
    dropped: list[str] = []

    # Parallelise the external price-history fetch — fetcher.get_price_history
    # hits FMP/KIS only (no DB), so this mirrors portfolio_history's proven
    # ThreadPoolExecutor(5) pattern without touching the DB pool. Cuts a cold
    # 20-ticker risk load from the serial sum (~4–16s) to ~the slowest single
    # fetch. ex.map preserves input order, and all result processing below
    # stays single-threaded, so `series`/`dropped` see no races and the
    # err/empty/short-history drop semantics are unchanged.
    from concurrent.futures import ThreadPoolExecutor

    def _fetch_one(t):
        try:
            return t, fetcher.get_price_history(t, period="3mo"), None
        except Exception as e:  # noqa: BLE001
            return t, None, e

    with ThreadPoolExecutor(max_workers=5) as ex:
        results = list(ex.map(_fetch_one, tickers))

    for t, h, err in results:
        if err is not None:
            logger.debug("risk: price history skip %s: %s", t, err)
            dropped.append(f"{t}(err)")
            continue
        if h is None or h.empty or "Close" not in h.columns:
            dropped.append(f"{t}(empty)")
            continue
        s = h["Close"].astype(float).dropna()
        # Lowered floor from 20 → 10. The per-layer checks already
        # guard on matrix.shape[0] >= 20 at the aggregated level, so
        # individual short tickers are still excluded when the final
        # intersect would be unreliable.
        if len(s) < 10:
            dropped.append(f"{t}(n={len(s)})")
            continue
        series[t] = s

    if dropped:
        logger.info("risk._build_returns_matrix dropped tickers: %s", dropped)

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


def _positions_signature(positions: list[Position]) -> str:
    """Stable hash of (ticker, shares, avg_cost) tuples — invalidates the
    risk snapshot cache the moment a user changes their book."""
    import hashlib
    parts = sorted(
        f"{p.ticker}|{float(p.shares or 0)}|{float(p.avg_cost or 0)}"
        for p in positions
    )
    return hashlib.sha1("\n".join(parts).encode("utf-8")).hexdigest()  # noqa: S324


def _portfolio_snapshot():
    """Build a portfolio_state dict for RiskDefenseSystem.check_all(). Also
    returns auxiliary pieces (tickers, returns_matrix, value series) that
    other endpoints can reuse without re-fetching.

    Perf P0-2 (2026-05-10): in-process 5-min TTL cache keyed on
    (user_id, positions_signature). Five risk endpoints fan in here — a
    single dashboard render previously did 5 × N FMP fetches; now the first
    call populates the cache and the next 4 within the TTL window are O(1).
    """
    positions = _user_positions()
    if not positions:
        return None, [], None, None

    # Cache lookup BEFORE the expensive fetch + numpy work.
    sig = None
    uid = None
    try:
        from services.cache_service import (
            risk_snapshot_cache_get,
            risk_snapshot_cache_set,
        )
        sig = _positions_signature(positions)
        uid = getattr(current_user, "id", None)
        cached = risk_snapshot_cache_get(uid, sig) if uid else None
        if cached is not None:
            return cached
    except Exception:
        # Cache layer must never break the request path. Fall through to
        # the uncached path on any failure.
        logger.debug("silent-fallback: risk_snapshot cache lookup", exc_info=True)
        sig = None
        uid = None

    tickers = [p.ticker for p in positions]
    matrix, valid, df_close = _build_returns_matrix(tickers)

    # Mark-to-market position values — best-effort.
    try:
        from services.container import realtime
        prices = realtime.get_prices_batch(tickers)
    except Exception:
        prices = {}

    # Currency normalization (CRITICAL): KR positions (.KS/.KQ) are already in
    # KRW; US positions are in USD and must be FX-converted before aggregation,
    # otherwise mixed US+KR portfolios get wrong weight/VaR/HHI.
    from services import fx_service
    fx_rate = fx_service.get_rate()  # USD → KRW, computed once

    pos_list: list[dict] = []
    total_value = 0.0
    for p in positions:
        price = (prices.get(p.ticker) or {}).get("price") or p.avg_cost or 0.0
        is_kr = p.ticker.upper().endswith(".KS") or p.ticker.upper().endswith(".KQ")
        value_native = float(price) * float(p.shares or 0)
        value = value_native if is_kr else value_native * fx_rate
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
        logger.debug("silent-fallback: _portfolio_snapshot", exc_info=True)
        pass

    state = {
        "positions":       pos_list,
        "portfolio_value": total_value,
        "daily_return":    0.0,
        "vix":             vix,
        "regime":          "TRANSITION",
        "returns_matrix":  matrix,
    }
    payload = (state, valid, matrix, df_close)

    # Populate cache on the way out. Best-effort — cache failures are silent.
    if uid and sig:
        try:
            risk_snapshot_cache_set(uid, sig, payload)
        except Exception:
            logger.debug("silent-fallback: risk_snapshot cache write", exc_info=True)

    return payload


def _score_to_status(score: int) -> str:
    if score >= 80:
        return "GREEN"
    if score >= 50:
        return "YELLOW"
    return "RED"


def _compute_cash_weight_pct(portfolio_value: float) -> tuple[float, str]:
    """Best-effort computation of cash buffer % of (cash + positions).

    Returns (cash_pct, source) where source is one of:
      - "alpaca" — Alpaca BYOK account cash
      - "kis"    — KIS BYOK account available_cash
      - "none"   — no broker connected / fetch failed → cash = 0

    Reuses existing BYOK broker infrastructure — adds zero new API calls if
    the user has no broker linked. All failures are swallowed and reported
    as cash=0 (the most conservative read for risk surfacing — RED status).

    Memory rule: feedback_no_extra_cost (2026-05-06) — no new paid endpoints.
    B-05 (2026-05-10): replaces hardcoded `cash_w_pct = 0.0` + status="GREEN".
    """
    cash_native = 0.0
    source = "none"

    # KIS cash buffer (KR users — KRW-denominated). KIS is the only supported
    # broker integration (Alpaca removed 2026-05-27).
    if source == "none":
        try:
            from services.broker.user_kis_service import (
                UserKISService,
                UserKISError,
            )
            try:
                svc = UserKISService(getattr(current_user, "id", None))
            except UserKISError:
                svc = None
            except Exception:
                svc = None
            if svc is not None:
                bal = svc.get_balance()
                if bal.get("ok"):
                    cash_val = bal.get("available_cash")
                    if cash_val is not None:
                        cash_native = float(cash_val)
                        source = "kis"
        except Exception as exc:
            logger.debug("L7 cash: kis lookup skipped (%s)", exc)

    if source == "none" or cash_native <= 0:
        return 0.0, source

    # Compute cash / (cash + positions) ratio. portfolio_value here is the
    # mark-to-market sum from _portfolio_snapshot in the user's native ticker
    # currency. For a single-broker BYOK user the units match. For mixed
    # books the ratio is a best-effort approximation that still surfaces a
    # meaningful relative magnitude (vs. the previous hardcoded 0%).
    pv = float(portfolio_value or 0.0)
    denom = pv + cash_native
    if denom <= 0:
        return 0.0, source
    pct = max(0.0, min(100.0, (cash_native / denom) * 100.0))
    return pct, source


def _cash_buffer_status(cash_w_pct: float, cfg: dict) -> str:
    """Threshold-based Cash Buffer status (B-05).

    GREEN  — cash >= bull_cash_pct (SoT from RiskDefenseSystem config)
    YELLOW — cash >= max(2%, bull_cash_pct/2)
    RED    — below YELLOW floor (insufficient buffer)

    Floors are derived rather than hardcoded so profile-specific tuning of
    bull_cash_pct (e.g., aggressive = 0%, defensive = 10%) cascades into the
    YELLOW band.
    """
    green_th = float(cfg.get("bull_cash_pct", 5))
    yellow_th = max(2.0, green_th / 2.0)
    if cash_w_pct >= green_th:
        return "GREEN"
    if cash_w_pct >= yellow_th:
        return "YELLOW"
    return "RED"


def _cash_buffer_observation(cash_w_pct: float, cfg: dict, source: str) -> str:
    """Neutral observational text for Layer 7 (no advice language)."""
    if source == "none":
        return "No broker connection — cash buffer not observable."
    status = _cash_buffer_status(cash_w_pct, cfg)
    if status == "RED":
        return "Cash buffer below soft-limit band."
    if status == "YELLOW":
        return "Cash buffer near soft-limit band."
    return "Cash buffer within band."


def _demo_summary_response() -> dict:
    """Neutral fallback for /summary when upstream data is unavailable."""
    return {
        "var_1d_pct":       0.0,
        "es_1d_pct":        0.0,
        "max_dd_90d_pct":   0.0,
        "corr_risk_index":  0.0,
        "hhi":              0.0,
        "is_demo":          True,
        "message":          "Risk data temporarily unavailable",
    }


def _demo_layers_response() -> dict:
    """Neutral fallback for /layers — 7 GREEN placeholder entries.

    Threshold strings are derived from the default RiskDefenseSystem config
    (the SoT for layer parameters), so this fallback stays in lockstep with
    the live response shape: every layer always emits  +
    .
    """
    cfg = RiskDefenseSystem.default_config()
    observed = _kst_now_str()
    layers = [
        {"no": 1, "name": "VaR Layer",          "metric_label": "Daily 1-day 95% VaR",
         "metric_value": "—", "status": "GREEN",
         "threshold": f"< {cfg['var_threshold_pct']:.1f}%",
         "observed_at_kst": observed,
         "observation": "Risk data temporarily unavailable."},
        {"no": 2, "name": "Correlation Layer",  "metric_label": "Avg pairwise correlation",
         "metric_value": "—", "status": "GREEN",
         "threshold": f"< {cfg['correlation_alert_threshold']:.2f}",
         "observed_at_kst": observed,
         "observation": "Risk data temporarily unavailable."},
        {"no": 3, "name": "VIX Regime",         "metric_label": "VIX",
         "metric_value": "—", "status": "GREEN",
         "threshold": f"< {cfg['vix_caution']:.0f} / {cfg['vix_panic']:.0f}",
         "observed_at_kst": observed,
         "observation": "Risk data temporarily unavailable."},
        {"no": 4, "name": "Tail Risk",          "metric_label": "Tail imbalance",
         "metric_value": "—", "status": "GREEN",
         "threshold": f"< {cfg['tail_imbalance_threshold']:.1f}x avg",
         "observed_at_kst": observed,
         "observation": "Risk data temporarily unavailable."},
        {"no": 5, "name": "Daily Loss Guard",   "metric_label": "Today's P&L",
         "metric_value": "0.00%", "status": "GREEN",
         "threshold": f"> -{cfg['daily_loss_limit_pct']:.1f}%",
         "observed_at_kst": observed,
         "observation": "Risk data temporarily unavailable."},
        {"no": 6, "name": "Sector Exposure",    "metric_label": "Max sector weight",
         "metric_value": "—", "status": "GREEN",
         "threshold": f"< {cfg['max_sector_pct']:.0f}%",
         "observed_at_kst": observed,
         "observation": "Risk data temporarily unavailable."},
        {"no": 7, "name": "Cash Buffer",        "metric_label": "Cash weight",
         "metric_value": "—", "status": "GREEN",
         "threshold": f"≥ {cfg['bull_cash_pct']:.0f}%",
         "observed_at_kst": observed,
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
            "hhi":              0.0,
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

        # HHI (Herfindahl-Hirschman index) — concentration metric on the
        # portfolio weight vector itself; independent of returns history,
        # so we surface it before any returns-based gating below. Single
        # asset → 1.0 (max concentration), perfectly diversified → 1/N.
        # Same calc as /api/risk/concentration so both gauges agree.
        try:
            hhi_weights = [float(p.get("weight") or 0.0) for p in state["positions"]]
            hhi = float(sum(w * w for w in hhi_weights))
            payload["hhi"] = round(hhi, 4)
        except Exception as e:
            logger.warning("risk.summary HHI compute failed: %s", e)
            payload["hhi"] = 0.0

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
            v = float(np.nanmean(c[mask]))
            # Wave-3 P2 (2026-06-10): a flat (halted) price series makes the
            # corrcoef row NaN -> nanmean NaN -> jsonify emits literal NaN =
            # invalid JSON, breaking the /risk poll. Mirror risk_layers'
            # isfinite guard.
            corr_idx = v if np.isfinite(v) else 0.0

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
        logger.exception("risk.layers failed: %s", e)
        return jsonify(_demo_layers_response())


def _risk_layers_impl():
    state, valid_tickers, matrix, _ = _portfolio_snapshot()

    n_pos_dbg = 0 if state is None else len(state.get("positions") or [])
    mshape_dbg = None if matrix is None else tuple(matrix.shape)
    logger.info(
        "risk.layers: positions=%s valid=%s matrix=%s",
        n_pos_dbg, len(valid_tickers or []), mshape_dbg,
    )

    # Resolve the user's profile-aware risk config up front. This is the SoT
    # for threshold strings; we read from rds.config rather than hard-coding
    # numbers, so updates to RiskDefenseSystem.PROFILE_DEFENSE_CONFIGS / the
    # default_config() automatically propagate to the API surface.
    rds = RiskDefenseSystem.from_profile(
        getattr(current_user, "investor_profile", "steady_accumulator")
        or "steady_accumulator"
    )
    cfg = rds.config
    observed = _kst_now_str()
    th_var      = f"< {cfg['var_threshold_pct']:.1f}%"
    th_corr     = f"< {cfg['correlation_alert_threshold']:.2f}"
    th_vix      = f"< {cfg['vix_caution']:.0f} / {cfg['vix_panic']:.0f}"
    th_tail     = f"< {cfg['tail_imbalance_threshold']:.1f}x avg"
    th_daily    = f"> -{cfg['daily_loss_limit_pct']:.1f}%"
    th_sector   = f"< {cfg['max_sector_pct']:.0f}%"
    th_cash     = f"≥ {cfg['bull_cash_pct']:.0f}%"

    # Default layers when portfolio is empty
    default_layers = [
        {"no": 1, "name": "VaR Layer",          "metric_label": "Daily 1-day 95% VaR",
         "metric_value": "—", "status": "GREEN",
         "threshold": th_var, "observed_at_kst": observed,
         "observation": "No positions under observation."},
        {"no": 2, "name": "Correlation Layer",  "metric_label": "Avg pairwise correlation",
         "metric_value": "—", "status": "GREEN",
         "threshold": th_corr, "observed_at_kst": observed,
         "observation": "No positions under observation."},
        {"no": 3, "name": "VIX Regime",         "metric_label": "VIX",
         "metric_value": "—", "status": "GREEN",
         "threshold": th_vix, "observed_at_kst": observed,
         "observation": "No VIX signal attached."},
        {"no": 4, "name": "Tail Risk",          "metric_label": "Tail imbalance",
         "metric_value": "—", "status": "GREEN",
         "threshold": th_tail, "observed_at_kst": observed,
         "observation": "No positions under observation."},
        {"no": 5, "name": "Daily Loss Guard",   "metric_label": "Today's P&L",
         "metric_value": "0.00%", "status": "GREEN",
         "threshold": th_daily, "observed_at_kst": observed,
         "observation": "Within band."},
        {"no": 6, "name": "Sector Exposure",    "metric_label": "Max sector weight",
         "metric_value": "—", "status": "GREEN",
         "threshold": th_sector, "observed_at_kst": observed,
         "observation": "No positions under observation."},
        {"no": 7, "name": "Cash Buffer",        "metric_label": "Cash weight",
         "metric_value": "—", "status": "GREEN",
         "threshold": th_cash, "observed_at_kst": observed,
         "observation": "No positions under observation."},
    ]

    if state is None:
        return jsonify(default_layers)

    # Run full check_all() for layers_triggered / defense_score. Any exception
    # here must NOT kill the whole ladder — we compute metric strings below
    # independently per-layer so even a partial failure shows real numbers
    # (was Bug A: a single layer's crash swallowed all 7 behind "—").
    try:
        actions = rds.check_all(state)
    except Exception as e:
        logger.exception("risk_layers check_all failed (partial fallback): %s", e)
        actions = {"layers_triggered": [], "defense_score": 100}

    triggered = set(actions.get("layers_triggered", []))

    # ── Compute per-layer metric values from the snapshot ──
    # Each block is independently guarded: Bug A (2026-04-24) was that a
    # single failure (e.g., shape-mismatched weights, NaN corrcoef on a
    # 1-column matrix) would bubble up and turn all 7 metric strings into
    # "—". Now each metric is computed in its own try/except; a crash in
    # one layer only blanks that one layer.
    n_pos = len(state["positions"])
    try:
        weights = np.array([p["weight"] or (1.0 / max(n_pos, 1))
                            for p in state["positions"]], dtype=float)
        if matrix is not None and weights.shape[0] != matrix.shape[1]:
            weights = np.ones(matrix.shape[1], dtype=float) / matrix.shape[1]
        s = weights.sum()
        if s > 0:
            weights = weights / s
    except Exception as e:
        logger.warning("risk_layers weights compute failed: %s", e)
        weights = (
            np.ones(matrix.shape[1], dtype=float) / matrix.shape[1]
            if matrix is not None and matrix.shape[1] > 0
            else np.array([1.0])
        )

    var_pct_str = "—"
    try:
        if matrix is not None and matrix.shape[0] >= 20 and matrix.shape[1] > 0:
            pr = matrix @ weights
            var_pct_str = f"{-float(np.percentile(pr, 5)) * 100:.2f}%"
    except Exception as e:
        logger.warning("risk_layers L1 VaR metric failed: %s", e)

    corr_str = "—"
    try:
        if matrix is not None and matrix.shape[0] >= 20 and matrix.shape[1] >= 2:
            recent = matrix[-20:]
            c = np.corrcoef(recent.T)
            mask = ~np.eye(c.shape[0], dtype=bool)
            corr_val = float(np.nanmean(c[mask]))
            if np.isfinite(corr_val):
                corr_str = f"{corr_val:.2f}"
    except Exception as e:
        logger.warning("risk_layers L2 Correlation metric failed: %s", e)

    vix = state.get("vix")
    vix_str = f"{vix:.1f}" if isinstance(vix, (int, float)) else "—"

    daily_ret = state.get("daily_return", 0.0)

    # Sector concentration — all sectors currently "Unknown" (no sector data),
    # so we fall back to showing the largest single position weight.
    try:
        max_w = max((p.get("weight") or 0.0 for p in state["positions"]), default=0.0)
        sector_str = f"{max_w * 100:.0f}% max position"
    except Exception as e:
        logger.warning("risk_layers L6 Sector metric failed: %s", e)
        sector_str = "—"

    # ── Layer 7: Cash Buffer — real calculation (B-05, 2026-05-10) ──
    # Source: bug-hunter wave found cash_w_pct hardcoded 0.0 + status="GREEN".
    # Now: try BYOK broker cash balance (Alpaca → KIS), fall back to 0 only if
    # both unavailable. Status uses bull_cash_pct config (SoT) as the GREEN
    # threshold so risk_defense.py tuning auto-propagates here.
    cash_w_pct, cash_source = _compute_cash_weight_pct(state.get("portfolio_value", 0.0))

    layers = [
        {
            "no": 1, "name": "VaR Layer",
            "metric_label": "Daily 1-day 95% VaR",
            "metric_value": var_pct_str,
            "threshold": th_var,
            "observed_at_kst": observed,
            "status": "RED" if "L1_VAR" in triggered else "GREEN",
            "observation": "VaR observed above soft limit." if "L1_VAR" in triggered
                            else "Within historical band.",
        },
        {
            "no": 2, "name": "Correlation Layer",
            "metric_label": "Avg pairwise correlation",
            "metric_value": corr_str,
            "threshold": th_corr,
            "observed_at_kst": observed,
            "status": "YELLOW" if "L2_CORRELATION" in triggered else "GREEN",
            "observation": "Observed elevated pairwise correlation."
                           if "L2_CORRELATION" in triggered
                           else "Diversification within expected band.",
        },
        {
            "no": 3, "name": "VIX Regime",
            "metric_label": "VIX",
            "metric_value": vix_str,
            "threshold": th_vix,
            "observed_at_kst": observed,
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
            "threshold": th_tail,
            "observed_at_kst": observed,
            "status": "YELLOW" if "L4_TAIL_RISK" in triggered else "GREEN",
            "observation": "Left-tail concentration observed."
                           if "L4_TAIL_RISK" in triggered
                           else "Balanced right/left tail.",
        },
        {
            "no": 5, "name": "Daily Loss Guard",
            "metric_label": "Today's P&L",
            "metric_value": f"{daily_ret:.2f}%",
            "threshold": th_daily,
            "observed_at_kst": observed,
            "status": "RED" if "L5_DAILY_LOSS" in triggered else "GREEN",
            "observation": "Today's loss above soft limit."
                           if "L5_DAILY_LOSS" in triggered
                           else "Within daily loss band.",
        },
        {
            "no": 6, "name": "Sector Exposure",
            "metric_label": "Max position weight",
            "metric_value": sector_str,
            "threshold": th_sector,
            "observed_at_kst": observed,
            "status": "YELLOW" if "L6_SECTOR_CONCENTRATION" in triggered else "GREEN",
            "observation": "Position concentration above soft-limit band."
                           if "L6_SECTOR_CONCENTRATION" in triggered
                           else "Concentration within band.",
        },
        {
            "no": 7, "name": "Cash Buffer",
            "metric_label": "Cash weight",
            "metric_value": f"{cash_w_pct:.0f}%",
            "threshold": th_cash,
            "observed_at_kst": observed,
            "status": _cash_buffer_status(cash_w_pct, cfg),
            "observation": _cash_buffer_observation(cash_w_pct, cfg, cash_source),
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
            logger.warning("corr compute failed: %s", e)
            return jsonify({"labels": [], "matrix": []})

        matrix_out = [[round(float(v), 2) if np.isfinite(v) else 0.0 for v in row]
                      for row in c]
        return jsonify({"labels": labels, "matrix": matrix_out})
    except Exception as e:
        logger.warning("risk.correlation failed: %s", e, exc_info=True)
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
        logger.warning("risk.rolling_var failed: %s", e, exc_info=True)
        return jsonify([])



@risk_bp.route("/timeline")
@api_auth
@legal_scrub_response
def risk_timeline():
    """Daily composite-risk series for the user's portfolio.

    Query
      days (int, default 90, range 30..180)

    Response (200)
      [
        {date, composite, vix, var95, max_dd, sharpe},
        ...
      ]

    All values are observational; status banding is NOT included (see
    `/api/risk/layers` for status). When the portfolio is empty or the
    returns matrix is too short, returns `[]` — the FE risk-timeline hook
    treats this as "no data yet" and renders a placeholder.

    Implementation notes
      • Reuses `_portfolio_snapshot()` so the 5-minute cache covers this
        endpoint too (no extra FMP cost).
      • Composite = weighted blend of (VaR severity, max-DD severity,
        VIX severity) on a 0-100 scale, lower = calmer. The exact weights
        match the 7-Layer Risk Defense weighting (1/3, 1/3, 1/3 here is
        a simplification — the live `/api/risk/summary` HHI/correlation
        layers are not back-castable so they are omitted on the timeline).
      • Rolling windows: 20-day for VaR, 90-day for max-DD, full window
        for Sharpe. Sharpe annualised at √252.
      • VIX is point-in-time (snapshot) not historical — surfaced as a
        flat reference line so the FE can overlay regime banding.
    """
    try:
        days_param = int(request.args.get("days", 90))
    except (TypeError, ValueError):
        days_param = 90
    days_param = max(30, min(180, days_param))

    try:
        state, _, matrix, df_close = _portfolio_snapshot()
    except Exception as exc:
        logger.warning("risk.timeline snapshot failed: %s", exc, exc_info=True)
        return jsonify([])

    if state is None or matrix is None or matrix.shape[0] < 25 or df_close is None:
        return jsonify([])

    try:
        import pandas as pd  # noqa: F401  (already a transitive dep)
        n_pos = len(state["positions"])
        weights = np.array(
            [p["weight"] or (1.0 / max(n_pos, 1)) for p in state["positions"]],
            dtype=float,
        )
        if weights.shape[0] != matrix.shape[1]:
            weights = np.ones(matrix.shape[1], dtype=float) / matrix.shape[1]
        s = weights.sum()
        if s > 0:
            weights = weights / s

        # Daily portfolio returns
        port_rets = matrix @ weights

        window = 20
        if len(port_rets) < window + 5:
            return jsonify([])

        # Align with the tail of df_close index for dates
        try:
            all_dates = list(df_close.index[-len(port_rets):])
        except Exception:
            all_dates = [
                datetime.now(timezone.utc) - timedelta(days=i)
                for i in range(len(port_rets) - 1, -1, -1)
            ]

        vix_snapshot = state.get("vix")

        # Cumulative equity series for max-DD calc
        cum = np.cumprod(1.0 + port_rets)

        out: list[dict] = []
        # Iterate from index `window` so the rolling VaR window has data.
        for i in range(window, len(port_rets)):
            w = port_rets[i - window:i]

            # 95% historical VaR (1-day) as positive percent of NAV
            var_pct = -float(np.percentile(w, 5)) * 100.0

            # Max drawdown over the last 90 trading days ending at i
            dd_lookback_start = max(0, i - 90)
            seg = cum[dd_lookback_start:i + 1]
            if len(seg) >= 2:
                peak = np.maximum.accumulate(seg)
                # Avoid division by zero
                with np.errstate(divide="ignore", invalid="ignore"):
                    dd_series = (seg - peak) / peak
                max_dd = float(np.nanmin(dd_series)) * 100.0  # negative %
            else:
                max_dd = 0.0

            # Sharpe annualised over the rolling window
            std = float(np.std(w, ddof=1)) if len(w) > 1 else 0.0
            mean_r = float(np.mean(w))
            if std > 0:
                # Subtract risk-free (rf=0.045 annual) for consistency with the
                # benchmark/analytics endpoint and risk_metrics.
                rf_daily = 0.045 / 252
                sharpe = ((mean_r - rf_daily) / std) * (252 ** 0.5)
            else:
                sharpe = 0.0

            # Composite (0-100, higher = more stress).
            # Heuristic mapping:
            #   VaR  : 1% → 10pts, 5% → 50pts (linear, capped 100)
            #   DD   : 5% → 25pts, 20% → 100pts (use abs(max_dd))
            #   VIX  : 15 → 10pts, 30 → 70pts, 40+ → 100pts
            var_score = max(0.0, min(100.0, var_pct * 10.0))
            dd_score = max(0.0, min(100.0, abs(max_dd) * 5.0))
            if vix_snapshot is None:
                vix_score = 30.0  # neutral midpoint when VIX unavailable
                vix_emit = None
            else:
                vix_score = max(0.0, min(100.0, (float(vix_snapshot) - 10.0) * 5.0))
                vix_emit = round(float(vix_snapshot), 2)

            composite = round((var_score + dd_score + vix_score) / 3.0, 1)

            d = all_dates[i]
            try:
                date_str = d.strftime("%Y-%m-%d")
            except Exception:
                date_str = str(d)[:10]

            out.append({
                "date":      date_str,
                "composite": composite,
                "vix":       vix_emit,
                "var95":     round(var_pct, 2),
                "max_dd":    round(max_dd, 2),
                "sharpe":    round(sharpe, 2),
            })

        # Trim to requested window (caller asks for `days_param` calendar
        # days; this is trading-day-trimmed which is the FE-friendly shape).
        return jsonify(out[-days_param:])
    except Exception as exc:
        logger.warning("risk.timeline compute failed: %s", exc, exc_info=True)
        return jsonify([])


@risk_bp.route("/concentration")
@api_auth
@legal_scrub_response
def risk_concentration():
    """Portfolio concentration metrics — HHI, top positions, sector buckets.

    Empty portfolio → 200 OK with empty arrays (NOT 404). Frontend Risk
    Board CONCENTRATION widget reads  for the gauge and 
    for the position rail. Sector resolution is best-effort:
      - KR tickers: services.kr_stock_registry.get_sector
      - US tickers: fmp_service.get_profile().sector (cached 7 days)
      - Unresolved: bucketed under "Unclassified"

    Response shape:
        {
          "hhi":            float,            # 0..1 (sum of weight^2)
          "hhi_label":      str,              # "low" | "medium" | "high"
          "top_positions":  [{ticker, weight, sector}],
          "sectors":        [{name, weight, count}],
          "position_count": int,
          "as_of":          ISO-8601 UTC,
        }
    """
    from datetime import datetime, timezone
    try:
        state, _, _, _ = _portfolio_snapshot()
        as_of = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        if state is None or not state.get("positions"):
            return jsonify({
                "hhi":            0.0,
                "hhi_label":      "low",
                "top_positions":  [],
                "sectors":        [],
                "position_count": 0,
                "as_of":          as_of,
            })

        positions = state["positions"]
        # Resolve sectors best-effort. KR registry first (no network), then
        # FMP profile (cached). Failures bucket as "Unclassified".
        try:
            from services.kr_stock_registry import get_sector as _kr_sector
        except Exception:
            _kr_sector = lambda _t: None  # type: ignore
        try:
            from services.data import fmp as _fmp
        except Exception:
            _fmp = None

        def _resolve_sector(t: str) -> str:
            try:
                is_kr = t.endswith(".KS") or t.endswith(".KQ")
                kr = _kr_sector(t) if is_kr else None
                if kr:
                    return kr
                # KR guard: FMP has no KRX coverage, so get_profile() returns {}
                # for .KS/.KQ while still burning an FMP call. Only hit FMP for
                # non-KR tickers; KR with no curated sector → Unclassified.
                if not is_kr and _fmp is not None:
                    prof = _fmp.get_profile(t) or {}
                    sec = prof.get("sector")
                    if isinstance(sec, str) and sec.strip():
                        return sec.strip()
            except Exception:
                logger.debug("silent-fallback: _resolve_sector", exc_info=True)
                pass
            return "Unclassified"

        # HHI (Herfindahl-Hirschman) — sum of squared weights, range 0..1.
        # Single-position book → 1.0 (max concentration).
        weights = [float(p.get("weight") or 0.0) for p in positions]
        hhi = sum(w * w for w in weights)
        if hhi >= 0.25:
            hhi_label = "high"
        elif hhi >= 0.15:
            hhi_label = "medium"
        else:
            hhi_label = "low"

        # Top positions sorted by weight desc.
        ranked = sorted(positions, key=lambda p: float(p.get("weight") or 0.0), reverse=True)
        top_positions = []
        sector_buckets: dict[str, dict] = {}
        for p in ranked:
            t = p.get("ticker") or ""
            w = float(p.get("weight") or 0.0)
            sec = _resolve_sector(t)
            top_positions.append({
                "ticker": t,
                "weight": round(w, 4),
                "sector": sec,
            })
            bucket = sector_buckets.setdefault(sec, {"name": sec, "weight": 0.0, "count": 0})
            bucket["weight"] += w
            bucket["count"] += 1

        sectors = sorted(sector_buckets.values(), key=lambda s: s["weight"], reverse=True)
        for s in sectors:
            s["weight"] = round(s["weight"], 4)

        return jsonify({
            "hhi":            round(hhi, 4),
            "hhi_label":      hhi_label,
            "top_positions":  top_positions[:10],
            "sectors":        sectors,
            "position_count": len(positions),
            "as_of":          as_of,
        })
    except Exception as e:
        logger.warning("risk.concentration failed: %s", e, exc_info=True)
        # Fail-safe: empty payload (200) so the gauge shows '—' rather than 404.
        return jsonify({
            "hhi":            0.0,
            "hhi_label":      "low",
            "top_positions":  [],
            "sectors":        [],
            "position_count": 0,
            "as_of":          datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "message":        "Concentration data temporarily unavailable",
        })
