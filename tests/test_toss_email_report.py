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
    unstyled — so the ones that establish the dark ground must all have one."""
    page = render_email_html(report, url=URL)
    for tag in re.findall(r"<div(?![^>]*style=)[^>]*>", page):
        pytest.fail(f"div without inline style: {tag}")
    assert page.count('style="') > 40


def test_bars_are_table_cells_with_a_width_not_a_drawing(report):
    page = render_email_html(report, url=URL)
    bars = re.findall(r'<td width="([\d.]+)%" style="background:#B8956A', page)
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
    assert "전체 리포트 열기" not in page
    assert "<a " not in page
    # the digest still stands on its own
    assert "기록이 되비추는 것" in page
