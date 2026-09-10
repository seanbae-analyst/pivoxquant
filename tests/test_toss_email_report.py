"""PivoxReport as an email digest.

The tests here are mostly about what must NOT be in the output: an inbox
strips or blocks most of what the browser page relies on, and a digest
that renders blank in Gmail is worse than no digest at all.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime

import pytest

from services.toss.email_report import render_email_html, render_email_text
from services.toss.email_report import PAPER, PAPER_INK
from services.toss.html_report import SCREEN
from services.toss.mirror_report import build_mirror_report

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "toss", "sample_raw_history.json")
URL = "https://example.invalid/report"


@pytest.fixture
def report():
    with open(FIX, encoding="utf-8") as fh:
        raw = json.load(fh)
    return build_mirror_report(
        account=raw["account"], holdings=raw["holdings"], closed_orders=raw["closed_orders"],
        open_orders=raw["open_orders"], fx=raw["fx"], history_since=raw["history_since"],
        window_days=90, names=raw["names"], prices=raw.get("prices"),
        as_of=datetime.fromisoformat(raw["fetched_at"]),
    )


def test_carries_nothing_an_inbox_strips_or_blocks(report):
    """No SVG (Gmail blocks it outright), no external stylesheet or <style>
    block (dropped or unreliable), no CSS variables (unsupported), no external
    image (blocked until the reader asks for it)."""
    page = render_email_html(report, url=URL)
    for hostile in ("<svg", "<link", "<style", "var(--", "<img", "<script"):
        assert hostile not in page, hostile


def test_every_element_that_paints_carries_its_own_style(report):
    """With no stylesheet surviving, a tag without an inline style renders
    unstyled — so every one of them must carry its own."""
    page = render_email_html(report, url=URL)
    for tag in re.findall(r"<div(?![^>]*style=)[^>]*>", page):
        pytest.fail(f"div without inline style: {tag}")
    assert page.count('style="') > 40


def test_bars_are_table_cells_with_a_width_not_a_drawing(report):
    page = render_email_html(report, url=URL)
    from services.toss.email_report import PAPER_MARK
    bars = re.findall(rf'<td width="([\d.]+)%" bgcolor="{PAPER_MARK}"', page)
    assert len(bars) == len(report["holdings"])
    assert all(0 <= float(w) <= 100 for w in bars)


def test_the_figures_match_the_report_it_summarises(report):
    page = render_email_html(report, url=URL)
    text = render_email_text(report, url=URL)
    equity = f"₩{int(round(report['valuation']['equity_value_krw'])):,}"
    realised = f"₩{int(round(report['history']['realised_net_krw'])):,}"
    for out in (page, text):
        assert equity in out and realised in out
        for line in report["analysis"]["headline"]:
            assert line in out
    assert URL in page and URL in text


def test_the_account_number_is_masked_and_the_vocabulary_line_holds(report):
    page = render_email_html(report, url=URL)
    assert report["account"]["account_no_masked"] in page
    assert "12345678901" not in page
    for word in ("추천", "조언", "권유", "물타기", "점수"):
        assert word not in page, word


def test_the_link_block_is_omitted_when_there_is_nowhere_to_link(report):
    page = render_email_html(report)
    assert "웹에서 열기" not in page
    assert "<a " not in page
    # the digest still stands on its own
    assert "기록이 되비추는 것" in page


def test_the_ground_is_paper_and_the_text_is_ink(report):
    """The bug this palette exists to fix: an ivory-on-Vantablack email meets
    Gmail's dark-mode transform, which pushes the two toward each other until
    the message is blank. Light ground, dark text is what survives it — and it
    is what globals.css already decided every export surface should be."""
    page = render_email_html(report, url=URL)
    assert SCREEN.ground not in page and SCREEN.ink not in page   # no lamp-side ground
    assert page.count(f'bgcolor="{PAPER}"') >= 2          # attribute, not only CSS
    assert PAPER_INK in page
    # every colour that carries text is opaque, so a client that repaints the
    # ground cannot drag the text along with it
    assert "rgba(" not in page


def test_the_pdf_is_what_the_reader_is_pointed_at_not_the_link(report):
    """A private page opened from an inbox has no session and renders as
    nothing, so the attachment — not the link — is the way in."""
    with_pdf = render_email_html(report, url=URL, attached=True)
    assert "첨부한 PDF" in with_pdf
    assert "로그인" in with_pdf                            # the link is labelled honestly
    assert "첨부한 PDF" in render_email_text(report, attached=True)
    assert "첨부한 PDF" not in render_email_html(report, url=URL)


def test_no_dashboard_furniture_and_korean_breaks_at_word_boundaries(report):
    """Same rebuild as the browser page: a statement block instead of a 2x2 tile
    grid, section heads that carry a count instead of an uppercase eyebrow, and
    no centred italic sign-off. Plus keep-all, without which Korean wraps inside
    a word — "손실은" split across two lines."""
    page = render_email_html(report, url=URL)
    assert "text-transform:uppercase" not in page
    assert "font-style:italic" not in page
    assert "text-align:center" not in page
    assert page.count("word-break:keep-all") > 8
    # the statement rules off where a 잔고 statement does
    assert page.count("border-top:1.5px solid") >= 2
