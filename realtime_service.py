"""
PivoxQuant — Unified Real-time Price Service
Routes: US stocks → Alpaca, KR stocks → KIS, fallback → FMP
Provides single interface for all price data across the app.
"""

import os
import logging
import time
import threading
from datetime import datetime

logger = logging.getLogger(__name__)


class RealtimeService:
    """Unified real-time price service. Alpaca (US) + KIS (KR) + FMP fallback.

    KR path: attempts KIS WebSocket (millisecond ticks) first. If approval_key
    fails or the socket drops repeatedly, falls back to REST polling.
    """

    def __init__(self):
        self.alpaca_client = None
        self.kis_token = None
        self.kis_token_expires = None
        self.alpaca_available = False
        self.kis_available = False
        self._price_cache = {}  # {ticker: {price, timestamp, ...}}
        self._cache_ttl = 5     # seconds

        # KIS WebSocket (lazy init on first KR request)
        self._kis_ws = None
        self._kis_ws_attempted = False
        self._kis_ws_lock = threading.Lock()

        # Init Alpaca (gated by ALPACA_ENABLED kill switch — default OFF).
        # When disabled, `alpaca_available` stays False and all downstream
        # code paths (routes/market.py, routes/portfolio.py, routes/realtime.py)
        # route US prices through FMP instead.
        alpaca_enabled = os.environ.get("ALPACA_ENABLED", "0").strip() in (
            "1", "true", "True", "TRUE", "yes",
        )
        api_key = os.environ.get("ALPACA_API_KEY", "").strip()
        secret = os.environ.get("ALPACA_SECRET_KEY", "").strip()
        if not alpaca_enabled:
            logger.info(
                "Realtime: Alpaca disabled (ALPACA_ENABLED=0); "
                "US realtime quotes will use FMP."
            )
        elif api_key and secret:
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
        # Real vs. Virtual (VTS) KIS endpoint
        _use_real = os.environ.get("KIS_USE_REAL", "0").strip() in ("1", "true", "True", "TRUE", "yes")
        self.kis_base = (
            "https://openapi.koreainvestment.com:9443"
            if _use_real
            else "https://openapivts.koreainvestment.com:29443"
        )
        if self.kis_key and self.kis_secret:
            self.kis_available = True
            logger.info(f"Realtime: KIS initialized (KR stocks) — base={self.kis_base} real={_use_real}")

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

        # Fallback to FMP
        if not result:
            result = self._get_fmp_price(ticker)

        if result:
            result["_ts"] = time.time()
            self._price_cache[ticker] = result

        return result

    def get_prices_batch(self, tickers):
        """Get prices for multiple tickers at once."""
        us_tickers = [t for t in tickers if not self.is_korean(t)]
        kr_tickers = [t for t in tickers if self.is_korean(t)]
        results = {}

        # Batch US via Alpaca — prefer latest trade prints over 1-min bars.
        if us_tickers and self.alpaca_available:
            try:
                from alpaca.data.requests import (
                    StockLatestTradeRequest,
                    StockLatestBarRequest,
                )
                trades_map = {}
                try:
                    tr_req = StockLatestTradeRequest(symbol_or_symbols=us_tickers)
                    trades_map = self.alpaca_client.get_stock_latest_trade(tr_req) or {}
                except Exception as te:
                    logger.debug(f"Alpaca batch latest trade failed: {te}")

                req = StockLatestBarRequest(symbol_or_symbols=us_tickers)
                bars = self.alpaca_client.get_stock_latest_bar(req) or {}
                # Union of symbols across both responses
                all_syms = set(bars.keys()) | set(trades_map.keys())
                for sym in all_syms:
                    bar = bars.get(sym)
                    trade = trades_map.get(sym)
                    trade_price = float(trade.price) if (trade and getattr(trade, "price", 0)) else None
                    if trade_price is None and bar is None:
                        continue
                    price = trade_price if trade_price is not None else float(bar.close)
                    ts = (
                        trade.timestamp.isoformat() if (trade and getattr(trade, "timestamp", None))
                        else (bar.timestamp.isoformat() if bar else datetime.now().isoformat())
                    )
                    results[sym] = {
                        "ticker": sym,
                        "price": round(price, 2),
                        "price_display": f"${price:,.2f}",
                        "open": round(float(bar.open), 2) if bar else round(price, 2),
                        "high": round(float(bar.high), 2) if bar else round(price, 2),
                        "low": round(float(bar.low), 2) if bar else round(price, 2),
                        "volume": int(bar.volume) if bar else 0,
                        "currency": "USD",
                        "source": "alpaca",
                        "timestamp": ts,
                    }
            except Exception as e:
                logger.warning(f"Alpaca batch failed: {e}")

        # KR: warm up WS subscriptions, then fetch per-ticker
        # (KIS REST doesn't support batch; WS pushes updates into cache)
        if kr_tickers and self.kis_available:
            ws = self._ensure_kis_ws()
            if ws is not None:
                for t in kr_tickers:
                    code = self.to_kr_code(t)
                    if code:
                        ws.subscribe(code)
        for t in kr_tickers:
            p = self._get_kis_price(t)
            if p:
                results[t] = p

        # Fallback for missing — parallel FMP calls with 5s hard deadline.
        # Previously this was a serial loop: N tickers * 10s FMP timeout = N*10s stall.
        # Now all missing tickers are fetched concurrently; the whole batch times out in 5s.
        missing = [t for t in tickers if t not in results]
        if missing:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            with ThreadPoolExecutor(max_workers=min(len(missing), 6)) as pool:
                fut_map = {pool.submit(self._get_fmp_price, t): t for t in missing}
                for fut in as_completed(fut_map, timeout=5):
                    try:
                        p = fut.result()
                        if p:
                            results[fut_map[fut]] = p
                    except Exception:
                        pass

        return results

    def get_all_realtime(self):
        """Get real-time snapshot for SSE streaming (all cached + fresh)."""
        return {k: v for k, v in self._price_cache.items() if time.time() - v.get("_ts", 0) < 30}

    # ── Alpaca (US) ───────────────────────────────────────────

    def _get_alpaca_price(self, ticker):
        if not self.alpaca_available:
            return None
        try:
            from alpaca.data.requests import (
                StockLatestTradeRequest,
                StockLatestQuoteRequest,
                StockLatestBarRequest,
            )
            # Latest trade (actual print, but RTH-only).
            trade_price = None
            trade_ts = None
            try:
                tr_req = StockLatestTradeRequest(symbol_or_symbols=[ticker])
                trades = self.alpaca_client.get_stock_latest_trade(tr_req)
                trade = trades.get(ticker) if trades else None
                if trade and getattr(trade, "price", 0):
                    trade_price = float(trade.price)
                    trade_ts = trade.timestamp
            except Exception as te:
                logger.debug(f"Alpaca latest trade failed {ticker}: {te}")

            # Latest quote — captures pre-market / after-hours via bid/ask.
            quote_price = None
            quote_ts = None
            try:
                q_req = StockLatestQuoteRequest(symbol_or_symbols=[ticker])
                quotes = self.alpaca_client.get_stock_latest_quote(q_req)
                quote = quotes.get(ticker) if quotes else None
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
            except Exception as qe:
                logger.debug(f"Alpaca latest quote failed {ticker}: {qe}")

            # Bar for OHLC.
            req = StockLatestBarRequest(symbol_or_symbols=[ticker])
            bars = self.alpaca_client.get_stock_latest_bar(req)
            bar = bars.get(ticker)
            if bar is None and trade_price is None and quote_price is None:
                return None

            # Pick freshest source: extended-hours quote often beats stale trade.
            price = trade_price if trade_price is not None else float(bar.close) if bar else quote_price
            if quote_price is not None and quote_ts is not None and trade_ts is not None:
                if quote_ts > trade_ts:
                    price = quote_price
                    trade_ts = quote_ts
            elif trade_price is None and quote_price is not None:
                price = quote_price
            return {
                "ticker": ticker,
                "price": round(price, 2),
                "price_display": f"${price:,.2f}",
                "open": round(float(bar.open), 2) if bar else round(price, 2),
                "high": round(float(bar.high), 2) if bar else round(price, 2),
                "low": round(float(bar.low), 2) if bar else round(price, 2),
                "volume": int(bar.volume) if bar else 0,
                "currency": "USD",
                "source": "alpaca",
                "timestamp": trade_ts or (bar.timestamp.isoformat() if bar else datetime.now().isoformat()),
            }
        except Exception as e:
            logger.warning(f"Alpaca price failed {ticker}: {e}")
            return None

    # ── KIS WebSocket bootstrap (millisecond streaming) ───────

    def _ensure_kis_ws(self):
        """Lazy-start KIS WebSocket. Returns the running instance or None.

        VTS(모의) 앱키는 대부분 실시간 WS 구독이 불가하므로 실패 시
        기존 REST polling 경로로 자연스럽게 폴백한다.
        """
        if not self.kis_available:
            return None
        with self._kis_ws_lock:
            if self._kis_ws is not None:
                return self._kis_ws
            if self._kis_ws_attempted:
                # already tried and failed; don't spam re-attempts
                return None
            self._kis_ws_attempted = True
            try:
                from kis_websocket_service import KISWebSocketService
                svc = KISWebSocketService(on_price=self._on_ws_tick)
                if not svc.available:
                    logger.info("KIS WS not available (library missing or creds), using polling")
                    return None
                if not svc.start():
                    logger.warning(
                        "KIS WS start failed (approval_key 발급 실패 가능) — polling 폴백"
                    )
                    return None
                self._kis_ws = svc
                logger.info("Realtime: KIS WebSocket streaming active")
                return svc
            except Exception as e:
                logger.warning(f"KIS WS init error: {e} — polling 폴백")
                return None

    def _on_ws_tick(self, data: dict):
        """Callback invoked by KIS WebSocket on every parsed trade tick.

        Pushes into the shared price cache so the existing SSE generator
        (which batches get_prices_batch()) streams fresh data unchanged.
        """
        try:
            ticker = data.get("ticker")
            if not ticker:
                return
            data["_ts"] = time.time()
            self._price_cache[ticker] = data
            # Also index by 6-digit code so either form hits cache
            code = ticker.replace(".KS", "").replace(".KQ", "")
            if code.isdigit() and len(code) == 6:
                self._price_cache[code] = data
        except Exception as e:
            logger.debug(f"WS tick cache error: {e}")

    def stop_kis_ws(self):
        """Gracefully stop the KIS WebSocket (for shutdown hooks)."""
        with self._kis_ws_lock:
            if self._kis_ws is not None:
                try:
                    self._kis_ws.stop()
                except Exception:
                    pass
                self._kis_ws = None

    # ── KIS (KR) ──────────────────────────────────────────────

    def _get_kis_token(self):
        """Delegate to the process-wide KISTokenManager.

        Keeps the old method name so existing internal callers work unchanged.
        """
        try:
            from kis_token_manager import get_kis_token_manager
            return get_kis_token_manager().get_token()
        except Exception as e:
            logger.error(f"KIS token manager error: {e}")
            return None

    def _get_kis_price(self, ticker):
        if not self.kis_available:
            return None

        kr_code = self.to_kr_code(ticker)
        if not kr_code:
            return None

        # ── Prefer live WebSocket stream if available ──
        ws = self._ensure_kis_ws()
        if ws is not None:
            ws.subscribe(kr_code)
            # Serve fresh cached tick (<30s) if any
            cached = self._price_cache.get(f"{kr_code}.KS") or self._price_cache.get(kr_code)
            if cached and cached.get("source") == "kis_ws" and time.time() - cached.get("_ts", 0) < 30:
                return cached
            # Otherwise fall through to REST — first tick seeds cache for next call

        token = self._get_kis_token()
        if not token:
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
                f"{self.kis_base}/uapi/domestic-stock/v1/quotations/inquire-price",
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

    # ── FMP fallback ─────────────────────────────────────────

    def _get_fmp_price(self, ticker):
        """FMP quote as fallback for Alpaca (US) and KIS (KR)."""
        try:
            import fmp_service as fmp
            q = fmp.get_quote(ticker)
            if not q or q.get("price", 0) <= 0:
                return None
            price = q["price"]
            is_kr = self.is_korean(ticker)
            return {
                "ticker": ticker,
                "price": round(float(price), 0 if is_kr else 2),
                "price_display": f"₩{int(price):,}" if is_kr else f"${float(price):,.2f}",
                "currency": "KRW" if is_kr else "USD",
                "source": "fmp",
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.warning(f"FMP fallback failed {ticker}: {e}")
            return None
