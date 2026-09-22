"""Observation notes service — create / list / read / delete / by-ticker.

설계 docs/design/observation-notes_2026-09-22.md §3. 검증(캡·정규화·비객체
body)은 전부 여기에 있고 라우트는 얇다 — services/pre_trade/friction.py 와
동일한 분업.

Ownership
---------
모든 읽기·삭제는 ``user_id`` 를 SQL 층에서 건다. 남의 노트는 존재 자체를
노출하지 않는다 — 조회 실패와 타인 소유는 똑같이 ``LookupError`` 다
(라우트가 둘 다 404 로 옮긴다).

Quotes
------
시세를 부르지 않는다. 3축(멈춤·기록·거울)과 같은 규칙이고, 벤더 시세 표시가
``MARKET_DATA_DISPLAY_ENABLED`` 뒤에 있는 것과도 무관하게 성립한다.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

from extensions import db
from models import ObservationNote
from models.observation_note import (
    DEFAULT_SOURCE,
    MAX_TAGS,
    MAX_TAG_CHARS,
    MAX_TICKERS,
    TICKER_MAX_LEN,
    VALID_SOURCES,
)
# 본문 캡은 멈춤 기록과 같은 숫자를 쓴다 — 유저가 두 표면에서 서로 다른
# 한도를 만나는 게 더 이상하다. 상수 두 벌을 만들지 않는다.
from services.pre_trade.friction import MAX_TEXT_CHARS
from services.ticker_normalizer import normalize_ticker

logger = logging.getLogger(__name__)

DEFAULT_LIST_LIMIT = 50
MAX_LIST_LIMIT = 200

# by-ticker 기본 창 — /pre-trade 가 "최근 30일 관찰 노트" 로 되비추는 폭.
DEFAULT_TICKER_DAYS = 30
MAX_TICKER_DAYS = 365
DEFAULT_TICKER_LIMIT = 5
MAX_TICKER_LIMIT = 50


# ── Public surface ───────────────────────────────────────────────────

def create_note(
    user_id: int,
    body,
    tickers=None,
    tags=None,
    source=None,
) -> dict:
    """Insert one note. Returns the ``to_dict()`` payload.

    Raises ``ValueError`` when:

    * ``body`` is not text, is blank after strip, or exceeds
      :data:`MAX_TEXT_CHARS`,
    * ``tickers`` is not a list or holds more than :data:`MAX_TICKERS`
      entries (each normalized; a blank entry is dropped),
    * ``tags`` is not a list or holds more than :data:`MAX_TAGS` entries,
      or any tag exceeds :data:`MAX_TAG_CHARS` after strip,
    * ``source`` is outside :data:`VALID_SOURCES`.
    """
    clean_body = _validate_body(body)
    clean_tickers = _validate_tickers(tickers)
    clean_tags = _validate_tags(tags)
    clean_source = _validate_source(source)

    row = ObservationNote(
        user_id=int(user_id),
        body=clean_body,
        tickers_json=json.dumps(clean_tickers, ensure_ascii=False),
        tags_json=json.dumps(clean_tags, ensure_ascii=False),
        source=clean_source,
        created_at=_utc_now(),
    )
    db.session.add(row)
    db.session.commit()
    return row.to_dict()


def list_notes(
    user_id: int,
    *,
    limit=DEFAULT_LIST_LIMIT,
    before=None,
    ticker=None,
    tag=None,
) -> dict:
    """The caller's own notes, newest first → ``{notes, next_before}``.

    ``before`` is an id cursor (strictly older rows). ``limit`` is clamped to
    ``[1, MAX_LIST_LIMIT]`` so a malformed query can't pull an unbounded set.
    ``next_before`` is the id to pass on the next page, or ``None`` when the
    caller has reached the end.
    """
    limit = _clamp_int(limit, default=DEFAULT_LIST_LIMIT, maximum=MAX_LIST_LIMIT)

    q = ObservationNote.query.filter(ObservationNote.user_id == int(user_id))

    cursor = _optional_int(before)
    if cursor is not None:
        q = q.filter(ObservationNote.id < cursor)
    if ticker:
        normalized = normalize_ticker(str(ticker))
        if normalized:
            q = _filter_json_element(q, ObservationNote.tickers_json, normalized)
    if tag:
        tag_str = str(tag).strip()[:MAX_TAG_CHARS]
        if tag_str:
            q = _filter_json_element(q, ObservationNote.tags_json, tag_str)

    # limit + 1 so we know whether another page exists without a COUNT.
    rows = (
        q.order_by(ObservationNote.created_at.desc(), ObservationNote.id.desc())
        .limit(limit + 1)
        .all()
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_before = int(rows[-1].id) if (has_more and rows) else None
    return {"notes": [r.to_dict() for r in rows], "next_before": next_before}


def get_note(note_id: int, user_id: int) -> dict:
    """One note the caller owns. Raises ``LookupError`` on miss / wrong owner."""
    return _load_owned(note_id, user_id).to_dict()


def delete_note(note_id: int, user_id: int) -> int:
    """Hard-delete one note the caller owns. Returns the deleted id.

    Append-only + delete is the whole policy — there is no edit path
    (설계 §8 Q1). Raises ``LookupError`` on miss / wrong owner.
    """
    row = _load_owned(note_id, user_id)
    deleted_id = int(row.id)
    db.session.delete(row)
    db.session.commit()
    return deleted_id


def notes_for_ticker(
    user_id: int,
    ticker: str,
    *,
    days=DEFAULT_TICKER_DAYS,
    limit=DEFAULT_TICKER_LIMIT,
) -> dict:
    """Recent notes the caller wrote about one ticker → ``{ticker, count, notes}``.

    ``count`` is how many notes fall inside the window (before ``limit``
    truncates the excerpt list), so /pre-trade can say "3개 · 「…」" honestly
    while rendering only the first few.
    """
    normalized = normalize_ticker(str(ticker or ""))
    if not normalized:
        raise ValueError("ticker is required")

    days = _clamp_int(days, default=DEFAULT_TICKER_DAYS, maximum=MAX_TICKER_DAYS)
    limit = _clamp_int(limit, default=DEFAULT_TICKER_LIMIT, maximum=MAX_TICKER_LIMIT)
    since = _utc_now() - timedelta(days=days)

    q = _filter_json_element(
        ObservationNote.query.filter(
            ObservationNote.user_id == int(user_id),
            ObservationNote.created_at >= since,
        ),
        ObservationNote.tickers_json,
        normalized,
    )
    count = q.count()
    rows = (
        q.order_by(ObservationNote.created_at.desc(), ObservationNote.id.desc())
        .limit(limit)
        .all()
    )
    return {
        "ticker": normalized,
        "count": int(count),
        "notes": [r.to_dict() for r in rows],
    }


# ── Validation ───────────────────────────────────────────────────────

def _validate_body(body) -> str:
    if body is None or not isinstance(body, str):
        raise ValueError("body must be text")
    stripped = body.strip()
    if not stripped:
        raise ValueError("body is required")
    if len(stripped) > MAX_TEXT_CHARS:
        raise ValueError(f"body must be at most {MAX_TEXT_CHARS} characters")
    return stripped


def _validate_tickers(tickers) -> list:
    if tickers is None:
        return []
    if not isinstance(tickers, list):
        raise ValueError("tickers must be a list")
    if len(tickers) > MAX_TICKERS:
        raise ValueError(f"tickers must be at most {MAX_TICKERS} entries")
    out: list[str] = []
    for raw in tickers:
        if not isinstance(raw, str):
            raise ValueError("tickers must be a list of text")
        # Canonicalise before storage so a bare "035760" lands as
        # "035760.KQ" — by-ticker lookups normalize the same way, and the
        # journal can render a 종목명 instead of a naked code.
        normalized = normalize_ticker(raw.strip())
        if not normalized:
            continue
        if len(normalized) > TICKER_MAX_LEN:
            raise ValueError(
                f"ticker must be at most {TICKER_MAX_LEN} characters"
            )
        if normalized not in out:
            out.append(normalized)
    return out


def _validate_tags(tags) -> list:
    if tags is None:
        return []
    if not isinstance(tags, list):
        raise ValueError("tags must be a list")
    if len(tags) > MAX_TAGS:
        raise ValueError(f"tags must be at most {MAX_TAGS} entries")
    out: list[str] = []
    for raw in tags:
        if not isinstance(raw, str):
            raise ValueError("tags must be a list of text")
        tag = raw.strip()
        if not tag:
            continue
        if len(tag) > MAX_TAG_CHARS:
            raise ValueError(f"tag must be at most {MAX_TAG_CHARS} characters")
        if tag not in out:
            out.append(tag)
    return out


def _validate_source(source) -> str:
    if source is None or source == "":
        return DEFAULT_SOURCE
    if not isinstance(source, str) or source not in VALID_SOURCES:
        raise ValueError("source must be one of: " + ", ".join(VALID_SOURCES))
    return source


# ── Internals ────────────────────────────────────────────────────────

def _load_owned(note_id: int, user_id: int) -> ObservationNote:
    row = ObservationNote.query.filter(
        ObservationNote.id == _optional_int(note_id),
        ObservationNote.user_id == int(user_id),
    ).first()
    if row is None:
        raise LookupError("observation note not found")
    return row


def _filter_json_element(query, column, value: str):
    """Narrow ``query`` to rows whose JSON-array ``column`` holds ``value``.

    The arrays are small and stored as text, so a LIKE on the *quoted*
    element (``%"AAPL"%``) is an exact element match rather than a substring
    one. LIKE wildcards inside a user-supplied tag are escaped so a tag of
    ``%`` can't widen the match to every row.
    """
    encoded = json.dumps(value, ensure_ascii=False)
    escaped = (
        encoded.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    )
    return query.filter(column.like(f"%{escaped}%", escape="\\"))


def _clamp_int(raw, *, default: int, maximum: int) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    if value < 1:
        return default
    return min(value, maximum)


def _optional_int(raw) -> int | None:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
