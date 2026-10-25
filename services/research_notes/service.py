"""Research notes service — 양식 저장 · 목록 · 다시 볼 날 · 채점 · 요약.

docs/design/research-notes_2026-10-15.md. 검증(캡·정규화·비객체 body)은 전부
여기에 있고 라우트는 얇다 — services/observation_notes 와 같은 분업.

Ownership
---------
모든 읽기·쓰기는 ``user_id`` 를 SQL 층에서 건다. 남의 노트는 존재 자체를
노출하지 않는다 — 조회 실패와 타인 소유는 똑같이 ``LookupError`` 다.

What "결과" means here
----------------------
채점은 유저가 한다(가정마다 맞음/틀림/모름). 우리가 붙이는 것은 같은 종목의
**본인 체결** 하나뿐이다: 리서치를 적은 시각 이후 그 종목을 판 기록이 있으면
그 매도들의 실현 손익 합의 부호(이익 / 손실 / 본전), 없으면 "아직 안 팖".
날짜만 있는 체결은 KST 같은 날 규칙을 따른다(``_sold_after``).
시세를 부르지 않는다 — 보유 중인 종목의 평가손익은 결과로 쓰지 않는다
(MARKET_DATA_DISPLAY_ENABLED 와 무관하게 3축 규칙). 등록용 행
(holding_seed / holding_adjust)은 체결이 아니라 뺀다.

판단 × 결과는 개수만 낸다. 점수·등급·적중률 같은 라벨을 만들지 않는다
(persona invariant — 기록 거울은 사실 서술).
"""
from __future__ import annotations

import calendar
import json
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func

from extensions import db
from models import ResearchNote, TradeHistory
from models.research_note import (
    DEFAULT_SURFACE,
    INFO_SOURCES,
    MAX_BUSINESS_CHARS,
    MAX_INVALIDATION_CHARS,
    MAX_NUMBERS_CHARS,
    MAX_REVIEW_NOTE_CHARS,
    MAX_RISK_CHARS,
    MAX_THESES,
    MAX_THESIS_CHARS,
    MIN_THESES,
    REVIEW_MONTHS,
    TICKER_MAX_LEN,
    VALID_SURFACES,
    VERDICTS,
)
from models.trade_history import REGISTRATION_SOURCES
from services.imports import is_date_only
from services.ticker_normalizer import normalize_ticker

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))
_KST_OFFSET = timedelta(hours=9)   # naive-UTC → KST wall clock (no DST)
DEFAULT_REVIEW_MONTHS = 3
DEFAULT_LIST_LIMIT = 50
MAX_LIST_LIMIT = 200
# 요약은 최근 노트까지만 본다 — 한 유저가 이 이상 적는 경우는 베타에서 없고,
# 무한정 읽는 경로를 막는 상한이다.
OVERVIEW_ROW_CAP = 1000

OUTCOMES = ("gain", "loss", "flat", "open")
# trade_history.action value for a disposal — a stored data literal, not copy.
_DISPOSAL_ACTION = "SELL"  # // legal-ok


# ── Public surface ───────────────────────────────────────────────────

def kst_today(now: datetime | None = None) -> date:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(KST).date()


def add_months(d: date, months: int) -> date:
    """Same day ``months`` later, clamped to the month's last day (1/31 → 2/28)."""
    m0 = d.month - 1 + months
    y, m = d.year + m0 // 12, m0 % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def create_research(user_id: int, data) -> dict:
    """Insert one research note. Returns its dict.

    Raises ``ValueError`` on any invalid field — see the ``_validate_*``
    helpers. ``review_months`` (1·3·6, default 3) sets the review day as that
    many months after today in KST.
    """
    if not isinstance(data, dict):
        raise ValueError("body must be a JSON object")
    ticker = _validate_ticker(data.get("ticker"))
    # Optional since 2026-10-25 (CEO "적어야 할게 너무 많다"): the form opens on
    # the reason and the wrong-signal; this one is folded. The column is NOT
    # NULL, so an unanswered field is stored as "".
    business = _validate_text(data.get("business"), "business", MAX_BUSINESS_CHARS) or ""
    theses = _validate_theses(data.get("theses"))
    invalidation = _validate_text(data.get("invalidation"), "invalidation", MAX_INVALIDATION_CHARS)
    risk = _validate_text(data.get("risk"), "risk", MAX_RISK_CHARS)
    numbers = _validate_text(data.get("numbers"), "numbers", MAX_NUMBERS_CHARS)
    info_source = _validate_choice(data.get("info_source"), "info_source", INFO_SOURCES)
    surface = _validate_choice(data.get("surface"), "surface", VALID_SURFACES) or DEFAULT_SURFACE
    months = _validate_months(data.get("review_months"))

    now = _utc_now()
    today = kst_today(now)
    row = ResearchNote(
        user_id=int(user_id),
        ticker=ticker,
        business=business,
        theses_json=json.dumps(theses, ensure_ascii=False),
        invalidation=invalidation,
        risk=risk,
        numbers=numbers,
        info_source=info_source,
        surface=surface,
        review_on=add_months(today, months),
        created_at=now,
    )
    db.session.add(row)
    db.session.commit()
    return _dicts(int(user_id), [row], today)[0]


def list_research(user_id: int, *, limit=DEFAULT_LIST_LIMIT, before=None, ticker=None) -> dict:
    """The caller's own notes, newest first → ``{notes, next_before}``.

    Same id-cursor contract as observation notes (``id desc`` + ``id <
    before``). Each note carries ``due`` and ``outcome``.
    """
    limit = _clamp_int(limit, default=DEFAULT_LIST_LIMIT, maximum=MAX_LIST_LIMIT)
    q = ResearchNote.query.filter(ResearchNote.user_id == int(user_id))
    cursor = _optional_int(before)
    if cursor is not None:
        q = q.filter(ResearchNote.id < cursor)
    if ticker:
        normalized = normalize_ticker(str(ticker))
        if normalized:
            q = q.filter(ResearchNote.ticker == normalized)
    rows = q.order_by(ResearchNote.id.desc()).limit(limit + 1).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    return {
        "notes": _dicts(int(user_id), rows, kst_today()),
        "next_before": int(rows[-1].id) if (has_more and rows) else None,
    }


def research_overview(user_id: int) -> dict:
    """What the research page opens on.

    ``due``      — notes whose review day has come and that are not scored,
                   oldest review day first.
    ``counts``   — notes · scored · due · waiting (review day still ahead).
    ``judgment`` — per *thesis* verdict × the note's outcome, counts only:
                   ``{"right": {"gain", "loss", "flat", "open"}, "wrong": {…}}``.
    ``unknown``  — theses scored 모름.
    ``by_source``— per info source (+ ``none``): right / wrong / unknown counts.
    """
    uid = int(user_id)
    today = kst_today()
    rows = (
        ResearchNote.query.filter(ResearchNote.user_id == uid)
        .order_by(ResearchNote.id.desc())
        .limit(OVERVIEW_ROW_CAP)
        .all()
    )
    outcomes = _outcomes(uid, rows)

    due_rows = sorted(
        (r for r in rows if r.is_due(today)),
        key=lambda r: (r.review_on, r.id),
    )
    judgment = {v: {o: 0 for o in OUTCOMES} for v in ("right", "wrong")}
    by_source = {s: {v: 0 for v in VERDICTS} for s in (*INFO_SOURCES, "none")}
    unknown = 0
    scored = 0
    for r in rows:
        if r.reviewed_at is None:
            continue
        scored += 1
        outcome = outcomes.get(r.id, "open")
        source = r.info_source if r.info_source in INFO_SOURCES else "none"
        for v in r.verdicts_list():
            by_source[source][v] += 1
            if v == "unknown":
                unknown += 1
            else:
                judgment[v][outcome] += 1

    return {
        "due": [_with_outcome(r.to_dict(today=today), outcomes.get(r.id)) for r in due_rows],
        "counts": {
            "notes": len(rows),
            "scored": scored,
            "due": len(due_rows),
            "waiting": sum(1 for r in rows if r.reviewed_at is None and not r.is_due(today)),
        },
        "judgment": judgment,
        "unknown": unknown,
        "by_source": by_source,
    }


def research_for_ticker(user_id: int, ticker: str) -> dict:
    """The caller's latest research on one ticker → ``{ticker, count, note}``.

    ``/pre-trade`` shows it above the questions so 이유·틀린 선 are read from
    what was written cold, before the moment of buying.
    """
    normalized = normalize_ticker(str(ticker or ""))
    if not normalized:
        raise ValueError("ticker is required")
    q = ResearchNote.query.filter(
        ResearchNote.user_id == int(user_id), ResearchNote.ticker == normalized
    )
    count = q.count()
    latest = q.order_by(ResearchNote.id.desc()).first()
    return {
        "ticker": normalized,
        "count": int(count),
        "note": _dicts(int(user_id), [latest], kst_today())[0] if latest else None,
    }


def get_research(note_id: int, user_id: int) -> dict:
    row = _load_owned(note_id, user_id)
    return _dicts(int(user_id), [row], kst_today())[0]


def delete_research(note_id: int, user_id: int) -> int:
    """Hard delete. The form itself has no edit path — like observation
    notes, a record that can be rewritten later stops being a mirror."""
    row = _load_owned(note_id, user_id)
    deleted = int(row.id)
    db.session.delete(row)
    db.session.commit()
    return deleted


def review_research(note_id: int, user_id: int, data) -> dict:
    """Score a note: one verdict per thesis, plus an optional line.

    Once only. The card shows the result on the user's own fills after a
    score is saved, so a second scoring would be done with hindsight — the
    money deciding whether the reason was right (legal-kr-fintech agent
    review 2026-10-15 — not attorney sign-off). Same rule as the form itself: what was written stands.
    Scoring before the review day is allowed — the day is a reminder.
    """
    if not isinstance(data, dict):
        raise ValueError("body must be a JSON object")
    row = _load_owned(note_id, user_id)
    if row.reviewed_at is not None:
        raise ValueError("this note is already scored")
    verdicts = data.get("verdicts")
    theses = row.theses_list()
    if not isinstance(verdicts, list) or len(verdicts) != len(theses):
        raise ValueError(f"verdicts must be a list of {len(theses)} entries")
    for v in verdicts:
        if v not in VERDICTS:
            raise ValueError(f"verdict must be one of {', '.join(VERDICTS)}")
    row.verdicts_json = json.dumps(list(verdicts))
    row.review_note = _validate_text(data.get("note"), "note", MAX_REVIEW_NOTE_CHARS)
    row.reviewed_at = _utc_now()
    db.session.commit()
    return _dicts(int(user_id), [row], kst_today())[0]


# ── Outcome from the user's own fills ────────────────────────────────

def _sold_after(traded_at: datetime, written_at: datetime | None) -> bool:
    """Did this sale happen at or after the note was written?

    ``created_at`` and timed fills are naive-UTC instants and compare as
    such. A date-only fill is stored as its KST date at 00:00, unshifted
    (``services.imports.kst_to_utc``), and has no time of day: it counts
    when that date is the note's KST day or later — the calendar-day rule
    of ``pre_trade.friction_outcome._at_or_after``.

    2026-10-15: both sides used to be cut to their UTC date, so a note
    written 00:00–09:00 KST took a sale from the previous KST day — before
    the note existed — as its result.
    """
    if written_at is None or traded_at >= written_at:
        return True
    return is_date_only(traded_at) and traded_at.date() >= (written_at + _KST_OFFSET).date()


def _outcomes(user_id: int, rows: list[ResearchNote]) -> dict[int, str]:
    """note id → gain / loss / flat / open, from SELLs of the same ticker
    at or after the moment the note was written (``_sold_after``)."""
    tickers = {r.ticker for r in rows if r.ticker}
    if not tickers:
        return {}
    sells: dict[str, list[tuple[datetime, float]]] = {}
    q = TradeHistory.query.filter(
        TradeHistory.user_id == int(user_id),
        func.upper(TradeHistory.action) == _DISPOSAL_ACTION,
    )
    for t in q.all():
        if (t.source or "") in REGISTRATION_SOURCES or not t.traded_at or not t.ticker:
            continue
        tk = normalize_ticker(t.ticker) or t.ticker.upper()
        if tk not in tickers:
            continue
        try:
            pnl = float(t.pnl or 0.0)
        except (TypeError, ValueError):
            pnl = 0.0
        sells.setdefault(tk, []).append((t.traded_at, pnl))

    out: dict[int, str] = {}
    for r in rows:
        after = [p for at, p in sells.get(r.ticker, []) if _sold_after(at, r.created_at)]
        if not after:
            out[r.id] = "open"
            continue
        total = sum(after)
        out[r.id] = "gain" if total > 0 else "loss" if total < 0 else "flat"
    return out


def _with_outcome(d: dict, outcome: str | None) -> dict:
    d["outcome"] = outcome or "open"
    return d


def _dicts(user_id: int, rows: list[ResearchNote], today: date) -> list[dict]:
    outcomes = _outcomes(user_id, rows)
    return [_with_outcome(r.to_dict(today=today), outcomes.get(r.id)) for r in rows]


# ── Validation ───────────────────────────────────────────────────────

def _validate_ticker(raw) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("ticker is required")
    normalized = normalize_ticker(raw.strip())
    if not normalized:
        raise ValueError("ticker is required")
    if len(normalized) > TICKER_MAX_LEN:
        raise ValueError(f"ticker must be at most {TICKER_MAX_LEN} characters")
    return normalized


def _validate_text(raw, field: str, max_chars: int, *, required: bool = False) -> str | None:
    if raw is None:
        if required:
            raise ValueError(f"{field} is required")
        return None
    if not isinstance(raw, str):
        raise ValueError(f"{field} must be text")
    text = raw.strip()
    if not text:
        if required:
            raise ValueError(f"{field} is required")
        return None
    if len(text) > max_chars:
        raise ValueError(f"{field} must be at most {max_chars} characters")
    return text


def _validate_theses(raw) -> list[str]:
    if not isinstance(raw, list):
        raise ValueError("theses must be a list")
    out: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            raise ValueError("theses must be a list of text")
        text = item.strip()
        if not text:
            continue
        if len(text) > MAX_THESIS_CHARS:
            raise ValueError(f"each thesis must be at most {MAX_THESIS_CHARS} characters")
        out.append(text)
    if not (MIN_THESES <= len(out) <= MAX_THESES):
        raise ValueError(f"theses must have {MIN_THESES} to {MAX_THESES} entries")
    return out


def _validate_choice(raw, field: str, allowed: tuple[str, ...]) -> str | None:
    if raw is None or raw == "":
        return None
    if raw not in allowed:
        raise ValueError(f"{field} must be one of {', '.join(allowed)}")
    return raw


def _validate_months(raw) -> int:
    if raw is None or raw == "":
        return DEFAULT_REVIEW_MONTHS
    if isinstance(raw, bool) or not isinstance(raw, int) or raw not in REVIEW_MONTHS:
        raise ValueError(f"review_months must be one of {REVIEW_MONTHS}")
    return raw


# ── Internals ────────────────────────────────────────────────────────

def _load_owned(note_id, user_id) -> ResearchNote:
    nid = _optional_int(note_id)
    row = (
        ResearchNote.query.filter(
            ResearchNote.id == nid, ResearchNote.user_id == int(user_id)
        ).first()
        if nid is not None
        else None
    )
    if row is None:
        raise LookupError("research note not found")
    return row


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _optional_int(raw) -> int | None:
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _clamp_int(raw, *, default: int, maximum: int) -> int:
    val = _optional_int(raw)
    if val is None:
        return default
    return max(1, min(val, maximum))
