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

from services.toss.html_report import (
    PAPER,
    PAPER_BRONZE,
    PAPER_DOWN,
    PAPER_INK,
    PAPER_RULE,
    PAPER_TLDR,
    PAPER_UP,
    _nm,
)

# Web-safe stacks: the display face is a nicety, the fallback is the design.
_SERIF = "Georgia, 'Times New Roman', serif"
_SANS = "-apple-system, 'Segoe UI', Roboto, 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif"
_MONO = "'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace"
# Opaque greys rather than an alpha on the ink: a client that recolours the
# ground underneath would otherwise drag the text with it.
_DIM = "#5A5A5A"
_SOFT = "#3A3A3A"


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


def _tile(label: str, value: str, sub: str, color: str) -> str:
    return (
        f'<td width="50%" bgcolor="{PAPER}" style="padding:14px 12px;border:1px solid {PAPER_RULE};vertical-align:top">'
        f'<div style="font-family:{_MONO};font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:{_DIM}">{_e(label)}</div>'
        f'<div style="font-family:{_SERIF};font-size:22px;line-height:1.15;padding-top:7px;color:{color}">{_e(value)}</div>'
        f'<div style="font-family:{_MONO};font-size:10.5px;color:{_DIM};padding-top:5px">{_e(sub)}</div></td>'
    )


def _bar(pct: float, color: str) -> str:
    """A bar an email client will actually draw: two cells, a width, a colour."""
    filled = max(min(pct, 100), 0)
    rest = 100 - filled
    cells = (f'<td width="{filled:.1f}%" bgcolor="{color}" '
             f'style="background:{color};font-size:0;line-height:0">&nbsp;</td>')
    if rest > 0.05:
        cells += (f'<td width="{rest:.1f}%" bgcolor="{PAPER_TLDR}" '
                  f'style="background:{PAPER_TLDR};font-size:0;line-height:0">&nbsp;</td>')
    return (f'<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" '
            f'style="height:9px;border-collapse:collapse"><tr style="height:9px">{cells}</tr></table>')


def _section(title: str) -> str:
    return (f'<div style="font-family:{_MONO};font-size:10px;letter-spacing:.14em;text-transform:uppercase;'
            f'color:{PAPER_BRONZE};padding:26px 0 9px">{_e(title)}</div>')


def render_email_html(rep: dict, *, url: str | None = None, attached: bool = False) -> str:
    """The digest. ``attached`` says a PDF of the full report rides along, which
    is what the closing line should point at rather than a link nobody can open
    without a session."""
    v, h = rep["valuation"], rep["history"]
    an = rep.get("analysis") or {}
    trades = an.get("trades") or {}
    after = an.get("after_selling") or {}
    gen = rep["generated_at"][:16].replace("T", " ")

    tiles = (
        "<tr>"
        + _tile("주식 평가액", _won(v["equity_value_krw"]), f"USD/KRW {rep['fx']['usdkrw']}", PAPER_INK)
        + _tile("미실현", _won(v["unrealised_krw"]), _pct(v["unrealised_rate_pct"]), _hue(v["unrealised_krw"]))
        + "</tr><tr>"
        + _tile("실현 누계", _won(h["realised_net_krw"]),
                "전체 이력" if h.get("realised_trustworthy", h["complete"]) else "부분 이력",
                _hue(h["realised_net_krw"]))
        + _tile("오늘", _won(v["daily_krw"]), _pct(v["daily_rate_pct"]), _hue(v["daily_krw"]))
        + "</tr>"
    )

    heads = "".join(
        f'<div bgcolor="{PAPER_TLDR}" style="background:{PAPER_TLDR};font-family:{_SERIF};font-size:14.5px;'
        f'line-height:1.55;color:{PAPER_INK};border-left:2px solid {PAPER_BRONZE};'
        f'padding:9px 12px;margin-bottom:9px">{_e(x)}</div>'
        for x in an.get("headline", [])
    )

    rows = []
    for r in rep["holdings"]:
        w = r.get("weight_pct") or 0
        rows.append(
            f'<tr><td style="padding:7px 0 3px;font-family:{_SANS};font-size:12.5px;color:{PAPER_INK}">{_e(_nm(r["symbol"], r["name"]))}</td>'
            f'<td align="right" style="padding:7px 0 3px;font-family:{_MONO};font-size:12px;color:{_DIM}">{w:.2f}%</td>'
            f'<td align="right" width="72" style="padding:7px 0 3px;font-family:{_MONO};font-size:12px;color:{_hue(r["unrealised_rate_pct"])}">'
            f'{_pct(r["unrealised_rate_pct"])}</td></tr>'
            f'<tr><td colspan="3" style="padding:0 0 6px">{_bar(w, PAPER_BRONZE)}</td></tr>'
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
        f'<tr><td width="120" style="padding:5px 10px 5px 0;font-family:{_MONO};font-size:10px;letter-spacing:.08em;'
        f'text-transform:uppercase;color:{_DIM};vertical-align:top">{_e(k)}</td>'
        f'<td style="padding:5px 0;font-family:{_SANS};font-size:12.5px;color:{_SOFT}">{_e(val)}</td></tr>'
        for k, val in facts)

    if h["complete"]:
        note = f"되짚은 보유 {h['checked_symbols']}종목이 토스 잔고와 전부 일치한다."
    elif h.get("realised_trustworthy"):
        note = (f"{len(h['mismatches'])}종목이 잔고와 다르지만 주식 수가 바뀐 것뿐이라 "
                "실현손익은 그대로 신뢰할 수 있다.")
    else:
        note = f"{len(h['mismatches'])}종목의 취득원가가 이력 밖에 있어 실현손익이 일부 비어 있다."

    tail = ""
    if attached:
        tail = (f'<div style="font-family:{_SANS};font-size:11.5px;color:{_DIM};padding:22px 0 0">'
                f'차트·종목별 이력·분석 표는 <strong style="color:{_SOFT}">첨부한 PDF</strong> 에 전부 있다. '
                f'이 메일은 요약이다.</div>')
    if url:
        tail += (f'<div style="padding:14px 0 0"><a href="{_e(url)}" '
                 f'style="font-family:{_MONO};font-size:12px;color:{PAPER};background:{PAPER_BRONZE};'
                 f'text-decoration:none;padding:11px 18px;display:inline-block">웹에서 열기 →</a></div>'
                 f'<div style="font-family:{_SANS};font-size:11.5px;color:{_DIM};padding-top:9px">'
                 f'링크는 로그인한 브라우저에서만 열린다.</div>')

    return f"""<div bgcolor="{PAPER}" style="margin:0;padding:0;background:{PAPER}">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" bgcolor="{PAPER}" style="background:{PAPER};border-collapse:collapse">
<tr><td align="center" style="padding:28px 16px 44px">
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="600" style="width:600px;max-width:100%;border-collapse:collapse">
<tr><td>

<div style="font-family:{_MONO};font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:{PAPER_BRONZE}">
PivoxReport · 토스증권 계좌 {_e(rep['account']['account_no_masked'])}</div>
<div style="font-family:{_SERIF};font-size:27px;line-height:1.2;color:{PAPER_INK};padding:7px 0 5px">기록이 되비추는 것</div>
<div style="font-family:{_MONO};font-size:10.5px;color:{_DIM}">{_e(gen)} KST · Toss Open API, read-only</div>

<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="border-collapse:collapse;margin-top:18px">{tiles}</table>
<div style="font-family:{_SANS};font-size:11.5px;color:{_DIM};padding-top:10px">{_e(note)}</div>

{_section("이 계좌가 말하는 것") if heads else ""}{heads}

{_section("보유")}
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="border-collapse:collapse">{holdings}</table>

{_section("거래") if fact_rows else ""}
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="border-collapse:collapse">{fact_rows}</table>
{tail}

<div style="font-family:{_SERIF};font-style:italic;font-size:12.5px;color:{_DIM};padding:34px 0 0;text-align:center">
기록을 되비추는 거울이다. 다음에 무엇을 할지는 여기 없다.</div>

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
