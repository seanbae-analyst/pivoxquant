"""Tests for services.legal_filter — 자본시장법 §6 / §101 방어선 회귀 테스트.

42 replacement patterns + 6 prohibited patterns. Each group has at least one
sample that proves the pattern fires. These tests are the canary — if any
assert fails, production is one deploy away from a regulatory exposure.
"""
from __future__ import annotations

import pytest

from services.legal_filter import (
    detect_prohibited,
    ensure_disclaimer,
    safe_scrub,
    scrub_response,
    scrub_signal,
    scrub_text,
)


class TestReplacements:
    """Each sample hits one of the 42 regex patterns and confirms it rewrites."""

    # ── Group 1: 복합 구문 ────────────────────────────────────────────────
    def test_position_reduction(self):
        assert "약세 신호 감지" in scrub_text("포지션 축소 또는 청산 고려")

    def test_exposure_reduction(self):
        assert "노출 지표 상승 관찰" in scrub_text("노출 축소 권고")

    def test_new_entry_hold(self):
        assert "신규 진입 관찰 구간" == scrub_text("신규 매수 보류")

    def test_cash_ratio(self):
        assert "현금 비중 관찰 지표" == scrub_text("현금 비중 확대 권고")

    def test_tp_sl(self):
        assert "TP/SL 레벨 관찰" == scrub_text("부분 익절 / 손절 고려")

    # ── Group 2: 권고 / 추천 / 조언 ─────────────────────────────────────
    @pytest.mark.parametrize(
        "original",
        [
            "매수 추천", "매수 권고", "매수 권장",
            "매도 추천", "매도 권고", "매도 권장",
            "손절 권고", "익절 권고",
        ],
    )
    def test_single_verb_recommendation_removed(self, original):
        result = scrub_text(original)
        assert "추천" not in result
        assert "권고" not in result
        assert "권장" not in result

    def test_chumchun_drimnida(self):
        assert "추천" not in scrub_text("AAPL 추천 드립니다.")

    def test_gwanyu(self):
        assert "권유" not in scrub_text("투자 권유 드립니다.")

    # ── Group 3: 타이밍 / 목표가 ────────────────────────────────────────
    def test_buy_timing(self):
        assert "진입 레벨 관찰" == scrub_text("매수 타이밍")

    def test_sell_timing(self):
        assert "청산 레벨 관찰" == scrub_text("매도 타이밍")

    def test_target_price(self):
        assert "목표가" not in scrub_text("목표가 도달")
        assert "참고 지표" in scrub_text("목표가 도달")

    def test_fair_price(self):
        assert "적정가" not in scrub_text("적정가 분석")

    def test_expected_return_pct(self):
        # "예상 수익률 +12.5%" 전체 구가 "과거 기록 지표"로
        out = scrub_text("예상 수익률 +12.5%")
        assert "+12.5%" not in out
        assert "과거 기록 지표" in out

    # ── Group 4: 전망 / 예측 ────────────────────────────────────────────
    def test_outlook_future(self):
        assert "전망" not in scrub_text("향후 전망")

    def test_market_outlook(self):
        assert "시장 관찰 구간" == scrub_text("시장 전망")

    def test_will_rise(self):
        assert "상승 지표가 관찰됩니다" in scrub_text("오를 것으로 보입니다.")

    def test_will_fall(self):
        assert "하락 지표가 관찰됩니다" in scrub_text("내릴 것 같습니다.")

    # ── Group 5: 가치 판단 ──────────────────────────────────────────────
    def test_favorable(self):
        assert "지표가 높은" in scrub_text("유리한 종목")

    def test_unfavorable(self):
        assert "지표가 낮은" in scrub_text("불리한 종목")

    def test_promising(self):
        assert "관찰 대상인" in scrub_text("유망한 종목")

    def test_overvalued(self):
        assert "고평가" not in scrub_text("고평가 구간")

    def test_aggressive(self):
        assert "변동성 높은 투자" in scrub_text("공격적 투자 접근")

    def test_best_stock(self):
        assert "상위 지표 종목" == scrub_text("베스트 종목")

    # ── Group 6: English imperatives ────────────────────────────────────
    def test_buy_signal_en(self):
        assert "POSITIVE indicator" == scrub_text("BUY signal")

    def test_sell_signal_en(self):
        assert "NEGATIVE indicator" == scrub_text("SELL signal")

    def test_recommend(self):
        assert "recommend" not in scrub_text("We recommend AAPL").lower()

    def test_advise(self):
        assert "advise" not in scrub_text("We advise caution").lower()

    def test_suggest(self):
        assert "suggest" not in scrub_text("We suggest review").lower()

    def test_target_price_en(self):
        assert "reference price" in scrub_text("Target price $200")

    def test_fair_value_en(self):
        assert "reference value" in scrub_text("Fair value estimate")

    # ── Group 7: 시장 비교 / 전망 영문 ─────────────────────────────────
    def test_outperform(self):
        out = scrub_text("This stock will outperform").lower()
        assert "outperform" not in out

    def test_beat_market(self):
        assert "benchmark 대비 기록" in scrub_text("Beat the market")

    def test_beat_sp500(self):
        assert "S&P 500 benchmark 대비 기록" in scrub_text("Beat S&P 500")

    def test_bullish(self):
        assert "상승 관찰" == scrub_text("bullish")

    def test_bearish(self):
        assert "하락 관찰" == scrub_text("bearish")

    def test_predict(self):
        assert "predict" not in scrub_text("Models predict rally").lower()

    def test_forecast(self):
        assert "forecast" not in scrub_text("Forecast is positive").lower()

    def test_best_opportunity(self):
        assert "highest indicator" == scrub_text("best opportunity")

    def test_most_attractive(self):
        assert "highest indicator" == scrub_text("most attractive")


class TestProhibitedDetection:
    """Patterns that cannot be surgically fixed — must be caught upstream."""

    @pytest.mark.parametrize(
        "text",
        [
            "목표가 $200",
            "목표가 ₩50,000",
            "예상 수익률 +15%",
            "적정가 $180",
            "price target: $200",
            "expected return: +15%",
            "fair value: $180",
        ],
    )
    def test_prohibited_detected(self, text):
        assert detect_prohibited(text), f"Failed to detect: {text}"

    def test_clean_text_no_detection(self):
        assert detect_prohibited("POSITIVE indicator observed.") == []

    def test_empty_text(self):
        assert detect_prohibited("") == []
        assert detect_prohibited(None) == []


class TestSafeScrub:
    def test_none_passthrough(self):
        assert safe_scrub(None) is None

    def test_empty_passthrough(self):
        assert safe_scrub("") == ""

    def test_non_string_passthrough(self):
        assert safe_scrub(123) == 123  # type: ignore[arg-type]

    def test_logs_prohibited(self, caplog):
        import logging
        caplog.set_level(logging.WARNING)
        safe_scrub("목표가 $200", context="unit-test")
        assert any("prohibited" in r.message for r in caplog.records)


class TestScrubSignal:
    def test_nested_dict(self):
        data = {
            "ticker": "AAPL",
            "score": 72,
            "commentary_kr": "매수 추천",
            "summary": "BUY signal strong",
            "ai_commentary": {"thesis": "outperform the market"},
        }
        out = scrub_signal(data)
        assert "추천" not in out["commentary_kr"]
        assert "POSITIVE" in out["summary"]
        assert "outperform" not in out["ai_commentary"]["thesis"]
        # non-string fields intact
        assert out["ticker"] == "AAPL"
        assert out["score"] == 72

    def test_non_dict_noop(self):
        assert scrub_signal("not a dict") == "not a dict"
        assert scrub_signal(None) is None


class TestScrubResponse:
    def test_nested_list_and_dict(self):
        payload = {
            "items": [
                {"analysis": "매수 권고합니다"},
                {"analysis": "SELL signal"},
            ],
            "note": "bullish outlook",
        }
        out = scrub_response(payload)
        assert "권고" not in out["items"][0]["analysis"]
        assert "SELL" not in out["items"][1]["analysis"]
        assert "상승 관찰" in out["note"]


class TestWave4LegalFilterShipBlocker:
    """Wave 4 (2026-05-17) — F1+F2+F3 SHIP-BLOCKER 회귀 게이트.

    verify-security agent 발견 자본시장법 §6 미등록 투자자문 위험 6건 중
    legal_filter 영역 3건 (F1 engine msg_kr, F2 구어체, F3 naked BUY/SELL)
    의 회귀 방지. legal-guard.yml CI 도 활성화되어 PR 단계에서 차단된다.
    """

    # ── F1: Group 10 expansion ────────────────────────────────────────────
    def test_f1_kigwan_buy_estimate(self):
        assert "매수" not in scrub_text("기관 매수 추정")
        assert "기관 유입 관찰" == scrub_text("기관 매수 추정")

    def test_f1_kigwan_sell_estimate(self):
        assert "매도" not in scrub_text("기관 매도 추정")
        assert "기관 유출 관찰" == scrub_text("기관 매도 추정")

    def test_f1_new_buy_avoidance(self):
        assert "매수" not in scrub_text("신규 매수 회피")

    def test_f1_strong_sell_pressure(self):
        assert "매도" not in scrub_text("강한 매도 압력")
        assert "강한 유출 강도" == scrub_text("강한 매도 압력")

    def test_f1_signals_list_traversal(self):
        """scrub_signal walks signals[].msg_kr — was bypass site."""
        payload = {
            "ticker": "005930.KS",
            "score": 72,
            "signals": [
                {"type": "bullish", "msg": "High-volume breakout — institutional accumulation detected",
                 "msg_kr": "거래량 급증 상승 — 기관 매수 추정"},
                {"type": "bearish", "msg": "Order Flow: Strong selling pressure",
                 "msg_kr": "주문흐름: 강한 매도 압력"},
            ],
        }
        out = scrub_signal(payload)
        assert "기관 매수 추정" not in out["signals"][0]["msg_kr"]
        assert "기관 유입 관찰" in out["signals"][0]["msg_kr"]
        assert "강한 매도 압력" not in out["signals"][1]["msg_kr"]
        assert "강한 유출 강도" in out["signals"][1]["msg_kr"]
        # non-string fields intact
        assert out["signals"][0]["type"] == "bullish"
        assert out["score"] == 72

    # ── F2: Group 11 구어체 ───────────────────────────────────────────────
    @pytest.mark.parametrize(
        "directive",
        ["사세요", "파세요", "팔아요", "사라", "팔아",
         "주식 사면 됩니다", "주식 사면 돼요",
         "지금 사야 해요", "지금 사야 합니다"],
    )
    def test_f2_colloquial_directive_scrubbed(self, directive):
        result = scrub_text(directive)
        # 매수/매도 동사가 완전히 제거되어야 함
        for forbidden in ("사세요", "파세요", "팔아요", "사라", "팔아", "사면", "사야"):
            assert forbidden not in result, f"'{forbidden}' bypassed scrub of '{directive}' → '{result}'"

    # ── F2b: ticker-interjected directive ("buy AAPL right now") ──────────
    @pytest.mark.parametrize(
        "directive",
        ["buy AAPL right now", "sell TSLA now", "Buy NVDA today",
         "sell $MSFT immediately", "buy GOOG asap"],
    )
    def test_f2b_ticker_interjected_directive_scrubbed(self, directive):
        result = scrub_text(directive)
        assert result == "관찰 시점", f"{directive!r} not scrubbed → {result!r}"

    @pytest.mark.parametrize(
        "prose",
        ["a good buy", "best-seller", "will sell products today",
         "people who buy apple pie today", "buy stocks now"],
    )
    def test_f2b_lowercase_prose_not_over_scrubbed(self, prose):
        # The ticker-interjected pattern requires an UPPERCASE ticker, so
        # lowercase prose must pass through untouched (no over-scrub).
        assert scrub_text(prose) == prose, f"over-scrubbed: {prose!r}"

    # ── F3: naked BUY/SELL (Group 6 보강) ─────────────────────────────────
    def test_f3_naked_buy(self):
        assert "ENTRY" == scrub_text("BUY")
        assert "BUY" not in scrub_text("BUY")

    def test_f3_naked_sell(self):
        assert "EXIT" == scrub_text("SELL")
        assert "SELL" not in scrub_text("SELL")

    def test_f3_buy_signal_unchanged(self):
        """기존 'BUY signal' 케이스가 깨지지 않아야 함 (Group 6 순서 의존)."""
        assert "POSITIVE indicator" == scrub_text("BUY signal")
        assert "NEGATIVE indicator" == scrub_text("SELL signal")

    def test_f3_backtester_trade_dict(self):
        """backtester trades[].action raw BUY/SELL → ENTRY/EXIT via scrub_response."""
        trades_payload = {
            "trades": [
                {"date": "2024-01-15", "action": "BUY", "price": 150.0, "shares": 10},
                {"date": "2024-02-20", "action": "SELL", "price": 165.0, "shares": 10},
            ],
            "summary": "1 round-trip",
        }
        out = scrub_response(trades_payload)
        assert out["trades"][0]["action"] == "ENTRY"
        assert out["trades"][1]["action"] == "EXIT"
        # numeric fields untouched
        assert out["trades"][0]["price"] == 150.0


class TestEnsureDisclaimer:
    def test_append_kr(self):
        out = ensure_disclaimer("관찰 지표입니다.", "kr")
        assert "정보 제공 목적이며 투자 권유가 아닙니다" in out

    def test_append_en(self):
        out = ensure_disclaimer("Observed.", "en")
        assert "informational only" in out

    def test_idempotent(self):
        text = "Observed.\n\nThis is informational only and not investment advice."
        assert ensure_disclaimer(text, "en") == text

    def test_none_passthrough(self):
        assert ensure_disclaimer(None) is None


class TestTakeProfitStopLossGap:
    """2026-05-22: take profit / stop loss / 익절 / 손절 매매 지시어 갭.

    public AI chat 이 쓰는 공용 legal_filter 가 이 4개 매매 지시어를
    scrub 도 detect 도 못 하던 갭을 메움 (legal_gate.py ADVICE_PATTERNS 만 잡았음).
    Group 11e (EN) + Group 11f (KR) + _COMPLIANCE_FORBIDDEN_PATTERNS 추가.
    """

    # ── scrub: 4개 입력이 이제 surgical 치환됨 ────────────────────────────
    def test_take_profit_scrubbed(self):
        out = scrub_text("Take profit here at 300")
        assert "Take profit" not in out
        assert "TP 레벨 관찰" in out

    def test_take_quick_profits_scrubbed(self):
        out = scrub_text("take quick profits now")
        assert "take quick profits" not in out
        assert "TP 레벨 관찰" in out

    def test_stop_loss_scrubbed(self):
        out = scrub_text("Stop loss at 250")
        assert "Stop loss" not in out
        assert "SL 레벨 관찰" in out

    def test_stoploss_no_space_scrubbed(self):
        assert "SL 레벨 관찰" in scrub_text("set a stoploss")

    def test_ikjeol_scrubbed(self):
        out = scrub_text("익절하세요")
        assert "익절" not in out
        assert "TP 레벨 관찰" in out

    def test_sonjeol_scrubbed(self):
        out = scrub_text("손절 타이밍")
        assert "손절" not in out
        assert "SL 레벨 관찰" in out

    # ── is_compliant: 4개 입력이 이제 hard-drop 대상 ───────────────────────
    @pytest.mark.parametrize(
        "text",
        [
            "Take profit here at 300",
            "Stop loss at 250",
            "익절하세요",
            "손절 타이밍",
        ],
    )
    def test_advisory_now_blocked(self, text):
        from services.legal_filter import is_compliant
        assert not is_compliant(text), f"{text!r} is advisory — must be blocked"

    # ── 음성(false-positive) 케이스: 오치환 / 오탐 없어야 함 ───────────────
    @pytest.mark.parametrize(
        "text",
        [
            "the company will profit from growth",
            "non-stop service",
            "the stop is non-negotiable",
            "profits rose sharply this quarter",
        ],
    )
    def test_negative_cases_not_scrubbed(self, text):
        # take/loss 가 없으므로 치환 대상 표현이 새로 들어가면 안 됨
        out = scrub_text(text)
        assert "TP 레벨 관찰" not in out
        assert "SL 레벨 관찰" not in out

    @pytest.mark.parametrize(
        "text",
        [
            "the company will profit from growth",
            "non-stop service",
        ],
    )
    def test_negative_cases_stay_compliant(self, text):
        from services.legal_filter import is_compliant
        assert is_compliant(text), f"{text!r} is a legit phrase — should not trigger hard-drop"

    # ── 기존 복합 패턴 우선순위 보존 (단독형이 침범하지 않음) ──────────────
    def test_compound_ikjeol_sonjeol_priority_preserved(self):
        # Group 1 line 44 (부분 익절/손절 고려) 가 단독 Group 11f 보다 먼저 매칭
        assert scrub_text("부분 익절 / 손절 고려") == "TP/SL 레벨 관찰"

    def test_compound_recommendation_priority_preserved(self):
        # Group 2 line 49/50 (손절/익절 권고) 가 단독형보다 먼저 매칭
        assert "정보 고지" in scrub_text("손절 권고")
        assert "정보 고지" in scrub_text("익절 권고")


class TestImperativeBuySellStreamGap:
    """2026-05-22: 소문자 명령형 buy/sell 갭 (Group 11g).

    naked 대문자 \\bBUY\\b/\\bSELL\\b 는 의도적 case-sensitive 라 스트리밍
    AI chat 이 흘리는 소문자 명령형("you should buy now")이 per-chunk
    safe_scrub 를 통과했음. 명령 부사/어미와 결합된 좁은 형태만 보강.
    절대 광범위 \\bbuy\\b IGNORECASE 가 아니므로 산문은 보존되어야 함.
    """

    # ── 명령형: Group 11g 가 직접 잡는 케이스 (선행 그룹 미간섭) ──────────
    @pytest.mark.parametrize(
        "text",
        [
            "sell immediately",
            "buy today",
            "sell asap",
            "buy right now",
            "sell now",
            "Buy Now",
        ],
    )
    def test_en_imperative_scrubbed(self, text):
        out = scrub_text(text)
        assert "관찰 시점" in out, f"{text!r} → {out!r}"
        # 명령형 buy/sell 동사가 부사와 함께 사라져야 함
        assert "buy now" not in out.lower()
        assert "sell now" not in out.lower()
        assert "buy today" not in out.lower()
        assert "sell immediately" not in out.lower()

    def test_should_buy_now_neutralized_upstream(self):
        # "you should buy now": Group 8 의 \bShould\s+buy\b 가 먼저 "note" 로
        # 치환 → "you note now". 위험 동사 buy 제거됨. is_compliant 는 원문에
        # buy 가 있어 차단. (Group 11g 가 직접 잡진 않으나 누출은 막힘.)
        out = scrub_text("you should buy now")
        assert "buy" not in out.lower()
        from services.legal_filter import is_compliant
        assert not is_compliant("you should buy now")

    @pytest.mark.parametrize(
        "text",
        ["지금 매수하세요", "지금 매도", "매수하세요", "매도하라", "매수해라"],
    )
    def test_kr_imperative_scrubbed(self, text):
        out = scrub_text(text)
        assert "관찰 시점" in out or "관찰 중" in out
        assert "매수하세요" not in out
        assert "매도하라" not in out
        assert "지금 매수" not in out

    # ── 명령형: is_compliant hard-drop 대상 ───────────────────────────────
    @pytest.mark.parametrize(
        "text",
        ["you should buy now", "sell immediately", "지금 매수하세요"],
    )
    def test_imperative_blocked_by_is_compliant(self, text):
        from services.legal_filter import is_compliant
        assert not is_compliant(text), f"{text!r} is an imperative directive — must be blocked"

    # ── 음성(산문) 케이스: over-scrub 금지 ────────────────────────────────
    @pytest.mark.parametrize(
        "text",
        [
            "a good buy opportunity",
            "buying pressure rose",
            "best-seller list",
            "the company will sell products",
            "buyout rumors today",
            "sellers outnumbered buyers",
        ],
    )
    def test_prose_not_over_scrubbed(self, text):
        # 명령 부사가 없으므로 새 중립표현이 주입되면 안 됨
        out = scrub_text(text)
        assert "관찰 시점" not in out, f"prose {text!r} was over-scrubbed → {out!r}"


class TestOverboughtOversoldGuard:
    """2026-05-22 — `매수\\s*신호` / `매도\\s*신호` replacement rules lacked the
    `(?<!과)` lookbehind that the detection regex already had, so safe_scrub
    corrupted the technical-analysis terms 과매수(overbought) / 과매도(oversold):
        safe_scrub("과매수 신호") → "과POSITIVE 지표"  (BUG)
        safe_scrub("과매도 신호") → "과NEGATIVE 지표"  (BUG)
    The replacement rules now carry the same guard. Bare advisory forms must
    still be scrubbed.
    """

    @pytest.mark.parametrize(
        "text",
        [
            "과매수 신호",
            "과매도 신호",
            "RSI 과매수 신호 포착",
            "과매수 기회",
            "과매수 유리",
            "과매도 유리",
            "과매수 압력",
        ],
    )
    def test_overbought_oversold_preserved(self, text):
        out = safe_scrub(text)
        assert out == text, f"quant term {text!r} was over-scrubbed → {out!r}"
        # No neutral replacement tokens injected.
        for token in ("POSITIVE", "NEGATIVE", "지표 저점 영역", "지표 유리 영역", "유입 강도"):
            assert token not in out, f"{text!r} corrupted with {token!r} → {out!r}"

    @pytest.mark.parametrize(
        "text,expected_token",
        [
            ("매수 신호", "POSITIVE 지표"),
            ("매도 신호", "NEGATIVE 지표"),
            ("매수 기회", "지표 저점 영역"),
            ("매수 유리", "지표 유리 영역"),
            ("매도 유리", "지표 유리 영역"),
            ("매수 압력", "유입 강도"),
        ],
    )
    def test_bare_advisory_still_scrubbed(self, text, expected_token):
        out = safe_scrub(text)
        assert expected_token in out, f"bare {text!r} should still scrub → {out!r}"
        assert out != text


class TestOverScrubFixes2026_05_25:
    """Regression guard for 5 over-scrub corruptions fixed 2026-05-25.

    The scrub rules previously mangled legitimate prose / disclaimer text:
      1. "suggests" → "observe" (suffix dropped, broke grammar)
      2. "정보 제안을" → "정보 정보 제공을" (duplicated "정보")
      3. "자문 서비스가 아닙니다" → "정보 제공 서비스가 아닙니다" (면책 의미 역전)
      4. "포트폴리오 리밸런싱" → "포트폴리오 포트폴리오 재점검" (duplicated)
      5. "이기적/이기주의" → "benchmark 대비 기록하…" (한국어 명사 파괴)

    Each fix must (a) preserve the original prose AND (b) leave genuine
    advisory vocabulary still scrubbed (protection not weakened).
    """

    # ── Fix #1: suggest inflections keep grammatical "observe" forms ──
    @pytest.mark.parametrize(
        "original,expected",
        [
            ("This suggests strong momentum", "This observes strong momentum"),
            ("The data suggested a trend", "The data observed a trend"),
            ("It is suggesting caution", "It is observing caution"),
            ("a helpful suggestion", "a helpful observation"),
            ("several suggestions", "several observations"),
        ],
    )
    def test_suggest_grammar_preserved(self, original, expected):
        assert scrub_text(original) == expected

    # ── Fix #2: "제안" no longer duplicates a preceding "정보" ──
    def test_jean_no_double_jeongbo(self):
        out = scrub_text("정보 제안을 드립니다")
        assert "정보 정보" not in out, f"duplicated 정보 → {out!r}"
        assert "제안" not in out, f"제안 should still scrub → {out!r}"

    # ── Fix #3 (CRITICAL): 자문 disclaimer meaning preserved ──
    @pytest.mark.parametrize(
        "original",
        [
            "본 서비스는 투자 자문 서비스가 아닙니다",
            "이것은 자문 서비스가 아님을 고지합니다",
            "전문가의 자문을 받으시기 바랍니다",
            "본 정보는 자문을 구성하지 않습니다",
            "자문 없이 제공되는 정보입니다",
        ],
    )
    def test_jamun_disclaimer_preserved(self, original):
        out = scrub_text(original)
        assert "자문" in out, f"면책 자문 표현이 손상됨 → {out!r}"
        assert out == original, f"면책 의미 역전 → {out!r}"

    # ── Fix #4: 리밸런싱 no longer duplicates 포트폴리오 ──
    def test_rebalancing_no_double_portfolio(self):
        out = scrub_text("포트폴리오 리밸런싱")
        assert "포트폴리오 포트폴리오" not in out, f"duplicated → {out!r}"
        assert "리밸런싱" not in out, f"리밸런싱 should still scrub → {out!r}"
        assert out == "포트폴리오 재배분"

    # ── Fix #5: 이기 verb-stem only; nouns preserved ──
    @pytest.mark.parametrize(
        "noun",
        ["이기적인 행동", "이기주의", "이기심", "이기적 동기"],
    )
    def test_igi_noun_preserved(self, noun):
        out = scrub_text(noun)
        assert out == noun, f"한국어 명사 파괴 → {out!r}"
        assert "benchmark" not in out

    @pytest.mark.parametrize(
        "verb",
        ["시장을 이기다", "벤치마크를 이기고", "지수를 이기는"],
    )
    def test_igi_verb_still_scrubbed(self, verb):
        out = scrub_text(verb)
        assert "이기" not in out or "benchmark 대비 기록" in out
        assert "benchmark 대비 기록" in out, f"동사 어간 미치환 → {out!r}"

    # ── Protection-not-weakened sanity: real advisory verbs still scrub ──
    @pytest.mark.parametrize(
        "original,banned",
        [
            ("지금 매수하세요", "매수"),
            ("삼성전자 매도 권고", "권고"),
            ("You should BUY now", "BUY"),
            ("SELL signal detected", "SELL"),
            ("take profit here", "profit"),
        ],
    )
    def test_forbidden_still_scrubbed(self, original, banned):
        out = scrub_text(original)
        assert banned not in out, f"보호 약화 — {banned!r} survived → {out!r}"


class TestOverScrubFixes2026_05_26:
    """Regression guard for 2 over-scrub gaps fixed 2026-05-26.

    Follow-on to the 2026-05-25 wave:
      #4 (MEDIUM): 명사형 "이기기 위한/위해"(beat market) 가 §101 필터를 통과해
          버렸음 (동사 어미 lookahead 에 명사화 "이기**기**" 미포함).
      #5 (LOW): "성능 최적화" / "SEO 최적화" 같은 공백 포함 tech 어휘가
          over-scrub 되어 "성능 재구성" 으로 손상됐음 (단일문자 char-class
          lookbehind 가 공백 앞 prefix 를 못 봄).

    각 fix 는 (a) 잡아야 할 변형은 잡고 (b) 정상 산문은 보존하며 (c) 기존
    advisory 보호를 약화시키지 않아야 한다.
    """

    # ── Gap #4: "이기기 위한/위해" beat-market 명사형 잡힘 ──
    @pytest.mark.parametrize(
        "text",
        [
            "시장을 이기기 위한 전략",
            "S&P 500을 이기기 위해 집중투자하세요",
            "시장을 이기기 위한",
            "지수를 이기기 위해",
        ],
    )
    def test_igi_gi_wihae_scrubbed(self, text):
        out = scrub_text(text)
        assert "이기기 위" not in out, f"beat-market 명사형 미치환 → {out!r}"
        assert "benchmark 대비 기록" in out, f"치환 누락 → {out!r}"

    # ── Gap #4: 비금융 "이기기 ..." 및 명사는 여전히 보존 ──
    @pytest.mark.parametrize(
        "text",
        [
            "이기기 싫다",
            "이기기가 어렵다",
            "이기적인 행동",
            "이기주의",
            "이기심",
        ],
    )
    def test_igi_gi_nonfinancial_preserved(self, text):
        out = scrub_text(text)
        assert out == text, f"비금융 산문 파괴 → {out!r}"
        assert "benchmark" not in out

    # ── Gap #4: 기존 동사 어간 치환은 그대로 유지 ──
    @pytest.mark.parametrize(
        "text",
        ["이기다", "이기고 있다", "시장을 이기는"],
    )
    def test_igi_verb_stem_still_scrubbed(self, text):
        out = scrub_text(text)
        assert "benchmark 대비 기록" in out, f"기존 동사 치환 회귀 → {out!r}"

    # ── Gap #5: tech 어휘 "X 최적화" 공백 포함구문 보존 ──
    @pytest.mark.parametrize(
        "text",
        [
            "성능 최적화 가이드",
            "SEO 최적화",
            "프로세스 최적화",
            "UX 최적화",
        ],
    )
    def test_tech_optimize_preserved(self, text):
        out = scrub_text(text)
        assert "재구성" not in out, f"tech 어휘 over-scrub → {out!r}"
        assert out == text, f"산문 변형 → {out!r}"

    # ── Gap #5: 금융 권유 맥락 "최적화" 는 여전히 치환 ──
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("포트폴리오 최적화", "포트폴리오 재구성"),
            ("자산 최적화", "자산 재구성"),
            ("최적화", "재구성"),
        ],
    )
    def test_financial_optimize_still_scrubbed(self, text, expected):
        assert scrub_text(text) == expected

    # ── 보호-약화 sanity: 진짜 금지어는 여전히 scrub ──
    @pytest.mark.parametrize(
        "original,banned",
        [
            ("지금 매수하세요", "매수"),
            ("매도 권고", "권고"),
            ("You should BUY now", "BUY"),
        ],
    )
    def test_protection_not_weakened(self, original, banned):
        out = scrub_text(original)
        assert banned not in out, f"보호 약화 — {banned!r} survived → {out!r}"
