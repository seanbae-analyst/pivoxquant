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
    # holdings · timeline · KR-US split · cumulative · scatter · attribution
    # · slope · matrix — eight page-width drawings, eight different marks —
    # plus one average-cost track per symbol card
    assert page.count('<div class="tbl"><svg') == 8
    sy = _report()["analysis"]["symbols"]
    # every card with a fill gets a track — one fill still says where the
    # average sits against today. The odd card out is padded with an empty
    # cell so the table's last row keeps its columns.
    assert page.count('<svg class="spark"') == sum(1 for c in sy["cards"] if c["track"])
    assert page.count('<div class="card">') == len(sy["cards"]) + len(sy["cards"]) % 2
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
    assert ">전체 이력<" in page        # the statement's own basis column
    assert "<b>전체 이력</b> · 수수료·세금 차감" in page


def test_markdown_emphasis_in_shared_reason_strings_becomes_html_not_asterisks():
    from services.toss.html_report import _em
    assert _em("빠진 매수는 없다 — **--since 를 넓혀도 닫히지 않는다**") == (
        "빠진 매수는 없다 — <strong>--since 를 넓혀도 닫히지 않는다</strong>")
    # escaping happens first, so a reason can never inject a tag
    assert _em("<script>x</script>") == "&lt;script&gt;x&lt;/script&gt;"


def test_paper_mode_puts_the_whole_document_on_the_report_surface():
    """The charts write literal fills, so the ground being a parameter has to
    reach them too, not only the stylesheet. Neither ground is an inversion of
    the other: the marks are re-stepped for each."""
    from services.toss.html_report import SCREEN, STOCK
    paper, screen = _page(paper=True), _page()
    for lamp in (SCREEN.ground, SCREEN.ink, SCREEN.mark):
        assert lamp in screen and lamp not in paper, lamp
    for stock in (STOCK.ground, STOCK.ink, STOCK.mark, STOCK.rise, STOCK.fall):
        assert stock in paper, stock
    assert "color-scheme: light" in paper and "color-scheme: dark" in screen
    assert paper.count("<svg") == screen.count("<svg")


def test_korean_comes_from_one_host_and_never_from_a_dynamic_subset():
    """Pretendard's dynamic subset is ~250 unicode-range faces, and a renderer
    that ignores the ranges paints hangul from whichever slice it loaded — the
    text arrives as *other* hangul, which reads as writing and so hides the bug.
    IBM Plex Sans KR is one face from the one host every renderer here reaches."""
    both = _page() + _page(paper=True)
    assert "jsdelivr" not in both and "pretendard" not in both.lower()
    assert both.count("IBM+Plex+Sans+KR") == 2


def test_the_page_carries_no_dashboard_furniture():
    """The layout language is a brokerage statement, not a dashboard. The tile
    grid, the accent-railed callout boxes, the uppercase eyebrow on every
    section and the centred italic sign-off were each a template tell, and each
    was also saying something twice — the headline sentences appeared at the top
    AND again inside 분석."""
    page = _page()
    for tell in ('class="tiles"', 'class="tile"', 'class="head"', 'class="eyebrow"',
                 'class="sig"', 'class="status"', 'class="lede"', 'text-align:center'):
        assert tell not in page, tell
    assert page.count('<table class="stmt">') >= 2
    assert page.count('class="lead"') == 1


def test_the_lead_finding_is_stated_once_not_twice():
    rep = _report()
    heads = rep["analysis"]["headline"]
    page = render_mirror_html(rep)
    assert heads[0] in page
    # each finding appears exactly once in the document
    for line in heads:
        assert page.count(line) == 1, line


def test_each_measurement_gets_the_mark_its_data_asks_for():
    """The record was four bar charts. A total accumulating over time is a line;
    a distribution is points; a before-and-after from one origin is a slope; two
    categorical dimensions that interact are a matrix. None of those is a bar."""
    from services.toss.html_report import (
        SCREEN, _cumulative_svg, _matrix_svg, _slope_svg, _trade_scatter_svg)
    rep = _report()
    an = rep["analysis"]
    assert "<path" in _cumulative_svg(an["trades"]["sales"], SCREEN)          # step line
    assert "<circle" in _trade_scatter_svg(an["trades"]["sales"], SCREEN)     # points
    assert "<line" in _slope_svg(an["after_selling"]["rows"], SCREEN)         # slopes
    assert "<rect" in _matrix_svg(an["timing"], SCREEN)                       # cells
    # and never a drawing of nothing
    assert _cumulative_svg([], SCREEN) == ""
    assert _trade_scatter_svg(an["trades"]["sales"][:1], SCREEN) == ""
    assert _slope_svg([], SCREEN) == ""
    assert _matrix_svg({"fills": 0}, SCREEN) == ""


def test_the_record_does_not_wear_the_product_s_tokens():
    """PivoxReport is a personal instrument, not a product surface. Dressing it
    as the app made it read as the app's marketing rather than as a measurement,
    so it has its own identity — and none of v3's."""
    both = _page() + _page(paper=True)
    for v3 in ("#050505", "#F5F0E8", "#B8956A", "#D18888", "#7AA0C8",
               "Playfair", "Source Serif", "Geist", "Pretendard"):
        assert v3 not in both, v3
    assert "Fraunces" in both and "IBM+Plex" in both


def test_every_drawing_scrolls_inside_its_own_container():
    """A phone is 390 CSS px and the page-width drawings are 600 at their
    smallest legible size, so each has to scroll inside something. Four of the
    eight used to be emitted bare — instead of scrolling they widened the
    document, and every line of text on the page went off-screen with them.

    The card tracks are the exception and must stay the exception: they are
    drawn at 344 to fit the phone outright, so putting one in a scroller would
    give it a scrollbar it can never use."""
    from services.toss.html_report import SCREEN, _split_bar_svg
    page = _page()
    wide = page.count("<svg") - page.count('<svg class="spark"')
    assert page.count('<div class="tbl"><svg') == wide == 8
    assert '<div class="tbl"><svg class="spark"' not in page
    assert _split_bar_svg(30.0, 70.0, SCREEN).startswith('<div class="tbl"><svg')


def test_the_page_is_laid_out_for_the_phone_it_is_read_on():
    css = _page()
    assert "@media (max-width:440px)" in css     # iPhone 14 is 390
    assert "@media (max-width:640px)" in css     # two-cell heads stack first
    # the plate-number margin is what a narrow screen cannot afford
    assert ".body {{ padding-left:0; }}".replace("{{", "{").replace("}}", "}") in css
