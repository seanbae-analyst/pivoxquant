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
* **A line the user adopted.** The onboarding question asked how they
  *usually* behave — a self-description, not a promise. It becomes a rule
  only when the user says so (``InvestmentProfile.rules_confirmed_at``,
  POST /api/profile/rules/confirm). Before that the lines and counts are
  shown as "what you said", without 선 안/밖 and without the fill-push line
  (services/fill_memo.py). Re-answering a rule question clears the
  confirmation — a new line is adopted again, never silently.
* **From the day it was adopted.** Once adopted, the card reads "내 규칙 ·
  YYYY-MM-DD부터", so 선 안/밖, the month series and the fill-push count
  look only at records from that moment on (``_at_or_after``) — a fill
  from before the user drew the line is not "선 밖" of it. Before adoption
  the preview shows the whole record (2026-10-15).
* **One direction per line.** A line is crossed only in the direction the
  evidence calls costly: trading MORE often than the ceiling, selling SOONER
  than the minimum hold, holding FEWER names than the minimum (more
  concentrated). Doing less — fewer trades, longer holds, more names — is
  never "선 밖"; flagging it would push the user toward more activity. Rules
  read the way people state them: "5번 이하", "7일 이상", "4종목 이상".
* **A fact, not a verdict.** 선 안 / 선 밖 with the raw counts. No score, no
  grade, no streak, no "지키세요".
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
  KST calendar days between the purchase day and the sale day — the unit the
  onboarding buckets are stated in ("하루 안에 정리" = the same KST day;
  bought in the afternoon and sold next morning is "며칠", not under a day).
  A 매도 whose lots were all registration seeds carries no purchase date and
  is skipped, as in the holding mirror.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterable

from services.imports import is_date_only
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

# The onboarding answers a line is drawn from. Changing any of them changes a
# line, so it clears ``rules_confirmed_at`` (routes/profile.py).
RULE_ANSWER_IDS: tuple[str, ...] = (
    "declared_frequency",
    "declared_holding",
    "declared_positions",
    "declared_drawdown_response",
)

# ── declared_frequency → monthly ceiling (fills / month) ─────────────────
# The upper end of the bucket the user picked ("3~5번" → 5). "40번 이상" has
# no ceiling to cross.
FREQUENCY_CEILING: dict[str, int | None] = {
    "rare": 2,
    "few": 5,
    "moderate": 15,
    "frequent": 40,
    "daily": None,
}

# ── declared_holding → minimum hold in KST calendar days ─────────────────
# The lower edge of the answer's natural day range (하루 안 / 며칠 1~7 /
# 몇 주 7~30 / 몇 달 30~365 / 1년 이상). "하루 안에 정리" has no minimum.
# Counted in calendar days, not 24-hour blocks (2026-10-15): "며칠" means
# "not the same day", so a 14:00 buy sold at 10:00 the next morning is 1 day
# held — it used to be 0.83 and was called sooner than the line.
HOLD_MIN_DAYS: dict[str, int | None] = {
    "intraday": None,
    "days": 1,
    "weeks": 7,
    "months": 30,
    "years": 365,
}

_HOLD_LINE: dict[str, str] = {
    "intraday": "산 날 안에 판다 — 최소 보유 기간을 두지 않았어요",
    "days": "산 날을 넘겨 들고 있다가 판다",
    "weeks": "7일 이상 들고 있다가 판다",
    "months": "30일 이상 들고 있다가 판다",
    "years": "1년 이상 들고 있다가 판다",
}

# The 매도 that fell under the line, and the sentence when none did.
_HOLD_SOONER: dict[str, str] = {
    "days": "산 날 판 것",
    "weeks": "7일 전에 판 것",
    "months": "30일 전에 판 것",
    "years": "1년 전에 판 것",
}

_HOLD_ALL_WITHIN: dict[str, str] = {
    "days": "모두 산 날을 넘겨 들고 있다가 팔았어요",
    "weeks": "모두 7일 이상 들고 있다가 팔았어요",
    "months": "모두 30일 이상 들고 있다가 팔았어요",
    "years": "모두 1년 이상 들고 있다가 팔았어요",
}

# ── declared_positions → minimum open positions ──────────────────────────
# The lower edge of the bucket ("4~8종목" → 4). "1~3종목" is a deliberately
# concentrated style with no floor to fall under.
POSITION_MIN: dict[str, int | None] = {
    "ultra_focused": None,
    "focused": 4,
    "moderate": 9,
    "diversified": 16,
    "broad": 25,
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


def rule_answers_changed(old: dict | None, new: dict | None) -> bool:
    """True when any answer a line is drawn from differs between two
    onboarding-answer dicts (``record_habit`` alone does not count)."""
    old = old if isinstance(old, dict) else {}
    new = new if isinstance(new, dict) else {}
    return any(old.get(k) != new.get(k) for k in RULE_ANSWER_IDS)


def kst_month(dt: datetime) -> str:
    """``YYYY-MM`` of a naive-UTC timestamp, in KST."""
    return (dt + _KST).strftime("%Y-%m")


def kst_month_start_utc(now: datetime) -> datetime:
    """First instant of ``now``'s KST month, as naive UTC (for DB filters)."""
    local = now + _KST
    return local.replace(day=1, hour=0, minute=0, second=0, microsecond=0) - _KST


def kst_day(dt: datetime) -> date:
    """KST calendar day of a stored ``traded_at``. Timed fills are naive UTC;
    date-only ones are their KST date at 00:00, unshifted — +9h gives the KST
    day for both (``services.imports.dedupe.kst_day``)."""
    return (dt + _KST).date()


def _at_or_after(ts: datetime, since: datetime | None) -> bool:
    """Was this fill at or after the moment the lines were adopted?

    ``None`` = not adopted: everything counts (the preview). A date-only fill
    (00:00) has no time of day, so it counts when its KST day is the adoption
    day or later — the calendar-day rule of
    ``pre_trade.friction_outcome._at_or_after``.
    """
    if since is None or ts >= since:
        return True
    return is_date_only(ts) and ts.date() >= kst_day(since)


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
    since: datetime | None = None,
) -> int:
    """Fills in ``now``'s KST month: recorded fills plus fills still waiting
    in the import inbox (``pending_times`` = their ``traded_at``). With
    ``since`` (``rules_confirmed_at``) only the fills from that moment on
    (``_at_or_after``). One SoT for the /mirror card and the fill push
    (services/fill_memo.py)."""
    current = kst_month(now)
    times = [t.traded_at for t in trades if is_recorded_fill(t)]
    times += [ts for ts in pending_times if ts is not None]
    return sum(1 for ts in times if kst_month(ts) == current and _at_or_after(ts, since))


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
    since: datetime | None = None,
) -> dict:
    ceiling = FREQUENCY_CEILING.get(answer)
    current = kst_month(now)
    # Adopted lines count from the adoption on — the month series included,
    # so no month before the user drew the line is shown as past it.
    recorded = [t.traded_at for t in trades if is_recorded_fill(t) and _at_or_after(t.traded_at, since)]
    inbox = [ts for ts in pending_times if _at_or_after(ts, since)]
    counts: dict[str, int] = {}
    for ts in recorded + inbox:
        key = kst_month(ts)
        counts[key] = counts.get(key, 0) + 1
    # Fills that arrived (phone automation / import) but wait in the inbox
    # count too — the fill happened; approving it is bookkeeping. Said so in
    # the sentence so the card and the push never disagree silently.
    waiting = sum(1 for ts in inbox if kst_month(ts) == current)
    # In the month the lines were adopted, "이번 달" is only the part after it.
    this_label = "선을 정한 뒤 이번 달" if since is not None and kst_month(since) == current else "이번 달"
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
        observed = f"{this_label} {this_month}번{waiting_note}"
    else:
        line = f"한 달에 매수·매도 {ceiling}번 이하"
        status = "outside" if this_month > ceiling else "within"
        observed = f"{this_label} {this_month}번{waiting_note} · 선 {ceiling}번"
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
        "months_over": sum(1 for m in months if m["over"]),
        "months_shown": len(months),
    }


def _holding_rule(
    answer: str, trades: list, now: datetime, since: datetime | None = None,
) -> dict:
    min_days = HOLD_MIN_DAYS[answer]
    window_start = now - timedelta(days=HOLD_WINDOW_DAYS)
    sells = collapse_pairs_by_sell(fifo_match_closed_trades_with_pnl(trades))
    total = sooner = 0
    for pair, _pct in sells:
        if pair.buy_is_seed or pair.sell_time < window_start or pair.sell_time > now:
            continue
        # Adopted lines: only 매도 from the adoption on (a lot bought before
        # it still counts — the decision to sell came after).
        if not _at_or_after(pair.sell_time, since):
            continue
        total += 1
        # KST calendar days (module docstring, Units). A merged 매도's
        # ``buy_time`` is its share-weighted purchase time.
        held = (kst_day(pair.sell_time) - kst_day(pair.buy_time)).days
        if min_days is not None and held < min_days:
            sooner += 1
    # Adopted inside the window: the count runs from then, and says so.
    scope = "선을 정한 뒤" if since is not None and since > window_start else f"최근 {HOLD_WINDOW_DAYS}일"
    head = f"{scope} 매도 {total}번"
    if min_days is None:
        status = "no_line"
        observed = head if total else f"{scope} 매도 기록 없음"
    elif total == 0:
        status, observed = "no_data", f"{scope} 매도 기록 없음"
    else:
        status = "outside" if sooner else "within"
        observed = (
            f"{head} · {_HOLD_SOONER[answer]} {sooner}번" if sooner
            else f"{head} · {_HOLD_ALL_WITHIN[answer]}"
        )
    return {
        "id": "holding",
        "title": "보유 기간",
        "line": _HOLD_LINE[answer],
        "measurable": True,
        "status": status,
        "observed": observed,
        "window_days": HOLD_WINDOW_DAYS,
        "sells": total,
        "sooner": sooner,
        "min_days": min_days,
    }


def _positions_rule(answer: str, open_positions: int) -> dict:
    floor = POSITION_MIN[answer]
    n = max(0, int(open_positions))
    if floor is None:
        line = "1~3종목에 모아 담는다 — 최소 종목 수를 두지 않았어요"
        status = "no_line"
        observed = f"지금 {n}종목" if n else "등록된 보유 종목 없음"
    else:
        line = f"{floor}종목 이상 나눠 담는다"
        if n == 0:
            # Holdings may simply not be registered yet — not "0 stocks".
            status, observed = "no_data", "등록된 보유 종목 없음"
        elif n < floor:
            status, observed = "outside", f"지금 {n}종목 · 선보다 적음"
        else:
            status, observed = "within", f"지금 {n}종목"
    return {
        "id": "positions",
        "title": "종목 수",
        "line": line,
        "measurable": True,
        "status": status,
        "observed": observed,
        "open_positions": n,
        "min_positions": floor,
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
    confirmed_at: datetime | None = None,
) -> dict:
    """The user's declared lines and where their own record sits against each.

    ``answers`` — ``InvestmentProfile.onboarding_answers()`` (V3 ids).
    ``trades`` — the user's ``TradeHistory`` rows (any order).
    ``open_positions`` — distinct tickers held with shares > 0.
    ``now`` — naive UTC; decides "this month" and the hold window.
    ``pending_times`` — ``traded_at`` of fills still waiting in the import
    inbox (``PendingTrade`` status pending). Counted by the frequency line
    only; they have no FIFO lots yet.
    ``confirmed_at`` — ``InvestmentProfile.rules_confirmed_at``. ``confirmed``
    in the payload tells the client whether these are the user's adopted
    rules or still only what they said. Unset, the counts are a preview over
    the whole record; set, the frequency series and the hold count take only
    records from that moment on, matching the card's "YYYY-MM-DD부터". The
    open-position count is "now" either way.

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
        items.append(_frequency_rule(freq, rows, waiting, now, since=confirmed_at))
    hold = str(answers.get("declared_holding"))
    if hold in HOLD_MIN_DAYS:
        items.append(_holding_rule(hold, rows, now, since=confirmed_at))
    pos = str(answers.get("declared_positions"))
    if pos in POSITION_MIN:
        items.append(_positions_rule(pos, int(open_positions or 0)))
    dd = str(answers.get("declared_drawdown_response"))
    if dd in _DRAWDOWN_LINE:
        items.append(_drawdown_rule(dd))

    counted = [i for i in items if i["status"] in ("within", "outside")]
    available = bool(items)
    return {
        "available": available,
        "source": "onboarding",
        "confirmed": available and confirmed_at is not None,
        "confirmed_at": confirmed_at.isoformat() if (available and confirmed_at) else None,
        # KST calendar date the user adopted the lines, ready to print.
        "confirmed_on": (
            kst_day(confirmed_at).isoformat() if (available and confirmed_at) else None
        ),
        "items": items,
        "counted": len(counted),
        "outside": sum(1 for i in counted if i["status"] == "outside"),
    }
