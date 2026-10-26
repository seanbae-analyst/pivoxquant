"""Import Inbox parsers + ledger (docs/product/IMPORT_INBOX_DESIGN.md).

Shared pieces live here so ``csv_parser`` / ``text_parser`` / ``dedupe`` /
``ledger`` can import them without a cycle:

- :class:`RawTrade` — the parser-neutral intermediate row.
- :func:`mask_sensitive` — account-number masking applied to every
  ``raw_snippet`` before it is stored (LOCAL_AGENT_LEGAL_RISK §5).
- :func:`parse_number` / :func:`parse_datetime` — tolerant scalar parsers
  shared by both parsers.
- :class:`ImportParseError` — raised for unreadable / unsupported input;
  ``code`` maps 1:1 onto the API error codes in the design.

Nothing in this package reads broker APIs, images or an AI model — the
server only ever sees the file bytes or text the user pasted.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

RAW_SNIPPET_MAX = 300

# Account-number shapes: ``123-45-678901`` style and any 8+ digit run.
# ISO dates (``2026-09-01`` / ``20260901``) share those shapes; they are the
# one thing a fill snippet must keep, so a token that is a plausible
# calendar date is left alone. The hyphen may be any dash a phone or OCR
# hands back (en/em dash, minus, non-breaking hyphen, underscore), and a
# phone number may be spaced or dotted (2026-10-13 — the same gaps as the
# on-device mask, frontend/src/lib/fill-ocr/mask.ts).
_DASH = "[-\u2013\u2014\u2212\u2011_]"
_ACCOUNT_DASHED = re.compile(rf"\d{{2,}}{_DASH}\d{{2,}}{_DASH}\d{{2,}}")
_ACCOUNT_LONG = re.compile(r"\d{8,}")
_PHONE = re.compile(r"(?<!\d)01[016789][ .]\d{3,4}[ .]\d{4}(?!\d)")
_ISO_DATE = re.compile(rf"^(19|20)\d{{2}}{_DASH}(0?[1-9]|1[0-2]){_DASH}(0?[1-9]|[12]\d|3[01])$")
_COMPACT_DATE = re.compile(r"^(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])$")



class ImportParseError(Exception):
    """Input could not be parsed at all (format / encoding)."""

    def __init__(self, code: str, en: str, kr: str):
        super().__init__(en)
        self.code = code
        self.en = en
        self.kr = kr


@dataclass
class RawTrade:
    """One candidate fill as read from a file row or a text line.

    ``skip_reason`` is set (and the other fields may be blank) when the row
    was recognised but is not a fill — deposits, dividends, fees — or when
    a required field could not be read. The route reports these back to
    the user instead of dropping them silently.
    """

    name: str = ""
    code: str = ""
    action: str = ""          # "BUY" | "SELL" (TradeHistory.action data value)
    shares: float = 0.0
    price: float = 0.0
    currency: str | None = None
    # True when ``currency`` is the parser's guess (text line with no 원/₩/$
    # mark: a 6-digit code, a Latin code, a Hangul name) rather than stated
    # by the input. A stated currency is what the price is in, so a ticker of
    # the other currency must not re-label it (routes/imports.py).
    currency_guessed: bool = False
    traded_at: datetime | None = None
    # True when the input printed a time of day for ``traded_at`` (2026-10-15).
    # ``kst_to_utc`` shifts only such a value; one without is a date-only fill.
    # Guessing it from 00:00 made a 09:00 KST fill (00:00 UTC) date-only.
    time_given: bool = False
    confidence: float = 1.0
    raw_snippet: str = ""
    skip_reason: str | None = None
    extra: dict = field(default_factory=dict)


def utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def today_naive() -> datetime:
    """The user's calendar today (Asia/Seoul) at 00:00, naive. Used when a
    fill has no date. Date-only values are stored unshifted (see
    ``kst_to_utc``), so this must be the KST date — the UTC date is
    yesterday between 00:00 and 09:00 KST."""
    return (utcnow_naive() + KST_OFFSET).replace(hour=0, minute=0, second=0, microsecond=0)


def mask_sensitive(text: str | None, limit: int = RAW_SNIPPET_MAX) -> str:
    """Mask account-number patterns and cap the length for storage."""
    if not text:
        return ""
    s = " ".join(str(text).split())
    s = _ACCOUNT_DASHED.sub(lambda m: m.group(0) if _ISO_DATE.match(m.group(0)) else "***", s)
    s = _ACCOUNT_LONG.sub(lambda m: m.group(0) if _COMPACT_DATE.match(m.group(0)) else "***", s)
    s = _PHONE.sub("***", s)
    return s[:limit]


_NUM_STRIP = re.compile(r"[,\s₩$원주株]|USD|KRW|usd|krw")
_NUM = re.compile(r"^[-+]?\d+(?:\.\d+)?$")


def parse_number(value) -> float | None:
    """``"71,200원"`` → 71200.0. Returns None when no number is present."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = _NUM_STRIP.sub("", str(value)).strip()
    if not s:
        return None
    neg = s.startswith("(") and s.endswith(")")
    if neg:
        s = s[1:-1]
    if not _NUM.match(s):
        return None
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


_DATE_PATTERNS = (
    # 2026-09-01, 2026/09/01, 2026.09.01 (+ optional time). The fraction is
    # our own export's isoformat() (a timed fill stored at 00:00:00.000001 —
    # see ``as_timed``) and must survive a re-import.
    re.compile(
        r"(?P<y>\d{4})[-./](?P<m>\d{1,2})[-./](?P<d>\d{1,2})"
        r"(?:[ T](?P<H>\d{1,2}):(?P<M>\d{2})(?::(?P<S>\d{2})(?:\.(?P<f>\d{1,6}))?)?)?"
    ),
    # 20260901 (+ optional time)
    re.compile(
        r"(?<!\d)(?P<y>\d{4})(?P<m>\d{2})(?P<d>\d{2})(?!\d)"
        r"(?:[ T]?(?P<H>\d{1,2}):(?P<M>\d{2})(?::(?P<S>\d{2}))?)?"
    ),
    # 2025년 3월 4일 / 9월 1일 (no year → current) (+ optional time).
    # 2026-10-13: the 년 was not read, so "2025년 03월 04일" became 2026-03-04.
    re.compile(
        r"(?:(?P<y>\d{4})년\s*)?(?P<m>\d{1,2})월\s*(?P<d>\d{1,2})일"
        r"(?:\s*(?P<H>\d{1,2}):(?P<M>\d{2})(?::(?P<S>\d{2}))?)?"
    ),
)
_TIME_ONLY = re.compile(r"(?<![\d:])(?P<H>\d{1,2}):(?P<M>\d{2})(?::(?P<S>\d{2}))?(?![\d:])")

# 오전/오후 · AM/PM next to a printed time (2026-10-21). Korean broker texts
# and Excel time cells print a 12-hour clock ("오후 2:05:00"); read without the
# marker, a 14:05 fill became 02:05 — and since dedupe compares two printed
# times (2026-10-15), the same fill pasted once as "14:05" and once as
# "오후 2:05" was stored twice.
_MERIDIEM_BEFORE = re.compile(r"(?:(오전|오후)|(?<![A-Za-z])(AM|PM|A\.M\.|P\.M\.))\s*$", re.IGNORECASE)
_MERIDIEM_AFTER = re.compile(r"^\s*(AM|PM|A\.M\.|P\.M\.)(?![A-Za-z])", re.IGNORECASE)


def _meridiem(text: str, start: int, end: int) -> str | None:
    """``"am"`` / ``"pm"`` when a marker sits right before ``text[start:end]``
    (오후 2:05 · PM 2:05) or right after it (2:05 PM), else None."""
    m = _MERIDIEM_BEFORE.search(text[max(0, start - 6):start])
    mark = (m.group(1) or m.group(2)) if m else None
    if mark is None:
        a = _MERIDIEM_AFTER.match(text[end:end + 7])
        mark = a.group(1) if a else None
    if mark is None:
        return None
    return "pm" if mark in ("오후",) or mark.upper().startswith("P") else "am"


def meridiem_hour(text: str, start: int, end: int, hour: int) -> int:
    """The 24-hour value of ``hour`` printed at ``text[start:end]``. A printed
    13~23 is already 24-hour (오후 14:05) and stays."""
    mark = _meridiem(text, start, end)
    if mark == "pm" and hour < 12:
        return hour + 12
    if mark == "am" and hour == 12:
        return 0
    return hour


def parse_datetime(value, time_value=None) -> datetime | None:
    """Parse a date (+ optional separate time) into a naive datetime.

    Accepts ``datetime``/``date`` objects (openpyxl / pandas cells) and the
    string shapes listed in the design: ``YYYY-MM-DD`` · ``/`` · ``.`` ·
    ``YYYYMMDD``, each with an optional ``HH:MM[:SS]``.
    """
    return parse_datetime_has_time(value, time_value)[0]


def parse_datetime_has_time(value, time_value=None) -> tuple[datetime | None, bool]:
    """:func:`parse_datetime` plus whether the input gave a time of day.

    Text: a time was printed (``HH:MM`` in the value or a parsed
    ``time_value``). A ``datetime`` cell carries no such fact — openpyxl
    returns a date-formatted cell as 00:00 — so there a non-midnight time is
    the only evidence of one (a 00:00:00 cell reads as date-only).
    """
    if value is None or value == "":
        return None, False
    if isinstance(value, datetime):
        dt = value.replace(tzinfo=None) if value.tzinfo else value
        has_time = not is_date_only(dt)
    elif hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
        dt, has_time = datetime(value.year, value.month, value.day), False
    else:
        s = str(value).strip()
        dt, has_time = None, False
        for pat in _DATE_PATTERNS:
            m = pat.search(s)
            if not m:
                continue
            g = m.groupdict()
            year = int(g["y"]) if g.get("y") else utcnow_naive().year
            hour = int(g["H"] or 0)
            if g.get("H") is not None:
                hour = meridiem_hour(s, m.start("H"), m.end(), hour)
            try:
                dt = datetime(
                    year, int(g["m"]), int(g["d"]),
                    hour, int(g["M"] or 0), int(g["S"] or 0),
                    int((g.get("f") or "0").ljust(6, "0")),
                )
            except ValueError:
                return None, False
            has_time = g.get("H") is not None
            if not has_time:
                # "2026-09-01 오후 2:05:00" — the marker keeps the date pattern
                # from taking the time; read it only with a marker beside it.
                rest = s[m.end():]
                tm = _TIME_ONLY.search(rest)
                if tm and _meridiem(rest, tm.start(), tm.end()):
                    h = meridiem_hour(rest, tm.start(), tm.end(), int(tm.group("H")))
                    mi, se = int(tm.group("M")), int(tm.group("S") or 0)
                    if h < 24 and mi < 60 and se < 60:
                        dt = dt.replace(hour=h, minute=mi, second=se)
                        has_time = True
            break
        if dt is None:
            return None, False
    if time_value not in (None, ""):
        t = _parse_time(time_value)
        if t is not None:
            dt = dt.replace(hour=t[0], minute=t[1], second=t[2], microsecond=0)
            has_time = True
    return dt, has_time


def _parse_time(value) -> tuple[int, int, int] | None:
    if hasattr(value, "hour") and hasattr(value, "minute"):
        return (value.hour, value.minute, getattr(value, "second", 0) or 0)
    m = _TIME_ONLY.search(str(value))
    if not m:
        digits = re.sub(r"\D", "", str(value))
        # A time cell stored as a number lost its leading zero: 93000 = 09:30:00.
        if len(digits) in (3, 5):
            digits = "0" + digits
        if len(digits) in (4, 6):
            h, mi = int(digits[:2]), int(digits[2:4])
            se = int(digits[4:6]) if len(digits) == 6 else 0
            if h < 24 and mi < 60 and se < 60:
                return (h, mi, se)
        return None
    h, mi = int(m.group("H")), int(m.group("M"))
    se = int(m.group("S") or 0)
    if h > 23 or mi > 59 or se > 59:
        return None
    return (meridiem_hour(str(value), m.start(), m.end(), h), mi, se)


_NOT_A_FILL = re.compile(r"취소|정정|환전")


def side_from_text(value) -> str | None:
    """Map a broker "구분" cell / notification word to a buy / sell side value.

    Anything else (입금·출금·배당·이자·수수료·환전 …) → None, so the caller
    records a skip reason instead of guessing.
    """
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    # A cancelled / amended order or a currency exchange is not a fill:
    # "매수취소" read as 매수, "환전매도" as 매도 (2026-10-13 bug hunt).
    if _NOT_A_FILL.search(s):
        return None
    low = s.lower()
    if "매수" in s or re.search(r"\b(buy|bought|long)\b", low) or low in ("b", "매입"):
        return "BUY"  # // legal-ok — trade action data value, not user copy
    if "매도" in s or re.search(r"\b(sell|sold|short)\b", low) or low == "s":
        return "SELL"  # // legal-ok — trade action data value, not user copy
    return None



# ── shared validators (review 2026-09-14) ─────────────────────────────
# Mirrors routes/portfolio.py::_validate_amount (finite, 0 < v <= 1e9) so an
# imported fill can never carry NaN / inf / 1e300 into positions; a length /
# charset rule for tickers so a Postgres String(20) column never raises; a
# sane range for fill timestamps; and the KST → UTC shift, because broker
# apps and files print Korean wall-clock while trade_history stores naive UTC.
MAX_AMOUNT = 1e9
MIN_FILL_YEAR = 1990
KST_OFFSET = timedelta(hours=9)
TICKER_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,19}$")


def amount_ok(v) -> bool:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return False
    return math.isfinite(f) and 0 < f <= MAX_AMOUNT


def ticker_ok(t) -> bool:
    return isinstance(t, str) and bool(TICKER_RE.match(t))


def traded_at_ok(dt) -> bool:
    if not isinstance(dt, datetime):
        return False
    return dt.year >= MIN_FILL_YEAR and dt <= utcnow_naive() + timedelta(days=1)


# ── stored fill time: date-only vs timed (2026-10-15) ─────────────────
# ``traded_at`` has no "time known" column. A date-only fill is stored as its
# KST date at exactly 00:00:00.000000, unshifted — the shape manual entries
# use (routes/portfolio.py::_parse_purchase_date stamps ``YYYY-MM-DD`` at
# midnight). A timed fill is a UTC instant; one that lands exactly on UTC
# midnight (09:00:00 KST — the KRX open) is stored 1 µs later, so that shape
# stays unambiguous for every reader that tests all four fields
# (``is_date_only`` here, ledger, pre_trade.friction_outcome._at_or_after,
# research_notes). Rows stored before this convention keep their 00:00.

def is_date_only(dt: datetime) -> bool:
    """A stored ``traded_at`` with no time of day (see the block above)."""
    return (dt.hour, dt.minute, dt.second, dt.microsecond) == (0, 0, 0, 0)


def as_timed(dt: datetime) -> datetime:
    """Store a timed UTC instant so it can never read as date-only."""
    return dt + timedelta(microseconds=1) if is_date_only(dt) else dt


def kst_to_utc(dt: datetime, *, has_time: bool) -> datetime:
    """Broker wall-clock (Asia/Seoul) → naive UTC. ``has_time`` is the
    parser's word that the input printed a time (``RawTrade.time_given``);
    without one the value is a date-only fill and stays its KST date at
    00:00. The 00:00 itself is no evidence either way: 09:00 KST is 00:00
    UTC, and a US fill at 00:00 KST must still move back 9 hours."""
    if not has_time:
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return as_timed(dt - KST_OFFSET)


_TZ_SUFFIX = re.compile(r"(Z|[+-]\d{2}:?\d{2})$")


def parse_datetime_tz(value) -> tuple[datetime | None, bool, bool]:
    """Like :func:`parse_datetime` but honours an explicit zone.

    Returns ``(naive_dt, is_utc, has_time)``: ``is_utc`` is ``True`` when the
    input carried ``Z`` or an offset (converted to UTC, and timed), ``False``
    when it was wall-clock text the caller should treat as KST; ``has_time``
    as in :func:`parse_datetime_has_time`.
    """
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None), True, True
    if isinstance(value, str) and _TZ_SUFFIX.search(value.strip()):
        try:
            aware = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            if aware.tzinfo is not None:
                return aware.astimezone(timezone.utc).replace(tzinfo=None), True, True
        except ValueError:
            pass
    dt, has_time = parse_datetime_has_time(value)
    return dt, False, has_time


__all__ = [
    "RawTrade",
    "ImportParseError",
    "mask_sensitive",
    "parse_number",
    "parse_datetime",
    "meridiem_hour",
    "parse_datetime_has_time",
    "parse_datetime_tz",
    "amount_ok",
    "ticker_ok",
    "traded_at_ok",
    "kst_to_utc",
    "is_date_only",
    "as_timed",
    "MAX_AMOUNT",
    "side_from_text",
    "utcnow_naive",
    "today_naive",
    "RAW_SNIPPET_MAX",
]
