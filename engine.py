"""
StockPilot — Quantitative Analysis Engine v2
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
import yfinance as yf
import logging
from data_fetcher import DataFetcher
from quant_models import MeanReversion, MomentumBreakout, VolatilityRegime, RegimeSwitching, MLSignal

logger = logging.getLogger(__name__)
_fetcher = DataFetcher()


class QuantEngine:

    MAX_ALLOC   = 0.45   # max allocation per position
    BUY_THRESH  = 70.0   # composite score minimum for BUY signal
    SELL_THRESH = 25.0   # below this → SELL signal

    DISCOVER_POOL = [
        # ── US: High-momentum / growth ──
        "NVDA","TSLA","AAPL","MSFT","AMZN","GOOGL","META","AMD","PLTR","SMCI",
        "RXRX","IONQ","RKLB","HOOD","COIN","MSTR","CRWD","NET","DDOG","ZS",
        "SNOW","SHOP","SQ","PYPL","SOFI","RIVN","LCID","RBLX","U","SPOT",
        "NFLX","UBER","ABNB","DASH","OKTA","GTLB","PATH","AI","SOUN","BBAI",
        # ── US: Macro / value ──
        "BA","GM","F","GE","XOM","CVX","JPM","GS","MS","BAC",
        # ── KR: Blue chip + growth ──
        "005930.KS","000660.KS","035720.KS","035420.KS","005380.KS",
        "207940.KS","006400.KS","051910.KS","003670.KS","066570.KS",
        "105560.KS","055550.KS","086790.KS","017670.KS","030200.KS",
        "096770.KS","012330.KS","028260.KS","032830.KS","015760.KS",
    ]

    # ── Public ────────────────────────────────────────────────────────────────

    def analyze(self, ticker: str, capital_usd: float = 10_000.0,
                capital_krw: float = 0.0) -> dict | None:
        ticker   = ticker.upper().strip()
        snapshot = _fetcher.get_stock_snapshot(ticker)
        hist     = _fetcher.get_price_history(ticker, "6mo")
        if snapshot is None or hist is None:
            return None

        price     = snapshot["price"]
        currency  = snapshot.get("currency", "USD")
        is_korean = snapshot.get("is_korean", False)

        # Use the currency-matched capital for Kelly sizing
        capital = capital_krw if (is_korean and capital_krw > 0) else capital_usd

        tech_score, tech_sigs = self._technical(hist)
        fund_score, fund_sigs = self._fundamental(snapshot)
        news_score, news_sigs = _fetcher.score_news_sentiment(ticker)

        # ── Advanced Quant Models (40% weight) ──
        quant_score, quant_sigs = self._quant_models(hist)

        # New composite: Tech 25% + Fund 15% + News 10% + Quant 50%
        composite = round(
            tech_score * 0.25 +
            fund_score * 0.15 +
            news_score * 0.10 +
            quant_score * 0.50, 1
        )
        signal = (
            "BUY"  if composite >= self.BUY_THRESH  else
            "SELL" if composite <  self.SELL_THRESH else
            "HOLD"
        )

        rec_inv, rec_sh, rec_timing = self._size(composite, price, capital, signal)
        reason_en, reason_kr        = self._reason(signal, composite, tech_score,
                                                    fund_score, news_score, quant_score)

        needs_capital  = (signal == "BUY" and rec_sh == 0 and rec_timing in ("NO_CAPITAL", "INSUFFICIENT"))
        capital_needed = None
        capital_gap    = None
        if rec_timing == "INSUFFICIENT" and capital > 0:
            dp_n = 0 if is_korean else 2
            capital_needed = round(price, dp_n)
            capital_gap    = round(price - capital, dp_n)   # how much more needed

        # SELL recommendation
        sell_pct    = 0
        sell_timing = ""
        if signal == "SELL":
            if composite < 15:
                sell_pct    = 100
                sell_timing = "Exit immediately — full position"
            else:
                sell_pct    = 50
                sell_timing = "Reduce by half — protect gains"

        # Take-profit / stop-loss targets
        beta = snapshot.get("beta") or 1.0
        if signal == "BUY":
            tp_pct = 30 if composite >= 85 else 20
            sl_pct = -12 if beta > 1.5 else -8
        else:
            tp_pct = 15
            sl_pct = -8

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
            "rec_investment":  round(rec_inv, 2),
            "rec_shares":      rec_sh,
            "rec_timing":      "" if needs_capital else rec_timing,
            "needs_capital":   needs_capital,
            "capital_needed":  capital_needed,
            "sell_pct":        sell_pct,
            "sell_timing":     sell_timing,
            "tp_pct":          tp_pct,
            "sl_pct":          sl_pct,
            "take_profit":     round(price * (1 + tp_pct / 100), dp),
            "stop_loss":       round(price * (1 + sl_pct / 100), dp),
            "priority":        priority,
            "capital_gap":     capital_gap,
            "signals":         tech_sigs + fund_sigs + news_sigs + quant_sigs,
            "reason":          reason_en,
            "reason_kr":       reason_kr,
            "snapshot":        snapshot,
        }

    # ── Technical Analysis ────────────────────────────────────────────────────

    def _technical(self, hist: pd.DataFrame) -> tuple[float, list[dict]]:
        sigs  = []
        score = 50.0
        close = hist["Close"].astype(float)
        vol   = hist["Volume"].astype(float)

        # RSI ─────────────────────────────────────────────────────────────────
        rsi = self._rsi(close)
        if len(rsi.dropna()):
            r = float(rsi.iloc[-1])
            if r < 30:
                score += 20
                sigs.append({"type": "bullish",
                              "msg":    f"RSI oversold ({r:.0f}) — statistically cheap; bounce expected",
                              "msg_kr": f"RSI 과매도 ({r:.0f}) — 통계적 저점, 반등 기대"})
            elif r < 45:
                score += 10
                sigs.append({"type": "bullish",
                              "msg":    f"RSI below neutral ({r:.0f}) — momentum building",
                              "msg_kr": f"RSI 중립 이하 ({r:.0f}) — 모멘텀 형성 중"})
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
                    score += 15
                    sigs.append({"type": "bullish",
                                  "msg":    "Price near lower Bollinger Band — statistically undervalued",
                                  "msg_kr": "볼린저 하단 근접 — 통계적 저평가 구간"})
                elif pct_b >= 0.85:
                    score -= 15
                    sigs.append({"type": "bearish",
                                  "msg":    "Price near upper Bollinger Band — statistically stretched",
                                  "msg_kr": "볼린저 상단 근접 — 통계적 과매수 구간"})

        # Moving Averages (50/200) ────────────────────────────────────────────
        ma50  = close.rolling(50).mean()
        ma200 = close.rolling(200).mean()
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

        return max(0.0, min(100.0, score)), sigs

    # ── Position Sizing ────────────────────────────────────────────────────────

    def _size(self, score: float, price: float, capital: float,
              signal: str = "BUY") -> tuple[float, int, str]:
        if signal != "BUY":
            return 0.0, 0, ""
        if capital <= 0 or price <= 0:
            return 0.0, 0, "NO_CAPITAL"
        if capital < price:
            return 0.0, 0, "INSUFFICIENT"   # can't buy even 1 share

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

        if shares < 1:
            shares = 1
            timing = "Minimum entry — 1 share within available capital"

        return round(shares * price, 2), shares, timing

    # ── Reason Builder ────────────────────────────────────────────────────────

    def _reason(self, sig: str, score: float, tech: float, fund: float, news: float, quant: float = 50.0):
        dom = max([("Technical", tech), ("Fundamental", fund), ("News Sentiment", news), ("Quant Models", quant)],
                  key=lambda x: x[1])
        dom_kr = {"Technical": "기술적 분석", "Fundamental": "기본적 분석",
                  "News Sentiment": "뉴스 센티멘트", "Quant Models": "퀀트 모델"}[dom[0]]
        weights = "Tech 25% + Fund 15% + News 10% + Quant 50%"
        en = (f"Composite score {score:.0f}/100 ({weights}). Primary driver: {dom[0]} ({dom[1]:.0f} pts). "
              + {"BUY":  "Multi-factor quant model detects favorable entry. Scale in with defined risk.",
                 "HOLD": "Hold current position. Await stronger signal before adding.",
                 "SELL": "Quant model flags deteriorating conditions. Consider reducing or exiting position."}.get(sig, ""))
        kr = (f"종합 점수 {score:.0f}/100 ({weights}). 주요 동인: {dom_kr} ({dom[1]:.0f}점). "
              + {"BUY":  "멀티팩터 퀀트 모델이 매수 기회 감지. 분할 매수 권장.",
                 "HOLD": "현 포지션 유지. 추가 진입 시그널 대기.",
                 "SELL": "퀀트 모델이 약세 신호 감지. 포지션 축소 또는 청산 고려."}.get(sig, ""))
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
                h = yf.Ticker(ticker).history(period="3mo")
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
        d = p.diff()
        g = d.where(d > 0, 0.0).rolling(n).mean()
        l = (-d.where(d < 0, 0.0)).rolling(n).mean()
        return 100 - 100 / (1 + g / l.replace(0, np.nan))

    @staticmethod
    def _macd(p: pd.Series) -> tuple[pd.Series, pd.Series]:
        m = p.ewm(span=12, adjust=False).mean() - p.ewm(span=26, adjust=False).mean()
        return m, m.ewm(span=9, adjust=False).mean()

    @staticmethod
    def _bollinger(p: pd.Series, n: int = 20, k: float = 2.0):
        mid = p.rolling(n).mean()
        std = p.rolling(n).std()
        return mid + k * std, mid, mid - k * std

    # ── Advanced Quant Models ────────────────────────────────────────────────────

    def _quant_models(self, hist: pd.DataFrame) -> tuple[float, list[dict]]:
        """Run Mean Reversion + Momentum Breakout + Volatility Regime models."""
        sigs = []
        score = 50.0
        close = hist["Close"].astype(float).values
        high = hist["High"].astype(float).values
        low = hist["Low"].astype(float).values
        vol = hist["Volume"].astype(float).values

        # 1. Mean Reversion (10% → maps to 0-100)
        try:
            mr = MeanReversion.analyze(close)
            if mr:
                mr_score = mr["score"]
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
                if mb["signal"] == "BUY":
                    score += 20
                    for s in mb.get("signals", []):
                        sigs.append(s)
                elif mb["signal"] == "SELL":
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

        return max(0.0, min(100.0, score)), sigs
