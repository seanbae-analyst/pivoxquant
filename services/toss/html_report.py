"""PivoxReport — the report drawn as an observation record.

The account is one subject observed over a couple of years, so the document is
built the way a record of observations is: numbered plates, each measuring one
thing, each captioned with what it shows. The plate number hangs in the margin
so a finding can be pointed at.

This does not use the product's v3 tokens. PivoxReport is a personal instrument,
not a product surface, and dressing it as the app made it read as the app's
marketing rather than as a measurement. It has its own identity: chart stock
rather than paper or Vantablack, an instrument ink, and the Korean rise/fall
polarity at printing-ink saturation rather than the app's muted pair.

Type is three roles from two families. IBM Plex — a family drawn for engineering
documentation — carries everything the reader measures with: Plex Sans and Plex
Sans KR for text, Plex Mono for every figure and annotation. Fraunces carries
the voice: the title, the plate titles, the one sentence at the top. Both come
from Google Fonts, which also means Korean arrives from a real Korean cut on the
one host every renderer here can reach.

Every chart is inline SVG computed in this file; hover detail rides on
``<title>``. No JavaScript, no external asset but the fonts. Numbers are the
report's numbers — this module formats and places them and never derives one.
"""
from __future__ import annotations

import html
import math
import re
from datetime import date
from typing import NamedTuple


class Palette(NamedTuple):
    """Every colour the document draws with, so the ground is a parameter.

    The charts write their fills as literal hex: a ``var()`` in an SVG
    presentation attribute is not something every renderer resolves, and the PDF
    path is exactly the renderer that would drop it silently. Threading the
    palette means the drawings and the stylesheet can never disagree about which
    ground they are on.
    """

    ground: str        # the stock itself
    band: str          # a ruled band or inset
    ink: str
    ink2: str          # secondary text
    ink3: str          # annotation, axis text
    rule: str          # hairline
    grid: str          # finer ruling inside a drawing
    mark: str          # the instrument ink — marks with no polarity
    rise: str          # 상승 (KR convention: red)
    fall: str          # 하락 (KR convention: blue)
    ghost: str         # a subject no longer held
    scheme: str


# Chart stock: a green-grey whisper, not cream and not white, so a hairline has
# something to sit on. The instrument ink is a deep pine; the polarity pair is
# madder and prussian — the Korean convention at the saturation a press would
# actually print, which is where the app's muted pair could not go because it
# had to sit on Vantablack.
STOCK = Palette(
    ground="#EDEFEC", band="#E4E7E2", ink="#16191A", ink2="#454E4B", ink3="#79837F",
    rule="#C6CCC5", grid="#D9DED8", mark="#2F5D50", rise="#A32B2B", fall="#1F4C86",
    ghost="#A6AEA9", scheme="light",
)

# The same record under a lamp rather than on a desk. Not an inversion: the
# marks are re-stepped so pine, madder and prussian each still read as
# themselves against a dark ground.
SCREEN = Palette(
    ground="#14171A", band="#1B1F22", ink="#E7EAE6", ink2="#A5ADA9", ink3="#79837F",
    rule="#2E3438", grid="#232A2D", mark="#63AF97", rise="#D96A6A", fall="#6FA0D8",
    ghost="#5A625E", scheme="dark",
)

_FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    "family=Fraunces:opsz,wght@9..144,400;9..144,600&"
    "family=IBM+Plex+Sans:wght@400;500;600&"
    "family=IBM+Plex+Sans+KR:wght@400;500;600&"
    "family=IBM+Plex+Mono:wght@400;500&display=swap\">"
)


def _css(p: Palette) -> str:
    return f"""
:root {{ --ground:{p.ground}; --band:{p.band}; --ink:{p.ink}; --ink2:{p.ink2}; --ink3:{p.ink3};
  --rule:{p.rule}; --grid:{p.grid}; --mark:{p.mark}; --rise:{p.rise}; --fall:{p.fall}; --ghost:{p.ghost};
  --display:Fraunces, Georgia, "Times New Roman", serif;
  --sans:"IBM Plex Sans", "IBM Plex Sans KR", -apple-system, system-ui, sans-serif;
  --mono:"IBM Plex Mono", "IBM Plex Sans KR", ui-monospace, Menlo, Consolas, monospace; }}
html {{ color-scheme: {p.scheme}; }}
/* keep-all is the difference between Korean that is typeset and Korean that is
   merely wrapped: without it the browser breaks inside a word, so "손실은"
   arrives as "손실" / "은" on two lines. Latin has no character-level break to
   suppress; the figure columns get overflow-wrap back below. */
body {{ margin:0; background:var(--ground); color:var(--ink); font-family:var(--sans); font-size:14px;
  line-height:1.62; word-break:keep-all; padding-block:48px 76px; padding-inline:20px; -webkit-font-smoothing:antialiased; }}
.wrap {{ max-width:820px; margin:0 auto; }}

/* The record is headed, not launched: it names itself on the left and stamps
   its provenance on the right, on one baseline over one heavy rule. */
/* CSS tables, not flex or grid: this document's other renderer is WeasyPrint,
   which has no grid and only partial flex, and a masthead that silently
   overflows the page margin is exactly how that shows up. */
.mast {{ display:table; width:100%; border-bottom:1.5px solid var(--ink); padding-bottom:12px; }}
.mast h1 {{ display:table-cell; vertical-align:bottom; font-family:var(--display); font-weight:600;
  font-size:29px; line-height:1.15; margin:0; letter-spacing:-.01em; }}
.mast .who {{ display:table-cell; vertical-align:bottom; width:200px; padding-left:24px;
  font-family:var(--mono); font-size:11px; color:var(--ink3); text-align:right; line-height:1.8; }}

/* Only plates are numbered. The findings used to carry ordinals too, in the
   same margin and the same face, so "01" meant two different things one inch
   apart. They are a short list now and the numbering belongs to the plates. */
.lead {{ margin:30px 0 0; }}
.lead p {{ font-family:var(--display); font-weight:400; font-size:21px; line-height:1.45; margin:0;
  max-width:48ch; text-wrap:balance; }}
.finds {{ margin:20px 0 0; padding:0; list-style:none; display:grid; gap:11px; max-width:68ch; }}
.finds li {{ font-size:13.5px; line-height:1.58; color:var(--ink2); padding-left:17px; position:relative; }}
.finds li::before {{ content:""; position:absolute; left:0; top:.62em; width:6px; height:6px; background:var(--mark); }}
.n {{ font-family:var(--mono); font-size:10.5px; letter-spacing:.06em; color:var(--mark); }}

/* Plates. The number hangs in the margin so a finding can be pointed at, the
   title sits in the voice face, and the basis of the measurement is stamped at
   the right on the same baseline. */
.plate {{ margin-top:40px; }}
.ph {{ display:table; width:100%; border-top:1px solid var(--ink); padding-top:11px; }}
.ph .n {{ display:table-cell; width:34px; vertical-align:baseline; }}
.ph h2 {{ display:table-cell; vertical-align:baseline; font-family:var(--display); font-weight:600;
  font-size:19px; margin:0; letter-spacing:-.005em; }}
.ph .basis {{ display:table-cell; vertical-align:baseline; text-align:right; white-space:nowrap;
  font-family:var(--mono); font-size:10.5px; color:var(--ink3); padding-left:20px; }}
.body {{ padding-left:34px; }}

.cap {{ font-size:12.5px; line-height:1.6; color:var(--ink2); margin:11px 0 0; max-width:70ch; }}
.cap b {{ font-weight:600; color:var(--ink); }}
.rise {{ color:var(--rise); }} .fall {{ color:var(--fall); }} .dim {{ color:var(--ink3); }}

/* Statement block: label left, figure right in tabular mono, legs indented
   under their total, the heavier rule where a 잔고 statement rules off. */
.stmt {{ width:100%; border-collapse:collapse; font-variant-numeric:tabular-nums; margin-top:14px; }}
.stmt td {{ padding:9px 0; border-bottom:1px solid var(--grid); vertical-align:baseline; }}
.stmt td.k {{ font-size:13px; color:var(--ink2); }}
.stmt td.v {{ text-align:right; font-family:var(--mono); font-size:13.5px; white-space:nowrap; padding-left:16px; overflow-wrap:anywhere; }}
.stmt td.x {{ text-align:right; font-family:var(--mono); font-size:11px; color:var(--ink3); white-space:nowrap; padding-left:14px; width:120px; }}
.stmt tr.sub td.k {{ padding-left:16px; font-size:12.5px; color:var(--ink3); }}
.stmt tr.sub td.v {{ font-size:12.5px; color:var(--ink3); }}
.stmt tr.rule td {{ border-top:1.5px solid var(--rule); }}
.stmt tr.big td.v {{ font-family:var(--display); font-weight:600; font-size:21px; }}
.stmt tr:last-child td {{ border-bottom:0; }}

.rlist {{ margin:14px 0 0; padding:0; list-style:none; display:grid; gap:12px; }}
.rlist li {{ display:table; width:100%; font-size:12.5px; line-height:1.55; color:var(--ink2); }}
.rlist li > span {{ display:table-cell; vertical-align:baseline; }}
.rlist .s {{ width:136px; padding-right:14px; font-family:var(--mono); font-size:11.5px; color:var(--ink); }}
.rlist .s em {{ display:block; font-style:normal; color:var(--ink3); font-size:10.5px; padding-top:2px; }}
.recon {{ font-size:13.5px; line-height:1.6; margin:14px 0 0; }}
.recon strong {{ font-weight:600; }}

svg {{ display:block; width:100%; min-width:600px; height:auto; margin-top:16px; }}
.tbl {{ overflow-x:auto; -webkit-overflow-scrolling:touch; }}
svg text {{ font-family:var(--mono); font-size:10.5px; fill:var(--ink3); }}
svg .lbl {{ font-family:var(--sans); font-size:11.5px; fill:var(--ink); }}
svg .fig {{ font-family:var(--mono); font-size:11px; fill:var(--ink2); }}
svg .axis {{ stroke:var(--rule); stroke-width:1; }}
svg .grid {{ stroke:var(--grid); stroke-width:1; }}

table.plain {{ width:100%; border-collapse:collapse; font-variant-numeric:tabular-nums; font-size:12.5px; margin-top:14px; }}
table.plain th {{ font-family:var(--mono); font-size:10px; letter-spacing:.08em; text-transform:uppercase; color:var(--ink3); font-weight:400; text-align:left; padding:7px 8px; border-bottom:1px solid var(--rule); }}
table.plain td {{ padding:8px; border-bottom:1px solid var(--grid); overflow-wrap:anywhere; }}
table.plain td.n {{ text-align:right; font-family:var(--mono); white-space:nowrap; }}
.mirror {{ width:100%; border-collapse:collapse; font-variant-numeric:tabular-nums; margin-top:14px; }}
.mirror th, .mirror td {{ padding:9px 8px; border-bottom:1px solid var(--grid); vertical-align:top; text-align:right; }}
.mirror th {{ font-family:var(--mono); font-size:10px; letter-spacing:.08em; text-transform:uppercase; color:var(--ink3); font-weight:400; }}
.mirror td:first-child, .mirror th:first-child {{ text-align:left; color:var(--ink2); }}
.mirror td {{ font-family:var(--mono); font-size:12.5px; }}

/* Symbol cards. One card is drawn at 344 units and asks for ~360 CSS px, which
   is exactly what an iPhone 14 has after the page gutter — so the phone gets
   one column and never a sideways scroll. Where there is room for two the
   table puts two side by side rather than stretching one to twice its design
   width, which is also what fits an A4 column. Table, not grid: WeasyPrint. */
.cards {{ display:table; width:100%; table-layout:fixed; border-collapse:separate; border-spacing:0; margin-top:6px; }}
.crow {{ display:table-row; }}
/* border-box or the gutter is added outside the 50%: a fixed-layout table cell
   sizes its content box, so two 50% cells plus a 30px gutter come to 100%+30
   and the right-hand card hangs off the page in the PDF. */
.card {{ display:table-cell; box-sizing:border-box; width:50%; vertical-align:top; padding:14px 15px 20px; }}
/* the gutter goes between the cards, never outside them, and both halves keep
   the same drawing width — otherwise one card's chart is 30px narrower than
   its twin and the pair stops reading as one object */
.crow .card:first-child {{ padding-left:0; }}
.crow .card:last-child {{ padding-right:0; }}
.card:empty {{ padding:0; }}
.ch {{ display:table; width:100%; border-top:1px solid var(--ink); padding-top:8px; }}
.ch .s {{ display:table-cell; font-size:13.5px; font-weight:600; line-height:1.35; }}
.ch .w {{ display:table-cell; text-align:right; white-space:nowrap; vertical-align:baseline;
  font-family:var(--mono); font-size:11px; color:var(--ink3); padding-left:10px; }}
.cm {{ font-family:var(--mono); font-size:10.5px; color:var(--ink3); margin:5px 0 0; line-height:1.55; }}
.cn {{ font-size:12.5px; line-height:1.55; color:var(--ink2); margin:8px 0 0; border-left:2px solid var(--mark); padding-left:9px; }}
svg.spark {{ min-width:0; margin-top:7px; }}
.cf {{ width:100%; table-layout:fixed; border-collapse:collapse; font-variant-numeric:tabular-nums; margin-top:9px; }}
.cf th {{ font-family:var(--mono); font-weight:400; font-size:9.5px; letter-spacing:.07em; color:var(--ink3);
  text-align:left; padding:0 6px 2px 0; border-top:1px solid var(--grid); padding-top:7px; }}
.cf td {{ font-family:var(--mono); font-size:11.5px; text-align:left; padding:0 6px 0 0; overflow-wrap:anywhere; }}
.legend {{ display:flex; gap:16px; flex-wrap:wrap; font-family:var(--mono); font-size:10.5px; color:var(--ink3); margin-top:10px; }}
.legend i {{ display:inline-block; width:9px; height:9px; margin-right:6px; vertical-align:-1px; }}
h3 {{ font-family:var(--sans); font-size:12px; font-weight:600; letter-spacing:.02em; color:var(--ink); margin:26px 0 0; padding-bottom:7px; border-bottom:1px solid var(--grid); }}

.foot {{ margin-top:50px; border-top:1.5px solid var(--ink); padding-top:16px; font-size:11.5px; line-height:1.8; color:var(--ink3); max-width:70ch; }}
.foot ul {{ margin:8px 0 0; padding-left:16px; }}
.foot .basis {{ color:var(--ink2); }}
/* A phone is 390 CSS px wide — an iPhone 14 exactly — and everything below is
   what that width costs. Two-cell heads stack, the margin the plate numbers
   hang in goes away, the third column of a statement gives up its padding
   before its content, and the drawings keep their own scrollbar (see _svg)
   with a shadow at the edge so it is discoverable rather than guessed at. */
@media (max-width:640px) {{
  .body {{ padding-left:0; }}
  .mast h1, .mast .who {{ display:block; width:auto; padding-left:0; text-align:left; }}
  .mast .who {{ padding-top:9px; }}
  .ph, .ph .n, .ph h2, .ph .basis {{ display:block; width:auto; text-align:left; padding-left:0; }}
  .ph .n {{ padding-bottom:2px; }}
  .ph .basis {{ padding-top:3px; }}
  .cards, .crow, .card {{ display:block; width:auto; }}
  .card {{ padding:13px 0 17px; }}
  .card + .card {{ padding-left:0; }}
}}
@media (max-width:440px) {{
  body {{ padding-inline:15px; font-size:13.5px; padding-block:34px 56px; }}
  .mast h1 {{ font-size:24px; }}
  .lead p {{ font-size:18px; }}
  .finds li, .cap {{ font-size:12.5px; }}
  .stmt td.k {{ font-size:12.5px; }}
  .stmt td.v {{ font-size:12.5px; padding-left:9px; }}
  .stmt td.x {{ width:76px; font-size:10px; padding-left:8px; white-space:normal; }}
  .stmt tr.big td.v {{ font-size:17px; }}
  .rlist li, .rlist li > span {{ display:block; width:auto; padding-right:0; }}
  .rlist .s {{ padding-bottom:3px; }}
  .rlist .s em {{ display:inline; padding-left:6px; }}
  .plate {{ margin-top:32px; }}
  /* the classic scroll shadow: a fixed gradient at the right edge, over one
     that scrolls with the content, so the shadow shows only while there is
     more chart to the right of it */
  .tbl {{
    background:
      linear-gradient(to left, var(--ground), rgba(0,0,0,0)) right / 26px 100% no-repeat,
      radial-gradient(farthest-side at 100%, rgba(0,0,0,.18), rgba(0,0,0,0)) right / 9px 100% no-repeat;
    background-attachment: local, scroll;
  }}
}}
""" + (_PRINT_CSS if p.scheme == "light" else "")


# On the stock the horizontal-scroll escape hatch has nowhere to scroll, so the
# drawings shrink to the column instead. A plate is asked to keep its head with
# its drawing, but never to stay whole: the long ones are taller than a page, so
# that request is unsatisfiable and each would take a fresh page with a hand's
# width of white above it.
_PRINT_CSS = """
@page { size: A4; margin: 15mm 13mm 17mm; }
body { padding-block: 0; padding-inline: 0; font-size: 12px; }
.wrap { max-width: none; }
svg { min-width: 0; }
.tbl { overflow-x: visible; }
.plate { margin-top: 26px; }
.body { padding-left: 34px; }
.ph, h2, h3 { break-after: avoid; }
.ph, .stmt tr, svg, tr, .finds li, .rlist li, .lead, .card { break-inside: avoid; }
.crow { break-inside: avoid; }
.card { padding-top: 12px; }
.mast h1 { font-size: 25px; }
.lead p { font-size: 17.5px; }
.foot { margin-top: 32px; }
"""


# ── formatting ───────────────────────────────────────────────────────────────
def _e(s) -> str:
    return html.escape(str(s if s is not None else ""))


def _em(s) -> str:
    """Escape, then promote the ``**bold**`` the shared reason strings carry for
    the markdown renderer. Escaping first means the promotion can never introduce
    a tag the source did not ask for."""
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", _e(s))


def _won(v) -> str:
    return "—" if v is None else f"₩{int(round(v)):,}"


def _kwon(v) -> str:
    """A figure short enough to sit beside a mark: 만 for KRW, no decimals."""
    if v is None:
        return "—"
    v = float(v)
    if abs(v) >= 1_000_000:
        return f"{v / 10_000:,.0f}만"
    return f"{v / 10_000:,.1f}만" if abs(v) >= 10_000 else f"{v:,.0f}"


def _pct(v, signed=True) -> str:
    if v is None:
        return "—"
    return f"{v:+.2f}%" if signed else f"{v:.2f}%"


def _price(v, currency: str) -> str:
    """A share price in the currency it was paid in — two decimals for dollars,
    none for won, because a won price with cents is not a price anyone quotes."""
    if v is None:
        return "—"
    return f"${v:,.2f}" if currency == "USD" else f"{v:,.0f}"


def _cls(v) -> str:
    if v is None or v == 0:
        return "dim"
    return "rise" if v > 0 else "fall"


def _nm(sym, name) -> str:
    return f"{name} ({sym})" if name and name != sym else sym


def _d(s: str | None) -> date | None:
    return date.fromisoformat(s) if s else None


def _days(v) -> str:
    return "—" if v is None else f"{v:g}일"


def _fit(label: str, budget_px: float, size_px: float = 11.5) -> str:
    """Trim a label to the pixels it actually gets.

    A fixed character count cannot do this: hangul is a full em wide and latin a
    bit over half, so the same 22 characters are 264px of "아이티센글로벌
    (124520)" or 145px of "SMR". The wide ones ran into the mark beside them.
    """
    def w(ch: str) -> float:
        return size_px if ord(ch) > 0x1100 else size_px * 0.62

    if sum(w(c) for c in label) <= budget_px:
        return label
    budget_px -= size_px * 0.62
    out, used = [], 0.0
    for ch in label:
        if used + w(ch) > budget_px:
            break
        out.append(ch)
        used += w(ch)
    return "".join(out).rstrip() + "…"


def _stmt(rows) -> str:
    """A statement block: label, figure, note. ``rows`` are
    ``(label, figure, note, colour_class, flags)`` where flags is any of ``sub``
    (a leg indented under the row above), ``rule`` (the heavier rule a statement
    draws where it rules off) and ``big`` (the figure a reader is looking for)."""
    out = ['<table class="stmt">']
    for label, figure, note, cls, flags in rows:
        attr = f' class="{flags}"' if flags else ""
        out.append(f'<tr{attr}><td class="k">{_e(label)}</td>'
                   f'<td class="v {cls}">{_e(figure)}</td>'
                   f'<td class="x">{_e(note)}</td></tr>')
    out.append("</table>")
    return "".join(out)


# WeasyPrint does not apply the document stylesheet inside an <svg>: its SVG
# engine reads presentation attributes and nothing else. Every `svg text`,
# `.lbl` and `.fig` rule in _css is therefore screen-only, and on paper the
# annotations came out at the 16px UA default in black — which is how a figure
# placed for 11px ends up outside the viewBox and clipped. So the type is said
# twice: once in CSS for the browser, once as attributes for the renderer that
# cannot read it. Both from this table, so they cannot drift apart.
_SVG_TYPE = {
    None: ('"IBM Plex Mono", "IBM Plex Sans KR", monospace', "10.5", "ink3"),
    "lbl": ('"IBM Plex Sans", "IBM Plex Sans KR", sans-serif', "11.5", "ink"),
    "fig": ('"IBM Plex Mono", "IBM Plex Sans KR", monospace', "11", "ink2"),
}
_TEXT_TAG = re.compile(r"<text\b([^>]*)>")


def _typeset(body: str, p: Palette) -> str:
    """Stamp the type of every <text> onto the element itself."""
    def one(m: re.Match) -> str:
        attrs = m.group(1)
        cls = re.search(r'class="([^"]*)"', attrs)
        family, size, ink = _SVG_TYPE.get(cls.group(1) if cls else None, _SVG_TYPE[None])
        add = f" font-family='{family}' font-size='{size}'"
        # A drawing that named a colour meant it. It has to say so inline: a
        # presentation attribute loses to the `svg .lbl { fill: … }` rule in the
        # stylesheet, which is how the departed symbols' ghost grey and the
        # matrix's knocked-out digits were being repainted on screen.
        if "fill" not in attrs:
            add += f' style="fill:{getattr(p, ink)}"'
        return f"<text{attrs}{add}>"
    return _TEXT_TAG.sub(one, body)


def _svg(w: int, h: int, label: str, body: list[str], p: Palette) -> str:
    """A drawing, in the container that keeps it from widening the page.

    The drawings are ~600px wide at their smallest legible size and a phone is
    390: they have to scroll inside something. Four of them used to be emitted
    bare, so instead of scrolling they pushed the whole document sideways and
    every line of text on it went off-screen with them.
    """
    return (f'<div class="tbl"><svg viewBox="0 0 {w} {h}" role="img" aria-label="{_e(label)}">'
            + _typeset("".join(body), p) + "</svg></div>")


# ── the composition ─────────────────────────────────────────────────────────
def _holdings_svg(holdings: list[dict], p: Palette, chunk: int | None = None) -> str:
    """One row per holding: weight as magnitude on the left, return diverging
    from a zero line on the right. Same order down both, so the two read as one
    table rather than two charts."""
    if not holdings:
        return '<p class="cap dim">보유 종목 없음</p>'
    if chunk and len(holdings) > chunk:
        return "".join(_holdings_svg(holdings[i:i + chunk], p)
                       for i in range(0, len(holdings), chunk))
    W, name_w, bar_h, row_h, pad_top = 720, 196, 15, 29, 26
    wcol_x, wcol_w = name_w, 210
    rcol_x = wcol_x + wcol_w + 58
    rcol_w = W - rcol_x - 54
    max_w = max(h["weight_pct"] or 0 for h in holdings) or 1
    max_r = max(abs(h["unrealised_rate_pct"] or 0) for h in holdings) or 1
    zero_x = rcol_x + rcol_w / 2
    H = pad_top + row_h * len(holdings) + 8
    out = [f'<text x="{wcol_x}" y="12">비중 · 평가액 기준</text>',
           f'<text x="{zero_x}" y="12" text-anchor="middle">손익률 · 평단 대비</text>',
           f'<line x1="{zero_x}" y1="{pad_top - 5}" x2="{zero_x}" y2="{H - 6}" class="axis"/>']
    for i, h in enumerate(holdings):
        y = pad_top + i * row_h
        cy = y + bar_h / 2 + 4
        label = _nm(h["symbol"], h["name"])
        out.append(f'<text x="0" y="{cy}" class="lbl">{_e(_fit(label, name_w - 14))}</text>')
        w = (h["weight_pct"] or 0) / max_w * (wcol_w - 4)
        out.append(f'<rect x="{wcol_x}" y="{y}" width="{w:.1f}" height="{bar_h}" fill="{p.mark}" opacity=".9">'
                   f'<title>{_e(label)} · 비중 {_pct(h["weight_pct"], False)} · 평가액 {_won(h["market_value_krw"])}</title></rect>')
        out.append(f'<text x="{wcol_x + wcol_w + 8:.1f}" y="{cy}" class="fig">{_pct(h["weight_pct"], False)}</text>')
        r = h["unrealised_rate_pct"] or 0
        rw = abs(r) / max_r * (rcol_w / 2 - 6)
        colour = p.rise if r > 0 else p.fall
        x = zero_x if r >= 0 else zero_x - rw
        out.append(f'<rect x="{x:.1f}" y="{y}" width="{max(rw, 1):.1f}" height="{bar_h}" fill="{colour}">'
                   f'<title>{_e(label)} · 손익률 {_pct(r)} · 평단 {h["avg_purchase_price"]:,}</title></rect>')
        tx = zero_x + rw + 7 if r >= 0 else zero_x - rw - 7
        out.append(f'<text x="{tx:.1f}" y="{cy}" text-anchor="{"start" if r >= 0 else "end"}" class="fig">{_pct(r)}</text>')
    return _svg(W, H, "보유 종목의 비중과 손익률", out, p)


# ── the path ────────────────────────────────────────────────────────────────
def _timeline_svg(rep: dict, p: Palette, chunk: int | None = None) -> str:
    """One track per symbol from its first fill to today (open) or its last fill
    (departed), every fill a tick above or below the track."""
    holdings, departed = rep["holdings"], rep["departed"]
    tracks = []
    today = _d(rep["generated_at"][:10])
    for h in holdings:
        if h.get("opened_at"):
            tracks.append((_nm(h["symbol"], h["name"]), _d(h["opened_at"]), today, True, h["symbol"]))
    for d in departed:
        tracks.append((_nm(d["symbol"], d["name"]), _d(d["first_fill_at"]), _d(d["last_fill_at"]), False, d["symbol"]))
    if not tracks:
        return '<p class="cap dim">이력 안에 체결이 없어 그릴 경로가 없다.</p>'
    x0d = min(t[1] for t in tracks)
    span = max((today - x0d).days, 1)
    W, name_w, right, row_h, pad_top = 720, 196, 26, 25, 28
    px = lambda d: name_w + (d - x0d).days / span * (W - name_w - right)  # noqa: E731
    by_sym: dict[str, list[dict]] = {}
    for f in rep.get("fills_for_chart") or []:
        by_sym.setdefault(f["symbol"], []).append(f)
    if chunk and len(tracks) > chunk:
        # An SVG is a replaced element: a paginating renderer cannot split one,
        # so a drawing taller than the page is clipped and the tracks below the
        # fold are simply gone. Page-sized pieces sharing one axis are the same
        # drawing, put where it fits.
        return "".join(_one_track_block(tracks[i:i + chunk], by_sym, x0d, today, span, p, W, name_w, row_h, pad_top, px)
                       for i in range(0, len(tracks), chunk))
    return _one_track_block(tracks, by_sym, x0d, today, span, p, W, name_w, row_h, pad_top, px)


def _one_track_block(tracks, by_sym, x0d, today, span, p: Palette, W, name_w, row_h, pad_top, px) -> str:
    H = pad_top + row_h * len(tracks) + 22
    out = []
    m = date(x0d.year, x0d.month, 1)
    while m <= today:
        x = px(m)
        if x >= name_w:
            out.append(f'<line x1="{x:.1f}" y1="{pad_top - 9}" x2="{x:.1f}" y2="{H - 18}" class="grid"/>')
            if m.month in (1, 4, 7, 10) or span < 200:
                out.append(f'<text x="{x + 3:.1f}" y="{pad_top - 13}">{m.strftime("%y.%m") if m.month != 1 else m.strftime("%Y")}</text>')
        m = date(m.year + (m.month // 12), m.month % 12 + 1, 1)
    out.append(f'<line x1="{px(today):.1f}" y1="{pad_top - 9}" x2="{px(today):.1f}" y2="{H - 18}" stroke="{p.mark}" stroke-width="1" stroke-dasharray="2 3"/>')
    out.append(f'<text x="{px(today) - 4:.1f}" y="{H - 5}" text-anchor="end">오늘</text>')
    for i, (label, a, b, is_open, sym) in enumerate(tracks):
        y = pad_top + i * row_h + 9
        out.append(f'<text x="0" y="{y + 4}" class="lbl" style="fill:{p.ink if is_open else p.ghost}">{_e(_fit(label, name_w - 14))}</text>')
        xa, xb = px(a), px(b)
        out.append(f'<line x1="{xa:.1f}" y1="{y}" x2="{max(xb, xa + 2):.1f}" y2="{y}" stroke="{p.mark if is_open else p.ghost}" stroke-width="{2.5 if is_open else 1.5}">'
                   f'<title>{_e(label)} · {a} → {"오늘" if is_open else b} · {(b - a).days}일</title></line>')
        for f in by_sym.get(sym, []):
            x = px(_d(f["date"]))
            if f["side"] == "in":
                out.append(f'<path d="M{x:.1f},{y - 2.5} l-3.5,-6.5 h7 z" fill="{p.rise}"><title>{f["date"]} 매수 {f["qty"]:g}주 @ {f["price"]:,}</title></path>')
            else:
                out.append(f'<path d="M{x:.1f},{y + 2.5} l-3.5,6.5 h7 z" fill="{p.fall}"><title>{f["date"]} 매도 {f["qty"]:g}주 @ {f["price"]:,} · {_pct(f.get("pnl_pct"))}</title></path>')
    return _svg(W, H, "종목별 보유 경로와 체결", out, p)


# ── realised, accumulating ──────────────────────────────────────────────────
def _cumulative_svg(sales: list[dict], p: Palette) -> str:
    """Realised P&L accumulating over the record.

    A total is a number; how it got there is a shape, and the report had no line
    in it at all. A step is the honest mark here — nothing happens between two
    sales, so a smoothed curve would draw motion that did not occur.
    """
    if len(sales) < 2:
        return ""
    pts, run = [], 0.0
    for s in sales:
        run += s["realised_krw"]
        pts.append((_d(s["date"]), run, s))
    W, left, right, top, H = 720, 16, 92, 20, 210
    base = H - 30
    x0, x1 = pts[0][0], pts[-1][0]
    span = max((x1 - x0).days, 1)
    lo, hi = min(0.0, min(v for _, v, _ in pts)), max(0.0, max(v for _, v, _ in pts))
    rng = (hi - lo) or 1
    px = lambda d: left + (d - x0).days / span * (W - left - right)  # noqa: E731
    py = lambda v: base - (v - lo) / rng * (base - top)  # noqa: E731
    out = []
    for frac in (0, .25, .5, .75, 1):
        v = lo + rng * frac
        y = py(v)
        out.append(f'<line x1="{left}" y1="{y:.1f}" x2="{W - right}" y2="{y:.1f}" class="grid"/>')
        out.append(f'<text x="{W - right + 6}" y="{y + 3.5:.1f}">{_kwon(v)}</text>')
    zy = py(0)
    out.append(f'<line x1="{left}" y1="{zy:.1f}" x2="{W - right}" y2="{zy:.1f}" class="axis"/>')
    d = [f"M{px(pts[0][0]):.1f},{zy:.1f}"]
    for dt, v, _ in pts:
        d.append(f"H{px(dt):.1f}")
        d.append(f"V{py(v):.1f}")
    path = " ".join(d)
    out.append(f'<path d="{path} V{zy:.1f} Z" fill="{p.mark}" opacity=".10"/>')
    out.append(f'<path d="{path}" fill="none" stroke="{p.mark}" stroke-width="1.6" stroke-linejoin="miter"/>')
    for dt, v, s in pts:
        if abs(s["realised_krw"]) >= rng * .12:
            out.append(f'<circle cx="{px(dt):.1f}" cy="{py(v):.1f}" r="2.6" fill="{p.rise if s["realised_krw"] > 0 else p.fall}">'
                       f'<title>{s["date"]} {_e(s["symbol"])} {_won(s["realised_krw"])} ({_pct(s["pnl_pct"])})</title></circle>')
    for dt, lab in ((x0, x0.strftime("%Y.%m")), (x1, x1.strftime("%Y.%m"))):
        anchor = "start" if dt == x0 else "end"
        out.append(f'<text x="{px(dt):.1f}" y="{H - 10}" text-anchor="{anchor}">{lab}</text>')
    # The running total belongs inside the plot, above its own last step: at the
    # right margin it sat on the top gridline's own label.
    out.append(f'<text x="{W - right - 6}" y="{max(py(pts[-1][1]) - 9, top + 9):.1f}" text-anchor="end" '
               f'class="fig" style="fill:{p.ink}">{_won(pts[-1][1])}</text>')
    return _svg(W, H, "실현손익 누적", out, p)


# ── every closed trade ──────────────────────────────────────────────────────
def _trade_scatter_svg(sales: list[dict], p: Palette) -> str:
    """Holding days against realised return, one mark per closed trade.

    The medians say losses are held longer; this says whether that is a rule or
    an average of two habits. Days run on a log axis because the trades span one
    day to a year, and the mark's area carries what the trade was worth so a
    ₩1M decision does not read the same as a ₩10k one.
    """
    if len(sales) < 3:
        return ""
    W, left, right, top, H = 720, 48, 30, 22, 306
    base = H - 42
    days = [max(s["held_days"], 0.6) for s in sales]
    pcts = [s["pnl_pct"] for s in sales]
    krw = [abs(s["realised_krw"]) for s in sales]
    lo_d, hi_d = math.log10(min(days)), math.log10(max(max(days), 2))
    span_d = (hi_d - lo_d) or 1
    lo_p, hi_p = min(min(pcts), 0), max(max(pcts), 0)
    pad = (hi_p - lo_p) * .08 or 1
    lo_p, hi_p = lo_p - pad, hi_p + pad
    mk = max(krw) or 1
    px = lambda v: left + (math.log10(v) - lo_d) / span_d * (W - left - right)  # noqa: E731
    py = lambda v: base - (v - lo_p) / (hi_p - lo_p) * (base - top)  # noqa: E731
    out = []
    for t in (1, 7, 30, 90, 180, 365):
        if not (min(days) * .9 <= t <= max(days) * 1.1):
            continue
        x = px(t)
        out.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{base}" class="grid"/>')
        out.append(f'<text x="{x:.1f}" y="{base + 15}" text-anchor="middle">{t}일</text>')
    for v in _ticks(lo_p, hi_p):
        y = py(v)
        out.append(f'<line x1="{left}" y1="{y:.1f}" x2="{W - right}" y2="{y:.1f}" class="{"axis" if v == 0 else "grid"}"/>')
        out.append(f'<text x="{left - 8}" y="{y + 3.5:.1f}" text-anchor="end">{v:+.0f}%</text>')
    for s in sorted(sales, key=lambda s: abs(s["realised_krw"])):
        r = 2.4 + math.sqrt(abs(s["realised_krw"]) / mk) * 8
        colour = p.rise if s["pnl_pct"] > 0 else p.fall
        out.append(f'<circle cx="{px(max(s["held_days"], 0.6)):.1f}" cy="{py(s["pnl_pct"]):.1f}" r="{r:.1f}" '
                   f'fill="{colour}" fill-opacity=".42" stroke="{colour}" stroke-width="1">'
                   f'<title>{_e(s["symbol"])} {s["date"]} · 보유 {s["held_days"]}일 · {_pct(s["pnl_pct"])} · {_won(s["realised_krw"])}</title></circle>')
    out.append(f'<text x="{left}" y="{base + 30}">보유 기간 →</text>')
    return _svg(W, H, "닫힌 거래: 보유 기간과 수익률", out, p)


def _ticks(lo: float, hi: float) -> list[float]:
    """Round tick values that include zero, at most six of them."""
    raw = (hi - lo) / 5
    mag = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1
    step = min((m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw), default=mag)
    out, v = [], math.ceil(lo / step) * step
    while v <= hi and len(out) < 8:
        out.append(round(v, 6))
        v += step
    return out or [0.0]


# ── after selling ───────────────────────────────────────────────────────────
def _slope_svg(rows: list[dict], p: Palette) -> str:
    """Each sold-out symbol as one line from the day it was sold to now.

    Both ends start at the same place — the sale, at zero — so the slope alone
    carries the whole comparison, which is the one thing a bar chart of "since
    sale %" cannot show: that these all left from the same gate.
    """
    if len(rows) < 2:
        return ""
    W, left, right, top, H = 720, 92, 128, 22, 300
    base = H - 26
    pcts = [r["since_sale_pct"] for r in rows]
    hi = max(max(pcts), 0) * 1.06 or 1
    lo = min(min(pcts), 0) * 1.06 or -1
    py = lambda v: base - (v - lo) / (hi - lo) * (base - top)  # noqa: E731
    out = []
    for v in _ticks(lo, hi):
        y = py(v)
        out.append(f'<line x1="{left}" y1="{y:.1f}" x2="{W - right}" y2="{y:.1f}" class="{"axis" if v == 0 else "grid"}"/>')
        out.append(f'<text x="{left - 8}" y="{y + 3.5:.1f}" text-anchor="end">{v:+.0f}%</text>')
    out.append(f'<text x="{left}" y="{base + 16}" text-anchor="middle">판 날</text>')
    out.append(f'<text x="{W - right}" y="{base + 16}" text-anchor="middle">오늘</text>')
    zy = py(0)
    named = sorted(rows, key=lambda r: -abs(r["since_sale_pct"]))[:6]
    for r in sorted(rows, key=lambda r: abs(r["since_sale_pct"])):
        y = py(r["since_sale_pct"])
        colour = p.rise if r["since_sale_pct"] > 0 else p.fall
        strong = r in named
        out.append(f'<line x1="{left}" y1="{zy:.1f}" x2="{W - right}" y2="{y:.1f}" stroke="{colour}" '
                   f'stroke-width="{1.5 if strong else 1}" stroke-opacity="{0.95 if strong else 0.4}">'
                   f'<title>{_e(_nm(r["symbol"], r.get("name")))} · {r["last_sold_at"]} 매도 {r["avg_sell_price"]:,} → 지금 {r["price_now"]:,} · '
                   f'{_pct(r["since_sale_pct"])} · 안 팔았다면 {_won(r["kept_delta_krw"])}</title></line>')
        out.append(f'<circle cx="{W - right}" cy="{y:.1f}" r="{2.6 if strong else 1.8}" fill="{colour}"/>')
    # Six lines can land within a few pixels of each other at the right edge, and
    # six labels stacked on one another read as none. Place them in order and
    # push each clear of the one above.
    placed: list[float] = []
    for r in sorted(named, key=lambda r: -r["since_sale_pct"]):
        y = py(r["since_sale_pct"])
        if placed and y - placed[-1] < 12:
            y = placed[-1] + 12
        placed.append(y)
        out.append(f'<text x="{W - right + 8}" y="{y + 3.5:.1f}" class="fig">'
                   f'{_e(_fit(r["symbol"], 74))} {r["since_sale_pct"]:+.0f}%</text>')
    out.append(f'<circle cx="{left}" cy="{zy:.1f}" r="3" fill="{p.ink}"/>')
    return _svg(W, H, "정리한 종목: 판 날 대비 지금", out, p)


# ── the rhythm of the fills ─────────────────────────────────────────────────
_WEEK = ("월", "화", "수", "목", "금", "토", "일")


def _matrix_svg(tm: dict, p: Palette) -> str:
    """Fills as a weekday x hour matrix.

    Two bar charts of the margins cannot show an interaction: "Friday nights" is
    invisible in a Friday total and in a 22:00 total, and this account trades two
    markets whose sessions sit in different halves of the clock.
    """
    grid = tm.get("matrix")
    if not grid:
        return ""
    W, left, top, cell, gap = 720, 34, 24, 26.5, 2
    rows, cols = 7, 24
    H = top + rows * cell + 42
    mx = max(max(r) for r in grid) or 1
    out = []
    for h in range(0, 24, 3):
        out.append(f'<text x="{left + h * cell + cell / 2:.1f}" y="{top - 8}" text-anchor="middle">{h:02d}</text>')
    for d in range(rows):
        y = top + d * cell
        out.append(f'<text x="{left - 9}" y="{y + cell / 2 + 3.5:.1f}" text-anchor="end" class="lbl">{_WEEK[d]}</text>')
        for h in range(cols):
            n = grid[d][h]
            x = left + h * cell
            if not n:
                out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell - gap:.1f}" height="{cell - gap:.1f}" fill="{p.grid}" opacity=".55"/>')
                continue
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell - gap:.1f}" height="{cell - gap:.1f}" fill="{p.mark}" '
                       f'fill-opacity="{0.16 + 0.84 * (n / mx):.2f}"><title>{_WEEK[d]} {h:02d}시 · {n}건</title></rect>')
            if n >= mx * .5:
                out.append(f'<text x="{x + (cell - gap) / 2:.1f}" y="{y + cell / 2 + 3:.1f}" text-anchor="middle" style="fill:{p.ground}">{n}</text>')
    bands = [(9, 15, "KR 정규"), (22, 24, "US 정규"), (0, 6, "US 정규")]
    by = top + rows * cell + 9
    for a, b, lab in bands:
        x1, x2 = left + a * cell, left + b * cell - gap
        out.append(f'<line x1="{x1:.1f}" y1="{by}" x2="{x2:.1f}" y2="{by}" stroke="{p.rule}" stroke-width="1"/>')
        out.append(f'<text x="{(x1 + x2) / 2:.1f}" y="{by + 14}" text-anchor="middle">{lab}</text>')
    return _svg(W, H, "요일과 시간대별 체결", out, p)


# ── contribution ────────────────────────────────────────────────────────────
def _attribution_svg(rows: list[dict], p: Palette) -> str:
    """One diverging bar per symbol: realised plus unrealised, in KRW."""
    if not rows:
        return ""
    shown = rows if len(rows) <= 14 else rows[:7] + rows[-7:]
    folded = len(rows) - len(shown)
    W, name_w, right, bar_h, row_h, pad_top = 720, 196, 104, 15, 25, 18
    plot_w = W - name_w - right
    mx = max(abs(r["total_krw"]) for r in shown) or 1
    neg = max(0, -min(r["total_krw"] for r in shown))
    zero = name_w + plot_w * (neg / (mx + neg)) if any(r["total_krw"] < 0 for r in shown) else name_w
    scale = (W - right - zero) / mx if any(r["total_krw"] > 0 for r in shown) else (zero - name_w) / mx
    H = pad_top + row_h * len(shown) + (row_h if folded else 0) + 8
    out = [f'<line x1="{zero:.1f}" y1="{pad_top - 6}" x2="{zero:.1f}" y2="{H - 4}" class="axis"/>']
    for i, r in enumerate(shown):
        y = pad_top + i * row_h + (row_h if folded and i >= 7 else 0)
        v = r["total_krw"]
        w = abs(v) * scale
        x = zero if v >= 0 else zero - w
        colour = p.rise if v > 0 else p.fall
        label = _nm(r["symbol"], r["name"])
        out.append(f'<text x="0" y="{y + bar_h / 2 + 4}" class="lbl" fill="{p.ink if r["held"] else p.ghost}">{_e(_fit(label, name_w - 14))}</text>')
        out.append(f'<rect x="{x:.1f}" y="{y}" width="{max(w, 1):.1f}" height="{bar_h}" fill="{colour}">'
                   f'<title>{_e(label)} · 실현 {_won(r["realised_krw"])} · 미실현 {_won(r["unrealised_krw"])} · 합계 {_won(v)}</title></rect>')
        # Loss figures sit just right of the zero line, where no bar competes for
        # the space, so a long loss bar never runs its figure into the names.
        tx = zero + w + 7 if v >= 0 else zero + 7
        out.append(f'<text x="{tx:.1f}" y="{y + bar_h / 2 + 4}" class="fig">{_won(v)}</text>')
        if folded and i == 6:
            out.append(f'<text x="{zero:.1f}" y="{y + row_h + bar_h / 2 + 4}" text-anchor="middle">중간 {folded}종목 생략</text>')
    return _svg(W, H, "종목별 손익 기여", out, p)


# ── one symbol at a time ────────────────────────────────────────────────────
_REL = {"below": "아래", "above": "위", "flat": "와 같은 값"}


def _track_svg(c: dict, p: Palette) -> str:
    """The average-cost track for one symbol, with every fill on it.

    A broker shows today's average and nothing about how it got there. Drawn,
    the two habits separate on sight: buys under the line walk it down, buys
    over it walk it up, and the line is flat wherever nothing was bought.

    Sized to one card — 300 units — rather than to the page, and 300 is not a
    round number chosen for looks: it is inside the narrowest card the layout
    can produce, an A4 column (695) less the plate indent (34), halved, less
    half the gutter, which is 316. WeasyPrint lays a viewBox'd SVG out at its
    intrinsic width and then clips it to the cell instead of scaling it down,
    so anything wider loses its right-hand figures in the PDF while looking
    perfect on screen. Draw for the narrowest case and both are right.
    """
    track = c.get("track") or []
    if not track:
        return ""
    xs = [_d(t["date"]) for t in track]
    d0, d1 = min(xs), max(xs)
    span = max((d1 - d0).days, 1)
    W, H, left, top, bot = 300, 94, 6, 12, 16
    # The right gutter is the widest end label, not a guess: "71,999" and
    # "1,234,567" are 40px apart in mono, and a gutter cut for the first clips
    # the second against the edge of the drawing, where SVG hides it silently.
    now = (c["avg_now"] * (1 + c["unrealised_rate_pct"] / 100)
           if c["held"] and c.get("avg_now") and c.get("unrealised_rate_pct") is not None else None)
    ends = [_price(v, c["currency"]) for v in (c.get("avg_now"), track[-1]["price"], now) if v is not None]
    right = min(max(7 + max(len(e) for e in ends) * 6.6, 44), 86)
    plot_w = W - left - right
    ys = ([t["price"] for t in track]
          + [t["avg_after"] for t in track if t["avg_after"] is not None]
          + ([now] if now is not None else []))
    lo, hi = min(ys), max(ys)
    pad = (hi - lo) * 0.14 or (hi or 1) * 0.04
    lo, hi = lo - pad, hi + pad
    px = lambda d: left + (d - d0).days / span * plot_w          # noqa: E731
    py = lambda v: H - bot - (v - lo) / (hi - lo) * (H - bot - top)  # noqa: E731

    out = [f'<line x1="{left}" y1="{H - bot + 1}" x2="{W - right:.1f}" y2="{H - bot + 1}" class="grid"/>']
    # The average-cost line is a step: it moves only where a purchase moved it,
    # and it ends where the position was emptied rather than sliding across the
    # gap to the next holding.
    seg: list[str] = []
    prev = None
    for t, x in zip(track, (px(d) for d in xs)):
        a = t["avg_after"]
        if a is None:
            if prev is not None:
                seg.append(f"{x:.1f},{py(prev):.1f}")
            if len(seg) > 1:
                out.append(f'<polyline points="{" ".join(seg)}" fill="none" stroke="{p.mark}" stroke-width="1.6"/>')
            seg, prev = [], None
            continue
        if prev is not None:
            seg.append(f"{x:.1f},{py(prev):.1f}")
        seg.append(f"{x:.1f},{py(a):.1f}")
        prev = a
    if prev is not None:
        seg.append(f"{W - right:.1f},{py(prev):.1f}")
        if len(seg) > 1:
            out.append(f'<polyline points="{" ".join(seg)}" fill="none" stroke="{p.mark}" stroke-width="1.6"/>')

    for t, d in zip(track, xs):
        x, y = px(d), py(t["price"])
        buy = t["side"] == "BUY"  # // legal-ok — Toss enum, compared only
        colour = p.rise if buy else p.fall
        tip = f'{t["date"]} {"매수" if buy else "매도"} {_price(t["price"], c["currency"])} x {t["qty"]:g}'
        if t.get("relation"):
            tip += f' · 평단 {_price(t["avg_before"], c["currency"])} {_REL[t["relation"]]}'
        if t.get("pnl_pct") is not None:
            tip += f' · {_pct(t["pnl_pct"])}'
        m = (f'{x:.1f},{y - 3.4:.1f} {x - 3.1:.1f},{y + 2.4:.1f} {x + 3.1:.1f},{y + 2.4:.1f}' if buy
             else f'{x:.1f},{y + 3.4:.1f} {x - 3.1:.1f},{y - 2.4:.1f} {x + 3.1:.1f},{y - 2.4:.1f}')
        out.append(f'<polygon points="{m}" fill="{colour}"><title>{_e(tip)}</title></polygon>')

    if prev is not None:
        out.append(f'<text x="{W - right + 5:.1f}" y="{py(prev) + 3.4:.1f}" class="fig" style="fill:{p.mark}">'
                   f'{_e(_price(prev, c["currency"]))}</text>')
    else:
        # A position that was emptied has no average left to label, and without
        # one the drawing carries no figure at all — the last sale is the number
        # the reader is looking for there.
        last = track[-1]
        out.append(f'<text x="{W - right + 5:.1f}" y="{py(last["price"]) + 3.4:.1f}" class="fig" style="fill:{p.fall}">'
                   f'{_e(_price(last["price"], c["currency"]))}</text>')
    if now is not None:
        yn = py(now)
        colour = p.rise if now >= (prev or now) else p.fall
        out.append(f'<circle cx="{W - right:.1f}" cy="{yn:.1f}" r="2.8" fill="{colour}">'
                   f'<title>지금 {_e(_price(now, c["currency"]))}</title></circle>')
        # The two end labels are the same two numbers the reader is comparing,
        # so they must not land on each other when the position sits near even.
        if abs(yn - py(prev)) < 10:
            yn = py(prev) + (11 if now < (prev or now) else -11)
        out.append(f'<text x="{W - right + 5:.1f}" y="{yn + 3.4:.1f}" class="fig" style="fill:{colour}">'
                   f'{_e(_price(now, c["currency"]))}</text>')
    out.append(f'<text x="{left}" y="{H - 4}">{d0.strftime("%y.%m")}</text>')
    if d1 != d0:
        out.append(f'<text x="{W - right:.1f}" y="{H - 4}" text-anchor="end">{d1.strftime("%y.%m")}</text>')
    return (f'<svg class="spark" viewBox="0 0 {W} {H}" role="img" '
            f'aria-label="{_e(c["symbol"])} 평단 궤적">' + _typeset("".join(out), p) + "</svg>")


def _fo_phrase(fo: dict) -> str:
    """"평단 아래 4 · 위 2", never the two nicknames those two counts have.

    The report describes and does not label: a nickname is a verdict wearing a
    noun, and the whole point of the drawing beside this line is that the reader
    can see which one it was without being told.
    """
    bits = [f"{lab} {fo[k]}" for k, lab in (("below", "평단 아래"), ("above", "위"), ("flat", "같은 값")) if fo[k]]
    return "추가 매수 " + " · ".join(bits) if bits else "추가 매수 없음"


def _symbol_cards(sy: dict, p: Palette) -> str:
    """The cards, two to a row where there is room for two.

    A CSS table rather than a grid: this document's other renderer has no grid,
    and a card that silently drops out of the flow in the PDF is the failure
    that would not show up on screen.
    """
    cards = sy.get("cards") or []
    if not cards:
        return '<p class="cap dim">체결 이력이 있는 종목 없음</p>'
    cells = []
    for c in cards:
        head = (f'<div class="ch"><span class="s">{_e(_fit(_nm(c["symbol"], c["name"]), 216, 13))}</span>'
                f'<span class="w">{_pct(c["weight_pct"], False) if c["held"] else "정리함"}</span></div>')
        line1 = " · ".join(filter(None, [
            f'보유 {_days(c["held_days"])}' if c["held"] and c["held_days"] is not None else None,
            f'매수 {c["buys"]} · 매도 {c["sells"]}',
            _fo_phrase(c["follow_on"]),
        ]))
        closed = (f'닫힌 {c["closed"]}건 중 {c["wins"]}승 ({c["win_rate_pct"]}%) · 중앙값 {_pct(c["median_sell_pct"])}'
                  if c["closed"] else "닫은 거래 없음")
        # Label over figure, not label beside figure: three ₩ amounts in one
        # nowrap row is ~430px of min-content and the card has 360.
        figs = ('<table class="cf"><tr><th>실현</th><th>미실현</th><th>합계</th></tr><tr>'
                + "".join(f'<td class="{_cls(c[k])}">{_won(c[k])}</td>'
                          for k in ("realised_krw", "unrealised_krw", "total_krw"))
                + "</tr></table>")
        note = f'<p class="cn">{_e(c["note"])}</p>' if c.get("note") else ""
        cells.append(f'<div class="card">{head}<p class="cm">{_e(line1)}</p>{_track_svg(c, p)}'
                     f'<p class="cm">{_e(closed)}</p>{figs}{note}</div>')
    if len(cells) % 2:
        cells.append('<div class="card"></div>')
    rows = "".join(f'<div class="crow">{cells[i]}{cells[i + 1]}</div>' for i in range(0, len(cells), 2))
    return f'<div class="cards">{rows}</div>'


def _split_bar_svg(kr: float | None, us: float | None, p: Palette) -> str:
    if kr is None:
        return ""
    W, H = 720, 40
    kw = kr / 100 * W
    return _svg(W, H, "국내 해외 비중", [
        f'<rect x="0" y="8" width="{max(kw - 1.5, 0):.1f}" height="13" fill="{p.mark}"><title>국내 {kr:.2f}%</title></rect>',
        f'<rect x="{kw + 1.5:.1f}" y="8" width="{max(W - kw - 1.5, 0):.1f}" height="13" fill="{p.mark}" opacity=".38"><title>해외 {us:.2f}%</title></rect>',
        f'<text x="0" y="36" class="fig">국내 {kr:.2f}%</text>',
        f'<text x="{W}" y="36" text-anchor="end" class="fig">해외 {us:.2f}%</text>'], p)


# ── the mirror table ─────────────────────────────────────────────────────────
def _mirror_table(m: dict, window_days: int) -> str:
    w, a = m["window"], m["all"]

    def t(block, key):
        return block["turnover"].get(key)

    def side(block, s, key):
        x = block["profit_loss"].get(s)
        return x.get(key) if x else None

    def fo(block, key):
        return block["follow_on"].get(key)

    rows = [
        ("체결", f"{t(w,'trade_count') or 0}건 (매수 {t(w,'buy_count') or 0} · 매도 {t(w,'sell_count') or 0})",
                f"{t(a,'trade_count') or 0}건 (매수 {t(a,'buy_count') or 0} · 매도 {t(a,'sell_count') or 0})"),
        ("매수→매도 보유 중앙값", _days(t(w, "median_hold_days")), _days(t(a, "median_hold_days"))),
        ("이미 보유한 종목 추가 매수", _fo(fo(w, "follow_on_count"), fo(w, "below_avg_count"), fo(w, "above_avg_count")),
                                  _fo(fo(a, "follow_on_count"), fo(a, "below_avg_count"), fo(a, "above_avg_count"))),
        ("이익을 실현한 매도", _side(side(w, "take_profit", "count"), side(w, "take_profit", "median_hold_days"), side(w, "take_profit", "median_gain_pct")),
                          _side(side(a, "take_profit", "count"), side(a, "take_profit", "median_hold_days"), side(a, "take_profit", "median_gain_pct"))),
        ("손실을 실현한 매도", _side(side(w, "stop_loss", "count"), side(w, "stop_loss", "median_hold_days"), side(w, "stop_loss", "median_loss_pct")),
                          _side(side(a, "stop_loss", "count"), side(a, "stop_loss", "median_hold_days"), side(a, "stop_loss", "median_loss_pct"))),
    ]
    body = "".join(f"<tr><td>{_e(k)}</td><td>{_e(x)}</td><td>{_e(y)}</td></tr>" for k, x, y in rows)
    ages = m["open_lot_ages_days"]
    foot = (f'<p class="cap">지금 들고 있는 매수분 {ages["lots"]}건의 나이: 중앙값 {_days(ages["median"])} · 가장 오래된 것 {_days(ages["oldest"])}</p>'
            if ages["lots"] else "")
    return (f'<div class="tbl"><table class="mirror"><thead><tr><th></th><th>최근 {window_days}일</th><th>전체 이력</th></tr></thead>'
            f'<tbody>{body}</tbody></table></div>{foot}')


def _fo(n, below, above) -> str:
    return "없음" if not n else f"{n}건 · 평단 아래 {below} / 위 {above}"


def _side(n, hold, pct) -> str:
    return "없음" if not n else f"{n}건 · 보유 {_days(hold)} · {pct:+.2f}%"


def _mismatch_qty(mm: dict) -> str:
    if mm["kind"] in ("unmatched_sales", "fractional_dust"):
        return f"{mm.get('unmatched_sell_qty', 0):g}주"
    if mm["kind"] == "absent":
        return f"토스 {mm['toss_qty']:g}주"
    return f"이력 {mm['rebuilt_qty']:g}주 / 토스 {mm['toss_qty']:g}주"


def _history_status(h: dict) -> str:
    if h["complete"]:
        return (f'<p class="recon">이력으로 되짚은 보유 {h["checked_symbols"]}종목의 수량·평균단가가 '
                f'<strong>토스 잔고와 전부 일치</strong>한다. 아래 실현손익은 전체 이력 기준이다.</p>')
    trust = h.get("realised_trustworthy")
    items = "".join(
        f'<li><span class="s">{_e(m["symbol"])}<em>{_e(_mismatch_qty(m))}</em></span>'
        f'<span>{_em(m["reason"])}</span></li>'
        for m in h["mismatches"])
    verdict = ("주식 수가 바뀐 것뿐이고 들어오거나 나간 주식은 없다 — <strong>실현손익은 그대로 신뢰할 수 있다</strong>."
               if trust else "<strong>실현손익은 이만큼 비어 있다</strong>.")
    return (f'<p class="recon">이력으로 되짚은 결과가 토스 잔고와 '
            f'<strong>{len(h["mismatches"])}종목에서 다르다</strong>. {verdict}</p>'
            f'<ul class="rlist">{items}</ul>')


class _Plates:
    """The plates in the order they are added, numbered on the way out.

    They used to carry their numbers as literals at the call site, which meant
    inserting one in the middle was a rename of every plate after it — and a
    number that disagrees with the caption pointing at it is worse than no
    number at all.
    """

    def __init__(self) -> None:
        self._items: list[tuple[str, str, str]] = []

    def add(self, title: str, basis: str, body: str) -> None:
        self._items.append((title, basis, body))

    def html(self) -> str:
        return "".join(
            f'<section class="plate"><div class="ph"><span class="n">{i:02d}</span>'
            f'<h2>{_e(title)}</h2><span class="basis">{_e(basis)}</span></div>'
            f'<div class="body">{body}</div></section>'
            for i, (title, basis, body) in enumerate(self._items, 1))


def render_mirror_html(rep: dict, *, paper: bool = False) -> str:
    """The record as one self-contained page.

    ``paper=True`` renders it on chart stock for print and for PDF; the default
    is the same record under a lamp. Neither is a translation of the other — the
    marks are re-stepped so the instrument ink and the polarity pair read as
    themselves on both grounds.
    """
    p = STOCK if paper else SCREEN
    # A4 less its margins is 184mm wide, so one viewBox unit is 0.256mm and a
    # 265mm column holds ~1035 of them. Leaving a plate head and caption their
    # share, a drawing gets ~880: 34 timeline tracks at 25 units, 29 holdings
    # rows at 29. A lamp has no fold and needs no cap.
    tracks_per_page = 34 if paper else None
    rows_per_page = 29 if paper else None

    v, c, h = rep["valuation"], rep["concentration"], rep["history"]
    an = rep.get("analysis") or {}
    t = an.get("trades") or {}
    a = an.get("attribution") or {}
    af = an.get("after_selling") or {}
    tm = an.get("timing") or {}
    sz = an.get("sizing") or {}
    bm = an.get("by_market") or []
    sales = t.get("sales") or []
    acct = rep["account"]["account_no_masked"]
    gen = rep["generated_at"][:16].replace("T", " ")
    n_dep = len(rep["departed"])
    n_hold = c["positions"]

    basis = "전체 이력" if h.get("realised_trustworthy", h["complete"]) else "부분 이력"
    stmt = _stmt([
        ("주식 평가액", _won(v["equity_value_krw"]), "", "", ""),
        ("국내", _won(v["krw_leg"]), "", "", "sub"),
        ("해외", f"${(v['usd_leg'] or 0):,.2f}", f"USD/KRW {rep['fx']['usdkrw']}", "", "sub"),
        ("매입 총액", _won(v["purchase_total_krw"]), "", "", ""),
        ("미실현 손익", _won(v["unrealised_krw"]), _pct(v["unrealised_rate_pct"]), _cls(v["unrealised_krw"]), "rule big"),
        ("실현 손익 누계", _won(h["realised_net_krw"]), basis, _cls(h["realised_net_krw"]), "big"),
        ("당일", _won(v["daily_krw"]), _pct(v["daily_rate_pct"]), _cls(v["daily_krw"]), "rule"),
    ])

    heads = an.get("headline") or []
    lead = f'<div class="lead"><p>{_e(heads[0])}</p></div>' if heads else ""
    finds = "".join(f"<li>{_e(x)}</li>" for x in heads[1:])
    finds = f'<ul class="finds">{finds}</ul>' if finds else ""

    plates = _Plates()
    plates.add("평가", f"{gen} KST", stmt
               + f'<p class="cap">실현 손익 누계는 <b>{_e(basis)}</b> · 수수료·세금 차감 기준이다.</p>')
    plates.add("이력 대조", f"체결 {h['fills']}건", _history_status(h)
               + f'<p class="cap">조회 시작 {_e(h["since"] or "전체")} · 첫 체결 {_e(h["first_fill_at"] or "—")}</p>')

    conc = (f'가장 큰 종목은 <b>{_e(_nm(c["largest"]["symbol"], c["largest"]["name"]))}</b>, 평가액의 {c["largest"]["weight_pct"]:.2f}%. '
            f'30% 선을 넘는 종목: {_e(", ".join(c["over_30pct"]) if c["over_30pct"] else "없음")}.' if c["largest"] else "보유 종목 없음.")
    plates.add("보유 구성", f"{n_hold}종목",
                         f'{_holdings_svg(rep["holdings"], p, rows_per_page)}'
                         f'<div class="legend"><span><i style="background:{p.mark}"></i>비중</span>'
                         f'<span><i style="background:{p.rise}"></i>평단 위</span>'
                         f'<span><i style="background:{p.fall}"></i>평단 아래</span></div>'
                         f'<p class="cap">왼쪽은 평가액에서 차지하는 몫, 오른쪽은 평단 대비 지금 위치. 같은 줄이 같은 종목이다. {conc}</p>'
                         f'{_split_bar_svg(c["kr_pct"], c["us_pct"], p)}')

    if (sy := an.get("symbols") or {}).get("cards"):
        plates.add("종목 하나하나", f"{sy['held_shown']}종목 보유 · 카드 {len(sy['cards'])}장",
                   '<p class="cap">앞의 표가 종목을 세로로 세운다면 여기는 한 종목씩 옆으로 눕힌다. '
                   '초록 선이 <b>평단</b>이고, 매수 ▲ 가 그 선을 어디로 옮겼는지가 이 그림의 전부다 — '
                   '선 아래에서 산 것들은 평단을 끌어내리고, 위에서 산 것들은 밀어올린다. '
                   '선이 끊긴 자리는 그 종목을 한 번 비웠다는 뜻이고, 오른쪽 끝의 점은 지금 가격이다.'
                   + (f' 기여가 작은 {sy["folded"]}종목은 카드 없이 원장에만 있다.' if sy.get("folded") else "")
                   + '</p>'
                   + _symbol_cards(sy, p))

    plates.add("경로", f"보유 {n_hold} · 정리 {n_dep}",
                         f'{_timeline_svg(rep, p, tracks_per_page)}'
                         f'<div class="legend"><span><i style="background:{p.mark}"></i>보유 중</span>'
                         f'<span><i style="background:{p.ghost}"></i>정리함</span>'
                         f'<span style="color:{p.rise}">▲ 매수</span><span style="color:{p.fall}">▼ 매도</span></div>'
                         f'<p class="cap">종목마다 처음 산 날부터 오늘까지의 선. 위쪽 삼각형이 매수, 아래쪽이 매도.</p>')

    if (cum := _cumulative_svg(sales, p)):
        plates.add("실현손익 누적", f"매도 {len(sales)}건", cum
                             + '<p class="cap">매도가 있을 때만 값이 바뀌므로 계단이다. 사이의 평평한 구간은 아무 일도 없었다는 뜻이지 '
                               '변화가 없었다는 뜻이 아니다 — 그 동안의 변화는 미실현 쪽에 있다. 점은 한 건이 전체 폭의 12%를 넘게 움직인 매도.</p>')

    if (sc := _trade_scatter_svg(sales, p)):
        closed = _stmt([
            ("닫힌 거래", f"{t['closed']}건", f"이익 {t['wins']} · 손실 {t['losses']}", "", ""),
            ("승률", f"{t['win_rate_pct']}%", "", "", ""),
            ("이익/손실 크기 비", str(t["payoff_ratio"] or "—"), "", "", ""),
            ("거래당 기대값", _won(t["expectancy_krw"]), f"중앙값 {_won(t['median_trade_krw'])}",
             _cls(t["expectancy_krw"]), "rule big"),
        ])
        extremes = (f'<p class="cap">최고 {_e(t["best"]["symbol"])} {t["best"]["date"]} {_won(t["best"]["realised_krw"])} '
                    f'({_pct(t["best"]["pnl_pct"])}) · 최저 {_e(t["worst"]["symbol"])} {t["worst"]["date"]} '
                    f'{_won(t["worst"]["realised_krw"])} ({_pct(t["worst"]["pnl_pct"])})'
                    + (f' · 실현 이익의 {t["top5_share_pct"]}%가 상위 5건' if t.get("top5_share_pct") else "") + "</p>")
        plates.add("닫힌 거래 하나하나", f"{t.get('closed')}건",
                             closed + extremes + sc + f'<p class="cap">가로는 보유 기간(로그), 세로는 실현 수익률, 원의 넓이는 그 거래의 크기. '
                                  f'중앙값은 <b>이익 {_days(t.get("win_hold_median_days"))} / 손실 {_days(t.get("loss_hold_median_days"))}</b> '
                                  f'이지만 그것이 규칙인지 두 습관의 평균인지는 이 흩어짐이 말한다. '
                                  f'왼쪽 위에 몰리고 오른쪽 아래로 끌리면 이익은 빨리 끊고 손실은 오래 쥔 것이다.</p>')

    if a.get("rows"):
        plates.add("손익 기여", f"실현+미실현 {_won(a['total_krw'])}",
                             f'<p class="cap">실현 <span class="{_cls(a["realised_krw"])}">{_won(a["realised_krw"])}</span> + '
                             f'미실현 <span class="{_cls(a["unrealised_krw"])}">{_won(a["unrealised_krw"])}</span> = '
                             f'<b>{_won(a["total_krw"])}</b> · 수수료·세금 {_won(a["fees_krw"])}. 흐린 이름은 이미 정리한 종목.</p>'
                             f'{_attribution_svg(a["rows"], p)}')

    if af.get("available") and af.get("count"):
        rows = "".join(f'<tr><td>{_e(_nm(r["symbol"], r["name"]))}</td><td>{_e(r["last_sold_at"])}</td><td class="n">{r["avg_sell_price"]:,}</td>'
                       f'<td class="n">{r["price_now"]:,}</td><td class="n {_cls(r["since_sale_pct"])}">{_pct(r["since_sale_pct"])}</td>'
                       f'<td class="n {_cls(r["kept_delta_krw"])}">{_won(r["kept_delta_krw"])}</td></tr>' for r in af["rows"])
        plates.add("팔고 난 뒤", f"{af['count']}종목",
                             _slope_svg(af["rows"], p)
                             + f'<p class="cap">정리한 {af["count"]}종목이 전부 같은 자리(판 날, 0%)에서 출발한다. '
                               f'지금 판 가격보다 위인 것 <b>{af["higher_now"]}</b>, 아래인 것 {af["lower_now"]}, 이후 변화 중앙값 {_pct(af["median_since_sale_pct"])}. '
                               f'판 수량을 그대로 들고 있었다면 지금 <span class="{_cls(af["kept_delta_krw"])}">{_won(af["kept_delta_krw"])}</span> 차이.</p>'
                               f'<div class="tbl"><table class="plain"><thead><tr><th>종목</th><th>마지막 매도</th><th>평균 매도가</th>'
                               f'<th>지금</th><th>이후</th><th>안 팔았다면</th></tr></thead><tbody>{rows}</tbody></table></div>')

    if (mx := _matrix_svg(tm, p)):
        plates.add("체결의 리듬", f"체결 {tm['fills']}건",
                             mx + f'<p class="cap">거래일 {tm["trade_days"]}일 · 하루 평균 {tm["fills_per_trade_day"]}건 · '
                                  f'3건 이상인 날 {tm["days_with_3plus"]}일 · 최다 {tm["busiest_day"]["date"]} {tm["busiest_day"]["fills"]}건'
                                  + (f' · 국내 체결 중 개장 첫 시간 {tm["kr_first_hour_pct"]}%' if tm.get("kr_first_hour_pct") is not None else "")
                                  + '. 두 시장의 정규장이 시계의 반대편에 있어 요일과 시간을 따로 세면 서로를 가린다.</p>')

    plates.add("거울", f"최근 {rep['window_days']}일 대 전체",
                         '<p class="cap">같은 잣대를 두 기간에 나란히 댄다. 두 열이 다르면 최근이 평소와 다른 것이다. '
                         '최근 열의 평단·보유일은 전체 이력을 딛고 계산한다.</p>'
                         + _mirror_table(rep["mirrors"], rep["window_days"]))

    hold_rows = "".join(
        f'<tr><td>{_e(_nm(r["symbol"], r["name"]))}</td><td>{_e(r["opened_at"] or "이력 밖")}</td><td class="n">{_days(r["held_days"])}</td>'
        f'<td class="n">{r["buys"]}/{r["sells"]}</td><td>{_e(r["last_fill_at"] or "—")}</td><td class="n">{r["quantity"]:g}</td>'
        f'<td class="n">{r["avg_purchase_price"]:,}</td><td class="n {_cls(r["unrealised_rate_pct"])}">{_pct(r["unrealised_rate_pct"])}</td></tr>'
        for r in rep["holdings"])
    dep_rows = "".join(
        f'<tr><td>{_e(_nm(d["symbol"], d["name"]))}{" (이력 불완전)" if d["oversold"] else ""}</td><td>{_e(d["first_fill_at"])}</td><td>{_e(d["last_fill_at"])}</td>'
        f'<td class="n">{d["buys"]}/{d["sells"]}</td><td class="n {_cls(d["realised_net_krw"])}">{_won(d["realised_net_krw"])}</td>'
        f'<td class="n {_cls(d["median_sell_pct"])}">{_pct(d["median_sell_pct"])}</td></tr>'
        for d in rep["departed"]) or '<tr><td colspan="6" class="dim">이 이력 안에서 완전히 정리한 종목 없음</td></tr>'
    size = (f'<p class="cap">매수 {sz["buys"]}건 · 중앙값 {_won(sz["median_buy_krw"])} · 평균 {_won(sz["mean_buy_krw"])} · '
            f'최대 {_won(sz["largest_buy_krw"])} (전체 매수액의 {sz["largest_share_pct"]}%) · 편차/평균 {sz["cv"]}</p>' if sz.get("buys") else "")
    market = "".join(f'<tr><td>{m["market"]}</td><td class="n">{m["symbols"]}</td><td class="n">{m["closed"]}</td>'
                     f'<td class="n">{_pct(m["win_rate_pct"], False)}</td><td class="n">{_days(m["median_hold_days"])}</td>'
                     f'<td class="n {_cls(m["realised_krw"])}">{_won(m["realised_krw"])}</td>'
                     f'<td class="n {_cls(m["unrealised_krw"])}">{_won(m["unrealised_krw"])}</td>'
                     f'<td class="n {_cls(m["total_krw"])}">{_won(m["total_krw"])}</td></tr>' for m in bm)
    ledger = (f'<h3>보유 종목</h3><div class="tbl"><table class="plain"><thead><tr><th>종목</th><th>보유 시작</th><th>보유일</th>'
              f'<th>매수/매도</th><th>마지막 체결</th><th>수량</th><th>평단</th><th>손익률</th></tr></thead><tbody>{hold_rows}</tbody></table></div>'
              f'<h3>떠난 종목</h3><div class="tbl"><table class="plain"><thead><tr><th>종목</th><th>처음</th><th>마지막</th>'
              f'<th>매수/매도</th><th>실현손익</th><th>매도 수익률 중앙값</th></tr></thead><tbody>{dep_rows}</tbody></table></div>'
              f'<h3>한 번에 얼마나 사나</h3>{size}')
    if market:
        ledger += (f'<h3>국내 vs 해외</h3><div class="tbl"><table class="plain"><thead><tr><th></th><th>종목</th><th>닫힌 거래</th>'
                   f'<th>승률</th><th>보유 중앙값</th><th>실현</th><th>미실현</th><th>합계</th></tr></thead><tbody>{market}</tbody></table></div>')
    plates.add("원장", f"보유 {n_hold} · 정리 {n_dep}", ledger)

    limits = "".join(f"<li>{_e(x)}</li>" for x in rep["limits"])
    return f"""<title>PivoxReport {acct}</title>
{_FONTS}
<style>{_css(p)}</style>
<div class="wrap">
<header class="mast">
  <h1>기록이 되비추는 것</h1>
  <div class="who">토스증권 계좌 {_e(acct)}<br>{_e(gen)} KST<br>Toss Open API · read-only</div>
</header>

{lead}
{finds}

{plates.html()}

<div class="foot">
  <span class="basis">토스증권 Open API 를 읽기 전용으로 조회해 만든 기록이다. 주문 경로는 없다.
  되비추는 거울이며, 다음에 무엇을 할지는 여기 없다.</span>
  <ul>{limits}</ul>
</div>
</div>
"""
