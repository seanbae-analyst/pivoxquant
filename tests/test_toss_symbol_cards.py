"""One symbol at a time — the average-cost track and the card that carries it.

Everything else in the report crosses the whole account. These tests cover the
one section that does not: what each purchase did to that symbol's average,
whether the position was ever emptied and re-entered, and how the drawing
survives the two renderers it has to survive.
"""
from __future__ import annotations

from decimal import Decimal

from services.toss.analysis import attribution, per_symbol
from services.toss.history import fills_from_orders, reconstruct
from services.toss.html_report import SCREEN, STOCK, _track_svg, _typeset

FX = Decimal("1350")


def _order(oid, sym, side, qty, px, at, cur="KRW"):
    return {"orderId": oid, "symbol": sym, "side": side, "status": "FILLED", "currency": cur,
            "orderedAt": at, "execution": {"filledQuantity": str(qty), "averageFilledPrice": str(px),
                                           "filledAmount": str(qty * px), "commission": "0",
                                           "tax": "0", "filledAt": at}}


def _cards(orders, holdings=()):
    book = reconstruct(fills_from_orders(orders))
    rows = list(holdings)
    a = attribution(book, rows, FX, {})
    return {c["symbol"]: c for c in per_symbol(book, rows, FX, {}, a["rows"])["cards"]}


# ── the track ────────────────────────────────────────────────────────────────
def test_the_running_average_is_recorded_at_every_fill_not_just_at_the_end():
    """The broker shows today's average. Where it came from is the whole point
    of the drawing, and it exists only if each fill records where it landed."""
    c = _cards([
        _order("1", "005930", "BUY", 10, 70000, "2025-01-10T09:30:00+09:00"),
        _order("2", "005930", "BUY", 10, 50000, "2025-03-10T09:30:00+09:00"),
    ])["005930"]
    assert [t["avg_after"] for t in c["track"]] == [70000.0, 60000.0]
    assert c["avg_first"] == 70000.0 and c["avg_now"] == 60000.0
    assert c["follow_on"] == {"below": 1, "above": 0, "flat": 0}


def test_a_sale_does_not_move_the_average_but_emptying_the_position_ends_it():
    c = _cards([
        _order("1", "AAPL", "BUY", 10, 100, "2025-01-10T23:30:00+09:00", "USD"),
        _order("2", "AAPL", "SELL", 4, 130, "2025-02-10T23:30:00+09:00", "USD"),
        _order("3", "AAPL", "SELL", 6, 140, "2025-03-10T23:30:00+09:00", "USD"),
    ])["AAPL"]
    assert [t["avg_after"] for t in c["track"]] == [100.0, 100.0, None]


def test_buying_back_in_after_a_liquidation_is_a_re_entry_not_a_follow_on():
    """Averaging down and coming back to a symbol are different acts, and the
    difference is invisible unless the emptying is noticed."""
    c = _cards([
        _order("1", "035420", "BUY", 5, 200000, "2025-01-10T09:30:00+09:00"),
        _order("2", "035420", "SELL", 5, 220000, "2025-02-10T09:30:00+09:00"),
        _order("3", "035420", "BUY", 5, 180000, "2025-04-01T09:30:00+09:00"),
    ], [{"symbol": "035420", "name": "NAVER", "weight_pct": 100.0, "held_days": 40,
         "unrealised_rate_pct": 2.0, "market_value_krw": 918000, "purchase_amount_krw": 900000}])["035420"]
    assert c["reentries"] == 1
    assert c["gap_days"] == 50.0
    # the re-entry is not counted as a purchase into an existing position
    assert c["follow_on"] == {"below": 0, "above": 0, "flat": 0}
    assert "다시 샀다" in c["note"]


def test_the_note_says_nothing_when_the_symbol_has_no_pattern():
    c = _cards([_order("1", "TSLA", "BUY", 1, 300, "2025-01-10T23:30:00+09:00", "USD")])["TSLA"]
    assert c["note"] is None


def test_held_symbols_come_first_and_departed_ones_by_what_they_moved():
    orders = [
        _order("1", "AAA", "BUY", 1, 1000, "2025-01-10T09:30:00+09:00"),
        _order("2", "BBB", "BUY", 1, 5000, "2025-01-10T09:30:00+09:00"),
        _order("3", "BBB", "SELL", 1, 9000, "2025-02-10T09:30:00+09:00"),
        _order("4", "CCC", "BUY", 1, 5000, "2025-01-10T09:30:00+09:00"),
        _order("5", "CCC", "SELL", 1, 4000, "2025-02-10T09:30:00+09:00"),
    ]
    book = reconstruct(fills_from_orders(orders))
    rows = [{"symbol": "AAA", "name": "", "weight_pct": 100.0, "held_days": 30, "unrealised_rate_pct": 1.0,
             "market_value_krw": 1010, "purchase_amount_krw": 1000}]
    a = attribution(book, rows, FX, {})
    sy = per_symbol(book, rows, FX, {}, a["rows"])
    assert [c["symbol"] for c in sy["cards"]] == ["AAA", "BBB", "CCC"]
    assert sy["held_shown"] == 1 and sy["folded"] == 0


# ── the drawing ──────────────────────────────────────────────────────────────
def test_the_track_is_narrow_enough_for_the_narrowest_card_it_can_land_in():
    """An A4 column halved is ~316px of card, and WeasyPrint lays a viewBox'd
    SVG out at its intrinsic width and then clips rather than scaling it. A
    wider drawing loses its right-hand figures in the PDF and only there."""
    c = _cards([
        _order("1", "005930", "BUY", 10, 70000, "2025-01-10T09:30:00+09:00"),
        _order("2", "005930", "BUY", 10, 50000, "2025-03-10T09:30:00+09:00"),
    ])["005930"]
    svg = _track_svg(c, STOCK)
    assert 'viewBox="0 0 300 94"' in svg
    assert svg.startswith('<svg class="spark"')      # never inside a scroller


def test_svg_type_is_stamped_on_the_element_because_the_pdf_cannot_read_css():
    """`svg text { font-size: 10.5px }` in the stylesheet is screen-only:
    WeasyPrint's SVG engine reads presentation attributes and nothing else, so
    without this every annotation printed at the 16px UA default in black and
    ran outside its own viewBox.

    The colour goes on as an inline style, not an attribute: an attribute loses
    to the class rule in the stylesheet, so on screen it would repaint every
    deliberate colour back to the class default."""
    out = _typeset('<text class="fig">1</text><text>2</text>'
                   '<text class="lbl" style="fill:#123456">3</text>', SCREEN)
    assert "font-size='11'" in out and f'style="fill:{SCREEN.ink2}"' in out
    assert "font-size='10.5'" in out and f'style="fill:{SCREEN.ink3}"' in out
    # a colour the drawing chose on purpose survives, and is not doubled
    assert out.count("fill:#123456") == 1 and f"fill:{SCREEN.ink}" not in out


def test_the_two_palettes_reach_the_drawing_rather_than_the_stylesheet():
    c = _cards([
        _order("1", "005930", "BUY", 10, 70000, "2025-01-10T09:30:00+09:00"),
        _order("2", "005930", "SELL", 10, 80000, "2025-03-10T09:30:00+09:00"),
    ])["005930"]
    assert STOCK.mark in _track_svg(c, STOCK)
    assert SCREEN.mark in _track_svg(c, SCREEN)
    assert STOCK.mark not in _track_svg(c, SCREEN)


def test_a_position_still_held_runs_to_today_not_to_its_last_purchase():
    """Buy once and keep it and the last fill is the last date there is. Ending
    the axis there gives the whole holding zero width and draws no line at all."""
    from datetime import date
    c = _cards([_order("1", "AAPL", "BUY", 8, 190, "2025-01-10T23:30:00+09:00", "USD")],
               [{"symbol": "AAPL", "name": "Apple Inc.", "weight_pct": 100.0, "held_days": 240,
                 "unrealised_rate_pct": 27.9, "market_value_krw": 2_600_000,
                 "purchase_amount_krw": 2_030_000}])["AAPL"]
    svg = _track_svg(c, STOCK, date(2025, 9, 10))
    assert ">25.01<" in svg and ">25.09<" in svg      # both ends stamped
    assert "<polyline" in svg                          # and there is a line to see
    # without today the axis is one day wide and the two stamps collapse to one
    assert _track_svg(c, STOCK).count("<text") < svg.count("<text")


# ── Korean on paper ──────────────────────────────────────────────────────────
def test_korean_words_are_unbreakable_on_paper_because_weasyprint_ignores_keep_all():
    """`word-break: keep-all` is in the stylesheet and WeasyPrint does not
    implement it — measured, it splits 오르내린기록이다 after the first syllable
    with the rule exactly as without it. Paper wraps each word instead.

    The screen page must not carry the spans: browsers honour the rule, and the
    markup is for the renderer that cannot."""
    import json
    import os
    from datetime import datetime

    from services.toss.html_report import render_mirror_html
    from services.toss.mirror_report import build_mirror_report

    fix = os.path.join(os.path.dirname(__file__), "fixtures", "toss", "sample_raw_history.json")
    with open(fix, encoding="utf-8") as fh:
        raw = json.load(fh)
    rep = build_mirror_report(
        account=raw["account"], holdings=raw["holdings"], closed_orders=raw["closed_orders"],
        open_orders=raw["open_orders"], fx=raw["fx"], history_since=raw["history_since"],
        window_days=90, names=raw["names"], prices=raw.get("prices"),
        as_of=datetime.fromisoformat(raw["fetched_at"]))
    screen, paper = render_mirror_html(rep), render_mirror_html(rep, paper=True)
    assert '<span class="kr">' not in screen
    assert paper.count('<span class="kr">') > 100
    assert ".kr {" in paper.replace("{{", "{")


def test_the_drawings_and_the_stylesheet_never_get_a_span_inside_them():
    """SVG has no <span>, so one inside a <text> is broken markup — and CSS with
    one inside is a broken stylesheet."""
    from services.toss.html_report import _keep_all
    out = _keep_all('<p>정리한 종목</p><svg><text>정리한 종목</text></svg>'
                    '<style>/* 정리한 종목 */</style><p>남은 것</p>')
    assert out.count('<span class="kr">') == 4          # two words in each <p>, none between
    assert "<text>정리한 종목</text>" in out
    assert "<style>/* 정리한 종목 */</style>" in out
