"""
StockPilot — Unified Real-time Price Service
Routes: US stocks → Alpaca, KR stocks → KIS, fallback → yfinance
Provides single interface for all price data across the app.
"""

import os
import logging
import time
import threading
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class RealtimeService:
    """Unified real-time price service. Alpaca (US) + KIS (KR) + yfinance fallback."""

    def __init__(self):
        self.alpaca_client = None
        self.kis_token = None
        self.kis_token_expires = None
        self.alpaca_available = False
        self.kis_available = False
        self._price_cache = {}  # {ticker: {price, timestamp, ...}}
        self._cache_ttl = 5     # seconds

        # Init Alpaca
        api_key = os.environ.get("ALPACA_API_KEY", "").strip()
        secret = os.environ.get("ALPACA_SECRET_KEY", "").strip()
        if api_key and secret:
            try:
                from alpaca.data.historical import StockHistoricalDataClient
                self.alpaca_client = StockHistoricalDataClient(api_key, secret)
                self.alpaca_available = True
                logger.info("Realtime: Alpaca initialized (US stocks)")
            except Exception as e:
                logger.warning(f"Alpaca init failed: {e}")

        # Init KIS
        self.kis_key = os.environ.get("KIS_APP_KEY", "").strip()
        self.kis_secret = os.environ.get("KIS_APP_SECRET", "").strip()
        if self.kis_key and self.kis_secret:
            self.kis_available = True
            logger.info("Realtime: KIS initialized (KR stocks)")

    @staticmethod
    def is_korean(ticker):
        t = ticker.upper().strip()
        return t.endswith(".KS") or t.endswith(".KQ") or (t.isdigit() and len(t) == 6)

    @staticmethod
    def to_kr_code(ticker):
        """Convert ticker to 6-digit KR code."""
        t = ticker.upper().strip()
        if t.endswith(".KS"):
            return t.replace(".KS", "")
        if t.endswith(".KQ"):
            return t.replace(".KQ", "")
        if t.isdigit() and len(t) == 6:
            return t
        return None

    # ── Unified Price API ─────────────────────────────────────

    def get_price(self, ticker):
        """Get real-time price for any ticker. Routes to appropriate API."""
        ticker = ticker.upper().strip()

        # Check cache
        cached = self._price_cache.get(ticker)
        if cached and time.time() - cached.get("_ts", 0) < self._cache_ttl:
            return cached

        if self.is_korean(ticker):
            result = self._get_kis_price(ticker)
        else:
            result = self._get_alpaca_price(ticker)

        # Fallback to yfinance
        if not result:
            result = self._get_yfinance_price(ticker)

        if result:
            result["_ts"] = time.time()
            self._price_cache[ticker] = result

        return result

    def get_prices_batch(self, tickers):
        """Get prices for multiple tickers at once."""
        us_tickers = [t for t in tickers if not self.is_korean(t)]
        kr_tickers = [t for t in tickers if self.is_korean(t)]
        results = {}

        # Batch US via Alpaca
        if us_tickers and self.alpaca_available:
            try:
                from alpaca.data.requests import StockLatestBarRequest
                req = StockLatestBarRequest(symbol_or_symbols=us_tickers)
                bars = self.alpaca_client.get_stock_latest_bar(req)
                for sym, bar in bars.items():
                    results[sym] = {
                        "ticker": sym,
                        "price": round(float(bar.close), 2),
                        "price_display": f"${float(bar.close):,.2f}",
                        "open": round(float(bar.open), 2),
                        "high": round(float(bar.high), 2),
                        "low": round(float(bar.low), 2),
                        "volume": int(bar.volume),
                        "currency": "USD",
                        "source": "alpaca",
                        "timestamp": bar.timestamp.isoformat(),
                    }
            except Exception as e:
                logger.warning(f"Alpaca batch failed: {e}")

        # KR one by one (KIS doesn't support batch)
        for t in kr_tickers:
            p = self._get_kis_price(t)
            if p:
                results[t] = p

        # Fallback for missing
        missing = [t for t in tickers if t not in results]
        for t in missing:
            p = self._get_yfinance_price(t)
            if p:
                results[t] = p

        return results

    def get_all_realtime(self):
        """Get real-time snapshot for SSE streaming (all cached + fresh)."""
        return {k: v for k, v in self._price_cache.items() if time.time() - v.get("_ts", 0) < 30}

    # ── Alpaca (US) ───────────────────────────────────────────

    def _get_alpaca_price(self, ticker):
        if not self.alpaca_available:
            return None
        try:
            from alpaca.data.requests import StockLatestBarRequest
            req = StockLatestBarRequest(symbol_or_symbols=[ticker])
            bars = self.alpaca_client.get_stock_latest_bar(req)
            bar = bars.get(ticker)
            if not bar:
                return None
            return {
                "ticker": ticker,
                "price": round(float(bar.close), 2),
                "price_display": f"${float(bar.close):,.2f}",
                "open": round(float(bar.open), 2),
                "high": round(float(bar.high), 2),
                "low": round(float(bar.low), 2),
                "volume": int(bar.volume),
                "currency": "USD",
                "source": "alpaca",
                "timestamp": bar.timestamp.isoformat(),
            }
        except Exception as e:
            logger.warning(f"Alpaca price failed {ticker}: {e}")
            return None

    # ── KIS (KR) ──────────────────────────────────────────────

    def _get_kis_token(self):
        if self.kis_token and self.kis_token_expires and datetime.now() < self.kis_token_expires:
            return self.kis_token
        try:
            import requests as req
            r = req.post(
                "https://openapivts.koreainvestment.com:29443/oauth2/tokenP",
                json={"grant_type": "client_credentials", "appkey": self.kis_key, "appsecret": self.kis_secret},
                timeout=10,
            )
            data = r.json()
            token = data.get("access_token")
            if token:
                self.kis_token = token
                self.kis_token_expires = datetime.now() + timedelta(hours=12)
                return token
            logger.warning(f"KIS token error: {data}")
            return None
        except Exception as e:
            logger.error(f"KIS token failed: {e}")
            return None

    def _get_kis_price(self, ticker):
        if not self.kis_available:
            return None
        token = self._get_kis_token()
        if not token:
            return None

        kr_code = self.to_kr_code(ticker)
        if not kr_code:
            return None

        try:
            import requests as req
            headers = {
                "Content-Type": "application/json; charset=utf-8",
                "authorization": f"Bearer {token}",
                "appkey": self.kis_key,
                "appsecret": self.kis_secret,
                "tr_id": "FHKST01010100",
            }
            params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": kr_code}
            r = req.get(
                "https://openapivts.koreainvestment.com:29443/uapi/domestic-stock/v1/quotations/inquire-price",
                headers=headers, params=params, timeout=10,
            )
            data = r.json()
            o = data.get("output", {})
            price = int(o.get("stck_prpr", 0))
            if not price:
                return None

            # Normalize ticker to .KS format
            norm_ticker = ticker if ".K" in ticker else kr_code + ".KS"

            return {
                "ticker": norm_ticker,
                "price": price,
                "price_display": f"₩{price:,}",
                "open": int(o.get("stck_oprc", 0)),
                "high": int(o.get("stck_hgpr", 0)),
                "low": int(o.get("stck_lwpr", 0)),
                "volume": int(o.get("acml_vol", 0)),
                "change": int(o.get("prdy_vrss", 0)),
                "change_pct": float(o.get("prdy_ctrt", 0)),
                "currency": "KRW",
                "source": "kis",
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.warning(f"KIS price failed {ticker}: {e}")
            return None

    # ── yfinance fallback ─────────────────────────────────────

    def _get_yfinance_price(self, ticker):
        try:
            import yfinance as yf
            stock = yf.Ticker(ticker)
            fi = stock.fast_info
            price = fi.last_price
            if not price or price <= 0:
                return None
            is_kr = self.is_korean(ticker)
            return {
                "ticker": ticker,
                "price": round(float(price), 0 if is_kr else 2),
                "price_display": f"₩{int(price):,}" if is_kr else f"${float(price):,.2f}",
                "currency": "KRW" if is_kr else "USD",
                "source": "yfinance",
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.warning(f"yfinance fallback failed {ticker}: {e}")
            return None
