"""PivoxReport v2 — the product's mirrors, held up to one real account.

v1 (:mod:`services.toss.report`) rearranged the holdings payload and
summarised a window of orders on its own terms. Running it on a live
account showed what the payload actually supports and what the product
already knows how to say. v2 keeps v1's valuation and concentration
helpers and replaces the activity section with the product's own mirrors,
computed by the product's own functions over the account's full history:

* 회전 — :func:`services.behavior.turnover_mirror.compute_turnover_mirror`
* 추가매수 — :func:`services.behavior.averaging_down_mirror.compute_averaging_down_mirror`
* 손익처분 — :func:`services.behavior.profit_loss_mirror.compute_profit_loss_mirror`

"전체 이력" runs those three functions unchanged, so that block says
exactly what the product would say about this account. "최근 N일" is
computed here from the rebuilt book instead: the product functions treat
their window as the whole world (a follow-on buy whose first lot predates
the window reads as an opening buy; a sell whose lot predates the window
drops out of the profit/loss pairs), which is right for a cohort scan and
wrong for one person's recent stretch. The recent block therefore keeps
the full-history cost basis and simply restricts *which fills* it counts
to the window, anchored on today rather than on the last trade. The two
blocks share vocabulary and shape so the reader can lay them side by side. Positions are rebuilt by :mod:`services.toss.history`, and the
report says in its first lines whether that rebuild agrees with Toss's
own holdings; realised figures are called whole only when it does.

Things v1 printed that v2 does not: an HHI, a turnover-as-percent-of-
equity, and any word that grades a pattern. The product's mirrors emit
counts, days, and percentages of *return*, never a ratio that scores the
person; this report follows them.
"""
from __future__ import annotations

import statistics
from datetime import datetime, timedelta
from decimal import Decimal

from services.behavior.averaging_down_mirror import compute_averaging_down_mirror
from services.behavior.profit_loss_mirror import compute_profit_loss_mirror
from services.behavior.turnover_mirror import compute_turnover_mirror
from services.profile.fifo_util import fifo_open_position_ages
from services.toss.analysis import analyse, asymmetry_phrase
from services.toss.history import fills_from_orders, reconcile, reconstruct, to_trade_rows
from services.toss.report import KST, D, _f, _n, _p, _px, _usd, _won, summarise_holdings, to_krw

_MIN = {"min_trades": 1, "min_follow_on": 1, "min_pairs": 1}  # a personal report has n=1; the product's floors are for cohorts


def _concentration(rows: list[dict]) -> dict:
    """Largest holding's share of equity value, count, and the 30 % line —
    the same three facts the in-app concentration mirror surfaces. No index."""
    weights = [(r["symbol"], r.get("name"), r.get("weight_pct")) for r in rows if r.get("weight_pct") is not None]
    if not weights:
        return {"positions": 0, "largest": None, "over_30pct": [], "kr_pct": None, "us_pct": None}
    sym, name, w = weights[0]
    kr = sum(r["weight_pct"] for r in rows if r.get("market") == "KR" and r.get("weight_pct") is not None)
    return {
        "positions": len(weights),
        "largest": {"symbol": sym, "name": name, "weight_pct": w},
        "over_30pct": [s for s, _, x in weights if x > 30],
        "kr_pct": _f(Decimal(str(kr))),
        "us_pct": _f(Decimal(str(100 - kr))),
    }


def _window_block(book: dict, *, window_days: int, as_of_naive: datetime) -> dict:
    """Same shape as the product mirrors, computed on the rebuilt book for
    fills inside ``[as_of − window_days, as_of]``. See module docstring."""
    start = as_of_naive - timedelta(days=window_days)
    buys = [b for p in book.values() for b in p.buy_outcomes if start <= b.fill.at <= as_of_naive]
    sells = [s for p in book.values() for s in p.sell_outcomes if start <= s.fill.at <= as_of_naive]
    gross: dict[str, Decimal] = {}
    for o in buys + sells:
        gross[o.fill.currency] = gross.get(o.fill.currency, Decimal(0)) + o.fill.amount
    holds = [s.held_days for s in sells]
    n = len(buys) + len(sells)
    turnover = {
        "sufficient_data": n > 0, "period_days": window_days,
        "trade_count": n, "buy_count": len(buys), "sell_count": len(sells),
        "by_currency": [{"currency": c, "gross_value": float(v), "trade_count": sum(1 for o in buys + sells if o.fill.currency == c)}
                        for c, v in sorted(gross.items(), key=lambda kv: (-kv[1], kv[0]))],
        "median_hold_days": round(statistics.median(holds), 1) if holds else None,
        "mean_hold_days": round(statistics.fmean(holds), 1) if holds else None,
    }
    fo = [b for b in buys if b.follow_on]
    follow_on = {
        "sufficient_data": bool(fo), "period_days": window_days,
        "follow_on_count": len(fo) if fo else None,
        "below_avg_count": sum(1 for b in fo if b.relation == "below") if fo else None,
        "above_avg_count": sum(1 for b in fo if b.relation == "above") if fo else None,
        "flat_count": sum(1 for b in fo if b.relation == "flat") if fo else None,
        "by_ticker": [],
    }
    tp = [s for s in sells if s.pnl_pct > 0]
    sl = [s for s in sells if s.pnl_pct < 0]

    def side(xs, key):
        if not xs:
            return None
        return {"count": len(xs),
                "median_hold_days": round(statistics.median([x.held_days for x in xs]), 1),
                "mean_hold_days": round(statistics.fmean([x.held_days for x in xs]), 1),
                f"median_{key}_pct": round(statistics.median([x.pnl_pct for x in xs]), 2),
                f"mean_{key}_pct": round(statistics.fmean([x.pnl_pct for x in xs]), 2)}
    profit_loss = {
        "sufficient_data": bool(tp or sl), "one_sided": bool(tp) != bool(sl),
        "total_closed_pairs": len(sells), "take_profit": side(tp, "gain"), "stop_loss": side(sl, "loss"),
    }
    return {"turnover": turnover, "follow_on": follow_on, "profit_loss": profit_loss}


def _mirrors(trade_rows: list, book: dict, *, window_days: int, as_of_naive: datetime) -> dict:
    ages = fifo_open_position_ages(trade_rows, reference_time=as_of_naive)
    return {
        "window": _window_block(book, window_days=window_days, as_of_naive=as_of_naive),
        "all": {
            "turnover": compute_turnover_mirror(trade_rows, period_days=None, min_trades=_MIN["min_trades"]),
            "follow_on": compute_averaging_down_mirror(trade_rows, period_days=None, min_follow_on=_MIN["min_follow_on"]),
            "profit_loss": compute_profit_loss_mirror(trade_rows, period_days=None, min_pairs=_MIN["min_pairs"]),
        },
        "open_lot_ages_days": {"median": round(statistics.median(ages), 1) if ages else None,
                               "oldest": round(max(ages), 1) if ages else None, "lots": len(ages)},
    }


def _holding_histories(book: dict, holdings_rows: list[dict], as_of_naive: datetime) -> list[dict]:
    out = []
    for r in holdings_rows:
        p = book.get(r["symbol"])
        opened = p.opened_at if p else None
        out.append({
            **{k: r[k] for k in ("symbol", "name", "market", "currency", "quantity", "avg_purchase_price",
                                 "market_value_krw", "weight_pct", "unrealised_rate_pct")},
            "opened_at": opened.date().isoformat() if opened else None,
            "held_days": (as_of_naive - opened).days if opened else None,
            "buys": p.buys if p else 0,
            "sells": p.sells if p else 0,
            "last_fill_at": p.last_fill_at.date().isoformat() if p and p.last_fill_at else None,
            "rebuilt_avg": _f(p.average_cost, 4) if p and p.average_cost is not None else None,
        })
    return out


def _departed(book: dict, held: set[str], names: dict[str, str], usdkrw: Decimal) -> list[dict]:
    out = []
    for sym, p in book.items():
        if sym in held or not p.sell_outcomes:
            continue
        net = sum((o.realised_net for o in p.sell_outcomes), Decimal(0))
        gross = sum((o.realised_gross for o in p.sell_outcomes), Decimal(0))
        out.append({
            "symbol": sym, "name": names.get(sym, ""), "currency": p.currency,
            "first_fill_at": p.first_fill_at.date().isoformat() if p.first_fill_at else None,
            "last_fill_at": p.last_fill_at.date().isoformat() if p.last_fill_at else None,
            "buys": p.buys, "sells": p.sells,
            "realised_gross": _f(gross), "realised_net": _f(net),
            "realised_net_krw": _f(to_krw(net, p.currency, usdkrw), 0),
            "median_sell_pct": round(statistics.median([o.pnl_pct for o in p.sell_outcomes]), 2),
            "oversold": p.oversold,
        })
    out.sort(key=lambda d: d["last_fill_at"] or "", reverse=True)
    return out


def build_mirror_report(
    *,
    account: dict,
    holdings: dict,
    closed_orders: list[dict],
    open_orders: list[dict] | None,
    fx: dict,
    history_since: str | None,
    window_days: int = 90,
    names: dict[str, str] | None = None,
    prices: dict[str, dict] | None = None,
    as_of: datetime | None = None,
) -> dict:
    as_of = as_of or datetime.now(KST)
    as_of_naive = as_of.astimezone(KST).replace(tzinfo=None)
    usdkrw = D(fx.get("rate"))
    if usdkrw <= 0:
        raise ValueError("exchange-rate result had no positive rate")

    val = summarise_holdings(holdings, usdkrw)
    names = {**{r["symbol"]: r["name"] for r in val["holdings"] if r.get("name")}, **(names or {})}

    fills = fills_from_orders(closed_orders)
    book = reconstruct(fills)
    recon = reconcile(book, holdings.get("items") or [])
    trade_rows = to_trade_rows(fills, book, names)
    held = {r["symbol"] for r in val["holdings"]}

    realised_net_total = sum((to_krw(sum((o.realised_net for o in p.sell_outcomes), Decimal(0)), p.currency, usdkrw)
                              for p in book.values()), Decimal(0))
    acct_no = str(account.get("accountNo") or "")
    return {
        "version": 2,
        "generated_at": as_of.isoformat(timespec="seconds"),
        "source": "Toss Securities Open API (read-only, own account)",
        "account": {"account_seq": account.get("accountSeq"),
                    "account_no_masked": f"***{acct_no[-4:]}" if len(acct_no) >= 4 else "***",
                    "account_type": account.get("accountType")},
        "fx": {"usdkrw": _f(usdkrw, 2), "valid_until": fx.get("validUntil")},
        "history": {
            "since": history_since,
            "first_fill_at": fills[0].at.date().isoformat() if fills else None,
            "fills": len(fills),
            "complete": recon["complete"],
            "realised_trustworthy": recon["realised_trustworthy"],
            "checked_symbols": recon["checked"],
            "mismatches": recon["mismatches"],
            "realised_net_krw": _f(realised_net_total, 0),
            "realised_scope": (
                "전체" if recon["complete"]
                else "전체 — 주식 수 변경은 취득원가를 바꾸지 않는다" if recon["realised_trustworthy"]
                else "부분 — 아래 종목은 취득원가가 이력 밖에 있어 그 몫이 빠져 있다"
            ),
        },
        "valuation": val["valuation"],
        "concentration": _concentration(val["holdings"]),
        "mirrors": _mirrors(trade_rows, book, window_days=window_days, as_of_naive=as_of_naive),
        "window_days": window_days,
        "holdings": _holding_histories(book, val["holdings"], as_of_naive),
        "departed": _departed(book, held, names, usdkrw),
        # Every fill, for the timeline chart: purchases and sales as they happened.
        "fills_for_chart": [
            {"symbol": f.symbol, "date": f.at.date().isoformat(), "side": "in" if f.side == "BUY" else "out",  # // legal-ok — Toss enum, compared only
             "qty": float(f.quantity), "price": float(f.price),
             "pnl_pct": next((round(o.pnl_pct, 2) for pp in book.values() for o in pp.sell_outcomes if o.fill.order_id == f.order_id), None)}
            for f in fills
        ],
        "open_orders": len(open_orders or []),
        "analysis": analyse(book=book, fills=fills, holdings_rows=val["holdings"], usdkrw=usdkrw, prices=prices, names=names),
        "limits": [
            "평가액은 KR·US 주식만 — 예수금·옵션·채권은 holdings 응답에 없음",
            "환율은 토스 표시환율(1분 갱신), 체결환율과 다를 수 있음",
            "Open API 미지원 호가(시간외단일가 등)로 낸 주문은 이력에 안 나옴 — 불일치가 생기는 흔한 원인",
            "실현손익은 평균단가법 재구성값 — 토스 앱의 세후 실현손익과 다를 수 있음",
        ],
    }


# ── render ───────────────────────────────────────────────────────────────────
def _days(v) -> str:
    return "—" if v is None else f"{v:g}일"


def _nm(sym: str, name: str | None) -> str:
    return f"{name} ({sym})" if name and name != sym else sym


def _mirror_block(m: dict, label: str) -> list[str]:
    t, fo, pl = m["turnover"], m["follow_on"], m["profit_loss"]
    L = [f"**{label}**", ""]
    if t["sufficient_data"]:
        by_cur = " · ".join(f"{c['currency']} {c['gross_value']:,.0f}" if c["currency"] == "KRW" else f"{c['currency']} {c['gross_value']:,.2f}"
                            for c in t["by_currency"])
        L.append(f"- 체결 {t['trade_count']}건 (매수 {t['buy_count']} · 매도 {t['sell_count']}) · 거래대금 {by_cur}")
        L.append(f"- 매수→매도까지 보유: 중앙값 {_days(t['median_hold_days'])} · 평균 {_days(t['mean_hold_days'])}")
    else:
        L.append("- 체결 없음")
    if fo["sufficient_data"]:
        L.append(f"- 이미 보유한 종목을 추가 매수 {fo['follow_on_count']}건: 평균단가보다 낮게 {fo['below_avg_count']} · 높게 {fo['above_avg_count']} · 같게 {fo['flat_count']}")
    else:
        L.append("- 추가 매수 없음")
    if pl["sufficient_data"]:
        tp, sl = pl["take_profit"], pl["stop_loss"]
        if tp:
            L.append(f"- 이익을 실현한 매도 {tp['count']}건: 보유 중앙값 {_days(tp['median_hold_days'])} · 수익률 중앙값 {tp['median_gain_pct']:+.2f}%")
        if sl:
            L.append(f"- 손실을 실현한 매도 {sl['count']}건: 보유 중앙값 {_days(sl['median_hold_days'])} · 수익률 중앙값 {sl['median_loss_pct']:+.2f}%")
        if pl["one_sided"]:
            L.append("- 매도가 한쪽으로만 있음 — 반대쪽은 이 기간에 없었다")
    else:
        L.append("- 매수→매도로 닫힌 거래 없음")
    L.append("")
    return L


def _mismatch_qty(mm: dict) -> str:
    """The number that actually matters for this finding — not always a pair of
    share counts (for an unmatched sale, both sides are zero and say nothing)."""
    if mm["kind"] in ("unmatched_sales", "fractional_dust"):
        return f"{mm.get('unmatched_sell_qty', 0):g}주"
    if mm["kind"] == "absent":
        return f"토스 {mm['toss_qty']:g}주"
    return f"이력 {mm['rebuilt_qty']:g}주 / 토스 {mm['toss_qty']:g}주"


def _analysis_markdown(an: dict) -> list[str]:
    if not an:
        return []
    a, t, af, tm, sz = an["attribution"], an["trades"], an["after_selling"], an["timing"], an["sizing"]
    L = ["", "## 분석", ""]
    L += [f"**{i + 1}. {line}**" for i, line in enumerate(an["headline"])] or ["- 분석할 닫힌 거래가 없다"]
    L += ["", "### 손익 분해", "",
          f"- 실현 {_won(a['realised_krw'])} + 미실현 {_won(a['unrealised_krw'])} = {_won(a['total_krw'])} · 수수료+세금 {_won(a['fees_krw'])}"
          + (f" (실현 손익 총액 대비 {a['fee_share_of_gross_pct']:.1f}%)" if a.get("fee_share_of_gross_pct") is not None else "")]
    if a["rows"]:
        L.append("- 가장 벌어준 종목: " + ", ".join(f"{_nm(r['symbol'], r['name'])} {_won(r['total_krw'])}" for r in a["top"]))
        L.append("- 가장 까먹은 종목: " + ", ".join(f"{_nm(r['symbol'], r['name'])} {_won(r['total_krw'])}" for r in a["bottom"]))
    if t.get("closed"):
        L += ["", "### 닫힌 거래", "",
              f"- {t['closed']}건 · 이익 {t['wins']} / 손실 {t['losses']} · 승률 {t['win_rate_pct']}%",
              f"- 이길 때 중앙값 {t['median_win_pct']:+.2f}% · 질 때 {t['median_loss_pct']:+.2f}% · 이익/손실 크기 비 {t['payoff_ratio'] or '—'}",
              f"- 거래당 기대값 {_won(t['expectancy_krw'])} · 거래당 중앙값 {_won(t['median_trade_krw'])}",
              f"- 이익 거래 보유 중앙값 {_days(t['win_hold_median_days'])} · 손실 거래 {_days(t['loss_hold_median_days'])}"
              + (f" · {asymmetry_phrase(t['hold_asymmetry'])}" if t.get("hold_asymmetry") else ""),
              f"- 최고 {t['best']['symbol']} {t['best']['date']} {_won(t['best']['realised_krw'])} ({t['best']['pnl_pct']:+.2f}%) · 최저 {t['worst']['symbol']} {t['worst']['date']} {_won(t['worst']['realised_krw'])} ({t['worst']['pnl_pct']:+.2f}%)"]
    L += ["", "### 팔고 난 뒤", ""]
    if af.get("available") and af.get("count"):
        L += [f"- 정리한 {af['count']}종목 중 지금 가격이 판 가격보다 높은 것 {af['higher_now']} · 낮은 것 {af['lower_now']} · 이후 변화 중앙값 {af['median_since_sale_pct']:+.2f}%",
              f"- 판 수량을 그대로 들고 있었다면 지금 {_won(af['kept_delta_krw'])} 차이",
              "", "| 종목 | 마지막 매도 | 평균 매도가 | 지금 | 이후 | 안 팔았다면 |", "|---|---|---:|---:|---:|---:|"]
        L += [f"| {_nm(r['symbol'], r['name'])} | {r['last_sold_at']} | {_px(r['avg_sell_price'])} | {_px(r['price_now'])} | {_p(r['since_sale_pct'])} | {_won(r['kept_delta_krw'])} |" for r in af["rows"]]
    else:
        L.append("- 현재가를 받지 못해 건너뜀")
    if tm.get("fills"):
        wd = " · ".join(f"{x['day']} {x['fills']}" for x in tm["by_weekday"] if x["fills"])
        peak = sorted(tm["by_hour"], key=lambda x: -x["fills"])[:3]
        L += ["", "### 언제 사고파나", "",
              f"- 요일: {wd}",
              "- 시간대(KST) 상위: " + " · ".join(f"{x['hour']:02d}시 {x['fills']}건" for x in peak if x["fills"]),
              f"- 거래일 {tm['trade_days']}일 · 하루 평균 {tm['fills_per_trade_day']}건 · 3건 이상인 날 {tm['days_with_3plus']}일 · 최다 {tm['busiest_day']['date']} {tm['busiest_day']['fills']}건"
              + (f" · 국내 체결 중 개장 첫 시간 {tm['kr_first_hour_pct']}%" if tm.get("kr_first_hour_pct") is not None else "")
              + (f" · 해외 체결 중 정규장 야간 {tm['us_regular_night_pct']}%" if tm.get("us_regular_night_pct") is not None else "")]
    if sz.get("buys"):
        L += ["", "### 한 번에 얼마나 사나", "",
              f"- 매수 {sz['buys']}건 · 중앙값 {_won(sz['median_buy_krw'])} · 평균 {_won(sz['mean_buy_krw'])} · 최대 {_won(sz['largest_buy_krw'])} (전체의 {sz['largest_share_pct']}%) · 편차/평균 {sz['cv']}"]
    L += ["", "### 국내 vs 해외", "", "| | 종목 | 닫힌 거래 | 승률 | 보유 중앙값 | 실현 | 미실현 | 합계 |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    L += [f"| {m['market']} | {m['symbols']} | {m['closed']} | {_n(m['win_rate_pct'])} | {_days(m['median_hold_days'])} | {_won(m['realised_krw'])} | {_won(m['unrealised_krw'])} | {_won(m['total_krw'])} |" for m in an["by_market"]]
    return L


def render_mirror_markdown(rep: dict) -> str:
    v, c, h, m = rep["valuation"], rep["concentration"], rep["history"], rep["mirrors"]
    L = [
        f"# PivoxReport — 토스증권 계좌 {rep['account']['account_no_masked']}",
        "",
        f"생성 {rep['generated_at']} · {rep['source']} · USD/KRW {rep['fx']['usdkrw']}",
        "",
        "## 이 리포트가 딛고 선 이력",
        "",
        f"- 주문 이력 조회 시작 {h['since'] or '전체'} · 첫 체결 {h['first_fill_at'] or '—'} · 체결 {h['fills']}건",
    ]
    if h["complete"]:
        L.append(f"- 이력으로 되짚은 보유 {h['checked_symbols']}종목의 수량·평균단가가 **토스 잔고와 전부 일치** — 아래 실현손익은 전체 이력 기준이다")
    else:
        verdict = "실현손익은 그대로 신뢰할 수 있다" if h.get("realised_trustworthy") else f"실현손익은 {h['realised_scope']}"
        L.append(f"- 이력으로 되짚은 결과가 토스 잔고와 **{len(h['mismatches'])}종목에서 다르다** — {verdict}")
        for mm in h["mismatches"]:
            L.append(f"  - **{mm['symbol']}** ({_mismatch_qty(mm)}): {mm['reason']}")
    L += [
        "",
        "## 평가",
        "",
        "| 항목 | 값 |",
        "|---|---|",
        f"| 주식 평가액 (KRW 환산) | {_won(v['equity_value_krw'])} |",
        f"| ├ 국내 (KRW) | {_won(v['krw_leg'])} |",
        f"| └ 해외 (USD) | {_usd(v['usd_leg'])} |",
        f"| 매입 총액 (KRW 환산) | {_won(v['purchase_total_krw'])} |",
        f"| 미실현 손익 | {_won(v['unrealised_krw'])} ({_p(v['unrealised_rate_pct'])}) |",
        f"| 실현 손익 누계 (이력 기준, 수수료·세금 차감) | {_won(h['realised_net_krw'])} · {h['realised_scope'].split(' — ')[0]} |",
        f"| 오늘 | {_won(v['daily_krw'])} ({_p(v['daily_rate_pct'])}) |",
        "",
        "## 거울",
        "",
        f"같은 잣대를 최근 {rep['window_days']}일과 전체 이력에 나란히 댄다. 두 블록이 다르면 최근이 평소와 다른 것이다. "
        "최근 블록의 평균단가·보유일은 전체 이력을 딛고 계산한다.",
        "",
    ]
    L += _mirror_block(m["window"], f"최근 {rep['window_days']}일")
    L += _mirror_block(m["all"], "전체 이력")
    ages = m["open_lot_ages_days"]
    if ages["lots"]:
        L.append(f"- 지금 들고 있는 매수분 {ages['lots']}건의 나이: 중앙값 {_days(ages['median'])} · 가장 오래된 것 {_days(ages['oldest'])}")
        L.append("")
    L += [
        "## 집중",
        "",
    ]
    if c["largest"]:
        L.append(f"- 보유 {c['positions']}종목 · 가장 큰 종목 {_nm(c['largest']['symbol'], c['largest']['name'])} {c['largest']['weight_pct']:.2f}% · 국내 {c['kr_pct']:.2f}% / 해외 {c['us_pct']:.2f}%")
        L.append(f"- 30% 선을 넘는 종목: {', '.join(c['over_30pct']) if c['over_30pct'] else '없음'}")
    else:
        L.append("- 보유 종목 없음")
    L += [
        "",
        "## 보유 종목의 이력",
        "",
        "| 종목 | 보유 시작 | 보유일 | 매수/매도 | 마지막 체결 | 수량 | 평단 | 비중 | 손익률 |",
        "|---|---|---:|---:|---|---:|---:|---:|---:|",
    ]
    for r in rep["holdings"]:
        L.append(f"| {_nm(r['symbol'], r['name'])} | {r['opened_at'] or '이력 밖'} | {_days(r['held_days'])} | {r['buys']}/{r['sells']} | "
                 f"{r['last_fill_at'] or '—'} | {r['quantity']:g} | {_px(r['avg_purchase_price'])} | {r['weight_pct']:.2f}% | {_p(r['unrealised_rate_pct'])} |")
    if not rep["holdings"]:
        L.append("| (없음) | | | | | | | | |")
    L += ["", "## 떠난 종목", ""]
    if rep["departed"]:
        L += ["| 종목 | 처음 | 마지막 | 매수/매도 | 실현손익 (수수료·세금 차감) | 매도 수익률 중앙값 |", "|---|---|---|---:|---:|---:|"]
        for d in rep["departed"]:
            amt = _won(d["realised_net_krw"]) if d["currency"] == "KRW" else f"{_usd(d['realised_net'])} ≈ {_won(d['realised_net_krw'])}"
            flag = " (이력 불완전)" if d["oversold"] else ""
            L.append(f"| {_nm(d['symbol'], d['name'])}{flag} | {d['first_fill_at']} | {d['last_fill_at']} | {d['buys']}/{d['sells']} | {amt} | {d['median_sell_pct']:+.2f}% |")
    else:
        L.append("- 이 이력 안에서 완전히 정리한 종목 없음")
    L += _analysis_markdown(rep.get("analysis") or {})
    L += ["", "## 이 숫자가 말하지 않는 것", ""]
    L += [f"- {x}" for x in rep["limits"]]
    L += ["", "_기록을 되비추는 거울이다. 다음에 무엇을 할지는 여기 없다._", ""]
    return "\n".join(L)
