"""올해의 기록 — 한 해를 유저 본인의 기록과 본인의 말로만 되비춘다.

2026-10-15. 루프(멈춤 → 기록 → 거울)의 한 해 치를 한 화면에 모은다. 월간 거울
(services/reports/mirror_pdf.py · services/email/record_summary.py)은 한 달
단위이고, 한 해를 모으거나 유저가 쓴 문장을 되돌려 주는 곳은 없었다. 연말이
되돌아보기 가장 자연스러운 때라 12월 전에 있어야 한다.

무엇인가 (그리고 무엇이 아닌가)
--------------------------------
* **세는 것과 옮겨 적는 것뿐이다.** 체결·멈춤·기록·보유의 개수와 중앙값, 그리고
  유저가 그해 직접 쓴 문장 최대 3개. 점수·등급·연속 기록·순위·"잘했어요" 가 없고
  다른 유저와 비교하지 않는다 (DECISIONS — 점수화 폐기).
* **시세·네트워크·FX·LLM·시계가 없다.** 호출자(routes/year_recap.py)가 행을 읽고
  ``now`` 를 넘긴다. 금액을 다루지 않으므로 통화 합산도 없다 — 보유 기간은
  날짜 차이, 나머지는 개수다. ``services/behavior/*`` 와 같은 규율.
* **다른 거울의 계산을 다시 하지 않는다.** 멈춤의 귀결과 "취소 후 결국 샀나"는
  ``pre_trade.friction_outcome`` 을, 체결 단위·월·규칙 선은 ``profile.my_rules``
  를, 매도 한 번 = 관찰 한 건은 ``fifo_util.collapse_pairs_by_sell`` 을 그대로
  부른다. 여기서 새로 정한 것은 "한 해"라는 창과 인용 고르는 규칙뿐이다.

한 해 (KST 달력)
----------------
``traded_at`` · ``created_at`` 등은 naive UTC 다. KST 는 서머타임이 없어 +9h 고정이
정확하다 (friction_outcome · my_rules 와 같은 규약). 해 Y 의 창은
``[Y-01-01 00:00 KST, Y+1-01-01 00:00 KST)`` = ``[Y-1-12-31 15:00 UTC, Y-12-31 15:00 UTC)``
이고, 올해면 끝을 ``now`` 로 자른다 (``partial``). 12월 31일 23:30 KST 체결은
14:30 UTC 라 그해에 들어간다.

"취소 후 결국 샀나"는 **지금까지**의 매매로 판정한다 — 지난해 12월에 멈추고
올해 2월에 샀으면 지난해 화면에서도 "결국 샀다"로 보인다. 그게 일어난 일이다.

내 말 (인용 고르는 규칙 — 결정론적)
------------------------------------
각 칸은 데이터가 없으면 비운다. 같은 문장을 두 칸에 쓰지 않는다.

(b) ``not_taken`` — 일어나지 않은 거래: 그해 시작한 **매수 쪽** 멈춤 중 취소했고
    그 종목을 지금까지 사지 않은 것, **가장 먼저 취소한 것**. 가장 오래 "안 산"
    상태로 남은 기록이 이 칸의 뜻에 가장 가깝다. 제품의 남은 진짜 자산이라
    가장 먼저 고른다.
(a) ``first_reason`` — 그해 처음 적은 이유: 멈춤 이유(``rationale``)와 체결
    승인 때 적은 이유(``PendingTrade.approved_thesis``) 중 **가장 이른 것**,
    (b) 에 쓴 멈춤은 뺀다.
(c) ``scored_thesis`` — 나중에 채점한 리서치: 그해 쓴 리서치 노트 중 채점을
    마친 것, **가장 먼저 쓴 것**의 첫 번째 이유 + 유저 본인의 채점.

문장은 첫 줄만, :data:`QUOTE_MAX_CHARS` 자에서 자른다. 우리가 고치지 않는다
(라우트가 ``text`` 키만 스크럽에서 뺀다 — routes/research_notes.py 와 같은 방식).
"""
from __future__ import annotations

import statistics
from collections.abc import Iterable
from datetime import datetime, timedelta
from typing import Any

from models.research_note import VERDICTS
from services.pre_trade.friction_outcome import compute_friction_outcome, ticker_key
from services.profile.fifo_util import collapse_pairs_by_sell, fifo_match_closed_trades_with_pnl
from services.profile.my_rules import HOLD_MIN_DAYS, frequency_ceiling, is_recorded_fill, kst_month

_KST = timedelta(hours=9)
# TradeHistory.action 저장값 — 매수/매도 구분 데이터 필드다.
_BUY = "BUY"  # // legal-ok — stored enum value, compared only
_SELL = "SELL"  # // legal-ok — stored enum value, compared only

# 인용 한 칸의 최대 글자 수. 공유 카드에는 인용이 들어가지 않는다 — 화면용.
QUOTE_MAX_CHARS = 120


# ── 시간 ─────────────────────────────────────────────────────────────────

def kst_year(ts: datetime) -> int:
    """KST 달력의 해 (naive UTC 입력)."""
    return (ts + _KST).year


def _year_window(year: int, now: datetime) -> tuple[datetime, datetime, bool]:
    """해 ``year`` 의 [시작, 끝) — naive UTC. 올해면 끝을 ``now`` 로 자른다."""
    start = datetime(year, 1, 1) - _KST
    full_end = datetime(year + 1, 1, 1) - _KST
    return start, min(full_end, now), now < full_end


def _kst_date(ts: datetime) -> str:
    return (ts + _KST).date().isoformat()


def _months(year: int, end: datetime, partial: bool) -> list[str]:
    """그해의 ``YYYY-MM`` — 올해면 ``now`` 의 달까지."""
    last = kst_month(end) if partial else f"{year:04d}-12"
    return [f"{year:04d}-{m:02d}" for m in range(1, 13) if f"{year:04d}-{m:02d}" <= last]


# ── 섹션 ─────────────────────────────────────────────────────────────────

def _fills_section(fills: list, months: list[str]) -> dict:
    per_month = {m: 0 for m in months}
    for t in fills:
        key = kst_month(t.traded_at)
        if key in per_month:
            per_month[key] += 1
    return {
        "total": len(fills),
        "buys": sum(1 for t in fills if (t.action or "").upper() == _BUY),
        "sells": sum(1 for t in fills if (t.action or "").upper() == _SELL),
        "tickers": len({ticker_key(t.ticker) for t in fills if t.ticker}),
        "months_active": sum(1 for n in per_month.values() if n),
        "by_month": [{"month": m, "count": n} for m, n in per_month.items()],
    }


def _pauses_section(year_reflections: list, trades: list, now: datetime) -> dict:
    """멈춤의 귀결 — friction_outcome 그대로. 창은 호출자가 이미 잘랐다."""
    fo = compute_friction_outcome(year_reflections, trades, now=now)
    follow = fo["cancelled_followthrough"]
    return {
        **fo["stopped"],
        # 매수 쪽 취소만 "결국 샀나"를 묻는다 (friction_outcome 규약).
        "cancelled_buy": follow["cancelled"],
        "bought_later_anyway": follow["bought_later_anyway"],
        "never_bought": follow["never_bought"],
    }


def _records_section(
    fills: list, approved: list, notes: list, observation_times: list[datetime], in_year,
) -> dict:
    # 이유가 적힌 체결 = 가져오기 승인 때 이유를 쓴 체결(approved_thesis 는 승인
    # 필수 칸) + 멈춤에 직접 이은 매수(그 멈춤의 rationale 이 그 매수의 이유다 —
    # components/pre-trade/reflection-link-line.tsx). Position.thesis 는 종목
    # 단위라 체결 단위로 세지 않는다.
    thesis_ids = {
        p.approved_trade_id for p in approved
        if p.approved_trade_id and (p.approved_thesis or "").strip()
    }
    reasoned = sum(
        1 for t in fills
        if t.id in thesis_ids or getattr(t, "reflection_id", None)
    )
    reviewed = [n for n in notes if n.reviewed_at is not None and in_year(n.reviewed_at)]
    verdicts = {v: 0 for v in VERDICTS}
    for n in reviewed:
        for v in n.verdicts_list():
            verdicts[v] += 1
    return {
        "reasoned_fills": reasoned,
        "research_written": sum(1 for n in notes if in_year(n.created_at)),
        "research_reviewed": len(reviewed),
        "verdicts": verdicts,
        "observation_notes": sum(1 for ts in observation_times if in_year(ts)),
    }


def _year_sells(trades: list, in_year) -> list:
    """그해 닫힌 매도 — 한 번 = 한 건, 시드 로트(매수일 없음)는 뺀다."""
    return [
        pair for pair, _pct in collapse_pairs_by_sell(fifo_match_closed_trades_with_pnl(trades))
        if not pair.buy_is_seed and in_year(pair.sell_time)
    ]


def _holding_section(sells: list) -> dict:
    days = [p.hold_days for p in sells]
    return {
        "sells": len(days),
        # median — 보유 기간은 꼬리가 길다 (다른 거울과 같은 규약).
        "median_days": round(statistics.median(days), 1) if days else None,
    }


def _rules_section(
    answers: dict | None, confirmed_at: datetime | None, fills: list, sells: list,
    months: list[str], end: datetime,
) -> dict | None:
    """채택한 뒤의 달만, 선 안/밖 개수. 채택 전이면 None — "말한 나"는 규칙이 아니다."""
    if confirmed_at is None or confirmed_at >= end or not isinstance(answers, dict):
        return None
    ceiling = frequency_ceiling(answers)
    hold_min = HOLD_MIN_DAYS.get(str(answers.get("declared_holding")))
    adopted = kst_month(confirmed_at)
    after = [t for t in fills if t.traded_at >= confirmed_at]
    frequency = None
    if ceiling is not None:
        rows = []
        for m in (m for m in months if m >= adopted):
            n = sum(1 for t in after if kst_month(t.traded_at) == m)
            # 채택한 달은 채택 뒤 체결만, 올해의 이번 달은 지금까지만 — 둘 다 한 달이 아니다.
            rows.append({"month": m, "count": n, "over": n > ceiling,
                         "partial": m == adopted or m == kst_month(end)})
        frequency = {
            "ceiling": ceiling, "months": rows,
            "within": sum(1 for r in rows if not r["over"]),
            "outside": sum(1 for r in rows if r["over"]),
        }
    holding = None
    if hold_min is not None:
        later = [p for p in sells if p.sell_time >= confirmed_at]
        holding = {"min_days": hold_min, "sells": len(later),
                   "sooner": sum(1 for p in later if p.hold_days < hold_min)}
    if frequency is None and holding is None:
        return None
    return {"confirmed_on": _kst_date(confirmed_at), "frequency": frequency, "holding": holding}


# ── 내 말 ────────────────────────────────────────────────────────────────

def _excerpt(text: Any) -> str | None:
    """첫 줄, 최대 :data:`QUOTE_MAX_CHARS` 자. 빈 글이면 None."""
    for line in str(text or "").splitlines():
        line = line.strip()
        if line:
            return line if len(line) <= QUOTE_MAX_CHARS else line[: QUOTE_MAX_CHARS - 1].rstrip() + "…"
    return None


def _quote(kind: str, source: str, text: str, at: datetime, ticker: Any, **extra) -> dict:
    return {"kind": kind, "source": source, "text": text,
            "date": _kst_date(at), "ticker": ticker or None, **extra}


def _not_taken_quote(year_reflections: list, trades: list, now: datetime) -> tuple[dict | None, Any]:
    cancelled = sorted(
        (r for r in year_reflections if r.cancelled_at is not None and r.proceeded_at is None),
        key=lambda r: (r.cancelled_at, r.id or 0),
    )
    for r in cancelled:
        text = _excerpt(r.rationale)
        if not text:
            continue
        # 한 건씩 friction_outcome 에 물어본다 — 매수 쪽인지, 그 뒤 샀는지 판정을
        # 여기서 다시 구현하지 않는다 (명시 연결·접미사·날짜만 있는 체결 규칙 포함).
        follow = compute_friction_outcome([r], trades, now=now)["cancelled_followthrough"]
        if follow["never_bought"] == 1:
            return _quote("not_taken", "pause", text, r.created_at, r.intended_ticker), r
    return None, None


def _first_reason_quote(year_reflections: list, approved: list, in_year, skip) -> dict | None:
    candidates = [
        (r.created_at, 0, r.id or 0, "pause", r.rationale, r.intended_ticker)
        for r in year_reflections if r is not skip
    ] + [
        (p.approved_at, 1, p.id or 0, "fill", p.approved_thesis, p.ticker)
        for p in approved if p.approved_at is not None and in_year(p.approved_at)
    ]
    for at, _order, _id, source, raw, ticker in sorted(candidates, key=lambda c: c[:3]):
        text = _excerpt(raw)
        if text:
            return _quote("first_reason", source, text, at, ticker)
    return None


def _scored_thesis_quote(notes: list, in_year) -> dict | None:
    scored = sorted(
        (n for n in notes if in_year(n.created_at) and n.reviewed_at is not None),
        key=lambda n: (n.created_at, n.id or 0),
    )
    for n in scored:
        theses = n.theses_list()
        text = _excerpt(theses[0]) if theses else None
        if text:
            verdicts = n.verdicts_list()
            return _quote("scored_thesis", "research", text, n.created_at, n.ticker,
                          verdict=verdicts[0] if verdicts else None)
    return None


def _quotes(year_reflections, approved, notes, trades, now, in_year) -> list[dict]:
    not_taken, used = _not_taken_quote(year_reflections, trades, now)
    picks = [
        _first_reason_quote(year_reflections, approved, in_year, used),
        not_taken,
        _scored_thesis_quote(notes, in_year),
    ]
    return [q for q in picks if q]


# ── 공개 함수 ────────────────────────────────────────────────────────────

def compute_year_recap(
    year: int,
    *,
    now: datetime,
    trades: Iterable,
    reflections: Iterable,
    approved_pending: Iterable = (),
    research_notes: Iterable = (),
    observation_times: Iterable[datetime] = (),
    rules_answers: dict | None = None,
    rules_confirmed_at: datetime | None = None,
) -> dict:
    """한 유저의 한 해. 모든 입력은 **그 유저의 행**이고 호출자가 읽어 넘긴다.

    ``trades`` 는 전체 이력이어야 한다 — 그해 매도의 매수 로트가 전해에 있고,
    "취소 후 결국 샀나"는 지금까지의 매수로 판정한다. 그해로 자르는 건 여기서 한다.
    ``approved_pending`` = 승인된 ``PendingTrade`` (``approved_thesis`` ·
    ``approved_trade_id`` · ``approved_at``). ``observation_times`` = 관찰 노트의
    ``created_at`` 만 (본문은 세지 않으므로 복호화할 필요가 없다).
    """
    start, end, partial = _year_window(year, now)

    def in_year(ts: datetime | None) -> bool:
        return ts is not None and start <= ts < end

    trades = list(trades)
    approved = list(approved_pending)
    notes = list(research_notes)
    year_reflections = [r for r in reflections if in_year(r.created_at)]
    fills = [t for t in trades if is_recorded_fill(t) and in_year(t.traded_at)]
    months = _months(year, end, partial)
    sells = _year_sells(trades, in_year)

    records = _records_section(fills, approved, notes, list(observation_times), in_year)
    pauses = _pauses_section(year_reflections, trades, now)
    return {
        "year": year,
        "range": {"start": f"{year:04d}-01-01", "end": _kst_date(end - timedelta(microseconds=1)),
                  "partial": partial},
        "fills": _fills_section(fills, months),
        "pauses": pauses,
        "records": records,
        "holding": _holding_section(sells),
        "rules": _rules_section(rules_answers, rules_confirmed_at, fills, sells, months, end),
        "quotes": _quotes(year_reflections, approved, notes, trades, now, in_year),
        # 문 앞 멈춤(doorway pause, services/doorway/ — 별도 작업 중)이 채울 자리.
        # 그 기능이 머지되면 그해의 문 앞 멈춤 개수를 여기에 담는다. 지금은 늘 None.
        "doorway": None,
        # 그해 아무 기록도 없으면 화면은 짧은 한 줄만 쓴다 — 0 으로 채운 표를 그리지 않는다.
        "empty": not (fills or year_reflections or records["research_written"]
                      or records["research_reviewed"] or records["observation_notes"]
                      or records["reasoned_fills"]),
    }


def available_years(timestamps: Iterable[datetime | None], now: datetime) -> list[int]:
    """기록이 하나라도 있는 KST 해, 최신순. ``now`` 이후 시각은 무시한다."""
    years = {kst_year(ts) for ts in timestamps if ts is not None and ts <= now}
    return sorted(years, reverse=True)
