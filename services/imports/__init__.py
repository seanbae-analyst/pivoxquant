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
# calendar date is left alone.
_ACCOUNT_DASHED = re.compile(r"\d{2,}-\d{2,}-\d{2,}")
_ACCOUNT_LONG = re.compile(r"\d{8,}")
_ISO_DATE = re.compile(r"^(19|20)\d{2}-(0?[1-9]|1[0-2])-(0?[1-9]|[12]\d|3[01])$")
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
    traded_at: datetime | None = None
    confidence: float = 1.0
    raw_snippet: str = ""
    skip_reason: str | None = None
    extra: dict = field(default_factory=dict)


def utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def today_naive() -> datetime:
    """Today at 00:00 UTC (naive). Used when a fill has no date."""
    return utcnow_naive().replace(hour=0, minute=0, second=0, microsecond=0)


def mask_sensitive(text: str | None, limit: int = RAW_SNIPPET_MAX) -> str:
    """Mask account-number patterns and cap the length for storage."""
    if not text:
        return ""
    s = " ".join(str(text).split())
    s = _ACCOUNT_DASHED.sub(lambda m: m.group(0) if _ISO_DATE.match(m.group(0)) else "***", s)
    s = _ACCOUNT_LONG.sub(lambda m: m.group(0) if _COMPACT_DATE.match(m.group(0)) else "***", s)
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
    # 2026-09-01, 2026/09/01, 2026.09.01 (+ optional time)
    re.compile(
        r"(?P<y>\d{4})[-./](?P<m>\d{1,2})[-./](?P<d>\d{1,2})"
        r"(?:[ T](?P<H>\d{1,2}):(?P<M>\d{2})(?::(?P<S>\d{2}))?)?"
    ),
    # 20260901 (+ optional time)
    re.compile(
        r"(?<!\d)(?P<y>\d{4})(?P<m>\d{2})(?P<d>\d{2})(?!\d)"
        r"(?:[ T]?(?P<H>\d{1,2}):(?P<M>\d{2})(?::(?P<S>\d{2}))?)?"
    ),
    # 9월 1일 / 09월 01일 (year = current) (+ optional time)
    re.compile(
        r"(?P<m>\d{1,2})월\s*(?P<d>\d{1,2})일"
        r"(?:\s*(?P<H>\d{1,2}):(?P<M>\d{2})(?::(?P<S>\d{2}))?)?"
    ),
)
_TIME_ONLY = re.compile(r"(?<![\d:])(?P<H>\d{1,2}):(?P<M>\d{2})(?::(?P<S>\d{2}))?(?![\d:])")


def parse_datetime(value, time_value=None) -> datetime | None:
    """Parse a date (+ optional separate time) into a naive datetime.

    Accepts ``datetime``/``date`` objects (openpyxl / pandas cells) and the
    string shapes listed in the design: ``YYYY-MM-DD`` · ``/`` · ``.`` ·
    ``YYYYMMDD``, each with an optional ``HH:MM[:SS]``.
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value.replace(tzinfo=None) if value.tzinfo else value
    elif hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
        dt = datetime(value.year, value.month, value.day)
    else:
        s = str(value).strip()
        dt = None
        for pat in _DATE_PATTERNS:
            m = pat.search(s)
            if not m:
                continue
            g = m.groupdict()
            year = int(g["y"]) if g.get("y") else utcnow_naive().year
            try:
                dt = datetime(
                    year, int(g["m"]), int(g["d"]),
                    int(g["H"] or 0), int(g["M"] or 0), int(g["S"] or 0),
                )
            except ValueError:
                return None
            break
        if dt is None:
            return None
    if time_value not in (None, ""):
        t = _parse_time(time_value)
        if t is not None:
            dt = dt.replace(hour=t[0], minute=t[1], second=t[2])
    return dt


def _parse_time(value) -> tuple[int, int, int] | None:
    if hasattr(value, "hour") and hasattr(value, "minute"):
        return (value.hour, value.minute, getattr(value, "second", 0) or 0)
    m = _TIME_ONLY.search(str(value))
    if not m:
        digits = re.sub(r"\D", "", str(value))
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
    return (h, mi, se)


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


def kst_to_utc(dt: datetime) -> datetime:
    """Broker wall-clock (Asia/Seoul) → naive UTC. Date-only values (00:00)
    are left alone so they line up with manual entries, which stamp
    ``YYYY-MM-DD`` as 00:00 UTC (routes/portfolio.py::_parse_purchase_date)."""
    if dt.hour == 0 and dt.minute == 0 and dt.second == 0:
        return dt
    return dt - KST_OFFSET


_TZ_SUFFIX = re.compile(r"(Z|[+-]\d{2}:?\d{2})$")


def parse_datetime_tz(value) -> tuple[datetime | None, bool]:
    """Like :func:`parse_datetime` but honours an explicit zone.

    Returns ``(naive_dt, is_utc)``: ``True`` when the input carried ``Z`` or
    an offset (converted to UTC), ``False`` when it was wall-clock text the
    caller should treat as KST.
    """
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None), True
    if isinstance(value, str) and _TZ_SUFFIX.search(value.strip()):
        try:
            aware = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
            if aware.tzinfo is not None:
                return aware.astimezone(timezone.utc).replace(tzinfo=None), True
        except ValueError:
            pass
    return parse_datetime(value), False


__all__ = [
    "RawTrade",
    "ImportParseError",
    "mask_sensitive",
    "parse_number",
    "parse_datetime",
    "parse_datetime_tz",
    "amount_ok",
    "ticker_ok",
    "traded_at_ok",
    "kst_to_utc",
    "MAX_AMOUNT",
    "side_from_text",
    "utcnow_naive",
    "today_naive",
    "RAW_SNIPPET_MAX",
]
