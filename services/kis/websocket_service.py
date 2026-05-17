"""
PivoxQuant — KIS WebSocket Real-time Price Streaming
----------------------------------------------------
Streams Korean stock trade ticks (H0STCNT0) over KIS WebSocket, parses
each tick, and fires a callback with a normalized price dict. Designed
to plug into RealtimeService's price cache so the existing SSE endpoint
broadcasts real-time data to the frontend without any client changes.

Key behavior
- REST approval_key issuance: POST /oauth2/Approval (production or VTS)
- WS URL: ws://ops.koreainvestment.com:21000  (실전)
          ws://ops.koreainvestment.com:31000  (모의) — 실시간시세 구독은
          대부분 실전 앱키에서만 허용됨. 모의키 사용 시 즉시 오류
          응답이 올 수 있어 명확한 로그를 남기고 polling 폴백을 유도.
- Subscribe/unsubscribe JSON frames with tr_id=H0STCNT0
- Heartbeat: KIS sends PINGPONG frames — answer with PINGPONG response
- Reconnect: exponential backoff 1s → 2s → 4s → ... capped at 30s
- Throttle: at most 2 updates/sec per ticker to match frontend rules

The service runs its own asyncio loop in a background thread so it
can coexist with Flask's sync request workers.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import threading
import time
from datetime import datetime
from typing import Callable, Dict, Optional, Set

import requests

# ── Sensitive-data masking (H3, 2026-04-24) ─────────────────────────────
_WS_SENSITIVE_RE = re.compile(
    r'("(?:appkey|appsecret|app_key|app_secret|secretkey|access_token|'
    r'approval_key|authorization|token|secret)"\s*:\s*")([^"]*)(")',
    re.IGNORECASE,
)


def _ws_redact(text: str, max_len: int = 200) -> str:
    if not text:
        return ""
    return _WS_SENSITIVE_RE.sub(lambda m: f'{m.group(1)}***{m.group(3)}', text)[:max_len]


def _ws_redact_dict(d: dict) -> dict:
    """Shallow redact a dict for logging; replaces sensitive values with '***'."""
    if not isinstance(d, dict):
        return d
    redacted = {}
    sensitive = {
        "appkey", "appsecret", "app_key", "app_secret", "secretkey",
        "access_token", "approval_key", "authorization", "token", "secret",
    }
    for k, v in d.items():
        if isinstance(k, str) and k.lower() in sensitive:
            redacted[k] = "***"
        else:
            redacted[k] = v
    return redacted

try:
    import websockets
    from websockets.exceptions import ConnectionClosed, InvalidStatusCode, WebSocketException
    WEBSOCKETS_OK = True
except Exception:  # pragma: no cover
    websockets = None  # type: ignore
    ConnectionClosed = Exception  # type: ignore
    InvalidStatusCode = Exception  # type: ignore
    WebSocketException = Exception  # type: ignore
    WEBSOCKETS_OK = False


logger = logging.getLogger(__name__)

# ── Endpoints ────────────────────────────────────────────────────────────
WS_URL_REAL = "ws://ops.koreainvestment.com:21000"
WS_URL_VTS = "ws://ops.koreainvestment.com:31000"
REST_URL_REAL = "https://openapi.koreainvestment.com:9443"
REST_URL_VTS = "https://openapivts.koreainvestment.com:29443"

# ── TR IDs ───────────────────────────────────────────────────────────────
TR_CONTRACT = "H0STCNT0"   # 주식 체결가 (real-time trade)
TR_ORDERBOOK = "H0STASP0"  # 주식 호가 (real-time orderbook)

# ── Field indices for H0STCNT0 pipe-delimited payload ───────────────────
# Reference: KIS Open API — 실시간시세 가이드
# 0: MKSC_SHRN_ISCD (종목코드)
# 1: STCK_CNTG_HOUR (체결 시간 HHMMSS)
# 2: STCK_PRPR (현재가)
# 3: PRDY_VRSS_SIGN (전일대비 부호 1~5)
# 4: PRDY_VRSS (전일대비)
# 5: PRDY_CTRT (전일대비율)
# 6: WGHN_AVRG_STCK_PRC (가중평균가)
# 7: STCK_OPRC (시가)
# 8: STCK_HGPR (고가)
# 9: STCK_LWPR (저가)
# 12: CNTG_VOL (체결거래량)
# 13: ACML_VOL (누적거래량)
IDX_CODE = 0
IDX_TIME = 1
IDX_PRICE = 2
IDX_CHG_SIGN = 3
IDX_CHG = 4
IDX_CHG_PCT = 5
IDX_OPEN = 7
IDX_HIGH = 8
IDX_LOW = 9
IDX_ACML_VOL = 13


class KISWebSocketService:
    """KIS real-time WebSocket client.

    Usage:
        svc = KISWebSocketService(on_price=lambda d: ...)
        if svc.start():
            svc.subscribe("005930")
            ...
            svc.stop()

    The price callback receives a dict shaped like RealtimeService output:
        {
          "ticker": "005930.KS",
          "price": 78300,
          "price_display": "₩78,300",
          "open": ..., "high": ..., "low": ...,
          "volume": ..., "change": ..., "change_pct": ...,
          "currency": "KRW",
          "source": "kis_ws",
          "timestamp": "...",
        }
    """

    # ── Reconnect policy ─────────────────────────────────────────────
    INITIAL_BACKOFF = 1.0
    MAX_BACKOFF = 30.0

    # ── Throttle: max 2 updates/sec per ticker ───────────────────────
    THROTTLE_MIN_INTERVAL = 0.5

    def __init__(
        self,
        on_price: Optional[Callable[[dict], None]] = None,
        is_real: Optional[bool] = None,
    ):
        self.app_key = os.environ.get("KIS_APP_KEY", "").strip()
        self.app_secret = os.environ.get("KIS_APP_SECRET", "").strip()
        self.on_price = on_price

        # VTS (모의) vs real. Default: if key looks like VTS (env flag), use VTS.
        # The env flag KIS_USE_REAL=1 forces production URL.
        if is_real is None:
            is_real = os.environ.get("KIS_USE_REAL", "").strip() in ("1", "true", "True")
        self.is_real = bool(is_real)

        self.ws_url = WS_URL_REAL if self.is_real else WS_URL_VTS
        self.rest_url = REST_URL_REAL if self.is_real else REST_URL_VTS

        self._approval_key: Optional[str] = None
        self._approval_fetched_at: float = 0.0

        # Subscribed stock codes (6-digit strings, no .KS suffix)
        self._subscribed: Set[str] = set()
        # Tickers that have been SUBSCRIBE-ed on the current socket
        self._active_on_socket: Set[str] = set()

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._ws = None  # current live websocket
        self._stop_event: Optional[asyncio.Event] = None
        self._running = False

        # Per-ticker throttle: code -> last emit time
        self._last_emit: Dict[str, float] = {}

        # State flag used by RealtimeService to decide fallback behavior
        self.available = bool(self.app_key and self.app_secret and WEBSOCKETS_OK)
        if not WEBSOCKETS_OK:
            logger.warning("KISWebSocketService: `websockets` package not installed — WS disabled")

    # ── Public API ───────────────────────────────────────────────────

    def get_approval_key(self, force: bool = False) -> Optional[str]:
        """Issue a short-lived approval_key via REST /oauth2/Approval.
        Cached for ~12h; callers can `force=True` to refresh.
        """
        if not self.available:
            return None
        if not force and self._approval_key and (time.time() - self._approval_fetched_at) < 11 * 3600:
            return self._approval_key

        try:
            body = {
                "grant_type": "client_credentials",
                "appkey": self.app_key,
                "secretkey": self.app_secret,
            }
            r = requests.post(
                f"{self.rest_url}/oauth2/Approval",
                json=body,
                headers={"Content-Type": "application/json; charset=utf-8"},
                timeout=10,
            )
            if r.ok:
                data = r.json()
                key = data.get("approval_key")
                if key:
                    self._approval_key = key
                    self._approval_fetched_at = time.time()
                    logger.info(
                        "KIS WS approval_key issued (url=%s)",
                        "real" if self.is_real else "vts",
                    )
                    return key
                logger.warning(
                    "KIS /oauth2/Approval missing approval_key in response: %s",
                    _ws_redact_dict(data),
                )
            else:
                logger.warning(
                    "KIS /oauth2/Approval HTTP %s: %s (VTS keys often cannot subscribe to real-time WS)",
                    r.status_code, _ws_redact(r.text, max_len=200),
                )
            return None
        except Exception as e:
            logger.warning("KIS approval_key request failed: %s", e)
            return None

    def start(self) -> bool:
        """Start the background asyncio thread. Returns True if launched."""
        if self._running:
            return True
        if not self.available:
            logger.info("KIS WS service unavailable — missing key/secret or websockets lib")
            return False
        key = self.get_approval_key()
        if not key:
            logger.warning(
                "KIS WS: approval_key unavailable — falling back to polling. "
                "Note: 모의투자(VTS) 앱키로는 실시간 WS 구독이 제한될 수 있습니다."
            )
            return False

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="kis-ws")
        self._thread.start()
        logger.info("KIS WebSocket service started")
        return True

    def stop(self) -> None:
        """Gracefully stop the background loop."""
        if not self._running:
            return
        self._running = False
        loop = self._loop
        stop_event = self._stop_event
        if loop and stop_event:
            loop.call_soon_threadsafe(stop_event.set)
        if self._thread:
            self._thread.join(timeout=5)
        self._loop = None
        self._thread = None
        logger.info("KIS WebSocket service stopped")

    def subscribe(self, ticker: str) -> None:
        """Subscribe to real-time trades for a ticker. Accepts 6-digit or .KS/.KQ."""
        code = self._to_kr_code(ticker)
        if not code:
            return
        if code in self._subscribed:
            return
        self._subscribed.add(code)
        if self._loop and self._running:
            self._loop.call_soon_threadsafe(lambda c=code: asyncio.create_task(self._send_subscribe(c)))

    def unsubscribe(self, ticker: str) -> None:
        code = self._to_kr_code(ticker)
        if not code:
            return
        self._subscribed.discard(code)
        if self._loop and self._running:
            self._loop.call_soon_threadsafe(lambda c=code: asyncio.create_task(self._send_unsubscribe(c)))

    def is_connected(self) -> bool:
        return self._ws is not None and self._running

    # ── Internals ────────────────────────────────────────────────────

    @staticmethod
    def _to_kr_code(ticker: str) -> Optional[str]:
        t = (ticker or "").upper().strip()
        if t.endswith(".KS"):
            t = t[:-3]
        elif t.endswith(".KQ"):
            t = t[:-3]
        if t.isdigit() and len(t) == 6:
            return t
        return None

    def _run_loop(self):
        """Thread entrypoint: runs asyncio event loop until stop()."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._stop_event = asyncio.Event()
        try:
            loop.run_until_complete(self._connect_forever())
        except Exception as e:
            logger.error("KIS WS thread error: %s", e)
        finally:
            try:
                loop.close()
            except Exception:
                logger.debug("silent-fallback: _run_loop", exc_info=True)
                pass
            self._loop = None

    async def _connect_forever(self):
        """Maintain a single socket, reconnecting with exponential backoff."""
        backoff = self.INITIAL_BACKOFF
        while self._running:
            try:
                # Always refresh approval_key before each fresh connection attempt
                key = self.get_approval_key(force=False)
                if not key:
                    logger.warning("KIS WS: approval_key missing, retry in %.1fs", backoff)
                    await self._sleep_or_stop(backoff)
                    backoff = min(backoff * 2, self.MAX_BACKOFF)
                    continue

                logger.info("KIS WS connecting: %s", self.ws_url)
                async with websockets.connect(
                    self.ws_url,
                    ping_interval=None,  # KIS uses custom PINGPONG frames
                    ping_timeout=None,
                    open_timeout=15,
                    close_timeout=5,
                    max_size=2 ** 20,
                ) as ws:
                    self._ws = ws
                    self._active_on_socket.clear()
                    backoff = self.INITIAL_BACKOFF  # reset on success

                    # (Re)subscribe to everything the caller asked for
                    for code in list(self._subscribed):
                        await self._send_subscribe(code)

                    # Main receive loop
                    await self._receive_loop(ws)

            except asyncio.CancelledError:
                break
            except (ConnectionClosed, WebSocketException, InvalidStatusCode, OSError) as e:
                logger.warning("KIS WS connection lost: %s", e)
            except RuntimeError as e:
                # Phase 4-B (2026-05-17): graceful shutdown distinguishes from
                # actual error. SIGTERM 또는 atexit 시점에 ThreadPoolExecutor
                # 가 이미 shutdown되어 새 future schedule 불가 →
                # "cannot schedule new futures after interpreter shutdown" /
                # "Event loop is closed" 등. 이는 정상 종료 sequence 이므로
                # ERROR (log noise) 가 아니라 INFO + break.
                msg = str(e)
                if any(s in msg for s in (
                    "cannot schedule new futures",
                    "interpreter shutdown",
                    "Event loop is closed",
                )):
                    logger.info("KIS WS shutdown detected (%s) — exiting reconnect loop", msg)
                    break
                logger.error("KIS WS unexpected RuntimeError: %s", e)
            except Exception as e:
                logger.error("KIS WS unexpected error: %s", e)
            finally:
                self._ws = None
                self._active_on_socket.clear()

            if not self._running:
                break

            # Backoff before reconnect
            logger.info("KIS WS reconnecting in %.1fs", backoff)
            await self._sleep_or_stop(backoff)
            backoff = min(backoff * 2, self.MAX_BACKOFF)

    async def _sleep_or_stop(self, seconds: float):
        """Sleep but break out immediately if stop_event is set."""
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            logger.debug("silent-fallback: _run_loop", exc_info=True)
            pass

    async def _receive_loop(self, ws):
        async for msg in ws:
            if not self._running:
                break
            # KIS sends JSON for control messages, pipe-delimited for market data
            if isinstance(msg, bytes):
                try:
                    msg = msg.decode("utf-8", errors="ignore")
                except Exception:
                    logger.debug("silent-fallback: _run_loop", exc_info=True)
                    continue

            if not msg:
                continue

            first = msg[0]
            if first == "0" or first == "1":
                # Market data frame: "<encrypted>|<tr_id>|<count>|<body>"
                try:
                    self._handle_market_frame(msg)
                except Exception as e:
                    logger.debug("KIS WS parse error: %s", e)
            elif first == "{":
                # Control frame (subscribe ack, PINGPONG, errors)
                try:
                    obj = json.loads(msg)
                    await self._handle_control_frame(ws, obj)
                except Exception as e:
                    logger.debug("KIS WS ctrl parse error: %s", e)

    async def _handle_control_frame(self, ws, obj: dict):
        header = obj.get("header", {}) or {}
        body = obj.get("body", {}) or {}
        tr_id = header.get("tr_id")

        if tr_id == "PINGPONG":
            # Mirror back the same frame — keeps the connection alive.
            try:
                await ws.send(json.dumps(obj))
            except Exception:
                logger.debug("silent-fallback: Mirror back the same frame — keeps the connection alive. | _run_loop", exc_info=True)
                pass
            return

        rt_cd = body.get("rt_cd")
        msg_cd = body.get("msg_cd", "")
        msg1 = body.get("msg1", "")
        if rt_cd == "0":
            logger.debug("KIS WS ack tr_id=%s: %s", tr_id, msg1 or "OK")
        elif rt_cd is not None:
            # Phase 4-B (2026-05-17): repeated invalid-approval / already-in-use
            # 에러는 KIS 서버 측 상태로 매 재연결마다 동일 메시지 반복 (68회
            # 누적 confirmed in prod logs). 로그 노이즈 회피 + CEO 외부 액션
            # (KIS key rotate / billing 검증) 영역. 1분당 1회로 throttle.
            # Most common VTS failure: "해당 계좌는 실시간시세 이용이 불가합니다"
            now = time.time()
            recent = getattr(self, "_last_server_error_log", 0.0)
            if msg_cd in ("OPSP0011", "OPSP8996") and (now - recent) < 60:
                logger.debug(
                    "KIS WS server error throttled tr_id=%s code=%s msg=%s",
                    tr_id, msg_cd, msg1,
                )
            else:
                logger.warning(
                    "KIS WS server error tr_id=%s code=%s msg=%s",
                    tr_id, msg_cd, msg1,
                )
                self._last_server_error_log = now

    def _handle_market_frame(self, msg: str):
        """Parse a '0|<tr>|<count>|<body>' message and emit per-trade events."""
        parts = msg.split("|", 3)
        if len(parts) < 4:
            return
        _enc, tr_id, count_str, body = parts
        if tr_id != TR_CONTRACT:
            return

        try:
            count = int(count_str or "1")
        except ValueError:
            count = 1

        # Body contains `count` records, each with 46 pipe-delimited fields.
        fields = body.split("^")
        fields_per_record = max(1, len(fields) // max(count, 1))

        for i in range(count):
            start = i * fields_per_record
            rec = fields[start:start + fields_per_record]
            if len(rec) <= IDX_ACML_VOL:
                continue
            try:
                code = rec[IDX_CODE]
                price = int(rec[IDX_PRICE])
                if not price:
                    continue

                # Throttle per-ticker to max 2 updates/sec
                now = time.time()
                last = self._last_emit.get(code, 0.0)
                if now - last < self.THROTTLE_MIN_INTERVAL:
                    continue
                self._last_emit[code] = now

                change = int(rec[IDX_CHG] or 0)
                # Sign: 1=상한, 2=상승, 3=보합, 4=하한, 5=하락
                sign = rec[IDX_CHG_SIGN] or "3"
                if sign in ("4", "5") and change > 0:
                    change = -change
                try:
                    change_pct = float(rec[IDX_CHG_PCT])
                    if sign in ("4", "5") and change_pct > 0:
                        change_pct = -change_pct
                except ValueError:
                    change_pct = 0.0

                payload = {
                    "ticker": f"{code}.KS",
                    "price": price,
                    "price_display": f"₩{price:,}",
                    "open": int(rec[IDX_OPEN] or 0),
                    "high": int(rec[IDX_HIGH] or 0),
                    "low": int(rec[IDX_LOW] or 0),
                    "volume": int(rec[IDX_ACML_VOL] or 0),
                    "change": change,
                    "change_pct": change_pct,
                    "currency": "KRW",
                    "source": "kis_ws",
                    "timestamp": datetime.now().isoformat(),
                }

                if self.on_price:
                    try:
                        self.on_price(payload)
                    except Exception as e:
                        logger.debug("KIS WS callback error: %s", e)
            except (ValueError, IndexError) as e:
                logger.debug("KIS WS record parse skip: %s", e)

    # ── Subscribe / Unsubscribe frames ───────────────────────────────

    def _build_subscription_frame(self, code: str, tr_type: str) -> str:
        """tr_type='1' subscribe, '2' unsubscribe."""
        return json.dumps({
            "header": {
                "approval_key": self._approval_key or "",
                "custtype": "P",
                "tr_type": tr_type,
                "content-type": "utf-8",
            },
            "body": {
                "input": {
                    "tr_id": TR_CONTRACT,
                    "tr_key": code,
                }
            }
        })

    async def _send_subscribe(self, code: str):
        ws = self._ws
        if not ws:
            return
        if code in self._active_on_socket:
            return
        try:
            await ws.send(self._build_subscription_frame(code, "1"))
            self._active_on_socket.add(code)
            logger.info("KIS WS subscribed %s", code)
        except Exception as e:
            logger.warning("KIS WS subscribe %s failed: %s", code, e)

    async def _send_unsubscribe(self, code: str):
        ws = self._ws
        if not ws:
            return
        if code not in self._active_on_socket:
            return
        try:
            await ws.send(self._build_subscription_frame(code, "2"))
            self._active_on_socket.discard(code)
            logger.info("KIS WS unsubscribed %s", code)
        except Exception as e:
            logger.warning("KIS WS unsubscribe %s failed: %s", code, e)
