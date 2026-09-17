"""tests/test_mirror_report_pdf.py — 월간 거울 리포트 (services/reports/mirror_pdf.py).

세 가지를 잠근다:

1. **데이터** — 기록이 없으면 ``has_content=False`` (예외가 아니라 플래그로).
   기록이 있으면 네 거울이 실제로 채워지고, 기간 밖 기록은 들어오지 않는다.
2. **어휘** — 렌더 결과에 지시로 읽힐 낱말이 없다. 권위 있는 목록
   (``services/legal/forbidden_terms.py`` 의 FORBIDDEN_DIRECTIVE_TERMS)을
   그대로 들이대서 검사한다 — 테스트가 자기만의 목록을 따로 들고 있으면
   SoT 가 늘어날 때 조용히 뒤처진다.
3. **면책** — SoT 문구(services/legal/disclaimers.py)가 글자 그대로 들어간다.

weasyprint 는 macOS 로컬에서 native lib(pango/gobject) 때문에 import 가 깨질 수
있다(HANDOVER.md). PDF 단계만 skip 되고, 데이터와 HTML 검사는 weasyprint 없이도
반드시 돈다.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta

import pytest

from services.legal.disclaimers import (
    DISCLAIMER_ARTIFACT_KR,
    DISCLAIMER_MIRROR_RETROSPECTIVE_KR,
)
from services.legal.forbidden_terms import FORBIDDEN_DIRECTIVE_TERMS
from services.reports.mirror_pdf import (
    build_mirror_report,
    render_mirror_html,
    render_mirror_pdf,
)

# 창을 고정해서 "오늘"에 따라 결과가 흔들리지 않게 한다.
AS_OF = datetime(2026, 9, 17, 12, 0, 0)

LOCALES = ("ko", "en")

# 과제 명세가 못 박은 낱말. FORBIDDEN_DIRECTIVE_TERMS 전수 검사와 별개로,
# 이 여섯은 사라지면 안 되는 최소 보증이라 따로 단언한다.
_SPEC_BANNED = ("buy", "sell", "hold", "recommend", "advice", "추천", "조언")
_SPEC_BANNED_RE = re.compile(
    r"\b(buy|sell|hold|recommend|recommendation|advice|advise)\b|추천|조언",
    re.IGNORECASE,
)


# ── fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def add_trade(app):
    """기록을 한 줄 심는다. ``days_ago`` 는 AS_OF 기준."""
    from extensions import db
    from models import TradeHistory

    def _add(user_id, *, ticker="AAPL", action="BUY", shares=10.0, price=100.0,
             days_ago=5, currency="USD", pnl_pct=0.0, name=""):
        with app.app_context():
            row = TradeHistory(
                user_id=user_id,
                ticker=ticker,
                name=name or ticker,
                action=action,
                shares=shares,
                price_per_share=price,
                total_value=shares * price,
                # 손익 분류는 SELL 행에 저장된 pnl_pct 를 읽는다
                # (services/profile/fifo_util.fifo_match_closed_trades_with_pnl).
                pnl_pct=pnl_pct,
                pnl=shares * price * pnl_pct / 100.0,
                currency=currency,
                traded_at=AS_OF - timedelta(days=days_ago),
            )
            db.session.add(row)
            db.session.commit()
            return row.id
    return _add


@pytest.fixture
def active_user(app, make_user, add_trade):
    """한 달 안에 취득·처분·추가 취득·닫힌 거래가 모두 있는 유저."""
    user = make_user(email="mirror@test.com")
    uid = user["id"]
    # AAPL: 취득 → 같은 종목 추가 취득(평균매입가보다 낮게) → 이익 실현 처분
    add_trade(uid, ticker="AAPL", action="BUY", shares=10, price=100.0, days_ago=25)
    add_trade(uid, ticker="AAPL", action="BUY", shares=10, price=80.0, days_ago=18)
    add_trade(uid, ticker="AAPL", action="SELL", shares=10, price=120.0, days_ago=6, pnl_pct=20.0)
    # 005930: 취득 → 손실 실현 처분 (원화 기록 — 통화가 섞여도 합치지 않는다)
    add_trade(uid, ticker="005930", action="BUY", shares=5, price=70000.0,
              days_ago=20, currency="KRW", name="삼성전자")
    add_trade(uid, ticker="005930", action="SELL", shares=5, price=63000.0,
              days_ago=3, currency="KRW", name="삼성전자", pnl_pct=-10.0)
    return user


# ── build_mirror_report ──────────────────────────────────────────────

class TestBuild:
    def test_no_records_has_content_false(self, app, make_user):
        user = make_user(email="empty@test.com")
        with app.app_context():
            data = build_mirror_report(user["id"], as_of=AS_OF)

        assert data["has_content"] is False
        # 예외가 아니라 플래그다 — 발송 쪽이 이걸로 스킵을 판단한다.
        assert data["window_trade_count"] == 0
        assert data["turnover"]["sufficient_data"] is False
        assert data["averaging_down"]["sufficient_data"] is False
        assert data["profit_loss"]["sufficient_data"] is False

    def test_period_fields(self, app, make_user):
        user = make_user(email="period@test.com")
        with app.app_context():
            data = build_mirror_report(user["id"], period_days=30, as_of=AS_OF)

        assert data["period_days"] == 30
        assert data["period_end"] == "2026-09-17"
        assert data["period_start"] == "2026-08-18"
        assert data["user_id"] == user["id"]
        assert data["generated_at"]

    def test_records_fill_every_mirror(self, app, active_user):
        with app.app_context():
            data = build_mirror_report(active_user["id"], as_of=AS_OF)

        assert data["has_content"] is True
        assert data["window_trade_count"] == 5

        turnover = data["turnover"]
        assert turnover["sufficient_data"] is True
        assert turnover["trade_count"] == 5
        assert turnover["buy_count"] == 3
        assert turnover["sell_count"] == 2
        # 통화는 끝까지 따로 — 원화와 달러가 한 숫자로 합쳐지지 않는다.
        assert {c["currency"] for c in turnover["by_currency"]} == {"USD", "KRW"}
        assert turnover["median_hold_days"] is not None

        followon = data["averaging_down"]
        assert followon["sufficient_data"] is True
        assert followon["follow_on_count"] == 1
        assert followon["below_avg_count"] == 1

        closed = data["profit_loss"]
        assert closed["sufficient_data"] is True
        assert closed["take_profit"]["count"] >= 1
        assert closed["stop_loss"]["count"] >= 1
        assert closed["take_profit"]["median_gain_pct"] > 0
        assert closed["stop_loss"]["median_loss_pct"] < 0

    def test_records_outside_the_window_are_excluded(self, app, make_user, add_trade):
        """창은 as_of 기준이다 — 마지막 체결 기준이 아니라."""
        user = make_user(email="stale@test.com")
        add_trade(user["id"], action="BUY", days_ago=200)
        add_trade(user["id"], action="SELL", days_ago=190, pnl_pct=5.0)
        with app.app_context():
            data = build_mirror_report(user["id"], period_days=30, as_of=AS_OF)

        # 반 년 전에 멈춘 유저에게 "그때의 30일" 을 이번 달로 내밀지 않는다.
        assert data["has_content"] is False
        assert data["window_trade_count"] == 0

    def test_as_of_accepts_a_date(self, app, active_user):
        """date 는 그 날의 끝으로 읽는다 — 그날의 체결이 빠지면 안 된다."""
        with app.app_context():
            data = build_mirror_report(active_user["id"], as_of=date(2026, 9, 17))
        assert data["period_end"] == "2026-09-17"
        assert data["window_trade_count"] == 5

    def test_concentration_is_present(self, app, make_user, add_position):
        user = make_user(email="conc@test.com")
        add_position(user["id"], ticker="AAPL", shares=10.0, avg_cost=150.0)
        with app.app_context():
            data = build_mirror_report(user["id"], as_of=AS_OF)

        conc = data["concentration"]
        assert conc["sufficient_data"] is True
        assert conc["ticker_count"] == 1
        assert conc["max_weight_pct"] == 100.0
        # 보유분만 있고 기간 안 기록이 없으면 보낼 리포트가 아니다.
        assert data["has_content"] is False

    def test_no_score_or_grade_anywhere(self, app, active_user):
        """점수·등급·순위 필드가 없다. 제품의 공개 약속이다."""
        with app.app_context():
            data = build_mirror_report(active_user["id"], as_of=AS_OF)

        offenders: list[str] = []
        # 토큰 단위로 본다 — "period_start" 가 "star" 로 걸리면 가드가 아니라 소음이다.
        banned_tokens = {
            "score", "scores", "grade", "grades", "rank", "ranking",
            "rating", "star", "stars", "점수", "등급", "순위",
        }

        def walk(node, path=""):
            if isinstance(node, dict):
                for key, value in node.items():
                    tokens = set(re.split(r"[_\W]+", str(key).lower()))
                    if tokens & banned_tokens:
                        offenders.append(f"{path}.{key}")
                    walk(value, f"{path}.{key}")
            elif isinstance(node, list):
                for i, value in enumerate(node):
                    walk(value, f"{path}[{i}]")

        walk(data)
        assert offenders == [], f"score-like keys in report data: {offenders}"

    def test_scorer_is_not_imported(self):
        """services.behavior.scorer 는 이 기능의 의존이 아니다."""
        import services.reports.mirror_pdf as module

        source = open(module.__file__, encoding="utf-8").read()
        assert "from services.behavior.scorer" not in source
        assert "import scorer" not in source


# ── 렌더 (HTML — weasyprint 불필요) ──────────────────────────────────

def _html_for(app, user_id, locale="ko"):
    with app.app_context():
        data = build_mirror_report(user_id, as_of=AS_OF)
    return render_mirror_html(data, locale=locale)


def _visible_text(html: str) -> str:
    """스타일·스크립트·주석을 걷어낸 사람이 읽는 텍스트."""
    body = re.sub(r"(?is)<(style|script).*?</\1>", " ", html)
    body = re.sub(r"(?s)<!--.*?-->", " ", body)
    body = re.sub(r"(?s)<[^>]+>", " ", body)
    return re.sub(r"\s+", " ", body)


class TestRenderHtml:
    @pytest.mark.parametrize("locale", LOCALES)
    def test_disclaimer_is_the_sot_text(self, app, active_user, locale):
        html = _html_for(app, active_user["id"], locale)
        assert DISCLAIMER_MIRROR_RETROSPECTIVE_KR in html
        assert DISCLAIMER_ARTIFACT_KR in html

    @pytest.mark.parametrize("locale", LOCALES)
    def test_no_forbidden_directive_vocabulary(self, app, active_user, locale):
        """FORBIDDEN_DIRECTIVE_TERMS 전수 — 면책 문구까지 포함해 통과해야 한다."""
        text = _visible_text(_html_for(app, active_user["id"], locale)).lower()
        hits = sorted(term for term in FORBIDDEN_DIRECTIVE_TERMS if term in text)
        assert hits == [], f"[{locale}] forbidden directive terms rendered: {hits}"

    @pytest.mark.parametrize("locale", LOCALES)
    def test_spec_banned_words_absent(self, app, active_user, locale):
        text = _visible_text(_html_for(app, active_user["id"], locale))
        assert _SPEC_BANNED_RE.search(text) is None, (
            f"[{locale}] banned word rendered: {_SPEC_BANNED_RE.search(text).group(0)!r}"
        )

    @pytest.mark.parametrize("locale", LOCALES)
    def test_empty_report_still_renders(self, app, make_user, locale):
        user = make_user(email=f"blank-{locale}@test.com")
        html = _html_for(app, user["id"], locale)
        assert DISCLAIMER_MIRROR_RETROSPECTIVE_KR in html
        text = _visible_text(html)
        # 숫자가 없어도 한계 고지와 면책은 그대로 나간다.
        assert "—" in text or "0" in text

    def test_sections_are_present(self, app, active_user):
        text = _visible_text(_html_for(app, active_user["id"], "ko"))
        for heading in (
            "월간 거울 리포트",
            "기록한 체결",
            "이미 보유한 종목을 다시 취득한 기록",
            "기간 안에서 닫힌 거래",
            "생성 시점의 보유 집중",
            "이 숫자가 말하지 않는 것",
            "면책 고지",
        ):
            assert heading in text, f"missing section: {heading}"

    def test_recorded_numbers_are_rendered(self, app, active_user):
        text = _visible_text(_html_for(app, active_user["id"], "ko"))
        assert "KRW" in text and "USD" in text
        assert "2026-09-17" in text

    def test_unknown_locale_falls_back_to_korean(self, app, active_user):
        html = _html_for(app, active_user["id"], "fr")
        assert "월간 거울 리포트" in html


# ── 렌더 (PDF — weasyprint 필요) ─────────────────────────────────────

def _pdf_or_skip(data, locale="ko") -> bytes:
    pytest.importorskip("weasyprint", reason="weasyprint native libs unavailable")
    try:
        return render_mirror_pdf(data, locale=locale)
    except OSError as exc:  # macOS: dlopen libgobject (HANDOVER.md)
        pytest.skip(f"weasyprint cannot render here: {exc}")


class TestRenderPdf:
    def test_pdf_bytes(self, app, active_user):
        with app.app_context():
            data = build_mirror_report(active_user["id"], as_of=AS_OF)
        pdf = _pdf_or_skip(data)
        assert isinstance(pdf, bytes)
        assert pdf.startswith(b"%PDF")
        assert len(pdf) > 1000

    def test_empty_report_renders_a_pdf(self, app, make_user):
        user = make_user(email="blankpdf@test.com")
        with app.app_context():
            data = build_mirror_report(user["id"], as_of=AS_OF)
        assert data["has_content"] is False
        assert _pdf_or_skip(data).startswith(b"%PDF")

    def test_pdf_text_carries_disclaimer_and_no_banned_words(self, app, active_user):
        pdfplumber = pytest.importorskip("pdfplumber")
        with app.app_context():
            data = build_mirror_report(active_user["id"], as_of=AS_OF)
        pdf = _pdf_or_skip(data)

        import io

        with pdfplumber.open(io.BytesIO(pdf)) as doc:
            text = "\n".join(page.extract_text() or "" for page in doc.pages)
        flat = re.sub(r"\s+", " ", text)

        assert DISCLAIMER_MIRROR_RETROSPECTIVE_KR.replace(" ", "") in flat.replace(" ", "")
        assert _SPEC_BANNED_RE.search(flat) is None
        lowered = flat.lower()
        hits = sorted(term for term in FORBIDDEN_DIRECTIVE_TERMS if term in lowered)
        assert hits == [], f"forbidden directive terms in PDF text: {hits}"


def test_spec_banned_list_is_covered_by_the_regex():
    """가드의 가드 — 명세의 여섯 낱말을 regex 가 실제로 잡는지."""
    for word in _SPEC_BANNED:
        assert _SPEC_BANNED_RE.search(word) is not None, word
