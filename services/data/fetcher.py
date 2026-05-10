"""
PivoxQuant — Data Fetcher v3
Data sources: Alpaca (US primary), KIS (KR primary), FMP (fundamentals +
licensed news aggregator), alternative.me (Fear & Greed only).
Supports US equities + Korean stocks (.KS / .KQ).
"""

import os
import logging
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

from services.data import fmp

logger = logging.getLogger(__name__)

# ── Alpaca Historical Data Client (US stocks — no call limit) ─────────────────
# Kill-switched via ALPACA_ENABLED (config.py / Dockerfile). Default OFF —
# Alpaca is disabled to remove the legal risk tied to its "My Data" license.
# When disabled, US prices fall back to FMP only.
_alpaca_hist_client = None
_alpaca_hist_available = False

_ALPACA_ENABLED = os.environ.get("ALPACA_ENABLED", "0").strip() in (
    "1", "true", "True", "TRUE", "yes",
)

try:
    if not _ALPACA_ENABLED:
        logger.info(
            "DataFetcher: Alpaca disabled (ALPACA_ENABLED=0); "
            "US prices will use FMP exclusively."
        )
    else:
        _alpaca_key = os.environ.get("ALPACA_API_KEY", "").strip()
        _alpaca_secret = os.environ.get("ALPACA_SECRET_KEY", "").strip()
        if _alpaca_key and _alpaca_secret:
            from alpaca.data.historical import StockHistoricalDataClient
            _alpaca_hist_client = StockHistoricalDataClient(_alpaca_key, _alpaca_secret)
            _alpaca_hist_available = True
            logger.info("DataFetcher: Alpaca historical client initialized (US price source)")
except Exception as e:
    logger.warning("DataFetcher: Alpaca init failed, will use FMP for US prices: %s", e)

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

# Korean stock sector mapping (FMP often returns empty sector for KR tickers on free tier)
KOREAN_SECTORS = {
    "005930.KS": "Technology", "000660.KS": "Technology",
    "035420.KS": "Communication Services", "035720.KS": "Communication Services",
    "005380.KS": "Consumer Cyclical", "000270.KS": "Consumer Cyclical",
    "005490.KS": "Basic Materials", "051910.KS": "Basic Materials",
    "066570.KS": "Technology", "068270.KS": "Healthcare",
    "373220.KS": "Industrials", "207940.KS": "Healthcare",
    "003550.KS": "Industrials", "096770.KS": "Energy",
    "017670.KS": "Communication Services", "030200.KS": "Communication Services",
    "105560.KS": "Financial Services", "086790.KS": "Financial Services",
    "055550.KS": "Financial Services", "000810.KS": "Financial Services",
    "032830.KS": "Financial Services", "009150.KS": "Technology",
    "028260.KS": "Industrials", "010140.KS": "Industrials",
    "047050.KS": "Communication Services", "263750.KS": "Communication Services",
    "035900.KQ": "Communication Services", "041510.KQ": "Communication Services",
    "122870.KQ": "Communication Services", "352820.KS": "Communication Services",
    "377300.KS": "Financial Services", "403550.KS": "Financial Services",
    # Bug #10 safety net — minimum scope (1 entry per spec). KIS
    # bstp_kor_isnm path is the primary fix; this is a fallback when
    # KIS rate-limits / token unavailable.
    # 124500.KQ = IT Sengle (KOSDAQ IT services).
    "124500.KQ": "Technology",
}

# ── Sector resolution ─────────────────────────────────────────────────────────
def _resolve_sector(ticker: str, info: dict, is_kr: bool) -> str:
    """Resolve display sector for a ticker via a 3-step chain.

    US tickers: trust ``info["sector"]`` from FMP (no Starter coverage gap
    on US equities). Empty/missing → "Unknown".

    KR tickers (.KS / .KQ) — FMP Starter has no KRX sector coverage so
    info["sector"] is typically empty. Chain:
      1. ``info.get("sector")`` — only populated if FMP shipped one
         (rare on KR; preserves backward-compat for any future coverage).
      2. ``info.get("sector_kr")`` — KIS ``bstp_kor_isnm`` parsed by
         ``services.data.kr_fundamentals.get_kr_fundamentals``. Korean
         display string (e.g. "IT 서비스", "전기·전자"). Frontend renders
         the field verbatim — KR users expect Korean labels on KR tickers.
      3. ``KOREAN_SECTORS`` hardcoded mapping — backup for KIS rate-limit
         / network-fail / pre-onboarded tickers. Covers the legacy
         hardcoded set plus any explicit additions below.
      4. "Unknown" — terminal fallback (preserved for parity with
         pre-change behaviour; never raises).

    Returns a string (never None) so downstream JSON serialisers don't
    have to special-case missing sector.
    """
    fmp_sector = info.get("sector")
    if isinstance(fmp_sector, str) and fmp_sector.strip():
        return fmp_sector.strip()

    if is_kr:
        kis_sector = info.get("sector_kr")
        if isinstance(kis_sector, str) and kis_sector.strip():
            return kis_sector.strip()

        mapped = KOREAN_SECTORS.get(ticker.upper())
        if isinstance(mapped, str) and mapped.strip():
            return mapped

    return "Unknown"


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

# Wall Street news: sourced via FMP /news/general (licensed aggregator).
# Direct Reuters/MarketWatch/CNBC/Seeking Alpha RSS removed 2026-04-19
# for commercial-use ToS compliance.


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

    @staticmethod
    def _alpaca_latest_quote(ticker: str) -> "dict | None":
        """Fetch latest trade price from Alpaca for US tickers.

        Uses StockLatestTradeRequest (actual last trade) — fresher than
        StockLatestBarRequest which aggregates a 1-min bar and can lag
        30-60s during fast markets. Falls back to latest bar if trade
        endpoint fails (e.g., illiquid symbols outside RTH).
        Returns {price, open, high, low, volume} or None.

        Class-share normalization: Alpaca expects slash form (BRK/B) for
        multi-class tickers. Accept callers passing BRK.B or BRK-B and
        translate. Mirrors the dot/dash logic in `_get_history_alpaca`.
        """
        if not _alpaca_hist_available or not _alpaca_hist_client:
            return None
        try:
            from alpaca.data.requests import (
                StockLatestTradeRequest,
                StockLatestQuoteRequest,
                StockLatestBarRequest,
            )

            # Class-share normalize: BRK.B / BRK-B → BRK/B for Alpaca.
            alpaca_symbol = ticker
            if "-" in alpaca_symbol and not alpaca_symbol.startswith("^"):
                alpaca_symbol = alpaca_symbol.replace("-", "/")
            elif "." in alpaca_symbol and not alpaca_symbol.endswith(".KS") \
                    and not alpaca_symbol.endswith(".KQ") \
                    and not alpaca_symbol.startswith("^"):
                base, _, suf = alpaca_symbol.rpartition(".")
                if base and len(suf) == 1 and suf.isalpha():
                    alpaca_symbol = f"{base}/{suf}"
            lookup_key = alpaca_symbol  # Alpaca dict keys come back in the request form.

            # Latest trade — RTH only.
            try:
                tr_req = StockLatestTradeRequest(symbol_or_symbols=[alpaca_symbol])
                trades = _alpaca_hist_client.get_stock_latest_trade(tr_req)
                trade = trades.get(lookup_key) if trades else None
            except Exception:
                trade = None

            # Latest quote — captures pre-market / after-hours bid/ask.
            try:
                q_req = StockLatestQuoteRequest(symbol_or_symbols=[alpaca_symbol])
                quotes = _alpaca_hist_client.get_stock_latest_quote(q_req)
                quote = quotes.get(lookup_key) if quotes else None
            except Exception:
                quote = None

            try:
                br_req = StockLatestBarRequest(symbol_or_symbols=[alpaca_symbol])
                bars = _alpaca_hist_client.get_stock_latest_bar(br_req)
                bar = bars.get(lookup_key) if bars else None
            except Exception:
                bar = None

            if trade is None and bar is None and quote is None:
                return None

            # Compute quote midpoint
            quote_price = None
            quote_ts = None
            if quote:
                bid = float(getattr(quote, "bid_price", 0) or 0)
                ask = float(getattr(quote, "ask_price", 0) or 0)
                if bid > 0 and ask > 0:
                    quote_price = (bid + ask) / 2
                elif bid > 0:
                    quote_price = bid
                elif ask > 0:
                    quote_price = ask
                quote_ts = getattr(quote, "timestamp", None)

            trade_price = float(trade.price) if (trade and getattr(trade, "price", 0)) else None
            trade_ts = getattr(trade, "timestamp", None) if trade else None

            # Pick freshest source: quote often wins in extended hours.
            if quote_price and quote_ts and trade_ts:
                price = quote_price if quote_ts > trade_ts else trade_price
            elif trade_price:
                price = trade_price
            elif quote_price:
                price = quote_price
            elif bar:
                price = float(bar.close)
            else:
                return None

            if price <= 0:
                return None

            return {
                "price":  price,
                "open":   float(bar.open) if bar else price,
                "high":   float(bar.high) if bar else price,
                "low":    float(bar.low) if bar else price,
                "volume": int(bar.volume) if bar else 0,
            }
        except Exception as e:
            logger.debug("Alpaca latest quote failed %s: %s", ticker, e)
            return None

    def quick_lookup(self, ticker: str) -> "dict | None":
        """
        Fast ticker lookup for real-time modal UX.
        Routing:
          - KR: KIS primary -> FMP fallback
          - US: Alpaca primary (no call limit) -> FMP fallback -> FMP profile price -> stale cache
        """
        ticker = ticker.strip().upper()
        if not ticker:
            return None
        if ticker.isdigit() and len(ticker) == 6:
            ticker = ticker + ".KS"
        try:
            curr = self.currency(ticker)
            price = None
            name = None
            # KR canonical name source (Korean preferred, BUG-01 2026-05-10):
            # kr_stock_registry returns Korean (e.g. "삼성전자"), the curated
            # KOREAN_NAMES dict above returns English ("Samsung Electronics")
            # and used to populate snapshots — making /api/signals/<t> emit
            # English while /api/market/profile/<t> emitted Korean. The user
            # has repeatedly directed Korean preferred for KR tickers
            # (memory feedback_ticker_display).
            if self.is_korean(ticker):
                try:
                    from services import kr_stock_registry as _kr_reg
                    name = _kr_reg.get_name(ticker)
                except Exception:
                    logger.debug("silent-fallback: quick_lookup", exc_info=True)
                    pass
            if not name:
                # Backward-compat: KOREAN_NAMES (English) only used when the
                # registry misses for a curated ticker (very rare — registry
                # is the superset).
                name = KOREAN_NAMES.get(ticker)

            if self.is_korean(ticker):
                # Korean stocks: use KIS API (FMP free tier does not serve KR)
                try:
                    from services.container import realtime as _rt
                    kis_data = _rt.get_price(ticker)
                    if kis_data and kis_data.get("price"):
                        price = kis_data["price"]
                except Exception as kis_err:
                    logger.warning("KIS lookup failed %s: %s", ticker, kis_err)
            else:
                # US stocks: Alpaca first (unlimited), FMP fallback only if Alpaca fails
                alp = self._alpaca_latest_quote(ticker)
                if alp and alp.get("price", 0) > 0:
                    price = alp["price"]
                    # Alpaca doesn't return company name — try cached FMP profile/info
                    # (cheap: zero network calls when cached within 7d/24h TTL)
                    if not name:
                        try:
                            info_cached = fmp.get_info(ticker)
                            if info_cached:
                                name = info_cached.get("shortName") or info_cached.get("longName")
                        except Exception:
                            logger.debug("silent-fallback: quick_lookup", exc_info=True)
                            pass
                else:
                    # Alpaca failed — try FMP quote (may return None on 402)
                    q = fmp.get_quote(ticker)
                    if q:
                        price = q.get("price")
                        if not name:
                            name = q.get("name", "")

            if not price or price <= 0:
                # Final fallback: try FMP profile for cached price + company name (US only)
                if not self.is_korean(ticker):
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
            logger.error("Quick lookup failed %s: %s", ticker, e)
            return None

    # ── Per-Ticker News ───────────────────────────────────────────────────────

    def get_news(self, ticker: str) -> list[dict]:
        """Fetch per-ticker news.

        Routing:
          - KR (.KS / .KQ) → Naver Developers Search News API (official)
          - US             → FMP ``/news/stock`` only. No RSS fallback.

        Rationale: Google News RSS and Yahoo Finance RSS were removed
        2026-04-19 for legal/commercial-use compliance. When FMP returns
        nothing we return [] — the UI shows a "no recent news" state.

        Always returns a list (possibly empty) — never raises.
        """
        # KR branch — FMP has no Korean coverage
        if self.is_korean(ticker):
            try:
                from services.news_service import get_news_naver
                return get_news_naver(ticker)[:15]
            except Exception as ex:
                logger.warning("Naver news failed %s: %s", ticker, ex)
                return []

        # US branch — FMP only (paid, commercial-safe)
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
            logger.warning("FMP news fetch failed %s: %s", ticker, ex)

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
            import os
            import anthropic
            # dotenv는 app.py 시작 시점에 이미 로드됨. Railway에선 환경변수로 주입.
            api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
            if not api_key:
                return None

            headlines = "\n".join(f"- {n['title']}" for n in news[:8])

            client = anthropic.Anthropic(api_key=api_key, timeout=15.0, max_retries=1)
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
            import json
            import re
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
            logger.debug("AI news scoring failed for %s: %s", ticker, e)
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
        Aggregate top Wall Street stories via FMP ``/news/general``.

        FMP aggregates licensed news feeds (Reuters, MarketWatch,
        Bloomberg, etc.) so commercial redistribution is permitted.
        Direct Reuters/MarketWatch/CNBC/Seeking Alpha RSS calls were
        removed 2026-04-19 for ToS compliance. On failure → empty stories.

        Returns GS-style morning brief payload with fields
        ``{stories, market_mood, mood_color, bull_count, bear_count,
        sources, date, generated_at}``.
        """
        stories: list[dict] = []
        sources_ok_set: set[str] = set()

        try:
            raw = fmp.get_general_news(limit=24) or []
        except Exception as ex:
            logger.debug("FMP general news failed: %s", ex)
            raw = []

        for item in raw:
            if not isinstance(item, dict):
                continue
            title = (item.get("title") or "").strip()
            if not title or len(title) < 10:
                continue
            # FMP schema: title / text / publishedDate / url / site / image
            summary_raw = item.get("text") or item.get("summary") or ""
            summary = str(summary_raw)[:200].strip()
            published = item.get("publishedDate") or item.get("published") or ""
            link = item.get("url") or item.get("link") or ""
            source = (item.get("site") or item.get("publisher")
                      or item.get("source") or "FMP").strip() or "FMP"

            words = set(title.lower().split())
            bull = len(words & BULLISH_WORDS)
            bear = len(words & BEARISH_WORDS)
            sentiment = "bullish" if bull > bear else "bearish" if bear > bull else "neutral"

            stories.append({
                "title":     title,
                "summary":   summary,
                "published": published,
                "link":      link,
                "source":    source,
                "sentiment": sentiment,
            })
            sources_ok_set.add(source)

        stories = stories[:24]
        sources_ok = sorted(sources_ok_set)
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
            "date":        datetime.now(timezone.utc).replace(tzinfo=None).strftime("%B %d, %Y"),
            "generated_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
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
                logger.debug("silent-fallback: _fetch_fng", exc_info=True)
                pass
            return {"value": 50, "label": "Neutral"}
        fng_future = executor.submit(_fetch_fng)

        # FMP v4 stable: use get_quote() for all — works for indices, ETFs, crypto
        index_syms = ["^GSPC", "^IXIC", "^DJI", "^RUT", "^VIX", "^TNX", "^IRX", "^TYX"]
        # SPY/QQQ/DIA/IWM added 2026-04-29 (Wave 2 Bug #11): always fetch
        # the index ETF proxies so /discover/market-overview can publish the
        # same unit-scale value as /api/market/indices.
        stock_syms = ["GLD", "USO", "SLV", "UUP", "SPY", "QQQ", "DIA", "IWM"]
        fx_pairs = ["USDKRW", "EURUSD", "USDJPY"]

        def _get_single_quote(sym):
            """Fetch a single quote via FMP v4 stable /quote endpoint."""
            q = fmp.get_quote(sym)
            if q and q.get("price"):
                price = q.get("price", 0)
                chg = q.get("changesPercentage", q.get("changePercentage", 0)) or 0
                return (sym, (price, chg))
            return (sym, None)

        def _get_index_quotes():
            from concurrent.futures import ThreadPoolExecutor as _TPE
            result = {}
            with _TPE(max_workers=8) as pool:
                for sym, val in pool.map(_get_single_quote, index_syms):
                    if val is not None:
                        result[sym] = val
            return result

        def _get_stock_quotes():
            quotes = fmp.get_quotes_batch(stock_syms)
            return {sym: (q.get("price", 0), q.get("changesPercentage", q.get("changePercentage", 0)) or 0)
                    for sym, q in quotes.items()} if quotes else {}

        def _get_fx_quotes():
            """Fetch FX rates via get_quote() — works for all pairs (USDKRW, EURUSD, USDJPY).
            get_fx_rate() has a >100 sanity check that blocks EUR/USD (~1.17) and USD/JPY (~150),
            so we use get_quote() directly for the macro dashboard."""
            from concurrent.futures import ThreadPoolExecutor as _TPE
            result = {}
            def _fetch_pair(pair):
                q = fmp.get_quote(pair)
                if q and q.get("price"):
                    return (pair, q["price"])
                # Fallback: try get_fx_rate (works for USDKRW where rate > 100)
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

        # ── Alpaca fallback for FMP-gated symbols ────────────────────────────
        # FMP Starter tier returns 402 for raw index quotes (^GSPC/^IXIC/^DJI/
        # ^RUT/^VIX) on every request. Alpaca Market Data does not serve the
        # caret-prefixed index symbols either, but it DOES cover their ETF
        # proxies with live pricing. Map each index to its most liquid ETF so
        # the macro payload has real 2026 values instead of stale snapshots.
        ALPACA_STOCK_MAP = {"GLD": "GLD", "USO": "USO", "SLV": "SLV", "UUP": "UUP"}
        INDEX_ETF_PROXY = {
            "^GSPC": "SPY",   # S&P 500
            "^IXIC": "QQQ",   # Nasdaq 100 (proxy for Composite)
            "^DJI":  "DIA",   # Dow Jones
            "^RUT":  "IWM",   # Russell 2000
            "^VIX":  "VIXY",  # Short-term VIX futures ETF
        }

        missing_stk = [s for s in stock_syms if s not in stk_data]
        missing_idx = [s for s in index_syms if s not in idx_data]

        if (missing_stk or missing_idx) and _ALPACA_ENABLED:
            try:
                from services.data import alpaca_market_adapter as ama

                for sym in missing_stk:
                    a_sym = ALPACA_STOCK_MAP.get(sym)
                    if not a_sym:
                        continue
                    q = ama.get_quote(a_sym)
                    if q and q.get("price") is not None:
                        stk_data[sym] = (float(q["price"]),
                                          float(q.get("changesPercentage") or 0))

                for sym in missing_idx:
                    a_sym = INDEX_ETF_PROXY.get(sym)
                    if not a_sym:
                        continue
                    q = ama.get_quote(a_sym)
                    if q and q.get("price") is not None:
                        idx_data[sym] = (float(q["price"]),
                                          float(q.get("changesPercentage") or 0))
            except Exception as _ama_err:
                logger.warning("Alpaca fallback failed: %s", _ama_err)

        # Equity indices — the ETF proxy price IS the level we publish. The
        # UI shows a single number + % change; using SPY=$708 instead of
        # GSPC=5800 keeps the relative move + 52W range mathematically honest
        # (ETFs track their index within ±0.02% intraday). Attempting a
        # scale conversion via historical ratio would inject drift and
        # produce subtly wrong numbers, so we publish ETF-native values.
        # Index level normalization (Wave 2 Bug #11 fix 2026-04-29):
        # Some FMP plans return raw ^GSPC/^IXIC/^DJI/^RUT (e.g. SPX 7,139)
        # while others reject the symbol and we substitute the ETF proxy
        # (SPY 711). The /api/market/indices route always publishes ETF
        # proxies for unit consistency; if we mix raw + proxy here, the same
        # UI can show "S&P 500 = 711" on /market/indices and "S&P 500 = 7,139"
        # on /discover/market-overview — a 10x divergence that triggers a
        # 표시광고법 §3 기만표시 risk (bug-hunter Wave 2 finding).
        # Policy: when an ETF proxy quote is available, prefer it. Emit a
        # `proxy_ticker` field so consumers can label "S&P 500 · SPY proxy".
        ETF_PROXY_FOR = {"^GSPC": "SPY", "^IXIC": "QQQ", "^DJI": "DIA", "^RUT": "IWM"}
        for sym, key in [("^GSPC","sp500"),("^IXIC","nasdaq"),("^DJI","dow"),("^RUT","russell2000")]:
            proxy = ETF_PROXY_FOR.get(sym)
            proxy_q = stk_data.get(proxy) if proxy else None
            # 1) Try ETF proxy first (matches /api/market/indices unit scale).
            if proxy_q is not None:
                p, c = proxy_q
                macro[key] = {
                    "price":        self._safe(p),
                    "change_pct":   self._safe(c),
                    "proxy_ticker": proxy,
                }
            # 2) Fall back to whatever idx_data has — could be the FMP raw
            #    index level OR (when missing_idx triggered above) the same
            #    Alpaca ETF proxy slotted under the caret symbol.
            elif sym in idx_data:
                p, c = idx_data[sym]
                entry: dict = {
                    "price":      self._safe(p),
                    "change_pct": self._safe(c),
                }
                # If the value came from the missing-idx Alpaca ETF fallback,
                # tag it so the consumer can still surface the proxy badge.
                p_val = entry["price"]
                if proxy and isinstance(p_val, (int, float)) and 0 < p_val < 1500:
                    entry["proxy_ticker"] = proxy
                macro[key] = entry

        # Korean indices — FMP does not serve KR indices on free tier, prefer KIS.
        # Fall back to FMP only if KIS fails.
        try:
            from services.container import realtime as _rt
            kis_ready = getattr(_rt, "kis_available", False)
        except Exception:
            kis_ready = False

        # KOSPI / KOSDAQ sanity bounds. Drop any reading outside these ranges
        # rather than publish a value the user has flagged as suspect (the
        # 6,641.02 incident on 2026-04-28 — most likely a KIS scaling glitch
        # or alternate index code returned in the response).
        # Override with PIVOX_KOSPI_RANGE / PIVOX_KOSDAQ_RANGE (low,high) only
        # if you've verified the rating with an external source (KRX/Yahoo).
        def _parse_range(env_key: str, default: tuple[float, float]) -> tuple[float, float]:
            import os as _os
            raw = (_os.getenv(env_key) or "").strip()
            if not raw:
                return default
            try:
                lo, hi = (float(x) for x in raw.split(","))
                if 0 < lo < hi:
                    return (lo, hi)
            except Exception:
                logger.debug("silent-fallback: _parse_range", exc_info=True)
                pass
            return default
        # Default ranges per CEO directive 2026-04-29: ceiling pushed to
        # 50,000 to absorb future re-rates without code change. The guard
        # still catches 100x unit-confusion glitches (e.g. KOSPI 660,000).
        # KOSPI valid floor: 1500 (legacy low) -- ceiling: 50000 (head-room)
        # KOSDAQ valid floor: 500 -- ceiling: 50000 (head-room)
        #
        # 2026-05-10 (B-06 KIS endpoint re-verify): bounds restored to
        # wide [1500, 50000] / [500, 50000]. The 2026-05-10 narrowing
        # (W-04) hypothesised that KIS "0001" was returning a 3x-scaled
        # KOSPI-200 mark-to-mid; live KIS API probe disproved this --
        # KOSPI=7498 is the real 2026-05-10 level (continuous uptrend in
        # KIS daily-price history 5052 -> 7498 across 2026-Q2). The
        # narrow bound was silently suppressing real data. The 100x
        # unit-confusion guard (e.g. KOSPI=749,800) remains preserved.
        # See routes/market.py:_kis_index_snapshot for the full evidence
        # log. Memory [공식 라이선스만] preserved (KIS Open API only).
        _KOSPI_RANGE = _parse_range("PIVOX_KOSPI_RANGE", (1500.0, 50000.0))
        _KOSDAQ_RANGE = _parse_range("PIVOX_KOSDAQ_RANGE", (500.0, 50000.0))

        if kis_ready:
            try:
                from services.kis.service import KISService
                _kis = KISService()
                for code, key, sanity in [
                    ("0001", "kospi",  _KOSPI_RANGE),
                    ("1001", "kosdaq", _KOSDAQ_RANGE),
                ]:
                    idx = _kis.get_index_price(code)
                    if idx and idx.get("price"):
                        price = self._safe(idx["price"])
                        if price is None or not (sanity[0] <= price <= sanity[1]):
                            logger.warning(
                                "KIS %s level %.2f outside sanity %s — dropping",
                                key.upper(), price or 0.0, sanity,
                            )
                            continue
                        macro[key] = {
                            "price":      price,
                            "change_pct": self._safe(idx.get("change_pct", 0)),
                        }
            except Exception as e:
                logger.debug("KIS index fetch failed: %s", e)

        # FMP fallback for KR indices (rarely works on free tier)
        for sym, key, sanity in [
            ("^KS11", "kospi",  _KOSPI_RANGE),
            ("^KQ11", "kosdaq", _KOSDAQ_RANGE),
        ]:
            if key not in macro and sym in idx_data:
                p, c = idx_data[sym]
                price = self._safe(p)
                if price is None or not (sanity[0] <= price <= sanity[1]):
                    logger.warning(
                        "FMP %s level %.2f outside sanity %s — dropping",
                        key.upper(), price or 0.0, sanity,
                    )
                    continue
                macro[key] = {"price": price, "change_pct": self._safe(c)}

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
                            "change_pct": self._safe(btc_data.get("changesPercentage", btc_data.get("changePercentage", 0)))}

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
            logger.debug("silent-fallback: Yield curve | get_enhanced_macro", exc_info=True)
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
                themes.append("🔥 EXTREME FEAR: Historically associated with contrarian opportunity windows in past observation periods (informational only).")
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
            themes.append(f"🐻 S&P SELLING: Index {sp_chg:.1f}% — defensive rotation pattern observed.")
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

            is_kr = self.is_korean(ticker)

            # Korean stocks: FMP free tier does NOT serve KR directly, but
            # fmp.get_info() routes KR tickers (.KS / .KQ) through the licensed
            # KIS `inquire-price` path internally (see fmp_service.py L711-727),
            # which publishes PER/EPS/PBR/시가총액 on a commercial ToS. Skipping
            # the call here was leaving every KR ticker with empty fundamentals
            # (P/E, EPS, profit_margin all null → "—" everywhere). Try get_info
            # for both US and KR; fall back to {} on failure rather than crashing.
            try:
                info = fmp.get_info(ticker) or {}
            except Exception as e:
                logger.warning("fmp.get_info failed for %s: %s", ticker, e)
                info = {}

            # Use get_price_history() which routes through KIS for KR, Alpaca for US
            hist = self.get_price_history(ticker, period="1y")

            # Get current price — KIS for KR, Alpaca first for US then FMP fallback
            cur = 0
            if is_kr:
                try:
                    from services.container import realtime as _rt
                    kis_data = _rt.get_price(ticker)
                    if kis_data and kis_data.get("price"):
                        cur = float(kis_data["price"])
                except Exception as kis_err:
                    logger.warning("KIS snapshot price failed %s: %s", ticker, kis_err)
            else:
                # US: Alpaca primary (unlimited), FMP fallback on Alpaca failure
                alp = self._alpaca_latest_quote(ticker)
                if alp and alp.get("price", 0) > 0:
                    cur = float(alp["price"])
                else:
                    q = fmp.get_quote(ticker)
                    cur = float(q.get("price", 0)) if q else float(info.get("price", 0) or 0)

            # Fallback to last close from history if live price missing
            if (not cur or cur <= 0) and hist is not None and not hist.empty:
                cur = float(hist["Close"].iloc[-1])

            if not cur or cur <= 0:
                return None

            if hist is None or hist.empty or len(hist) < 20:
                return None

            prev = float(hist["Close"].iloc[-2]) if len(hist) > 1 else cur
            chg = (cur - prev) / prev * 100
            curr = self.currency(ticker)
            # KR canonical name (BUG-01 2026-05-10): Korean preferred for
            # .KS/.KQ tickers regardless of FMP shortName (which is English).
            name = None
            if is_kr:
                try:
                    from services import kr_stock_registry as _kr_reg
                    name = _kr_reg.get_name(ticker.upper())
                except Exception:
                    logger.debug("silent-fallback: snapshot kr_name", exc_info=True)
            if not name:
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
                "sector":         _resolve_sector(ticker, info, is_kr),
                "industry":       info.get("industry", "Unknown"),
                "beta":           info.get("beta"),
                "currency":       curr,
                "is_korean":      is_kr,
            }
        except Exception as e:
            logger.error("Snapshot failed %s: %s", ticker, e)
            return None

    _history_cache = {}  # {(ticker, period): (timestamp, data)}
    _HISTORY_TTL = 300   # 5 minute cache for historical data

    def get_price_history(self, ticker: str, period: str = "6mo") -> "pd.DataFrame | None":
        """Get historical OHLCV.
        US stocks: Alpaca (primary, no call limit) -> FMP (fallback).
        KR stocks: KIS (primary) -> FMP (fallback).
        Indices (^): FMP only.
        """
        import time as _time
        cache_key = (ticker.upper(), period)
        cached = self._history_cache.get(cache_key)
        if cached and _time.time() - cached[0] < self._HISTORY_TTL:
            return cached[1]

        result = None

        # Route to appropriate primary source
        if ticker.startswith("^"):
            # Index tickers — FMP only (Alpaca doesn't serve indices)
            result = self._get_history_fmp(ticker, period)
        elif self.is_korean(ticker):
            # Korean stocks — try KIS first, FMP fallback
            result = self._get_history_kis(ticker, period)
            if result is None:
                result = self._get_history_fmp(ticker, period)
        else:
            # US stocks — try Alpaca first (no call limit), FMP fallback
            result = self._get_history_alpaca(ticker, period)
            if result is None:
                result = self._get_history_fmp(ticker, period)

        if result is not None:
            self._history_cache[cache_key] = (_time.time(), result)
        return result

    @staticmethod
    def _get_history_fmp(ticker: str, period: str) -> "pd.DataFrame | None":
        """Fetch historical data from FMP (fallback source)."""
        try:
            h = fmp.get_history(ticker, period=period)
            return h if h is not None and not h.empty else None
        except Exception:
            logger.debug("silent-fallback: _get_history_fmp", exc_info=True)
            return None

    @staticmethod
    def _get_history_alpaca(ticker: str, period: str) -> "pd.DataFrame | None":
        """Fetch historical daily bars from Alpaca (US stocks, no call limit)."""
        if not _alpaca_hist_available or not _alpaca_hist_client:
            return None
        try:
            from alpaca.data.requests import StockBarsRequest
            from alpaca.data.timeframe import TimeFrame
            from alpaca.data.enums import Adjustment

            # Map period string to days
            period_map = {
                "1d": 1, "5d": 5, "1mo": 30, "3mo": 90,
                "6mo": 180, "1y": 365, "2y": 730, "3y": 1095, "5y": 1825,
            }
            days = period_map.get(period, 90)
            start = datetime.now() - timedelta(days=days)

            # Class-share normalization: Alpaca expects `BRK/B` notation.
            # Accept callers that pass `BRK-B` or `BRK.B` and convert.
            alpaca_symbol = ticker
            if "-" in alpaca_symbol and not alpaca_symbol.startswith("^"):
                alpaca_symbol = alpaca_symbol.replace("-", "/")
            elif "." in alpaca_symbol and not alpaca_symbol.endswith(".KS") \
                    and not alpaca_symbol.endswith(".KQ") \
                    and not alpaca_symbol.startswith("^"):
                # Only treat a single-char suffix (e.g. BRK.B) as class share;
                # leave real suffixes alone.
                base, _, suf = alpaca_symbol.rpartition(".")
                if base and len(suf) == 1:
                    alpaca_symbol = f"{base}/{suf}"

            req = StockBarsRequest(
                symbol_or_symbols=[alpaca_symbol],
                timeframe=TimeFrame.Day,
                start=start,
                adjustment=Adjustment.ALL,  # split + dividend adjusted
            )
            bars = _alpaca_hist_client.get_stock_bars(req)
            df = bars.df

            if df is None or df.empty:
                return None

            # Alpaca returns MultiIndex (symbol, timestamp) — flatten
            if isinstance(df.index, pd.MultiIndex):
                # Try normalized symbol first, then original.
                try:
                    df = df.xs(alpaca_symbol, level="symbol")
                except KeyError:
                    df = df.xs(ticker, level="symbol")

            # Rename columns to match standard OHLCV format
            col_map = {
                "open": "Open", "high": "High", "low": "Low",
                "close": "Close", "volume": "Volume",
                "trade_count": "TradeCount", "vwap": "VWAP",
            }
            df = df.rename(columns=col_map)
            df.index.name = "Date"

            # Ensure required columns
            for col in ["Open", "High", "Low", "Close", "Volume"]:
                if col not in df.columns:
                    df[col] = 0

            logger.debug("Alpaca historical: %s returned %s bars", ticker, len(df))
            return df

        except Exception as e:
            logger.warning("Alpaca historical failed for %s: %s", ticker, e)
            return None

    @staticmethod
    def _get_history_kis(ticker: str, period: str) -> "pd.DataFrame | None":
        """Fetch historical daily bars from KIS API (Korean stocks).
        KIS daily chart API: /uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice
        """
        try:
            kis_key = os.environ.get("KIS_APP_KEY", "").strip()
            kis_secret = os.environ.get("KIS_APP_SECRET", "").strip()
            if not kis_key or not kis_secret:
                return None

            # Get KIS access token via the process-wide token manager
            # (avoids racing with RealtimeService / KISService for KIS's
            # 1-token-per-minute quota — see kis_token_manager.py).
            from services.kis.token_manager import get_kis_token_manager
            access_token = get_kis_token_manager().get_token()
            if not access_token:
                return None

            # Convert ticker to 6-digit code
            stock_code = ticker.upper().replace(".KS", "").replace(".KQ", "")
            if not stock_code.isdigit():
                return None

            period_map = {
                "1d": 1, "5d": 5, "1mo": 30, "3mo": 90,
                "6mo": 180, "1y": 365, "2y": 730, "3y": 1095, "5y": 1825,
            }
            days = period_map.get(period, 90)
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")

            headers = {
                "authorization": f"Bearer {access_token}",
                "appkey": kis_key,
                "appsecret": kis_secret,
                "tr_id": "FHKST03010100",
                "content-type": "application/json; charset=utf-8",
            }

            # KIS returns max 100 records per call — paginate backwards
            import time as _kis_time
            all_rows = []
            cursor_end = end_date

            for _page in range(15):  # max 15 pages = ~1500 bars (6y)
                params = {
                    "FID_COND_MRKT_DIV_CODE": "J",
                    "FID_INPUT_ISCD": stock_code,
                    "FID_INPUT_DATE_1": start_date,
                    "FID_INPUT_DATE_2": cursor_end,
                    "FID_PERIOD_DIV_CODE": "D",
                    "FID_ORG_ADJ_PRC": "0",
                }
                r = requests.get(
                    "https://openapi.koreainvestment.com:9443"
                    "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
                    headers=headers,
                    params=params,
                    timeout=10,
                )
                data = r.json()
                records = data.get("output2", [])
                if not records:
                    break

                page_rows = []
                earliest_dt = None
                for rec in records:
                    try:
                        dt = rec.get("stck_bsop_date", "")
                        if not dt or len(dt) != 8:
                            continue
                        page_rows.append({
                            "Date": pd.Timestamp(f"{dt[:4]}-{dt[4:6]}-{dt[6:8]}"),
                            "Open": float(rec.get("stck_oprc", 0)),
                            "High": float(rec.get("stck_hgpr", 0)),
                            "Low": float(rec.get("stck_lwpr", 0)),
                            "Close": float(rec.get("stck_clpr", 0)),
                            "Volume": int(rec.get("acml_vol", 0)),
                        })
                        if earliest_dt is None or dt < earliest_dt:
                            earliest_dt = dt
                    except (ValueError, TypeError):
                        logger.debug("silent-fallback: _get_history_kis", exc_info=True)
                        continue

                if not page_rows:
                    break
                all_rows.extend(page_rows)

                # If we got fewer than 100 records, no more pages
                if len(records) < 100:
                    break
                # If earliest record is at or before start_date, done
                if earliest_dt and earliest_dt <= start_date:
                    break
                # Move cursor to day before earliest record
                if earliest_dt:
                    from datetime import datetime as _dt_cls
                    prev = _dt_cls.strptime(earliest_dt, "%Y%m%d") - timedelta(days=1)
                    cursor_end = prev.strftime("%Y%m%d")

                _kis_time.sleep(0.15)  # rate limit courtesy

            if not all_rows:
                return None

            df = pd.DataFrame(all_rows)
            df = df.drop_duplicates(subset=["Date"])
            df = df.set_index("Date").sort_index()
            logger.debug(f"KIS historical: {ticker} returned {len(df)} bars ({_page+1} pages)")
            return df

        except Exception as e:
            logger.warning("KIS historical failed for %s: %s", ticker, e)
            return None

    def get_prices_batch(self, tickers: list[str]) -> dict:
        """Batch price fetch with multi-source fallback.

        Routing:
          - US tickers: Alpaca batch (unlimited) primary, FMP batch fallback
          - KR tickers: KIS (via realtime service), FMP fallback
        """
        result = {}
        if not tickers:
            return result

        us_tickers = [t for t in tickers if not self.is_korean(t)]
        kr_tickers = [t for t in tickers if self.is_korean(t)]

        # US: Alpaca batch first (no daily call limit)
        if us_tickers and _alpaca_hist_available and _alpaca_hist_client:
            try:
                from alpaca.data.requests import StockLatestBarRequest
                req = StockLatestBarRequest(symbol_or_symbols=us_tickers)
                bars = _alpaca_hist_client.get_stock_latest_bar(req)
                for sym, bar in bars.items():
                    if bar and float(bar.close) > 0:
                        price = float(bar.close)
                        result[sym] = {
                            "price":         round(price, 2),
                            "price_display": self.fmt_price(price, sym),
                            "currency":      "USD",
                            "source":        "alpaca",
                        }
            except Exception as e:
                logger.warning("Alpaca batch price fetch failed: %s", e)

        # KR: KIS via realtime service (iterates internally)
        if kr_tickers:
            try:
                from services.container import realtime as _rt
                kis_prices = _rt.get_prices_batch(kr_tickers)
                for t, p in kis_prices.items():
                    if p and p.get("price", 0) > 0:
                        price = p["price"]
                        result[t] = {
                            "price":         round(price, 0),
                            "price_display": self.fmt_price(price, t),
                            "currency":      "KRW",
                            "source":        p.get("source", "kis"),
                        }
            except Exception as e:
                logger.warning("KIS batch price fetch failed: %s", e)

        # FMP fallback for any ticker still missing
        missing = [t for t in tickers if t not in result]
        if missing:
            try:
                quotes = fmp.get_quotes_batch(missing)
                for ticker in missing:
                    q = quotes.get(ticker)
                    if q and q.get("price", 0) > 0:
                        price = q["price"]
                        curr = self.currency(ticker)
                        result[ticker] = {
                            "price":         round(price, 0 if curr == "KRW" else 2),
                            "price_display": self.fmt_price(price, ticker),
                            "currency":      curr,
                            "source":        "fmp",
                        }
            except Exception as e:
                logger.debug("FMP batch fallback failed: %s", e)

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
        filled = set()
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
                    filled.add(sym)
        except Exception:
            logger.debug("silent-fallback: get_sector_performance", exc_info=True)
            pass

        missing = [(sym, name) for sym, name in sectors if sym not in filled]
        if missing and _ALPACA_ENABLED:
            try:
                from services.data import alpaca_market_adapter as ama

                for sym, name in missing:
                    q = ama.get_quote(sym)
                    if q and q.get("price") is not None:
                        result.append({
                            "sector":     name,
                            "symbol":     sym,
                            "change_pct": round(float(q.get("changesPercentage") or 0), 2),
                            "price":      round(float(q["price"]), 2),
                        })
            except Exception as exc:
                logger.warning("Alpaca sector fallback failed: %s", exc)
        return result

    # ── Pre-warm Cache ────────────────────────────────────────────────────────

    def prefetch_discover_pool(self, tickers: list[str] = None):
        """Pre-warm FMP cache for discover pool tickers using batch API calls.

        This should be called once on app startup or before a discover scan.
        Dramatically reduces FMP API calls by:
        - Fetching profiles in batch (50 tickers = 1 call instead of 50)
        - Fetching quotes in batch (50 tickers = 1 call instead of 50)
        - Pre-building get_info() cache from components

        Without prefetch: 50 tickers * 6 calls = 300 FMP calls
        With prefetch:    2 batch + ~100 individual ratios/metrics = ~102 calls (first run)
                          2 batch + 0 (cached from 24h TTL) = 2 calls (subsequent runs same day)
        """
        if tickers is None:
            # Import discover pool from engine if not provided
            try:
                from services.quant.engine import QuantEngine
                tickers = QuantEngine.DISCOVER_POOL
            except ImportError:
                logger.warning("Cannot import QuantEngine for discover pool")
                return
        fmp.prefetch_fundamentals(tickers)
