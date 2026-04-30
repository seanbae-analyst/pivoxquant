"""
PivoxQuant — Quantitative Analysis Engine v2
Goldman Sachs-style multi-factor model. Zero AI API cost.

Scoring:
  Technical Analysis   50 %  (RSI, MACD, Bollinger, MA cross, Volume)
  Fundamental Analysis 30 %  (P/E, Revenue Growth, Margins, Leverage, Beta)
  News Sentiment       20 %  (keyword-based RSS, no LLM)

Each signal carries both English (msg) and Korean (msg_kr) text for the
language-toggle feature in the frontend.
"""

import numpy as np
import pandas as pd
import fmp_service as fmp
import logging
from data_fetcher import DataFetcher
from quant_models import (MeanReversion, MomentumBreakout, VolatilityRegime, RegimeSwitching, MLSignal,
                          VarianceRatioFilter, TSMOM, FiftyTwoWeekHigh,
                          DonchianBreakout, DualMomentum, CorrelationRegime)
from signal_models import DispositionEffect, OrderFlowImbalance, AnchoringBias, SentimentPriceDivergence

logger = logging.getLogger(__name__)
_fetcher = DataFetcher()


class QuantEngine:

    MAX_ALLOC   = 0.45   # max allocation per position
    BUY_THRESH  = 70.0   # composite score minimum for POSITIVE signal
    SELL_THRESH = 25.0   # below this → NEGATIVE signal

    DISCOVER_POOL = [
        # ── US: High-momentum / growth ──
        "NVDA","TSLA","AAPL","MSFT","AMZN","GOOGL","GOOG","META","AMD","PLTR","SMCI",
        "RXRX","IONQ","RKLB","HOOD","COIN","MSTR","CRWD","NET","DDOG","ZS",
        "SNOW","SHOP","SQ","PYPL","SOFI","RIVN","LCID","RBLX","U","SPOT",
        "NFLX","UBER","ABNB","DASH","OKTA","GTLB","PATH","AI","SOUN","BBAI",
        # ── US: Macro / value ──
        "BA","GM","F","GE","XOM","CVX","JPM","GS","MS","BAC",
        # ── US: S&P 500 large-cap blue chips (added 2026-04-29 — DISCOVER_POOL P0) ──
        "V","JNJ","WMT","PG","MA","HD","ABBV","KO","PFE","AVGO",
        "COST","MRK","DIS","LLY","ADBE","CRM","BRK-B","MCD","CSCO","ORCL",
        "ACN","TMO","ABT","NKE","INTC","IBM","QCOM","T","VZ","CAT",
        "AXP","BLK","SCHW","SPGI","NOW","INTU","AMAT","BKNG","SBUX",
        # ── KR: Blue chip + growth ──
        "005930.KS","000660.KS","035720.KS","035420.KS","005380.KS",
        "207940.KS","006400.KS","051910.KS","003670.KS","066570.KS",
        "105560.KS","055550.KS","086790.KS","017670.KS","030200.KS",
        "096770.KS","012330.KS","028260.KS","032830.KS","015760.KS",
    ]

    # ── FMP Budget Optimization ────────────────────────────────────────────────
    _pool_prefetched = False
    _DISCOVER_SET = frozenset(DISCOVER_POOL)  # O(1) lookup for prefetch check

    @classmethod
    def prefetch_discover_pool(cls):
        """Pre-warm FMP cache for all discover pool tickers using batch API calls.
        Call this before a discover scan to reduce per-ticker FMP calls from ~6 to ~0.
        Safe to call multiple times -- will skip if already prefetched this session.
        """
        if cls._pool_prefetched:
            return
        try:
            fmp.prefetch_fundamentals(cls.DISCOVER_POOL)
            cls._pool_prefetched = True
        except Exception as e:
            logger.warning(f"Discover pool prefetch failed: {e}")

    def _auto_prefetch_if_needed(self, ticker: str):
        """Auto-trigger pool prefetch on first discover pool ticker analysis.
        This ensures batch caching happens even if prefetch_discover_pool()
        was not explicitly called by the route.
        """
        if not QuantEngine._pool_prefetched and ticker in self._DISCOVER_SET:
            QuantEngine.prefetch_discover_pool()

    # ── Public ────────────────────────────────────────────────────────────────

    def analyze(self, ticker: str, capital_usd: float = 10_000.0,
                capital_krw: float = 0.0, fx_rate: float = 0.0,
                current_pnl_pct: float = None,
                profile_params: dict = None,
                user_id: int | None = None) -> "dict | None":
        ticker   = ticker.upper().strip()
        self._auto_prefetch_if_needed(ticker)
        snapshot = _fetcher.get_stock_snapshot(ticker)
        hist     = _fetcher.get_price_history(ticker, "6mo")
        if snapshot is None or hist is None:
            return None

        price     = snapshot["price"]
        currency  = snapshot.get("currency", "USD")
        is_korean = snapshot.get("is_korean", False)

        # Use the currency-matched capital for Kelly sizing
        if is_korean and capital_krw > 0:
            capital = capital_krw
        elif is_korean:
            # No KRW capital set — convert USD to KRW so sizing works
            _fx = fx_rate if fx_rate > 0 else 1350  # fallback rate
            capital = capital_usd * _fx
        else:
            capital = capital_usd

        tech_score, tech_sigs = self._technical(hist)
        fund_score, fund_sigs = self._fundamental(snapshot)
        news_score, news_sigs = _fetcher.score_news_sentiment(ticker)

        # ── Advanced Quant Models ──
        (quant_score, quant_sigs, vr_result, tsmom_result, high52_result,
         disp_result, ofi_result, anchor_result, spd_result,
         donchian_result, dual_mom_result, corr_regime_result) = self._quant_models(
            hist, profile_params=profile_params, news_score=news_score
        )

        # ── Sector Relative Strength ──
        try:
            sector = snapshot.get("sector", "")
            _sector_etf_map = {
                "Technology": "XLK", "Healthcare": "XLV", "Financials": "XLF",
                "Consumer Cyclical": "XLY", "Consumer Defensive": "XLP",
                "Industrials": "XLI", "Energy": "XLE", "Utilities": "XLU",
                "Real Estate": "XLRE", "Materials": "XLB", "Communication Services": "XLC",
            }
            sector_etf = _sector_etf_map.get(sector)
            if sector_etf and not is_korean:
                sector_hist = _fetcher.get_price_history(sector_etf, "1mo")
                if sector_hist is not None and len(sector_hist) >= 5:
                    sector_ret = (float(sector_hist["Close"].iloc[-1]) / float(sector_hist["Close"].iloc[0]) - 1) * 100
                    stock_close = hist["Close"].astype(float)
                    stock_ret = (float(stock_close.iloc[-1]) / float(stock_close.iloc[-22]) - 1) * 100 if len(stock_close) >= 22 else 0
                    relative = stock_ret - sector_ret
                    if relative < -10:
                        tech_score = max(0, tech_score - 10)
                        tech_sigs.append({"type": "bearish",
                            "msg": f"Sector laggard: {relative:+.0f}% vs {sector} ({sector_ret:+.1f}%)",
                            "msg_kr": f"섹터 대비 약세: {relative:+.0f}% vs {sector}"})
                    elif relative > 10:
                        tech_score = min(100, tech_score + 5)
                        tech_sigs.append({"type": "bullish",
                            "msg": f"Sector leader: {relative:+.0f}% vs {sector} ({sector_ret:+.1f}%)",
                            "msg_kr": f"섹터 대비 강세: {relative:+.0f}% vs {sector}"})
        except Exception:
            pass

        # ── Adaptive Weights + Thresholds ──
        sector = snapshot.get("sector", "Unknown")
        market_cap = snapshot.get("market_cap") or 0
        is_etf = sector == "ETF" or "ETF" in (snapshot.get("name",""))

        # Determine stock type for adaptive scoring
        if is_etf:
            w_tech, w_fund, w_news, w_quant = 0.50, 0.05, 0.03, 0.42
            buy_thresh, sell_thresh = 65, 40
        elif is_korean:
            w_tech, w_fund, w_news, w_quant = 0.28, 0.32, 0.03, 0.37
            buy_thresh, sell_thresh = 63, 38
        elif market_cap and market_cap > 100e9:
            # Large cap: fundamentals heavy, news almost zero
            w_tech, w_fund, w_news, w_quant = 0.22, 0.25, 0.03, 0.50
            buy_thresh, sell_thresh = 68, 40
        elif market_cap and market_cap < 10e9:
            # Small cap: highest bar, fundamentals still matter
            w_tech, w_fund, w_news, w_quant = 0.25, 0.22, 0.03, 0.50
            buy_thresh, sell_thresh = 70, 42
        else:
            w_tech, w_fund, w_news, w_quant = 0.22, 0.25, 0.03, 0.50
            buy_thresh, sell_thresh = 68, 40

        # ── Profile-based override (투자성향 시스템) ──
        if profile_params:
            # Blend profile weights with stock-type weights (50/50)
            pp = profile_params
            w_tech = (w_tech + pp.get("tech_weight", w_tech)) / 2
            w_fund = (w_fund + pp.get("fund_weight", w_fund)) / 2
            w_news = (w_news + pp.get("news_weight", w_news)) / 2
            # Normalize to sum=1 (quant weight gets remainder)
            non_quant = w_tech + w_fund + w_news
            if non_quant > 0.65:
                scale = 0.65 / non_quant
                w_tech *= scale
                w_fund *= scale
                w_news *= scale
            w_quant = 1.0 - w_tech - w_fund - w_news
            # Threshold override
            buy_thresh = pp.get("buy_threshold", buy_thresh)
            sell_thresh = pp.get("sell_threshold", sell_thresh)

        # Market regime adjustment: in strong bull, lower threshold
        if quant_score >= 70:
            buy_thresh -= 5  # Bull market: easier to buy
        elif quant_score <= 30:
            buy_thresh += 5  # Bear market: harder to buy

        # ── Quant Composer hook (Feature 1) ──
        # Apply the user's per-model selection + weight composition to the
        # quant pillar before it enters the composite. Backward-compatible:
        # when ``user_id`` is None or the user has not opted in, this is a
        # no-op (returns ``quant_score`` unchanged). Failures here MUST NOT
        # break the engine's hot path — fall back to the unmodified score.
        if user_id is not None:
            try:
                from services.quant.composer import apply_user_composition
                quant_score = apply_user_composition(user_id, quant_score)
            except Exception:  # pragma: no cover — defensive
                logger.exception("Quant Composer apply failed for user_id=%s", user_id)

        composite = round(
            tech_score * w_tech +
            fund_score * w_fund +
            news_score * w_news +
            quant_score * w_quant, 1
        )

        # ── 52-Week High Momentum Boost + Anchoring Bias Boost (applied to final composite) ──
        anchor_boost = anchor_result.get("boost", 1.0) if anchor_result else 1.0
        composite = composite * high52_result.get("boost", 1.0) * anchor_boost
        composite = max(0, min(100, round(composite, 1)))

        # ── Macro Environment Adjustment ──
        # VIX: raise the bar when market is fearful
        try:
            from quant_models import VIXStrategy
            vix_data = VIXStrategy().analyze()
            vix = vix_data.get("vix", 20)
            if vix > 30:
                buy_thresh += 5
                composite -= 5
                tech_sigs.append({"type": "bearish",
                    "msg": f"VIX {vix:.0f} — extreme fear, raising buy bar",
                    "msg_kr": f"VIX {vix:.0f} — 극도 공포, 매수 기준 강화"})
            elif vix > 25:
                buy_thresh += 3
                composite -= 2
            elif vix < 15:
                buy_thresh -= 2
        except Exception:
            pass

        # Cross-Asset Momentum: macro headwind/tailwind
        try:
            from quant_models import CrossAssetMomentum
            cam = CrossAssetMomentum().analyze()
            macro_regime = cam.get("macro_regime", "NEUTRAL")
            if macro_regime in ("RISK_OFF", "LIQUIDATION"):
                composite -= 8
                tech_sigs.append({"type": "bearish",
                    "msg": f"Macro regime: {macro_regime} — headwind for risk assets",
                    "msg_kr": f"매크로: {macro_regime} — 위험자산 역풍"})
            elif macro_regime == "RISK_ON":
                composite += 3
                tech_sigs.append({"type": "bullish",
                    "msg": "Macro regime: RISK_ON — tailwind for risk assets",
                    "msg_kr": "매크로: RISK_ON — 위험자산 순풍"})
        except Exception:
            pass

        # ── Common-Sense Filters ──
        # These override pure math — no amount of RSI/MACD makes a bad business good
        disqualified = False
        disq_reasons = []

        # 1) Unprofitable + no revenue growth = don't buy
        margin = snapshot.get("profit_margin")
        rev_g = snapshot.get("revenue_growth")
        if margin is not None and margin < 0 and (rev_g is None or rev_g < 0.10):
            disqualified = True
            disq_reasons.append("Unprofitable with weak revenue — not investable")

        # 2) Leveraged / inverse ETFs = no long-term hold
        name_upper = (snapshot.get("name") or "").upper()
        if any(x in name_upper for x in ["2X", "3X", "LEVERAGED", "INVERSE", "ULTRA"]):
            disqualified = True
            disq_reasons.append("Leveraged/inverse product — not suitable for holding")

        # 3) Downtrend: price below 200MA = don't catch falling knives
        close = hist["Close"].astype(float)
        ma200 = close.rolling(200).mean()
        if len(ma200.dropna()) >= 1:
            cur_price = float(close.iloc[-1])
            ma200_val = float(ma200.dropna().iloc[-1])
            if cur_price < ma200_val * 0.9:  # 10%+ below 200MA
                disqualified = True
                disq_reasons.append(f"Deep downtrend — price {((cur_price/ma200_val - 1)*100):.0f}% below 200MA")

        # 4) Extreme drawdown from 52-week high
        high_52w = snapshot.get("week52_high")
        if high_52w and high_52w > 0:
            drawdown = (price - high_52w) / high_52w * 100
            if drawdown < -50:
                disqualified = True
                disq_reasons.append(f"Crashed {drawdown:.0f}% from 52-week high")

        if disqualified:
            # Block POSITIVE — disqualified stocks can only be NEUTRAL or NEGATIVE
            signal = "NEGATIVE" if composite < sell_thresh else "NEUTRAL"
            for r in disq_reasons:
                tech_sigs.append({"type": "bearish", "msg": f"⛔ {r}", "msg_kr": f"⛔ {r}"})
        else:
            signal = (
                "POSITIVE"  if composite >= buy_thresh  else
                "NEGATIVE"  if composite <  sell_thresh else
                "NEUTRAL"
            )

        # ── Smart Exit for Existing Holdings ──
        # Not a fixed %, but "is the investment thesis still intact?"
        if current_pnl_pct is not None:
            sell_override = False
            sell_reason = ""

            if disqualified and current_pnl_pct < -5:
                # Disqualified stock already losing → get out
                sell_override = True
                sell_reason = "Investment thesis broken + losing position — exit recommended"
            elif current_pnl_pct < -30 and composite < 55:
                # Deep loss + weak score = thesis is dead
                sell_override = True
                sell_reason = f"Down {current_pnl_pct:.0f}% with weak outlook (score {composite}) — cut losses"
            elif current_pnl_pct < -15 and fund_score < 35:
                # Moderate loss + terrible fundamentals
                sell_override = True
                sell_reason = f"Down {current_pnl_pct:.0f}% + poor fundamentals — reassess position"
            elif current_pnl_pct > 40 and composite < 55:
                # Big gain + deteriorating outlook = take profit
                sell_override = True
                sell_reason = f"Up {current_pnl_pct:.0f}% but weakening (score {composite}) — lock in profits"

            if sell_override:
                signal = "NEGATIVE"
                tech_sigs.append({"type": "bearish",
                    "msg": f"🔴 {sell_reason}",
                    "msg_kr": f"🔴 {sell_reason}"})

        rec_inv, rec_sh, rec_timing = self._size(composite, price, capital, signal)
        weights_str = f"Tech {int(w_tech*100)}% + Fund {int(w_fund*100)}% + News {int(w_news*100)}% + Quant {int(w_quant*100)}%"
        reason_en, reason_kr        = self._reason(signal, composite, tech_score,
                                                    fund_score, news_score, quant_score, weights_str)

        needs_capital  = (signal == "POSITIVE" and rec_sh == 0 and rec_timing in ("NO_CAPITAL", "INSUFFICIENT"))
        capital_needed = None
        capital_gap    = None
        if rec_timing == "INSUFFICIENT" and capital > 0:
            dp_n = 0 if is_korean else 2
            capital_needed = round(price, dp_n)
            capital_gap    = round(price - capital, dp_n)   # how much more needed

        # REMOVED: Legal compliance — 자본시장법 제7조
        # sell_pct    = 0
        # sell_timing = ""
        # if signal == "SELL":
        #     if composite < 15:
        #         sell_pct    = 100
        #         sell_timing = "Exit immediately — full position"
        #     else:
        #         sell_pct    = 50
        #         sell_timing = "Reduce by half — protect gains"

        # Take-profit / stop-loss targets (adaptive via 3-Layer regime model)
        beta = snapshot.get("beta") or 1.0
        try:
            from quant_models import AdaptiveParams
            ap = AdaptiveParams.calculate(
                hist["Close"].values, hist["High"].values,
                hist["Low"].values, hist["Volume"].values
            )
            regime_profile = ap["profile"]
            regime_label = ap.get("profile_label", "")
            regime_label_kr = ap.get("profile_label_kr", "")
            regime_desc = ap.get("profile_desc", "")
            regime_info = ap.get("regime_info", {})
            layers_active = ap.get("layers_active", [])

            if ap["skip_trade"]:
                tp_pct = 0
                sl_pct = 0
            elif signal == "POSITIVE":
                tp_pct = ap["tp_pct"]
                sl_pct = -ap["sl_pct"]
            elif signal == "NEGATIVE":
                # For NEGATIVE: use adaptive SL as cover target
                tp_pct = ap["sl_pct"]  # profit from short ≈ SL distance
                sl_pct = -ap["tp_pct"] * 0.3  # stop for short ≈ 30% of TP
            else:
                # NEUTRAL: show what params WOULD be if entering
                tp_pct = ap["tp_pct"]
                sl_pct = -ap["sl_pct"]
        except Exception:
            beta = snapshot.get("beta") or 1.0
            tp_pct = 30 if composite >= 85 else 20
            sl_pct = -12 if beta > 1.5 else -8
            regime_profile = "default"
            regime_label = ""
            regime_label_kr = ""
            regime_desc = ""
            regime_info = {}
            layers_active = []

        # ── Profile TP/SL clamp (투자성향에 따라 TP/SL 범위 제한) ──
        if profile_params and tp_pct != 0:
            pp_tp_max = profile_params.get("tp_max", 40)
            pp_sl_max = profile_params.get("sl_max", 20)
            tp_pct = min(tp_pct, pp_tp_max)
            sl_pct = max(sl_pct, -pp_sl_max)

        # Priority score for capital allocation ranking
        safe_beta = max(float(beta) if beta else 1.0, 0.5)
        priority  = round(composite * 0.6 + (composite / safe_beta) * 0.3 + (news_score / 100) * 10, 1)

        dp = 0 if is_korean else 2

        return {
            "ticker":          ticker,
            "name":            snapshot.get("name", ticker),
            "sector":          snapshot.get("sector", "Unknown"),
            "price":           price,
            "price_display":   snapshot.get("price_display", str(price)),
            "price_per_share": round(price, dp),
            "currency":        currency,
            "is_korean":       is_korean,
            "change_pct":      snapshot.get("change_pct", 0),
            "signal":          signal,
            "score":           composite,
            "tech_score":      round(tech_score, 1),
            "fund_score":      round(fund_score, 1),
            "news_score":      round(news_score, 1),
            "quant_score":     round(quant_score, 1),
            # REMOVED: Legal compliance — 자본시장법 제7조
            # "rec_investment":  round(rec_inv, 2),
            # "rec_shares":      rec_sh,
            "rec_timing":      "" if needs_capital else rec_timing,
            "needs_capital":   needs_capital,
            "capital_needed":  capital_needed,
            # REMOVED: Legal compliance — 자본시장법 제7조
            # "sell_pct":        sell_pct,
            # "sell_timing":     sell_timing,
            "tp_pct":          tp_pct,
            "sl_pct":          sl_pct,
            # REMOVED: Legal compliance — 자본시장법 제7조
            # "take_profit":     round(price * (1 + tp_pct / 100), dp),
            # "stop_loss":       round(price * (1 + sl_pct / 100), dp),
            "regime_profile":  regime_profile,
            "regime_label":    regime_label,
            "regime_label_kr": regime_label_kr,
            "regime_desc":     regime_desc,
            "regime_info":     regime_info,
            "layers_active":   layers_active,
            "priority":        priority,
            "capital_gap":     capital_gap,
            "signals":         tech_sigs + fund_sigs + news_sigs + quant_sigs,
            "reason":          reason_en,
            "reason_kr":       reason_kr,
            "snapshot":        snapshot,
            "variance_ratio":  vr_result,
            "tsmom":           tsmom_result,
            "high_52w":        high52_result,
            # ── New signal models (behavioral + microstructure) ──
            "disposition_effect": disp_result,
            "order_flow":         ofi_result,
            "anchoring_bias":     anchor_result,
            "sentiment_divergence": spd_result,
            "donchian_breakout":  donchian_result,
            "dual_momentum":      dual_mom_result,
            "correlation_regime": corr_regime_result,
            # Earnings Tone: NOT integrated into 4-pillar scoring (cost control).
            # Cache-only lookup — never triggers a Claude API call from analyze().
            # Populated by /api/ai/earnings-tone endpoint (Pro/Premium, lazy).
            # TTL: 90 days (quarterly earnings cycle). Free users always see None.
            "earnings_tone":      self._get_cached_earnings_tone(ticker),
        }

    # ── Earnings Tone (cache-only read; populated via /api/ai/earnings-tone) ──

    @staticmethod
    def _get_cached_earnings_tone(ticker: str):
        """Return cached earnings_tone for ticker or None.
        This MUST remain a pure cache lookup — never call the Claude API here.
        Writes happen only through the tier-gated POST /api/ai/earnings-tone
        endpoint so free users incur zero AI cost from the analyze() path.
        """
        try:
            from services import cache_service
            return cache_service.earnings_tone_cache_get(ticker)
        except Exception as e:
            logger.warning(f"earnings_tone cache lookup failed for {ticker}: {e}")
            return None

    # ── Technical Analysis ────────────────────────────────────────────────────

    def _technical(self, hist: pd.DataFrame) -> tuple[float, list[dict]]:
        sigs  = []
        score = 50.0
        close = hist["Close"].astype(float)
        vol   = hist["Volume"].astype(float)

        # ── Trend Context (used to adjust oversold/overbought signals) ──
        ma50  = close.rolling(50).mean()
        ma200 = close.rolling(200).mean()
        cur_price = float(close.iloc[-1])
        above_200ma = True  # default optimistic if not enough data
        above_50ma = True
        if len(ma200.dropna()) >= 1:
            above_200ma = cur_price > float(ma200.dropna().iloc[-1])
        if len(ma50.dropna()) >= 1:
            above_50ma = cur_price > float(ma50.dropna().iloc[-1])

        # RSI ─────────────────────────────────────────────────────────────────
        # Trend-adjusted: oversold in uptrend = opportunity, in downtrend = falling knife
        rsi = self._rsi(close)
        if len(rsi.dropna()):
            r = float(rsi.iloc[-1])
            if r < 30:
                if above_200ma:
                    score += 20
                    sigs.append({"type": "bullish",
                                  "msg":    f"RSI oversold ({r:.0f}) in uptrend — strong bounce expected",
                                  "msg_kr": f"RSI 과매도 ({r:.0f}) 상승추세 중 — 강한 반등 기대"})
                elif above_50ma:
                    score += 5
                    sigs.append({"type": "neutral",
                                  "msg":    f"RSI oversold ({r:.0f}) but below 200MA — cautious",
                                  "msg_kr": f"RSI 과매도 ({r:.0f}) 200MA 하회 — 신중"})
                else:
                    # Below both MAs — falling knife, no bonus
                    sigs.append({"type": "bearish",
                                  "msg":    f"RSI oversold ({r:.0f}) in downtrend — falling knife, not a positive signal",
                                  "msg_kr": f"RSI 과매도 ({r:.0f}) 하락추세 — 낙폭 확대 가능, 매수 신호 아님"})
            elif r < 45:
                adj = 10 if above_200ma else 3
                score += adj
                sigs.append({"type": "bullish" if above_200ma else "neutral",
                              "msg":    f"RSI below neutral ({r:.0f})",
                              "msg_kr": f"RSI 중립 이하 ({r:.0f})"})
            elif r > 70:
                score -= 20
                sigs.append({"type": "bearish",
                              "msg":    f"RSI overbought ({r:.0f}) — pullback risk elevated",
                              "msg_kr": f"RSI 과매수 ({r:.0f}) — 조정 위험 상승"})
            elif r > 58:
                score += 5
                sigs.append({"type": "neutral",
                              "msg":    f"RSI healthy ({r:.0f})",
                              "msg_kr": f"RSI 건강한 구간 ({r:.0f})"})

        # MACD ────────────────────────────────────────────────────────────────
        macd, sig_line = self._macd(close)
        if len(macd.dropna()) >= 3:
            m, s = float(macd.iloc[-1]), float(sig_line.iloc[-1])
            mp, sp = float(macd.iloc[-2]), float(sig_line.iloc[-2])
            if m > s and mp <= sp:
                score += 18
                sigs.append({"type": "bullish",
                              "msg":    "MACD golden cross — momentum flipped positive",
                              "msg_kr": "MACD 골든크로스 — 상승 모멘텀 전환"})
            elif m > s:
                score += 8
                sigs.append({"type": "bullish",
                              "msg":    "MACD above signal line — positive momentum",
                              "msg_kr": "MACD 시그널 위 — 양호한 모멘텀"})
            elif m < s and mp >= sp:
                score -= 18
                sigs.append({"type": "bearish",
                              "msg":    "MACD death cross — momentum turned negative",
                              "msg_kr": "MACD 데드크로스 — 하락 모멘텀 전환 경고"})
            elif m < s:
                score -= 8
                sigs.append({"type": "bearish",
                              "msg":    "MACD below signal line — weak momentum",
                              "msg_kr": "MACD 시그널 아래 — 약한 모멘텀"})

        # Bollinger Bands ─────────────────────────────────────────────────────
        ub, _, lb = self._bollinger(close)
        if len(lb.dropna()):
            cur, lo, up = float(close.iloc[-1]), float(lb.iloc[-1]), float(ub.iloc[-1])
            bw = up - lo
            if bw > 0:
                pct_b = (cur - lo) / bw
                if pct_b <= 0.15:
                    bb_adj = 15 if above_200ma else 3  # downtrend = less bounce potential
                    score += bb_adj
                    sigs.append({"type": "bullish" if above_200ma else "neutral",
                                  "msg":    f"Price near lower Bollinger Band{' (downtrend — limited bounce)' if not above_200ma else ''}",
                                  "msg_kr": f"볼린저 하단 근접{' (하락추세 — 반등 제한)' if not above_200ma else ''}"})
                elif pct_b >= 0.85:
                    score -= 15
                    sigs.append({"type": "bearish",
                                  "msg":    "Price near upper Bollinger Band — statistically stretched",
                                  "msg_kr": "볼린저 상단 근접 — 통계적 과매수 구간"})

        # Moving Averages (50/200) — already computed above for trend context
        if len(ma200.dropna()) >= 5:
            m50, m200 = float(ma50.iloc[-1]), float(ma200.iloc[-1])
            m50p = float(ma50.dropna().iloc[-5])
            m200p = float(ma200.dropna().iloc[-5])
            if m50 > m200 and m50p <= m200p:
                score += 18
                sigs.append({"type": "bullish",
                              "msg":    "Golden Cross (50MA > 200MA) — strongest long-term bull signal",
                              "msg_kr": "골든크로스 (50MA > 200MA) — 가장 강한 장기 강세 신호"})
            elif m50 < m200 and m50p >= m200p:
                score -= 18
                sigs.append({"type": "bearish",
                              "msg":    "Death Cross (50MA < 200MA) — long-term bear warning",
                              "msg_kr": "데드크로스 (50MA < 200MA) — 장기 약세장 전환 경고"})
            elif m50 > m200:
                score += 8
                sigs.append({"type": "bullish",
                              "msg":    "Above 200-day MA — long-term uptrend intact",
                              "msg_kr": "200일 이동평균 위 — 장기 상승추세 유지"})
            else:
                score -= 8
                sigs.append({"type": "bearish",
                              "msg":    "Below 200-day MA — long-term downtrend",
                              "msg_kr": "200일 이동평균 아래 — 장기 하락추세"})
        elif len(ma50.dropna()) >= 1:
            if float(close.iloc[-1]) > float(ma50.iloc[-1]):
                score += 5
                sigs.append({"type": "bullish",
                              "msg":    "Above 50-day MA — short-term strength",
                              "msg_kr": "50일 이동평균 위 — 단기 강세"})

        # Volume ──────────────────────────────────────────────────────────────
        vol_avg = vol.rolling(20).mean()
        if len(vol_avg.dropna()):
            vc, va = float(vol.iloc[-1]), float(vol_avg.iloc[-1])
            cc, cp = float(close.iloc[-1]), float(close.iloc[-2]) if len(close) > 1 else float(close.iloc[-1])
            if vc > va * 1.5 and cc > cp:
                score += 12
                sigs.append({"type": "bullish",
                              "msg":    "High-volume breakout — institutional accumulation detected",
                              "msg_kr": "거래량 급증 상승 — 기관 매수 추정"})
            elif vc > va * 1.5 and cc < cp:
                score -= 12
                sigs.append({"type": "bearish",
                              "msg":    "High-volume selloff — institutional distribution detected",
                              "msg_kr": "거래량 급증 하락 — 기관 매도 추정"})

        # ADX — Trend Strength ────────────────────────────────────────────────
        if "High" in hist.columns and "Low" in hist.columns:
            high = hist["High"].astype(float)
            low = hist["Low"].astype(float)
            adx = self._adx(high, low, close)
            if adx is not None and len(adx.dropna()):
                adx_val = float(adx.dropna().iloc[-1])
                if adx_val > 40:
                    # Strong trend — trust momentum signals more
                    trend_dir = "up" if above_200ma else "down"
                    if trend_dir == "up":
                        score += 8
                        sigs.append({"type": "bullish",
                                      "msg": f"ADX {adx_val:.0f} — strong uptrend confirmed",
                                      "msg_kr": f"ADX {adx_val:.0f} — 강한 상승추세 확인"})
                    else:
                        score -= 8
                        sigs.append({"type": "bearish",
                                      "msg": f"ADX {adx_val:.0f} — strong downtrend confirmed",
                                      "msg_kr": f"ADX {adx_val:.0f} — 강한 하락추세 확인"})
                elif adx_val < 20:
                    sigs.append({"type": "neutral",
                                  "msg": f"ADX {adx_val:.0f} — no clear trend, choppy market",
                                  "msg_kr": f"ADX {adx_val:.0f} — 추세 없음, 횡보"})

            # Stochastic ──────────────────────────────────────────────────────
            stoch = self._stochastic(high, low, close)
            if stoch:
                k_line, d_line = stoch
                if len(k_line.dropna()):
                    k = float(k_line.dropna().iloc[-1])
                    if k < 20 and above_200ma:
                        score += 8
                        sigs.append({"type": "bullish",
                                      "msg": f"Stochastic oversold ({k:.0f}) in uptrend — buy dip",
                                      "msg_kr": f"스토캐스틱 과매도 ({k:.0f}) 상승추세 — 저가 매수 기회"})
                    elif k > 80:
                        score -= 5
                        sigs.append({"type": "bearish",
                                      "msg": f"Stochastic overbought ({k:.0f})",
                                      "msg_kr": f"스토캐스틱 과매수 ({k:.0f})"})

            # OBV Trend — money flow ──────────────────────────────────────────
            obv = self._obv(close, vol)
            if obv is not None and len(obv.dropna()) >= 20:
                obv_sma = obv.rolling(20).mean()
                if len(obv_sma.dropna()):
                    obv_cur = float(obv.dropna().iloc[-1])
                    obv_avg = float(obv_sma.dropna().iloc[-1])
                    if obv_cur > obv_avg * 1.1:
                        score += 5
                        sigs.append({"type": "bullish",
                                      "msg": "OBV rising — smart money accumulating",
                                      "msg_kr": "OBV 상승 — 스마트머니 매집 중"})
                    elif obv_cur < obv_avg * 0.9:
                        score -= 5
                        sigs.append({"type": "bearish",
                                      "msg": "OBV declining — smart money distributing",
                                      "msg_kr": "OBV 하락 — 스마트머니 매도 중"})

        # ── Advanced Indicators (ta library) ─────────────────────────────────
        try:
            if "High" in hist.columns and "Low" in hist.columns:
                high = hist["High"].astype(float)
                low = hist["Low"].astype(float)

                # Ichimoku Cloud — trend direction + support/resistance
                from ta.trend import IchimokuIndicator
                ichi = IchimokuIndicator(high=high, low=low, close=close)
                span_a = ichi.ichimoku_a()
                span_b = ichi.ichimoku_b()
                if len(span_a.dropna()) > 0 and len(span_b.dropna()) > 0:
                    sa = float(span_a.dropna().iloc[-1])
                    sb = float(span_b.dropna().iloc[-1])
                    if cur_price > max(sa, sb):
                        score += 6
                        sigs.append({"type": "bullish",
                                      "msg": "Above Ichimoku Cloud — bullish structure",
                                      "msg_kr": "이치모쿠 구름 위 — 강세 구조"})
                    elif cur_price < min(sa, sb):
                        score -= 6
                        sigs.append({"type": "bearish",
                                      "msg": "Below Ichimoku Cloud — bearish structure",
                                      "msg_kr": "이치모쿠 구름 아래 — 약세 구조"})

                # CCI — Commodity Channel Index (mean-reversion + trend)
                from ta.trend import CCIIndicator
                cci = CCIIndicator(high=high, low=low, close=close).cci()
                if len(cci.dropna()) > 0:
                    cci_val = float(cci.dropna().iloc[-1])
                    if cci_val < -200 and above_200ma:
                        score += 8
                        sigs.append({"type": "bullish",
                                      "msg": f"CCI extreme oversold ({cci_val:.0f}) in uptrend — snap-back likely",
                                      "msg_kr": f"CCI 극단적 과매도 ({cci_val:.0f}) 상승추세 — 급반등 기대"})
                    elif cci_val > 200:
                        score -= 5
                        sigs.append({"type": "bearish",
                                      "msg": f"CCI extreme overbought ({cci_val:.0f}) — overextended",
                                      "msg_kr": f"CCI 극단적 과매수 ({cci_val:.0f}) — 과열"})

                # MFI — Money Flow Index (volume-weighted RSI)
                from ta.volume import MFIIndicator
                mfi = MFIIndicator(high=high, low=low, close=close, volume=vol).money_flow_index()
                if len(mfi.dropna()) > 0:
                    mfi_val = float(mfi.dropna().iloc[-1])
                    if mfi_val < 20 and above_200ma:
                        score += 8
                        sigs.append({"type": "bullish",
                                      "msg": f"MFI oversold ({mfi_val:.0f}) — heavy buying pressure",
                                      "msg_kr": f"MFI 과매도 ({mfi_val:.0f}) — 강한 매수세"})
                    elif mfi_val > 80:
                        score -= 5
                        sigs.append({"type": "bearish",
                                      "msg": f"MFI overbought ({mfi_val:.0f}) — selling pressure building",
                                      "msg_kr": f"MFI 과매수 ({mfi_val:.0f}) — 매도세 형성"})

                # Keltner Channel — volatility squeeze detection
                from ta.volatility import KeltnerChannel
                kc = KeltnerChannel(high=high, low=low, close=close)
                kc_high = kc.keltner_channel_hband()
                kc_low = kc.keltner_channel_lband()
                if len(kc_high.dropna()) > 0:
                    kch = float(kc_high.dropna().iloc[-1])
                    kcl = float(kc_low.dropna().iloc[-1])
                    # Bollinger inside Keltner = squeeze (low vol → breakout imminent)
                    ub_bb, _, lb_bb = self._bollinger(close)
                    if len(ub_bb.dropna()) > 0:
                        bb_upper = float(ub_bb.dropna().iloc[-1])
                        bb_lower = float(lb_bb.dropna().iloc[-1])
                        if bb_upper < kch and bb_lower > kcl:
                            sigs.append({"type": "neutral",
                                          "msg": "Volatility squeeze detected — breakout imminent",
                                          "msg_kr": "변동성 압축 감지 — 돌파 임박"})

                # Williams %R — momentum confirmation
                from ta.momentum import WilliamsRIndicator
                wr = WilliamsRIndicator(high=high, low=low, close=close).williams_r()
                if len(wr.dropna()) > 0:
                    wr_val = float(wr.dropna().iloc[-1])
                    if wr_val < -80 and above_200ma:
                        score += 5
                    elif wr_val > -20:
                        score -= 3

                # Aroon — trend maturity
                from ta.trend import AroonIndicator
                aroon = AroonIndicator(high=high, low=low)
                aroon_up = aroon.aroon_up()
                aroon_down = aroon.aroon_down()
                if len(aroon_up.dropna()) > 0:
                    au = float(aroon_up.dropna().iloc[-1])
                    ad = float(aroon_down.dropna().iloc[-1])
                    if au > 80 and ad < 20:
                        score += 5
                        sigs.append({"type": "bullish",
                                      "msg": f"Aroon strong uptrend (↑{au:.0f} ↓{ad:.0f})",
                                      "msg_kr": f"아룬 강한 상승 (↑{au:.0f} ↓{ad:.0f})"})
                    elif ad > 80 and au < 20:
                        score -= 5
                        sigs.append({"type": "bearish",
                                      "msg": f"Aroon strong downtrend (↑{au:.0f} ↓{ad:.0f})",
                                      "msg_kr": f"아룬 강한 하락 (↑{au:.0f} ↓{ad:.0f})"})
        except Exception:
            pass  # ta library indicators are bonus — don't break if unavailable

        return max(0.0, min(100.0, score)), sigs

    # ── Fundamental Analysis ──────────────────────────────────────────────────

    def _fundamental(self, snap: dict) -> tuple[float, list[dict]]:
        sigs  = []
        score = 50.0

        # P/E Ratio ───────────────────────────────────────────────────────────
        pe = snap.get("pe_ratio") or snap.get("forward_pe")
        if pe and pe > 0:
            if pe < 12:
                score += 22
                sigs.append({"type": "bullish",
                              "msg":    f"Very low P/E ({pe:.1f}x) — deep value; intrinsic undervaluation",
                              "msg_kr": f"매우 낮은 P/E ({pe:.1f}x) — 명확한 저평가"})
            elif pe < 20:
                score += 12
                sigs.append({"type": "bullish",
                              "msg":    f"Reasonable P/E ({pe:.1f}x) — fairly valued",
                              "msg_kr": f"합리적 P/E ({pe:.1f}x) — 적정 밸류에이션"})
            elif pe < 30:
                score += 3
                sigs.append({"type": "neutral",
                              "msg":    f"Elevated P/E ({pe:.1f}x) — growth premium embedded",
                              "msg_kr": f"다소 높은 P/E ({pe:.1f}x) — 성장 프리미엄 반영"})
            elif pe > 50:
                score -= 18
                sigs.append({"type": "bearish",
                              "msg":    f"Very high P/E ({pe:.1f}x) — expensive; execution risk",
                              "msg_kr": f"고 P/E ({pe:.1f}x) — 높은 가격, 실적 부담"})
            else:
                score -= 8
                sigs.append({"type": "bearish",
                              "msg":    f"High P/E ({pe:.1f}x)",
                              "msg_kr": f"높은 P/E ({pe:.1f}x)"})

        # Revenue Growth ──────────────────────────────────────────────────────
        rev_g = snap.get("revenue_growth")
        if rev_g is not None:
            pct = rev_g * 100
            if pct > 25:
                score += 20
                sigs.append({"type": "bullish",
                              "msg":    f"Strong revenue growth (+{pct:.0f}%) — powerful top-line momentum",
                              "msg_kr": f"매출 고성장 (+{pct:.0f}%) — 강한 사업 모멘텀"})
            elif pct > 10:
                score += 10
                sigs.append({"type": "bullish",
                              "msg":    f"Solid revenue growth (+{pct:.0f}%)",
                              "msg_kr": f"안정적 매출 성장 (+{pct:.0f}%)"})
            elif pct < 0:
                score -= 15
                sigs.append({"type": "bearish",
                              "msg":    f"Revenue declining ({pct:.1f}%) — core business under pressure",
                              "msg_kr": f"매출 감소 ({pct:.1f}%) — 핵심 사업 둔화"})

        # Profit Margin ───────────────────────────────────────────────────────
        margin = snap.get("profit_margin")
        if margin is not None:
            pct = margin * 100
            if pct > 20:
                score += 15
                sigs.append({"type": "bullish",
                              "msg":    f"Excellent profit margin ({pct:.0f}%) — wide economic moat",
                              "msg_kr": f"우수한 순이익률 ({pct:.0f}%) — 경제적 해자 존재"})
            elif pct > 10:
                score += 7
                sigs.append({"type": "neutral",
                              "msg":    f"Healthy profit margin ({pct:.0f}%)",
                              "msg_kr": f"양호한 순이익률 ({pct:.0f}%)"})
            elif pct < 0:
                score -= 18
                sigs.append({"type": "bearish",
                              "msg":    "Unprofitable — monitor path to positive FCF",
                              "msg_kr": "적자 기업 — 흑자 전환 일정 확인 필요"})

        # Leverage ────────────────────────────────────────────────────────────
        de = snap.get("debt_equity")
        if de is not None:
            if de < 30:
                score += 10
                sigs.append({"type": "bullish",
                              "msg":    "Low leverage — fortress balance sheet",
                              "msg_kr": "저부채 — 탄탄한 재무구조"})
            elif de > 200:
                score -= 12
                sigs.append({"type": "bearish",
                              "msg":    f"High leverage (D/E {de:.0f}%) — rate-sensitivity risk",
                              "msg_kr": f"고레버리지 (D/E {de:.0f}%) — 금리 민감도 위험"})

        # Beta ────────────────────────────────────────────────────────────────
        beta = snap.get("beta")
        if beta and beta > 2.0:
            score -= 5
            sigs.append({"type": "bearish",
                          "msg":    f"High beta ({beta:.1f}) — amplified market swings",
                          "msg_kr": f"고 베타 ({beta:.1f}) — 시장 변동성 증폭"})

        # Forward P/E vs Trailing P/E — growth expectation ────────────────────
        fwd_pe = snap.get("forward_pe")
        trail_pe = snap.get("pe_ratio")
        if fwd_pe and trail_pe and fwd_pe > 0 and trail_pe > 0:
            pe_compression = (fwd_pe - trail_pe) / trail_pe * 100
            if pe_compression < -20:
                score += 8
                sigs.append({"type": "bullish",
                              "msg": f"Earnings growth expected — Forward P/E {fwd_pe:.1f}x vs Trailing {trail_pe:.1f}x",
                              "msg_kr": f"실적 성장 기대 — Forward P/E {fwd_pe:.1f}x vs Trailing {trail_pe:.1f}x"})
            elif pe_compression > 20:
                score -= 5
                sigs.append({"type": "bearish",
                              "msg": f"Earnings decline expected — Forward P/E {fwd_pe:.1f}x vs Trailing {trail_pe:.1f}x",
                              "msg_kr": f"실적 둔화 예상 — Forward P/E {fwd_pe:.1f}x vs Trailing {trail_pe:.1f}x"})

        # EPS positive/negative ───────────────────────────────────────────────
        eps = snap.get("eps")
        if eps is not None:
            if eps > 0 and (margin is not None and margin > 0):
                score += 3  # Profitable company bonus
            elif eps < 0 and not (rev_g and rev_g > 0.5):
                # Unprofitable AND not hyper-growing = bad
                score -= 8
                sigs.append({"type": "bearish",
                              "msg": f"Negative EPS (${eps:.2f}) without high growth",
                              "msg_kr": f"EPS 적자 (${eps:.2f}) 고성장 없음"})

        return max(0.0, min(100.0, score)), sigs

    # ── Position Sizing ────────────────────────────────────────────────────────

    def _size(self, score: float, price: float, capital: float,
              signal: str = "POSITIVE") -> tuple[float, int, str]:
        if signal != "POSITIVE":
            return 0.0, 0, ""
        if capital <= 0 or price <= 0:
            return 0.0, 0, "NO_CAPITAL"
        if capital < price:
            return 0.0, 0, "INSUFFICIENT"   # can't buy even 1 share

        # Max affordable shares as upper bound
        max_affordable = int(capital / price)

        if score >= 85:
            alloc, timing = 0.45, "Full conviction — aggressive accumulation"
        elif score >= 80:
            alloc, timing = 0.35, "High conviction — strong accumulation"
        elif score >= 75:
            alloc, timing = 0.25, "Scale in aggressively over the week"
        else:
            alloc, timing = 0.15, "Pilot entry — build position on dips"

        invest = min(capital * alloc, capital * self.MAX_ALLOC)
        shares = int(invest / price)

        # Always recommend at least 1 share if affordable
        if shares < 1:
            shares = 1
            timing = "Minimum entry — 1 share"

        # Never exceed what user can actually afford
        shares = min(shares, max_affordable)

        return round(shares * price, 2), shares, timing

    # ── Reason Builder ────────────────────────────────────────────────────────

    def _reason(self, sig: str, score: float, tech: float, fund: float, news: float, quant: float = 50.0, weights: str = ""):
        dom = max([("Technical", tech), ("Fundamental", fund), ("News Sentiment", news), ("Quant Models", quant)],
                  key=lambda x: x[1])
        dom_kr = {"Technical": "기술적 분석", "Fundamental": "기본적 분석",
                  "News Sentiment": "뉴스 센티멘트", "Quant Models": "퀀트 모델"}[dom[0]]
        if not weights:
            weights = "Adaptive"
        en = (f"Composite score {score:.0f}/100 ({weights}). Primary driver: {dom[0]} ({dom[1]:.0f} pts). "
              + {"POSITIVE":  "Multi-factor quant model detects favorable conditions. Scale in with defined risk.",
                 "NEUTRAL": "Hold current position. Await stronger signal before adding.",
                 "NEGATIVE": "Quant model flags deteriorating conditions. Consider reducing or exiting position."}.get(sig, ""))
        kr = (f"종합 점수 {score:.0f}/100 ({weights}). 주요 동인: {dom_kr} ({dom[1]:.0f}점). "
              + {"POSITIVE":  "멀티팩터 퀀트 모델이 유리한 조건 감지. 분할 진입 권장.",
                 "NEUTRAL": "현 포지션 유지. 추가 진입 시그널 대기.",
                 "NEGATIVE": "퀀트 모델이 약세 신호 감지. 포지션 축소 또는 청산 고려."}.get(sig, ""))
        return en, kr

    # ── Portfolio-Level Analytics ─────────────────────────────────────────────

    def portfolio_analytics(self, positions: list[dict], capital: float) -> dict:
        """
        Approximate Sharpe, Max Drawdown, sector allocation.
        Uses 3-month price history. No AI, no external paid APIs.
        """
        if not positions:
            return {}

        total_mv = sum(p.get("market_value", 0) for p in positions)
        sector_alloc: dict[str, float] = {}
        combined: pd.Series | None = None

        for pos in positions:
            ticker = pos.get("ticker", "")
            weight = pos.get("market_value", 0) / total_mv if total_mv > 0 else 0
            sector = pos.get("sector", "Unknown")
            sector_alloc[sector] = sector_alloc.get(sector, 0) + weight * 100

            try:
                h = fmp.get_history(ticker, period="3mo")
                if h.empty or len(h) < 20:
                    continue
                ret = h["Close"].pct_change().dropna() * weight
                combined = ret if combined is None else combined.add(ret, fill_value=0)
            except Exception:
                pass

        result: dict = {
            "total_value":   round(total_mv, 2),
            "cash":          round(capital, 2),
            "invested_pct":  round(total_mv / (total_mv + capital) * 100, 1) if (total_mv + capital) > 0 else 0,
            "sector_allocation": {k: round(v, 1) for k, v in
                                   sorted(sector_alloc.items(), key=lambda x: -x[1])},
        }

        if combined is not None and len(combined) >= 20:
            ann_ret = float(combined.mean()) * 252
            ann_vol = float(combined.std()) * np.sqrt(252)
            sharpe  = (ann_ret - 0.045) / ann_vol if ann_vol > 0 else 0  # 4.5% RF rate
            cum     = (1 + combined).cumprod()
            dd      = ((cum - cum.cummax()) / cum.cummax()).min() * 100
            result.update({
                "ann_return_pct":   round(ann_ret * 100, 2),
                "ann_vol_pct":      round(ann_vol * 100, 2),
                "sharpe_ratio":     round(sharpe, 2),
                "max_drawdown_pct": round(float(dd), 2),
            })

        return result

    # ── Math Primitives ───────────────────────────────────────────────────────

    @staticmethod
    def _rsi(p: pd.Series, n: int = 14) -> pd.Series:
        try:
            from ta.momentum import RSIIndicator
            return RSIIndicator(close=p, window=n).rsi()
        except Exception:
            d = p.diff()
            g = d.where(d > 0, 0.0).rolling(n).mean()
            l = (-d.where(d < 0, 0.0)).rolling(n).mean()
            return 100 - 100 / (1 + g / l.replace(0, np.nan))

    @staticmethod
    def _macd(p: pd.Series) -> tuple[pd.Series, pd.Series]:
        try:
            from ta.trend import MACD as MACD_TA
            macd_ind = MACD_TA(close=p)
            return macd_ind.macd(), macd_ind.macd_signal()
        except Exception:
            m = p.ewm(span=12, adjust=False).mean() - p.ewm(span=26, adjust=False).mean()
            return m, m.ewm(span=9, adjust=False).mean()

    @staticmethod
    def _bollinger(p: pd.Series, n: int = 20, k: float = 2.0):
        try:
            from ta.volatility import BollingerBands
            bb = BollingerBands(close=p, window=n, window_dev=k)
            return bb.bollinger_hband(), bb.bollinger_mavg(), bb.bollinger_lband()
        except Exception:
            mid = p.rolling(n).mean()
            std = p.rolling(n).std()
            return mid + k * std, mid, mid - k * std

    @staticmethod
    def _adx(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> "pd.Series | None":
        """Average Directional Index — trend strength (0-100). >25 = trending."""
        try:
            from ta.trend import ADXIndicator
            return ADXIndicator(high=high, low=low, close=close, window=n).adx()
        except Exception:
            return None

    @staticmethod
    def _stochastic(high: pd.Series, low: pd.Series, close: pd.Series) -> "tuple[pd.Series, pd.Series] | None":
        """Stochastic Oscillator — %K and %D."""
        try:
            from ta.momentum import StochasticOscillator
            stoch = StochasticOscillator(high=high, low=low, close=close)
            return stoch.stoch(), stoch.stoch_signal()
        except Exception:
            return None

    @staticmethod
    def _obv(close: pd.Series, volume: pd.Series) -> "pd.Series | None":
        """On-Balance Volume — accumulation/distribution."""
        try:
            from ta.volume import OnBalanceVolumeIndicator
            return OnBalanceVolumeIndicator(close=close, volume=volume).on_balance_volume()
        except Exception:
            return None

    # ── Advanced Quant Models ────────────────────────────────────────────────────

    def _quant_models(self, hist: pd.DataFrame, profile_params: dict = None,
                       news_score: float = 50) -> tuple[float, list[dict]]:
        """Run Mean Reversion + Momentum Breakout + Volatility Regime +
        Disposition Effect + Order Flow + Anchoring Bias + Sentiment Divergence models."""
        sigs = []
        score = 50.0
        close = hist["Close"].astype(float).values
        high = hist["High"].astype(float).values
        low = hist["Low"].astype(float).values
        vol = hist["Volume"].astype(float).values
        opens = hist["Open"].astype(float).values if "Open" in hist.columns else close.copy()

        # 1. Mean Reversion (10% → maps to 0-100)
        try:
            mr = MeanReversion.analyze(close)
            if mr:
                mr["score"]
                z = mr["z_score"]
                if z < -2:
                    score += 20
                    sigs.append({"type": "bullish",
                                 "msg": f"Mean Reversion: Price {abs(z):.1f}σ below mean — strong bounce expected",
                                 "msg_kr": f"평균회귀: 가격이 평균보다 {abs(z):.1f}σ 아래 — 강한 반등 예상"})
                elif z < -1:
                    score += 10
                    sigs.append({"type": "bullish",
                                 "msg": f"Mean Reversion: Price {abs(z):.1f}σ below mean",
                                 "msg_kr": f"평균회귀: 가격이 평균보다 {abs(z):.1f}σ 아래"})
                elif z > 2:
                    score -= 20
                    sigs.append({"type": "bearish",
                                 "msg": f"Mean Reversion: Price {z:.1f}σ above mean — pullback risk",
                                 "msg_kr": f"평균회귀: 가격이 평균보다 {z:.1f}σ 위 — 조정 위험"})
                elif z > 1:
                    score -= 10
                    sigs.append({"type": "bearish",
                                 "msg": f"Mean Reversion: Price {z:.1f}σ above mean — extended",
                                 "msg_kr": f"평균회귀: 가격이 평균보다 {z:.1f}σ 위 — 과확장"})
        except Exception:
            pass

        # 2. Momentum Breakout (10%)
        try:
            mb = MomentumBreakout.analyze(close, high, low, vol)
            if mb:
                if mb["signal"] == "POSITIVE":
                    score += 20
                    for s in mb.get("signals", []):
                        sigs.append(s)
                elif mb["signal"] == "NEGATIVE":
                    score -= 20
                    for s in mb.get("signals", []):
                        sigs.append(s)
                elif mb.get("signals"):
                    for s in mb["signals"]:
                        sigs.append(s)
        except Exception:
            pass

        # 3. Volatility Regime (10%)
        try:
            vr = VolatilityRegime.analyze(close)
            if vr:
                regime = vr["regime"]
                if regime == "LOW_VOL":
                    score += 8
                    sigs.append({"type": "bullish",
                                 "msg": f"Volatility: Low ({vr['current_vol']:.0f}%) — favorable for entries",
                                 "msg_kr": f"변동성: 저 ({vr['current_vol']:.0f}%) — 진입에 유리"})
                elif regime == "HIGH_VOL":
                    score -= 10
                    sigs.append({"type": "bearish",
                                 "msg": f"Volatility: High ({vr['current_vol']:.0f}%) — reduce exposure",
                                 "msg_kr": f"변동성: 고 ({vr['current_vol']:.0f}%) — 노출 축소 권고"})
                elif regime == "CRISIS":
                    score -= 20
                    sigs.append({"type": "bearish",
                                 "msg": f"Volatility: CRISIS ({vr['current_vol']:.0f}%) — cash is king",
                                 "msg_kr": f"변동성: 위기 ({vr['current_vol']:.0f}%) — 현금 보유 권고"})
        except Exception:
            pass

        # 4. Regime Switching (10%)
        try:
            rs = RegimeSwitching.analyze(close)
            if rs:
                regime = rs["regime"]
                if regime in ("BULL",):
                    score += 15
                    sigs.append({"type": "bullish",
                                 "msg": f"Regime: {rs['label']} (Sharpe {rs['sharpe_20d']:.1f}) — momentum favors longs",
                                 "msg_kr": f"시장체제: {rs['label_kr']} (샤프 {rs['sharpe_20d']:.1f}) — 매수 유리"})
                elif regime == "MILD_BULL":
                    score += 8
                    sigs.append({"type": "bullish",
                                 "msg": f"Regime: {rs['label']} — cautiously bullish",
                                 "msg_kr": f"시장체제: {rs['label_kr']} — 조심스러운 강세"})
                elif regime in ("BEAR",):
                    score -= 15
                    sigs.append({"type": "bearish",
                                 "msg": f"Regime: {rs['label']} (Sharpe {rs['sharpe_20d']:.1f}) — avoid new longs",
                                 "msg_kr": f"시장체제: {rs['label_kr']} (샤프 {rs['sharpe_20d']:.1f}) — 신규 매수 회피"})
                elif regime == "MILD_BEAR":
                    score -= 8
                    sigs.append({"type": "bearish",
                                 "msg": f"Regime: {rs['label']} — defensive positioning",
                                 "msg_kr": f"시장체제: {rs['label_kr']} — 방어적 포지션"})
                if rs.get("shifting"):
                    sigs.append({"type": "neutral",
                                 "msg": f"Regime Shift: {rs['shift_direction']}",
                                 "msg_kr": f"체제 전환: {rs['shift_kr']}"})
        except Exception:
            pass

        # 5. ML Signal
        try:
            ml = MLSignal.generate(close, high, low, vol)
            if ml:
                if ml["signal"] == "BULLISH":
                    score += min(12, ml["confidence"] / 100 * 12)
                    sigs.append({"type": "bullish",
                                 "msg": f"ML Signal: BULLISH — {ml['votes_up']}↑ vs {ml['votes_down']}↓ votes (↑{ml['prob_up']:.0f}% confidence {ml['confidence']:.0f}%)",
                                 "msg_kr": f"ML 시그널: 강세 — {ml['votes_up']}↑ vs {ml['votes_down']}↓ 투표 (상승 {ml['prob_up']:.0f}% 신뢰도 {ml['confidence']:.0f}%)"})
                elif ml["signal"] == "BEARISH":
                    score -= min(12, ml["confidence"] / 100 * 12)
                    sigs.append({"type": "bearish",
                                 "msg": f"ML Signal: BEARISH — {ml['votes_up']}↑ vs {ml['votes_down']}↓ votes (↓{ml['prob_down']:.0f}% confidence {ml['confidence']:.0f}%)",
                                 "msg_kr": f"ML 시그널: 약세 — {ml['votes_up']}↑ vs {ml['votes_down']}↓ 투표 (하락 {ml['prob_down']:.0f}% 신뢰도 {ml['confidence']:.0f}%)"})
                else:
                    sigs.append({"type": "neutral",
                                 "msg": f"ML Signal: NEUTRAL — {ml['votes_up']}↑ vs {ml['votes_down']}↓ votes (confidence {ml['confidence']:.0f}%)",
                                 "msg_kr": f"ML 시그널: 중립 — {ml['votes_up']}↑ vs {ml['votes_down']}↓ 투표 (신뢰도 {ml['confidence']:.0f}%)"})
        except Exception:
            pass

        # 6. Variance Ratio Filter — trending vs mean-reverting regime
        vr_result = {"vr": 1.0, "regime": "unknown", "use_momentum": False}
        try:
            vr_result = VarianceRatioFilter.calculate(list(close))
            if vr_result["use_momentum"]:
                score += 10
                sigs.append({"type": "bullish",
                             "msg": f"Variance Ratio: Trending regime (VR={vr_result['vr']:.2f}) — momentum strategies favored",
                             "msg_kr": f"분산비: 추세 레짐 (VR={vr_result['vr']:.2f}) — 모멘텀 전략 유리"})
            elif vr_result["regime"] == "mean_reverting":
                sigs.append({"type": "neutral",
                             "msg": f"Variance Ratio: Mean-reverting regime (VR={vr_result['vr']:.2f})",
                             "msg_kr": f"분산비: 평균회귀 레짐 (VR={vr_result['vr']:.2f})"})
        except Exception:
            pass

        # 7. TSMOM — 12-month time-series momentum
        tsmom_result = {"signal": "NEUTRAL", "momentum_12m": 0, "strength": 0}
        try:
            tsmom_result = TSMOM.calculate(list(close))
            if tsmom_result["signal"] == "POSITIVE":
                score += 12
                sigs.append({"type": "bullish",
                             "msg": f"TSMOM: 12M return +{tsmom_result['momentum_12m']:.1f}% (strength {tsmom_result['strength']:.2f})",
                             "msg_kr": f"TSMOM: 12개월 수익률 +{tsmom_result['momentum_12m']:.1f}% (강도 {tsmom_result['strength']:.2f})"})
            elif tsmom_result["signal"] == "NEGATIVE":
                score -= 12
                sigs.append({"type": "bearish",
                             "msg": f"TSMOM: 12M return {tsmom_result['momentum_12m']:.1f}% (strength {tsmom_result['strength']:.2f})",
                             "msg_kr": f"TSMOM: 12개월 수익률 {tsmom_result['momentum_12m']:.1f}% (강도 {tsmom_result['strength']:.2f})"})
        except Exception:
            pass

        # 8. 52-Week High Momentum — nearness to 52-week high
        high52_result = {"ratio": 0, "signal": "NEUTRAL", "boost": 1.0}
        try:
            high52_result = FiftyTwoWeekHigh.calculate(list(close))
            if high52_result["signal"] == "POSITIVE":
                sigs.append({"type": "bullish",
                             "msg": f"52W High: {high52_result['ratio']:.1%} of high (${high52_result['high_52w']:.2f})" + (" — NEW HIGH" if high52_result.get("new_high_3d") else ""),
                             "msg_kr": f"52주 고점: 고점 대비 {high52_result['ratio']:.1%} (${high52_result['high_52w']:.2f})" + (" — 신고가" if high52_result.get("new_high_3d") else "")})
            elif high52_result["signal"] == "NEGATIVE":
                sigs.append({"type": "bearish",
                             "msg": f"52W High: Only {high52_result['ratio']:.1%} of high (${high52_result['high_52w']:.2f}) — deep pullback",
                             "msg_kr": f"52주 고점: 고점 대비 {high52_result['ratio']:.1%} (${high52_result['high_52w']:.2f}) — 큰 폭 하락"})
        except Exception:
            pass

        # 9. Disposition Effect — Capital Gains Overhang (Frazzini 2006)
        disp_result = {"cgo": None}
        try:
            if (not profile_params or profile_params.get("use_disposition", True)):
                closes_list = list(close)
                vols_list = list(vol)
                if len(closes_list) >= DispositionEffect.MIN_WINDOW:
                    disp_result = DispositionEffect.calculate(closes_list, vols_list)
                    cgo = disp_result.get("cgo", 0) or 0
                    # High CGO (>0.15) = selling pressure from retail → contrarian buy signal
                    if cgo > 0.15:
                        score += 8
                        sigs.append({"type": "bullish",
                                     "msg": f"Disposition Effect: High CGO ({cgo:.3f}) — retail selling pressure, contrarian buy",
                                     "msg_kr": f"처분효과: 높은 CGO ({cgo:.3f}) — 개인 매도 압력, 역발상 매수 신호"})
                    elif cgo < -0.15:
                        score -= 5
                        sigs.append({"type": "bearish",
                                     "msg": f"Disposition Effect: Low CGO ({cgo:.3f}) — no disposition pressure",
                                     "msg_kr": f"처분효과: 낮은 CGO ({cgo:.3f}) — 처분 압력 없음"})
        except Exception:
            pass

        # 10. Order Flow Imbalance — Cont, Kukanov & Stoikov (2014)
        ofi_result = {"ofi_normalized": None, "pressure_level": "neutral"}
        try:
            if (not profile_params or profile_params.get("use_order_flow", True)):
                opens_list = list(opens)
                closes_list = list(close)
                vols_list = list(vol)
                if len(closes_list) >= OrderFlowImbalance.MIN_WINDOW:
                    ofi_result = OrderFlowImbalance.calculate(opens_list, closes_list, vols_list)
                    pressure = ofi_result.get("pressure_level", "neutral")
                    if pressure == "high_positive":
                        score += 6
                        sigs.append({"type": "bullish",
                                     "msg": f"Order Flow: Strong buying pressure (OFI={ofi_result.get('ofi_normalized', 0):.3f})",
                                     "msg_kr": f"주문흐름: 강한 매수 압력 (OFI={ofi_result.get('ofi_normalized', 0):.3f})"})
                    elif pressure == "high_negative":
                        score -= 6
                        sigs.append({"type": "bearish",
                                     "msg": f"Order Flow: Strong selling pressure (OFI={ofi_result.get('ofi_normalized', 0):.3f})",
                                     "msg_kr": f"주문흐름: 강한 매도 압력 (OFI={ofi_result.get('ofi_normalized', 0):.3f})"})
        except Exception:
            pass

        # 11. Anchoring Bias — George & Hwang (2004)
        #     Multiplicative boost applied to composite later (like 52WeekHigh)
        anchor_result = {"nearness": None, "boost": 1.0}
        try:
            if (not profile_params or profile_params.get("use_anchoring", True)):
                closes_list = list(close)
                vols_list = list(vol)
                if len(closes_list) >= AnchoringBias.MIN_WINDOW:
                    anchor_result = AnchoringBias.calculate(closes_list, vols_list)
                    nearness = anchor_result.get("nearness", 0) or 0
                    # Derive boost: near 52W high = strong momentum → small positive boost
                    # Far from 52W high = weak momentum → small negative boost
                    if nearness > 0.95:
                        anchor_result["boost"] = 1.03   # +3% composite boost
                        sigs.append({"type": "bullish",
                                     "msg": f"Anchoring: Near 52W high ({nearness:.1%}) — momentum intact",
                                     "msg_kr": f"앵커링: 52주 고점 근접 ({nearness:.1%}) — 모멘텀 유지"})
                    elif nearness > 0.85:
                        anchor_result["boost"] = 1.01   # +1% mild boost
                    elif nearness < 0.70:
                        anchor_result["boost"] = 0.97   # -3% composite drag
                        sigs.append({"type": "bearish",
                                     "msg": f"Anchoring: Far from 52W high ({nearness:.1%}) — weak momentum",
                                     "msg_kr": f"앵커링: 52주 고점 대비 괴리 ({nearness:.1%}) — 약한 모멘텀"})
                    else:
                        anchor_result["boost"] = 1.0    # neutral zone
        except Exception:
            pass

        # 12b. Donchian Channel Breakout — Turtle Trading simplified (55/20)
        donchian_result = {"signal": "NEUTRAL", "entry_level": None, "exit_level": None}
        try:
            donchian_result = DonchianBreakout.calculate(list(high), list(low), list(close))
            if donchian_result["signal"] == "POSITIVE":
                score += 10
                sigs.append({"type": "bullish",
                             "msg": f"Donchian Breakout: Price broke 55-day high (${donchian_result.get('entry_level')})",
                             "msg_kr": f"돈치안 돌파: 55일 신고가 돌파 (${donchian_result.get('entry_level')})"})
            elif donchian_result["signal"] == "NEGATIVE":
                score -= 10
                sigs.append({"type": "bearish",
                             "msg": f"Donchian Breakout: Price broke 20-day low (${donchian_result.get('exit_level')})",
                             "msg_kr": f"돈치안 이탈: 20일 저가 이탈 (${donchian_result.get('exit_level')})"})
        except Exception:
            pass

        # 12c. Dual Momentum — Antonacci (absolute + relative vs SPY benchmark)
        dual_mom_result = {"signal": "NEUTRAL", "absolute_momentum": None, "relative_momentum": None}
        try:
            if len(close) >= 252:
                from services.container import fetcher as _fetcher_dm
                bench_hist = _fetcher_dm.get_price_history("SPY", "1y")
                if bench_hist is not None and not bench_hist.empty and len(bench_hist) >= 252:
                    bench_closes = bench_hist["Close"].astype(float).values
                    dual_mom_result = DualMomentum.calculate(list(close), list(bench_closes))
                    if dual_mom_result["signal"] == "POSITIVE":
                        score += 10
                        sigs.append({"type": "bullish",
                                     "msg": f"Dual Momentum: Asset +{dual_mom_result['asset_return_12m']:.1f}% beats SPY +{dual_mom_result['benchmark_return_12m']:.1f}%",
                                     "msg_kr": f"듀얼 모멘텀: 자산 +{dual_mom_result['asset_return_12m']:.1f}% > SPY +{dual_mom_result['benchmark_return_12m']:.1f}%"})
                    elif dual_mom_result["signal"] == "NEGATIVE":
                        score -= 10
                        sigs.append({"type": "bearish",
                                     "msg": f"Dual Momentum: Asset {dual_mom_result['asset_return_12m']:.1f}% (absolute momentum fails)",
                                     "msg_kr": f"듀얼 모멘텀: 자산 {dual_mom_result['asset_return_12m']:.1f}% (절대 모멘텀 실패)"})
        except Exception:
            pass

        # 12d. Correlation Regime — diversification breakdown detector (sector basket)
        corr_regime_result = {"avg_correlation": None, "regime": "unknown"}
        try:
            from services.container import fetcher as _fetcher_cr
            basket = ["SPY", "QQQ", "IWM", "DIA", "XLK"]
            returns_list = []
            for tk in basket:
                bh = _fetcher_cr.get_price_history(tk, "6mo")
                if bh is not None and not bh.empty and len(bh) >= 60:
                    br = bh["Close"].astype(float).pct_change().dropna().values
                    if len(br) >= 60:
                        returns_list.append(list(br))
            if len(returns_list) >= 2:
                corr_regime_result = CorrelationRegime.calculate(returns_list)
                regime = corr_regime_result.get("regime", "unknown")
                if regime == "high_correlation":
                    score -= 5
                    sigs.append({"type": "bearish",
                                 "msg": f"Correlation Regime: High ({corr_regime_result.get('avg_correlation')}) — systemic risk, diversification failing",
                                 "msg_kr": f"상관관계 레짐: 높음 ({corr_regime_result.get('avg_correlation')}) — 시스템 리스크, 분산 실패"})
                elif regime == "low_correlation":
                    score += 3
                    sigs.append({"type": "bullish",
                                 "msg": f"Correlation Regime: Low ({corr_regime_result.get('avg_correlation')}) — stock-picking environment",
                                 "msg_kr": f"상관관계 레짐: 낮음 ({corr_regime_result.get('avg_correlation')}) — 개별종목 장세"})
        except Exception:
            pass

        # 12. Sentiment-Price Divergence — detect sentiment/price disconnect
        spd_result = {"divergence_type": "none", "divergence_score": None}
        try:
            if (not profile_params or profile_params.get("use_sentiment_divergence", True)):
                closes_list = list(close)
                if len(closes_list) >= SentimentPriceDivergence.MIN_DATA:
                    # Use current news_score as constant proxy (no historical sentiment array)
                    window_len = min(len(closes_list), 30)
                    sentiment_scores = [news_score] * window_len
                    spd_result = SentimentPriceDivergence.calculate(
                        closes_list[-window_len:], sentiment_scores
                    )
                    div_type = spd_result.get("divergence_type", "neutral")
                    price_roc = spd_result.get("price_roc", 0)
                    sent_roc = spd_result.get("sentiment_roc", 0)

                    # Interpret direction: divergence + price falling but sentiment up = bullish
                    if div_type in ("strong_divergence", "mild_divergence"):
                        if price_roc < 0 and sent_roc >= 0:
                            # Sentiment up, price down → bullish divergence
                            score += 10
                            sigs.append({"type": "bullish",
                                         "msg": f"Sentiment Divergence: Bullish — sentiment holds while price drops ({spd_result.get('divergence_score', 0):.3f})",
                                         "msg_kr": f"센티먼트 괴리: 강세 — 가격 하락에도 심리 유지 ({spd_result.get('divergence_score', 0):.3f})"})
                        elif price_roc > 0 and sent_roc <= 0:
                            # Sentiment down, price up → bearish divergence
                            score -= 10
                            sigs.append({"type": "bearish",
                                         "msg": f"Sentiment Divergence: Bearish — price rises but sentiment deteriorates ({spd_result.get('divergence_score', 0):.3f})",
                                         "msg_kr": f"센티먼트 괴리: 약세 — 가격 상승에도 심리 악화 ({spd_result.get('divergence_score', 0):.3f})"})
        except Exception:
            pass

        return (max(0.0, min(100.0, score)), sigs, vr_result, tsmom_result, high52_result,
                disp_result, ofi_result, anchor_result, spd_result,
                donchian_result, dual_mom_result, corr_regime_result)
