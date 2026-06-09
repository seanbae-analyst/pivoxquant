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


# ── KIS REST quote throttle ──────────────────────────────────────────────
# KIS public tier allows ~20 req/sec but trips a per-second guard near the
# cap. When the KR batch fetches tickers concurrently, space the quote calls
# ~0.12s apart (~8 req/s) so parallelism never hits the throttle. Module-level
# so the spacing is shared across all concurrent callers/greenlets.
_KIS_QUOTE_MIN_INTERVAL = 0.12
_kis_quote_lock = threading.Lock()
_kis_quote_last_ts = 0.0


def _kis_quote_throttle() -> None:
    """Thread-safe fixed-interval spacer between KIS quote calls (never raises)."""
    global _kis_quote_last_ts
    with _kis_quote_lock:
        elapsed = time.time() - _kis_quote_last_ts
        if elapsed < _KIS_QUOTE_MIN_INTERVAL:
            time.sleep(_KIS_QUOTE_MIN_INTERVAL - elapsed)
        _kis_quote_last_ts = time.time()


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
        # Wave F-2 Bug #3: serialize check-then-set on the cache. KIS
        # WebSocket writes from an OS thread (`_on_ws_tick`) race with
        # gevent greenlets reading from the SSE generator. CPython's GIL
        # makes the underlying dict mutation safe from corruption, but
        # the *check-then-fetch* sequence in ``get_price`` is not atomic
        # — two greenlets can both miss the cache and fire duplicate
        # FMP calls (real $$ on the metered plan). The lock guards only
        # the cache read/write, never network I/O.
        self._price_cache_lock = threading.Lock()

        # KIS WebSocket (lazy init on first KR request)
        # SSE-2 fix (2026-05-09): TTL'd cooldown so a transient KIS gateway
        # outage does not permanently demote to REST polling.
        self._kis_ws = None
        self._kis_ws_attempted_at = None  # monotonic timestamp; Optional[float]
        self._KIS_WS_RETRY_AFTER = 300.0  # 5 min cooldown
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
                logger.warning("Alpaca init failed: %s", e)

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
            logger.info("Realtime: KIS initialized (KR stocks) — base=%s real=%s", self.kis_base, _use_real)

        # Self-heal guard: flips to True the first time a live KIS quote
        # returns EGW02004 (app-key/domain mismatch) so _get_kis_price
        # corrects self.kis_base exactly once and never recurses forever.
        self._kis_domain_corrected = False
        # The EGW02004 self-heal mutates _kis_domain_corrected AND self.kis_base
        # together. Under the concurrent KR batch (ThreadPoolExecutor workers are
        # real OS threads) an unguarded check-then-set let two threads both
        # "correct" and flip the domain back and forth, permanently stranding
        # kis_base on the wrong endpoint (→ every later KIS call EGW02004 → silent
        # stale fallback until restart). This lock makes the flip strictly
        # once-only and atomic.
        self._kis_domain_lock = threading.Lock()

        # KR realtime health (exposed via /api/realtime/status). Epoch
        # seconds of the last successful / failed KIS KR fetch — lets ops see
        # a degraded KR feed instead of discovering frozen prices by chance.
        self._kr_last_ok = None
        self._kr_last_fail = None
        # Per-quote REST timeout. Was 10s; bounded to 4s so one slow ticker
        # can't stall the concurrent KR batch past its deadline.
        self._KIS_QUOTE_TIMEOUT = 4

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

        # Wave F-2 Bug #3: lock-guarded cache read so concurrent callers
        # don't both observe a miss and race to call the upstream API
        # (duplicate FMP calls = wasted budget). Network I/O stays
        # outside the lock so a slow upstream doesn't block other
        # tickers.
        with self._price_cache_lock:
            cached = self._price_cache.get(ticker)
            if cached and time.time() - cached.get("_ts", 0) < self._cache_ttl:
                return cached

        if self.is_korean(ticker):
            result = self._get_kis_price(ticker)
            self._mark_kr(bool(result))  # track KR live-feed health
        else:
            result = self._get_alpaca_price(ticker)

        # Fallback to FMP
        if not result:
            result = self._get_fmp_price(ticker)

        if result:
            result["_ts"] = time.time()
            with self._price_cache_lock:
                self._price_cache[ticker] = result
            return result

        # Resilience: every live provider missed. Degrade to the last-known
        # cached value (flagged stale) so the price never vanishes from the UI
        # on a transient outage. Returns None only if nothing was ever cached.
        return self._serve_stale(ticker)

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
                    logger.debug("Alpaca batch latest trade failed: %s", te)

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
                logger.warning("Alpaca batch failed: %s", e)

        # KR: warm up WS subscriptions, then fetch tickers CONCURRENTLY.
        # KIS REST has no batch endpoint; the old serial loop stalled multi-KR
        # portfolios (N × per-call). Parallel fetch + shared per-second
        # throttle (_kis_quote_throttle, applied in _get_kis_price) + a hard
        # collect deadline keeps it fast without tripping the KIS rate guard.
        # WS still pushes ticks into the cache for subsequent rounds.
        if kr_tickers and self.kis_available:
            ws = self._ensure_kis_ws()
            if ws is not None:
                for t in kr_tickers:
                    code = self.to_kr_code(t)
                    if code:
                        ws.subscribe(code)
            from concurrent.futures import (
                ThreadPoolExecutor, as_completed, TimeoutError as _FTimeout,
            )
            with ThreadPoolExecutor(max_workers=min(len(kr_tickers), 6)) as pool:
                kr_fut = {pool.submit(self._get_kis_price, t): t for t in kr_tickers}
                try:
                    for fut in as_completed(kr_fut, timeout=8):
                        try:
                            p = fut.result()
                            if p:
                                results[kr_fut[fut]] = p
                        except Exception:
                            logger.debug("silent-fallback: KR batch fetch", exc_info=True)
                except _FTimeout:
                    logger.warning("KR batch hit 8s collect deadline; partial result")
            self._mark_kr(any(t in results for t in kr_tickers))

        # Fallback for missing — parallel FMP calls with a 5s collect deadline.
        # Previously serial: N tickers * 10s FMP timeout = N*10s stall. Now all
        # missing tickers run concurrently and we stop collecting after 5s.
        missing = [t for t in tickers if t not in results]
        if missing:
            from concurrent.futures import (
                ThreadPoolExecutor, as_completed, TimeoutError as _FTimeout,
            )
            with ThreadPoolExecutor(max_workers=min(len(missing), 6)) as pool:
                fut_map = {pool.submit(self._get_fmp_price, t): t for t in missing}
                try:
                    for fut in as_completed(fut_map, timeout=5):
                        try:
                            p = fut.result()
                            if p:
                                results[fut_map[fut]] = p
                        except Exception:
                            logger.debug("silent-fallback: get_prices_batch", exc_info=True)
                except _FTimeout:
                    # Don't let the collect deadline bubble out of the batch.
                    logger.warning("FMP batch fallback hit 5s collect deadline; partial result")

        # Resilience: anything STILL missing degrades to its last-known cached
        # value (flagged stale) so a transient KIS/FMP outage shows "last
        # price + 지연" instead of a vanished row. Mostly matters for KR.
        for t in [tk for tk in tickers if tk not in results]:
            stale = self._serve_stale(t)
            if stale is not None:
                results[t] = stale

        return results

    def get_all_realtime(self):
        """Get real-time snapshot for SSE streaming (all cached + fresh)."""
        # Wave F-2 Bug #3: snapshot the cache under lock to avoid
        # "dictionary changed size during iteration" when the KIS WS
        # thread mutates concurrently.
        now = time.time()
        with self._price_cache_lock:
            items = list(self._price_cache.items())
        return {k: v for k, v in items if now - v.get("_ts", 0) < 30}

    # ── Resilience: stale fallback + health ───────────────────

    def _serve_stale(self, ticker):
        """Return the last-known cached quote flagged ``stale``, or None.

        Resilience backstop: when every live provider misses, the client
        shows the last good price + a 'stale/지연' badge instead of the value
        vanishing. Combined with the frontend's ``keepPreviousData`` this
        makes a transient KIS/FMP outage invisible beyond the badge. Matters
        most for KR (FMP can't serve KRW quotes, so KIS is the only feed).
        """
        t = ticker.upper().strip()
        with self._price_cache_lock:
            cached = (
                self._price_cache.get(t)
                or self._price_cache.get(self.to_kr_code(t) or "")
            )
        if not cached or not cached.get("price"):
            return None
        out = dict(cached)
        out["stale"] = True
        out["stale_at"] = cached.get("_ts")
        out.pop("_ts", None)  # never let a stale entry pass the freshness check
        return out

    def _mark_kr(self, ok):
        """Record KR live-feed success/failure for the /status health probe."""
        if ok:
            self._kr_last_ok = time.time()
        else:
            self._kr_last_fail = time.time()

    def kr_health(self):
        """KR realtime health snapshot for /api/realtime/status.

        ``degraded`` is True when the most recent KR fetch failed (and was
        recent) — i.e. we are likely serving stale KR prices right now.
        """
        now = time.time()
        ok, fail = self._kr_last_ok, self._kr_last_fail
        degraded = bool(fail and (ok is None or fail >= ok) and (now - fail) < 120)
        return {
            "last_ok_age_s": round(now - ok, 1) if ok else None,
            "last_fail_age_s": round(now - fail, 1) if fail else None,
            "degraded": degraded,
        }

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
                logger.debug("Alpaca latest trade failed %s: %s", ticker, te)

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
                logger.debug("Alpaca latest quote failed %s: %s", ticker, qe)

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
            logger.warning("Alpaca price failed %s: %s", ticker, e)
            return None

    # ── KIS WebSocket bootstrap (millisecond streaming) ───────

    def _ensure_kis_ws(self):
        """Lazy-start KIS WebSocket. Returns the running instance or None.

        VTS(모의) 앱키는 대부분 실시간 WS 구독이 불가하므로 실패 시
        기존 REST polling 경로로 자연스럽게 폴백한다.
        """
        if not self.kis_available:
            return None
        import time as _time
        with self._kis_ws_lock:
            if self._kis_ws is not None:
                return self._kis_ws
            if self._kis_ws_attempted_at is not None:
                elapsed = _time.monotonic() - self._kis_ws_attempted_at
                if elapsed < self._KIS_WS_RETRY_AFTER:
                    return None
                logger.info(
                    "KIS WS cooldown elapsed (%.0fs) - retrying init", elapsed
                )
            self._kis_ws_attempted_at = _time.monotonic()
            try:
                from services.kis.websocket_service import KISWebSocketService
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
                logger.warning("KIS WS init error: %s — polling 폴백", e)
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
            # Wave F-2 Bug #3: serialize WS-thread writes against
            # greenlet readers in get_price/get_prices_batch.
            with self._price_cache_lock:
                self._price_cache[ticker] = data
                # Also index by 6-digit code so either form hits cache
                code = ticker.replace(".KS", "").replace(".KQ", "")
                if code.isdigit() and len(code) == 6:
                    self._price_cache[code] = data
        except Exception as e:
            logger.debug("WS tick cache error: %s", e)

    def stop_kis_ws(self):
        """Gracefully stop the KIS WebSocket (for shutdown hooks)."""
        with self._kis_ws_lock:
            if self._kis_ws is not None:
                try:
                    self._kis_ws.stop()
                except Exception:
                    logger.debug("silent-fallback: stop_kis_ws", exc_info=True)
                    pass
                self._kis_ws = None

    # ── KIS (KR) ──────────────────────────────────────────────

    def _get_kis_token(self):
        """Delegate to the process-wide KISTokenManager.

        Keeps the old method name so existing internal callers work unchanged.
        """
        try:
            from services.kis.token_manager import get_kis_token_manager
            return get_kis_token_manager().get_token()
        except Exception as e:
            logger.error("KIS token manager error: %s", e)
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
            # Serve fresh cached tick (<30s) if any.
            # Wave F-2 Bug #3: lock-guarded read so we never observe a
            # half-mutated dict from the WS thread.
            with self._price_cache_lock:
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
            _kis_quote_throttle()  # space concurrent KR calls under the KIS rate guard
            r = req.get(
                f"{self.kis_base}/uapi/domestic-stock/v1/quotations/inquire-price",
                headers=headers, params=params, timeout=self._KIS_QUOTE_TIMEOUT,
            )
            data = r.json()

            # ── Self-heal: app-key / domain mismatch (EGW02004) ──
            # A 모의(VTS) app-key hitting the 실전 domain (or vice-versa) is
            # rejected with EGW02004 BEFORE any price comes back. That is the
            # exact KIS_USE_REAL/app-key drift that silently froze KR quotes
            # at the prior daily close. Flip to the opposite KIS domain once,
            # re-pin the token there, and retry so live KR prices keep
            # flowing regardless of the env var. A correctly-configured
            # deployment never returns EGW02004, so this branch is inert.
            if data.get("msg_cd") == "EGW02004":
                # Atomic, once-only domain correction (see _kis_domain_lock).
                corrected_base = None
                with self._kis_domain_lock:
                    if not self._kis_domain_corrected:
                        self._kis_domain_corrected = True
                        real_now = self.kis_base == "https://openapi.koreainvestment.com:9443"
                        self.kis_base = (
                            "https://openapivts.koreainvestment.com:29443"
                            if real_now
                            else "https://openapi.koreainvestment.com:9443"
                        )
                        corrected_base = self.kis_base
                if corrected_base is None:
                    # Another thread already performed the one-time correction;
                    # this EGW02004 is a stale reply on the old domain. Do NOT
                    # flip again (that caused the back-and-forth strand). Fail
                    # this ticker for this cycle — the next fetch uses the
                    # corrected domain.
                    return None
                logger.error(
                    "KIS EGW02004 app-key/domain mismatch (%s) — auto-switching "
                    "to %s and retrying. Set KIS_USE_REAL=%s to fix at the source.",
                    data.get("msg1"), corrected_base,
                    "0" if corrected_base.startswith("https://openapivts") else "1",
                )
                try:
                    from services.kis.token_manager import get_kis_token_manager
                    get_kis_token_manager().force_domain(
                        use_real=not corrected_base.startswith("https://openapivts")
                    )
                except Exception as exc:
                    logger.warning("KIS token domain switch failed: %s", exc)
                return self._get_kis_price(ticker)  # one retry on corrected domain

            o = data.get("output", {})
            price = int(o.get("stck_prpr", 0))
            if not price:
                return None

            # Normalize ticker to .KS format
            norm_ticker = ticker if ".K" in ticker else kr_code + ".KS"

            result = {
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
            # Seed the shared cache (both key forms) so every caller — get_price,
            # get_prices_batch, quick_lookup — leaves a last-known KR value for
            # the stale fallback to serve during a later outage.
            with self._price_cache_lock:
                result["_ts"] = time.time()
                self._price_cache[norm_ticker] = result
                self._price_cache[kr_code] = result
            return result
        except Exception as e:
            logger.warning("KIS price failed %s: %s", ticker, e)
            return None

    # ── FMP fallback ─────────────────────────────────────────

    def _get_fmp_price(self, ticker):
        """FMP quote as fallback for Alpaca (US) and KIS (KR).

        Fallback order when the primary provider (Alpaca/KIS) misses:
          1. ``fmp.get_quote`` — may itself serve stale cache or Alpaca
             fallback. We inspect the result and propagate the ``stale``
             flag if ``fmp.get_quote`` returned a stale entry.
          2. ``fmp._get_cache_stale`` direct — belt+suspenders. Covers the
             path where ``fmp.get_quote`` returned ``None`` because the
             daily budget was hard-stopped BEFORE the stale-check branch
             could fire, or where a future refactor skips the internal
             stale lookup.
          3. Return ``None`` → route layer decodes this as
             "data_provider_throttled" (503) vs "ticker not found" (404).

        Returning ``None`` is reserved for "no data anywhere" — not for
        "FMP failed, try stale next time". The whole point of this fix is
        that a 402 cooldown or daily-soft-limit budget exhaustion must NOT cause
        every cache-miss ticker to 404 at the route layer.
        """
        is_kr = self.is_korean(ticker)

        def _format_quote(q, is_stale=False, stale_at=None):
            price = q.get("price") if isinstance(q, dict) else None
            if price is None or float(price) <= 0:
                return None
            payload = {
                "ticker": ticker,
                "price": round(float(price), 0 if is_kr else 2),
                "price_display": (
                    f"₩{int(price):,}" if is_kr else f"${float(price):,.2f}"
                ),
                "currency": "KRW" if is_kr else "USD",
                "source": "fmp_stale" if is_stale else "fmp",
                "timestamp": datetime.now().isoformat(),
            }
            if is_stale:
                payload["stale"] = True
                if stale_at is not None:
                    payload["stale_at"] = stale_at
            return payload

        try:
            from services.data import fmp as fmp
        except Exception as e:
            logger.warning("FMP import failed %s: %s", ticker, e)
            return None

        # 1. Normal path — `fmp.get_quote` already layers fresh cache,
        #    network, Alpaca fallback, and stale cache-of-last-resort.
        q = None
        try:
            q = fmp.get_quote(ticker)
        except Exception as e:
            logger.warning("FMP get_quote failed %s: %s", ticker, e)

        if q and isinstance(q, dict) and q.get("price", 0) and float(q.get("price") or 0) > 0:
            return _format_quote(q, is_stale=False)

        # 2. Belt+suspenders: if get_quote returned None (budget-exhausted
        #    BEFORE the internal stale branch could run, or other exotic
        #    failure), directly probe the stale cache ourselves.
        try:
            cache_key = f"quote:{ticker}"
            with fmp._cache_lock:
                entry = fmp._cache.get(cache_key)
            if entry and isinstance(entry, dict):
                stale_data = entry.get("data")
                stale_ts = entry.get("ts")
                if stale_data and isinstance(stale_data, dict):
                    formatted = _format_quote(
                        stale_data, is_stale=True, stale_at=stale_ts,
                    )
                    if formatted is not None:
                        logger.info(
                            "FMP stale cache served for %s (age=%.0fs)",
                            ticker,
                            (time.time() - stale_ts) if stale_ts else -1,
                        )
                        return formatted
        except Exception as e:
            logger.debug("FMP stale cache probe failed %s: %s", ticker, e)

        # 3. Truly no data — let the caller decide 404 vs 503.
        return None

    # ── Provider health introspection ────────────────────────
    def fmp_is_throttled(self):
        """True when FMP is budget-exhausted or every endpoint is cooling.

        Used by the route layer (``routes/realtime.py``) to distinguish
        ``data_provider_throttled`` (503) from ``ticker_not_found`` (404).
        Never raises — a missing helper yields False (assume healthy so
        the route stays 404 on legitimate lookup misses).
        """
        try:
            from services.data import fmp as fmp
        except Exception:
            return False
        try:
            if fmp._is_budget_exhausted():
                return True
            # /quote is the only endpoint realtime_service hits. If it's
            # in 402 cooldown AND the budget is already in stale-mode,
            # that's effectively "all primary paths down for US quotes".
            if fmp._is_endpoint_blocked("/quote") and fmp._is_budget_stale():
                return True
        except Exception:
            return False
        return False
