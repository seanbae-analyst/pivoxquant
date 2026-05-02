"""
PivoxQuant — KIS (Korea Investment & Securities) Service
Real-time Korean stock data via KIS Open API.
Supports: real-time price, intraday bars, momentum scanning.
"""

import os
import logging
import re
import requests
import time
import numpy as np
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# ── Sensitive-data masking (H3/H4, 2026-04-24) ─────────────────────────────
# JSON keys that may carry secrets if KIS echoes the request back on error.
_KIS_SENSITIVE_RE = re.compile(
    r'("(?:appkey|appsecret|app_key|app_secret|access_token|approval_key|'
    r'authorization|CANO|ACNT_PRDT_CD|ACNT_NO|account_no|token|secret)"\s*:\s*")'
    r'([^"]*)(")',
    re.IGNORECASE,
)
_KIS_BARE_ACCOUNT_RE = re.compile(r"\b(\d{6,20})\b")


def _kis_mask_token(val: str) -> str:
    if not val:
        return "***"
    if len(val) <= 6:
        return "***"
    return f"{val[:4]}***{val[-2:]}"


def _kis_redact_snippet(text: str, max_len: int = 200) -> str:
    """Redact secrets from a raw HTTP response body before logging."""
    if not text:
        return ""
    redacted = _KIS_SENSITIVE_RE.sub(
        lambda m: f'{m.group(1)}{_kis_mask_token(m.group(2))}{m.group(3)}',
        text,
    )
    redacted = _KIS_BARE_ACCOUNT_RE.sub(lambda m: _kis_mask_token(m.group(1)), redacted)
    return redacted[:max_len]


def _kis_mask_account(account_no: str) -> str:
    """Mask a KIS 계좌번호 for logs: show only last 4 digits."""
    if not account_no:
        return "***"
    s = str(account_no)
    if len(s) <= 4:
        return "***"
    return f"***{s[-4:]}"

_USE_REAL = os.environ.get("KIS_USE_REAL", "").strip() in ("1", "true", "True")
BASE_URL = "https://openapi.koreainvestment.com:9443" if _USE_REAL else "https://openapivts.koreainvestment.com:29443"

# Popular Korean stocks for day trade scanning
KR_DAY_TRADE_POOL = [
    "005930",  # Samsung Electronics
    "000660",  # SK Hynix
    "035420",  # NAVER
    "035720",  # Kakao
    "005380",  # Hyundai Motor
    "000270",  # Kia
    "207940",  # Samsung Biologics
    "006400",  # Samsung SDI
    "051910",  # LG Chem
    "066570",  # LG Electronics
    "373220",  # LG Energy Solution
    "068270",  # Celltrion
    "096770",  # SK Innovation
    "047050",  # Krafton
    "352820",  # HYBE
    "003670",  # POSCO Future M
    "055550",  # Shinhan Financial
    "105560",  # KB Financial
    "017670",  # SK Telecom
    "030200",  # KT Corp
]

STOCK_NAMES = {
    "005930": "삼성전자", "000660": "SK하이닉스", "035420": "NAVER",
    "035720": "카카오", "005380": "현대차", "000270": "기아",
    "207940": "삼성바이오로직스", "006400": "삼성SDI", "051910": "LG화학",
    "066570": "LG전자", "373220": "LG에너지솔루션", "068270": "셀트리온",
    "096770": "SK이노베이션", "047050": "크래프톤", "352820": "하이브",
    "003670": "포스코퓨처엠", "055550": "신한지주", "105560": "KB금융",
    "017670": "SK텔레콤", "030200": "KT",
}


class KISService:

    def __init__(self):
        self.available = False
        self.app_key = os.environ.get("KIS_APP_KEY", "").strip()
        self.app_secret = os.environ.get("KIS_APP_SECRET", "").strip()
        self.base_url = BASE_URL
        self.access_token = None
        self.token_expires = None

        # 계좌번호: 앞 8자리 + 상품코드 뒤 2자리 (trading API에 필요)
        # .env에 KIS_ACCOUNT_NO, KIS_ACCOUNT_PROD 설정 필요
        self.account_no = os.environ.get("KIS_ACCOUNT_NO", "").strip()
        self.account_prod = os.environ.get("KIS_ACCOUNT_PROD", "01").strip()

        if self.app_key and self.app_secret:
            self.available = True
            logger.info("KIS Service initialized (Korea Investment)")
            if not self.account_no:
                logger.warning("KIS_ACCOUNT_NO not set — balance/order APIs will not work")

    _TOKEN_CACHE_FILE = os.path.join(os.path.dirname(__file__), ".kis_token_cache.json")

    def _get_token(self):
        """Delegate to the process-wide KISTokenManager.

        Previously this class issued its own tokens, which competed with
        RealtimeService and data_fetcher for the 1-token-per-minute
        quota (`EGW00133`). Routing everything through the singleton
        collapses those competing calls into one.
        """
        try:
            from kis_token_manager import get_kis_token_manager
            token = get_kis_token_manager().get_token()
            # Mirror into self for legacy callers that peek at attributes.
            if token:
                self.access_token = token
            return token
        except Exception as e:
            logger.warning(f"KIS token manager error: {e}")
            return None

    def _headers(self):
        token = self._get_token()
        if not token:
            return None
        return {
            "Content-Type": "application/json; charset=utf-8",
            "authorization": f"Bearer {token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret,
        }

    def get_current_price(self, stock_code):
        """Get real-time current price for a Korean stock."""
        if not self.available:
            return None
        headers = self._headers()
        if not headers:
            return None

        try:
            headers["tr_id"] = "FHKST01010100"
            params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": stock_code}
            r = requests.get(
                f"{BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price",
                headers=headers, params=params, timeout=10
            )
            if r.ok:
                output = r.json().get("output", {})
                return {
                    "stock_code": stock_code,
                    "name": STOCK_NAMES.get(stock_code, stock_code),
                    "price": int(output.get("stck_prpr", 0)),
                    "change": int(output.get("prdy_vrss", 0)),
                    "change_pct": float(output.get("prdy_ctrt", 0)),
                    "volume": int(output.get("acml_vol", 0)),
                    "high": int(output.get("stck_hgpr", 0)),
                    "low": int(output.get("stck_lwpr", 0)),
                    "open": int(output.get("stck_oprc", 0)),
                    "prev_close": int(output.get("stck_sdpr", 0)),
                    "market_cap": int(output.get("hts_avls", 0)) * 100000000,
                    "timestamp": datetime.now().isoformat(),
                }
            elif r.status_code == 500 and "초당" in r.text:
                time.sleep(1.0)
                r2 = requests.get(
                    f"{BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price",
                    headers=headers, params=params, timeout=10
                )
                if r2.ok:
                    output = r2.json().get("output", {})
                    return {
                        "stock_code": stock_code,
                        "name": STOCK_NAMES.get(stock_code, stock_code),
                        "price": int(output.get("stck_prpr", 0)),
                        "change": int(output.get("prdy_vrss", 0)),
                        "change_pct": float(output.get("prdy_ctrt", 0)),
                        "volume": int(output.get("acml_vol", 0)),
                        "high": int(output.get("stck_hgpr", 0)),
                        "low": int(output.get("stck_lwpr", 0)),
                        "open": int(output.get("stck_oprc", 0)),
                        "prev_close": int(output.get("stck_sdpr", 0)),
                        "market_cap": int(output.get("hts_avls", 0)) * 100000000,
                        "timestamp": datetime.now().isoformat(),
                    }
            return None
        except Exception:
            logger.debug("silent-fallback: get_current_price", exc_info=True)
            return None

    def get_index_price(self, index_code: str):
        """Get current price for KR market index.
        index_code: '0001' = KOSPI, '1001' = KOSDAQ, '2001' = KOSPI200.

        KIS API: /uapi/domestic-stock/v1/quotations/inquire-index-price
        tr_id: FHPUP02100000

        Note: This endpoint requires production-grade access. Mock (VTS) endpoint
        may not serve index data — we try production URL directly.

        Returns: dict with price/change_pct or None.
        """
        if not self.available:
            return None
        token = self._get_token()
        if not token:
            return None
        try:
            headers = {
                "Content-Type": "application/json; charset=utf-8",
                "authorization": f"Bearer {token}",
                "appkey": self.app_key,
                "appsecret": self.app_secret,
                "tr_id": "FHPUP02100000",
            }
            params = {
                "FID_COND_MRKT_DIV_CODE": "U",
                "FID_INPUT_ISCD": index_code,
            }
            # Try production URL first (index data usually only on real endpoint)
            for base in ("https://openapi.koreainvestment.com:9443", self.base_url):
                r = requests.get(
                    f"{base}/uapi/domestic-stock/v1/quotations/inquire-index-price",
                    headers=headers, params=params, timeout=10,
                )
                if r.ok:
                    data = r.json()
                    if data.get("rt_cd") == "0":
                        o = data.get("output", {})
                        price = float(o.get("bstp_nmix_prpr", 0))
                        change_pct = float(o.get("bstp_nmix_prdy_ctrt", 0))
                        if price > 0:
                            return {
                                "index_code": index_code,
                                "price": price,
                                "change": float(o.get("bstp_nmix_prdy_vrss", 0)),
                                "change_pct": change_pct,
                                "volume": int(float(o.get("acml_vol", 0))),
                            }
            return None
        except Exception as e:
            logger.debug(f"KIS index price {index_code} failed: {e}")
            return None

    def get_index_history(self, index_code: str, period: str = "1y"):
        """Get daily chart history for a KR market index.

        Uses KIS `inquire-index-daily-price` (tr_id FHPUP02120000). Accepts
        the same index codes as :meth:`get_index_price` (``0001`` KOSPI,
        ``1001`` KOSDAQ, ``2001`` KOSPI200, ``2203`` KOSDAQ150). Mirrors
        :meth:`get_index_price`'s production-URL-first behaviour — the VTS
        (paper) endpoint does not serve index data.

        Returns a list of ``{date, open, high, low, close, volume}`` dicts
        ordered oldest→newest, or ``None`` on any failure. The caller is
        expected to downsample via ``.tail(N)``; we do not truncate here.
        """
        if not self.available:
            return None
        token = self._get_token()
        if not token:
            return None

        # Period → number of calendar days to request. KIS returns up to
        # ~100 rows per call so "1y" maps to ~252 trading days but the
        # endpoint will only return what it has.
        period_map = {
            "1mo": 30, "3mo": 90, "6mo": 180,
            "1y": 365, "2y": 730, "5y": 1825,
            "5d": 10, "1d": 5,
        }
        days = period_map.get(period, 365)
        end = datetime.now()
        start = end - timedelta(days=days)

        try:
            headers = {
                "Content-Type": "application/json; charset=utf-8",
                "authorization": f"Bearer {token}",
                "appkey": self.app_key,
                "appsecret": self.app_secret,
                "tr_id": "FHPUP02120000",
            }
            params = {
                "FID_COND_MRKT_DIV_CODE": "U",
                "FID_INPUT_ISCD": index_code,
                "FID_INPUT_DATE_1": start.strftime("%Y%m%d"),
                "FID_INPUT_DATE_2": end.strftime("%Y%m%d"),
                "FID_PERIOD_DIV_CODE": "D",  # D=day, W=week, M=month
            }
            for base in ("https://openapi.koreainvestment.com:9443", self.base_url):
                try:
                    r = requests.get(
                        f"{base}/uapi/domestic-stock/v1/quotations/inquire-index-daily-price",
                        headers=headers, params=params, timeout=10,
                    )
                except Exception:
                    logger.debug("silent-fallback: get_index_history", exc_info=True)
                    continue
                if not r.ok:
                    continue
                data = r.json()
                if data.get("rt_cd") != "0":
                    continue
                rows = data.get("output2") or data.get("output") or []
                if not isinstance(rows, list) or not rows:
                    continue
                parsed = []
                for row in rows:
                    close = row.get("bstp_nmix_prpr") or row.get("stck_bsop_date_cls_prc")
                    if close is None:
                        continue
                    try:
                        close = float(close)
                    except (TypeError, ValueError):
                        logger.debug("silent-fallback: get_index_history", exc_info=True)
                        continue
                    if close <= 0:
                        continue
                    date_s = row.get("stck_bsop_date") or row.get("bstp_nmix_bsop_date") or ""
                    parsed.append({
                        "date":   date_s,
                        "open":   float(row.get("bstp_nmix_oprc") or close),
                        "high":   float(row.get("bstp_nmix_hgpr") or close),
                        "low":    float(row.get("bstp_nmix_lwpr") or close),
                        "close":  close,
                        "volume": int(float(row.get("acml_vol") or 0)),
                    })
                if not parsed:
                    continue
                # KIS returns newest-first → reverse to oldest-first.
                parsed.sort(key=lambda x: x.get("date") or "")
                return parsed
            return None
        except Exception as e:
            logger.debug(f"KIS index history {index_code} failed: {e}")
            return None

    def get_intraday_bars(self, stock_code, timeframe="1"):
        """Get intraday minute bars."""
        if not self.available:
            return []
        headers = self._headers()
        if not headers:
            return []
        try:
            headers["tr_id"] = "FHKST03010200"
            params = {
                "FID_ETC_CLS_CODE": "",
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": stock_code,
                "FID_INPUT_HOUR_1": datetime.now().strftime("%H%M%S"),
                "FID_PW_DATA_INCU_YN": "Y",
            }
            r = requests.get(
                f"{BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice",
                headers=headers, params=params, timeout=10
            )
            if r.ok:
                bars = []
                for item in r.json().get("output2", []):
                    bars.append({
                        "time": item.get("stck_cntg_hour", ""),
                        "open": int(item.get("stck_oprc", 0)),
                        "high": int(item.get("stck_hgpr", 0)),
                        "low": int(item.get("stck_lwpr", 0)),
                        "close": int(item.get("stck_prpr", 0)),
                        "volume": int(item.get("cntg_vol", 0)),
                    })
                bars.reverse()
                return bars
            return []
        except Exception:
            return []

    def get_all_prices(self):
        results = {}
        for code in KR_DAY_TRADE_POOL:
            price = self.get_current_price(code)
            if price:
                results[code] = price
            time.sleep(0.55)
        return results

    # ── Account / Trading APIs (모의투자) ────────────────────────

    def get_balance(self):
        """한투 계좌 잔고 조회 (예수금 + 보유종목).

        KIS API: GET /uapi/domestic-stock/v1/trading/inquire-balance
        tr_id: VTTC8434R (모의투자)
        """
        if not self.available:
            return {"error": "KIS not configured"}
        if not self.account_no:
            return {"error": "KIS_ACCOUNT_NO not set"}

        try:
            headers = self._headers()
            if not headers:
                return {"error": "KIS token unavailable"}
            headers["tr_id"] = "VTTC8434R"  # 모의투자 잔고조회

            params = {
                "CANO": self.account_no,
                "ACNT_PRDT_CD": self.account_prod,
                "AFHR_FLPR_YN": "N",
                "OFL_YN": "",
                "INQR_DVSN": "02",
                "UNPR_DVSN": "01",
                "FUND_STTL_ICLD_YN": "N",
                "FNCG_AMT_AUTO_RDPT_YN": "N",
                "PRCS_DVSN": "01",
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": "",
            }

            resp = requests.get(
                f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-balance",
                headers=headers, params=params, timeout=10,
            )
            if not resp.ok:
                # H3/H4: redact any echoed appkey/appsecret/CANO before logging.
                logger.warning(
                    "KIS get_balance HTTP %s (account=%s): %s",
                    resp.status_code,
                    _kis_mask_account(self.account_no),
                    _kis_redact_snippet(resp.text, max_len=200),
                )
                return {"error": f"KIS API error ({resp.status_code})"}

            data = resp.json()
            if data.get("rt_cd") != "0":
                return {"error": data.get("msg1", "Unknown KIS error")}

            positions = []
            for item in data.get("output1", []):
                qty = int(item.get("hldg_qty", 0))
                if qty > 0:
                    positions.append({
                        "ticker": item.get("pdno", ""),
                        "name": item.get("prdt_name", ""),
                        "shares": qty,
                        "avg_cost": float(item.get("pchs_avg_pric", 0)),
                        "current_price": float(item.get("prpr", 0)),
                        "pnl": float(item.get("evlu_pfls_amt", 0)),
                        "pnl_pct": float(item.get("evlu_pfls_rt", 0)),
                        "currency": "KRW",
                    })

            output2 = data.get("output2", [{}])
            if isinstance(output2, list) and output2:
                balance_info = output2[0]
            else:
                balance_info = output2 or {}

            return {
                "available_cash": float(balance_info.get("dnca_tot_amt", 0)),
                "total_value": float(balance_info.get("tot_evlu_amt", 0)),
                "positions": positions,
            }
        except Exception as e:
            # H4: redact any CANO / appkey that may appear in the exception
            # string (e.g. requests.HTTPError echoes the URL with query params).
            safe_err = _kis_redact_snippet(str(e), max_len=200)
            logger.error(
                "KIS get_balance error (account=%s): %s",
                _kis_mask_account(self.account_no),
                safe_err,
            )
            return {"error": "KIS balance lookup failed"}

    def buy_order(self, ticker: str, quantity: int, price: int = 0, order_type: str = "00"):
        """DISABLED -- KIS order execution is read-only for legal compliance.

        한투 주문 실행은 투자일임업(자본시장법) 규제로 영구 비활성화됨.
        DO NOT re-enable without a licensed broker integration — violating this
        would expose the service operator to 자본시장법 위반 (criminal penalty).
        Users must execute trades directly in the KIS app.
        """
        return {
            "ok": False,
            "error": "KIS order execution is disabled. Please use the KIS app to place orders.",
            "code": "KIS_READ_ONLY",
        }

    def sell_order(self, ticker: str, quantity: int, price: int = 0, order_type: str = "00"):
        """DISABLED -- KIS order execution is read-only for legal compliance.

        한투 주문 실행은 투자일임업(자본시장법) 규제로 영구 비활성화됨.
        DO NOT re-enable without a licensed broker integration — violating this
        would expose the service operator to 자본시장법 위반 (criminal penalty).
        Users must execute trades directly in the KIS app.
        """
        return {
            "ok": False,
            "error": "KIS order execution is disabled. Please use the KIS app to place orders.",
            "code": "KIS_READ_ONLY",
        }

    def _place_order(self, ticker: str, quantity: int, price: int, order_type: str, side: str):
        """DISABLED -- order execution removed for legal compliance (자본시장법).

        KIS order execution is permanently disabled. The prior inline commented
        implementation was removed (2026-04-24, H5) to eliminate the risk of
        accidental re-enablement by a future edit. If orders are ever required,
        they must go through a dedicated licensed broker integration — NOT by
        re-introducing code here.
        """
        return {
            "ok": False,
            "error": "KIS order execution is disabled. Please use the KIS app to place orders.",
            "code": "KIS_READ_ONLY",
        }

    def get_order_status(self, start_date: str = None, end_date: str = None):
        """주문 체결 내역 조회.

        KIS API: GET /uapi/domestic-stock/v1/trading/inquire-daily-ccld
        tr_id: VTTC8001R (모의투자)

        Args:
            start_date: 조회 시작일 (YYYYMMDD). 기본값: 오늘.
            end_date: 조회 종료일 (YYYYMMDD). 기본값: 오늘.

        Returns:
            dict with "ok" and "orders" list.
        """
        if not self.available:
            return {"ok": False, "orders": [], "error": "KIS not configured"}
        if not self.account_no:
            return {"ok": False, "orders": [], "error": "KIS_ACCOUNT_NO not set"}

        today = datetime.now().strftime("%Y%m%d")
        if not start_date:
            start_date = today
        if not end_date:
            end_date = today

        try:
            headers = self._headers()
            if not headers:
                return {"ok": False, "orders": [], "error": "KIS token unavailable"}
            headers["tr_id"] = "VTTC8001R"  # 모의투자 일별체결조회

            params = {
                "CANO": self.account_no,
                "ACNT_PRDT_CD": self.account_prod,
                "INQR_STRT_DT": start_date,
                "INQR_END_DT": end_date,
                "SLL_BUY_DVSN_CD": "00",  # 전체 (매수+매도)
                "INQR_DVSN": "00",        # 역순
                "PDNO": "",               # 전종목
                "CCLD_DVSN": "00",        # 전체 (체결+미체결)
                "ORD_GNO_BRNO": "",
                "ODNO": "",
                "INQR_DVSN_3": "00",
                "INQR_DVSN_1": "",
                "CTX_AREA_FK100": "",
                "CTX_AREA_NK100": "",
            }

            resp = requests.get(
                f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-daily-ccld",
                headers=headers, params=params, timeout=10,
            )
            if not resp.ok:
                logger.warning(f"KIS get_order_status HTTP {resp.status_code}")
                return {"ok": False, "orders": [], "error": f"HTTP {resp.status_code}"}

            data = resp.json()
            if data.get("rt_cd") != "0":
                return {"ok": False, "orders": [], "error": data.get("msg1", "Unknown error")}

            orders = []
            for item in data.get("output1", []):
                orders.append({
                    "order_no": item.get("odno", ""),
                    "ticker": item.get("pdno", ""),
                    "name": item.get("prdt_name", ""),
                    "side": "buy" if item.get("sll_buy_dvsn_cd") == "02" else "sell",
                    "order_type": "limit" if item.get("ord_dvsn_cd") == "00" else "market",
                    "order_qty": int(item.get("ord_qty", 0)),
                    "filled_qty": int(item.get("tot_ccld_qty", 0)),
                    "order_price": float(item.get("ord_unpr", 0)),
                    "filled_price": float(item.get("avg_prvs", 0)),
                    "status": "filled" if int(item.get("tot_ccld_qty", 0)) > 0 else "pending",
                    "order_time": item.get("ord_tmd", ""),
                    "order_date": item.get("ord_dt", ""),
                })

            return {"ok": True, "orders": orders}
        except Exception as e:
            # H4: redact CANO/appkey from exception string before logging.
            safe_err = _kis_redact_snippet(str(e), max_len=200)
            logger.error(
                "KIS get_order_status error (account=%s): %s",
                _kis_mask_account(self.account_no),
                safe_err,
            )
            return {"ok": False, "orders": [], "error": "KIS order lookup failed"}

    @staticmethod
    def _sig(typ, en, kr):
        """Create bilingual signal dict."""
        return {"type": typ, "msg": en, "msg_kr": kr}

    def scan_momentum(self, held_tickers=None):
        """
        Full signal scan for Korean stocks.
        - Held stocks: EXIT signals (sell/hold timing)
        - New stocks: ENTRY signals (buy timing)
        """
        held_tickers = set(held_tickers or [])
        results = []
        S = self._sig  # shorthand

        for code in KR_DAY_TRADE_POOL:
            try:
                price_data = self.get_current_price(code)
                if not price_data or price_data["price"] == 0:
                    continue

                bars = self.get_intraday_bars(code)
                time.sleep(0.55)

                score = 50.0
                signals = []
                is_held = code in held_tickers
                price = price_data["price"]
                chg = price_data["change_pct"]
                high = price_data.get("high", 0)
                low = price_data.get("low", 0)
                opn = price_data.get("open", 0)
                volume = price_data.get("volume", 0)

                # ── 1. Price momentum ─────────────────────────
                if chg > 5:
                    score += 20
                    signals.append(S("bullish", f"Surging +{chg:.1f}%", f"급등 +{chg:.1f}%"))
                elif chg > 3:
                    score += 15
                    signals.append(S("bullish", f"Strong rally +{chg:.1f}%", f"강한 상승 +{chg:.1f}%"))
                elif chg > 1:
                    score += 8
                    signals.append(S("bullish", f"Up +{chg:.1f}%", f"상승 +{chg:.1f}%"))
                elif chg < -5:
                    score -= 20
                    signals.append(S("bearish", f"Crashing {chg:.1f}%", f"급락 {chg:.1f}%"))
                elif chg < -3:
                    score -= 15
                    signals.append(S("bearish", f"Sharp drop {chg:.1f}%", f"강한 하락 {chg:.1f}%"))
                elif chg < -1:
                    score -= 8
                    signals.append(S("bearish", f"Down {chg:.1f}%", f"하락 {chg:.1f}%"))

                # ── 2. Intraday position ──────────────────────
                if high > low > 0:
                    day_range = high - low
                    pos_in_range = (price - low) / day_range
                    if pos_in_range > 0.85:
                        signals.append(S("bearish", f"Near intraday high ({pos_in_range*100:.0f}%)", f"장중 고점 근접 ({pos_in_range*100:.0f}%)"))
                        score -= 5
                    elif pos_in_range < 0.15:
                        signals.append(S("bullish", f"Near intraday low ({pos_in_range*100:.0f}%)", f"장중 저점 근접 ({pos_in_range*100:.0f}%)"))
                        score += 5

                rsi = None
                vol_ratio = None

                if bars and len(bars) > 5:
                    closes = [b["close"] for b in bars if b["close"] > 0]
                    volumes = [b["volume"] for b in bars if b["volume"] > 0]

                    # ── 3. RSI ─────────────────────────────────
                    if len(closes) >= 14:
                        rsi = self._calc_rsi(np.array(closes), 14)
                        if rsi is not None:
                            if rsi < 25:
                                score += 18
                                signals.append(S("bullish", f"RSI extreme oversold ({rsi:.0f}) — bounce imminent", f"RSI 극과매도 ({rsi:.0f}) — 반등 임박"))
                            elif rsi < 35:
                                score += 12
                                signals.append(S("bullish", f"RSI oversold ({rsi:.0f})", f"RSI 과매도 ({rsi:.0f})"))
                            elif rsi > 80:
                                score -= 18
                                signals.append(S("bearish", f"RSI extreme overbought ({rsi:.0f}) — pullback likely", f"RSI 극과매수 ({rsi:.0f}) — 하락 주의"))
                            elif rsi > 70:
                                score -= 12
                                signals.append(S("bearish", f"RSI overbought ({rsi:.0f})", f"RSI 과매수 ({rsi:.0f})"))

                    # ── 4. Volume ──────────────────────────────
                    if len(volumes) > 3:
                        avg_vol = np.mean(volumes[:-1])
                        cur_vol = volumes[-1] if volumes else 0
                        if avg_vol > 0:
                            vol_ratio = round(cur_vol / avg_vol, 1)
                            if vol_ratio >= 5:
                                score += 15
                                signals.append(S("bullish", f"Volume explosion {vol_ratio}x — institutional flow", f"거래량 폭발 {vol_ratio}배 — 세력 유입"))
                            elif vol_ratio >= 3:
                                score += 10
                                signals.append(S("bullish", f"Volume surge {vol_ratio}x avg", f"거래량 급증 {vol_ratio}배"))
                            elif vol_ratio < 0.3:
                                signals.append(S("neutral", "Volume dried up — wait for confirmation", "거래량 실종 — 관망"))

                    # ── 5. MA crossover ────────────────────────
                    if len(closes) >= 20:
                        ma5 = np.mean(closes[-5:])
                        ma20 = np.mean(closes[-20:])
                        if ma5 > ma20 and closes[-1] > ma5:
                            score += 8
                            signals.append(S("bullish", "Short MA > Long MA — uptrend confirmed", "단기MA > 중기MA — 상승 추세"))
                        elif ma5 < ma20 and closes[-1] < ma5:
                            score -= 8
                            signals.append(S("bearish", "Short MA < Long MA — downtrend", "단기MA < 중기MA — 하락 추세"))

                    # ── 6. Recent 5-bar momentum ───────────────
                    if len(closes) >= 6:
                        recent_chg = (closes[-1] - closes[-5]) / closes[-5] * 100
                        if recent_chg > 1.5:
                            signals.append(S("bullish", f"Last 5 bars rising +{recent_chg:.1f}%", f"직전 5봉 상승 +{recent_chg:.1f}%"))
                        elif recent_chg < -1.5:
                            signals.append(S("bearish", f"Last 5 bars falling {recent_chg:.1f}%", f"직전 5봉 하락 {recent_chg:.1f}%"))

                # ── 7. Gap analysis ────────────────────────────
                if opn > 0:
                    gap = (price - opn) / opn * 100
                    if gap > 3:
                        signals.append(S("bullish", f"Gap up +{gap:.1f}% — bullish open", f"갭 상승 +{gap:.1f}% — 강세"))
                    elif gap < -3:
                        signals.append(S("bearish", f"Gap down {gap:.1f}%", f"갭 하락 {gap:.1f}%"))

                score = max(0, min(100, score))

                # ── Signal: held vs new ────────────────────────
                if is_held:
                    if score < 30 or (rsi and rsi > 80):
                        signal = "NEGATIVE"
                        en = "EXIT — Take profit now" if chg > 0 else "EXIT — Cut losses"
                        kr = "청산 — 익절 타이밍" if chg > 0 else "청산 — 손절 필요"
                    elif score < 45:
                        signal = "NEGATIVE"
                        en = "PARTIAL EXIT — Sell half, hold rest"
                        kr = "일부 청산 — 절반 정리 후 관망"
                    elif score >= 65:
                        signal = "NEUTRAL"
                        en = "NEUTRAL — Trend intact, let it ride"
                        kr = "홀딩 — 추세 유지, 더 갈 수 있음"
                    else:
                        signal = "NEUTRAL"
                        en = "WATCH — Momentum fading, stay alert"
                        kr = "관망 — 추세 약화, 주시 필요"
                    signals.insert(0, S("neutral", en, kr))
                else:
                    if score >= 72:
                        signal = "ENTRY"
                        en = "ENTRY — Strong momentum, buy now"
                        kr = "진입 — 강한 모멘텀, 매수 타이밍"
                    elif score >= 62:
                        signal = "WATCH"
                        en = "WATCH — Setting up, confirm volume before entry"
                        kr = "주시 — 조건 충족 중, 거래량 확인 후 진입"
                    elif score < 30:
                        signal = "AVOID"
                        en = "AVOID — Bearish momentum, stay out"
                        kr = "회피 — 하락 모멘텀, 진입 ��지"
                    else:
                        signal = "WAIT"
                        en = "WAIT — No clear setup yet"
                        kr = "대기 — 진입 조건 미달"
                    signals.insert(0, S("neutral", en, kr))

                results.append({
                    "ticker": code,
                    "name": price_data["name"],
                    "price": price,
                    "change_pct": chg,
                    "volume": volume,
                    "score": round(score, 1),
                    "signal": signal,
                    "signals": signals,
                    "currency": "KRW",
                    "is_korean": True,
                    "is_held": is_held,
                    "rsi": round(rsi, 1) if rsi else None,
                    "vol_ratio": vol_ratio,
                })

            except Exception as e:
                logger.debug(f"KIS scan skip {code}: {e}")

        # Held stocks first, then by score
        results.sort(key=lambda x: (-int(x.get("is_held", False)), -x.get("score", 0)))
        return results

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
