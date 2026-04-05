"""
StockPilot — KIS (Korea Investment & Securities) Service
Real-time Korean stock data via KIS Open API.
Supports: real-time price, intraday bars, order execution (future).
"""

import os
import json
import logging
import requests
import time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

BASE_URL = "https://openapivts.koreainvestment.com:29443"  # 모의투자
# BASE_URL_REAL = "https://openapi.koreainvestment.com:9443"  # 실전투자

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
        self.access_token = None
        self.token_expires = None

        if self.app_key and self.app_secret:
            self.available = True
            logger.info("KIS Service initialized (Korea Investment)")

    def _get_token(self):
        """Get or refresh OAuth access token."""
        if self.access_token and self.token_expires and datetime.now() < self.token_expires:
            return self.access_token

        try:
            url = f"{BASE_URL}/oauth2/tokenP"
            body = {
                "grant_type": "client_credentials",
                "appkey": self.app_key,
                "appsecret": self.app_secret,
            }
            r = requests.post(url, json=body, timeout=10)
            if r.ok:
                data = r.json()
                self.access_token = data.get("access_token")
                expires_in = int(data.get("expires_in", 86400))
                self.token_expires = datetime.now() + timedelta(seconds=expires_in - 60)
                logger.info("KIS token refreshed")
                return self.access_token
            else:
                logger.error(f"KIS token failed: {r.status_code} {r.text}")
                return None
        except Exception as e:
            logger.error(f"KIS token error: {e}")
            return None

    def _headers(self):
        """Build request headers with auth token."""
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
            headers["tr_id"] = "FHKST01010100"  # 주식현재가 시세
            params = {
                "FID_COND_MRKT_DIV_CODE": "J",  # 주식
                "FID_INPUT_ISCD": stock_code,
            }
            r = requests.get(
                f"{BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price",
                headers=headers, params=params, timeout=10
            )
            if r.ok:
                data = r.json()
                output = data.get("output", {})
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
                    "market_cap": int(output.get("hts_avls", 0)) * 100000000,  # 억 단위
                    "timestamp": datetime.now().isoformat(),
                }
            else:
                logger.error(f"KIS price error: {r.status_code} {r.text[:200]}")
                return None
        except Exception as e:
            logger.error(f"KIS price error {stock_code}: {e}")
            return None

    def get_intraday_bars(self, stock_code, timeframe="1"):
        """Get intraday minute bars. timeframe: '1' or '5' (minutes)."""
        if not self.available:
            return []
        headers = self._headers()
        if not headers:
            return []

        try:
            headers["tr_id"] = "FHKST03010200"  # 주식현재가 분봉조회
            now = datetime.now()
            params = {
                "FID_ETC_CLS_CODE": "",
                "FID_COND_MRKT_DIV_CODE": "J",
                "FID_INPUT_ISCD": stock_code,
                "FID_INPUT_HOUR_1": now.strftime("%H%M%S"),
                "FID_PW_DATA_INCU_YN": "Y",
            }
            r = requests.get(
                f"{BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice",
                headers=headers, params=params, timeout=10
            )
            if r.ok:
                data = r.json()
                bars = []
                for item in data.get("output2", []):
                    bars.append({
                        "time": item.get("stck_cntg_hour", ""),
                        "open": int(item.get("stck_oprc", 0)),
                        "high": int(item.get("stck_hgpr", 0)),
                        "low": int(item.get("stck_lwpr", 0)),
                        "close": int(item.get("stck_prpr", 0)),
                        "volume": int(item.get("cntg_vol", 0)),
                    })
                bars.reverse()  # oldest first
                return bars
            return []
        except Exception as e:
            logger.error(f"KIS intraday error {stock_code}: {e}")
            return []

    def get_all_prices(self):
        """Get current prices for all KR day trade pool stocks."""
        results = {}
        for code in KR_DAY_TRADE_POOL:
            price = self.get_current_price(code)
            if price:
                results[code] = price
            time.sleep(0.1)  # Rate limit: 초당 10건
        return results

    def scan_momentum(self):
        """Scan Korean stocks for momentum signals."""
        import numpy as np
        results = []
        for code in KR_DAY_TRADE_POOL:
            try:
                price_data = self.get_current_price(code)
                if not price_data or price_data["price"] == 0:
                    continue

                bars = self.get_intraday_bars(code)

                score = 50.0
                signals = []

                # Price change momentum
                chg = price_data["change_pct"]
                if chg > 3:
                    score += 15
                    signals.append({"type": "bullish", "msg": f"Strong up +{chg:.1f}%", "msg_kr": f"강한 상승 +{chg:.1f}%"})
                elif chg > 1:
                    score += 8
                    signals.append({"type": "bullish", "msg": f"Up +{chg:.1f}%", "msg_kr": f"상승 +{chg:.1f}%"})
                elif chg < -3:
                    score -= 15
                    signals.append({"type": "bearish", "msg": f"Strong down {chg:.1f}%", "msg_kr": f"강한 하락 {chg:.1f}%"})
                elif chg < -1:
                    score -= 8
                    signals.append({"type": "bearish", "msg": f"Down {chg:.1f}%", "msg_kr": f"하락 {chg:.1f}%"})

                # Volume analysis
                if bars and len(bars) > 5:
                    closes = [b["close"] for b in bars if b["close"] > 0]
                    volumes = [b["volume"] for b in bars if b["volume"] > 0]

                    if len(closes) >= 14:
                        rsi = self._calc_rsi(np.array(closes), 14)
                        if rsi is not None:
                            if rsi < 30:
                                score += 15
                                signals.append({"type": "bullish", "msg": f"RSI oversold ({rsi:.0f})", "msg_kr": f"RSI 과매도 ({rsi:.0f})"})
                            elif rsi > 70:
                                score -= 15
                                signals.append({"type": "bearish", "msg": f"RSI overbought ({rsi:.0f})", "msg_kr": f"RSI 과매수 ({rsi:.0f})"})

                    if len(volumes) > 1:
                        avg_vol = np.mean(volumes[:-1])
                        cur_vol = volumes[-1]
                        if avg_vol > 0 and cur_vol >= avg_vol * 3:
                            score += 10
                            signals.append({"type": "bullish", "msg": f"Volume spike {cur_vol/avg_vol:.1f}x", "msg_kr": f"거래량 급증 {cur_vol/avg_vol:.1f}배"})

                score = max(0, min(100, score))
                signal = "BUY" if score >= 65 else "SELL" if score < 30 else "HOLD"

                results.append({
                    "ticker": code,
                    "name": price_data["name"],
                    "price": price_data["price"],
                    "change_pct": price_data["change_pct"],
                    "volume": price_data["volume"],
                    "score": round(score, 1),
                    "signal": signal,
                    "signals": signals,
                    "currency": "KRW",
                    "is_korean": True,
                })
                time.sleep(0.1)
            except Exception as e:
                logger.error(f"KIS scan error {code}: {e}")

        results.sort(key=lambda x: -abs(x.get("change_pct", 0)))
        return results

    @staticmethod
    def _calc_rsi(prices, period=14):
        if len(prices) < period + 1:
            return None
        import numpy as np
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return float(100 - 100 / (1 + rs))
