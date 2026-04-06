"""
StockPilot — KIS (Korea Investment & Securities) Service
Real-time Korean stock data via KIS Open API.
Supports: real-time price, intraday bars, momentum scanning.
"""

import os
import json
import logging
import requests
import time
import numpy as np
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

BASE_URL = "https://openapivts.koreainvestment.com:29443"  # 모의투자

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

    _TOKEN_CACHE_FILE = os.path.join(os.path.dirname(__file__), ".kis_token_cache.json")

    def _get_token(self):
        """Get or refresh OAuth access token. Caches to file to survive restarts."""
        if self.access_token and self.token_expires and datetime.now() < self.token_expires:
            return self.access_token

        # Try loading cached token from file
        try:
            if os.path.exists(self._TOKEN_CACHE_FILE):
                with open(self._TOKEN_CACHE_FILE, "r") as f:
                    cache = json.load(f)
                expires = datetime.fromisoformat(cache["expires"])
                if datetime.now() < expires:
                    self.access_token = cache["token"]
                    self.token_expires = expires
                    logger.info("KIS token loaded from cache")
                    return self.access_token
        except Exception:
            pass

        # Request new token
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
                try:
                    with open(self._TOKEN_CACHE_FILE, "w") as f:
                        json.dump({"token": self.access_token, "expires": self.token_expires.isoformat()}, f)
                except Exception:
                    pass
                logger.info("KIS token refreshed")
                return self.access_token
            else:
                logger.warning("KIS token rate limited, will retry later")
                return None
        except Exception as e:
            logger.warning(f"KIS token error: {e}")
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
                                signals.append(S("neutral", f"Volume dried up — wait for confirmation", f"거래량 실종 — 관망"))

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
                        signal = "SELL"
                        en = "EXIT — Take profit now" if chg > 0 else "EXIT — Cut losses"
                        kr = "청산 — 익절 타이밍" if chg > 0 else "청산 — 손절 필요"
                    elif score < 45:
                        signal = "SELL"
                        en = "PARTIAL EXIT — Sell half, hold rest"
                        kr = "일부 청산 — 절반 정리 후 관망"
                    elif score >= 65:
                        signal = "HOLD"
                        en = "HOLD — Trend intact, let it ride"
                        kr = "홀딩 — 추세 유지, 더 갈 수 있음"
                    else:
                        signal = "HOLD"
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
