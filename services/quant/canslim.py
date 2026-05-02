"""CAN SLIM Screener -- William O'Neil's 7-factor stock selection system.

Fundamental inputs pulled from FMP (/income-statement, /institutional-ownership)
with EDGAR fallback on 402/plan-gated errors. Price/volume inputs supplied by
the caller (engine or quant route).

Pure mathematical screening; not investment advice.
"""

import logging
import numpy as np

logger = logging.getLogger(__name__)


def _safe_growth(curr, prev):
    """Compute YoY growth % with safe handling of None/zero/negative base.

    Returns float or None. Uses abs(prev) in the denominator so a swing
    from negative to positive still produces a finite, interpretable number.
    """
    if curr is None or prev is None:
        return None
    try:
        curr_f = float(curr)
        prev_f = float(prev)
    except (TypeError, ValueError):
        return None
    if prev_f == 0:
        return None
    return ((curr_f - prev_f) / abs(prev_f)) * 100.0


def _check_current_eps(ticker):
    """C -- Current quarterly EPS YoY growth >= 25%.

    Compares the most recent quarterly EPS to the same quarter one year ago
    (4 quarters back, which is seasonally aligned).

    Returns dict: {"value": growth_pct, "pass": bool, "source": ...}
                  or {"value": None, "pass": False, "reason": ...}.
    """
    try:
        import fmp_service as fmp
    except Exception as e:
        logger.warning(f"canslim C: fmp_service unavailable: {e}")
        return {"value": None, "pass": False, "reason": "fmp_service unavailable"}

    try:
        quarterly = fmp.get_quarterly_eps(ticker, quarters=6)
    except Exception as e:
        logger.warning(f"canslim C fetch failed for {ticker}: {e}")
        return {"value": None, "pass": False, "reason": "fetch error"}

    if not quarterly or len(quarterly) < 5:
        return {"value": None, "pass": False, "reason": "insufficient quarterly data"}

    current_eps = quarterly[0].get("eps")
    yoy_eps = quarterly[4].get("eps")  # 4 quarters back = same fiscal quarter prior year
    growth = _safe_growth(current_eps, yoy_eps)
    if growth is None:
        return {"value": None, "pass": False, "reason": "prior-year EPS is zero or missing"}

    return {
        "value": round(growth, 2),
        "threshold": 25,
        "pass": growth >= 25.0,
        "current_eps": current_eps,
        "yoy_eps": yoy_eps,
        "current_period": f"{quarterly[0].get('period', '')} {quarterly[0].get('calendarYear', '')}".strip(),
        "source": "FMP /income-statement (quarter)",
    }


def _check_annual_eps(ticker):
    """A -- Annual EPS up 3 consecutive years, each >= 25%.

    Requires 4 most-recent fiscal years (so we can measure three YoY deltas).

    Returns dict with per-year growth list + pass flag.
    """
    try:
        import fmp_service as fmp
    except Exception as e:
        logger.warning(f"canslim A: fmp_service unavailable: {e}")
        return {"value": None, "pass": False, "reason": "fmp_service unavailable"}

    try:
        annual = fmp.get_annual_eps(ticker, years=4)
    except Exception as e:
        logger.warning(f"canslim A fetch failed for {ticker}: {e}")
        return {"value": None, "pass": False, "reason": "fetch error"}

    if not annual or len(annual) < 4:
        return {"value": None, "pass": False, "reason": "need 4y of annual EPS"}

    # annual[0] = most recent FY, annual[3] = 3y ago
    growths = []
    for i in range(3):
        curr = annual[i].get("eps")
        prev = annual[i + 1].get("eps")
        g = _safe_growth(curr, prev)
        if g is None:
            return {
                "value": None,
                "pass": False,
                "reason": f"EPS missing/zero between {annual[i].get('date')} and {annual[i+1].get('date')}",
            }
        growths.append(round(g, 2))

    all_25 = all(g >= 25.0 for g in growths)
    return {
        "value": growths,               # [latest, mid, oldest] YoY % growths
        "threshold": 25,
        "pass": all_25,
        "years": [a.get("date") for a in annual[:4]],
        "source": "FMP /income-statement (annual)",
    }


def _check_institutional(ticker, closes):
    """I -- Institutional sponsorship.

    Primary path: FMP institutional ownership summary. Passes when the
    institution count grew QoQ *or* ownership % increased.

    Fallback: price/volume momentum proxy (3-month return > 5% AND volume
    surge in the recent 20-day window). Marked as proxy in the result so the
    frontend can surface the caveat.
    """
    proxy_result = None
    # Compute proxy ahead of time so we can fall back gracefully.
    if closes is not None and len(closes) >= 63:
        ret_3m = (closes[-1] / max(closes[-63], 1e-8)) - 1
        proxy_pass = bool(ret_3m > 0.05)
        proxy_result = {
            "value": round(float(ret_3m * 100), 2),
            "threshold": 5,
            "pass": proxy_pass,
            "method": "PROXY",
            "note": "3-month price momentum (institutional data unavailable)",
        }

    try:
        import fmp_service as fmp
        data = fmp.get_institutional_ownership(ticker)
    except Exception as e:
        logger.warning(f"canslim I fetch failed for {ticker}: {e}")
        data = None

    if data and data.get("available"):
        holder_count = data.get("holder_count")
        change = data.get("ownership_change")
        own_pct = data.get("ownership_pct")

        # Pass when we see net accumulation:
        # ownership_change > 0 (QoQ % increase) OR sufficient holder breadth.
        pass_flag = False
        reasons = []
        if change is not None:
            pass_flag = change > 0
            reasons.append(f"QoQ ownership change: {change:+.2f}pp")
        elif holder_count is not None:
            # With only holder_count, use a soft threshold (>=50 institutions).
            pass_flag = holder_count >= 50
            reasons.append(f"{holder_count} institutional holders")

        return {
            "value": own_pct,
            "holder_count": holder_count,
            "ownership_change": change,
            "pass": bool(pass_flag),
            "method": "FMP",
            "source": data.get("source"),
            "note": "; ".join(reasons) if reasons else None,
        }

    # Fallback to proxy
    if proxy_result is not None:
        return proxy_result

    return {"value": None, "pass": False, "reason": "no institutional or price data"}


class CANSLIMScreener:
    """
    C = Current quarterly EPS YoY growth >= 25%   (FMP quarterly income)
    A = Annual EPS 3 consecutive years >= 25%     (FMP annual income)
    N = New highs (within 5% of 52-week high)
    S = Supply/demand (volume surge + float)
    L = Leader (1-month return > 0)
    I = Institutional sponsorship (FMP ownership; price/volume proxy fallback)
    M = Market direction (regime BULL/MILD_BULL)
    """

    @classmethod
    def score(cls, ticker, closes, volumes, fundamentals=None, regime=None, float_shares=None):
        """Score a stock 0-7 on CAN SLIM criteria.

        Signature preserved for the existing caller in routes/quant.py.
        ``fundamentals`` (EDGAR) is still accepted as a last-resort fallback
        for C/A when FMP is unavailable.

        Returns: dict with score, per-criterion pass/fail + details.
        """

        results = {"ticker": ticker, "total_score": 0, "max_score": 7, "criteria": {}}

        # ── C: Current quarterly EPS YoY ≥ 25% ──────────────────
        c = _check_current_eps(ticker)
        if c.get("value") is None and fundamentals:
            # EDGAR fallback: use revenue_growth as a degraded proxy.
            rg = fundamentals.get("revenue_growth")
            if rg is not None:
                c = {
                    "value": rg,
                    "threshold": 25,
                    "pass": bool(rg is not None and rg > 25),
                    "method": "EDGAR_FALLBACK",
                    "note": "Using revenue_growth (EDGAR) — quarterly EPS unavailable",
                }
        c["name"] = "Current Quarterly EPS Growth"
        results["criteria"]["C"] = c
        if c.get("pass"):
            results["total_score"] += 1

        # ── A: Annual EPS 3y consecutive ≥ 25% ──────────────────
        a = _check_annual_eps(ticker)
        if a.get("value") is None and fundamentals:
            # EDGAR fallback: single-year revenue-up-and-positive check.
            rg = fundamentals.get("revenue_growth")
            rev = fundamentals.get("revenue")
            prev = fundamentals.get("prev_revenue")
            if rg is not None and rev is not None and prev is not None:
                a = {
                    "value": rg,
                    "threshold": 25,
                    "pass": bool(rg > 0 and rev > prev),
                    "method": "EDGAR_FALLBACK",
                    "note": "Using 1y revenue trend (EDGAR) — multi-year EPS unavailable",
                }
        a["name"] = "Annual EPS Growth (3y)"
        results["criteria"]["A"] = a
        if a.get("pass"):
            results["total_score"] += 1

        # ── N: Near 52-week high (within 5%) ────────────────────
        n_pass = False
        if len(closes) >= 252:
            high_52w = np.max(closes[-252:])
            ratio = closes[-1] / high_52w if high_52w > 0 else 0
            n_pass = bool(ratio > 0.95)
            results["criteria"]["N"] = {
                "name": "Near 52-Week High",
                "ratio": round(float(ratio), 4),
                "pass": n_pass,
            }
        else:
            results["criteria"]["N"] = {
                "name": "Near 52-Week High",
                "pass": False,
                "reason": "Insufficient history (need 252 bars)",
            }
        if n_pass:
            results["total_score"] += 1

        # ── S: Supply/demand (volume surge + float) ─────────────
        s_score = 0.0
        s_details = {"name": "Supply/Demand"}
        if len(volumes) >= 20:
            avg_vol = np.mean(volumes[-20:])
            vol_ratio = volumes[-1] / avg_vol if avg_vol > 0 else 0
            if vol_ratio > 1.5:
                s_score += 1
            s_details["vol_ratio"] = round(float(vol_ratio), 2)

        _float = float_shares
        if _float is None and fundamentals:
            _float = fundamentals.get("float_shares") or fundamentals.get("floatShares")
        if _float is not None:
            try:
                _float = float(_float)
            except (TypeError, ValueError):
                _float = None
        if _float and _float > 0:
            if _float < 100_000_000:
                s_score += 1
            elif _float < 500_000_000:
                s_score += 0.5
            s_details["float_shares"] = int(_float)
            s_details["float_category"] = (
                "tight" if _float < 100_000_000
                else "moderate" if _float < 500_000_000
                else "large"
            )

        s_pass = bool(s_score >= 1)
        s_details["sub_score"] = float(s_score)
        s_details["pass"] = s_pass
        results["criteria"]["S"] = s_details
        if s_pass:
            results["total_score"] += 1

        # ── L: Leader (1-month return > 0) ──────────────────────
        l_pass = False
        if len(closes) >= 21:
            ret_1m = (closes[-1] / max(closes[-21], 1e-8)) - 1
            l_pass = bool(ret_1m > 0)
            results["criteria"]["L"] = {
                "name": "Sector Leader",
                "return_1m": round(float(ret_1m * 100), 2),
                "pass": l_pass,
            }
        else:
            results["criteria"]["L"] = {"name": "Sector Leader", "pass": False}
        if l_pass:
            results["total_score"] += 1

        # ── I: Institutional sponsorship ────────────────────────
        i = _check_institutional(ticker, closes)
        i["name"] = "Institutional Sponsorship"
        results["criteria"]["I"] = i
        if i.get("pass"):
            results["total_score"] += 1

        # ── M: Market direction ─────────────────────────────────
        m_pass = False
        if regime:
            m_pass = regime in ("BULL", "MILD_BULL")
            results["criteria"]["M"] = {
                "name": "Market Direction",
                "regime": regime,
                "pass": m_pass,
            }
        else:
            results["criteria"]["M"] = {"name": "Market Direction", "pass": False}
        if m_pass:
            results["total_score"] += 1

        # ── Overall rating ──────────────────────────────────────
        score = results["total_score"]
        if score >= 6:
            results["rating"] = "STRONG"
        elif score >= 4:
            results["rating"] = "MODERATE"
        elif score >= 2:
            results["rating"] = "WEAK"
        else:
            results["rating"] = "AVOID"

        return results
