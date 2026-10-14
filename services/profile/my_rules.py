"""내 규칙 — 온보딩에서 스스로 말한 선을, 자기 거래로만 되비추는 거울.

2026-10-14. The /mirror radar compares a 9-axis declared shape with a 9-axis
observed shape. That is honest but abstract: nobody reads "회전율 ↑12%p" as
"I said I trade at most 5 times a month and this month I traded 7". This
module turns the V3 onboarding answers the user already gave
(``InvestmentProfile.onboarding_answers_json``) into plain lines and counts,
from the user's own rows only, whether each line held.

What it is (and is not)
-----------------------
* **The user's own line, not ours.** Every threshold comes from the bucket
  the user picked in onboarding (``services/profile/questionnaire.py``). We
  never suggest a number. Changing a line = answering the five questions
  again (``/onboarding?retake=1``), the existing path.
* **A fact, not a verdict.** Each rule reports where the record sits against
  the user's line — 선 안 / 선 밖 — with the raw counts. No score, no grade,
  no streak, no "지키세요". Within-vs-outside is arithmetic on the user's own
  number, the same comparison the /mirror gap already makes on buckets.
* **No market data.** Trade rows and the open-position count only — the same
  rule as ``services/behavior/*`` (CLAUDE.md §핵심 3축). That is also why the
  −10% answer is shown but never counted: without prices there is no way to
  know which week fell 10%.

Pure functions. The route reads the rows and passes ``now``; nothing here
touches the DB, the network or the clock, so every branch is testable.

Units
-----
* Fill = one ``TradeHistory`` row of either side, excluding the rows a
  holding-registration path wrote (``fifo_util.is_registration_row``) —
  the same "recorded fill" unit as the turnover mirror.
* Month = calendar month in KST (``traded_at`` is naive UTC; KST has no DST,
  so a fixed +9h is exact — same convention as ``pre_trade/friction_outcome``).
* Hold = one observation per 매도 (``fifo_util.collapse_pairs_by_sell``), in
  days. A 매도 whose lots were all registration seeds carries no purchase
  date and is skipped, as in the holding mirror.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable

from services.profile.fifo_util import (
    collapse_pairs_by_sell,
    fifo_match_closed_trades_with_pnl,
    is_registration_row,
)

_KST = timedelta(hours=9)
_FILL_SIDES = frozenset({"BUY", "SELL"})  # // legal-ok — TradeHistory.action values, compared only

# How many calendar months the frequency rule shows (current one included).
MONTHS_SHOWN = 6
# Window for the holding rule — sells are sparse, a month says too little.
HOLD_WINDOW_DAYS = 90

# ── declared_frequency → monthly ceiling (fills / month) ─────────────────
# The upper end of the bucket the user picked ("3~5번" → 5). Trading LESS
# than the bucket is not counted as crossing the line: the question asked how
# often they trade, and the line people hold themselves to is the ceiling.
# "40번 이상" has no ceiling to cross.
FREQUENCY_CEILING: dict[str, int | None] = {
    "rare": 2,
    "few": 5,
    "moderate": 15,
    "frequent": 40,
    "daily": None,
}

# ── declared_holding → hold range in days, [lo, hi) ──────────────────────
# Natural day edges of the answer labels (하루 안 / 며칠 / 몇 주 / 몇 달 /
# 1년 이상). These are shown to the user in days, so they use calendar edges
# rather than the radar's log-scale buckets.
HOLD_RANGE_DAYS: dict[str, tuple[float, float | None]] = {
    "intraday": (0.0, 1.0),
    "days": (1.0, 7.0),
    "weeks": (7.0, 30.0),
    "months": (30.0, 365.0),
    "years": (365.0, None),
}

_HOLD_LINE: dict[str, str] = {
    "intraday": "산 날 안에 판다 (1일 미만)",
    "days": "며칠 들고 있다가 판다 (1~7일)",
    "weeks": "몇 주 들고 있다가 판다 (7~30일)",
    "months": "몇 달 들고 있다가 판다 (30일~1년)",
    "years": "1년 넘게 들고 있다가 판다",
}

# ── declared_positions → open-position range, inclusive ──────────────────
POSITION_RANGE: dict[str, tuple[int, int | None]] = {
    "ultra_focused": (1, 3),
    "focused": (4, 8),
    "moderate": (9, 15),
    "diversified": (16, 25),
    "broad": (25, None),
}

# ── declared_drawdown_response → the user's own sentence ─────────────────
_DRAWDOWN_LINE: dict[str, str] = {
    "sell_all": "한 주에 10% 빠지면 다 판다",
    "sell_half": "한 주에 10% 빠지면 일부 판다",
    "hold": "한 주에 10% 빠지면 그냥 둔다",
    "buy_some": "한 주에 10% 빠지면 조금 더 산다",
    "buy_heavy": "한 주에 10% 빠지면 크게 더 산다",
}


def frequency_ceiling(answers: dict | None) -> int | None:
    """Monthly fill ceiling the user declared, or ``None`` (no answer / 40+)."""
    if not isinstance(answers, dict):
        return None
    return FREQUENCY_CEILING.get(str(answers.get("declared_frequency")))


def kst_month(dt: datetime) -> str:
    """``YYYY-MM`` of a naive-UTC timestamp, in KST."""
    return (dt + _KST).strftime("%Y-%m")


def kst_month_start_utc(now: datetime) -> datetime:
    """First instant of ``now``'s KST month, as naive UTC (for DB filters)."""
    local = now + _KST
    return local.replace(day=1, hour=0, minute=0, second=0, microsecond=0) - _KST


def is_recorded_fill(t) -> bool:
    """A ``TradeHistory`` row of either side that is a fill, not a registration row."""
    action = (getattr(t, "action", None) or "").upper()
    return (
        action in _FILL_SIDES
        and getattr(t, "traded_at", None) is not None
        and not is_registration_row(t)
    )


def month_fill_count(
    trades: Iterable, pending_times: Iterable[datetime], now: datetime,
) -> int:
    """Fills in ``now``'s KST month: recorded fills plus fills still waiting
    in the import inbox (``pending_times`` = their ``traded_at``). One SoT
    for the /mirror card and the fill push (services/fill_memo.py)."""
    current = kst_month(now)
    n = sum(1 for t in trades if is_recorded_fill(t) and kst_month(t.traded_at) == current)
    return n + sum(1 for ts in pending_times if ts is not None and kst_month(ts) == current)


def _month_seq(first: str, last: str, limit: int) -> list[str]:
    """``YYYY-MM`` strings from ``first`` to ``last`` inclusive, newest last,
    keeping only the newest ``limit``."""
    y, m = (int(x) for x in first.split("-"))
    ly, lm = (int(x) for x in last.split("-"))
    out: list[str] = []
    while (y, m) <= (ly, lm):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out[-limit:]


def _frequency_rule(
    answer: str, trades: list, pending_times: list[datetime], now: datetime,
) -> dict:
    ceiling = FREQUENCY_CEILING.get(answer)
    current = kst_month(now)
    counts: dict[str, int] = {}
    for ts in [t.traded_at for t in trades if is_recorded_fill(t)] + pending_times:
        key = kst_month(ts)
        counts[key] = counts.get(key, 0) + 1
    # Fills that arrived (phone automation / import) but wait in the inbox
    # count too — the fill happened; approving it is bookkeeping. Said so in
    # the sentence so the card and the push never disagree silently.
    waiting = sum(1 for ts in pending_times if kst_month(ts) == current)
    # Months before the first recorded fill are not "0 trades" — they are
    # months we have no record of. The series starts at the first fill.
    past = [k for k in counts if k <= current]
    first = min(past) if past else current
    months = []
    for key in _month_seq(first, current, MONTHS_SHOWN):
        n = counts.get(key, 0)
        months.append({
            "month": key,
            "count": n,
            "over": ceiling is not None and n > ceiling,
            "partial": key == current,
        })
    this_month = months[-1]["count"]
    waiting_note = f" (승인 대기 {waiting}번 포함)" if waiting else ""

    if ceiling is None:
        line = "한 달에 40번 넘게 사고판다 — 상한을 두지 않았어요"
        status = "no_line"
        observed = f"이번 달 {this_month}번{waiting_note}"
    else:
        line = f"한 달에 매수·매도 {ceiling}번 이하"
        status = "outside" if this_month > ceiling else "within"
        observed = f"이번 달 {this_month}번{waiting_note} · 선 {ceiling}번"
    over_months = sum(1 for m in months if m["over"])
    return {
        "id": "frequency",
        "title": "매매 횟수",
        "line": line,
        "measurable": True,
        "status": status,
        "observed": observed,
        "ceiling": ceiling,
        "this_month": this_month,
        "waiting": waiting,
        "months": months,
        "months_over": over_months,
        "months_shown": len(months),
    }


def _holding_rule(answer: str, trades: list, now: datetime) -> dict:
    lo, hi = HOLD_RANGE_DAYS[answer]
    since = now - timedelta(days=HOLD_WINDOW_DAYS)
    sells = collapse_pairs_by_sell(fifo_match_closed_trades_with_pnl(trades))
    shorter = within = longer = 0
    for pair, _pct in sells:
        if pair.buy_is_seed or pair.sell_time < since or pair.sell_time > now:
            continue
        d = pair.hold_days
        if d < lo:
            shorter += 1
        elif hi is not None and d >= hi:
            longer += 1
        else:
            within += 1
    total = shorter + within + longer
    if total == 0:
        status, observed = "no_data", f"최근 {HOLD_WINDOW_DAYS}일 매도 기록 없음"
    else:
        status = "within" if shorter == 0 and longer == 0 else "outside"
        parts = [f"최근 {HOLD_WINDOW_DAYS}일 매도 {total}번 중 선 안 {within}번"]
        if shorter:
            parts.append(f"더 일찍 {shorter}번")
        if longer:
            parts.append(f"더 오래 {longer}번")
        observed = " · ".join(parts)
    return {
        "id": "holding",
        "title": "보유 기간",
        "line": _HOLD_LINE[answer],
        "measurable": True,
        "status": status,
        "observed": observed,
        "window_days": HOLD_WINDOW_DAYS,
        "sells": total,
        "within": within,
        "shorter": shorter,
        "longer": longer,
        "lo_days": lo,
        "hi_days": hi,
    }


def _positions_rule(answer: str, open_positions: int) -> dict:
    lo, hi = POSITION_RANGE[answer]
    line = f"동시에 {lo}~{hi}종목을 들고 있다" if hi is not None else f"동시에 {lo}종목 이상 들고 있다"
    side = None
    if open_positions <= 0:
        # Holdings may simply not be registered yet — not "0 stocks".
        status, observed = "no_data", "등록된 보유 종목 없음"
    elif open_positions < lo:
        status, side, observed = "outside", "under", f"지금 {open_positions}종목 · 선보다 적음"
    elif hi is not None and open_positions > hi:
        status, side, observed = "outside", "over", f"지금 {open_positions}종목 · 선보다 많음"
    else:
        status, side, observed = "within", None, f"지금 {open_positions}종목"
    return {
        "id": "positions",
        "title": "종목 수",
        "line": line,
        "measurable": True,
        "status": status,
        "observed": observed,
        "side": side,
        "open_positions": max(0, int(open_positions)),
        "lo": lo,
        "hi": hi,
    }


def _drawdown_rule(answer: str) -> dict:
    return {
        "id": "drawdown",
        "title": "하락 대응",
        "line": _DRAWDOWN_LINE[answer],
        # Prices are never read here, so the week that fell 10% cannot be
        # found. The line is shown back as the user's own words; it is not
        # counted. (Adds below the running average are on /journal.)
        "measurable": False,
        "status": "not_counted",
        "observed": "시세를 쓰지 않아 10% 빠진 주를 알 수 없어요 — 세지 않아요",
    }


def compute_my_rules(
    answers: dict | None,
    trades: Iterable,
    open_positions: int,
    now: datetime,
    pending_times: Iterable[datetime] = (),
) -> dict:
    """The user's declared lines and where their own record sits against each.

    ``answers`` — ``InvestmentProfile.onboarding_answers()`` (V3 ids).
    ``trades`` — the user's ``TradeHistory`` rows (any order).
    ``open_positions`` — distinct tickers held with shares > 0.
    ``now`` — naive UTC; decides "this month" and the hold window.
    ``pending_times`` — ``traded_at`` of fills still waiting in the import
    inbox (``PendingTrade`` status pending). Counted by the frequency line
    only; they have no FIFO lots yet.

    ``available`` is False when none of the four lines was answered
    (pre-V3 profile or onboarding skipped) — the client then offers the
    five questions instead of an empty card.
    """
    answers = answers if isinstance(answers, dict) else {}
    rows = list(trades or [])
    waiting = [ts for ts in (pending_times or ()) if ts is not None]
    items: list[dict] = []

    freq = str(answers.get("declared_frequency"))
    if freq in FREQUENCY_CEILING:
        items.append(_frequency_rule(freq, rows, waiting, now))
    hold = str(answers.get("declared_holding"))
    if hold in HOLD_RANGE_DAYS:
        items.append(_holding_rule(hold, rows, now))
    pos = str(answers.get("declared_positions"))
    if pos in POSITION_RANGE:
        items.append(_positions_rule(pos, int(open_positions or 0)))
    dd = str(answers.get("declared_drawdown_response"))
    if dd in _DRAWDOWN_LINE:
        items.append(_drawdown_rule(dd))

    counted = [i for i in items if i["measurable"] and i["status"] not in ("no_data", "no_line")]
    return {
        "available": bool(items),
        "source": "onboarding",
        "items": items,
        "counted": len(counted),
        "outside": sum(1 for i in counted if i["status"] != "within"),
    }
