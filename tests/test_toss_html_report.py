"""PivoxReport HTML — the same report dict, drawn. Structure and vocabulary only;
the numbers are tested where they are computed."""
from __future__ import annotations

import json
import os
from datetime import datetime

from services.toss.html_report import render_mirror_html
from services.toss.mirror_report import build_mirror_report

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "toss", "sample_raw_history.json")


def _report():
    with open(FIX, encoding="utf-8") as fh:
        raw = json.load(fh)
    rep = build_mirror_report(
        account=raw["account"], holdings=raw["holdings"], closed_orders=raw["closed_orders"],
        open_orders=raw["open_orders"], fx=raw["fx"], history_since=raw["history_since"],
        window_days=90, names=raw["names"], prices=raw.get("prices"), as_of=datetime.fromisoformat(raw["fetched_at"]),
    )
    return rep


def _page(**kw):
    return render_mirror_html(_report(), **kw)


def test_html_draws_the_three_charts_and_names_every_symbol():
    page = _page()
    assert page.count("<svg") == 5                      # holdings rows · timeline · KR/US split · attribution · timing
    assert "팔고 난 뒤" in page and "엔비디아 (NVDA)" in page
    assert "삼성전자 (005930)" in page and "Apple Inc. (AAPL)" in page and "엔비디아 (NVDA)" in page
    assert "토스 잔고와 전부 일치" in page


def test_html_keeps_the_vocabulary_line_and_runs_nothing():
    page = _page()
    for word in ("추천", "조언", "권유", "물타기", "HHI", "회전율", "점수"):
        assert word not in page, word
    assert "12345678901" not in page
    assert "<script" not in page


def test_the_realised_tile_agrees_with_the_verdict_above_it():
    """A finding that leaves the cost basis intact must not make the tile say
    the total is partial while the status block says it is whole."""
    page = _page()
    assert "부분 이력" not in page      # the fixture reconciles completely
    assert "전체 이력 · 수수료·세금 차감" in page


def test_markdown_emphasis_in_shared_reason_strings_becomes_html_not_asterisks():
    from services.toss.html_report import _em
    assert _em("빠진 매수는 없다 — **--since 를 넓혀도 닫히지 않는다**") == (
        "빠진 매수는 없다 — <strong>--since 를 넓혀도 닫히지 않는다</strong>")
    # escaping happens first, so a reason can never inject a tag
    assert _em("<script>x</script>") == "&lt;script&gt;x&lt;/script&gt;"


def test_paper_mode_puts_the_whole_document_on_the_report_surface():
    """globals.css: "Light-theme ivory paper, regardless of app dark mode. Use on
    printable/export views." The charts write literal fills, so the ground being
    a parameter has to reach them too, not only the stylesheet."""
    from services.toss.html_report import BRONZE, INK, IVORY, PAPER, PAPER_BRONZE, PAPER_INK
    paper, screen = _page(paper=True), _page()
    assert INK in screen and IVORY in screen and BRONZE in screen
    for app_chrome in (INK, IVORY, BRONZE):
        assert app_chrome not in paper, app_chrome
    assert PAPER in paper and PAPER_INK in paper and PAPER_BRONZE in paper
    assert "color-scheme: light" in paper and "color-scheme: dark" in screen
    assert paper.count("<svg") == screen.count("<svg") == 5


def test_paper_drops_the_dynamic_subset_webfont_that_pdf_renderers_mis_map():
    """Pretendard's dynamic subset is ~250 unicode-range faces. A renderer that
    ignores the ranges paints hangul from whichever slice it loaded — the text
    comes out as *other* hangul, which reads as writing and so hides the bug."""
    assert "pretendard" in _page()
    assert "pretendard" not in _page(paper=True)
