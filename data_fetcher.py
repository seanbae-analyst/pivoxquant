"""
StockPilot — Data Fetcher v3
Data sources: FMP API (primary), KIS (Korean stocks), RSS feeds, alternative.me.
Supports US equities + Korean stocks (.KS / .KQ).
"""

import logging
from datetime import datetime

import feedparser
import pandas as pd
import requests

import fmp_service as fmp

logger = logging.getLogger(__name__)

# ── Korean Stock Registry ──────────────────────────────────────────────────────
KOREAN_NAMES = {
    "005930.KS": "Samsung Electronics", "000660.KS": "SK Hynix",
    "035420.KS": "NAVER Corp", "035720.KS": "Kakao",
    "005380.KS": "Hyundai Motor", "000270.KS": "Kia Corp",
    "005490.KS": "POSCO Holdings", "051910.KS": "LG Chem",
    "066570.KS": "LG Electronics", "068270.KS": "Celltrion",
    "373220.KS": "LG Energy Solution", "207940.KS": "Samsung Biologics",
    "003550.KS": "LG Corp", "096770.KS": "SK Innovation",
    "017670.KS": "SK Telecom", "030200.KS": "KT Corp",
    "105560.KS": "KB Financial", "086790.KS": "Hana Financial",
    "055550.KS": "Shinhan Financial", "000810.KS": "Samsung Fire & Marine",
    "032830.KS": "Samsung Life Insurance", "009150.KS": "Samsung Electro-Mechanics",
    "028260.KS": "Samsung C&T", "010140.KS": "Samsung Heavy Industries",
    "047050.KS": "Krafton", "263750.KS": "Pearl Abyss",
    "035900.KQ": "JYP Entertainment", "041510.KQ": "SM Entertainment",
    "122870.KQ": "YG Entertainment", "352820.KS": "HYBE",
    "377300.KS": "Kakao Pay", "403550.KS": "Kakao Bank",
}

# ── Sentiment Word Lists ───────────────────────────────────────────────────────
BULLISH_WORDS = {
    "beat", "beats", "surge", "surges", "soar", "soars", "rally",
    "upgrade", "upgraded", "outperform", "record", "growth", "profit",
    "strong", "breakout", "bullish", "upside", "higher", "gain",
    "rise", "rises", "positive", "boom", "accelerate", "expand",
    "buy", "overweight", "above", "exceed", "exceeds", "jumped",
    "recovery", "rebound", "boost", "optimistic", "revenue", "topped",
}
BEARISH_WORDS = {
    "miss", "misses", "plunge", "plunges", "crash", "crashes", "sell",
    "downgrade", "downgraded", "underperform", "weak", "decline", "falling",
    "loss", "layoffs", "recession", "warning", "bearish", "lower", "cut",
    "cuts", "drop", "drops", "below", "disappoints", "slump", "fear",
    "risk", "concern", "trouble", "fraud", "lawsuit", "tariff", "tariffs",
    "stagflation", "inflation", "default", "bankrupt",
}
KOREAN_BULLISH = {
    "상승", "급등", "돌파", "성장", "흑자", "최고", "호실적", "매수", "상향",
    "긍정", "증가", "기록", "강세", "호재", "반등", "개선", "확대", "상향조정",
}
KOREAN_BEARISH = {
    "하락", "급락", "적자", "손실", "매도", "하향", "부진", "감소", "위기",
    "우려", "악재", "충격", "약세", "리스크", "부채", "정체", "축소", "하향조정",
}

# Wall Street RSS feeds (free, no API key)
WS_FEEDS = [
    {"name": "Yahoo Finance",    "url": "https://finance.yahoo.com/rss/topstories"},
    {"name": "Reuters Business", "url": "https://feeds.reuters.com/reuters/businessNews"},
    {"name": "MarketWatch",      "url": "https://feeds.marketwatch.com/marketwatch/topstories/"},
    {"name": "CNBC Markets",     "url": "https://www.cnbc.com/id/15839069/device/rss/rss.html"},
    {"name": "Seeking Alpha",    "url": "https://seekingalpha.com/market_currents.xml"},
]


class DataFetcher:

    @staticmethod
    def _safe(v, dp=2):
        """Convert to float, return 0 if NaN/Inf."""
        import math
        try:
            f = float(v)
            return round(f, dp) if not math.isnan(f) and not math.isinf(f) else 0
        except (TypeError, ValueError):
            return 0

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def is_korean(ticker: str) -> bool:
        t = ticker.upper()
        return t.endswith(".KS") or t.endswith(".KQ")

    @staticmethod
    def currency(ticker: str) -> str:
        return "KRW" if DataFetcher.is_korean(ticker) else "USD"

    @staticmethod
    def fmt_price(price: float, ticker: str) -> str:
        if DataFetcher.is_korean(ticker):
            return f"₩{price:,.0f}"
        return f"${price:,.2f}"

    def quick_lookup(self, ticker: str) -> "dict | None":
        """
        Fast ticker lookup for real-time modal UX.
        Uses FMP quote API for US stocks, KIS for Korean stocks.
        """
        ticker = ticker.strip().upper()
        if not ticker:
            return None
        if ticker.isdigit() and len(ticker) == 6:
            ticker = ticker + ".KS"
        try:
            curr = self.currency(ticker)
            price = None
            name = KOREAN_NAMES.get(ticker)

            if self.is_korean(ticker):
                # Korean stocks: use KIS API or FMP won't have them
                # Try FMP first for non-Korean, KIS for Korean
                price = None  # KIS handled by realtime_service
            else:
                # US stocks: FMP quote
                q = fmp.get_quote(ticker)
                if q:
                    price = q.get("price")
                    if not name:
                        name = q.get("name", "")

            if not price or price <= 0:
                # Fallback: try FMP profile
                info = fmp.get_info(ticker)
                if info:
                    price = info.get("price", 0)
                    if not name:
                        name = info.get("shortName", ticker)

            if not price or price <= 0:
                return None
            if not name:
                name = ticker

            return {
                "ok":            True,
                "ticker":        ticker,
                "name":          name,
                "price":         round(float(price), 0 if curr == "KRW" else 2),
                "price_display": self.fmt_price(price, ticker),
                "currency":      curr,
                "is_korean":     self.is_korean(ticker),
            }
        except Exception as e:
            logger.error(f"Quick lookup failed {ticker}: {e}")
            return None

    _RSS_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    def _fetch_feed(self, url: str) -> "feedparser.FeedParserDict":
        """Fetch RSS via requests (with UA header) then parse the content."""
        try:
            r = requests.get(url, headers=self._RSS_HEADERS, timeout=8)
            return feedparser.parse(r.text)
        except Exception:
            return feedparser.parse("")

    # ── Per-Ticker News ───────────────────────────────────────────────────────

    def get_news(self, ticker: str) -> list[dict]:
        """Fetch per-ticker news via FMP API."""
        items: list[dict] = []
        try:
            raw = fmp.get_news(ticker, limit=15)
            for entry in raw:
                title = (entry.get("title") or "").strip()
                if not title or len(title) < 5:
                    continue
                import re
                summary = (entry.get("text") or "")[:300]
                summary = re.sub(r"<[^>]+>", "", summary).strip()
                items.append({
                    "title":     title,
                    "summary":   summary,
                    "published": entry.get("publishedDate", ""),
                    "link":      entry.get("url", ""),
                    "source":    entry.get("site", "FMP"),
                })
        except Exception as ex:
            logger.warning(f"News fetch failed {ticker}: {ex}")
        return items[:15]

    _news_score_cache = {}  # {ticker: (timestamp, (score, sigs))}
    _NEWS_SCORE_TTL = 600  # 10 min cache for news sentiment

    def score_news_sentiment(self, ticker: str) -> tuple[float, list[dict]]:
        import time as _time
        cache_key = ticker.upper()
        cached = self._news_score_cache.get(cache_key)
        if cached and _time.time() - cached[0] < self._NEWS_SCORE_TTL:
            return cached[1]

        news = self.get_news(ticker)
        if not news:
            return 50.0, [{"type": "neutral", "msg": "No recent news", "msg_kr": "최근 뉴스 없음"}]

        # Try Claude AI sentiment first, fallback to keyword-based
        ai_result = self._score_news_with_ai(ticker, news[:8])
        result = ai_result if ai_result else self._score_news_keywords(ticker, news)
        self._news_score_cache[cache_key] = (_time.time(), result)
        return result

    def _score_news_with_ai(self, ticker: str, news: list) -> "tuple[float, list[dict]] | None":
        """Use Claude Haiku for context-aware news sentiment analysis."""
        try:
            import os, anthropic
            api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
            if not api_key:
                # Try loading from .env file
                env_path = os.path.join(os.path.dirname(__file__), ".env")
                if os.path.exists(env_path):
                    with open(env_path) as f:
                        for line in f:
                            if line.startswith("ANTHROPIC_API_KEY="):
                                api_key = line.split("=", 1)[1].strip()
                                os.environ["ANTHROPIC_API_KEY"] = api_key
            if not api_key:
                return None

            headlines = "\n".join(f"- {n['title']}" for n in news[:8])

            client = anthropic.Anthropic(api_key=api_key)
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=300,
                messages=[{
                    "role": "user",
                    "content": f"""Analyze these news headlines for {ticker} stock. Rate sentiment 0-100 (0=very bearish, 50=neutral, 100=very bullish).

Consider:
- Is the news about the company itself or just the sector?
- Is it forward-looking (earnings guidance, new product) or backward (past results)?
- Could this headline be misleading? (e.g. "stock surges" could precede a crash)

Headlines:
{headlines}

Reply ONLY in this exact JSON format, nothing else:
{{"score": <number 0-100>, "sentiment": "<bullish/bearish/neutral>", "reason": "<1 sentence why>", "reason_kr": "<same in Korean>"}}"""
                }]
            )
            import json, re
            raw = resp.content[0].text.strip()
            # Strip markdown code fences if present
            raw = re.sub(r'^```(?:json)?\s*', '', raw)
            raw = re.sub(r'\s*```$', '', raw)
            data = json.loads(raw.strip())
            score = max(0, min(100, float(data["score"])))
            sentiment = data.get("sentiment", "neutral")
            sig_type = "bullish" if sentiment == "bullish" else "bearish" if sentiment == "bearish" else "neutral"
            return score, [{
                "type": sig_type,
                "msg": f"AI News Analysis: {data.get('reason', sentiment)} (score {score:.0f})",
                "msg_kr": f"AI 뉴스 분석: {data.get('reason_kr', sentiment)} (점수 {score:.0f})"
            }]
        except Exception as e:
            logger.debug(f"AI news scoring failed for {ticker}: {e}")
            return None

    def _score_news_keywords(self, ticker: str, news: list) -> tuple[float, list[dict]]:
        """Fallback keyword-based sentiment scoring."""
        is_kr = self.is_korean(ticker)
        bull = bear = 0
        for item in news[:10]:
            words = set(item["title"].lower().split())
            if is_kr:
                title_str = item["title"]
                bull += sum(1 for w in KOREAN_BULLISH if w in title_str)
                bear += sum(1 for w in KOREAN_BEARISH if w in title_str)
            bull += len(words & BULLISH_WORDS)
            bear += len(words & BEARISH_WORDS)
        total = bull + bear
        confidence = min(1.0, total / 5) if total > 0 else 0
        score = 50.0 if total == 0 else 50.0 + (bull - bear) / total * 35 * confidence
        score = max(0.0, min(100.0, score))
        sigs = []
        if bull > bear:
            sigs.append({"type": "bullish",
                          "msg":    f"Positive news flow ({bull} bullish signals)",
                          "msg_kr": f"긍정적 뉴스 흐름 ({bull}개 강세 시그널)"})
        elif bear > bull:
            sigs.append({"type": "bearish",
                          "msg":    f"Negative news flow ({bear} bearish signals)",
                          "msg_kr": f"부정적 뉴스 흐름 ({bear}개 약세 시그널)"})
        else:
            sigs.append({"type": "neutral",
                          "msg":    "Neutral news sentiment",
                          "msg_kr": "뉴스 중립"})
        return score, sigs

    # ── Wall Street Morning Brief ─────────────────────────────────────────────

    def get_wall_street_brief(self) -> dict:
        """
        Aggregate top Wall Street stories from multiple free RSS feeds.
        Returns GS-style morning brief payload.
        """
        stories: list[dict] = []
        sources_ok: list[str] = []

        for feed_info in WS_FEEDS:
            try:
                feed = self._fetch_feed(feed_info["url"])
                count = 0
                for e in feed.entries[:5]:
                    title = e.get("title", "").strip()
                    if not title or len(title) < 10:
                        continue
                    words = set(title.lower().split())
                    bull = len(words & BULLISH_WORDS)
                    bear = len(words & BEARISH_WORDS)
                    sentiment = "bullish" if bull > bear else "bearish" if bear > bull else "neutral"
                    stories.append({
                        "title":     title,
                        "summary":   e.get("summary", "")[:200].strip(),
                        "published": e.get("published", ""),
                        "link":      e.get("link", ""),
                        "source":    feed_info["name"],
                        "sentiment": sentiment,
                    })
                    count += 1
                if count:
                    sources_ok.append(feed_info["name"])
            except Exception as ex:
                logger.debug(f"Feed {feed_info['name']} failed: {ex}")

        stories = stories[:24]
        bull_cnt = sum(1 for s in stories if s["sentiment"] == "bullish")
        bear_cnt = sum(1 for s in stories if s["sentiment"] == "bearish")

        if bull_cnt > bear_cnt * 1.4:
            mood, mood_color = "Risk-On 📈", "bullish"
        elif bear_cnt > bull_cnt * 1.4:
            mood, mood_color = "Risk-Off 📉", "bearish"
        else:
            mood, mood_color = "Mixed / Neutral ⚖️", "neutral"

        return {
            "stories":    stories,
            "market_mood": mood,
            "mood_color":  mood_color,
            "bull_count":  bull_cnt,
            "bear_count":  bear_cnt,
            "sources":     sources_ok,
            "date":        datetime.utcnow().strftime("%B %d, %Y"),
            "generated_at": datetime.utcnow().isoformat(),
        }

    # ── Macro Data ────────────────────────────────────────────────────────────

    def get_macro_data(self) -> dict:
        """Basic macro data — delegates to get_enhanced_macro for full batch."""
        return self.get_enhanced_macro()

    def get_enhanced_macro(self) -> dict:
        """Full macro snapshot — FMP batch quotes + parallel index history."""
        from concurrent.futures import ThreadPoolExecutor
        macro: dict = {}

        executor = ThreadPoolExecutor(max_workers=5)

        # Fear & Greed Index
        def _fetch_fng():
            try:
                r = requests.get("https://api.alternative.me/fng/", timeout=6)
                if r.ok:
                    d = r.json()["data"][0]
                    return {"value": int(d["value"]), "label": d["value_classification"]}
            except Exception:
                pass
            return {"value": 50, "label": "Neutral"}
        fng_future = executor.submit(_fetch_fng)

        # FMP batch quote for indices and assets
        index_syms = ["^GSPC", "^IXIC", "^DJI", "^RUT", "^VIX", "^TNX", "^IRX", "^TYX"]
        stock_syms = ["GLD", "USO", "SLV", "UUP"]
        fx_pairs = ["USDKRW", "EURUSD", "USDJPY"]

        def _get_single_index(sym):
            h = fmp.get_history(sym, period="5d")
            if h is not None and not h.empty and len(h) >= 2:
                close = h["Close"].dropna()
                price = float(close.iloc[-1])
                prev = float(close.iloc[-2])
                chg = (price - prev) / prev * 100 if prev else 0
                return (sym, (price, chg))
            elif h is not None and not h.empty:
                return (sym, (float(h["Close"].iloc[-1]), 0))
            return (sym, None)

        def _get_index_quotes():
            from concurrent.futures import ThreadPoolExecutor as _TPE
            result = {}
            with _TPE(max_workers=8) as pool:
                for sym, val in pool.map(_get_single_index, index_syms):
                    if val is not None:
                        result[sym] = val
            return result

        def _get_stock_quotes():
            quotes = fmp.get_quotes_batch(stock_syms)
            return {sym: (q.get("price", 0), q.get("changesPercentage", 0))
                    for sym, q in quotes.items()} if quotes else {}

        def _get_fx_quotes():
            from concurrent.futures import ThreadPoolExecutor as _TPE
            result = {}
            def _fetch_pair(pair):
                rate = fmp.get_fx_rate(pair)
                return (pair, rate)
            with _TPE(max_workers=3) as pool:
                for pair, rate in pool.map(_fetch_pair, fx_pairs):
                    if rate:
                        result[pair] = rate
            return result

        def _get_btc_quote():
            q = fmp.get_quote("BTCUSD")
            return q if q else None

        idx_future = executor.submit(_get_index_quotes)
        stk_future = executor.submit(_get_stock_quotes)
        fx_future = executor.submit(_get_fx_quotes)
        btc_future = executor.submit(_get_btc_quote)

        idx_data = idx_future.result(timeout=15)
        stk_data = stk_future.result(timeout=15)
        fx_data = fx_future.result(timeout=15)
        btc_data = btc_future.result(timeout=15)

        # Equity indices
        for sym, key in [("^GSPC","sp500"),("^IXIC","nasdaq"),("^DJI","dow"),("^RUT","russell2000")]:
            if sym in idx_data:
                p, c = idx_data[sym]
                macro[key] = {"price": self._safe(p), "change_pct": self._safe(c)}

        # Korean indices (FMP may not have these — use defaults)
        for sym, key in [("^KS11","kospi"),("^KQ11","kosdaq")]:
            if sym in idx_data:
                p, c = idx_data[sym]
                macro[key] = {"price": self._safe(p), "change_pct": self._safe(c)}

        # VIX
        if "^VIX" in idx_data:
            macro["vix"] = round(idx_data["^VIX"][0], 2)

        # 10Y Treasury
        if "^TNX" in idx_data:
            macro["treasury_10y"] = round(idx_data["^TNX"][0], 2)

        # Commodities (using ETFs as proxies)
        for sym, key, name in [("USO","oil_wti","WTI Crude Oil"),
                                ("GLD","gold","Gold"),("SLV","silver","Silver")]:
            if sym in stk_data:
                p, c = stk_data[sym]
                macro[key] = {"price": self._safe(p), "change_pct": self._safe(c), "name": name}

        # FX
        for pair, key, name in [("USDKRW","usdkrw","USD/KRW"),
                                 ("EURUSD","eurusd","EUR/USD"),
                                 ("USDJPY","usdjpy","USD/JPY")]:
            if pair in fx_data:
                macro[key] = {"price": round(fx_data[pair], 4), "change_pct": 0, "name": name}

        # DXY via UUP (Dollar Index ETF proxy)
        if "UUP" in stk_data:
            p, c = stk_data["UUP"]
            macro["dxy"] = {"price": self._safe(p), "change_pct": self._safe(c), "name": "US Dollar Index"}

        # BTC (fetched in parallel above)
        if btc_data:
            macro["btc"] = {"price": self._safe(btc_data.get("price", 0), 0),
                            "change_pct": self._safe(btc_data.get("changesPercentage", 0))}

        # Yield curve
        try:
            p3m = idx_data.get("^IRX", (None,))[0]
            p10y = idx_data.get("^TNX", (None,))[0]
            p30y = idx_data.get("^TYX", (None,))[0]
            if p3m is not None and p10y is not None:
                spread = round(p10y - p3m, 2)
                macro["yield_curve"] = {
                    "t3m": self._safe(p3m), "t10y": self._safe(p10y),
                    "t30y": self._safe(p30y) if p30y else None,
                    "spread": spread, "inverted": spread < 0,
                }
        except Exception:
            pass

        macro["fear_greed"] = fng_future.result(timeout=8)
        executor.shutdown(wait=False)

        return macro

    # ── GS Algorithmic Market View ────────────────────────────────────────────

    def generate_gs_view(self, macro: dict) -> dict:
        """
        Rule-based Goldman Sachs-style analyst commentary.
        100% algorithmic — zero AI calls.
        """
        themes:    list[str] = []
        risk_lvl:  str = "MODERATE"
        bias:      str = "NEUTRAL"

        fg      = macro.get("fear_greed", {})
        vix     = macro.get("vix", 20)
        yc      = macro.get("yield_curve", {})
        sp500   = macro.get("sp500", {})
        t10y    = macro.get("treasury_10y", 4.0)
        oil     = macro.get("oil_wti", {})
        dxy     = macro.get("dxy", {})

        # ── VIX regime ────────────────────────────────────────────────────────
        if vix:
            if vix > 35:
                themes.append("⚠️ EXTREME VOLATILITY: VIX >35 signals institutional stress. Tail-risk hedges elevated.")
                risk_lvl = "EXTREME"
            elif vix > 25:
                themes.append(f"📊 ELEVATED VOLATILITY: VIX at {vix:.1f} — risk-off conditions. Reduce position sizing.")
                risk_lvl = "HIGH"
            elif vix < 13:
                themes.append(f"😴 COMPLACENCY SIGNAL: VIX at {vix:.1f} — markets pricing near-zero risk. Consider tail hedges.")

        # ── Fear & Greed ──────────────────────────────────────────────────────
        if fg:
            v = fg.get("value", 50)
            if v < 20:
                themes.append("🔥 EXTREME FEAR: Historically strongest contrarian buy window. Patient capital rewarded here.")
                bias = "BULLISH"
            elif v < 35:
                themes.append(f"😰 FEAR ZONE ({v}): Sentiment washout nearing. High-quality names offer asymmetric upside.")
                bias = "MODERATELY BULLISH"
            elif v > 80:
                themes.append(f"⚡ EXTREME GREED ({v}): Sentiment at peak. GS model flags elevated reversal probability.")
                bias = "BEARISH"
            elif v > 65:
                themes.append(f"📈 GREED TERRITORY ({v}): Momentum intact. Late-cycle rotation into quality underway.")
                bias = "MODERATELY BEARISH"

        # ── Yield curve ───────────────────────────────────────────────────────
        if yc:
            spread = yc.get("spread", 1.0)
            if yc.get("inverted"):
                themes.append(f"🔴 INVERTED YIELD CURVE: 10Y-3M spread at {spread:.2f}%. GS Economics flags elevated 12M recession probability.")
                if risk_lvl == "MODERATE":
                    risk_lvl = "HIGH"
            elif spread < 0.3:
                themes.append(f"🟡 FLAT YIELD CURVE: Spread compressed to {spread:.2f}%. Watch credit spreads for early-warning signals.")
            else:
                themes.append(f"🟢 NORMAL YIELD CURVE: 10Y-3M spread at {spread:.2f}%. Credit cycle intact.")

        # ── Rate environment ──────────────────────────────────────────────────
        if t10y:
            if t10y > 4.5:
                themes.append(f"🏦 HIGH RATE REGIME: 10Y at {t10y:.2f}%. Growth multiples compressed. Overweight Value / Quality.")
            elif t10y > 3.5:
                themes.append(f"⚖️ NEUTRAL RATES: 10Y at {t10y:.2f}%. Balanced equity/duration exposure warranted.")
            else:
                themes.append(f"💰 LOW RATE ENVIRONMENT: 10Y at {t10y:.2f}%. Duration and growth premium supportive.")

        # ── Oil & Dollar ──────────────────────────────────────────────────────
        if oil and oil.get("change_pct", 0) > 3:
            themes.append(f"🛢️ OIL SPIKE: WTI +{oil['change_pct']:.1f}%. Stagflation risk elevated. Energy overweight.")
        if dxy and dxy.get("change_pct", 0) > 1:
            themes.append(f"💵 DOLLAR STRENGTH: DXY +{dxy['change_pct']:.1f}%. EM equities and commodities face headwinds.")

        # ── S&P momentum ─────────────────────────────────────────────────────
        sp_chg = sp500.get("change_pct", 0) if sp500 else 0
        if sp_chg > 1.5:
            themes.append(f"🚀 S&P MOMENTUM: Index +{sp_chg:.1f}% — broad participation. Risk-on confirmed.")
            if bias == "NEUTRAL":
                bias = "MODERATELY BULLISH"
        elif sp_chg < -1.5:
            themes.append(f"🐻 S&P SELLING: Index {sp_chg:.1f}% — defensive rotation recommended.")
            if bias == "NEUTRAL":
                bias = "MODERATELY BEARISH"

        bias_note = {
            "BULLISH":            "GS Quant sees compelling risk/reward. Scale into quality longs with defined stops.",
            "MODERATELY BULLISH": "Constructive — selective long bias. High-quality growth + value blend optimal.",
            "NEUTRAL":            "Mixed signals warrant balanced positioning. Monitor key technicals for directional confirmation.",
            "MODERATELY BEARISH": "Cautious posture. Overweight cash, defensives, and short-duration assets.",
            "BEARISH":            "Risk-off. Capital preservation priority. Review stop-losses across all positions.",
        }.get(bias, "Maintain disciplined risk management.")

        return {
            "risk_level":  risk_lvl,
            "bias":        bias,
            "themes":      themes[:5],
            "bias_note":   bias_note,
            "vix":         vix,
        }

    # ── Stock Snapshot ────────────────────────────────────────────────────────

    _snapshot_cache = {}  # {ticker: (timestamp, data)}
    _SNAPSHOT_TTL = 60   # 1 minute cache

    def get_stock_snapshot(self, ticker: str) -> "dict | None":
        import time as _time
        cache_key = ticker.upper()
        cached = self._snapshot_cache.get(cache_key)
        if cached and _time.time() - cached[0] < self._SNAPSHOT_TTL:
            return cached[1]
        result = self._fetch_snapshot(ticker)
        if result:
            self._snapshot_cache[cache_key] = (_time.time(), result)
        return result

    def _fetch_snapshot(self, ticker: str) -> "dict | None":
        try:
            if ticker.strip().isdigit() and len(ticker.strip()) == 6:
                ticker = ticker.strip() + ".KS"

            info = fmp.get_info(ticker)
            hist = fmp.get_history(ticker, period="1y")

            # Get current price from quote or info
            q = fmp.get_quote(ticker)
            cur = q.get("price", 0) if q else info.get("price", 0)
            if not cur or cur <= 0:
                return None
            cur = float(cur)

            if hist is None or hist.empty or len(hist) < 20:
                return None

            prev = float(hist["Close"].iloc[-2]) if len(hist) > 1 else cur
            chg = (cur - prev) / prev * 100
            curr = self.currency(ticker)
            name = KOREAN_NAMES.get(ticker.upper(),
                   info.get("shortName", ticker))
            dp = 0 if curr == "KRW" else 2

            return {
                "ticker":         ticker.upper(),
                "name":           name,
                "price":          round(cur, dp),
                "price_display":  self.fmt_price(cur, ticker),
                "change_pct":     round(chg, 2),
                "volume":         int(hist["Volume"].iloc[-1]) if "Volume" in hist else 0,
                "avg_volume":     int(hist["Volume"].rolling(20).mean().iloc[-1]) if "Volume" in hist else 0,
                "market_cap":     info.get("marketCap"),
                "pe_ratio":       info.get("trailingPE"),
                "forward_pe":     info.get("forwardPE"),
                "eps":            info.get("trailingEps"),
                "revenue_growth": info.get("revenueGrowth"),
                "profit_margin":  info.get("netProfitMargin"),
                "debt_equity":    info.get("debtToEquity"),
                "week52_high":    round(float(hist["High"].max()), dp),
                "week52_low":     round(float(hist["Low"].min()), dp),
                "sector":         info.get("sector", "Unknown"),
                "industry":       info.get("industry", "Unknown"),
                "beta":           info.get("beta"),
                "currency":       curr,
                "is_korean":      self.is_korean(ticker),
            }
        except Exception as e:
            logger.error(f"Snapshot failed {ticker}: {e}")
            return None

    _history_cache = {}  # {(ticker, period): (timestamp, data)}
    _HISTORY_TTL = 300   # 5 minute cache for historical data

    def get_price_history(self, ticker: str, period: str = "6mo") -> "pd.DataFrame | None":
        import time as _time
        cache_key = (ticker.upper(), period)
        cached = self._history_cache.get(cache_key)
        if cached and _time.time() - cached[0] < self._HISTORY_TTL:
            return cached[1]
        try:
            h = fmp.get_history(ticker, period=period)
            result = h if h is not None and not h.empty else None
            if result is not None:
                self._history_cache[cache_key] = (_time.time(), result)
            return result
        except Exception:
            return None

    def get_prices_batch(self, tickers: list[str]) -> dict:
        """Batch price fetch using FMP batch quote API."""
        result = {}
        try:
            quotes = fmp.get_quotes_batch(tickers)
            for ticker in tickers:
                q = quotes.get(ticker)
                if q and q.get("price", 0) > 0:
                    price = q["price"]
                    curr = self.currency(ticker)
                    result[ticker] = {
                        "price":         round(price, 0 if curr == "KRW" else 2),
                        "price_display": self.fmt_price(price, ticker),
                        "currency":      curr,
                    }
        except Exception as e:
            logger.warning(f"Batch price fetch failed: {e}")
        return result

    # ── Sectors ───────────────────────────────────────────────────────────────

    def get_sector_performance(self) -> list[dict]:
        sectors = [
            ("XLK", "Technology"),     ("XLF", "Financials"),
            ("XLV", "Healthcare"),     ("XLE", "Energy"),
            ("XLY", "Consumer Disc."), ("XLP", "Consumer Staples"),
            ("XLI", "Industrials"),    ("XLB", "Materials"),
            ("XLRE", "Real Estate"),   ("XLU", "Utilities"),
            ("XLC", "Comm. Services"),
        ]
        syms = [s[0] for s in sectors]
        result = []
        try:
            quotes = fmp.get_quotes_batch(syms)
            for sym, name in sectors:
                q = quotes.get(sym)
                if q:
                    result.append({
                        "sector":     name,
                        "symbol":     sym,
                        "change_pct": round(q.get("changesPercentage", 0), 2),
                        "price":      round(q.get("price", 0), 2),
                    })
        except Exception:
            pass
        return result
