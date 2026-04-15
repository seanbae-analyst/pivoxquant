"""
PivoxQuant — Day Trade Service (Alpaca Real-time)
Real-time momentum scanning + short-term technical analysis.
"""

import os
import logging
import threading
import time
import json
import numpy as np
from datetime import datetime, timedelta
from collections import deque

logger = logging.getLogger(__name__)

# Watchlist for day trading
DAY_TRADE_POOL = [
    "NVDA", "TSLA", "AAPL", "AMD", "META", "AMZN", "GOOGL", "MSFT",
    "PLTR", "COIN", "HOOD", "SOFI", "RIVN", "MSTR", "SMCI", "IONQ",
    "RKLB", "SOUN", "AI", "SPY",
]


class DayTradeService:

    def __init__(self):
        self.available = False
        self.client = None
        self.stream = None
        self._prices = {}       # {symbol: {price, timestamp, change, volume, ...}}
        self._bars_1m = {}      # {symbol: deque of 1-min bars}
        self._bars_5m = {}      # {symbol: deque of 5-min bars}
        self._subscribers = []  # SSE subscribers
        self._lock = threading.Lock()

        api_key = os.environ.get("ALPACA_API_KEY", "").strip()
        secret = os.environ.get("ALPACA_SECRET_KEY", "").strip()

        if api_key and secret:
            try:
                from alpaca.data.historical import StockHistoricalDataClient
                self.client = StockHistoricalDataClient(api_key, secret)
                self.api_key = api_key
                self.secret = secret
                self.available = True
                logger.info("DayTrade Service initialized (Alpaca)")
            except Exception as e:
                logger.warning(f"DayTrade init failed: {e}")

    def get_latest_prices(self):
        """Get latest prices for all day trade pool symbols."""
        if not self.available:
            return {}
        try:
            from alpaca.data.requests import StockLatestBarRequest
            req = StockLatestBarRequest(symbol_or_symbols=DAY_TRADE_POOL)
            bars = self.client.get_stock_latest_bar(req)
            result = {}
            for sym, bar in bars.items():
                result[sym] = {
                    "price": round(float(bar.close), 2),
                    "open": round(float(bar.open), 2),
                    "high": round(float(bar.high), 2),
                    "low": round(float(bar.low), 2),
                    "volume": int(bar.volume),
                    "timestamp": bar.timestamp.isoformat(),
                }
            return result
        except Exception as e:
            logger.error(f"Latest prices error: {e}")
            return {}

    def get_intraday_bars(self, ticker, timeframe="5Min", limit=100):
        """Get intraday bars for charting."""
        if not self.available:
            return []
        try:
            from alpaca.data.requests import StockBarsRequest
            from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
            tf = TimeFrame.Minute if timeframe == "1Min" else TimeFrame(5, TimeFrameUnit.Minute)
            start = datetime.utcnow() - timedelta(days=1)
            req = StockBarsRequest(
                symbol_or_symbols=ticker.upper(),
                timeframe=tf,
                start=start,
                limit=limit,
            )
            bars = self.client.get_stock_bars(req)
            data = []
            bar_data = bars.get(ticker.upper(), []) if hasattr(bars, 'get') else bars.data.get(ticker.upper(), [])
            for bar in bar_data:
                data.append({
                    "time": bar.timestamp.isoformat(),
                    "open": round(float(bar.open), 2),
                    "high": round(float(bar.high), 2),
                    "low": round(float(bar.low), 2),
                    "close": round(float(bar.close), 2),
                    "volume": int(bar.volume),
                    "vwap": round(float(bar.vwap), 2) if bar.vwap else None,
                })
            return data
        except Exception as e:
            logger.error(f"Intraday bars error {ticker}: {e}")
            return []

    def analyze_short_term(self, ticker):
        """Short-term momentum analysis using 5-min bars."""
        bars = self.get_intraday_bars(ticker, "5Min", 100)
        if len(bars) < 20:
            return None

        closes = np.array([b["close"] for b in bars])
        volumes = np.array([b["volume"] for b in bars])
        vwaps = [b["vwap"] for b in bars if b["vwap"]]

        score = 50.0
        signals = []

        # RSI (14 periods on 5-min bars)
        rsi = self._calc_rsi(closes, 14)
        if rsi is not None:
            if rsi < 30:
                score += 20
                signals.append({"type": "bullish", "msg": f"RSI oversold ({rsi:.0f}) — bounce likely", "msg_kr": f"RSI 과매도 ({rsi:.0f}) — 반등 가능성"})
            elif rsi < 45:
                score += 10
                signals.append({"type": "bullish", "msg": f"RSI building momentum ({rsi:.0f})", "msg_kr": f"RSI 모멘텀 형성 중 ({rsi:.0f})"})
            elif rsi > 70:
                score -= 20
                signals.append({"type": "bearish", "msg": f"RSI overbought ({rsi:.0f}) — pullback risk", "msg_kr": f"RSI 과매수 ({rsi:.0f}) — 조정 위험"})
            elif rsi > 55:
                score += 5
                signals.append({"type": "neutral", "msg": f"RSI healthy ({rsi:.0f})", "msg_kr": f"RSI 건강 구간 ({rsi:.0f})"})

        # EMA 9/21 Cross
        ema9 = self._calc_ema(closes, 9)
        ema21 = self._calc_ema(closes, 21)
        if ema9 is not None and ema21 is not None:
            if ema9[-1] > ema21[-1] and ema9[-2] <= ema21[-2]:
                score += 18
                signals.append({"type": "bullish", "msg": "EMA 9/21 Golden Cross — short-term uptrend", "msg_kr": "EMA 9/21 골든크로스 — 단기 상승 전환"})
            elif ema9[-1] < ema21[-1] and ema9[-2] >= ema21[-2]:
                score -= 18
                signals.append({"type": "bearish", "msg": "EMA 9/21 Death Cross — short-term downtrend", "msg_kr": "EMA 9/21 데드크로스 — 단기 하락 전환"})
            elif ema9[-1] > ema21[-1]:
                score += 8
                signals.append({"type": "bullish", "msg": "Price above EMA 21 — uptrend intact", "msg_kr": "EMA 21 위 — 상승 추세 유지"})
            else:
                score -= 8
                signals.append({"type": "bearish", "msg": "Price below EMA 21 — downtrend", "msg_kr": "EMA 21 아래 — 하락 추세"})

        # VWAP
        cur_price = closes[-1]
        if vwaps:
            last_vwap = vwaps[-1]
            if cur_price > last_vwap * 1.01:
                score += 10
                signals.append({"type": "bullish", "msg": f"Above VWAP (${last_vwap:.2f}) — institutional buying", "msg_kr": f"VWAP 위 (${last_vwap:.2f}) — 기관 매수세"})
            elif cur_price < last_vwap * 0.99:
                score -= 10
                signals.append({"type": "bearish", "msg": f"Below VWAP (${last_vwap:.2f}) — institutional selling", "msg_kr": f"VWAP 아래 (${last_vwap:.2f}) — 기관 매도세"})

        # Volume Spike
        avg_vol = np.mean(volumes[:-1]) if len(volumes) > 1 else 0
        cur_vol = volumes[-1]
        if avg_vol > 0 and cur_vol >= avg_vol * 3:
            price_chg = (closes[-1] - closes[-2]) / closes[-2] * 100 if len(closes) > 1 else 0
            if price_chg > 0:
                score += 15
                signals.append({"type": "bullish", "msg": f"Volume spike ({cur_vol/avg_vol:.1f}x avg) + price up — breakout", "msg_kr": f"거래량 급증 ({cur_vol/avg_vol:.1f}x) + 상승 — 돌파 신호"})
            else:
                score -= 15
                signals.append({"type": "bearish", "msg": f"Volume spike ({cur_vol/avg_vol:.1f}x avg) + price down — selloff", "msg_kr": f"거래량 급증 ({cur_vol/avg_vol:.1f}x) + 하락 — 매도세"})

        # 5. Quant Models on intraday data
        try:
            from quant_models import MeanReversion, VolatilityRegime, RegimeSwitching
            mr = MeanReversion.analyze(closes)
            if mr:
                z = mr["z_score"]
                if z < -1.5:
                    score += 10
                    signals.append({"type": "bullish", "msg": f"Intraday Mean Reversion: {abs(z):.1f}σ below avg", "msg_kr": f"장중 평균회귀: 평균 {abs(z):.1f}σ 아래"})
                elif z > 1.5:
                    score -= 10
                    signals.append({"type": "bearish", "msg": f"Intraday Mean Reversion: {z:.1f}σ above avg", "msg_kr": f"장중 평균회귀: 평균 {z:.1f}σ 위"})

            rs = RegimeSwitching.analyze(closes, period=min(len(closes)-5, 40))
            if rs and rs["regime"] in ("BEAR", "MILD_BEAR"):
                score -= 8
                signals.append({"type": "bearish", "msg": f"Intraday Regime: {rs['label']}", "msg_kr": f"장중 체제: {rs['label_kr']}"})
            elif rs and rs["regime"] in ("BULL",):
                score += 8
                signals.append({"type": "bullish", "msg": f"Intraday Regime: {rs['label']}", "msg_kr": f"장중 체제: {rs['label_kr']}"})
        except Exception:
            pass

        score = max(0, min(100, score))
        signal = "POSITIVE" if score >= 65 else "NEGATIVE" if score < 30 else "NEUTRAL"

        # Price change
        day_open = bars[0]["open"] if bars else cur_price
        change_pct = round((cur_price - day_open) / day_open * 100, 2) if day_open else 0

        # ── TP/SL + Trailing Stop (regime-adaptive) ──
        atr = self._calc_atr(bars, 14) if len(bars) >= 15 else None

        # Get daily regime for ATR multiplier adjustment
        regime_profile = "default"
        tp_mult, sl_mult = 2.0, 1.0  # ATR multipliers (default)
        try:
            import fmp_service as fmp
            from quant_models import AdaptiveParams
            hist = fmp.get_history(ticker, period="3mo")
            if not hist.empty and len(hist) >= 20:
                ap = AdaptiveParams.calculate(
                    hist["Close"].values, hist["High"].values,
                    hist["Low"].values, hist["Volume"].values
                )
                regime_profile = ap["profile"]
                # Scale intraday ATR mults based on daily regime
                if regime_profile == "trend_rider":
                    tp_mult, sl_mult = 3.0, 1.5   # wider TP in trends
                elif regime_profile == "momentum":
                    tp_mult, sl_mult = 2.5, 1.2
                elif regime_profile == "defensive":
                    tp_mult, sl_mult = 1.5, 1.5   # tighter TP, wider SL
                elif regime_profile == "survival":
                    tp_mult, sl_mult = 1.0, 2.0   # tight TP, wide SL
                # scalper keeps default 2.0, 1.0
        except Exception:
            pass

        if signal == "POSITIVE":
            if atr:
                tp_price = round(cur_price + atr * tp_mult, 2)
                sl_price = round(cur_price - atr * sl_mult, 2)
                trail_pct = round((atr / cur_price) * 100 * (tp_mult / 2), 2)
            else:
                tp_price = round(cur_price * 1.02, 2)
                sl_price = round(cur_price * 0.99, 2)
                trail_pct = 1.0
            tp_pct = round((tp_price - cur_price) / cur_price * 100, 2)
            sl_pct = round((sl_price - cur_price) / cur_price * 100, 2)
            signals.append({"type": "neutral", "msg": f"Entry: ${cur_price:.2f} → TP: ${tp_price:.2f} (+{tp_pct}%) · SL: ${sl_price:.2f} ({sl_pct}%) [{regime_profile}]", "msg_kr": f"진입: ${cur_price:.2f} → 익절: ${tp_price:.2f} (+{tp_pct}%) · 손절: ${sl_price:.2f} ({sl_pct}%) [{regime_profile}]"})
            signals.append({"type": "neutral", "msg": f"Trailing stop: {trail_pct}% — auto-adjusts as price rises", "msg_kr": f"트레일링 스탑: {trail_pct}% — 가격 상승 시 자동 조정"})
        elif signal == "NEGATIVE":
            tp_price = round(cur_price * (1 - 0.02 * sl_mult), 2)
            sl_price = round(cur_price * (1 + 0.01 * sl_mult), 2)
            trail_pct = round(1.0 * sl_mult, 2)
            tp_pct = round((tp_price - cur_price) / cur_price * 100, 2)
            sl_pct = round((sl_price - cur_price) / cur_price * 100, 2)
            signals.append({"type": "neutral", "msg": f"Exit target: ${tp_price:.2f} ({tp_pct}%) · Stop: ${sl_price:.2f} (+{sl_pct}%) [{regime_profile}]", "msg_kr": f"청산 목표: ${tp_price:.2f} ({tp_pct}%) · 손절: ${sl_price:.2f} (+{sl_pct}%) [{regime_profile}]"})
        else:
            tp_price = None
            sl_price = None
            trail_pct = None
            tp_pct = None
            sl_pct = None

        return {
            "ticker": ticker.upper(),
            "price": round(cur_price, 2),
            "change_pct": change_pct,
            "score": round(score, 1),
            "signal": signal,
            "signals": signals,
            "rsi": round(rsi, 1) if rsi else None,
            "ema9": round(ema9[-1], 2) if ema9 is not None else None,
            "ema21": round(ema21[-1], 2) if ema21 is not None else None,
            "vwap": round(vwaps[-1], 2) if vwaps else None,
            "volume": int(cur_vol),
            "avg_volume": int(avg_vol),
            "vol_ratio": round(cur_vol / avg_vol, 1) if avg_vol > 0 else 0,
            "bars_count": len(bars),
            "take_profit": tp_price,
            "stop_loss": sl_price,
            "tp_pct": tp_pct,
            "sl_pct": sl_pct,
            "trailing_stop_pct": trail_pct,
            "atr": round(atr, 2) if atr else None,
            "regime_profile": regime_profile,
        }

    def scan_momentum(self):
        """Scan all day trade pool for momentum signals."""
        if not self.available:
            return []
        results = []
        from concurrent.futures import ThreadPoolExecutor
        def _analyze(sym):
            try:
                return self.analyze_short_term(sym)
            except Exception:
                return None
        with ThreadPoolExecutor(max_workers=10) as ex:
            futures = {ex.submit(_analyze, s): s for s in DAY_TRADE_POOL}
            from concurrent.futures import as_completed
            for f in as_completed(futures):
                r = f.result()
                if r:
                    results.append(r)
        results.sort(key=lambda x: -abs(x.get("change_pct", 0)))
        return results

    # ── Math helpers ──

    @staticmethod
    def _calc_rsi(prices, period=14):
        if len(prices) < period + 1:
            return None
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return float(100 - 100 / (1 + rs))

    @staticmethod
    def _calc_ema(prices, period):
        if len(prices) < period:
            return None
        ema = np.zeros(len(prices))
        ema[period-1] = np.mean(prices[:period])
        mult = 2 / (period + 1)
        for i in range(period, len(prices)):
            ema[i] = (prices[i] - ema[i-1]) * mult + ema[i-1]
        return ema

    @staticmethod
    def _calc_atr(bars, period=14):
        """Average True Range — measures volatility for dynamic TP/SL."""
        if len(bars) < period + 1:
            return None
        trs = []
        for i in range(1, len(bars)):
            h = bars[i]["high"]
            l = bars[i]["low"]
            pc = bars[i-1]["close"]
            tr = max(h - l, abs(h - pc), abs(l - pc))
            trs.append(tr)
        if len(trs) < period:
            return None
        return float(np.mean(trs[-period:]))
