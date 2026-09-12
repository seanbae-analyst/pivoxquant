"""PivoxReport — analysis of one account's rebuilt history.

Where the mirrors state facts one at a time, this module puts them next to
each other and says what the arrangement shows: which symbols made and
lost the money, what a closed trade has typically been worth, how the
holding period differs between the trades that ended up and the ones that
ended down, what the sold positions did after they were sold, when in the
day and week the fills happen, and how position sizes are distributed.
Every statement is a number the reader could recompute from the book;
the prose only names the pattern the numbers already form.

Section 8 is the one that crosses the other way. Everything above answers
"how do I trade"; the cards answer "what happened with this one" — where
the average went as each purchase moved it, whether the position was ever
emptied and re-entered, and what the symbol came to. The data was already
in the book; nothing was reading it per symbol.

Inputs are the rebuilt :class:`services.toss.history.PositionHistory` book,
the holdings rows, the FX rate, and a ``prices`` map of current prices for
symbols no longer held (from ``GET /api/v1/prices``) — without prices the
"after selling" section says so and is skipped, nothing is guessed.
"""
from __future__ import annotations

import statistics
from collections import Counter
from datetime import datetime
from decimal import Decimal

from services.toss.report import D, _f, to_krw

ZERO = Decimal(0)
_WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]


def _med(xs):
    return round(statistics.median(xs), 2) if xs else None


def _mean(xs):
    return round(statistics.fmean(xs), 2) if xs else None


# ── 1. P&L attribution ───────────────────────────────────────────────────────
def attribution(book: dict, holdings_rows: list[dict], usdkrw: Decimal, names: dict[str, str] | None = None) -> dict:
    """Realised (net of fees) and unrealised, per symbol, in KRW; totals; fee drag."""
    names = {**(names or {}), **{r["symbol"]: r.get("name") for r in holdings_rows if r.get("name")}}
    unreal = {r["symbol"]: Decimal(str(r["market_value_krw"])) - Decimal(str(r["purchase_amount_krw"])) for r in holdings_rows}
    rows = []
    fees_total = gross_total = ZERO
    for sym, p in book.items():
        real_net = sum((o.realised_net for o in p.sell_outcomes), ZERO)
        real_krw = to_krw(real_net, p.currency, usdkrw)
        fees_total += to_krw(p.fees, p.currency, usdkrw)
        gross_total += to_krw(sum((o.realised_gross for o in p.sell_outcomes), ZERO), p.currency, usdkrw)
        u = unreal.get(sym, ZERO)
        rows.append({"symbol": sym, "name": names.get(sym), "realised_krw": _f(real_krw, 0), "unrealised_krw": _f(u, 0),
                     "total_krw": _f(real_krw + u, 0), "held": sym in unreal})
    for sym, u in unreal.items():
        if sym not in book:
            rows.append({"symbol": sym, "name": names.get(sym), "realised_krw": 0.0, "unrealised_krw": _f(u, 0), "total_krw": _f(u, 0), "held": True})
    rows.sort(key=lambda r: r["total_krw"], reverse=True)
    realised = sum(r["realised_krw"] for r in rows)
    unrealised = sum(r["unrealised_krw"] for r in rows)
    return {
        "rows": rows,
        "realised_krw": round(realised), "unrealised_krw": round(unrealised), "total_krw": round(realised + unrealised),
        "fees_krw": _f(fees_total, 0),
        "fee_share_of_gross_pct": _f(fees_total / abs(gross_total) * 100) if gross_total else None,
        "top": [r for r in rows if r["total_krw"] > 0][:3],
        "bottom": [r for r in rows if r["total_krw"] < 0][::-1][:3],
    }


# ── 2. Closed-trade statistics ───────────────────────────────────────────────
def trade_stats(book: dict, usdkrw: Decimal) -> dict:
    """Every sale is one closed trade: win rate, typical win and loss, payoff,
    expectancy per trade (KRW), holding-day asymmetry, and the two extremes."""
    sells = [(p, o) for p in book.values() for o in p.sell_outcomes]
    if not sells:
        return {"closed": 0}
    wins = [(p, o) for p, o in sells if o.pnl_pct > 0]
    losses = [(p, o) for p, o in sells if o.pnl_pct < 0]
    krw = [float(to_krw(o.realised_net, p.currency, usdkrw)) for p, o in sells]
    win_pct = [o.pnl_pct for _, o in wins]
    loss_pct = [o.pnl_pct for _, o in losses]
    win_days = [o.held_days for _, o in wins]
    loss_days = [o.held_days for _, o in losses]
    best = max(sells, key=lambda po: to_krw(po[1].realised_net, po[0].currency, usdkrw))
    worst = min(sells, key=lambda po: to_krw(po[1].realised_net, po[0].currency, usdkrw))

    def ex(p, o):
        return {"symbol": p.symbol, "date": o.fill.at.date().isoformat(), "pnl_pct": round(o.pnl_pct, 2),
                "realised_krw": _f(to_krw(o.realised_net, p.currency, usdkrw), 0), "held_days": o.held_days}
    mw, ml = _mean(win_pct), _mean(loss_pct)
    return {
        "closed": len(sells), "wins": len(wins), "losses": len(losses),
        "win_rate_pct": round(len(wins) / len(sells) * 100, 1),
        "median_win_pct": _med(win_pct), "median_loss_pct": _med(loss_pct),
        "mean_win_pct": mw, "mean_loss_pct": ml,
        "payoff_ratio": round(abs(mw / ml), 2) if mw and ml else None,
        "expectancy_krw": round(statistics.fmean(krw)),
        "median_trade_krw": round(statistics.median(krw)),
        "win_hold_median_days": _med(win_days), "loss_hold_median_days": _med(loss_days),
        "hold_asymmetry": round(statistics.median(loss_days) / statistics.median(win_days), 2) if win_days and loss_days and statistics.median(win_days) > 0 else None,
        "best": ex(*best), "worst": ex(*worst),
        # Every closed trade, not just the medians of them. A median is a
        # summary of a distribution and cannot be drawn as one; the scatter and
        # the cumulative curve both need the trades themselves.
        "sales": sorted((ex(p, o) for p, o in sells), key=lambda x: x["date"]),
        "top5_share_pct": round(sum(sorted(pos, reverse=True)[:5]) / sum(pos) * 100, 1) if (pos := [k for k in krw if k > 0]) else None,
    }


# ── 3. After selling ─────────────────────────────────────────────────────────
def after_selling(book: dict, held: set[str], prices: dict[str, dict], usdkrw: Decimal, names: dict[str, str]) -> dict:
    """For each symbol fully sold: where its price is now versus the average
    sale price, and what the sold shares would be worth had they been kept.
    Needs current prices; without them the section reports that and stops."""
    if not prices:
        return {"available": False, "rows": []}
    rows = []
    kept_delta_total = ZERO
    for sym, p in book.items():
        if sym in held or not p.sell_outcomes or sym not in prices:
            continue
        now = D(prices[sym].get("lastPrice"))
        if now <= 0:
            continue
        qty = sum((o.fill.quantity for o in p.sell_outcomes), ZERO)
        proceeds = sum((o.fill.amount for o in p.sell_outcomes), ZERO)
        avg_sell = proceeds / qty if qty else ZERO
        delta = (now - avg_sell) * qty
        kept_delta_total += to_krw(delta, p.currency, usdkrw)
        rows.append({
            "symbol": sym, "name": names.get(sym, ""), "currency": p.currency,
            "last_sold_at": p.last_fill_at.date().isoformat() if p.last_fill_at else None,
            "avg_sell_price": _f(avg_sell, 4), "price_now": _f(now, 4),
            "since_sale_pct": _f((now - avg_sell) / avg_sell * 100) if avg_sell else None,
            "kept_delta_krw": _f(to_krw(delta, p.currency, usdkrw), 0),
        })
    rows.sort(key=lambda r: r["kept_delta_krw"], reverse=True)
    up = [r for r in rows if (r["since_sale_pct"] or 0) > 0]
    return {
        "available": True, "rows": rows, "count": len(rows),
        "higher_now": len(up), "lower_now": len(rows) - len(up),
        "kept_delta_krw": _f(kept_delta_total, 0),
        "median_since_sale_pct": _med([r["since_sale_pct"] for r in rows if r["since_sale_pct"] is not None]),
    }


# ── 4. When the fills happen ─────────────────────────────────────────────────
def timing(fills: list) -> dict:
    """Fills by weekday and by KST hour, and how bunched they are."""
    if not fills:
        return {"fills": 0}
    wd = Counter(f.at.weekday() for f in fills)
    hr = Counter(f.at.hour for f in fills)
    per_day = Counter(f.at.date() for f in fills)
    slot = Counter((f.at.weekday(), f.at.hour) for f in fills)
    kr_open = sum(1 for f in fills if f.currency == "KRW" and 9 <= f.at.hour < 10)
    kr = sum(1 for f in fills if f.currency == "KRW")
    us_night = sum(1 for f in fills if f.currency == "USD" and (f.at.hour >= 22 or f.at.hour < 6))
    us = sum(1 for f in fills if f.currency == "USD")
    busiest = per_day.most_common(1)[0]
    return {
        "fills": len(fills),
        "by_weekday": [{"day": _WEEKDAYS[i], "fills": wd.get(i, 0)} for i in range(7)],
        "by_hour": [{"hour": h, "fills": hr.get(h, 0)} for h in range(24)],
        # The two margins separately cannot show a weekday-hour interaction —
        # "Friday nights" is invisible in a Friday total and a 22:00 total. The
        # matrix is 7x24 of small integers, so it costs nothing to carry.
        "matrix": [[slot.get((d, h), 0) for h in range(24)] for d in range(7)],
        "kr_first_hour_pct": round(kr_open / kr * 100, 1) if kr else None,
        "us_regular_night_pct": round(us_night / us * 100, 1) if us else None,
        "trade_days": len(per_day),
        "days_with_3plus": sum(1 for n in per_day.values() if n >= 3),
        "busiest_day": {"date": busiest[0].isoformat(), "fills": busiest[1]},
        "fills_per_trade_day": round(len(fills) / len(per_day), 2),
    }


# ── 5. Position sizing ───────────────────────────────────────────────────────
def sizing(fills: list, usdkrw: Decimal) -> dict:
    buys = [float(to_krw(f.amount, f.currency, usdkrw)) for f in fills if f.side == "BUY"]  # // legal-ok — Toss enum, compared only
    if not buys:
        return {"buys": 0}
    total = sum(buys)
    largest = max(buys)
    mean = statistics.fmean(buys)
    return {
        "buys": len(buys), "median_buy_krw": round(statistics.median(buys)), "mean_buy_krw": round(mean),
        "largest_buy_krw": round(largest), "largest_share_pct": round(largest / total * 100, 1),
        "cv": round(statistics.pstdev(buys) / mean, 2) if mean else None,
        "under_100k_pct": round(sum(1 for b in buys if b < 100_000) / len(buys) * 100, 1),
    }


# ── 6. KR vs US ──────────────────────────────────────────────────────────────
def by_market(book: dict, holdings_rows: list[dict], usdkrw: Decimal) -> list[dict]:
    out = []
    for cur, label in (("KRW", "국내"), ("USD", "해외")):
        ps = [p for p in book.values() if p.currency == cur]
        sells = [o for p in ps for o in p.sell_outcomes]
        realised = sum((to_krw(o.realised_net, cur, usdkrw) for o in sells), ZERO)
        unreal = sum((Decimal(str(r["market_value_krw"])) - Decimal(str(r["purchase_amount_krw"]))
                      for r in holdings_rows if r.get("currency") == cur), ZERO)
        wins = sum(1 for o in sells if o.pnl_pct > 0)
        out.append({
            "market": label, "symbols": len(ps), "closed": len(sells),
            "win_rate_pct": round(wins / len(sells) * 100, 1) if sells else None,
            "median_hold_days": _med([o.held_days for o in sells]),
            "realised_krw": _f(realised, 0), "unrealised_krw": _f(unreal, 0), "total_krw": _f(realised + unreal, 0),
        })
    return out


def asymmetry_phrase(ratio: float) -> str:
    """'손실 쪽이 3.2배 길다' / '이익 쪽이 1.4배 길다' — never a ratio below one."""
    if ratio >= 1:
        return f"손실 쪽이 {ratio}배 길다"
    return f"이익 쪽이 {round(1 / ratio, 2)}배 길다"


# ── 7. The three lines ───────────────────────────────────────────────────────
def headline(a: dict, t: dict, s: dict, m: list[dict], after: dict, tm: dict) -> list[str]:
    """Pick the strongest patterns and say each in one sentence with its
    numbers. Ranked by how far each departs from even, so the same account
    always gets the same three."""
    cands: list[tuple[float, str]] = []
    if t.get("closed"):
        if t.get("hold_asymmetry"):
            cands.append((abs(t["hold_asymmetry"] - 1) * 2,
                          f"이익은 중앙값 {t['win_hold_median_days']:g}일 만에 실현하고 손실은 {t['loss_hold_median_days']:g}일 들고 있다 — {asymmetry_phrase(t['hold_asymmetry'])}."))
        cands.append((abs(t["win_rate_pct"] - 50) / 25,
                      f"닫힌 거래 {t['closed']}건 중 {t['wins']}건이 이익({t['win_rate_pct']}%). 이길 때 중앙값 {t['median_win_pct']:+.2f}%, 질 때 {t['median_loss_pct']:+.2f}%, 거래당 기대값 ₩{t['expectancy_krw']:,}."))
        if t.get("top5_share_pct") and t["top5_share_pct"] > 40 and t["wins"] > 5:
            cands.append((t["top5_share_pct"] / 50,
                          f"실현 이익의 {t['top5_share_pct']}%가 상위 5건에서 나왔다 — 나머지 이익 거래 {t['wins'] - 5}건을 합쳐도 그보다 작다."))
    if a.get("rows"):
        r, u = a["realised_krw"], a["unrealised_krw"]
        if (r > 0) != (u > 0) and r and u:
            cands.append((min(abs(r), abs(u)) / max(abs(r), abs(u)) + 1,
                          f"정리한 종목에서 ₩{int(r):,}를 실현했고, 들고 있는 종목은 ₩{int(u):,} 상태다 — 판 것과 쥔 것의 부호가 반대다."))
    km = {x["market"]: x for x in m}
    if km.get("국내", {}).get("closed") and km.get("해외", {}).get("closed"):
        kr, us = km["국내"], km["해외"]
        if kr["win_rate_pct"] is not None and us["win_rate_pct"] is not None:
            cands.append((abs(kr["win_rate_pct"] - us["win_rate_pct"]) / 25,
                          f"해외 거래 승률 {us['win_rate_pct']}% ({us['closed']}건) 대 국내 {kr['win_rate_pct']}% ({kr['closed']}건). 합산 손익은 해외 ₩{int(us['total_krw']):,}, 국내 ₩{int(kr['total_krw']):,}."))
    if after.get("available") and after.get("count"):
        cands.append((abs(after["kept_delta_krw"]) / max(abs(a.get("realised_krw") or 1), 1),
                      f"정리한 {after['count']}종목 중 {after['higher_now']}개는 판 가격보다 지금이 높다. 팔지 않았다면 ₩{int(after['kept_delta_krw']):,} 차이."))
    if tm.get("fills"):
        if tm.get("kr_first_hour_pct") and tm["kr_first_hour_pct"] > 40:
            cands.append((tm["kr_first_hour_pct"] / 60, f"국내 체결의 {tm['kr_first_hour_pct']}%가 개장 첫 한 시간(09~10시)에 몰려 있다."))
        if tm["days_with_3plus"]:
            cands.append((tm["days_with_3plus"] / max(tm["trade_days"], 1) * 2,
                          f"거래한 {tm['trade_days']}일 중 {tm['days_with_3plus']}일은 하루 3건 이상 체결했다. 가장 많은 날은 {tm['busiest_day']['date']}, {tm['busiest_day']['fills']}건."))
    if s.get("buys") and s.get("largest_share_pct") and s["largest_share_pct"] > 15:
        cands.append((s["largest_share_pct"] / 20, f"매수 한 건의 중앙값은 ₩{s['median_buy_krw']:,}인데 가장 큰 한 건이 ₩{s['largest_buy_krw']:,}, 전체 매수액의 {s['largest_share_pct']}%다."))
    cands.sort(key=lambda c: c[0], reverse=True)
    return [text for _, text in cands[:3]]


# ── 8. One symbol at a time ──────────────────────────────────────────────────
# Everything above crosses the whole account. That answers "how do I trade" and
# never "what happened with this one", which is the question a holdings list
# actually raises. The book already holds the answer per symbol — the running
# average before and after every fill — and nothing was reading it.
_CARD_CAP = 16


def _card_note(c: dict) -> str | None:
    """The one sentence this symbol earns, or nothing.

    Ranked inside the card rather than across the account: a card with no
    pattern says nothing rather than reaching for the least weak one.
    """
    fo, closed = c["follow_on"], c["closed"]
    # A won price with two decimals is not a price anyone quotes; a dollar one
    # without them is not either. The note is prose and has to read like it.
    def px(v):
        return "—" if v is None else (f"${v:,.2f}" if c["currency"] == "USD" else f"{round(v):,}")

    if c["reentries"]:
        gap = f"{c['gap_days']:.0f}일" if c["gap_days"] is not None else "얼마 뒤"
        return f"전량 정리하고 {gap} 만에 다시 샀다 — 이 종목에서 {c['reentries'] + 1}번째 자리다."
    if fo["below"] >= 3 and fo["below"] > fo["above"] * 2:
        return (f"추가 매수 {fo['below'] + fo['above'] + fo['flat']}건 중 {fo['below']}건이 평단 아래였다 — "
                f"평단이 {px(c['avg_first'])}에서 {px(c['avg_now'])}까지 내려왔다.")
    if fo["above"] >= 3 and fo["above"] > fo["below"] * 2:
        return (f"추가 매수 {fo['below'] + fo['above'] + fo['flat']}건 중 {fo['above']}건이 평단 위였다 — "
                f"오를수록 더 샀고 평단은 {px(c['avg_first'])}에서 {px(c['avg_now'])}가 됐다.")
    if closed >= 3 and c["win_rate_pct"] is not None and c["win_rate_pct"] <= 34:
        return f"이 종목에서 닫은 {closed}건 중 이익은 {c['wins']}건뿐이다."
    if closed >= 3 and c["win_rate_pct"] is not None and c["win_rate_pct"] >= 75:
        return f"이 종목에서 닫은 {closed}건 중 {c['wins']}건이 이익이다."
    if c["held"] and (c["held_days"] or 0) >= 180 and abs(c["unrealised_rate_pct"] or 0) < 3:
        return f"{c['held_days']}일 들고 있는 동안 평단 대비 {c['unrealised_rate_pct']:+.2f}%다 — 움직이지 않은 자리다."
    if c["sells"] == 0 and c["buys"] >= 4:
        return f"{c['buys']}번 사기만 하고 한 번도 팔지 않았다."
    return None


def per_symbol(book: dict, holdings_rows: list[dict], usdkrw: Decimal, names: dict[str, str],
               attribution_rows: list[dict]) -> dict:
    """One card per symbol: the average-cost track, what each buy did to it,
    what the closed trades came to, and what the symbol contributed.

    Held symbols first — they are what the reader owns and the question is about
    them — then the departed ones by how much they moved the account. Both are
    capped; the fold is reported, never silent.
    """
    held = {r["symbol"]: r for r in holdings_rows}
    contrib = {r["symbol"]: r for r in attribution_rows}
    cards = []
    for sym, p in book.items():
        events = sorted(
            [("BUY", b.fill, b.avg_cost_before, b.avg_cost_after, b.relation) for b in p.buy_outcomes]  # // legal-ok — Toss enum
            + [("SELL", s.fill, s.avg_cost_before, s.avg_cost_after, s.pnl_pct) for s in p.sell_outcomes],  # // legal-ok — Toss enum
            key=lambda e: e[1].at)
        if not events:
            continue
        track, reentries, gap_days, closed_at = [], 0, None, None
        for side, f, before, after, extra in events:
            if side == "BUY" and closed_at is not None:  # // legal-ok — Toss enum
                reentries += 1
                gap_days = round((f.at - closed_at).total_seconds() / 86400, 1)
                closed_at = None
            if side == "SELL" and after is None:  # // legal-ok — Toss enum
                closed_at = f.at
            track.append({
                "date": f.at.date().isoformat(), "side": side, "price": _f(f.price, 4),
                "qty": _f(f.quantity, 6), "amount_krw": _f(to_krw(f.amount, f.currency, usdkrw), 0),
                "avg_before": _f(before, 4) if before is not None else None,
                "avg_after": _f(after, 4) if after is not None else None,
                "relation": extra if side == "BUY" else None,  # // legal-ok — Toss enum
                "pnl_pct": round(extra, 2) if side == "SELL" else None,  # // legal-ok — Toss enum
            })
        fo = [b for b in p.buy_outcomes if b.follow_on]
        wins = [o for o in p.sell_outcomes if o.pnl_pct > 0]
        h = held.get(sym)
        ct = contrib.get(sym) or {}
        avgs = [t["avg_after"] for t in track if t["avg_after"] is not None]
        c = {
            "symbol": sym, "name": names.get(sym) or (h or {}).get("name") or "", "currency": p.currency,
            "held": sym in held,
            "weight_pct": (h or {}).get("weight_pct"),
            "held_days": (h or {}).get("held_days"),
            "unrealised_rate_pct": (h or {}).get("unrealised_rate_pct"),
            "buys": p.buys, "sells": p.sells,
            "follow_on": {"below": sum(1 for b in fo if b.relation == "below"),
                          "above": sum(1 for b in fo if b.relation == "above"),
                          "flat": sum(1 for b in fo if b.relation == "flat")},
            "closed": len(p.sell_outcomes), "wins": len(wins),
            "win_rate_pct": round(len(wins) / len(p.sell_outcomes) * 100, 1) if p.sell_outcomes else None,
            "median_sell_pct": _med([o.pnl_pct for o in p.sell_outcomes]),
            "realised_krw": ct.get("realised_krw", 0.0), "unrealised_krw": ct.get("unrealised_krw", 0.0),
            "total_krw": ct.get("total_krw", 0.0),
            "fees_krw": _f(to_krw(p.fees, p.currency, usdkrw), 0),
            "reentries": reentries, "gap_days": gap_days,
            "avg_first": avgs[0] if avgs else None,
            "avg_now": _f(p.average_cost, 4) if p.average_cost is not None else (avgs[-1] if avgs else None),
            "oversold": p.oversold,
            "track": track,
        }
        c["note"] = _card_note(c)
        cards.append(c)
    live = sorted([c for c in cards if c["held"]], key=lambda c: -(c["weight_pct"] or 0))
    gone = sorted([c for c in cards if not c["held"]], key=lambda c: -abs(c["total_krw"] or 0))
    shown = (live + gone)[:_CARD_CAP]
    return {"cards": shown, "total": len(cards), "folded": max(0, len(cards) - len(shown)),
            "held_shown": sum(1 for c in shown if c["held"])}


def analyse(*, book: dict, fills: list, holdings_rows: list[dict], usdkrw: Decimal, prices: dict | None, names: dict[str, str]) -> dict:
    held = {r["symbol"] for r in holdings_rows}
    a = attribution(book, holdings_rows, usdkrw, names)
    t = trade_stats(book, usdkrw)
    s = sizing(fills, usdkrw)
    m = by_market(book, holdings_rows, usdkrw)
    after = after_selling(book, held, prices or {}, usdkrw, names)
    tm = timing(fills)
    return {
        "headline": headline(a, t, s, m, after, tm),
        "attribution": a, "trades": t, "after_selling": after, "timing": tm, "sizing": s, "by_market": m,
        "symbols": per_symbol(book, holdings_rows, usdkrw, names, a["rows"]),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
