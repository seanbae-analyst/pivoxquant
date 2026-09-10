"""Position history reconstructed from Toss order fills — pure functions.

Why reconstruct at all
----------------------
``GET /api/v1/holdings`` tells you where the account *is*; it does not tell
you how it got there. Every mirror the product shows (보유기간 · 회전 ·
추가매수 · 손익처분) is a statement about the path, and the path lives only
in ``GET /api/v1/orders?status=CLOSED`` — so we walk every fill since the
start date, in order, and rebuild each position the way Toss itself
values it: **weighted-average cost** (총원가 ÷ 총주식수). That is what
``averagePurchasePrice`` is, so if the walk is complete our average lands
on Toss's to the won, and that agreement is the test we run.

What "complete" means, and why we insist on measuring it
--------------------------------------------------------
A realised P&L is only as good as the cost basis under it. If the first
order we fetched is not the first order the account ever placed — the
window starts too late, an after-hours order the Open API cannot list,
shares transferred in, a corporate action — the running average is wrong
and every "실현" figure built on it is wrong in a way that looks precise.
So :func:`reconcile` compares the rebuilt quantity and average for every
held symbol against what Toss reports, and a report may call its realised
numbers whole only when every line agrees. Anything else is labelled
partial, with the symbols that disagree named.

No judgement leaves this module: quantities, prices, dates, and the sign
of a number. (DECISIONS.md — AI 점수화 폐기.)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from services.toss.report import KST, D

ZERO = Decimal(0)
_QTY_EPS = Decimal("0.000001")
_AVG_TOLERANCE = Decimal("0.005")  # 0.5 % — Toss rounds; we do not
_PRICE_EPS = Decimal("0.0001")     # same-price band for "flat" follow-on buys
_SIDE_IN = "BUY"   # // legal-ok — Toss enum value, compared only
_SIDE_OUT = "SELL"  # // legal-ok — Toss enum value, compared only


@dataclass(frozen=True)
class Fill:
    order_id: str
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal
    amount: Decimal
    commission: Decimal
    tax: Decimal
    currency: str
    at: datetime  # naive, KST wall clock — all rows share the zone, only differences matter


@dataclass
class BuyOutcome:
    fill: Fill
    follow_on: bool              # the position already held shares at this instant
    relation: str | None         # "below" / "above" / "flat" vs the average just before — None when not a follow-on
    avg_cost_before: Decimal | None


@dataclass
class SellOutcome:
    fill: Fill
    avg_cost_before: Decimal
    realised_gross: Decimal      # (price − avg) × qty, before fees
    realised_net: Decimal        # gross − commission − tax
    pnl_pct: float               # (price − avg) / avg × 100
    held_days: float             # from the day the current holding opened to this sell


@dataclass
class PositionHistory:
    symbol: str
    currency: str
    quantity: Decimal = ZERO
    cost: Decimal = ZERO                       # quantity × running average
    buys: int = 0
    sells: int = 0
    first_fill_at: datetime | None = None      # first fill in the fetched window
    opened_at: datetime | None = None          # when the *current* holding went 0 → >0
    last_fill_at: datetime | None = None
    realised_gross: Decimal = ZERO
    fees: Decimal = ZERO
    oversold: bool = False                     # a sale exceeded what the window had bought
    unmatched_sell_qty: Decimal = ZERO         # shares sold with no cost basis here — the size of the hole
    buy_outcomes: list[BuyOutcome] = field(default_factory=list)
    sell_outcomes: list[SellOutcome] = field(default_factory=list)

    @property
    def average_cost(self) -> Decimal | None:
        return (self.cost / self.quantity) if self.quantity > _QTY_EPS else None


def _naive_kst(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(KST).replace(tzinfo=None)


def fills_from_orders(orders: list[dict]) -> list[Fill]:
    """One :class:`Fill` per order record that executed anything, oldest first.

    A record's final status is irrelevant here: the spec says CANCELED /
    REJECTED / REPLACED carry ``execution.filledQuantity`` for the part that
    did execute, and a REPLACED original plus its replacement are two
    records with two disjoint fills — so counting by quantity is exact and
    counting by status would double- or under-count.
    """
    out: list[Fill] = []
    for o in orders:
        ex = o.get("execution") or {}
        qty = D(ex.get("filledQuantity"))
        if qty <= 0 or not o.get("orderedAt"):
            continue
        price = D(ex.get("averageFilledPrice"))
        amount = D(ex.get("filledAmount")) or qty * price
        at = _naive_kst(ex.get("filledAt") or o["orderedAt"])
        out.append(Fill(
            order_id=str(o.get("orderId") or ""), symbol=str(o.get("symbol") or ""), side=str(o.get("side") or ""),
            quantity=qty, price=price, amount=amount, commission=D(ex.get("commission")), tax=D(ex.get("tax")),
            currency=str(o.get("currency") or "KRW"), at=at,
        ))
    out.sort(key=lambda f: (f.at, f.order_id))
    return out


def reconstruct(fills: list[Fill]) -> dict[str, PositionHistory]:
    """Walk fills chronologically and rebuild every position at average cost."""
    book: dict[str, PositionHistory] = {}
    for f in fills:
        p = book.setdefault(f.symbol, PositionHistory(symbol=f.symbol, currency=f.currency))
        p.first_fill_at = p.first_fill_at or f.at
        p.last_fill_at = f.at
        p.fees += f.commission + f.tax
        if f.side == _SIDE_IN:
            if p.quantity <= _QTY_EPS:
                p.opened_at = f.at
                p.cost = ZERO
                p.quantity = ZERO
                p.buy_outcomes.append(BuyOutcome(fill=f, follow_on=False, relation=None, avg_cost_before=None))
            else:
                avg = p.cost / p.quantity
                rel = "flat" if abs(f.price - avg) <= _PRICE_EPS * avg else ("below" if f.price < avg else "above")
                p.buy_outcomes.append(BuyOutcome(fill=f, follow_on=True, relation=rel, avg_cost_before=avg))
            p.quantity += f.quantity
            p.cost += f.quantity * f.price
            p.buys += 1
        elif f.side == _SIDE_OUT:
            p.sells += 1
            if p.quantity <= _QTY_EPS:
                # Selling what the window never bought: the history starts too late.
                p.oversold = True
                p.unmatched_sell_qty += f.quantity
                continue
            avg = p.cost / p.quantity
            qty = f.quantity
            if qty > p.quantity + _QTY_EPS:
                p.oversold = True
                p.unmatched_sell_qty += qty - p.quantity
                qty = p.quantity
            gross = (f.price - avg) * qty
            pct = float((f.price - avg) / avg * 100) if avg > 0 else 0.0
            held = (f.at - p.opened_at).total_seconds() / 86400 if p.opened_at else 0.0
            p.sell_outcomes.append(SellOutcome(
                fill=f, avg_cost_before=avg, realised_gross=gross,
                realised_net=gross - f.commission - f.tax, pnl_pct=pct, held_days=round(held, 1),
            ))
            p.realised_gross += gross
            p.quantity -= qty
            p.cost = avg * p.quantity if p.quantity > _QTY_EPS else ZERO
            if p.quantity <= _QTY_EPS:
                p.quantity = ZERO
                p.opened_at = None
    return book


_COST_TOLERANCE = Decimal("0.01")   # 1 % — a split rounds the per-share figures, not the money
# Which findings put the realised P&L in doubt. A share-count change does not by
# itself: the money that went in is unchanged. It only misvalues a sale that
# straddles the event, which is called out in that finding's own wording.
# "average" belongs here too: the share count agreeing while the money does not
# means our per-share cost is wrong, and every realised figure is measured
# against it.
_REALISED_BREAKING = {"absent", "quantity", "ghost", "unmatched_sales", "average"}


def reconcile(book: dict[str, PositionHistory], holdings_items: list[dict]) -> dict:
    """Compare the rebuilt book with what Toss says the account holds now.

    Every held symbol is checked on two axes — how many shares, and what they
    cost in total — because the two disagree for different reasons and only
    one of them means the money is wrong:

    * **Share count differs, total cost matches.** Nothing entered or left; the
      share count itself was rewritten by a split, a consolidation, or a merger
      conversion, none of which appear in the order history. The realised
      figures survive this, except for a sale that straddles the event, which
      was priced on one scale against an average built on the other.
    * **Both differ.** Shares genuinely entered or left outside this window —
      a purchase before the start date, a transfer in, an order the Open API
      cannot list. The cost basis is wrong and the realised figures with it.

    Returns ``{complete, realised_trustworthy, checked, mismatches[]}`` where
    each mismatch carries a ``kind`` and a sentence naming what to do about it.
    """
    toss = {str(it.get("symbol")): it for it in holdings_items}
    mismatches: list[dict] = []

    def row(sym, rq, tq, ra, ta, **extra):
        return {"symbol": sym, "rebuilt_qty": float(rq), "toss_qty": float(tq),
                "rebuilt_avg": float(ra) if ra is not None else None,
                "toss_avg": float(ta) if ta is not None else None, **extra}

    for sym, it in toss.items():
        tq, ta = D(it.get("quantity")), D(it.get("averagePurchasePrice"))
        p = book.get(sym)
        if p is None:
            mismatches.append(row(sym, ZERO, tq, None, ta, kind="absent",
                                  reason="이력에 이 종목의 체결이 하나도 없음 — 조회 시작일 이전에 산 것. --since 를 넓혀라"))
            continue
        rq, ra = p.quantity, p.average_cost
        if abs(rq - tq) > _QTY_EPS:
            rebuilt_cost, toss_cost = p.cost, tq * ta
            cost_matches = toss_cost > 0 and abs(rebuilt_cost - toss_cost) / toss_cost <= _COST_TOLERANCE
            if cost_matches and rq > _QTY_EPS:
                ratio = rq / tq if tq > 0 else None
                mismatches.append(row(
                    sym, rq, tq, ra, ta, kind="share_count_changed",
                    cost_krw_note=f"{float(rebuilt_cost):,.2f} ≈ {float(toss_cost):,.2f}",
                    ratio=round(float(ratio), 4) if ratio else None,
                    reason=("주식 수가 바뀌었다 (병합·분할·합병 전환) — 취득원가 총액은 "
                            f"{float(rebuilt_cost):,.2f} 대 {float(toss_cost):,.2f} 로 일치하고 수량만 "
                            f"{float(ratio):.4g}:1 로 달라졌다. 들어오거나 나간 주식은 없다. "
                            "다만 이 이벤트를 사이에 두고 낸 매도는 손익이 다른 눈금으로 계산됐을 수 있다"
                            if ratio else "주식 수가 바뀌었다 — 취득원가 총액은 일치한다")))
            else:
                mismatches.append(row(sym, rq, tq, ra, ta, kind="quantity",
                                      reason="수량과 취득원가가 모두 다름 — 이력 밖의 매수·입고가 있다. --since 를 넓혀라"))
        elif ra is not None and ta > 0 and abs(ra - ta) / ta > _AVG_TOLERANCE:
            mismatches.append(row(sym, rq, tq, ra, ta, kind="average",
                                  reason="수량은 맞지만 평균단가가 다름 — 취득 경로가 이력과 다르다"))

    for sym, p in book.items():
        already = {m["symbol"] for m in mismatches}
        if sym not in toss and p.quantity > _QTY_EPS and sym not in already:
            mismatches.append(row(sym, p.quantity, ZERO, p.average_cost, None, kind="ghost",
                                  reason="이력상 보유인데 계좌엔 없음 — 이력에 없는 매도·출고가 있다"))
        if p.oversold and sym not in {m["symbol"] for m in mismatches}:
            mismatches.append(row(sym, p.quantity, D(toss.get(sym, {}).get("quantity")), None, None,
                                  kind="unmatched_sales", unmatched_sell_qty=float(p.unmatched_sell_qty),
                                  reason=(f"취득 기록 없이 판 주식 {float(p.unmatched_sell_qty):g}주 — 조회 시작일 이전 매수가 있다. "
                                          "이 몫의 손익은 계산에서 빠져 있다 (0 으로 취급, 부풀리지 않음)")))

    return {
        "complete": not mismatches,
        "realised_trustworthy": not any(m["kind"] in _REALISED_BREAKING for m in mismatches),
        "checked": len(toss),
        "mismatches": mismatches,
    }


def to_trade_rows(fills: list[Fill], book: dict[str, PositionHistory], names: dict[str, str] | None = None) -> list:
    """Project fills onto the product's ``TradeHistory`` rows so the product's
    own mirrors can run on them unchanged.

    Sale rows carry ``pnl_pct`` / ``pnl`` from :func:`reconstruct`, which is
    what ``fifo_match_closed_trades_with_pnl`` attributes to each closed
    pair. Imported lazily: the model pulls in the Flask extensions, and the
    rest of this module must stay importable without them.
    """
    from models import TradeHistory  # noqa: PLC0415 — see docstring

    names = names or {}
    outcome_by_order = {o.fill.order_id: o for p in book.values() for o in p.sell_outcomes}
    rows = []
    for f in fills:
        o = outcome_by_order.get(f.order_id)
        rows.append(TradeHistory(
            ticker=f.symbol, name=names.get(f.symbol, ""), action=f.side,
            shares=float(f.quantity), price_per_share=float(f.price), total_value=float(f.amount),
            currency=f.currency, traded_at=f.at,
            pnl=float(o.realised_gross) if o else 0.0, pnl_pct=o.pnl_pct if o else 0.0,
        ))
    return rows
