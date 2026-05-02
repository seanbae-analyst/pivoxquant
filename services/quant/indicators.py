"""Additional technical indicators and fundamental factors for PivoxQuant.

Technical: 10 new indicators (Donchian, Supertrend, Parabolic SAR, CMF, ADL,
           Pivot Points, ATR Bands, VWAP, Heikin-Ashi, Keltner Width).
Fundamental: 8 new factors (PEG, P/S, P/B, FCF Yield, ROE, ROA,
             Current Ratio, Interest Coverage).

All pure numpy — no external dependencies beyond what is already installed.
Pure mathematical calculations; no investment advice.
"""

import numpy as np


class AdditionalIndicators:
    """10 new technical indicators to expand from 15 to 25."""

    @staticmethod
    def donchian_channel(highs, lows, closes, period=20):
        """Donchian Channel -- highest high / lowest low over N periods.

        Returns dict with upper, lower, mid, breakout signal, and width_pct.
        """
        if len(highs) < period or len(lows) < period or len(closes) < 1:
            return {"upper": None, "lower": None, "mid": None,
                    "breakout": "none", "width_pct": None}

        h = np.array(highs[-period:], dtype=float)
        l = np.array(lows[-period:], dtype=float)
        upper = float(np.max(h))
        lower = float(np.min(l))
        mid = (upper + lower) / 2
        current = float(closes[-1])
        breakout = "upper" if current >= upper else "lower" if current <= lower else "none"
        width_pct = (upper - lower) / mid * 100 if mid != 0 else 0.0
        return {
            "upper": round(upper, 2),
            "lower": round(lower, 2),
            "mid": round(mid, 2),
            "breakout": breakout,
            "width_pct": round(width_pct, 2),
        }

    @staticmethod
    def supertrend(highs, lows, closes, period=10, multiplier=3.0):
        """Supertrend indicator -- ATR-based trend direction.

        Returns dict with trend direction, supertrend value, and ATR.
        """
        if len(closes) < period + 1:
            return {"trend": "neutral", "value": None, "atr": None}

        h = np.array(highs, dtype=float)
        l = np.array(lows, dtype=float)
        c = np.array(closes, dtype=float)

        # True Range
        tr = np.maximum(
            h[1:] - l[1:],
            np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])),
        )
        atr = float(np.mean(tr[-period:]))

        hl2 = (h[-1] + l[-1]) / 2
        upper_band = hl2 + multiplier * atr
        lower_band = hl2 - multiplier * atr

        if c[-1] > upper_band:
            trend = "up"
        elif c[-1] < lower_band:
            trend = "down"
        elif c[-1] > c[-2]:
            trend = "up"
        else:
            trend = "down"

        value = lower_band if trend == "up" else upper_band
        return {"trend": trend, "value": round(value, 2), "atr": round(atr, 2)}

    @staticmethod
    def parabolic_sar(highs, lows, closes, af_start=0.02, af_max=0.20):
        """Parabolic SAR -- trend reversal detection.

        Returns dict with sar value, trend direction, and acceleration factor.
        """
        if len(closes) < 5:
            return {"sar": None, "trend": "neutral", "af": None}

        h = np.array(highs, dtype=float)
        l = np.array(lows, dtype=float)

        # Use last 20 bars (or fewer if not enough data)
        n = min(20, len(h))
        sar = float(l[-n])
        ep = float(h[-n])
        af = af_start
        trend = "up"

        for i in range(-n + 1, 0):
            if trend == "up":
                sar = sar + af * (ep - sar)
                if h[i] > ep:
                    ep = float(h[i])
                    af = min(af + af_start, af_max)
                if l[i] < sar:
                    trend = "down"
                    sar = ep
                    ep = float(l[i])
                    af = af_start
            else:
                sar = sar - af * (sar - ep)
                if l[i] < ep:
                    ep = float(l[i])
                    af = min(af + af_start, af_max)
                if h[i] > sar:
                    trend = "up"
                    sar = ep
                    ep = float(h[i])
                    af = af_start

        return {"sar": round(sar, 2), "trend": trend, "af": round(af, 4)}

    @staticmethod
    def cmf(highs, lows, closes, volumes, period=20):
        """Chaikin Money Flow -- buying/selling pressure.

        Returns dict with cmf value (-1 to +1) and pressure interpretation.
        """
        if len(closes) < period:
            return {"cmf": None, "pressure": "neutral"}

        h = np.array(highs[-period:], dtype=float)
        l = np.array(lows[-period:], dtype=float)
        c = np.array(closes[-period:], dtype=float)
        v = np.array(volumes[-period:], dtype=float)

        hl_range = h - l
        hl_range[hl_range == 0] = 1  # avoid division by zero
        mfm = ((c - l) - (h - c)) / hl_range
        mfv = mfm * v
        total_vol = float(np.sum(v))
        cmf_val = float(np.sum(mfv)) / total_vol if total_vol > 0 else 0.0

        if cmf_val > 0.15:
            pressure = "strong_buying"
        elif cmf_val > 0.05:
            pressure = "buying"
        elif cmf_val < -0.15:
            pressure = "strong_selling"
        elif cmf_val < -0.05:
            pressure = "selling"
        else:
            pressure = "neutral"

        return {"cmf": round(cmf_val, 4), "pressure": pressure}

    @staticmethod
    def adl(highs, lows, closes, volumes, period=20):
        """Accumulation/Distribution Line -- volume-price trend.

        Returns dict with adl value and trend (rising/falling/flat).
        """
        if len(closes) < period:
            return {"adl": None, "trend": "neutral"}

        h = np.array(highs[-period:], dtype=float)
        l = np.array(lows[-period:], dtype=float)
        c = np.array(closes[-period:], dtype=float)
        v = np.array(volumes[-period:], dtype=float)

        hl = h - l
        hl[hl == 0] = 1
        clv = ((c - l) - (h - c)) / hl
        adl_vals = np.cumsum(clv * v)

        if len(adl_vals) >= 5:
            trend = (
                "rising" if adl_vals[-1] > adl_vals[-5]
                else "falling" if adl_vals[-1] < adl_vals[-5]
                else "flat"
            )
        else:
            trend = "flat"

        return {"adl": round(float(adl_vals[-1]), 0), "trend": trend}

    @staticmethod
    def pivot_points(high, low, close):
        """Classic Pivot Points -- support/resistance levels.

        Takes single-bar high/low/close. Returns pivot, s1-s3, r1-r3.
        """
        h, l, c = float(high), float(low), float(close)
        pivot = (h + l + c) / 3
        r1 = 2 * pivot - l
        s1 = 2 * pivot - h
        r2 = pivot + (h - l)
        s2 = pivot - (h - l)
        r3 = h + 2 * (pivot - l)
        s3 = l - 2 * (h - pivot)
        return {
            "pivot": round(pivot, 2),
            "r1": round(r1, 2), "r2": round(r2, 2), "r3": round(r3, 2),
            "s1": round(s1, 2), "s2": round(s2, 2), "s3": round(s3, 2),
        }

    @staticmethod
    def atr_bands(closes, highs, lows, period=14, multiplier=2.0):
        """ATR Bands -- volatility-based bands (similar to Keltner but simpler).

        Returns dict with upper, lower, mid, atr, and atr_pct.
        """
        if len(closes) < period + 1:
            return {"upper": None, "lower": None, "mid": None, "atr": None, "atr_pct": None}

        h = np.array(highs, dtype=float)
        l = np.array(lows, dtype=float)
        c = np.array(closes, dtype=float)

        tr = np.maximum(
            h[1:] - l[1:],
            np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])),
        )
        atr = float(np.mean(tr[-period:]))

        mid = float(c[-1])
        upper = mid + multiplier * atr
        lower = mid - multiplier * atr
        atr_pct = atr / mid * 100 if mid != 0 else 0.0

        return {
            "upper": round(upper, 2),
            "lower": round(lower, 2),
            "mid": round(mid, 2),
            "atr": round(atr, 2),
            "atr_pct": round(atr_pct, 2),
        }

    @staticmethod
    def vwap_daily(highs, lows, closes, volumes):
        """Volume Weighted Average Price -- intraday/daily.

        Returns dict with vwap, deviation_pct, and above_vwap flag.
        """
        if len(closes) < 1:
            return {"vwap": None, "deviation_pct": None, "above_vwap": None}

        h = np.array(highs, dtype=float)
        l = np.array(lows, dtype=float)
        c = np.array(closes, dtype=float)
        v = np.array(volumes, dtype=float)

        typical = (h + l + c) / 3
        total_vol = float(np.sum(v))
        vwap = float(np.sum(typical * v)) / total_vol if total_vol > 0 else float(c[-1])
        deviation = (float(c[-1]) - vwap) / vwap * 100 if vwap != 0 else 0.0

        return {
            "vwap": round(vwap, 2),
            "deviation_pct": round(deviation, 2),
            "above_vwap": bool(c[-1] > vwap),
        }

    @staticmethod
    def heikin_ashi(opens, highs, lows, closes):
        """Heikin-Ashi -- smoothed candlestick trend.

        Returns dict with ha_trend (bullish/bearish), consecutive count,
        and ha_close.
        """
        if len(closes) < 3:
            return {"trend": "neutral", "consecutive": 0, "ha_close": None}

        o = np.array(opens, dtype=float)
        h = np.array(highs, dtype=float)
        l = np.array(lows, dtype=float)
        c = np.array(closes, dtype=float)

        # HA candles
        ha_close = (o + h + l + c) / 4
        ha_open = np.zeros_like(o)
        ha_open[0] = (o[0] + c[0]) / 2
        for i in range(1, len(o)):
            ha_open[i] = (ha_open[i - 1] + ha_close[i - 1]) / 2

        # Count consecutive bullish or bearish
        bullish = bool(ha_close[-1] > ha_open[-1])
        count = 0
        for i in range(len(ha_close) - 1, -1, -1):
            if (ha_close[i] > ha_open[i]) == bullish:
                count += 1
            else:
                break

        trend = "bullish" if bullish else "bearish"
        return {"trend": trend, "consecutive": count, "ha_close": round(float(ha_close[-1]), 2)}

    @staticmethod
    def keltner_width(highs, lows, closes, period=20):
        """Keltner Channel Width -- volatility squeeze detection.

        Returns dict with width_pct, is_squeeze flag, and atr.
        """
        # Need period+1 bars: period bars of H/L plus previous close for TR
        if len(closes) < period + 1:
            return {"width_pct": None, "is_squeeze": False, "atr": None}

        # Take period+1 bars so we can compute TR using previous close
        c = np.array(closes[-(period + 1):], dtype=float)
        h = np.array(highs[-period:], dtype=float)
        l = np.array(lows[-period:], dtype=float)
        prev_c = c[:-1]  # previous close for each of the period bars

        ema = float(np.mean(c[-period:]))  # simplified EMA as SMA
        # True Range: max(H-L, |H-prev_close|, |L-prev_close|)
        tr = np.maximum(h - l, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)))
        atr = float(np.mean(tr))

        upper = ema + 2 * atr
        lower = ema - 2 * atr
        width = (upper - lower) / ema * 100 if ema != 0 else 0.0

        # Squeeze: width below threshold
        is_squeeze = width < 5.0

        return {"width_pct": round(width, 2), "is_squeeze": bool(is_squeeze), "atr": round(atr, 2)}


class AdditionalFundamentals:
    """8 new fundamental factors. Uses SEC EDGAR data via edgar_service.py."""

    _FACTOR_KEYS = [
        "peg", "ps_ratio", "pb_ratio", "fcf_yield",
        "roe", "roa", "current_ratio", "interest_coverage",
    ]

    @classmethod
    def calculate_all(cls, ticker, current_price=None):
        """Calculate all 8 additional fundamental factors.

        Returns dict with all factors. Values are None when data is
        unavailable (graceful degradation -- never raises).
        """
        empty = {k: None for k in cls._FACTOR_KEYS}
        try:
            from edgar_service import EdgarService
            fund = EdgarService.get_fundamentals(ticker)
            if not fund:
                return empty

            revenue = fund.get("revenue")
            net_income = fund.get("net_income")
            eps = fund.get("eps")
            total_equity = fund.get("total_equity")
            total_debt = fund.get("total_debt")
            revenue_growth = fund.get("revenue_growth")

            results = {}

            # 1. PEG Ratio (P/E / Growth Rate)
            # NOTE: revenue_growth from edgar_service is already in percent
            # (e.g., 15.0 means 15%). PEG = PE / growth_rate_in_percent,
            # so pe / revenue_growth is correct as-is.
            if current_price and eps and eps > 0 and revenue_growth and revenue_growth > 0:
                pe = current_price / eps
                # Sanity: if revenue_growth somehow exceeds 1000%, cap to avoid
                # misleadingly tiny PEG values from hypergrowth outliers.
                growth_pct = revenue_growth if revenue_growth <= 1000 else 1000.0
                results["peg"] = round(pe / growth_pct, 2)
            else:
                results["peg"] = None

            # 2. Price/Sales
            shares = _estimate_shares(net_income, eps)
            if current_price and revenue and revenue > 0 and shares and shares > 0:
                results["ps_ratio"] = round(current_price * shares / revenue, 2)
            else:
                results["ps_ratio"] = None

            # 3. Price/Book
            if current_price and total_equity and total_equity > 0 and shares and shares > 0:
                bvps = total_equity / shares
                results["pb_ratio"] = round(current_price / bvps, 2) if bvps > 0 else None
            else:
                results["pb_ratio"] = None

            # 4. FCF Yield (simplified: net income / market cap as proxy)
            if net_income and shares and shares > 0 and current_price:
                market_cap = current_price * shares
                results["fcf_yield"] = (
                    round(net_income / market_cap * 100, 2) if market_cap > 0 else None
                )
            else:
                results["fcf_yield"] = None

            # 5. ROE (Return on Equity)
            if net_income and total_equity and total_equity > 0:
                results["roe"] = round(net_income / total_equity * 100, 2)
            else:
                results["roe"] = None

            # 6. ROA (Return on Assets -- approximate from equity + debt)
            total_assets = (total_equity or 0) + (total_debt or 0)
            if net_income and total_assets > 0:
                results["roa"] = round(net_income / total_assets * 100, 2)
            else:
                results["roa"] = None

            # 7. Current Ratio — from FMP balance sheet
            results["current_ratio"] = cls.current_ratio(ticker)

            # 8. Interest Coverage — from FMP income statement
            results["interest_coverage"] = cls.interest_coverage(ticker)

            return results

        except Exception:
            return empty

    # ── Individual fundamental helpers (FMP-backed) ──────────────────────
    # These return structured dicts {value, status, interpretation?, reason?}
    # rather than bare floats so callers can distinguish DATA_UNAVAILABLE
    # (plan-gated / network) from NO_DATA (empty payload) from INVALID
    # (math edge case -- e.g. 0 interest expense on a debt-free company).

    @staticmethod
    def current_ratio(ticker):
        """Current Ratio = totalCurrentAssets / totalCurrentLiabilities.

        Interpretation:
            >= 1.5  -> "양호"  (healthy short-term liquidity)
            >= 1.0  -> "주의"  (cautious -- can cover liabilities but little buffer)
            <  1.0  -> "위험"  (at risk of short-term solvency issues)
        """
        try:
            from fmp_service import get_balance_sheet
        except Exception:
            return {"value": None, "status": "DATA_UNAVAILABLE",
                    "reason": "fmp_service unavailable"}

        try:
            statements = get_balance_sheet(ticker)
        except Exception:
            return {"value": None, "status": "DATA_UNAVAILABLE",
                    "reason": "FMP request failed"}

        # None = plan-gated / network error; distinguish from empty list (no data).
        if statements is None:
            return {"value": None, "status": "DATA_UNAVAILABLE",
                    "reason": "FMP endpoint unavailable (402 or network)"}
        if not statements:
            return {"value": None, "status": "NO_DATA",
                    "reason": "No balance sheet data for ticker"}

        latest = statements[0] if isinstance(statements, list) else statements
        if not isinstance(latest, dict):
            return {"value": None, "status": "NO_DATA",
                    "reason": "Unexpected response shape"}

        assets = latest.get("totalCurrentAssets")
        liabilities = latest.get("totalCurrentLiabilities")

        try:
            assets = float(assets) if assets is not None else None
            liabilities = float(liabilities) if liabilities is not None else None
        except (TypeError, ValueError):
            return {"value": None, "status": "NO_DATA",
                    "reason": "Non-numeric balance sheet fields"}

        if assets is None or liabilities is None:
            return {"value": None, "status": "NO_DATA",
                    "reason": "Missing totalCurrentAssets or totalCurrentLiabilities"}

        if liabilities == 0:
            # No current liabilities -> ratio undefined; report as INVALID so
            # downstream UIs can show "n/a" rather than a misleading 0 or inf.
            return {"value": None, "status": "INVALID",
                    "reason": "Zero current liabilities"}

        ratio = assets / liabilities
        if ratio >= 1.5:
            interp = "양호"
        elif ratio >= 1.0:
            interp = "주의"
        else:
            interp = "위험"

        return {
            "value": round(ratio, 2),
            "status": "OK",
            "interpretation": interp,
            "period": latest.get("date"),
        }

    @staticmethod
    def interest_coverage(ticker):
        """Interest Coverage Ratio = operatingIncome / interestExpense.

        Proxy for EBIT/Interest. Interpretation:
            >= 5.0  -> "안전"  (strong ability to service debt)
            >= 1.5  -> "주의"  (covers interest but little margin)
            <  1.5  -> "위험"  (struggling to service debt)

        A company with zero interest expense is treated as INVALID (math
        undefined) rather than infinitely safe -- callers should display
        "무차입" separately if desired.
        """
        try:
            from fmp_service import get_income_statement
        except Exception:
            return {"value": None, "status": "DATA_UNAVAILABLE",
                    "reason": "fmp_service unavailable"}

        try:
            statements = get_income_statement(ticker)
        except Exception:
            return {"value": None, "status": "DATA_UNAVAILABLE",
                    "reason": "FMP request failed"}

        if statements is None:
            return {"value": None, "status": "DATA_UNAVAILABLE",
                    "reason": "FMP endpoint unavailable (402 or network)"}
        if not statements:
            return {"value": None, "status": "NO_DATA",
                    "reason": "No income statement data for ticker"}

        latest = statements[0] if isinstance(statements, list) else statements
        if not isinstance(latest, dict):
            return {"value": None, "status": "NO_DATA",
                    "reason": "Unexpected response shape"}

        operating_income = latest.get("operatingIncome")
        interest_expense = latest.get("interestExpense")

        try:
            operating_income = float(operating_income) if operating_income is not None else None
            interest_expense = float(interest_expense) if interest_expense is not None else None
        except (TypeError, ValueError):
            return {"value": None, "status": "NO_DATA",
                    "reason": "Non-numeric income statement fields"}

        if operating_income is None or interest_expense is None:
            return {"value": None, "status": "NO_DATA",
                    "reason": "Missing operatingIncome or interestExpense"}

        # FMP often reports interestExpense as a positive cost; some datasets
        # report it signed. Use absolute value for the denominator so the
        # ratio's sign reflects operating income direction, not reporting
        # convention. Zero-interest companies stay undefined.
        denom = abs(interest_expense)
        if denom == 0:
            return {"value": None, "status": "INVALID",
                    "reason": "Zero interest expense (debt-free or not disclosed)"}

        ratio = operating_income / denom
        if ratio >= 5.0:
            interp = "안전"
        elif ratio >= 1.5:
            interp = "주의"
        else:
            interp = "위험"

        return {
            "value": round(ratio, 2),
            "status": "OK",
            "interpretation": interp,
            "period": latest.get("date"),
        }


# ── Private helpers ──────────────────────────────────────────────────────────


def _estimate_shares(net_income, eps):
    """Estimate shares outstanding from net income and EPS.

    Returns None if either input is missing or EPS is non-positive.
    """
    if net_income and eps and eps > 0:
        shares = net_income / eps
        return shares if shares > 0 else None
    return None
