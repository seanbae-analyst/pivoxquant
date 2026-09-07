"""Record summary — the user's own facts, for the periodic emails.

Why this module exists
----------------------
Until 2026-09-07 the retention emails received six template variables and not
one of them came from the user's record: ``name``, ``dashboard_url``,
``pricing_url``, ``unsubscribe_url``, ``consent_at_kr``, ``consent_source``.
The mails were therefore generic product promotion with a name on top — which
is precisely the shape 정통망법 §50 treats as 광고성 정보, and which also
contradicts the product's own claim that the user's record is the only
material.

This module supplies the missing half. It computes, from the user's **own
stored record**, a small set of plain counts and hands back pre-composed
Korean sentences. That changes what the email *is*: a retrospective statement
of fact about the reader's own activity rather than an invitation to come back.

What it is NOT
--------------
* **No verdict.** No score, grade, ranking, "개선/악화", "잘함/못함". The
  numbers are counts; the reader draws the conclusion. Same posture as the six
  behaviour mirrors and as ``friction_outcome``.
* **No prices, no FX, no network.** Every input is the user's own
  ``PreTradeReflection`` / ``TradeHistory`` rows. This keeps the send path
  deterministic and keeps FMP/KIS redistribution terms out of email entirely.
* **Nothing prescriptive.** No sentence here tells the reader to do
  anything. The send path runs ``assert_legal_safe`` over the rendered body,
  so any directive term from
  ``services.legal.forbidden_terms.FORBIDDEN_DIRECTIVE_TERMS`` raises at
  dispatch. The list is deliberately not restated in this file — the
  pre-commit guard scans source too, and quoting the vocabulary in order to
  forbid it trips the same wire (it did, twice, while this was written).

The silence rule
----------------
:func:`build_record_summary` returns ``None`` when the window holds nothing
worth stating. That is deliberate and load-bearing: an email saying "you did
nothing this week" is a nudge, not a record, and it is exactly the kind of
message the §50 analysis above is trying to avoid becoming. The caller skips
the send instead of filling the gap with encouragement.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# A window with fewer than this many recorded events has nothing to reflect.
# One lone trade is not a pattern and does not earn an email.
MIN_EVENTS_TO_SPEAK = 2


def build_record_summary(
    user_id: int,
    *,
    window_days: int,
    now: Any = None,
) -> dict[str, Any] | None:
    """Return this user's own counts for the window, or ``None`` to stay quiet.

    Parameters
    ----------
    user_id:
        Owner of the record. All queries are scoped to this id.
    window_days:
        Look-back window. 7 for the D+7 mail, 30 for D+30.
    now:
        Clock the window is measured back from. The dispatcher already
        threads an injected ``now`` through the night gate; the summary must
        use the SAME one or the two disagree — in tests obviously, but also
        in production on any run where dispatch is replayed or back-dated.
        Defaults to real UTC.

    Returns
    -------
    dict | None
        ``None`` when the window is empty enough that there is nothing
        factual to say — the caller must then skip the send. Otherwise a dict
        with raw counts plus ``lines``, a list of ready-to-render Korean
        sentences (the templates stay free of formatting logic).
    """
    from models import PreTradeReflection, TradeHistory

    try:
        reflections = (
            PreTradeReflection.query.filter_by(user_id=user_id).all()
        )
        trades = TradeHistory.query.filter_by(user_id=user_id).all()
    except Exception:  # pragma: no cover — never let a summary break a send
        logger.exception("record_summary query failed for user_id=%s", user_id)
        return None

    try:
        from services.pre_trade.friction_outcome import compute_friction_outcome
        friction = compute_friction_outcome(
            reflections, trades, window_days=window_days, now=now
        )
    except Exception:  # pragma: no cover
        logger.exception("friction_outcome failed for user_id=%s", user_id)
        return None

    stopped = friction.get("stopped") or {}
    follow = friction.get("cancelled_followthrough") or {}

    started = int(stopped.get("started") or 0)
    proceeded = int(stopped.get("proceeded") or 0)
    cancelled = int(stopped.get("cancelled") or 0)
    never_bought = int(follow.get("never_bought") or 0)
    bought_later = int(follow.get("bought_later_anyway") or 0)

    trade_count = _trades_in_window(trades, window_days, now=now)

    # The silence rule. Nothing recorded → nothing to reflect → no mail.
    if (started + trade_count) < MIN_EVENTS_TO_SPEAK:
        return None

    lines = _compose(
        window_days=window_days,
        started=started,
        proceeded=proceeded,
        cancelled=cancelled,
        never_bought=never_bought,
        bought_later=bought_later,
        trade_count=trade_count,
    )
    if not lines:
        return None

    return {
        "window_days": window_days,
        "started": started,
        "proceeded": proceeded,
        "cancelled": cancelled,
        "never_bought": never_bought,
        "bought_later": bought_later,
        "trade_count": trade_count,
        "lines": lines,
    }


def _trades_in_window(
    trades: list[Any], window_days: int, *, now: Any = None
) -> int:
    """Count fills inside the window. Timezone-naive UTC, matching storage."""
    from datetime import datetime, timedelta, timezone

    ref = now or datetime.now(timezone.utc).replace(tzinfo=None)
    if getattr(ref, "tzinfo", None) is not None:
        ref = ref.astimezone(timezone.utc).replace(tzinfo=None)
    cutoff = ref - timedelta(days=window_days)
    n = 0
    for t in trades:
        ts = getattr(t, "traded_at", None)
        if ts is None:
            continue
        if getattr(ts, "tzinfo", None) is not None:
            ts = ts.astimezone(timezone.utc).replace(tzinfo=None)
        if ts >= cutoff:
            n += 1
    return n


def _compose(
    *,
    window_days: int,
    started: int,
    proceeded: int,
    cancelled: int,
    never_bought: int,
    bought_later: int,
    trade_count: int,
) -> list[str]:
    """Turn counts into plain Korean statements of fact.

    Every sentence is past-tense and descriptive. None of them tells the
    reader what to do next — that is what keeps this a record rather than a
    solicitation, and it is also what keeps the text clear of the forbidden
    directive vocabulary the send path asserts on.
    """
    lines: list[str] = []
    period = f"지난 {window_days}일"

    if started > 0:
        head = f"{period} 동안 {started}번 멈춰 서서 기록을 남기셨습니다."
        stems: list[str] = []
        if proceeded:
            stems.append(f"{proceeded}번은 그대로 진행하셨")
        if cancelled:
            stems.append(f"{cancelled}번은 취소하셨")
        if stems:
            parts = [
                st + ("습니다" if i == len(stems) - 1 else "고")
                for i, st in enumerate(stems)
            ]
            head += " " + ", ".join(parts) + "."
        lines.append(head)

        # 회피와 지연의 구분은 이 제품만 아는 사실이다. 어느 쪽이 낫다는
        # 말은 붙이지 않는다 — 기록은 그것까지 말해주지 않는다.
        # 절이 하나일 때 연결어미로 끝나지 않도록 마지막만 종결형으로 쓴다
        # ("…담지 않으셨고." 가 되던 버그).
        if cancelled > 0 and (never_bought or bought_later):
            clauses: list[tuple[str, str]] = []
            if never_bought:
                clauses.append((f"{never_bought}건은 그 뒤로 담지 않으셨",
                                "고"))
            if bought_later:
                clauses.append((f"{bought_later}건은 나중에 결국 담으셨",
                                "고"))
            if clauses:
                parts = [
                    stem + ("습니다" if i == len(clauses) - 1 else conj)
                    for i, (stem, conj) in enumerate(clauses)
                ]
                lines.append("취소한 것 중 " + ", ".join(parts) + ".")

    if trade_count > 0:
        lines.append(f"{period} 동안 체결 기록은 {trade_count}건입니다.")

    return lines
