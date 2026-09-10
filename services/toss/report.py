"""PivoxReport — turn one Toss account's raw API payloads into a mirror.

Pure functions. No network, no Flask, no DB: the CLI (``scripts/pivox_report.py``)
fetches, this module computes, and tests feed it the OpenAPI examples.

What the numbers are, and are not
---------------------------------
* Valuation comes from ``GET /api/v1/holdings`` — Toss's own ``marketValue`` and
  ``profitLoss``. We do not re-price anything. The USD→KRW conversion uses
  Toss's display rate (``GET /api/v1/exchange-rate``), refreshed each minute,
  which "may differ from the execution rate" per the API description.
* The holdings endpoint covers KR + US **equities only**. Cash, overseas
  options and bonds are not in it, so "NAV" here means *equity* value.
* Activity comes from ``status=CLOSED`` orders in the window. Toss only lists
  orders placed through order types the Open API supports (지정가·시장가·
  장마감지정가); after-hours single-price orders are invisible to it.
* Realised P&L is **not** computed: a fill's cost basis at the time of sale is
  not in the payload, and guessing it from today's average price would be wrong.

Everything rendered is observational — counts, weights, dates. The report
never says what to do next; that is the product's line, not a style choice.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

KST = timezone(timedelta(hours=9))

# Toss order sides as they appear in the payload. Data labels, not signals.
_SIDE_IN = "BUY"   # // legal-ok — Toss enum value, compared only
_SIDE_OUT = "SELL"  # // legal-ok — Toss enum value, compared only
_FILLED_STATES = {"FILLED", "PARTIAL_FILLED"}
_CANCELLED_STATES = {"CANCELED", "CANCELLED"}
_REJECTED_STATES = {"REJECTED"}

ZERO = Decimal(0)


def D(v) -> Decimal:
    """Toss sends every number as a string (or null). Null → 0."""
    if v is None or v == "":
        return ZERO
    try:
        return Decimal(str(v))
    except InvalidOperation:
        return ZERO


def _pct(part: Decimal, whole: Decimal) -> float | None:
    if whole <= 0:
        return None
    return float((part / whole) * 100)


def _f(v: Decimal | None, places: int = 2) -> float | None:
    return None if v is None else float(round(v, places))


def to_krw(amount: Decimal, currency: str, usdkrw: Decimal) -> Decimal:
    if currency == "KRW":
        return amount
    if currency == "USD":
        return amount * usdkrw
    raise ValueError(f"unsupported currency {currency}")


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


# ── valuation ────────────────────────────────────────────────────────────────
def summarise_holdings(holdings: dict, usdkrw: Decimal) -> dict:
    items = holdings.get("items") or []
    rows = []
    for it in items:
        cur = it.get("currency") or ("KRW" if it.get("marketCountry") == "KR" else "USD")
        mv = D((it.get("marketValue") or {}).get("amount"))
        pa = D((it.get("marketValue") or {}).get("purchaseAmount"))
        pl = it.get("profitLoss") or {}
        rows.append({
            "symbol": it.get("symbol"),
            "name": it.get("name"),
            "market": it.get("marketCountry"),
            "currency": cur,
            "quantity": _f(D(it.get("quantity")), 6),
            "last_price": _f(D(it.get("lastPrice")), 4),
            "avg_purchase_price": _f(D(it.get("averagePurchasePrice")), 4),
            "market_value": _f(mv),
            "market_value_krw": _f(to_krw(mv, cur, usdkrw), 0),
            "purchase_amount_krw": _f(to_krw(pa, cur, usdkrw), 0),
            "unrealised_rate_pct": _f(D(pl.get("rate")) * 100),
            "unrealised_after_cost_rate_pct": _f(D(pl.get("rateAfterCost")) * 100),
            "daily_rate_pct": _f(D((it.get("dailyProfitLoss") or {}).get("rate")) * 100),
        })

    total_krw = sum((Decimal(str(r["market_value_krw"])) for r in rows), ZERO)
    for r in rows:
        r["weight_pct"] = _f(Decimal(str(r["market_value_krw"])) / total_krw * 100) if total_krw > 0 else None
    rows.sort(key=lambda r: r["market_value_krw"] or 0, reverse=True)

    mv_tot = holdings.get("marketValue") or {}
    pl_tot = holdings.get("profitLoss") or {}
    dpl_tot = holdings.get("dailyProfitLoss") or {}
    krw_part = D((mv_tot.get("amount") or {}).get("krw"))
    usd_part = D((mv_tot.get("amount") or {}).get("usd"))
    purchase_krw = D((holdings.get("totalPurchaseAmount") or {}).get("krw")) + D(
        (holdings.get("totalPurchaseAmount") or {}).get("usd")) * usdkrw
    unreal_krw = D((pl_tot.get("amount") or {}).get("krw")) + D((pl_tot.get("amount") or {}).get("usd")) * usdkrw
    daily_krw = D((dpl_tot.get("amount") or {}).get("krw")) + D((dpl_tot.get("amount") or {}).get("usd")) * usdkrw

    valuation = {
        "equity_value_krw": _f(krw_part + usd_part * usdkrw, 0),
        "krw_leg": _f(krw_part, 0),
        "usd_leg": _f(usd_part),
        "usdkrw_rate": _f(usdkrw, 2),
        "purchase_total_krw": _f(purchase_krw, 0),
        "unrealised_krw": _f(unreal_krw, 0),
        "unrealised_rate_pct": _f(D(pl_tot.get("rate")) * 100),
        "unrealised_after_cost_rate_pct": _f(D(pl_tot.get("rateAfterCost")) * 100),
        "daily_krw": _f(daily_krw, 0),
        "daily_rate_pct": _f(D(dpl_tot.get("rate")) * 100),
        "note": "주식 평가액만이다 — 예수금·해외옵션·채권은 holdings 응답에 없다.",
    }
    return {"valuation": valuation, "holdings": rows}


def concentration(rows: list[dict]) -> dict:
    weights = [Decimal(str(r["weight_pct"])) for r in rows if r.get("weight_pct") is not None]
    n = len(weights)
    if n == 0:
        return {"positions": 0, "top1_pct": None, "top3_pct": None, "hhi": None, "kr_pct": None, "us_pct": None,
                "over_30pct": []}
    hhi = sum((w / 100) ** 2 for w in weights)
    by_market: dict[str, Decimal] = defaultdict(lambda: ZERO)
    for r in rows:
        if r.get("weight_pct") is not None:
            by_market[r.get("market") or "?"] += Decimal(str(r["weight_pct"]))
    return {
        "positions": n,
        "top1_pct": _f(weights[0]),
        "top3_pct": _f(sum(weights[:3], ZERO)),
        "hhi": _f(hhi, 3),
        "effective_positions": _f(Decimal(1) / hhi, 1) if hhi > 0 else None,
        "kr_pct": _f(by_market.get("KR", ZERO)),
        "us_pct": _f(by_market.get("US", ZERO)),
        # Same 30% line the in-app concentration alert uses (services/behavior).
        "over_30pct": [r["symbol"] for r in rows if (r.get("weight_pct") or 0) > 30],
    }


# ── activity ─────────────────────────────────────────────────────────────────
def summarise_orders(
    orders: list[dict],
    *,
    holdings_rows: list[dict],
    usdkrw: Decimal,
    equity_value_krw: Decimal,
    window_days: int,
    as_of: date,
) -> dict:
    start = as_of - timedelta(days=window_days)
    avg_price = {r["symbol"]: Decimal(str(r["avg_purchase_price"])) for r in holdings_rows
                 if r.get("avg_purchase_price") is not None}
    held = {r["symbol"] for r in holdings_rows}

    fills_in = fills_out = 0
    amt_in: dict[str, Decimal] = defaultdict(lambda: ZERO)
    amt_out: dict[str, Decimal] = defaultdict(lambda: ZERO)
    cancelled = rejected = 0
    per_symbol = Counter()
    trade_days: set[date] = set()
    follow_on_below_avg: list[dict] = []
    fees_krw = ZERO
    in_window = 0
    first_dt = last_dt = None

    for o in orders:
        dt = _parse_dt(o.get("orderedAt"))
        if dt is None:
            continue
        d = dt.astimezone(KST).date()
        if d < start or d > as_of:
            continue
        in_window += 1
        first_dt = d if first_dt is None or d < first_dt else first_dt
        last_dt = d if last_dt is None or d > last_dt else last_dt
        status = o.get("status")
        if status in _CANCELLED_STATES:
            cancelled += 1
            continue
        if status in _REJECTED_STATES:
            rejected += 1
            continue
        if status not in _FILLED_STATES:
            continue
        ex = o.get("execution") or {}
        qty = D(ex.get("filledQuantity"))
        if qty <= 0:
            continue
        cur = o.get("currency") or "KRW"
        amt = D(ex.get("filledAmount"))
        side = o.get("side")
        sym = o.get("symbol")
        per_symbol[sym] += 1
        trade_days.add(d)
        fees_krw += to_krw(D(ex.get("commission")) + D(ex.get("tax")), cur, usdkrw)
        if side == _SIDE_IN:
            fills_in += 1
            amt_in[cur] += amt
            fill_px = D(ex.get("averageFilledPrice"))
            ref = avg_price.get(sym)
            # A follow-on purchase priced under today's average cost is the
            # closest thing the payload offers to "물타기". It is a proxy: the
            # average moved with this very fill, so read it as a tendency.
            if ref is not None and fill_px > 0 and fill_px < ref:
                follow_on_below_avg.append({
                    "symbol": sym, "date": d.isoformat(), "fill_price": _f(fill_px, 4),
                    "current_avg_price": _f(ref, 4),
                })
        elif side == _SIDE_OUT:
            fills_out += 1
            amt_out[cur] += amt

    traded_krw = sum((to_krw(v, c, usdkrw) for c, v in amt_in.items()), ZERO) + \
        sum((to_krw(v, c, usdkrw) for c, v in amt_out.items()), ZERO)
    weeks = max(Decimal(window_days) / Decimal(7), Decimal(1))
    fills_total = fills_in + fills_out

    return {
        "window_days": window_days,
        "window_from": start.isoformat(),
        "window_to": as_of.isoformat(),
        "orders_in_window": in_window,
        "fills": fills_total,
        "fills_in": fills_in,
        "fills_out": fills_out,
        "cancelled": cancelled,
        "rejected": rejected,
        "fills_per_week": _f(Decimal(fills_total) / weeks, 2),
        "trade_days": len(trade_days),
        "first_trade_date": first_dt.isoformat() if first_dt else None,
        "last_trade_date": last_dt.isoformat() if last_dt else None,
        "bought": {c: _f(v) for c, v in amt_in.items()},
        "sold": {c: _f(v) for c, v in amt_out.items()},
        "traded_krw": _f(traded_krw, 0),
        "turnover_pct_of_equity": _pct(traded_krw, equity_value_krw),
        "fees_krw": _f(fees_krw, 0),
        "most_traded": [{"symbol": s, "fills": n} for s, n in per_symbol.most_common(5)],
        "symbols_traded": len(per_symbol),
        "held_but_untouched": sorted(held - set(per_symbol)),
        "traded_but_not_held": sorted(set(per_symbol) - held),
        "follow_on_buys_below_avg": follow_on_below_avg,
        "note": "실현손익은 계산하지 않는다 — 매도 시점의 취득단가가 응답에 없다.",
    }


# ── assemble ─────────────────────────────────────────────────────────────────
def build_report(
    *,
    account: dict,
    holdings: dict,
    closed_orders: list[dict],
    open_orders: list[dict] | None,
    fx: dict,
    window_days: int = 90,
    as_of: datetime | None = None,
) -> dict:
    as_of = as_of or datetime.now(KST)
    usdkrw = D(fx.get("rate"))
    if usdkrw <= 0:
        raise ValueError("exchange-rate result had no positive rate")
    val = summarise_holdings(holdings, usdkrw)
    conc = concentration(val["holdings"])
    act = summarise_orders(
        closed_orders,
        holdings_rows=val["holdings"],
        usdkrw=usdkrw,
        equity_value_krw=Decimal(str(val["valuation"]["equity_value_krw"])),
        window_days=window_days,
        as_of=as_of.astimezone(KST).date(),
    )
    acct_no = str(account.get("accountNo") or "")
    return {
        "generated_at": as_of.isoformat(timespec="seconds"),
        "source": "Toss Securities Open API (read-only, own account)",
        "account": {
            "account_seq": account.get("accountSeq"),
            "account_no_masked": f"***{acct_no[-4:]}" if len(acct_no) >= 4 else "***",
            "account_type": account.get("accountType"),
        },
        "fx": {"usdkrw": _f(usdkrw, 2), "valid_from": fx.get("validFrom"), "valid_until": fx.get("validUntil")},
        "valuation": val["valuation"],
        "holdings": val["holdings"],
        "concentration": conc,
        "activity": act,
        "open_orders": len(open_orders or []),
        "limits": [
            "holdings 는 KR·US 주식만 — 예수금·옵션·채권 제외",
            "환율은 토스 표시환율(1분 갱신), 체결환율과 다를 수 있음",
            "Open API 미지원 호가(시간외단일가 등)로 낸 주문은 목록에 안 나옴",
            "실현손익 미계산 (매도 시점 취득단가 부재)",
        ],
    }


# ── render ───────────────────────────────────────────────────────────────────
def _won(v) -> str:
    return "—" if v is None else f"₩{int(round(v)):,}"


def _px(v) -> str:
    """Prices: KR tickers are whole won, US tickers carry cents. Trim trailing zeros."""
    if v is None:
        return "—"
    return f"{v:,.0f}" if float(v).is_integer() else f"{v:,.4f}".rstrip("0").rstrip(".")


def _usd(v) -> str:
    return "—" if v is None else f"${v:,.2f}"


def _p(v) -> str:
    return "—" if v is None else f"{v:+.2f}%"


def _n(v) -> str:
    return "—" if v is None else f"{v:.2f}%"


def render_markdown(rep: dict) -> str:
    v, c, a = rep["valuation"], rep["concentration"], rep["activity"]
    L = [
        f"# PivoxReport — 토스증권 계좌 {rep['account']['account_no_masked']}",
        "",
        f"생성 {rep['generated_at']} · 출처 {rep['source']} · USD/KRW {rep['fx']['usdkrw']}",
        "",
        "## 평가",
        "",
        "| 항목 | 값 |",
        "|---|---|",
        f"| 주식 평가액 (KRW 환산) | {_won(v['equity_value_krw'])} |",
        f"| ├ 국내 (KRW) | {_won(v['krw_leg'])} |",
        f"| └ 해외 (USD) | {_usd(v['usd_leg'])} |",
        f"| 매입 총액 (KRW 환산) | {_won(v['purchase_total_krw'])} |",
        f"| 미실현 손익 | {_won(v['unrealised_krw'])} ({_p(v['unrealised_rate_pct'])}, 비용 차감 {_p(v['unrealised_after_cost_rate_pct'])}) |",
        f"| 오늘 | {_won(v['daily_krw'])} ({_p(v['daily_rate_pct'])}) |",
        "",
        f"> {v['note']}",
        "",
        "## 보유",
        "",
        "| 종목 | 시장 | 수량 | 현재가 | 평단 | 평가액(₩) | 비중 | 손익률 |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rep["holdings"]:
        L.append(
            f"| {r['symbol']} {r['name'] or ''} | {r['market']} | {r['quantity']:g} | {_px(r['last_price'])} | "
            f"{_px(r['avg_purchase_price'])} | {_won(r['market_value_krw'])} | {_n(r['weight_pct'])} | {_p(r['unrealised_rate_pct'])} |"
        )
    if not rep["holdings"]:
        L.append("| (보유 종목 없음) | | | | | | | |")
    L += [
        "",
        "## 집중도",
        "",
        f"- 종목 수 {c['positions']} · 상위 1종목 {_n(c['top1_pct'])} · 상위 3종목 {_n(c['top3_pct'])}",
        f"- HHI {c['hhi'] if c['hhi'] is not None else '—'} (유효 종목 수 {c.get('effective_positions') or '—'})",
        f"- 국내 {_n(c['kr_pct'])} / 해외 {_n(c['us_pct'])}",
    ]
    if c["over_30pct"]:
        L.append(f"- 30% 초과 종목: {', '.join(c['over_30pct'])}")
    L += [
        "",
        f"## 최근 {a['window_days']}일 활동 ({a['window_from']} ~ {a['window_to']})",
        "",
        f"- 체결 {a['fills']}건 (매수 {a['fills_in']} · 매도 {a['fills_out']}) · 취소 {a['cancelled']} · 거부 {a['rejected']} · 미체결 대기 {rep['open_orders']}",
        f"- 주당 체결 {a['fills_per_week']}건 · 거래일 {a['trade_days']}일 · 거래 종목 {a['symbols_traded']}개",
        f"- 거래대금 {_won(a['traded_krw'])} = 평가액의 {_n(a['turnover_pct_of_equity'])} · 수수료+세금 {_won(a['fees_krw'])}",
    ]
    if a["most_traded"]:
        L.append("- 가장 자주 체결된 종목: " + ", ".join(f"{m['symbol']}({m['fills']})" for m in a["most_traded"]))
    if a["held_but_untouched"]:
        L.append(f"- 보유 중이지만 이 기간 손대지 않은 종목: {', '.join(a['held_but_untouched'])}")
    if a["traded_but_not_held"]:
        L.append(f"- 이 기간 거래했지만 지금은 없는 종목: {', '.join(a['traded_but_not_held'])}")
    if a["follow_on_buys_below_avg"]:
        L.append(f"- 평단 아래에서 추가 매수한 체결 {len(a['follow_on_buys_below_avg'])}건: "
                 + ", ".join(f"{x['symbol']} {x['date']}" for x in a["follow_on_buys_below_avg"][:8]))
    L += ["", f"> {a['note']}", "", "## 이 숫자가 말하지 않는 것", ""]
    L += [f"- {x}" for x in rep["limits"]]
    L += ["", "_기록을 되비추는 거울이다. 다음에 무엇을 할지는 여기 없다._", ""]
    return "\n".join(L)
