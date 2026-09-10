"""PivoxReport — self-contained HTML rendering of the v2 mirror report.

Same dict :func:`services.toss.mirror_report.build_mirror_report` returns,
drawn instead of tabulated: weights and returns as one row per holding,
the account's path as a timeline of every fill, the two mirror columns
side by side. Design tokens are the product's v3 set (Vantablack ground,
bronze accent, carmine-rise / indigo-fall, and the same four type roles:
Playfair to display, Source Serif to caption, Geist with Pretendard to read,
JetBrains Mono to count) so the page reads as the same product as /mirror.

No JavaScript beyond nothing — every chart is inline SVG computed here,
hover detail rides on ``<title>``. No external asset but the fonts.
Numbers are the report's numbers; this module formats and places them and
never derives a new one.
"""
from __future__ import annotations

import html
import re
from datetime import date
from typing import NamedTuple

# ── v3 tokens (frontend/src/app/globals.css) ─────────────────────────────────
INK = "#050505"
ONYX = "#111111"
IVORY = "#F5F0E8"
BRONZE = "#B8956A"
BRONZE_LIGHT = "#A3845C"
# --up / --down (globals.css :root) and lib/format.ts PRICE_COLOR_HEX carry the
# same two values. Per the 2026-04-26 directive the Korean convention applies to
# KR and US symbols alike, in muted carmine and indigo rather than RGB primaries,
# so the pair sits inside the bronze palette instead of fighting it. (The
# identical --pq-terminal-up / --pq-terminal-down are defined but unused.)
UP = "#D18888"     # KR carmine — rise
DOWN = "#7AA0C8"   # KR indigo — fall

# The report surface tokens, also from globals.css (--report-paper / --report-ink
# / --report-rule / --report-tldr-bg). The product already decided that anything
# printable or exportable stays ivory paper no matter what the app's theme is —
# "we do NOT invert: printed reports don't invert". A PDF of a Vantablack page is
# unreadable on paper, and a dark-ground email is what Gmail's dark-mode transform
# turns into ivory-on-ivory. So the same report renders on two grounds.
PAPER = "#FAF8F3"
PAPER_INK = "#1A1A1A"
PAPER_RULE = "#D9D4C7"
PAPER_TLDR = "#F1EEE5"
# The three accents restepped for the light ground. The screen values are ~2.6:1
# on paper — invisible. These sit at 4.7-5.4:1 while keeping the same three hues,
# so the chart still reads as bronze / carmine / indigo.
PAPER_BRONZE = "#8A6A3E"
PAPER_BRONZE_LIGHT = "#A3845C"
PAPER_UP = "#A34A4A"
PAPER_DOWN = "#3F6A94"


class Palette(NamedTuple):
    """Every colour the page draws with, so the ground is a parameter.

    The SVG charts write their fills as literal hex — a CSS custom property in
    a presentation attribute is not something every renderer resolves, and the
    PDF path is exactly the renderer that would silently drop it. Threading the
    palette instead means the charts and the stylesheet can never disagree
    about which ground they are on.
    """

    ground: str        # page background
    raised: str        # tile / panel background
    text: str
    soft: str
    dim: str
    faint: str
    line: str
    line_soft: str
    veil: str
    bronze: str
    bronze_light: str
    up: str
    down: str
    ghost: str         # a departed symbol's track and label
    sale: str          # the sale tick, which must read against the ground
    scheme: str


SCREEN = Palette(
    ground=INK, raised=INK, text=IVORY,
    soft="rgba(245,240,232,.78)", dim="rgba(245,240,232,.55)", faint="rgba(245,240,232,.45)",
    line="rgba(245,240,232,.08)", line_soft="rgba(245,240,232,.05)", veil="rgba(245,240,232,.04)",
    bronze=BRONZE, bronze_light=BRONZE_LIGHT, up=UP, down=DOWN,
    ghost="rgba(245,240,232,.25)", sale=IVORY, scheme="dark",
)

PAPER_PALETTE = Palette(
    ground=PAPER, raised=PAPER_TLDR, text=PAPER_INK,
    soft="rgba(26,26,26,.80)", dim="#5A5A5A", faint="#6E6E6E",
    line=PAPER_RULE, line_soft="rgba(217,212,199,.55)", veil=PAPER_TLDR,
    bronze=PAPER_BRONZE, bronze_light=PAPER_BRONZE_LIGHT, up=PAPER_UP, down=PAPER_DOWN,
    ghost="#9A9488", sale=PAPER_INK, scheme="light",
)


def _css(p: Palette) -> str:
    return f"""
:root {{ --ink:{p.ground}; --onyx:{p.raised}; --ivory:{p.text}; --ivory-soft:{p.soft}; --ivory-dim:{p.dim};
  --ivory-faint:{p.faint}; --line:{p.line}; --line-soft:{p.line_soft}; --veil:{p.veil};
  --bronze:{p.bronze}; --bronze-light:{p.bronze_light}; --up:{p.up}; --down:{p.down};
  /* The app's four roles, in its order. Geist carries latin and has no hangul,
     so Korean falls to Pretendard exactly as it does in the product. Pretendard
     is served from jsdelivr, which a published artifact's CSP does not admit for
     stylesheets — there the link fails silently and Noto Sans KR, on the allowed
     host, takes the Korean. The local file gets the real face. */
  --display:"Playfair Display", Georgia, "Times New Roman", serif;
  --serif:"Source Serif 4", Georgia, "Times New Roman", serif;
  --sans:Geist, "Pretendard Variable", Pretendard, "Noto Sans KR", -apple-system, system-ui, sans-serif;
  --mono:"JetBrains Mono", ui-monospace, Menlo, Consolas, monospace; }}
html {{ color-scheme: {p.scheme}; }}
/* keep-all is the whole difference between Korean that is typeset and Korean
   that is merely wrapped: without it the browser breaks inside a word, so
   "손실은" becomes "손실" / "은" across two lines. Latin is unaffected — it has
   no character-level break to suppress — and the long unbroken things that do
   need to break (symbols, URLs) get anywhere back where they appear. */
body {{ margin:0; background:var(--ink); color:var(--ivory); font-family:var(--sans); font-size:14px; line-height:1.62; padding-block:44px 72px; padding-inline:20px; word-break:keep-all; -webkit-font-smoothing:antialiased; }}
td.v, td.x, .mirror td, table.plain td {{ overflow-wrap:anywhere; }}
.wrap {{ max-width:760px; margin:0 auto; }}

/* Masthead. A statement is headed, not launched: the document names itself on
   the left and stamps its own provenance on the right, both sitting on one
   baseline over a single heavy rule. No eyebrow, no hero. */
.mast {{ display:flex; align-items:baseline; justify-content:space-between; gap:20px 28px; flex-wrap:wrap; border-bottom:1.5px solid var(--ivory); padding-bottom:11px; }}
.mast h1 {{ font-family:var(--display); font-weight:400; font-size:27px; line-height:1.18; margin:0; }}
.mast .who {{ font-family:var(--mono); font-size:11px; color:var(--ivory-dim); text-align:right; line-height:1.75; }}

/* The lead. One sentence at reading-aloud size, then the rest of the findings
   with their ordinal in the margin — the number is a position on the page, not
   a badge stuck to a box. */
.lead {{ display:grid; grid-template-columns:22px 1fr; gap:10px; margin:28px 0 0; align-items:baseline; }}
.lead p {{ font-family:var(--serif); font-size:19.5px; line-height:1.45; margin:0; max-width:50ch; text-wrap:balance; }}
.lead .n {{ font-family:var(--mono); font-size:11px; color:var(--bronze); }}
.finds {{ margin:20px 0 0; padding:0; list-style:none; display:grid; gap:12px; }}
.finds li {{ display:grid; grid-template-columns:22px 1fr; gap:10px; align-items:baseline; font-size:13.5px; line-height:1.58; color:var(--ivory-soft); max-width:64ch; }}
.finds .n {{ font-family:var(--mono); font-size:11px; color:var(--bronze); }}

/* The statement block. Label left, figure right in tabular mono, one hairline
   per row, a heavier rule where a real 잔고 statement rules off a subtotal.
   This is the shape a brokerage prints; a grid of big-number tiles is the shape
   a dashboard prints, and the reader already has the dashboard. */
.stmt {{ width:100%; border-collapse:collapse; font-variant-numeric:tabular-nums; margin-top:26px; }}
.stmt td {{ padding:8px 0; border-bottom:1px solid var(--line-soft); vertical-align:baseline; }}
.stmt td.k {{ font-size:13px; color:var(--ivory-soft); }}
.stmt td.v {{ text-align:right; font-family:var(--mono); font-size:13.5px; white-space:nowrap; padding-left:16px; }}
.stmt td.x {{ text-align:right; font-family:var(--mono); font-size:11.5px; color:var(--ivory-dim); white-space:nowrap; padding-left:14px; width:104px; }}
.stmt tr.sub td.k {{ padding-left:15px; font-size:12.5px; color:var(--ivory-dim); }}
.stmt tr.sub td.v {{ font-size:12.5px; color:var(--ivory-dim); }}
.stmt tr.rule td {{ border-top:1.5px solid var(--line); }}
.stmt tr.big td.v {{ font-family:var(--display); font-size:20px; }}
.stmt tr:last-child td {{ border-bottom:0; }}

/* Section head: a rule, the title, and on the same baseline at the right the
   one figure that says how much follows. The count is information; an uppercase
   letterspaced label repeated nine times is furniture. */
.sec {{ padding-block:32px 0; }}
.sh {{ display:flex; align-items:baseline; justify-content:space-between; gap:16px; border-top:1px solid var(--line); padding-top:13px; margin-bottom:15px; }}
.sh h2 {{ font-family:var(--display); font-weight:400; font-size:19px; margin:0; }}
.sh .cnt {{ font-family:var(--mono); font-size:11px; color:var(--ivory-dim); white-space:nowrap; text-align:right; }}
.note {{ font-family:var(--serif); color:var(--ivory-soft); font-size:13px; margin:0 0 15px; max-width:60ch; }}
.note.tight {{ margin:10px 0 0; }}
.up {{ color:var(--up); }} .down {{ color:var(--down); }} .dim {{ color:var(--ivory-dim); }}

/* The reconciliation verdict and its findings use the same margin device as the
   lead: the symbol sits in the margin in mono, the reason runs in the column. */
.recon {{ font-size:13.5px; line-height:1.6; margin:0; }}
.recon strong {{ font-weight:600; }}
.recon.warn {{ color:var(--ivory); }}
.rlist {{ margin:14px 0 0; padding:0; list-style:none; display:grid; gap:11px; }}
.rlist li {{ display:grid; grid-template-columns:132px 1fr; gap:12px; align-items:baseline; font-size:12.5px; line-height:1.55; color:var(--ivory-soft); }}
.rlist .s {{ font-family:var(--mono); font-size:11.5px; color:var(--ivory); }}
.rlist .s em {{ display:block; font-style:normal; color:var(--ivory-dim); font-size:10.5px; padding-top:2px; }}

svg {{ display:block; width:100%; min-width:640px; height:auto; }}
.tbl {{ overflow-x:auto; -webkit-overflow-scrolling:touch; }}
svg text {{ font-family:var(--mono); font-size:11px; fill:var(--ivory-soft); }}
svg .lbl {{ font-family:var(--sans); font-size:12px; fill:var(--ivory); }}
svg .axis {{ stroke:var(--line); stroke-width:1; }}
svg .grid {{ stroke:var(--line-soft); stroke-width:1; }}
svg .muted {{ fill:var(--ivory-dim); }}
.mirror {{ width:100%; border-collapse:collapse; font-variant-numeric:tabular-nums; }}
.mirror th, .mirror td {{ padding:9px 8px; border-bottom:1px solid var(--line-soft); vertical-align:top; text-align:right; }}
.mirror th {{ font-family:var(--mono); font-size:10.5px; letter-spacing:.1em; text-transform:uppercase; color:var(--ivory-dim); font-weight:400; }}
.mirror td:first-child, .mirror th:first-child {{ text-align:left; color:var(--ivory-soft); }}
.mirror td {{ font-family:var(--mono); font-size:12.5px; }}
.mirror .diff td {{ color:var(--ivory); }}
table.plain {{ width:100%; border-collapse:collapse; font-variant-numeric:tabular-nums; font-size:12.5px; }}
table.plain th {{ font-family:var(--mono); font-size:10.5px; letter-spacing:.1em; text-transform:uppercase; color:var(--ivory-dim); font-weight:400; text-align:left; padding:6px 8px; border-bottom:1px solid var(--line); }}
table.plain td {{ padding:8px; border-bottom:1px solid var(--line-soft); }}
table.plain td.n {{ text-align:right; font-family:var(--mono); }}
.legend {{ display:flex; gap:16px; flex-wrap:wrap; font-family:var(--mono); font-size:10.5px; color:var(--ivory-dim); margin-top:9px; }}
.legend i {{ display:inline-block; width:9px; height:9px; margin-right:6px; vertical-align:-1px; }}

/* A sub-head inside a section, in the reading face rather than a second
   uppercase mono label competing with the section head above it. */
h3 {{ font-family:var(--sans); font-size:12.5px; letter-spacing:.02em; color:var(--ivory); font-weight:500; margin:28px 0 9px; padding-bottom:6px; border-bottom:1px solid var(--line-soft); }}

/* Statement footer: what the figures are computed from, ruled off at the bottom
   where a document puts its basis note. Not a centred italic epigraph. */
.foot {{ margin-top:46px; border-top:1.5px solid var(--line); padding-top:15px; font-size:11.5px; line-height:1.75; color:var(--ivory-dim); max-width:66ch; }}
.foot ul {{ margin:7px 0 0; padding-left:15px; }}
.foot li {{ margin-bottom:3px; }}
.foot .basis {{ color:var(--ivory-soft); }}
""" + (_PRINT_CSS if p.scheme == "light" else "")


# Paper is a fixed width, so the horizontal-scroll escape hatch the screen page
# uses for its 640px-wide charts has nowhere to scroll to. On paper the charts
# shrink to the text column instead, and a section is asked not to straddle a
# page break.
_PRINT_CSS = """
@page { size: A4; margin: 16mm 14mm 18mm; }
body { padding-block: 0; padding-inline: 0; font-size: 12.5px; }
.wrap { max-width: none; }
svg { min-width: 0; }
.tbl { overflow-x: visible; }
/* Keep a section's heading with the first of its content and never orphan a
   chart or a tile row across the fold — but do NOT ask a whole section to stay
   whole: the long ones are taller than a page, so the request is unsatisfiable
   and each becomes its own page with a hand's width of white above it. */
.sec { padding-block: 22px 0; }
.sh, h2, h3 { break-after: avoid; }
.sh, .stmt tr, svg, tr, .finds li, .rlist li { break-inside: avoid; }
.mast h1 { font-size: 24px; }
.lead { font-size: 17px; }
.foot { margin-top: 30px; }
"""


# Pretendard ships as a dynamic subset: ~250 ``@font-face`` rules that each
# carry a slice of hangul behind a ``unicode-range``. A browser honours the
# ranges; a PDF renderer that does not honour them reaches into whichever slice
# it loaded first and paints the glyph sitting at that index — the text comes
# out as other hangul and latin, which is worse than a fallback because it still
# looks like writing. Screen only, therefore, and paper takes Noto Sans KR from
# the same Google stylesheet the other three roles already come from.
_PRETENDARD = ('<link rel="preconnect" href="https://cdn.jsdelivr.net">\n'
               '<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/'
               'pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css">')


def _e(s) -> str:
    return html.escape(str(s if s is not None else ""))


def _em(s) -> str:
    """Escape, then promote the ``**bold**`` the shared reason strings carry for
    the markdown renderer. Escaping first means the promotion can never introduce
    a tag the source did not ask for."""
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", _e(s))


def _won(v) -> str:
    return "—" if v is None else f"₩{int(round(v)):,}"


def _pct(v, signed=True) -> str:
    if v is None:
        return "—"
    return f"{v:+.2f}%" if signed else f"{v:.2f}%"


def _cls(v) -> str:
    if v is None or v == 0:
        return "dim"
    return "up" if v > 0 else "down"


def _nm(sym, name) -> str:
    return f"{name} ({sym})" if name and name != sym else sym


def _fit(label: str, budget_px: float, size_px: float = 12.0) -> str:
    """Trim a label to the pixels it actually gets.

    A fixed character count cannot do this: hangul is a full em wide and latin
    is a bit over half of one, so the same 22 characters are 264px of "아이티센
    글로벌 (124520)" or 145px of "SMR". The wide ones ran into the bar beside
    them. Widths are the standard CJK/latin advances, close enough for a
    trim — and erring narrow only costs a character.
    """
    def w(ch: str) -> float:
        return size_px if ord(ch) > 0x1100 else size_px * 0.62

    if sum(w(c) for c in label) <= budget_px:
        return label
    budget_px -= size_px * 0.62  # room for the ellipsis
    out, used = [], 0.0
    for ch in label:
        if used + w(ch) > budget_px:
            break
        out.append(ch)
        used += w(ch)
    return "".join(out).rstrip() + "…"


def _d(s: str | None) -> date | None:
    return date.fromisoformat(s) if s else None


# ── charts ───────────────────────────────────────────────────────────────────
def _holdings_rows_svg(holdings: list[dict], p: Palette, chunk: int | None = None) -> str:
    """One row per holding: name · weight bar (bronze, magnitude) · return bar
    (diverging from a zero line, KR red/blue). Same order top to bottom so
    the two charts read as one table."""
    if not holdings:
        return '<p class="dim">보유 종목 없음</p>'
    if chunk and len(holdings) > chunk:
        # See _timeline_svg: a chart taller than the page loses its tail.
        return "".join(_holdings_rows_svg(holdings[i:i + chunk], p)
                       for i in range(0, len(holdings), chunk))
    W, name_w, gap, bar_h, row_h = 720, 196, 16, 18, 30
    pad_top = 22
    wcol_x, wcol_w = name_w, 220
    rcol_x = wcol_x + wcol_w + gap + 44
    rcol_w = W - rcol_x - 48
    max_w = max(h["weight_pct"] or 0 for h in holdings) or 1
    max_r = max(abs(h["unrealised_rate_pct"] or 0) for h in holdings) or 1
    zero_x = rcol_x + rcol_w / 2
    H = pad_top + row_h * len(holdings) + 8
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="보유 종목의 비중과 손익률">']
    out.append(f'<text x="{wcol_x}" y="12" class="muted">비중 (평가액 기준)</text>')
    out.append(f'<text x="{zero_x}" y="12" class="muted" text-anchor="middle">손익률 (평단 대비)</text>')
    out.append(f'<line x1="{zero_x}" y1="{pad_top - 4}" x2="{zero_x}" y2="{H - 6}" class="axis"/>')
    for i, h in enumerate(holdings):
        y = pad_top + i * row_h
        cy = y + bar_h / 2
        label = _nm(h["symbol"], h["name"])
        out.append(f'<text x="0" y="{cy + 4}" class="lbl">{_e(_fit(label, name_w - 14))}</text>')
        w = (h["weight_pct"] or 0) / max_w * (wcol_w - 46)
        out.append(f'<rect x="{wcol_x}" y="{y}" width="{w:.1f}" height="{bar_h}" fill="{p.bronze}" rx="0"><title>{_e(label)} · 비중 {_pct(h["weight_pct"], False)} · 평가액 {_won(h["market_value_krw"])}</title></rect>')
        out.append(f'<text x="{wcol_x + w + 6:.1f}" y="{cy + 4}">{_pct(h["weight_pct"], False)}</text>')
        r = h["unrealised_rate_pct"] or 0
        rw = abs(r) / max_r * (rcol_w / 2 - 44)
        color = p.up if r > 0 else p.down
        x = zero_x if r >= 0 else zero_x - rw
        out.append(f'<rect x="{x:.1f}" y="{y}" width="{max(rw, 1):.1f}" height="{bar_h}" fill="{color}"><title>{_e(label)} · 손익률 {_pct(r)} · 평단 {h["avg_purchase_price"]:,} → 현재가 기준</title></rect>')
        tx = zero_x + rw + 6 if r >= 0 else zero_x - rw - 6
        anchor = "start" if r >= 0 else "end"
        out.append(f'<text x="{tx:.1f}" y="{cy + 4}" text-anchor="{anchor}">{_pct(r)}</text>')
    out.append("</svg>")
    return "".join(out)


def _timeline_svg(rep: dict, p: Palette, chunk: int | None = None) -> str:
    """The account's path: one track per symbol from its first fill to today
    (open) or its last fill (departed); each fill a tick — purchases in
    bronze above the track, sales in ivory below."""
    holdings, departed = rep["holdings"], rep["departed"]
    tracks = []
    today = _d(rep["generated_at"][:10])
    for h in holdings:
        if h.get("opened_at"):
            tracks.append((_nm(h["symbol"], h["name"]), _d(h["opened_at"]), today, True, h["symbol"]))
    for d in departed:
        tracks.append((_nm(d["symbol"], d["name"]), _d(d["first_fill_at"]), _d(d["last_fill_at"]), False, d["symbol"]))
    fills = rep.get("fills_for_chart") or []
    if not tracks:
        return '<p class="dim">이력 안에 체결이 없어 그릴 경로가 없다.</p>'
    x0d = min(t[1] for t in tracks)
    span = max((today - x0d).days, 1)
    W, name_w, right = 720, 196, 24
    row_h, pad_top = 26, 26
    px = lambda d: name_w + (d - x0d).days / span * (W - name_w - right)  # noqa: E731
    by_sym: dict[str, list[dict]] = {}
    for f in fills:
        by_sym.setdefault(f["symbol"], []).append(f)
    if chunk and len(tracks) > chunk:
        # An SVG is a replaced element: a renderer paginating it cannot split it,
        # so one taller than the page is not shrunk — it is cut off, and the
        # tracks below the fold are simply gone. Emitting page-sized pieces that
        # share one time axis is the same chart, drawn where it fits.
        return "".join(
            _one_timeline(tracks[i:i + chunk], by_sym, x0d, today, span, p,
                          W, name_w, right, row_h, pad_top, px)
            for i in range(0, len(tracks), chunk))
    return _one_timeline(tracks, by_sym, x0d, today, span, p,
                         W, name_w, right, row_h, pad_top, px)


def _one_timeline(tracks, by_sym, x0d, today, span, p: Palette,
                  W, name_w, right, row_h, pad_top, px) -> str:
    H = pad_top + row_h * len(tracks) + 20
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="종목별 보유 경로와 체결">']
    # month grid
    m = date(x0d.year, x0d.month, 1)
    while m <= today:
        x = px(m)
        if x >= name_w:
            out.append(f'<line x1="{x:.1f}" y1="{pad_top - 8}" x2="{x:.1f}" y2="{H - 16}" class="grid"/>')
            if m.month in (1, 4, 7, 10) or span < 200:
                out.append(f'<text x="{x + 3:.1f}" y="{pad_top - 12}" class="muted">{m.strftime("%y.%m") if m.month != 1 else m.strftime("%Y")}</text>')
        m = date(m.year + (m.month // 12), m.month % 12 + 1, 1)
    out.append(f'<line x1="{px(today):.1f}" y1="{pad_top - 8}" x2="{px(today):.1f}" y2="{H - 16}" stroke="{p.bronze}" stroke-width="1" stroke-dasharray="2 3"/>')
    out.append(f'<text x="{px(today) - 3:.1f}" y="{H - 4}" class="muted" text-anchor="end">오늘</text>')
    for i, (label, a, b, is_open, sym) in enumerate(tracks):
        y = pad_top + i * row_h + 10
        out.append(f'<text x="0" y="{y + 4}" class="lbl" fill="{p.text if is_open else p.ghost}">{_e(_fit(label, name_w - 14))}</text>')
        xa, xb = px(a), px(b)
        out.append(f'<line x1="{xa:.1f}" y1="{y}" x2="{max(xb, xa + 2):.1f}" y2="{y}" stroke="{p.bronze if is_open else p.ghost}" stroke-width="{3 if is_open else 2}"><title>{_e(label)} · {a} → {"오늘" if is_open else b} · {(b - a).days}일</title></line>')
        for f in by_sym.get(sym, []):
            x = px(_d(f["date"]))
            if f["side"] == "in":
                out.append(f'<path d="M{x:.1f},{y - 3} l-4,-7 h8 z" fill="{p.bronze}"><title>{f["date"]} 매수 {f["qty"]:g}주 @ {f["price"]:,}</title></path>')
            else:
                out.append(f'<path d="M{x:.1f},{y + 3} l-4,7 h8 z" fill="{p.sale}"><title>{f["date"]} 매도 {f["qty"]:g}주 @ {f["price"]:,} · {_pct(f.get("pnl_pct"))}</title></path>')
    out.append("</svg>")
    return "".join(out)


def _split_bar_svg(kr: float | None, us: float | None, p: Palette) -> str:
    if kr is None:
        return ""
    W, H = 720, 34
    kw = kr / 100 * W
    return (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="국내 해외 비중">'
            f'<rect x="0" y="6" width="{max(kw - 1, 0):.1f}" height="14" fill="{p.bronze}"><title>국내 {kr:.2f}%</title></rect>'
            f'<rect x="{kw + 1:.1f}" y="6" width="{max(W - kw - 1, 0):.1f}" height="14" fill="{p.bronze_light}" opacity=".55"><title>해외 {us:.2f}%</title></rect>'
            f'<text x="0" y="32">국내 {kr:.2f}%</text><text x="{W}" y="32" text-anchor="end">해외 {us:.2f}%</text></svg>')


def _attribution_svg(rows: list[dict], p: Palette) -> str:
    """One diverging bar per symbol: realised + unrealised, KRW. Largest
    contributors and detractors; the middle is folded when there are many."""
    if not rows:
        return ""
    shown = rows if len(rows) <= 14 else rows[:7] + rows[-7:]
    folded = len(rows) - len(shown)
    W, name_w, right, bar_h, row_h, pad_top = 720, 196, 96, 16, 26, 20
    plot_w = W - name_w - right
    mx = max(abs(r["total_krw"]) for r in shown) or 1
    zero = name_w + plot_w * (max(0, -min(r["total_krw"] for r in shown)) / (mx + max(0, -min(r["total_krw"] for r in shown)))) if any(r["total_krw"] < 0 for r in shown) else name_w
    scale = (W - right - zero) / mx if any(r["total_krw"] > 0 for r in shown) else (zero - name_w) / mx
    H = pad_top + row_h * len(shown) + (row_h if folded else 0) + 8
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="종목별 손익 기여">',
           f'<line x1="{zero:.1f}" y1="{pad_top - 6}" x2="{zero:.1f}" y2="{H - 4}" class="axis"/>']
    for i, r in enumerate(shown):
        y = pad_top + i * row_h + (row_h if folded and i >= 7 else 0)
        v = r["total_krw"]
        w = abs(v) * scale
        x = zero if v >= 0 else zero - w
        color = p.up if v > 0 else p.down
        label = _nm(r["symbol"], r["name"])
        out.append(f'<text x="0" y="{y + bar_h / 2 + 4}" class="lbl" fill="{p.text if r["held"] else p.ghost}">{_e(_fit(label, name_w - 14))}</text>')
        out.append(f'<rect x="{x:.1f}" y="{y}" width="{max(w, 1):.1f}" height="{bar_h}" fill="{color}"><title>{_e(label)} · 실현 {_won(r["realised_krw"])} · 미실현 {_won(r["unrealised_krw"])} · 합계 {_won(v)}</title></rect>')
        # Loss labels sit just right of the zero line, where no bar competes for
        # the space, so a long loss bar never runs its figure into the name column.
        tx = zero + w + 6 if v >= 0 else zero + 6
        out.append(f'<text x="{tx:.1f}" y="{y + bar_h / 2 + 4}" text-anchor="start">{_won(v)}</text>')
        if folded and i == 6:
            out.append(f'<text x="{zero:.1f}" y="{y + row_h + bar_h / 2 + 4}" class="muted" text-anchor="middle">… 중간 {folded}종목 생략 …</text>')
    out.append("</svg>")
    return "".join(out)


def _timing_svg(tm: dict, p: Palette) -> str:
    if not tm.get("fills"):
        return ""
    W, H = 720, 92
    wd, hr = tm["by_weekday"], tm["by_hour"]
    mw = max(x["fills"] for x in wd) or 1
    mh = max(x["fills"] for x in hr) or 1
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="요일별 시간대별 체결">']
    out.append('<text x="0" y="12" class="muted">요일</text>')
    bw = 200 / 7
    for i, x in enumerate(wd):
        h = x["fills"] / mw * 44
        out.append(f'<rect x="{i * bw:.1f}" y="{62 - h:.1f}" width="{bw - 2:.1f}" height="{h:.1f}" fill="{p.bronze}"><title>{x["day"]} {x["fills"]}건</title></rect>')
        out.append(f'<text x="{i * bw + bw / 2 - 1:.1f}" y="{H - 14}" text-anchor="middle">{x["day"]}</text>')
    out.append('<text x="240" y="12" class="muted">시간대 (KST)</text>')
    hw = (W - 240) / 24
    for i, x in enumerate(hr):
        h = x["fills"] / mh * 44
        out.append(f'<rect x="{240 + i * hw:.1f}" y="{62 - h:.1f}" width="{hw - 1.5:.1f}" height="{h:.1f}" fill="{p.bronze}" opacity="{0.45 if 9 <= i < 16 else 1}"><title>{i:02d}시 {x["fills"]}건</title></rect>')
        if i % 3 == 0:
            out.append(f'<text x="{240 + i * hw:.1f}" y="{H - 14}">{i:02d}</text>')
    out.append("</svg>")
    return "".join(out)


def _stmt(rows) -> str:
    """A statement block: label, figure, and a note in a third column.

    ``rows`` are ``(label, figure, note, colour_class, flags)`` where ``flags``
    is any of ``sub`` (a leg indented under the row above, the way a 잔고
    statement breaks out a total), ``rule`` (the heavier rule a statement draws
    where it rules off) and ``big`` (the figure a reader is looking for).
    """
    out = ['<table class="stmt">']
    for label, figure, note, cls, flags in rows:
        attr = f' class="{flags}"' if flags else ""
        out.append(f'<tr{attr}><td class="k">{_e(label)}</td>'
                   f'<td class="v {cls}">{_e(figure)}</td>'
                   f'<td class="x">{_e(note)}</td></tr>')
    out.append("</table>")
    return "".join(out)


def _hold_span_svg(t: dict, p: Palette) -> str:
    """How long each side was held, drawn as two spans from the day of purchase.

    The account's loudest fact is that losses are carried several times longer
    than gains, and until now the report only said it in a sentence. Two bars on
    one day-axis is the whole argument: same origin, same scale, one obviously
    longer than the other.
    """
    w, l = t.get("win_hold_median_days"), t.get("loss_hold_median_days")
    if not t.get("closed") or w is None or l is None:
        return ""
    W, name_w, right, bar_h, row_h, pad_top = 720, 150, 150, 22, 44, 24
    plot = W - name_w - right
    mx = max(w, l, 1)
    H = pad_top + row_h * 2 + 6
    out = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="이익과 손실을 쥐고 있던 기간">',
           f'<text x="{name_w}" y="12" class="muted">매수일부터 매도일까지, 중앙값</text>',
           f'<line x1="{name_w}" y1="{pad_top - 6}" x2="{name_w}" y2="{H - 6}" class="axis"/>']
    for i, (label, days, pct, n, colour) in enumerate([
        ("이익을 실현할 때", w, t.get("median_win_pct"), t.get("wins"), p.up),
        ("손실을 실현할 때", l, t.get("median_loss_pct"), t.get("losses"), p.down),
    ]):
        y = pad_top + i * row_h
        cy = y + bar_h / 2 + 4
        out.append(f'<text x="0" y="{cy}" class="lbl">{_e(label)}</text>')
        out.append(f'<text x="{name_w - 10}" y="{cy}" text-anchor="end" class="muted">{n or 0}건</text>')
        bw = max(days / mx * plot, 2)
        out.append(f'<rect x="{name_w + 1}" y="{y}" width="{bw:.1f}" height="{bar_h}" fill="{colour}">'
                   f'<title>{_e(label)} · {n or 0}건 · 보유 중앙값 {days:g}일 · 수익률 중앙값 {_pct(pct)}</title></rect>')
        out.append(f'<text x="{name_w + bw + 8:.1f}" y="{cy}">{days:g}일 · {_pct(pct)}</text>')
    out.append("</svg>")
    return "".join(out)


def _analysis_section(an: dict, p: Palette) -> str:
    if not an:
        return ""
    a, t, af, tm, sz, bm = an["attribution"], an["trades"], an["after_selling"], an["timing"], an["sizing"], an["by_market"]
    closed = ""
    if t.get("closed"):
        closed = _stmt([
            ("닫힌 거래", f"{t['closed']}건", f"이익 {t['wins']} · 손실 {t['losses']}", "", ""),
            ("승률", f"{t['win_rate_pct']}%", "", "", ""),
            ("이익/손실 크기 비", str(t["payoff_ratio"] or "—"), "", "", ""),
            ("거래당 기대값", _won(t["expectancy_krw"]), f"중앙값 {_won(t['median_trade_krw'])}",
             _cls(t["expectancy_krw"]), "rule big"),
        ]) + _hold_span_svg(t, p) + (
            f'<p class="note tight">최고 {_e(t["best"]["symbol"])} {t["best"]["date"]} {_won(t["best"]["realised_krw"])} ({_pct(t["best"]["pnl_pct"])}) · '
            f'최저 {_e(t["worst"]["symbol"])} {t["worst"]["date"]} {_won(t["worst"]["realised_krw"])} ({_pct(t["worst"]["pnl_pct"])})'
            + (f' · 실현 이익의 {t["top5_share_pct"]}%가 상위 5건' if t.get("top5_share_pct") else "") + "</p>")
    else:
        closed = '<p class="note">분석할 닫힌 거래가 없다.</p>' 
    after = ""
    if af.get("available") and af.get("count"):
        rows = "".join(f'<tr><td>{_e(_nm(r["symbol"], r["name"]))}</td><td>{_e(r["last_sold_at"])}</td><td class="n">{r["avg_sell_price"]:,}</td><td class="n">{r["price_now"]:,}</td>'
                       f'<td class="n {_cls(r["since_sale_pct"])}">{_pct(r["since_sale_pct"])}</td><td class="n {_cls(r["kept_delta_krw"])}">{_won(r["kept_delta_krw"])}</td></tr>' for r in af["rows"])
        after = (f'<p class="note">정리한 {af["count"]}종목 중 지금 가격이 판 가격보다 높은 것 {af["higher_now"]}, 낮은 것 {af["lower_now"]}. 이후 변화 중앙값 {_pct(af["median_since_sale_pct"])}. '
                 f'판 수량을 그대로 들고 있었다면 지금 <span class="{_cls(af["kept_delta_krw"])}">{_won(af["kept_delta_krw"])}</span> 차이.</p>'
                 f'<div class="tbl"><table class="plain"><thead><tr><th>종목</th><th>마지막 매도</th><th>평균 매도가</th><th>지금</th><th>이후</th><th>안 팔았다면</th></tr></thead><tbody>{rows}</tbody></table></div>')
    else:
        after = '<p class="note dim">현재가를 받지 못해 건너뜀.</p>'
    timing = ""
    if tm.get("fills"):
        timing = (_timing_svg(tm, p) + f'<p class="note tight">거래일 {tm["trade_days"]}일 · 하루 평균 {tm["fills_per_trade_day"]}건 · 3건 이상인 날 {tm["days_with_3plus"]}일 · 최다 {tm["busiest_day"]["date"]} {tm["busiest_day"]["fills"]}건'
                  + (f' · 국내 체결 중 개장 첫 시간 {tm["kr_first_hour_pct"]}%' if tm.get("kr_first_hour_pct") is not None else "") + "</p>")
    size = (f'<p class="note">매수 {sz["buys"]}건 · 중앙값 {_won(sz["median_buy_krw"])} · 평균 {_won(sz["mean_buy_krw"])} · 최대 {_won(sz["largest_buy_krw"])} (전체 매수액의 {sz["largest_share_pct"]}%) · 편차/평균 {sz["cv"]}</p>'
            if sz.get("buys") else "")
    market = "".join(f'<tr><td>{m["market"]}</td><td class="n">{m["symbols"]}</td><td class="n">{m["closed"]}</td><td class="n">{_pct(m["win_rate_pct"], False)}</td><td class="n">{_days(m["median_hold_days"])}</td>'
                     f'<td class="n {_cls(m["realised_krw"])}">{_won(m["realised_krw"])}</td><td class="n {_cls(m["unrealised_krw"])}">{_won(m["unrealised_krw"])}</td><td class="n {_cls(m["total_krw"])}">{_won(m["total_krw"])}</td></tr>' for m in bm)
    return f"""
<section class="sec">
  <div class="sh"><h2>분석</h2><span class="cnt">닫힌 거래 {t.get("closed") or 0}건</span></div>
  <p class="note">위 문장들이 딛고 선 숫자를 항목별로 편다. 전부 이 리포트 안의 값으로 다시 계산할 수 있다.</p>

  <h3>손익 분해</h3>
  <p class="note">실현 <span class="{_cls(a['realised_krw'])}">{_won(a['realised_krw'])}</span> + 미실현 <span class="{_cls(a['unrealised_krw'])}">{_won(a['unrealised_krw'])}</span> = <strong>{_won(a['total_krw'])}</strong> · 수수료·세금 {_won(a['fees_krw'])}. 밝은 이름은 보유 중, 흐린 이름은 정리한 종목.</p>
  <div class="tbl">{_attribution_svg(a["rows"], p)}</div>

  <h3>닫힌 거래</h3>
  {closed}

  <h3>팔고 난 뒤</h3>
  {after}

  <h3>언제 사고파나</h3>
  <div class="tbl">{timing}</div>

  <h3>한 번에 얼마나 사나</h3>
  {size}

  <h3>국내 vs 해외</h3>
  <div class="tbl"><table class="plain"><thead><tr><th></th><th>종목</th><th>닫힌 거래</th><th>승률</th><th>보유 중앙값</th><th>실현</th><th>미실현</th><th>합계</th></tr></thead><tbody>{market}</tbody></table></div>
</section>
"""


# ── sections ─────────────────────────────────────────────────────────────────
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
    foot = (f'<p class="note tight">지금 들고 있는 매수분 {ages["lots"]}건의 나이: 중앙값 {_days(ages["median"])} · 가장 오래된 것 {_days(ages["oldest"])}</p>'
            if ages["lots"] else "")
    return (f'<div class="tbl"><table class="mirror"><thead><tr><th></th><th>최근 {window_days}일</th><th>전체 이력</th></tr></thead>'
            f'<tbody>{body}</tbody></table></div>{foot}')


def _days(v) -> str:
    return "—" if v is None else f"{v:g}일"


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
    stamp = (f'조회 시작 {_e(h["since"] or "전체")} · 첫 체결 {_e(h["first_fill_at"] or "—")} · 체결 {h["fills"]}건')
    if h["complete"]:
        return (f'<p class="recon">이력으로 되짚은 보유 {h["checked_symbols"]}종목의 수량·평균단가가 '
                f'<strong>토스 잔고와 전부 일치</strong>한다. 아래 실현손익은 전체 이력 기준이다.</p>'
                f'<p class="note tight">{stamp}</p>')
    trust = h.get("realised_trustworthy")
    items = "".join(
        f'<li><span class="s">{_e(m["symbol"])}<em>{_e(_mismatch_qty(m))}</em></span>'
        f'<span>{_em(m["reason"])}</span></li>'
        for m in h["mismatches"])
    verdict = ("주식 수가 바뀐 것뿐이고 들어오거나 나간 주식은 없다 — <strong>실현손익은 그대로 신뢰할 수 있다</strong>."
               if trust else "<strong>실현손익은 이만큼 비어 있다</strong>.")
    return (f'<p class="recon{"" if trust else " warn"}">이력으로 되짚은 결과가 토스 잔고와 '
            f'<strong>{len(h["mismatches"])}종목에서 다르다</strong>. {verdict}</p>'
            f'<ul class="rlist">{items}</ul>'
            f'<p class="note tight">{stamp}</p>')


def render_mirror_html(rep: dict, *, paper: bool = False) -> str:
    """The report as one self-contained page.

    ``paper=True`` renders the same document on the product's report surface —
    ivory ground, printed ink, accents restepped for it — which is what the PDF
    and any print of this page want. The screen default stays Vantablack so the
    page reads as the same product as ``/mirror``.
    """
    p = PAPER_PALETTE if paper else SCREEN
    # A4 less its margins is 182mm wide, so one viewBox unit is 0.253mm and a
    # 263mm-tall text column holds ~1040 of them. Leaving the section's heading
    # and lede their share, a chart gets ~880 — 32 timeline tracks at 26 units
    # each, or 28 holdings rows at 30. The screen has no fold and no cap.
    tracks_per_page = 32 if paper else None
    rows_per_page = 28 if paper else None
    v, c, h = rep["valuation"], rep["concentration"], rep["history"]
    acct = rep["account"]["account_no_masked"]
    gen = rep["generated_at"][:16].replace("T", " ")
    basis = "전체 이력" if h.get("realised_trustworthy", h["complete"]) else "부분 이력"
    stmt = _stmt([
        ("주식 평가액", _won(v["equity_value_krw"]), "", "", ""),
        ("국내", _won(v["krw_leg"]), "", "", "sub"),
        ("해외", f"${(v['usd_leg'] or 0):,.2f}", f"USD/KRW {rep['fx']['usdkrw']}", "", "sub"),
        ("매입 총액", _won(v["purchase_total_krw"]), "", "", ""),
        ("미실현 손익", _won(v["unrealised_krw"]), _pct(v["unrealised_rate_pct"]),
         _cls(v["unrealised_krw"]), "rule big"),
        ("실현 손익 누계", _won(h["realised_net_krw"]), basis, _cls(h["realised_net_krw"]), "big"),
        ("당일", _won(v["daily_krw"]), _pct(v["daily_rate_pct"]), _cls(v["daily_krw"]), "rule"),
    ])
    stmt += f'<p class="note tight">실현 손익 누계는 {basis} · 수수료·세금 차감 기준이다.</p>'

    # The lead is the report's own first finding, set to be read; the rest sit
    # under it with their ordinal in the margin. They used to be three identical
    # accent-railed boxes here AND again inside 분석 — the same sentences twice.
    heads = (rep.get("analysis") or {}).get("headline") or []
    lead = (f'<div class="lead"><span class="n">1</span><p>{_e(heads[0])}</p></div>'
            if heads else "")
    finds = ("".join(f'<li><span class="n">{i}</span><span>{_e(x)}</span></li>'
                     for i, x in enumerate(heads[1:], 2)))
    finds = f'<ul class="finds">{finds}</ul>' if finds else ""

    largest = c["largest"]
    conc = (f'<p class="note">가장 큰 종목은 {_e(_nm(largest["symbol"], largest["name"]))}, 평가액의 {largest["weight_pct"]:.2f}%. '
            f'30% 선을 넘는 종목: {_e(", ".join(c["over_30pct"]) if c["over_30pct"] else "없음")}.</p>' if largest else '<p class="note">보유 종목 없음.</p>')

    hold_rows = "".join(
        f'<tr><td>{_e(_nm(r["symbol"], r["name"]))}</td><td>{_e(r["opened_at"] or "이력 밖")}</td><td class="n">{_days(r["held_days"])}</td>'
        f'<td class="n">{r["buys"]}/{r["sells"]}</td><td>{_e(r["last_fill_at"] or "—")}</td><td class="n">{r["quantity"]:g}</td>'
        f'<td class="n">{r["avg_purchase_price"]:,}</td><td class="n {_cls(r["unrealised_rate_pct"])}">{_pct(r["unrealised_rate_pct"])}</td></tr>'
        for r in rep["holdings"])
    dep_rows = "".join(
        f'<tr><td>{_e(_nm(d["symbol"], d["name"]))}{" (이력 불완전)" if d["oversold"] else ""}</td><td>{_e(d["first_fill_at"])}</td><td>{_e(d["last_fill_at"])}</td>'
        f'<td class="n">{d["buys"]}/{d["sells"]}</td><td class="n {_cls(d["realised_net_krw"])}">{_won(d["realised_net_krw"])}</td><td class="n {_cls(d["median_sell_pct"])}">{_pct(d["median_sell_pct"])}</td></tr>'
        for d in rep["departed"]) or '<tr><td colspan="6" class="dim">이 이력 안에서 완전히 정리한 종목 없음</td></tr>'
    limits = "".join(f"<li>{_e(x)}</li>" for x in rep["limits"])
    n_dep = len(rep["departed"])

    return f"""<title>PivoxReport {acct}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;1,400&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;1,8..60,400&family=Geist:wght@400;500&family=Noto+Sans+KR:wght@400;500&family=JetBrains+Mono:wght@400&display=swap">
{_PRETENDARD if not paper else ""}
<style>{_css(p)}</style>
<div class="wrap">
<header class="mast">
  <h1>기록이 되비추는 것</h1>
  <div class="who">토스증권 계좌 {_e(acct)}<br>{_e(gen)} KST<br>Toss Open API · read-only</div>
</header>

{lead}
{finds}
{stmt}

<section class="sec">
  <div class="sh"><h2>이 리포트가 딛고 선 이력</h2><span class="cnt">체결 {h["fills"]}건</span></div>
  {_history_status(h)}
</section>

<section class="sec">
  <div class="sh"><h2>보유</h2><span class="cnt">{c["positions"]}종목</span></div>
  <p class="note">왼쪽은 각 종목이 평가액에서 차지하는 몫, 오른쪽은 평단 대비 지금 위치. 같은 줄이 같은 종목이다.</p>
  <div class="tbl">{_holdings_rows_svg(rep["holdings"], p, rows_per_page)}</div>
  <div class="legend"><span><i style="background:{p.bronze}"></i>비중</span><span><i style="background:{p.up}"></i>평단 위</span><span><i style="background:{p.down}"></i>평단 아래</span></div>
</section>

<section class="sec">
  <div class="sh"><h2>경로</h2><span class="cnt">{c["positions"]}종목 보유 · {n_dep}종목 정리</span></div>
  <p class="note">종목마다 처음 산 날부터 오늘까지의 선. 위쪽 삼각형이 매수, 아래쪽이 매도. 흐린 선은 이미 떠난 종목.</p>
  <div class="tbl">{_timeline_svg(rep, p, tracks_per_page)}</div>
  <div class="legend"><span><i style="background:{p.bronze}"></i>보유 중</span><span><i style="background:{p.ghost}"></i>정리함</span><span>▲ 매수 · ▼ 매도</span></div>
</section>

<section class="sec">
  <div class="sh"><h2>거울</h2><span class="cnt">최근 {rep["window_days"]}일 대 전체</span></div>
  <p class="note">같은 잣대를 두 기간에 나란히 댄다. 두 열이 다르면 최근이 평소와 다른 것이다. 최근 열의 평단·보유일은 전체 이력을 딛고 계산한다.</p>
  {_mirror_table(rep["mirrors"], rep["window_days"])}
</section>

<section class="sec">
  <div class="sh"><h2>집중</h2><span class="cnt">국내 {(c["kr_pct"] or 0):.1f}% · 해외 {(c["us_pct"] or 0):.1f}%</span></div>
  {conc}
  {_split_bar_svg(c["kr_pct"], c["us_pct"], p)}
</section>

<section class="sec">
  <div class="sh"><h2>보유 종목의 이력</h2><span class="cnt">{c["positions"]}종목</span></div>
  <div class="tbl"><table class="plain"><thead><tr><th>종목</th><th>보유 시작</th><th>보유일</th><th>매수/매도</th><th>마지막 체결</th><th>수량</th><th>평단</th><th>손익률</th></tr></thead><tbody>{hold_rows}</tbody></table></div>
</section>

<section class="sec">
  <div class="sh"><h2>떠난 종목</h2><span class="cnt">{n_dep}종목</span></div>
  <div class="tbl"><table class="plain"><thead><tr><th>종목</th><th>처음</th><th>마지막</th><th>매수/매도</th><th>실현손익</th><th>매도 수익률 중앙값</th></tr></thead><tbody>{dep_rows}</tbody></table></div>
</section>

{_analysis_section(rep.get("analysis") or {}, p)}
<div class="foot">
  <span class="basis">이 리포트는 토스증권 Open API 를 읽기 전용으로 조회해 만들었다. 주문 경로는 없다. 기록을 되비추는 거울이며, 다음에 무엇을 할지는 여기 없다.</span>
  <ul>{limits}</ul>
</div>
</div>
"""
