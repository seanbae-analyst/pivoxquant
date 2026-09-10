"""PivoxReport — the same report as an email digest.

An inbox is not a browser. Gmail drops ``<link>``, is unreliable about a
``<style>`` block, blocks SVG outright, and has no CSS variables, grid or
flex — so none of :mod:`services.toss.html_report` survives the trip. This
module renders the same numbers under those constraints: tables for
layout, an inline ``style`` on every element, bars drawn as table cells
with a background colour and a percentage width, and web-safe families
behind the display face.

The ground is the product's report surface — ivory paper, printed ink —
and not the app's Vantablack. That is the same call ``globals.css`` already
made for every exportable surface ("we do NOT invert: printed reports don't
invert"), and an inbox is the reason it matters most: a phone in dark mode
hands Gmail a dark-on-dark email and its colour transform pushes the ivory
text toward the ivory ground until the page is blank. Light ground, dark
text is the one combination every client's transform leaves readable.

It is a digest, not the report. The figures a person wants on a phone go
here; the full report — charts, per-symbol history, the analysis tables —
rides along as the attached PDF, which needs no session, no network and no
webfont, and so is readable wherever the mail is.
"""
from __future__ import annotations

import html

from services.toss.html_report import STOCK, _nm

# One palette, defined once, in html_report. The digest is the same record.
PAPER = STOCK.ground
PAPER_INK = STOCK.ink
PAPER_RULE = STOCK.grid
PAPER_BAND = STOCK.band
PAPER_MARK = STOCK.mark
PAPER_UP = STOCK.rise
PAPER_DOWN = STOCK.fall

# Web-safe stacks: the display face is a nicety, the fallback is the design.
_SERIF = "Georgia, 'Times New Roman', serif"          # stands in for Fraunces
# Korean breaks inside a word unless told not to; an email has no stylesheet to
# say it once, so it rides on every rule that sets a Korean-bearing family.
_KEEP = "word-break:keep-all;"
_SANS = ("-apple-system, 'Segoe UI', Roboto, 'Apple SD Gothic Neo', "
         "'Malgun Gothic', sans-serif")                        # stands in for IBM Plex Sans KR
_MONO = "'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace"  # for IBM Plex Mono
# Opaque greys rather than an alpha on the ink: a client that recolours the
# ground underneath would otherwise drag the text with it.
_DIM = STOCK.ink3
_SOFT = STOCK.ink2


def _e(s) -> str:
    return html.escape(str(s if s is not None else ""))


def _won(v) -> str:
    return "—" if v is None else f"₩{int(round(v)):,}"


def _pct(v) -> str:
    return "—" if v is None else f"{v:+.2f}%"


def _hue(v) -> str:
    if v is None or v == 0:
        return PAPER_INK
    return PAPER_UP if v > 0 else PAPER_DOWN


def _row(label: str, figure: str, note: str, color: str, *, sub=False, rule=False, big=False) -> str:
    """One statement line: label left, figure right, note in a third column.

    A statement is the shape a brokerage prints. A 2x2 grid of big-number tiles
    is the shape a dashboard prints — and the reader already has the dashboard
    on their phone, so the tiles said nothing new and looked like every other
    generated page.
    """
    top = f"border-top:1.5px solid {PAPER_RULE};" if rule else ""
    pad = "padding:8px 0 8px 15px" if sub else "padding:8px 0"
    lab = f"font-size:12px;color:{_DIM}" if sub else f"font-size:13px;color:{_SOFT}"
    fig = (f"font-family:{_SERIF};font-size:19px" if big
           else f"font-family:{_MONO};font-size:{'12' if sub else '13'}px")
    return (
        f'<tr>'
        f'<td style="{top}{pad};border-bottom:1px solid {PAPER_RULE};font-family:{_SANS};{_KEEP}{lab}">{_e(label)}</td>'
        f'<td align="right" style="{top}padding:8px 0 8px 10px;border-bottom:1px solid {PAPER_RULE};'
        f'{fig};color:{color};white-space:nowrap">{_e(figure)}</td>'
        # 86px, and the note may wrap inside it: a figure that breaks is a
        # different number, but "USD/KRW 1340.8" on two lines is only narrower.
        f'<td align="right" width="100" style="{top}padding:8px 0 8px 9px;border-bottom:1px solid {PAPER_RULE};'
        f'font-family:{_MONO};font-size:10.5px;line-height:1.45;color:{_DIM}">{_e(note)}</td>'
        f'</tr>'
    )


def _bar(pct: float, color: str) -> str:
    """A bar an email client will actually draw: two cells, a width, a colour."""
    filled = max(min(pct, 100), 0)
    rest = 100 - filled
    cells = (f'<td width="{filled:.1f}%" bgcolor="{color}" '
             f'style="background:{color};font-size:0;line-height:0">&nbsp;</td>')
    if rest > 0.05:
        cells += (f'<td width="{rest:.1f}%" bgcolor="{PAPER_BAND}" '
                  f'style="background:{PAPER_BAND};font-size:0;line-height:0">&nbsp;</td>')
    return (f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" '
            f'style="height:9px;border-collapse:collapse"><tr style="height:9px">{cells}</tr></table>')


def _spans(t: dict) -> str:
    """The headline, drawn: how long each side was held, from a common origin.

    An inbox blocks SVG, so the eight drawings on the page reach it as nothing
    at all — and the phone is where this report is actually read. Everything
    below is a chart built the only way an inbox will draw one: table cells
    with a background colour and a width. A bar is a bar whether an SVG or a
    <td> puts it on the screen.
    """
    w, l = t.get("win_hold_median_days"), t.get("loss_hold_median_days")
    if not t.get("closed") or w is None or l is None:
        return ""
    mx = max(w, l, 1)
    rows = ""
    for label, days, pct, n, colour in (
        ("이익을 실현할 때", w, t.get("median_win_pct"), t.get("wins"), PAPER_UP),
        ("손실을 실현할 때", l, t.get("median_loss_pct"), t.get("losses"), PAPER_DOWN),
    ):
        rows += (
            f'<tr><td style="padding:9px 0 3px;font-family:{_SANS};font-size:12.5px;{_KEEP}color:{PAPER_INK}">{_e(label)}</td>'
            f'<td align="right" style="padding:9px 0 3px;font-family:{_MONO};font-size:11.5px;color:{_DIM};white-space:nowrap">{n or 0}건</td>'
            f'<td align="right" width="118" style="padding:9px 0 3px;font-family:{_MONO};font-size:11.5px;'
            f'color:{_hue(pct)};white-space:nowrap">{days:g}일 · {_pct(pct)}</td></tr>'
            f'<tr><td colspan="3" style="padding:0 0 5px">{_bar(days / mx * 100, colour)}</td></tr>')
    return (f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" '
            f'style="border-collapse:collapse;margin-top:11px">{rows}</table>')


def _columns(sales: list[dict]) -> str:
    """Realised P&L accumulating, one column per month.

    73 sales in 358px is four pixels a sale, so the columns are months — the
    shape survives the binning and the individual sale was never legible at
    that width anyway. Columns rather than a line because an inbox cannot draw
    a line, and a column per month is honest about the resolution.
    """
    if len(sales) < 4:
        return ""
    months: dict[str, float] = {}
    run = 0.0
    for x in sales:
        run += x["realised_krw"]
        months[x["date"][:7]] = run
    keys = sorted(months)
    # carry the running total through months with no sale, or the chart would
    # claim the total dropped to zero whenever nothing was sold
    span, cur, series = [], 0.0, []
    y, m = (int(v) for v in keys[0].split("-"))
    ey, em = (int(v) for v in keys[-1].split("-"))
    while (y, m) <= (ey, em):
        k = f"{y:04d}-{m:02d}"
        cur = months.get(k, cur)
        span.append(k)
        series.append(cur)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    hi = max(max(series), 0) or 1
    lo = min(min(series), 0)
    rng = (hi - lo) or 1
    H = 86
    wid = 100 / len(series)
    cells = ""
    for k, v in zip(span, series):
        h = max(round((v - lo) / rng * H), 1)
        cells += (f'<td width="{wid:.2f}%" valign="bottom" style="padding:0 1px">'
                  f'<div style="height:{h}px;background:{PAPER_MARK};font-size:0;line-height:0">&nbsp;</div></td>')
    ticks = (f'<tr><td align="left" style="padding:5px 0 0;font-family:{_MONO};font-size:10px;color:{_DIM}">{_e(span[0])}</td>'
             f'<td align="right" style="padding:5px 0 0;font-family:{_MONO};font-size:10px;color:{_DIM}">{_e(span[-1])}</td></tr>')
    return (f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" '
            f'style="border-collapse:collapse;margin-top:12px"><tr>{cells}</tr></table>'
            f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" '
            f'style="border-collapse:collapse">{ticks}</table>')


def _diverging(rows: list[dict], n: int = 4) -> str:
    """Since-sale change for the biggest movers each way, around a zero line.

    Two half-width columns that grow away from a shared centre: a bar to the
    left is a price that fell after the sale, one to the right a price that
    rose. The extremes are taken from *both* ends rather than by magnitude —
    ranked by magnitude alone this account's top eight are all risers, and a
    diverging chart with nothing on one side reads as a broken chart rather
    than as a true fact about the data.
    """
    if len(rows) < 2:
        return ""
    ranked = sorted(rows, key=lambda r: r["since_sale_pct"])
    top = {id(r): r for r in ranked[-n:] + ranked[:n]}.values()
    mx = max(abs(r["since_sale_pct"]) for r in top) or 1
    out = ""
    for r in sorted(top, key=lambda r: -r["since_sale_pct"]):
        v = r["since_sale_pct"]
        p = min(abs(v) / mx * 100, 100)
        inner = ('table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" '
                 'style="height:8px;border-collapse:collapse"')
        gap = '<td style="height:8px;font-size:0;line-height:0">&nbsp;</td>'
        mid = f"border-right:1px solid {PAPER_RULE};"
        if v >= 0:
            half = (f'<td width="50%" style="{mid}height:8px;font-size:0;line-height:0">&nbsp;</td>'
                    f'<td width="50%" style="padding:0;height:8px"><{inner}><tr style="height:8px">'
                    f'<td width="{p:.1f}%" bgcolor="{PAPER_UP}" style="height:8px;background:{PAPER_UP};font-size:0;line-height:0">&nbsp;</td>'
                    f'{gap if p < 99.9 else ""}</tr></table></td>')
        else:
            half = (f'<td width="50%" style="{mid}padding:0;height:8px"><{inner}><tr style="height:8px">'
                    f'{gap if p < 99.9 else ""}'
                    f'<td width="{p:.1f}%" bgcolor="{PAPER_DOWN}" style="height:8px;background:{PAPER_DOWN};font-size:0;line-height:0">&nbsp;</td>'
                    f'</tr></table></td><td width="50%" style="height:8px;font-size:0;line-height:0">&nbsp;</td>')
        out += (f'<tr><td style="padding:8px 0 2px;font-family:{_SANS};font-size:12px;{_KEEP}color:{PAPER_INK}">'
                f'{_e(_nm(r["symbol"], r.get("name")))}</td>'
                f'<td align="right" style="padding:8px 0 2px;font-family:{_MONO};font-size:11.5px;'
                f'color:{_hue(v)};white-space:nowrap">{v:+.0f}%</td></tr>'
                f'<tr><td colspan="2" style="padding:0 0 4px"><table role="presentation" cellpadding="0" '
                f'cellspacing="0" border="0" width="100%" style="height:8px;border-collapse:collapse">'
                f'<tr style="height:8px">{half}</tr></table></td></tr>')
    return (f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" '
            f'style="border-collapse:collapse;margin-top:11px">{out}</table>')


def _matrix(tm: dict) -> str:
    """Fills by weekday and two-hour bin, as a table of tinted cells.

    A heat matrix is the one chart an inbox draws natively — it is a table with
    background colours and nothing else. Twelve bins rather than twenty-four
    because 24 columns in 358px is fifteen pixels a column, and this only has
    to show which half of the clock a weekday's trading sits in.
    """
    grid = tm.get("matrix")
    if not grid:
        return ""
    binned = [[sum(r[h * 2:h * 2 + 2]) for h in range(12)] for r in grid]
    mx = max(max(r) for r in binned) or 1
    head = ('<tr><td width="26" style="font-size:0;line-height:0">&nbsp;</td>'
            + "".join(f'<td align="center" style="padding:0 0 3px;font-family:{_MONO};font-size:9px;color:{_DIM}">'
                      f'{h * 2:02d}</td>' if h % 2 == 0 else '<td style="font-size:0;line-height:0">&nbsp;</td>'
                      for h in range(12)) + "</tr>")
    body = ""
    for d, name in enumerate(("월", "화", "수", "목", "금", "토", "일")):
        cells = ""
        for h in range(12):
            n = binned[d][h]
            # an inbox has no opacity on a background, so the tint is mixed
            # against the ground here and shipped as a flat colour
            bg = _tint(PAPER_MARK, n / mx) if n else PAPER_BAND
            cells += (f'<td bgcolor="{bg}" align="center" style="background:{bg};border:1px solid {PAPER};'
                      f'font-family:{_MONO};font-size:9px;line-height:15px;'
                      f'color:{PAPER if n >= mx * 0.55 else _DIM}">{n or "&nbsp;"}</td>')
        body += (f'<tr><td width="26" style="font-family:{_SANS};font-size:11px;color:{_SOFT};'
                 f'padding-right:5px">{name}</td>{cells}</tr>')
    return (f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" '
            f'style="border-collapse:collapse;margin-top:12px">{head}{body}</table>')


def _tint(hex_colour: str, t: float) -> str:
    """Mix a colour toward the ground. Email has no rgba on a background, and a
    PNG would be blocked until the reader asked for images — so the blend is
    computed here and shipped as a flat hex."""
    t = 0.18 + 0.82 * max(min(t, 1.0), 0.0)
    fg = [int(hex_colour[i:i + 2], 16) for i in (1, 3, 5)]
    bg = [int(PAPER[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(b + (f - b) * t):02X}" for f, b in zip(fg, bg))


def _section(title: str, count: str = "") -> str:
    """A section head: a rule, the title, and the one figure that says how much
    follows. The count is information; an uppercase letterspaced label repeated
    on every section is furniture."""
    return (f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" '
            f'style="border-collapse:collapse;margin-top:30px">'
            f'<tr><td style="border-top:1px solid {PAPER_RULE};padding:13px 0 0;'
            f'font-family:{_SERIF};font-size:18px;{_KEEP}color:{PAPER_INK}">{_e(title)}</td>'
            f'<td align="right" style="border-top:1px solid {PAPER_RULE};padding:15px 0 0;'
            f'font-family:{_MONO};font-size:11px;color:{_DIM};white-space:nowrap">{_e(count)}</td>'
            f'</tr></table>')


def render_email_html(rep: dict, *, url: str | None = None, attached: bool = False) -> str:
    """The digest. ``attached`` says a PDF of the full report rides along, which
    is what the closing line should point at rather than a link nobody can open
    without a session."""
    v, h = rep["valuation"], rep["history"]
    an = rep.get("analysis") or {}
    trades = an.get("trades") or {}
    after = an.get("after_selling") or {}
    gen = rep["generated_at"][:16].replace("T", " ")

    basis = "전체 이력" if h.get("realised_trustworthy", h["complete"]) else "부분 이력"
    stmt = (
        _row("주식 평가액", _won(v["equity_value_krw"]), "", PAPER_INK)
        + _row("국내", _won(v["krw_leg"]), "", _DIM, sub=True)
        + _row("해외", f"${(v['usd_leg'] or 0):,.2f}", f"USD/KRW {rep['fx']['usdkrw']}", _DIM, sub=True)
        + _row("매입 총액", _won(v["purchase_total_krw"]), "", PAPER_INK)
        + _row("미실현 손익", _won(v["unrealised_krw"]), _pct(v["unrealised_rate_pct"]),
               _hue(v["unrealised_krw"]), rule=True, big=True)
        + _row("실현 손익 누계", _won(h["realised_net_krw"]), basis, _hue(h["realised_net_krw"]), big=True)
        + _row("당일", _won(v["daily_krw"]), _pct(v["daily_rate_pct"]), _hue(v["daily_krw"]), rule=True)
    )

    heads = an.get("headline", [])
    lead = ""
    if heads:
        lead = (f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" '
                f'style="border-collapse:collapse;margin-top:26px">'
                f'<tr><td style="font-family:{_SERIF};font-size:20px;line-height:1.45;{_KEEP}color:{PAPER_INK}">'
                f'{_e(heads[0])}</td></tr></table>')
    finds = "".join(
        f'<tr><td width="16" valign="top" style="padding:11px 11px 0 0;font-size:0;line-height:0">'
        f'<div style="width:6px;height:6px;background:{PAPER_MARK};font-size:0;line-height:0;margin-top:7px">&nbsp;</div></td>'
        f'<td style="padding:11px 0 0;font-family:{_SANS};font-size:13px;line-height:1.55;{_KEEP}color:{_SOFT}">{_e(x)}</td></tr>'
        for x in heads[1:])
    if finds:
        finds = (f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" '
                 f'style="border-collapse:collapse;margin-top:6px">{finds}</table>')

    rows = []
    for r in rep["holdings"]:
        w = r.get("weight_pct") or 0
        rows.append(
            f'<tr><td style="padding:7px 0 3px;font-family:{_SANS};font-size:12.5px;color:{PAPER_INK}">{_e(_nm(r["symbol"], r["name"]))}</td>'
            f'<td align="right" style="padding:7px 0 3px;font-family:{_MONO};font-size:11.5px;color:{_DIM};white-space:nowrap">{w:.2f}%</td>'
            f'<td align="right" width="62" style="padding:7px 0 3px;font-family:{_MONO};font-size:11.5px;color:{_hue(r["unrealised_rate_pct"])}">'
            f'{_pct(r["unrealised_rate_pct"])}</td></tr>'
            f'<tr><td colspan="3" style="padding:0 0 6px">{_bar(w, PAPER_MARK)}</td></tr>'
        )
    holdings = "".join(rows) or f'<tr><td style="font-family:{_SANS};font-size:12.5px;color:{_DIM}">보유 종목 없음</td></tr>'

    facts = []
    if trades.get("closed"):
        facts += [
            ("닫힌 거래", f"{trades['closed']}건 · 이익 {trades['wins']} / 손실 {trades['losses']} · 승률 {trades['win_rate_pct']}%"),
            ("이길 때 / 질 때", f"{_pct(trades['median_win_pct'])} ({trades['win_hold_median_days']:g}일) / "
                              f"{_pct(trades['median_loss_pct'])} ({trades['loss_hold_median_days']:g}일)"),
            ("거래당 기대값", _won(trades["expectancy_krw"])),
        ]
    if after.get("available") and after.get("count"):
        facts.append(("팔고 난 뒤", f"{after['count']}종목 중 {after['higher_now']}개가 판 가격보다 높다 · "
                                 f"안 팔았다면 {_won(after['kept_delta_krw'])} 차이"))
    fact_rows = "".join(
        f'<tr><td width="92" valign="top" style="padding:6px 10px 6px 0;font-family:{_SANS};{_KEEP}font-size:11.5px;'
        f'color:{_DIM}">{_e(k)}</td>'
        f'<td style="padding:6px 0;font-family:{_SANS};font-size:12.5px;{_KEEP}color:{_SOFT}">{_e(val)}</td></tr>'
        for k, val in facts)

    if h["complete"]:
        note = f"되짚은 보유 {h['checked_symbols']}종목이 토스 잔고와 전부 일치한다."
    elif h.get("realised_trustworthy"):
        note = (f"{len(h['mismatches'])}종목이 잔고와 다르지만 주식 수가 바뀐 것뿐이라 "
                "실현손익은 그대로 신뢰할 수 있다.")
    else:
        note = f"{len(h['mismatches'])}종목의 취득원가가 이력 밖에 있어 실현손익이 일부 비어 있다."
    note = (f"실현 손익 누계는 {basis} · 수수료·세금 차감 기준이다. " + note)

    n_hold = f"{len(rep['holdings'])}종목"
    n_closed = f"닫힌 거래 {trades.get('closed') or 0}건"
    sales = trades.get("sales") or []
    spans, columns, diverging, matrix = _spans(trades), _columns(sales), "", _matrix(an.get("timing") or {})
    if after.get("available") and after.get("rows"):
        diverging = _diverging(after["rows"])
    cap = (f'font-family:{_SANS};font-size:11px;line-height:1.6;{_KEEP}color:{_DIM};padding-top:8px')

    tail = ""
    if attached:
        tail = (f'<div style="font-family:{_SANS};font-size:11.5px;color:{_DIM};padding:22px 0 0">'
                f'차트·종목별 이력·분석 표는 <strong style="color:{_SOFT}">첨부한 PDF</strong> 에 전부 있다. '
                f'이 메일은 요약이다.</div>')
    if url:
        tail += (f'<div style="padding:14px 0 0"><a href="{_e(url)}" '
                 f'style="font-family:{_MONO};font-size:12px;color:{PAPER};background:{PAPER_MARK};'
                 f'text-decoration:none;padding:11px 18px;display:inline-block">웹에서 열기 &#8594;</a></div>'
                 f'<div style="font-family:{_SANS};font-size:11.5px;color:{_DIM};padding-top:9px">'
                 f'링크는 로그인한 브라우저에서만 열린다.</div>')

    return f"""<div bgcolor="{PAPER}" style="margin:0;padding:0;background:{PAPER}">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" bgcolor="{PAPER}" style="background:{PAPER};border-collapse:collapse">
<tr><td align="center" style="padding:28px 15px 44px">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="max-width:600px;border-collapse:collapse">
<tr><td>

<div style="font-family:{_MONO};font-size:10.5px;line-height:1.75;color:{_DIM}">
토스증권 계좌 {_e(rep['account']['account_no_masked'])} &#183; {_e(gen)} KST<br>Toss Open API &#183; read-only</div>
<div style="border-bottom:1.5px solid {PAPER_INK};padding:4px 0 11px;font-family:{_SERIF};font-size:24px;line-height:1.2;{_KEEP}color:{PAPER_INK}">기록이 되비추는 것</div>

{lead}
{finds}

<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="border-collapse:collapse;margin-top:26px">{stmt}</table>
<div style="font-family:{_SANS};font-size:11.5px;line-height:1.7;{_KEEP}color:{_DIM};padding-top:10px">{_e(note)}</div>

{_section("보유 기간", n_closed) if spans else ""}{spans}
{f'<div style="{cap}">두 막대가 같은 자리에서 출발한다. 오른쪽 끝이 매도까지 걸린 날의 중앙값이다.</div>' if spans else ""}

{_section("보유", n_hold)}
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="border-collapse:collapse;margin-top:13px">{holdings}</table>

{_section("실현손익 누적", f"매도 {len(sales)}건") if columns else ""}{columns}
{f'<div style="{cap}">한 칸이 한 달, 높이는 그때까지 쌓인 실현손익이다. 매도가 없던 달은 앞의 값을 그대로 잇는다.</div>' if columns else ""}

{_section("팔고 난 뒤", f"{after.get('count') or 0}종목") if diverging else ""}{diverging}
{f'<div style="{cap}">가운데가 판 가격이다. 오른쪽으로 뻗으면 판 뒤에 올랐고, 왼쪽이면 내렸다. 양쪽 끝에서 네 종목씩.</div>' if diverging else ""}

{_section("체결의 리듬", f"체결 {(an.get('timing') or {}).get('fills') or 0}건") if matrix else ""}{matrix}
{f'<div style="{cap}">가로가 두 시간 단위, 진할수록 그 칸의 체결이 많다. 국내 정규장은 09-15시, 미국은 22시 이후다.</div>' if matrix else ""}

{_section("거래", n_closed) if fact_rows else ""}
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="border-collapse:collapse;margin-top:13px">{fact_rows}</table>
{tail}

<div style="border-top:1.5px solid {PAPER_RULE};margin-top:38px;padding-top:15px;font-family:{_SANS};font-size:11.5px;line-height:1.75;{_KEEP}color:{_DIM}">
토스증권 Open API 를 읽기 전용으로 조회해 만들었다. 주문 경로는 없다. 기록을 되비추는 거울이며, 다음에 무엇을 할지는 여기 없다.</div>

</td></tr></table>
</td></tr></table></div>"""


def render_email_text(rep: dict, *, url: str | None = None, attached: bool = False) -> str:
    """The plain-text alternative. Same figures, no markup."""
    v, h = rep["valuation"], rep["history"]
    an = rep.get("analysis") or {}
    L = [f"PivoxReport — 토스증권 계좌 {rep['account']['account_no_masked']}",
         f"{rep['generated_at'][:16].replace('T', ' ')} KST · Toss Open API, read-only", "",
         f"주식 평가액   {_won(v['equity_value_krw'])}",
         f"미실현       {_won(v['unrealised_krw'])} ({_pct(v['unrealised_rate_pct'])})",
         f"실현 누계     {_won(h['realised_net_krw'])}",
         f"오늘         {_won(v['daily_krw'])} ({_pct(v['daily_rate_pct'])})", ""]
    for i, x in enumerate(an.get("headline", []), 1):
        L.append(f"{i}. {x}")
    L += ["", "보유"]
    for r in rep["holdings"]:
        L.append(f"  {_nm(r['symbol'], r['name'])}  {(r.get('weight_pct') or 0):.2f}%  {_pct(r['unrealised_rate_pct'])}")
    if attached:
        L += ["", "차트·종목별 이력·분석 표는 첨부한 PDF 에 전부 있다."]
    if url:
        L += ["", f"웹에서 열기 (로그인 필요): {url}"]
    L += ["", "기록을 되비추는 거울이다. 다음에 무엇을 할지는 여기 없다."]
    return "\n".join(L)
