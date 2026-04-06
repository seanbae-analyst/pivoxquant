"""
StockPilot — Data Fetcher v2
Free data only: yfinance, RSS feeds, alternative.me.
Supports US equities + Korean stocks (.KS / .KQ).
Zero AI API calls.
"""

import yfinance as yf
import feedparser
import requests
import logging
import pandas as pd
import time
from datetime import datetime, timedelta
from functools import lru_cache

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
        Uses fast_info (< 1s) for price. Name from KOREAN_NAMES dict or yfinance info.
        """
        ticker = ticker.strip().upper()
        if not ticker:
            return None
        # Auto-append .KS for Korean stock codes (6-digit numbers without suffix)
        if ticker.isdigit() and len(ticker) == 6:
            ticker = ticker + ".KS"
        try:
            stock = yf.Ticker(ticker)
            fi    = stock.fast_info
            price = fi.last_price
            if not price or price <= 0:
                # Try .KQ (KOSDAQ) if .KS failed
                if ticker.endswith(".KS"):
                    ticker_kq = ticker.replace(".KS", ".KQ")
                    stock = yf.Ticker(ticker_kq)
                    fi = stock.fast_info
                    price = fi.last_price
                    if price and price > 0:
                        ticker = ticker_kq
                    else:
                        return None
                else:
                    return None

            curr = self.currency(ticker)

            # Name resolution: registry → yfinance shortName/longName → ticker
            name = KOREAN_NAMES.get(ticker)
            if not name:
                try:
                    info = stock.info
                    name = (info.get("shortName") or info.get("longName") or "").strip()
                except Exception:
                    name = ""
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
        """Fetch per-ticker news via yfinance .news (no RSS rate-limit issues)."""
        items: list[dict] = []
        try:
            raw = yf.Ticker(ticker).news or []
            for entry in raw[:15]:
                c = entry.get("content", {})
                title = (c.get("title") or "").strip()
                if not title or len(title) < 5:
                    continue
                url = (c.get("canonicalUrl") or c.get("clickThroughUrl") or {}).get("url", "")
                source = (c.get("provider") or {}).get("displayName", "Yahoo Finance")
                summary = (c.get("summary") or c.get("description") or "")[:300]
                # strip HTML tags from summary
                import re
                summary = re.sub(r"<[^>]+>", "", summary).strip()
                items.append({
                    "title":     title,
                    "summary":   summary,
                    "published": c.get("pubDate", ""),
                    "link":      url,
                    "source":    source,
                })
        except Exception as ex:
            logger.warning(f"News fetch failed {ticker}: {ex}")
        return items[:15]

    def score_news_sentiment(self, ticker: str) -> tuple[float, list[dict]]:
        news   = self.get_news(ticker)
        is_kr  = self.is_korean(ticker)
        bull = bear = 0
        for item in news[:10]:
            words = set(item["title"].lower().split())
            if is_kr:
                # Korean text: check character-by-character match
                title_str = item["title"]
                bull += sum(1 for w in KOREAN_BULLISH if w in title_str)
                bear += sum(1 for w in KOREAN_BEARISH if w in title_str)
            # Always run English keywords (some Korean news has English terms)
            bull += len(words & BULLISH_WORDS)
            bear += len(words & BEARISH_WORDS)
        score = 50.0 if bull + bear == 0 else 50.0 + (bull - bear) / (bull + bear) * 35
        score = max(0.0, min(100.0, score))
        sigs  = []
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
        """Full macro snapshot — single batch yf.download() for speed."""
        from concurrent.futures import ThreadPoolExecutor
        macro: dict = {}

        # Fear & Greed Index (parallel with yfinance)
        fng_future = None
        executor = ThreadPoolExecutor(max_workers=2)
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

        # ── Single batch download for ALL tickers ──
        all_syms = [
            "^GSPC", "^IXIC", "^DJI", "^RUT",        # US indices
            "^KS11", "^KQ11",                          # Korean indices
            "^VIX", "^TNX",                             # Volatility & rates
            "CL=F", "GC=F", "SI=F",                    # Commodities
            "DX-Y.NYB", "EURUSD=X", "KRW=X", "JPY=X", # FX
            "BTC-USD",                                   # Crypto
            "^IRX", "^TYX",                              # Yield curve (3M, 30Y)
        ]
        try:
            batch = yf.download(all_syms, period="5d", group_by="ticker",
                                threads=True, progress=False)
        except Exception:
            batch = pd.DataFrame()

        def _extract(sym):
            """Extract price & change_pct from batch download."""
            try:
                if len(all_syms) == 1:
                    h = batch
                else:
                    h = batch[sym] if sym in batch.columns.get_level_values(0) else pd.DataFrame()
                if h.empty or len(h) < 2:
                    return None, None
                close = h["Close"].dropna()
                if len(close) < 2:
                    return float(close.iloc[-1]), None
                price = float(close.iloc[-1])
                prev  = float(close.iloc[-2])
                chg   = (price - prev) / prev * 100 if prev else 0
                return price, chg
            except Exception:
                return None, None

        # Equity indices
        for sym, key in [("^GSPC","sp500"),("^IXIC","nasdaq"),("^DJI","dow"),
                         ("^RUT","russell2000"),("^KS11","kospi"),("^KQ11","kosdaq")]:
            price, chg = _extract(sym)
            if price is not None:
                macro[key] = {"price": self._safe(price), "change_pct": self._safe(chg)}

        # VIX
        price, _ = _extract("^VIX")
        if price is not None:
            macro["vix"] = round(price, 2)

        # 10Y Treasury
        price, _ = _extract("^TNX")
        if price is not None:
            macro["treasury_10y"] = round(price, 2)

        # Commodities
        for sym, key, name in [("CL=F","oil_wti","WTI Crude Oil"),
                                ("GC=F","gold","Gold"),("SI=F","silver","Silver")]:
            price, chg = _extract(sym)
            if price is not None:
                macro[key] = {"price": self._safe(price), "change_pct": self._safe(chg), "name": name}

        # FX
        for sym, key, name in [("DX-Y.NYB","dxy","US Dollar Index"),
                                ("EURUSD=X","eurusd","EUR/USD"),
                                ("KRW=X","usdkrw","USD/KRW"),
                                ("JPY=X","usdjpy","USD/JPY")]:
            price, chg = _extract(sym)
            if price is not None:
                macro[key] = {"price": round(price, 4), "change_pct": round(chg, 2) if chg else 0, "name": name}

        # Crypto
        price, chg = _extract("BTC-USD")
        if price is not None:
            macro["btc"] = {"price": self._safe(price, 0), "change_pct": self._safe(chg)}

        # Yield curve
        try:
            p3m, _ = _extract("^IRX")
            p10y, _ = _extract("^TNX")
            p30y, _ = _extract("^TYX")
            if p3m is not None and p10y is not None:
                spread = round(p10y - p3m, 2)
                macro["yield_curve"] = {
                    "t3m": self._safe(p3m), "t10y": self._safe(p10y),
                    "t30y": self._safe(p30y) if p30y else None,
                    "spread": spread, "inverted": spread < 0,
                }
        except Exception:
            pass

        # Fear & Greed (collect from parallel thread)
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

    def get_stock_snapshot(self, ticker: str) -> "dict | None":
        try:
            # Auto-append .KS for Korean stock codes
            if ticker.strip().isdigit() and len(ticker.strip()) == 6:
                ticker = ticker.strip() + ".KS"
            stock = yf.Ticker(ticker)

            # 1-min intraday (prepost) — most reliable current price
            h1 = stock.history(period="1d", interval="1m", prepost=True)
            if not h1.empty:
                cur = float(h1["Close"].dropna().iloc[-1])
            else:
                fi  = stock.fast_info
                cur = fi.last_price
            if not cur or cur <= 0:
                return None
            cur = float(cur)

            # History for technical indicators (need 1y for MA200)
            hist = stock.history(period="1y")
            if hist.empty or len(hist) < 20:
                return None

            try:
                info = stock.info
            except Exception:
                info = {}
            prev = float(hist["Close"].iloc[-2]) if len(hist) > 1 else cur
            chg  = (cur - prev) / prev * 100
            curr = self.currency(ticker)
            name = KOREAN_NAMES.get(ticker.upper(),
                   (info.get("shortName") or info.get("longName") or ticker))
            dp   = 0 if curr == "KRW" else 2

            return {
                "ticker":         ticker.upper(),
                "name":           name,
                "price":          round(cur, dp),
                "price_display":  self.fmt_price(cur, ticker),
                "change_pct":     round(chg, 2),
                "volume":         int(hist["Volume"].iloc[-1]),
                "avg_volume":     int(hist["Volume"].rolling(20).mean().iloc[-1]),
                "market_cap":     info.get("marketCap"),
                "pe_ratio":       info.get("trailingPE"),
                "forward_pe":     info.get("forwardPE"),
                "eps":            info.get("trailingEps"),
                "revenue_growth": info.get("revenueGrowth"),
                "profit_margin":  info.get("profitMargins"),
                "debt_equity":    info.get("debtToEquity"),
                "week52_high":    round(float(hist["High"].max()), dp),
                "week52_low":     round(float(hist["Low"].min()), dp),
                "sector":         info.get("sector", info.get("quoteType", "Unknown")),
                "industry":       info.get("industry", "Unknown"),
                "beta":           info.get("beta"),
                "currency":       curr,
                "is_korean":      self.is_korean(ticker),
            }
        except Exception as e:
            logger.error(f"Snapshot failed {ticker}: {e}")
            return None

    def get_price_history(self, ticker: str, period: str = "6mo") -> "pd.DataFrame | None":
        try:
            h = yf.Ticker(ticker).history(period=period)
            return h if not h.empty else None
        except Exception:
            return None

    def get_prices_batch(self, tickers: list[str]) -> dict:
        """Reliable parallel price fetch using 1-min intraday history (pre/post market included)."""
        from concurrent.futures import ThreadPoolExecutor

        def _one(ticker: str):
            try:
                # 1-min bars with pre/post — always fresh, bypasses fast_info cache issues
                h = yf.Ticker(ticker).history(period="1d", interval="1m", prepost=True)
                if h.empty:
                    # fallback: daily bar
                    h = yf.Ticker(ticker).history(period="5d", interval="1d")
                if h.empty:
                    return ticker, None
                price = float(h["Close"].dropna().iloc[-1])
                if price > 0:
                    curr = self.currency(ticker)
                    return ticker, {
                        "price":         round(price, 0 if curr == "KRW" else 2),
                        "price_display": self.fmt_price(price, ticker),
                        "currency":      curr,
                    }
            except Exception as e:
                logger.warning(f"Price fetch failed {ticker}: {e}")
            return ticker, None

        with ThreadPoolExecutor(max_workers=10) as pool:
            results = dict(pool.map(_one, tickers))

        return {k: v for k, v in results.items() if v is not None}

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
            batch = yf.download(syms, period="5d", group_by="ticker",
                                threads=True, progress=False)
        except Exception:
            return result
        for sym, name in sectors:
            try:
                h = batch[sym] if sym in batch.columns.get_level_values(0) else pd.DataFrame()
                close = h["Close"].dropna()
                if len(close) >= 2:
                    chg = (float(close.iloc[-1]) - float(close.iloc[-2])) / float(close.iloc[-2]) * 100
                    result.append({
                        "sector":     name,
                        "symbol":     sym,
                        "change_pct": round(chg, 2),
                        "price":      round(float(close.iloc[-1]), 2),
                    })
            except Exception:
                pass
        return result
