"""CAN SLIM Screener -- William O'Neil's 7-factor stock selection system.

Fundamental inputs pulled from FMP (/income-statement, /institutional-ownership)
with EDGAR fallback on 402/plan-gated errors. Price/volume inputs supplied by
the caller (engine or quant route).

Pure mathematical screening; not investment advice.

KR ticker policy (2026-05-17 Wave C-4):
    .KS / .KQ tickers route through FMP, which does not cover Korean fundamentals
    (income statement / institutional ownership endpoints return empty). Instead
    of silently failing C/A/I with reason="fetch error" — which the prior code did
    and which made KR scores systematically low for no diagnosable reason — we now
    short-circuit with method="UNAVAILABLE" + an explicit reason. Frontend can
    surface "N/A" rather than show a misleading red "fail". Future KIS API
    integration is tracked separately.
"""

import logging
import math

import numpy as np

logger = logging.getLogger(__name__)


def _is_kr_ticker(ticker):
    """Return True for Korean exchange tickers (.KS / .KQ).

    Used to short-circuit C/A/I factors which depend on FMP fundamental
    endpoints that have zero KR coverage.
    """
    if not ticker:
        return False
    t = ticker.upper()
    return t.endswith(".KS") or t.endswith(".KQ")


def _kr_unavailable(factor_letter):
    """Standard payload for KR tickers on FMP-dependent factors."""
    return {
        "value": None,
        "pass": None,  # Tri-state: None = N/A, not False
        "method": "UNAVAILABLE",
        "reason": (
            f"KR fundamental data not supported for {factor_letter} "
            "(FMP coverage gap; KIS integration tracked separately)"
        ),
    }


def _safe_growth(curr, prev):
    """Compute YoY growth % with safe handling of None/zero/negative base/NaN.

    Returns float or None. Uses abs(prev) in the denominator so a swing
    from negative to positive still produces a finite, interpretable number.

    NaN guard (2026-05-17 P3-02): float('nan') silently coerces through
    float() and produces a NaN growth value that breaks JSON serialization
    downstream. Detect via math.isnan and return None.
    """
    if curr is None or prev is None:
        return None
    try:
        curr_f = float(curr)
        prev_f = float(prev)
    except (TypeError, ValueError):
        logger.debug("silent-fallback: _safe_growth", exc_info=True)
        return None
    if math.isnan(curr_f) or math.isnan(prev_f):
        return None
    if prev_f == 0:
        return None
    return ((curr_f - prev_f) / abs(prev_f)) * 100.0


def _find_yoy_quarter(quarterly_data, target_quarter):
    """Locate the same fiscal period from one calendar year prior.

    The prior implementation assumed ``quarterly[4]`` was always seasonally
    aligned with ``quarterly[0]`` — which silently breaks whenever FMP omits a
    quarter (restatements, late filers, calendar/fiscal-year shifts). We now
    match on (calendarYear - 1, period) explicitly.

    Args:
        quarterly_data: list of dicts most-recent-first from
            ``fmp.get_quarterly_eps``.
        target_quarter: the reference quarter dict (typically ``quarterly[0]``).

    Returns the matching quarter dict or None if no exact match is found.
    """
    if not target_quarter:
        return None
    target_year = target_quarter.get("calendarYear")
    target_period = target_quarter.get("period")  # 'Q1' .. 'Q4'
    if target_year is None or not target_period:
        return None
    try:
        target_year = int(target_year)
    except (TypeError, ValueError):
        return None
    for q in quarterly_data:
        try:
            q_year = int(q.get("calendarYear")) if q.get("calendarYear") is not None else None
        except (TypeError, ValueError):
            continue
        if q_year == target_year - 1 and q.get("period") == target_period:
            return q
    return None


def _check_current_eps(ticker):
    """C -- Current quarterly EPS YoY growth >= 25%.

    Compares the most recent quarterly EPS to the *same fiscal quarter* one
    calendar year ago (matched by (calendarYear-1, period), not list index).

    Returns dict: {"value": growth_pct, "pass": bool, "source": ...}
                  or {"value": None, "pass": False, "reason": ...}.
    """
    if _is_kr_ticker(ticker):
        return _kr_unavailable("C")

    try:
        from services.data import fmp
    except Exception as e:
        logger.warning("canslim C: fmp_service unavailable: %s", e)
        return {"value": None, "pass": False, "reason": "fmp_service unavailable"}

    try:
        quarterly = fmp.get_quarterly_eps(ticker, quarters=6)
    except Exception as e:
        logger.warning("canslim C fetch failed for %s: %s", ticker, e)
        return {"value": None, "pass": False, "reason": "fetch error"}

    if not quarterly or len(quarterly) < 5:
        return {"value": None, "pass": False, "reason": "insufficient quarterly data"}

    current_q = quarterly[0]
    yoy_q = _find_yoy_quarter(quarterly, current_q)
    if yoy_q is None:
        return {
            "value": None,
            "pass": False,
            "reason": (
                f"no seasonally-aligned prior-year quarter found for "
                f"{current_q.get('period')} {current_q.get('calendarYear')}"
            ),
        }

    current_eps = current_q.get("eps")
    yoy_eps = yoy_q.get("eps")
    growth = _safe_growth(current_eps, yoy_eps)
    if growth is None:
        return {"value": None, "pass": False, "reason": "prior-year EPS is zero or missing"}

    return {
        "value": round(growth, 2),
        "threshold": 25,
        "pass": growth >= 25.0,
        "current_eps": current_eps,
        "yoy_eps": yoy_eps,
        "current_period": f"{current_q.get('period', '')} {current_q.get('calendarYear', '')}".strip(),
        "yoy_period": f"{yoy_q.get('period', '')} {yoy_q.get('calendarYear', '')}".strip(),
        "source": "FMP /income-statement (quarter)",
    }


def _check_annual_eps(ticker):
    """A -- Annual EPS up 3 consecutive years, each >= 25%.

    Requires 4 most-recent fiscal years (so we can measure three YoY deltas).

    Returns dict with per-year growth list + pass flag.
    """
    if _is_kr_ticker(ticker):
        return _kr_unavailable("A")

    try:
        from services.data import fmp
    except Exception as e:
        logger.warning("canslim A: fmp_service unavailable: %s", e)
        return {"value": None, "pass": False, "reason": "fmp_service unavailable"}

    try:
        annual = fmp.get_annual_eps(ticker, years=4)
    except Exception as e:
        logger.warning("canslim A fetch failed for %s: %s", ticker, e)
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
    if _is_kr_ticker(ticker):
        return _kr_unavailable("I")

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
        from services.data import fmp
        data = fmp.get_institutional_ownership(ticker)
    except Exception as e:
        logger.warning("canslim I fetch failed for %s: %s", ticker, e)
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

        # ``max_score`` decrements by 1 for every N/A factor (pass=None) so the
        # rating tier reflects the *applicable* checks. Without this, KR tickers
        # would systematically AVOID because 3 N/A factors are 3 silent failures.
        results = {"ticker": ticker, "total_score": 0, "max_score": 7, "na_count": 0, "criteria": {}}

        def _accumulate(letter, payload):
            results["criteria"][letter] = payload
            p = payload.get("pass")
            if p is None:
                # N/A — drop from denominator
                results["max_score"] -= 1
                results["na_count"] += 1
            elif p:
                results["total_score"] += 1

        # ── C: Current quarterly EPS YoY ≥ 25% ──────────────────
        c = _check_current_eps(ticker)
        # EDGAR fallback only when C is hard-fail (value=None, pass=False).
        # KR N/A short-circuits (pass=None) and should NOT fall through to
        # EDGAR — EDGAR has no KR coverage either.
        if c.get("value") is None and c.get("pass") is False and fundamentals:
            # EDGAR fallback: use revenue_growth as a degraded proxy.
            # Net income guard added 2026-05-17 P2-03: revenue growth without
            # positive earnings is not a CAN SLIM C-factor pass.
            rg = fundamentals.get("revenue_growth")
            net_income = fundamentals.get("net_income")
            if rg is not None:
                rg_pass = bool(rg > 25 and (net_income is None or net_income > 0))
                c = {
                    "value": rg,
                    "threshold": 25,
                    "pass": rg_pass,
                    "method": "EDGAR_REVENUE_PROXY",
                    "note": (
                        "Using revenue_growth (EDGAR) — quarterly EPS unavailable. "
                        "Requires revenue growth >25% AND net income >0."
                    ),
                    "net_income": net_income,
                }
        c["name"] = "Current Quarterly EPS Growth"
        _accumulate("C", c)

        # ── A: Annual EPS 3y consecutive ≥ 25% ──────────────────
        a = _check_annual_eps(ticker)
        if a.get("value") is None and a.get("pass") is False and fundamentals:
            # EDGAR fallback: single-year revenue-up-and-positive check.
            rg = fundamentals.get("revenue_growth")
            rev = fundamentals.get("revenue")
            prev = fundamentals.get("prev_revenue")
            if rg is not None and rev is not None and prev is not None:
                a = {
                    "value": rg,
                    "threshold": 25,
                    "pass": bool(rg > 0 and rev > prev),
                    "method": "EDGAR_REVENUE_PROXY",
                    "note": "Using 1y revenue trend (EDGAR) — multi-year EPS unavailable",
                }
        a["name"] = "Annual EPS Growth (3y)"
        _accumulate("A", a)

        # ── N: Near 52-week high (within 5%) ────────────────────
        if len(closes) >= 252:
            high_52w = np.max(closes[-252:])
            ratio = closes[-1] / high_52w if high_52w > 0 else 0
            n_pass = bool(ratio > 0.95)
            n_payload = {
                "name": "Near 52-Week High",
                "ratio": round(float(ratio), 4),
                "pass": n_pass,
            }
        else:
            n_payload = {
                "name": "Near 52-Week High",
                "pass": False,
                "reason": "Insufficient history (need 252 bars)",
            }
        _accumulate("N", n_payload)

        # ── S: Supply/demand (volume surge + float) ─────────────
        # 2026-05-17 P2-02: average excludes today (volumes[-21:-1]).
        # Including today in the denominator dampens the ratio whenever today
        # is itself a surge, which is exactly the case CAN SLIM is designed
        # to detect. Needs >=21 bars now (one extra) for the same window.
        s_score = 0.0
        s_details = {"name": "Supply/Demand"}
        if len(volumes) >= 21:
            avg_vol = np.mean(volumes[-21:-1])
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
        _accumulate("S", s_details)

        # ── L: Leader — 1-month positive return ─────────────────
        # NOTE: This is a momentum heuristic (1-month return > 0), NOT a true
        # relative-strength-vs-sector comparison. The marketing page intentionally
        # describes it as "1-month positive return" so wording matches behaviour.
        # A future PR may introduce a real sector benchmark (FMP /profile industry
        # + sector ETF universe), at which point both code and copy should change
        # together.
        if len(closes) >= 21:
            ret_1m = (closes[-1] / max(closes[-21], 1e-8)) - 1
            l_pass = bool(ret_1m > 0)
            l_payload = {
                "name": "Leader (1m Momentum)",
                "return_1m": round(float(ret_1m * 100), 2),
                "pass": l_pass,
                "method": "1M_RETURN",
                "note": "1-month positive return (momentum proxy, not sector-relative)",
            }
        else:
            l_payload = {
                "name": "Leader (1m Momentum)",
                "pass": False,
                "reason": "Insufficient history (need 21 bars)",
            }
        _accumulate("L", l_payload)

        # ── I: Institutional sponsorship ────────────────────────
        i = _check_institutional(ticker, closes)
        i["name"] = "Institutional Sponsorship"
        _accumulate("I", i)

        # ── M: Market direction ─────────────────────────────────
        # ``regime`` MUST be derived from a market index (^GSPC for US, ^KS11 for
        # KR) by the caller, not from the candidate ticker's own price series.
        # Passing per-ticker regime here previously made every uptrending stock
        # auto-pass M, defeating the point of the market filter.
        if regime:
            m_pass = regime in ("BULL", "MILD_BULL")
            m_payload = {
                "name": "Market Direction",
                "regime": regime,
                "pass": m_pass,
            }
        else:
            m_payload = {
                "name": "Market Direction",
                "pass": False,
                "reason": "regime unavailable",
            }
        _accumulate("M", m_payload)

        # ── Overall rating ──────────────────────────────────────
        # Scale rating thresholds to the effective max_score (after N/A drops).
        score = results["total_score"]
        max_score = max(results["max_score"], 1)
        score_pct = score / max_score
        if score_pct >= 6.0 / 7.0:
            results["rating"] = "STRONG"
        elif score_pct >= 4.0 / 7.0:
            results["rating"] = "MODERATE"
        elif score_pct >= 2.0 / 7.0:
            results["rating"] = "WEAK"
        else:
            results["rating"] = "AVOID"

        return results
