"""PivoxReport — self-contained HTML rendering of the v2 mirror report.

Same dict :func:`services.toss.mirror_report.build_mirror_report` returns,
drawn instead of tabulated: weights and returns as one row per holding,
the account's path as a timeline of every fill, the two mirror columns
side by side. Design tokens are the product's v3 set (Vantablack ground,
bronze accent, KR red-up / blue-down, Playfair for the headline figures)
so the page reads as the same product as /mirror.

No JavaScript beyond nothing — every chart is inline SVG computed here,
hover detail rides on ``<title>``. No external asset but the fonts.
Numbers are the report's numbers; this module formats and places them and
never derives a new one.
"""
from __future__ import annotations

import html
from datetime import date

# ── v3 tokens (frontend/src/app/globals.css) ─────────────────────────────────
INK = "#050505"
ONYX = "#111111"
IVORY = "#F5F0E8"
BRONZE = "#B8956A"
BRONZE_LIGHT = "#A3845C"
UP = "#D18888"     # KR convention: red = gain
DOWN = "#7AA0C8"   # KR convention: blue = loss

_CSS = f"""
:root {{ --ink:{INK}; --onyx:{ONYX}; --ivory:{IVORY}; --ivory-soft:rgba(245,240,232,.78); --ivory-dim:rgba(245,240,232,.55);
  --ivory-faint:rgba(245,240,232,.45); --line:rgba(245,240,232,.08); --line-soft:rgba(245,240,232,.05); --veil:rgba(245,240,232,.04);
  --bronze:{BRONZE}; --bronze-light:{BRONZE_LIGHT}; --up:{UP}; --down:{DOWN};
  --serif:"Playfair Display", Georgia, "Times New Roman", serif; --sans:"Noto Sans KR", Pretendard, -apple-system, system-ui, sans-serif;
  --mono:"JetBrains Mono", ui-monospace, Menlo, Consolas, monospace; }}
html {{ color-scheme: dark; }}
body {{ margin:0; background:var(--ink); color:var(--ivory); font-family:var(--sans); font-size:14px; line-height:1.6; padding-block:40px 64px; padding-inline:20px; -webkit-font-smoothing:antialiased; }}
.wrap {{ max-width:720px; margin:0 auto; }}
.eyebrow {{ font-family:var(--mono); font-size:10.5px; letter-spacing:.14em; text-transform:uppercase; color:var(--bronze); }}
h1 {{ font-family:var(--serif); font-weight:400; font-size:clamp(28px,6vw,40px); line-height:1.15; margin:8px 0 6px; text-wrap:balance; }}
.meta {{ font-family:var(--mono); font-size:11px; color:var(--ivory-dim); }}
h2 {{ font-family:var(--serif); font-weight:400; font-size:22px; margin:0 0 4px; }}
section {{ padding-block:28px; border-top:1px solid var(--line); }}
section:first-of-type {{ border-top:0; }}
.lede {{ color:var(--ivory-soft); font-size:13px; margin:0 0 18px; max-width:62ch; }}
.tiles {{ display:grid; grid-template-columns:repeat(2,1fr); gap:1px; background:var(--line); border:1px solid var(--line); margin-top:20px; }}
@media (min-width:560px) {{ .tiles {{ grid-template-columns:repeat(4,1fr); }} }}
.tile {{ background:var(--ink); padding:16px 14px 14px; }}
.tile .k {{ font-family:var(--mono); font-size:10.5px; letter-spacing:.1em; text-transform:uppercase; color:var(--ivory-dim); }}
.tile .v {{ font-family:var(--serif); font-size:24px; line-height:1.1; margin-top:8px; font-variant-numeric:tabular-nums; }}
.tile .s {{ font-family:var(--mono); font-size:11px; color:var(--ivory-dim); margin-top:6px; }}
.up {{ color:var(--up); }} .down {{ color:var(--down); }} .dim {{ color:var(--ivory-dim); }}
.status {{ display:flex; gap:10px; align-items:flex-start; padding:12px 14px; background:var(--veil); border-left:2px solid var(--bronze); font-size:13px; }}
.status.warn {{ border-left-color:var(--down); }}
.status ul {{ margin:6px 0 0; padding-left:18px; color:var(--ivory-soft); }}
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
.legend {{ display:flex; gap:16px; flex-wrap:wrap; font-family:var(--mono); font-size:11px; color:var(--ivory-dim); margin-top:8px; }}
.legend i {{ display:inline-block; width:10px; height:10px; margin-right:6px; vertical-align:-1px; }}
ul.limits {{ margin:0; padding-left:18px; color:var(--ivory-soft); font-size:13px; }}
.sig {{ margin-top:40px; font-family:var(--serif); font-style:italic; color:var(--ivory-dim); text-align:center; }}
"""


def _e(s) -> str:
    return html.escape(str(s if s is not None else ""))


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


def _d(s: str | None) -> date | None:
    return date.fromisoformat(s) if s else None


# ── charts ───────────────────────────────────────────────────────────────────
def _holdings_rows_svg(holdings: list[dict]) -> str:
    """One row per holding: name · weight bar (bronze, magnitude) · return bar
    (diverging from a zero line, KR red/blue). Same order top to bottom so
    the two charts read as one table."""
    if not holdings:
        return '<p class="dim">보유 종목 없음</p>'
    W, name_w, gap, bar_h, row_h = 720, 176, 16, 18, 30
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
        out.append(f'<text x="0" y="{cy + 4}" class="lbl">{_e(label[:22])}</text>')
        w = (h["weight_pct"] or 0) / max_w * (wcol_w - 46)
        out.append(f'<rect x="{wcol_x}" y="{y}" width="{w:.1f}" height="{bar_h}" fill="{BRONZE}" rx="0"><title>{_e(label)} · 비중 {_pct(h["weight_pct"], False)} · 평가액 {_won(h["market_value_krw"])}</title></rect>')
        out.append(f'<text x="{wcol_x + w + 6:.1f}" y="{cy + 4}">{_pct(h["weight_pct"], False)}</text>')
        r = h["unrealised_rate_pct"] or 0
        rw = abs(r) / max_r * (rcol_w / 2 - 44)
        color = UP if r > 0 else DOWN
        x = zero_x if r >= 0 else zero_x - rw
        out.append(f'<rect x="{x:.1f}" y="{y}" width="{max(rw, 1):.1f}" height="{bar_h}" fill="{color}"><title>{_e(label)} · 손익률 {_pct(r)} · 평단 {h["avg_purchase_price"]:,} → 현재가 기준</title></rect>')
        tx = zero_x + rw + 6 if r >= 0 else zero_x - rw - 6
        anchor = "start" if r >= 0 else "end"
        out.append(f'<text x="{tx:.1f}" y="{cy + 4}" text-anchor="{anchor}">{_pct(r)}</text>')
    out.append("</svg>")
    return "".join(out)


def _timeline_svg(rep: dict) -> str:
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
    W, name_w, right = 720, 176, 24
    row_h, pad_top = 26, 26
    px = lambda d: name_w + (d - x0d).days / span * (W - name_w - right)  # noqa: E731
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
    out.append(f'<line x1="{px(today):.1f}" y1="{pad_top - 8}" x2="{px(today):.1f}" y2="{H - 16}" stroke="{BRONZE}" stroke-width="1" stroke-dasharray="2 3"/>')
    out.append(f'<text x="{px(today) - 3:.1f}" y="{H - 4}" class="muted" text-anchor="end">오늘</text>')
    by_sym: dict[str, list[dict]] = {}
    for f in fills:
        by_sym.setdefault(f["symbol"], []).append(f)
    for i, (label, a, b, is_open, sym) in enumerate(tracks):
        y = pad_top + i * row_h + 10
        out.append(f'<text x="0" y="{y + 4}" class="lbl" fill="{IVORY if is_open else "rgba(245,240,232,.55)"}">{_e(label[:22])}</text>')
        xa, xb = px(a), px(b)
        out.append(f'<line x1="{xa:.1f}" y1="{y}" x2="{max(xb, xa + 2):.1f}" y2="{y}" stroke="{BRONZE if is_open else "rgba(245,240,232,.25)"}" stroke-width="{3 if is_open else 2}"><title>{_e(label)} · {a} → {"오늘" if is_open else b} · {(b - a).days}일</title></line>')
        for f in by_sym.get(sym, []):
            x = px(_d(f["date"]))
            if f["side"] == "in":
                out.append(f'<path d="M{x:.1f},{y - 3} l-4,-7 h8 z" fill="{BRONZE}"><title>{f["date"]} 매수 {f["qty"]:g}주 @ {f["price"]:,}</title></path>')
            else:
                out.append(f'<path d="M{x:.1f},{y + 3} l-4,7 h8 z" fill="{IVORY}"><title>{f["date"]} 매도 {f["qty"]:g}주 @ {f["price"]:,} · {_pct(f.get("pnl_pct"))}</title></path>')
    out.append("</svg>")
    return "".join(out)


def _split_bar_svg(kr: float | None, us: float | None) -> str:
    if kr is None:
        return ""
    W, H = 720, 34
    kw = kr / 100 * W
    return (f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="국내 해외 비중">'
            f'<rect x="0" y="6" width="{max(kw - 1, 0):.1f}" height="14" fill="{BRONZE}"><title>국내 {kr:.2f}%</title></rect>'
            f'<rect x="{kw + 1:.1f}" y="6" width="{max(W - kw - 1, 0):.1f}" height="14" fill="{BRONZE_LIGHT}" opacity=".55"><title>해외 {us:.2f}%</title></rect>'
            f'<text x="0" y="32">국내 {kr:.2f}%</text><text x="{W}" y="32" text-anchor="end">해외 {us:.2f}%</text></svg>')


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
    foot = (f'<p class="lede" style="margin-top:14px">지금 들고 있는 매수분 {ages["lots"]}건의 나이: 중앙값 {_days(ages["median"])} · 가장 오래된 것 {_days(ages["oldest"])}</p>'
            if ages["lots"] else "")
    return (f'<div class="tbl"><table class="mirror"><thead><tr><th></th><th>최근 {window_days}일</th><th>전체 이력</th></tr></thead>'
            f'<tbody>{body}</tbody></table></div>{foot}')


def _days(v) -> str:
    return "—" if v is None else f"{v:g}일"


def _fo(n, below, above) -> str:
    return "없음" if not n else f"{n}건 · 평단 아래 {below} / 위 {above}"


def _side(n, hold, pct) -> str:
    return "없음" if not n else f"{n}건 · 보유 {_days(hold)} · {pct:+.2f}%"


def _history_status(h: dict) -> str:
    if h["complete"]:
        return (f'<div class="status"><div>이력으로 되짚은 보유 {h["checked_symbols"]}종목의 수량·평균단가가 <strong>토스 잔고와 전부 일치</strong>. '
                f'조회 시작 {_e(h["since"] or "전체")} · 첫 체결 {_e(h["first_fill_at"] or "—")} · 체결 {h["fills"]}건. 아래 실현손익은 전체 이력 기준.</div></div>')
    items = "".join(f'<li>{_e(m["symbol"])}: {_e(m["reason"])} (이력 {m["rebuilt_qty"]:g}주 / 토스 {m["toss_qty"]:g}주)</li>' for m in h["mismatches"])
    return (f'<div class="status warn"><div>이력으로 되짚은 결과가 토스 잔고와 <strong>{len(h["mismatches"])}종목에서 다르다</strong>. '
            f'조회 시작 {_e(h["since"] or "전체")} · 체결 {h["fills"]}건. 실현손익은 부분 — 아래 종목은 취득단가가 틀렸을 수 있다.<ul>{items}</ul></div></div>')


def render_mirror_html(rep: dict) -> str:
    v, c, h = rep["valuation"], rep["concentration"], rep["history"]
    acct = rep["account"]["account_no_masked"]
    gen = rep["generated_at"][:16].replace("T", " ")
    tiles = [
        ("주식 평가액", _won(v["equity_value_krw"]), f"국내 {_won(v['krw_leg'])} · 해외 ${(v['usd_leg'] or 0):,.2f}", ""),
        ("미실현", _won(v["unrealised_krw"]), f"매입 {_won(v['purchase_total_krw'])} 대비 {_pct(v['unrealised_rate_pct'])}", _cls(v["unrealised_krw"])),
        ("실현 누계", _won(h["realised_net_krw"]), ("전체 이력 · 수수료·세금 차감" if h["complete"] else "부분 이력 · 수수료·세금 차감"), _cls(h["realised_net_krw"])),
        ("오늘", _won(v["daily_krw"]), _pct(v["daily_rate_pct"]), _cls(v["daily_krw"])),
    ]
    tiles_html = "".join(f'<div class="tile"><div class="k">{_e(k)}</div><div class="v {cl}">{_e(val)}</div><div class="s">{_e(s)}</div></div>' for k, val, s, cl in tiles)

    largest = c["largest"]
    conc = (f'<p class="lede">보유 {c["positions"]}종목. 가장 큰 종목은 {_e(_nm(largest["symbol"], largest["name"]))}, 평가액의 {largest["weight_pct"]:.2f}%. '
            f'30% 선을 넘는 종목: {_e(", ".join(c["over_30pct"]) if c["over_30pct"] else "없음")}.</p>' if largest else '<p class="lede">보유 종목 없음.</p>')

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

    return f"""<title>PivoxReport {acct}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;1,400&family=Noto+Sans+KR:wght@400;500&family=JetBrains+Mono:wght@400&display=swap">
<style>{_CSS}</style>
<div class="wrap">
<header>
  <div class="eyebrow">PivoxReport · 토스증권 계좌 {_e(acct)}</div>
  <h1>기록이 되비추는 것</h1>
  <div class="meta">{_e(gen)} KST · Toss Open API, read-only · USD/KRW {rep["fx"]["usdkrw"]}</div>
  <div class="tiles">{tiles_html}</div>
</header>

<section>
  <h2>이 리포트가 딛고 선 이력</h2>
  {_history_status(h)}
</section>

<section>
  <h2>보유</h2>
  <p class="lede">왼쪽은 각 종목이 평가액에서 차지하는 몫, 오른쪽은 평단 대비 지금 위치. 같은 줄이 같은 종목이다.</p>
  <div class="tbl">{_holdings_rows_svg(rep["holdings"])}</div>
  <div class="legend"><span><i style="background:{BRONZE}"></i>비중</span><span><i style="background:{UP}"></i>평단 위</span><span><i style="background:{DOWN}"></i>평단 아래</span></div>
</section>

<section>
  <h2>경로</h2>
  <p class="lede">종목마다 처음 산 날부터 오늘까지의 선. 위쪽 삼각형이 매수, 아래쪽이 매도. 흐린 선은 이미 떠난 종목.</p>
  <div class="tbl">{_timeline_svg(rep)}</div>
  <div class="legend"><span><i style="background:{BRONZE}"></i>보유 중</span><span><i style="background:rgba(245,240,232,.25)"></i>정리함</span><span>▲ 매수 · ▼ 매도</span></div>
</section>

<section>
  <h2>거울</h2>
  <p class="lede">같은 잣대를 최근 {rep["window_days"]}일과 전체 이력에 나란히 댄다. 두 열이 다르면 최근이 평소와 다른 것이다. 최근 열의 평단·보유일은 전체 이력을 딛고 계산한다.</p>
  {_mirror_table(rep["mirrors"], rep["window_days"])}
</section>

<section>
  <h2>집중</h2>
  {conc}
  {_split_bar_svg(c["kr_pct"], c["us_pct"])}
</section>

<section>
  <h2>보유 종목의 이력</h2>
  <div class="tbl"><table class="plain"><thead><tr><th>종목</th><th>보유 시작</th><th>보유일</th><th>매수/매도</th><th>마지막 체결</th><th>수량</th><th>평단</th><th>손익률</th></tr></thead><tbody>{hold_rows}</tbody></table></div>
</section>

<section>
  <h2>떠난 종목</h2>
  <div class="tbl"><table class="plain"><thead><tr><th>종목</th><th>처음</th><th>마지막</th><th>매수/매도</th><th>실현손익</th><th>매도 수익률 중앙값</th></tr></thead><tbody>{dep_rows}</tbody></table></div>
</section>

<section>
  <h2>이 숫자가 말하지 않는 것</h2>
  <ul class="limits">{limits}</ul>
  <p class="sig">기록을 되비추는 거울이다. 다음에 무엇을 할지는 여기 없다.</p>
</section>
</div>
"""
