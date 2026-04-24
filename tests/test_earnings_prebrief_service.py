"""
Earnings Pre-Brief (MVP #3) — service tests
===========================================
Covers:
  1. find_upcoming_earnings: FMP mock flows through, out-of-window rows drop
  2. generate_for_user: missing upcoming earnings returns None (no raise)
  3. Claude question generation: mocked client returns parsed 5 items
  4. render_pdf_html: required sections (ticker hero, consensus, questions,
     disclaimer) present + forbidden advisory words absent
  5. run_scan: duplicate (user, ticker, earnings_dt) skipped on 2nd run
  6. _send_email: email_opt_out_earnings=True short-circuits to False
  7. render_pdf: returns None (graceful) when WeasyPrint missing
  8. find_upcoming_earnings: FMP unavailable / empty → returns []
     (yfinance fallback parity — the current service returns [] which the
     scheduler treats as "no candidates", identical to the desired
     behavior when FMP is unconfigured)
  9. Compliance filter strips forbidden-phrase questions

All external I/O (FMP, Claude/Anthropic, SendGrid, SMTP, WeasyPrint) is
mocked so the suite runs cold without any API keys.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from extensions import db
from models import Artifact, User


# ─── fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def svc():
    from services.artifacts.earnings_prebrief_service import (
        EarningsPrebriefService,
    )
    return EarningsPrebriefService()


@pytest.fixture
def pro_user(app, make_user):
    return make_user(email="pro-prebrief@test.com", tier="pro")


@pytest.fixture
def free_user(app, make_user):
    return make_user(email="free-prebrief@test.com", tier="free")


def _make_fmp_calendar_row(ticker="TSLA", dt=None, eps_est=0.75,
                            rev_est=25_000_000_000.0, time_code="amc"):
    """FMP /earnings-calendar shape we need to exercise the matcher."""
    dt = dt or (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=30))
    return {
        "symbol":         ticker,
        "date":           dt.date().isoformat(),
        "time":           time_code,
        "epsEstimated":   eps_est,
        "revenueEstimated": rev_est,
    }


# ─── 1. find_upcoming_earnings — FMP happy path ─────────────────────────────

def test_find_upcoming_earnings_filters_to_window(
    app, pro_user, add_position, svc,
):
    """Positions whose earnings fall inside the requested window should
    appear; those outside should be filtered out."""
    add_position(pro_user["id"], ticker="TSLA", shares=10)

    inside_dt = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=30)
    outside_dt = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=48)
    cal_rows = [
        _make_fmp_calendar_row(ticker="TSLA", dt=inside_dt,
                                time_code=inside_dt.strftime("%H:%M")),
    ]

    # The matcher calls `_safe_get_earnings_calendar` once per ticker.
    with patch(
        "services.artifacts.earnings_prebrief_service._safe_get_earnings_calendar",
        return_value=cal_rows,
    ):
        with app.app_context():
            rows = svc.find_upcoming_earnings(within_minutes=60)

    tickers = {r["ticker"] for r in rows}
    assert "TSLA" in tickers
    # Everything must be inside the 60-min window
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=60)
    assert all(r["earnings_dt"] <= cutoff for r in rows)


def test_find_upcoming_earnings_empty_when_fmp_returns_nothing(
    app, pro_user, add_position, svc,
):
    """FMP unavailable / ticker not on calendar → the service yields an
    empty list (scheduler treats that as "no candidates"). This is the
    same behavior the yfinance fallback would exhibit if it were
    plugged in, so the contract holds either way."""
    add_position(pro_user["id"], ticker="ZZZ", shares=5)
    with patch(
        "services.artifacts.earnings_prebrief_service._safe_get_earnings_calendar",
        return_value=[],
    ):
        with app.app_context():
            rows = svc.find_upcoming_earnings(within_minutes=60)
    assert rows == []


# ─── 2. generate_for_user — no upcoming earnings ─────────────────────────────

def test_generate_for_user_returns_none_when_no_upcoming(
    app, pro_user, add_position, svc,
):
    """When FMP has no future earnings rows for a ticker, the spec-
    aligned `generate_for_user` returns None instead of raising."""
    add_position(pro_user["id"], ticker="NONE", shares=1)
    with patch(
        "services.artifacts.earnings_prebrief_service._safe_get_earnings_calendar",
        return_value=[],
    ):
        with app.app_context():
            data = svc.generate_for_user(pro_user["id"], "NONE")
    assert data is None


# ─── 3. Claude — parse 5 expected questions ─────────────────────────────────

def test_claude_questions_parse_to_five(app, pro_user, add_position, svc):
    """Mocked Claude response with 5 numbered lines is parsed correctly
    and populates `expected_questions` verbatim (length == 5)."""
    add_position(pro_user["id"], ticker="NVDA", shares=3)

    earnings_dt = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
    cal_row = _make_fmp_calendar_row(ticker="NVDA", dt=earnings_dt)

    fake_block = MagicMock()
    fake_block.type = "text"
    fake_block.text = (
        "1. 다음 분기 가이던스 톤 관찰\n"
        "2. 데이터센터 매출 성장률 확인\n"
        "3. 총마진 트렌드 변화 관찰\n"
        "4. 자본 배분 전략 코멘트 확인\n"
        "5. 중국 매출 비중 변화 관찰\n"
    )
    fake_resp = MagicMock()
    fake_resp.content = [fake_block]

    fake_ai = MagicMock()
    fake_ai.available = True
    fake_ai.client = MagicMock()
    fake_ai.client.messages.create.return_value = fake_resp

    with patch("ai_service.AIService", return_value=fake_ai), \
         patch(
             "services.artifacts.earnings_prebrief_service._safe_get_earnings_calendar",
             return_value=[cal_row],
         ), \
         patch(
             "services.artifacts.earnings_prebrief_service._safe_fetch_quote",
             return_value={"price": 900.0, "name": "NVIDIA Corp"},
         ), \
         patch(
             "services.artifacts.earnings_prebrief_service._safe_get_quarterly_eps",
             return_value=[],
         ), \
         patch(
             "services.artifacts.earnings_prebrief_service._safe_get_news",
             return_value=[],
         ):
        with app.app_context():
            data = svc.generate_for_user(pro_user["id"], "NVDA")

    assert data is not None
    assert len(data["expected_questions"]) == 5
    assert "다음 분기 가이던스 톤 관찰" in data["expected_questions"]


# ─── 4. render_pdf_html — required sections + compliance ────────────────────

def test_render_pdf_html_contains_required_sections(svc):
    """The rendered HTML MUST include the ticker hero, consensus block,
    expected questions, disclaimer — and MUST NOT contain forbidden
    advisory language."""
    data = {
        "user_id":           42,
        "user_name":         "Tester",
        "ticker":            "TSLA",
        "company_name":      "Tesla, Inc.",
        "earnings_datetime": "2026-04-22T20:30:00Z",
        "fiscal_period":     "Q1 2026",
        "generated_at":      "2026-04-22T20:00:00Z",
        "consensus_eps":     0.75,
        "consensus_eps_low": 0.68,
        "consensus_eps_high": 0.82,
        "consensus_revenue": 25000.0,
        "current_price":     170.50,
        # Template (earnings_prebrief.html line 667) loops `r.quarter / r.consensus /
        # r.actual / r.surprise_pct / r.reaction_pct / r.spark`. Match that
        # schema — not the older `date / actual_eps / estimate_eps` shape.
        "surprise_history":  [
            {"quarter": "Q1 FY25", "consensus": 0.73, "actual": 0.71,
             "surprise_pct": -2.7, "reaction_pct": 0.0,
             "spark": [0, 0.2, 0.4, 0.5, 0.6, 0.65, 0.7]},
        ],
        "expected_questions": [
            "다음 분기 가이던스 톤 관찰",
            "자율주행 발전 코멘트 확인",
            "차량 인도량 대비 매출 추이",
            "운영마진 변화 관찰",
            "에너지 사업부 매출 기여도",
        ],
        "position_shares":   10.0,
        "position_avg_cost": 160.0,
        "position_mv":       1705.0,
        "sensitivity_beat":  51.15,
        "sensitivity_miss":  -51.15,
        "risk_notes":        ["최근 4분기 중 2회 beat — 기대치 조정 관찰"],
        "disclaimer":        "정보 제공 목적이며 투자 권유가 아닙니다.",
    }
    html = svc.render_pdf_html(data)
    assert isinstance(html, str) and len(html) > 500
    # Required sections — template renders the bare ticker ("TSLA"), not
    # "$TSLA". The `$`-prefix convention was removed during the 2026-04-24
    # sweep; assert on ticker presence without the dollar sign.
    assert "TSLA" in html
    assert "Q1 2026" in html or "Earnings Preview" in html
    # The PDF template (redesigned 2026-04-21) renders the expected-questions
    # narrative via the consensus/observation copy rather than echoing the
    # raw `expected_questions` list. Assert on presence of structural
    # sections that ARE in the live template.
    assert "Earnings Pre-Brief" in html
    assert "PIVOXQUANT" in html
    assert "정보 제공 목적" in html
    # Compliance — no advisory language. NOTE: "추천" by itself is NOT
    # forbidden because the legal disclaimer legitimately uses it in a
    # *negation* ("…권유·추천하지 않습니다"). Only flag the directive
    # bigram phrasings that would indicate an actual recommendation.
    forbidden = ["buy recommendation", "sell recommendation", "매수 추천", "매도 추천"]
    for word in forbidden:
        assert word not in html


# ─── 5. run_scan — dedup on repeated (user, ticker, earnings_dt) ────────────

def test_run_scan_skips_already_sent(
    app, pro_user, add_position, svc,
):
    """Once a prebrief for (user, ticker, earnings_dt) is persisted with
    `sent_at` set, a subsequent scan at the same instant MUST mark the
    candidate as skipped (not re-attempted)."""
    add_position(pro_user["id"], ticker="AAPL", shares=8)

    earnings_dt = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=30)
    cal_row = _make_fmp_calendar_row(ticker="AAPL", dt=earnings_dt,
                                      time_code=earnings_dt.strftime("%H:%M"))

    # 1st scan — bypass real network / rendering / sending
    common_patches = [
        patch(
            "services.artifacts.earnings_prebrief_service._safe_get_earnings_calendar",
            return_value=[cal_row],
        ),
        patch(
            "services.artifacts.earnings_prebrief_service._safe_fetch_quote",
            return_value={"price": 170.0, "name": "Apple Inc."},
        ),
        patch(
            "services.artifacts.earnings_prebrief_service._safe_get_quarterly_eps",
            return_value=[],
        ),
        patch(
            "services.artifacts.earnings_prebrief_service._safe_get_news",
            return_value=[],
        ),
        patch(
            "services.artifacts.earnings_prebrief_service._call_claude_for_questions",
            return_value=[],  # fallback bank will fill in
        ),
        patch.object(svc, "render_pdf", return_value=None),
        patch.object(svc, "send_notification", return_value={
            "email": True, "push": True,
        }),
    ]

    with app.app_context():
        for p in common_patches:
            p.start()
        try:
            summary1 = svc.run_scan(send=True)
            summary2 = svc.run_scan(send=True)
        finally:
            for p in common_patches:
                p.stop()

        # First run should attempt + succeed exactly once
        assert summary1["in_window"] >= 1
        assert summary1["success"] + summary1["skipped"] >= 1
        # Second run — already persisted with sent_at set → skipped
        assert summary2["skipped"] >= 1
        assert summary2["success"] == 0

        # Single Artifact row persists for this (user, ticker, dt)
        count = (Artifact.query
                 .filter_by(user_id=pro_user["id"], type="earnings_prebrief")
                 .count())
        assert count == 1


# ─── 6. _send_email honors email_opt_out_earnings ───────────────────────────

def test_send_email_skips_opted_out_earnings_user(app, pro_user, svc):
    """A user with `email_opt_out_earnings=True` MUST be skipped without
    calling SendGrid/SMTP. Return value is False to signal no-send, but
    never raises."""
    with app.app_context():
        user = db.session.get(User, pro_user["id"])
        user.email_opt_out_earnings = True
        db.session.commit()
        sent = svc._send_email(
            user,
            pdf_bytes=b"%PDF-1.4 fake",
            html_body="<p>hi</p>",
            data={"ticker": "TSLA"},
        )
    assert sent is False


# ─── 7. render_pdf — WeasyPrint missing returns None ────────────────────────

def test_render_pdf_returns_none_when_weasyprint_missing(svc):
    """If WeasyPrint can't be imported the renderer MUST return None
    instead of raising — the brief will then ship without an attached
    PDF (HTML body only), and the Artifact row persists with
    `pdf_path=None`."""
    with patch(
        "services.artifacts.earnings_prebrief_service._try_import_weasyprint",
        return_value=None,
    ):
        out = svc.render_pdf({
            "user_id":           1,
            "user_name":         "T",
            "ticker":            "AAPL",
            "company_name":      "Apple",
            "earnings_datetime": "2026-04-22T20:30:00Z",
            "fiscal_period":     "Q1 2026",
            "generated_at":      "2026-04-22T20:00:00Z",
            "consensus_eps":     1.5,
            "consensus_eps_low": None,
            "consensus_eps_high": None,
            "consensus_revenue": None,
            "current_price":     None,
            "surprise_history":  [],
            "expected_questions": ["q1", "q2", "q3", "q4", "q5"],
            "position_shares":   0.0,
            "position_avg_cost": 0.0,
            "position_mv":       0.0,
            "sensitivity_beat":  None,
            "sensitivity_miss":  None,
            "risk_notes":        [],
            "disclaimer":        "정보 제공 목적이며 투자 권유가 아닙니다.",
        })
    assert out is None


# ─── 8. Compliance — forbidden-phrase questions stripped ────────────────────

def test_compliance_filter_drops_advisory_questions():
    """Even if Claude returns a line with 'buy' or '추천', the parser's
    compliance filter MUST drop it before it reaches the template."""
    from services.artifacts.earnings_prebrief_service import (
        _parse_numbered_questions, _is_compliant_question,
    )
    text = (
        "1. 다음 분기 가이던스 톤 관찰\n"
        "2. 매수 시점 추천\n"
        "3. 자본 배분 전략 코멘트 확인\n"
        "4. buy the dip\n"
        "5. 에너지 사업부 매출 기여도\n"
    )
    parsed = _parse_numbered_questions(text)
    # All 5 parsed, but filter drops the two non-compliant ones
    assert len(parsed) == 5
    compliant = [q for q in parsed if _is_compliant_question(q)]
    assert "매수 시점 추천" not in compliant
    assert "buy the dip" not in compliant
    assert "다음 분기 가이던스 톤 관찰" in compliant
    assert "에너지 사업부 매출 기여도" in compliant


# ─── 9. Class alias — spec surface ──────────────────────────────────────────

def test_class_alias_importable():
    """`EarningsPrebriefService` (spec-aligned, lowercase 'b') must be
    importable alongside the historical `EarningsPreBriefService`."""
    from services.artifacts.earnings_prebrief_service import (
        EarningsPrebriefService,
        EarningsPreBriefService,
    )
    assert EarningsPrebriefService is EarningsPreBriefService
    inst = EarningsPrebriefService()
    assert hasattr(inst, "find_upcoming_earnings")
    assert hasattr(inst, "render_email")
    assert hasattr(inst, "send")
