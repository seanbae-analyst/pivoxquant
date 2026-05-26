"""Day trading routes: scan, analyze, chart, prices, stream."""
import json
import logging
import time
from flask import Blueprint, request, jsonify, Response
from flask_login import current_user

from models import Position
from services.container import daytrade
from services.name_resolver import resolve_stock_name
from services.ticker_normalizer import normalize_ticker
from services.access_guard import is_user_allowed_ticker, access_denied_response
from .decorators import api_auth, legal_scrub_response

logger = logging.getLogger(__name__)

daytrade_bp = Blueprint("daytrade", __name__, url_prefix="/api/daytrade")

# Alpaca-supported intraday timeframes accepted by /chart.
VALID_TF = {"1Min", "5Min", "15Min", "30Min", "1Hour"}


@daytrade_bp.route("/status")
@api_auth
def status():
    return jsonify({"available": daytrade.available})


@daytrade_bp.route("/scan")
@api_auth
@legal_scrub_response
def scan():
    results = []
    if daytrade.available:
        try:
            us_results = daytrade.scan_momentum() or []
            results.extend(us_results)
        except Exception as e:
            logger.warning("US scan error: %s", e)

    try:
        from services.kis.service import KISService
        kis = KISService()
        if kis.available:
            held_kr = set()
            try:
                positions = Position.query.filter_by(user_id=current_user.id).all()
                for p in positions:
                    t = p.ticker.replace(".KS", "").replace(".KQ", "")
                    if t.isdigit() and len(t) == 6:
                        held_kr.add(t)
            except Exception:
                logger.debug("silent-fallback: scan", exc_info=True)
                pass
            kr_results = kis.scan_momentum(held_tickers=held_kr) or []
            results.extend(kr_results)
    except Exception as e:
        logger.warning("KR scan error: %s", e)

    if not results and not daytrade.available:
        return jsonify({"error": "Day trade not configured (Alpaca API key missing)"}), 503

    # Guarantee every scan hit carries a display name. The US scanner emits
    # ticker-only for long-tail Alpaca assets; KIS emits Korean names for KR.
    for item in results:
        if not isinstance(item, dict):
            continue
        t = item.get("ticker") or ""
        if t and (not item.get("name") or item.get("name") == t):
            item["name"] = resolve_stock_name(t) or t

    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return jsonify({"results": results, "count": len(results)})


@daytrade_bp.route("/analyze/<ticker>")
@api_auth
@legal_scrub_response
def analyze(ticker):
    # §101 회피 — 보유/watchlist 종목만 분석 허용 (fail-closed). access_guard
    # 는 정규화된 저장형(005930.KS)으로 조회하므로 gate 용 normalized 만 따로
    # 만들고, 아래 KR 분기(bare 6-digit 의존)·US 분기는 원본 ticker 를 보존한다.
    normalized = normalize_ticker(ticker)
    if not is_user_allowed_ticker(current_user.id, normalized):
        body, status = access_denied_response()
        return jsonify(body), status

    if ticker.isdigit() and len(ticker) == 6:
        try:
            from services.kis.service import KISService
            import numpy as np
            kis = KISService()
            if not kis.available:
                return jsonify({"error": "KIS not configured"}), 503

            price_data = kis.get_current_price(ticker)
            if not price_data or price_data["price"] == 0:
                return jsonify({"error": f"No price data for {ticker}"}), 404

            bars = kis.get_intraday_bars(ticker)
            score = 50.0
            signals = []
            rsi_val = vol_ratio = None
            price = price_data["price"]
            chg = price_data["change_pct"]
            high = price_data.get("high", 0)
            low = price_data.get("low", 0)
            opn = price_data.get("open", 0)

            if chg > 5: score += 20; signals.append({"type": "bullish", "msg": f"Surging +{chg:.1f}%", "msg_kr": f"급등 +{chg:.1f}%"})
            elif chg > 3: score += 15; signals.append({"type": "bullish", "msg": f"Strong rally +{chg:.1f}%", "msg_kr": f"강한 상승 +{chg:.1f}%"})
            elif chg > 1: score += 8; signals.append({"type": "bullish", "msg": f"Up +{chg:.1f}%", "msg_kr": f"상승 +{chg:.1f}%"})
            elif chg < -5: score -= 20; signals.append({"type": "bearish", "msg": f"Crashing {chg:.1f}%", "msg_kr": f"급락 {chg:.1f}%"})
            elif chg < -3: score -= 15; signals.append({"type": "bearish", "msg": f"Sharp drop {chg:.1f}%", "msg_kr": f"강한 하락 {chg:.1f}%"})
            elif chg < -1: score -= 8; signals.append({"type": "bearish", "msg": f"Down {chg:.1f}%", "msg_kr": f"하락 {chg:.1f}%"})

            if high > low > 0:
                pos_r = (price - low) / (high - low)
                if pos_r > 0.85: score -= 5; signals.append({"type": "bearish", "msg": f"Near intraday high ({pos_r*100:.0f}%)", "msg_kr": f"장중 고점 근접 ({pos_r*100:.0f}%)"})
                elif pos_r < 0.15: score += 5; signals.append({"type": "bullish", "msg": f"Near intraday low ({pos_r*100:.0f}%)", "msg_kr": f"장중 저점 근접 ({pos_r*100:.0f}%)"})

            if bars and len(bars) > 5:
                closes = [b["close"] for b in bars if b["close"] > 0]
                volumes = [b["volume"] for b in bars if b["volume"] > 0]

                if len(closes) >= 14:
                    rsi_val = KISService._calc_rsi(np.array(closes), 14)
                    if rsi_val is not None:
                        if rsi_val < 25: score += 18; signals.append({"type": "bullish", "msg": f"RSI extreme oversold ({rsi_val:.0f})", "msg_kr": f"RSI 극과매도 ({rsi_val:.0f})"})
                        elif rsi_val < 35: score += 12; signals.append({"type": "bullish", "msg": f"RSI oversold ({rsi_val:.0f})", "msg_kr": f"RSI 과매도 ({rsi_val:.0f})"})
                        elif rsi_val > 80: score -= 18; signals.append({"type": "bearish", "msg": f"RSI extreme overbought ({rsi_val:.0f})", "msg_kr": f"RSI 극과매수 ({rsi_val:.0f})"})
                        elif rsi_val > 70: score -= 12; signals.append({"type": "bearish", "msg": f"RSI overbought ({rsi_val:.0f})", "msg_kr": f"RSI 과매수 ({rsi_val:.0f})"})

                if len(volumes) > 3:
                    avg_v = np.mean(volumes[:-1])
                    if avg_v > 0:
                        vol_ratio = round(volumes[-1] / avg_v, 1)
                        if vol_ratio >= 5: score += 15; signals.append({"type": "bullish", "msg": f"Volume explosion {vol_ratio}x", "msg_kr": f"거래량 폭발 {vol_ratio}배"})
                        elif vol_ratio >= 3: score += 10; signals.append({"type": "bullish", "msg": f"Volume surge {vol_ratio}x", "msg_kr": f"거래량 급증 {vol_ratio}배"})

                if len(closes) >= 20:
                    ma5 = np.mean(closes[-5:]); ma20 = np.mean(closes[-20:])
                    if ma5 > ma20 and closes[-1] > ma5: score += 8; signals.append({"type": "bullish", "msg": "Short MA > Long MA — uptrend", "msg_kr": "단기MA > 중기MA — 상승"})
                    elif ma5 < ma20 and closes[-1] < ma5: score -= 8; signals.append({"type": "bearish", "msg": "Short MA < Long MA — downtrend", "msg_kr": "단기MA < 중기MA — 하락"})

                if len(closes) >= 6:
                    rc = (closes[-1] - closes[-5]) / closes[-5] * 100
                    if rc > 1.5: signals.append({"type": "bullish", "msg": f"Last 5 bars rising +{rc:.1f}%", "msg_kr": f"직전 5봉 상승 +{rc:.1f}%"})
                    elif rc < -1.5: signals.append({"type": "bearish", "msg": f"Last 5 bars falling {rc:.1f}%", "msg_kr": f"직전 5봉 하락 {rc:.1f}%"})

            if opn > 0:
                gap = (price - opn) / opn * 100
                if gap > 3: signals.append({"type": "bullish", "msg": f"Gap up +{gap:.1f}%", "msg_kr": f"갭 상승 +{gap:.1f}%"})
                elif gap < -3: signals.append({"type": "bearish", "msg": f"Gap down {gap:.1f}%", "msg_kr": f"갭 하락 {gap:.1f}%"})

            score = max(0, min(100, score))
            signal = "POSITIVE" if score >= 65 else "NEGATIVE" if score < 30 else "NEUTRAL"
            atr = (high - low) if high > low else price * 0.02
            tp_price = round(price + atr * 0.7)
            sl_price = round(price - atr * 0.5)

            return jsonify({
                "ticker": ticker, "name": price_data["name"],
                "price": price, "change_pct": chg, "score": round(score, 1),
                "signal": signal, "signals": signals,
                "rsi": round(rsi_val, 1) if rsi_val else None,
                "vwap": None, "vol_ratio": vol_ratio,
                "take_profit": tp_price, "stop_loss": sl_price,
                "tp_pct": round((tp_price - price) / price * 100, 2),
                "sl_pct": round((sl_price - price) / price * 100, 2),
                "trailing_stop_pct": round(atr / price * 100, 2),
                "atr": round(atr), "currency": "KRW",
                "is_korean": True, "regime_profile": "",
            })
        except Exception as e:
            logger.warning("KR daytrade error %s: %s", ticker, e)
        return jsonify({"error": f"No data for {ticker}"}), 404

    if not daytrade.available:
        return jsonify({"error": "Day trade not configured"}), 503
    r = daytrade.analyze_short_term(ticker)
    if not r:
        return jsonify({"error": f"No intraday data for {ticker}"}), 404
    # Backfill name for US daytrade payload (Alpaca scanner emits ticker-only
    # for long-tail listings — us_stock_registry covers the full ~12.7k set).
    if isinstance(r, dict):
        t_up = ticker.upper() if isinstance(ticker, str) else ticker
        if not r.get("name") or r.get("name") == t_up:
            r["name"] = resolve_stock_name(t_up) or t_up
    return jsonify(r)


@daytrade_bp.route("/chart/<ticker>")
@api_auth
def chart(ticker):
    if ticker.isdigit() and len(ticker) == 6:
        return jsonify({"ticker": ticker, "timeframe": "1Min", "bars": [], "note": "Korean stocks use KIS"})
    if not daytrade.available:
        return jsonify({"error": "Day trade not configured"}), 503
    # Validate/clamp query params (mirror portfolio.py:1291 pattern):
    # `?limit=abc` previously raised ValueError -> uncaught 500; an
    # unbounded limit or arbitrary tf both hit the upstream Alpaca API.
    tf = request.args.get("tf", "5Min")
    if tf not in VALID_TF:
        tf = "5Min"
    try:
        limit = int(request.args.get("limit", "100"))
    except (ValueError, TypeError):
        limit = 100
    limit = max(1, min(limit, 500))
    bars = daytrade.get_intraday_bars(ticker, tf, limit)
    return jsonify({"ticker": ticker.upper(), "timeframe": tf, "bars": bars})


@daytrade_bp.route("/prices")
@api_auth
def prices():
    if not daytrade.available:
        return jsonify({"error": "Day trade not configured"}), 503
    return jsonify({"prices": daytrade.get_latest_prices()})


@daytrade_bp.route("/stream")
@api_auth
def stream():
    if not daytrade.available:
        return jsonify({"error": "Day trade not configured"}), 503

    def generate():
        # Instantiate KIS once per stream rather than per loop iteration —
        # avoids re-loading creds + token on every 10s tick.
        try:
            from services.kis.service import KISService
            kis = KISService()
        except Exception:
            logger.debug("silent-fallback: KIS init", exc_info=True)
            kis = None
        try:
            while True:
                try:
                    prices = {}
                    if daytrade.available:
                        try:
                            prices.update(daytrade.get_latest_prices() or {})
                        except Exception:
                            logger.debug("silent-fallback: generate", exc_info=True)
                            pass
                    try:
                        if kis and kis.available:
                            for code in ['005930', '000660', '035420', '005380', '006400', '051910']:
                                p = kis.get_current_price(code)
                                if p:
                                    prices[code] = {"price": p["price"], "change_pct": p["change_pct"]}
                                time.sleep(0.55)
                    except Exception:
                        logger.debug("silent-fallback: generate", exc_info=True)
                        pass
                    yield f"data: {json.dumps(prices, ensure_ascii=False)}\n\n"
                except Exception as e:
                    import logging as _logging
                    _logging.getLogger(__name__).error(f"Daytrade stream error: {e}")
                    yield f"data: {json.dumps({'error': 'Price update failed'})}\n\n"
                time.sleep(10)
        except GeneratorExit:
            return

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
