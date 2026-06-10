"""Pre-Trade Friction service — start / check / proceed / cancel a self-imposed cooldown.

Legal posture
-------------
We never block the user's broker call. ``proceed()`` only stamps
``proceeded_at`` on the reflection row — the broker route is invoked
separately by the user, exactly the way it was before this feature
existed. The cooldown is **the user's own** reflection time. We extend
it under high-vol/FOMC windows because *that's what the user signed up
for*, never as a "do not trade" recommendation.

Inputs
------
``intended_side`` is a free-text label the user picks for their own
record. We accept upper or lower case and normalise to the upper-case
literal ``BUY`` / ``SELL`` for storage. Non-allowed values become
``None`` so the row stays factually accurate.

Auto-extend triggers
--------------------
2026-05-22 (CEO directive "2분 없애"): the enforced cooldown is now 0 —
both DEFAULT_ and EXTENDED_COOLDOWN_SECONDS are 0, so the reflection is
immediately "ready" after the 7 questions (no timed wait). The 7-question
self-reflection itself is preserved; only the timer is removed. The
auto-extend trigger detection below still runs (and stamps
``auto_extended_reason`` for the audit row) but, with both windows at 0,
it no longer changes the wait. Historically the default was 2 minutes,
extended to 5 minutes when:

* FOMC meeting fires within ±30 minutes (services.market_status hook,
  optional — when the helper is missing this trigger is a no-op).
* VIX > 30 (read from cached fetcher / realtime services where possible).
* The intended ticker has moved more than 5% in the last hour.

Each trigger maps to one of the values in
``models.pre_trade_reflection.AUTO_EXTEND_REASONS``. If none fire we
leave ``auto_extended_reason`` null and use the default duration.
"""
from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from extensions import db
from models import (
    PreTradeReflection,
    MIN_RATIONALE_CHARS,
    DEFAULT_COOLDOWN_SECONDS,
    EXTENDED_COOLDOWN_SECONDS,
)
from services.crypto_service import backend_name, is_encrypted_value
from services.ticker_normalizer import normalize_ticker

logger = logging.getLogger(__name__)

# Finite + bounded guards for user-supplied numerics. Mirrors
# routes/portfolio.py:_validate_amount so a crafted inf / NaN / 1e308 payload
# can't reach the DB — Postgres NUMERIC raises DataError on a non-finite or
# out-of-precision Decimal, which the /start route (catching only ValueError)
# would surface as an uncaught 500 instead of a clean 400.
_MAX_SHARES = 1e9          # well within intended_shares Numeric(20,4)
_MAX_VOLATILITY = 9999.0   # market_volatility_at_request Numeric(8,4) ceiling


# ── Public surface ───────────────────────────────────────────────────

def start_cooldown(
    user_id: int,
    ticker: str,
    side: str | None,
    shares: float | None,
    rationale: str,
    devil_advocate: str | None = None,
    *,
    now: datetime | None = None,
    market_volatility: float | None = None,
) -> dict:
    """Open a fresh reflection row.

    Returns the ``to_dict()`` payload with the new ``id``,
    ``cooldown_ends_at`` and (when an auto-extend trigger fires) a
    populated ``auto_extended_reason``. Raises ``ValueError`` when:

    * ``rationale`` is shorter than :data:`MIN_RATIONALE_CHARS`,
    * ``ticker`` is empty,
    * ``shares`` is negative.
    """
    if not ticker or not str(ticker).strip():
        raise ValueError("ticker is required")
    # Canonicalise before any storage / lookup so a bare "035760" lands as
    # "035760.KQ" (registry-guided) instead of a naked code that the Journal
    # would later render without a company name. Mirrors the portfolio routes.
    ticker = normalize_ticker(str(ticker))
    if not ticker:
        raise ValueError("ticker is required")
    if not rationale or len(rationale.strip()) < MIN_RATIONALE_CHARS:
        raise ValueError(
            f"rationale must be at least {MIN_RATIONALE_CHARS} characters"
        )
    if shares is not None:
        try:
            shares_f = float(shares)
        except (TypeError, ValueError):
            raise ValueError("shares must be a number")
        if not math.isfinite(shares_f):
            raise ValueError("shares must be a finite number")
        if shares_f < 0:
            raise ValueError("shares must be non-negative")
        if shares_f > _MAX_SHARES:
            raise ValueError("shares is out of range")

    now = now or _utc_now()

    reason = _should_extend_cooldown(
        ticker=ticker,
        now=now,
        market_volatility=market_volatility,
    )
    seconds = (
        EXTENDED_COOLDOWN_SECONDS if reason else DEFAULT_COOLDOWN_SECONDS
    )

    side_label = _normalise_side(side)
    shares_dec = _to_decimal(shares)
    # Telemetry, not user input — drop a non-finite / out-of-range snapshot to
    # None rather than 500 the user's reflection on commit.
    sane_vol = _sane_volatility(market_volatility)
    vol_dec = _to_decimal(sane_vol)

    row = PreTradeReflection(
        user_id=user_id,
        intended_ticker=ticker,
        intended_side=side_label,
        intended_shares=shares_dec,
        rationale=rationale.strip(),
        devil_advocate_seen=devil_advocate,
        market_volatility_at_request=vol_dec,
        cooldown_started_at=now,
        cooldown_ends_at=now + timedelta(seconds=seconds),
        auto_extended_reason=reason,
        observed_context_json=_collect_observed_context(
            ticker, now=now, vix_hint=sane_vol,
        ),
    )
    db.session.add(row)
    db.session.commit()
    return row.to_dict(now=now)


# Pagination guard for the Journal feed — keeps a single read bounded
# regardless of what the client sends in ?limit=.
DEFAULT_LIST_LIMIT = 50
MAX_LIST_LIMIT = 200


def list_reflections(user_id: int, *, limit: int = DEFAULT_LIST_LIMIT) -> list[dict]:
    """Return the user's own reflections, newest first, as ``to_dict()`` rows.

    User isolation: every row is filtered on ``user_id == user_id`` at the
    SQL level — a foreign user can never appear in the feed. ``limit`` is
    clamped to ``[1, MAX_LIST_LIMIT]`` so a hostile / malformed query can't
    pull an unbounded result set.
    """
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = DEFAULT_LIST_LIMIT
    if limit < 1:
        limit = DEFAULT_LIST_LIMIT
    limit = min(limit, MAX_LIST_LIMIT)

    now = _utc_now()
    rows = (
        PreTradeReflection.query
        .filter(PreTradeReflection.user_id == int(user_id))
        .order_by(PreTradeReflection.created_at.desc(), PreTradeReflection.id.desc())
        .limit(limit)
        .all()
    )
    return [r.to_dict(now=now) for r in rows]


def check_status(reflection_id: int, user_id: int) -> dict:
    """Return ``to_dict()`` with current ``status`` + ``seconds_remaining``.

    ``user_id`` is mandatory — we never let one user read another's
    reflection. Raises ``LookupError`` on miss / wrong owner.
    """
    row = _load_owned(reflection_id, user_id)
    return row.to_dict(now=_utc_now())


def proceed(reflection_id: int, user_id: int) -> dict:
    """Stamp ``proceeded_at`` once the cooldown has elapsed.

    Returns the updated ``to_dict()``. Raises ``ValueError`` when:

    * cooldown has not elapsed yet,
    * the reflection is already cancelled / proceeded.

    NOTE: we do not invoke the broker here. The frontend pulls this
    return value, then triggers the user's existing broker route
    (``/api/portfolio/position/...`` or ``/api/autotrade/...``) which is
    untouched by this feature.
    """
    row = _load_owned(reflection_id, user_id, for_update=True)
    now = _utc_now()
    if row.cancelled_at is not None:
        raise ValueError("reflection already cancelled")
    if row.proceeded_at is not None:
        raise ValueError("reflection already proceeded")
    if row.seconds_remaining(now) > 0:
        raise ValueError("cooldown has not elapsed yet")
    row.proceeded_at = now
    db.session.commit()
    return row.to_dict(now=now)


def cancel(reflection_id: int, user_id: int) -> dict:
    """Stamp ``cancelled_at`` and end the reflection."""
    row = _load_owned(reflection_id, user_id, for_update=True)
    now = _utc_now()
    if row.cancelled_at is not None:
        # Idempotent — re-cancelling is a no-op for the caller.
        return row.to_dict(now=now)
    if row.proceeded_at is not None:
        raise ValueError("reflection already proceeded")
    row.cancelled_at = now
    db.session.commit()
    return row.to_dict(now=now)


# ── Observed-context snapshot (record-as-spine Phase 2) ─────────────

def _collect_observed_context(
    ticker: str, *, now: datetime, vix_hint: float | None = None,
) -> str | None:
    """JSON snapshot of what the product was showing at reflection time.

    The journal's rationale answers "왜 들어갔나"; this answers "그때 무엇을
    보고 있었나" — the ticker's own POSITIVE/NEGATIVE/NEUTRAL signal label +
    score from SignalCache, the VIX level, and the last-hour move.

    Strictly best-effort: every lookup is wrapped, and a total failure
    returns ``None`` — collection must NEVER block the reflection write.

    Compliance (§17): a FACTUAL record of already-displayed observation
    surfaces. Only the legal label fields are copied — never ``rec_*`` /
    ``take_profit`` / ``stop_loss`` or anything directive.
    """
    ctx: dict[str, Any] = {}

    try:
        from models import SignalCache

        cached = SignalCache.query.filter_by(ticker=ticker).first()
        if cached and cached.data_json:
            sd = json.loads(cached.data_json)
            signal = sd.get("signal")
            if signal in ("POSITIVE", "NEGATIVE", "NEUTRAL"):
                ctx["signal"] = signal
                score = sd.get("score")
                if isinstance(score, (int, float)) and math.isfinite(float(score)):
                    ctx["score"] = float(score)
            sector = sd.get("sector")
            if sector and sector != "Unknown":
                ctx["sector"] = str(sector)[:60]
    except Exception:
        logger.debug("observed-context: signal lookup failed", exc_info=True)

    try:
        vix = vix_hint if vix_hint is not None else _read_vix(now)
        if vix is not None and math.isfinite(float(vix)) and 0 < float(vix) < 200:
            ctx["vix"] = round(float(vix), 2)
    except Exception:
        logger.debug("observed-context: vix lookup failed", exc_info=True)

    try:
        from services.data import realtime as rt  # type: ignore

        fn = getattr(rt, "last_hour_pct_change", None)
        if callable(fn):
            change = fn(ticker)
            if change is not None and math.isfinite(float(change)):
                ctx["change_1h_pct"] = round(float(change), 2)
    except Exception:
        logger.debug("observed-context: 1h-move lookup failed", exc_info=True)

    if not ctx:
        return None
    ctx["captured_at"] = now.isoformat()
    try:
        return json.dumps(ctx, ensure_ascii=False)
    except Exception:
        return None


# ── Auto-extend logic ────────────────────────────────────────────────

# VIX threshold (CBOE convention: > 30 = high-volatility regime).
HIGH_VIX_THRESHOLD = 30.0

# Hourly price-move threshold that flips us to the extended window.
# The user has just typed a rationale into a moving market — give them
# more time to sit with it. 5% is a common circuit-breaker proxy.
BIG_MOVE_PCT_1H = 5.0

# FOMC window — ±30 minutes around the announcement, in seconds.
FOMC_WINDOW_SECONDS = 30 * 60


def _should_extend_cooldown(
    *,
    ticker: str,
    now: datetime,
    market_volatility: float | None,
) -> str | None:
    """Return the reason string to record, or ``None`` to keep default 2 min.

    Resolution order: FOMC → VIX → big move. Each branch is wrapped in
    a try/except because the underlying market data services are
    optional / may rate-limit. A failure to resolve a trigger just
    falls through to the next one — never blocks ``start_cooldown``.
    """
    # 1) FOMC announcement window. Optional dependency — we look up
    #    `services.market_status.fomc_window_active(now)` if it exists.
    if _fomc_window_active(now):
        return "fomc_30min"

    # 2) VIX gate. Caller may pass a snapshot in `market_volatility`;
    #    otherwise we try to read it from the realtime/fetcher layer.
    try:
        vix = market_volatility
        if vix is None:
            vix = _read_vix(now)
        if vix is not None and float(vix) > HIGH_VIX_THRESHOLD:
            return "high_vix"
    except Exception as exc:  # pragma: no cover — defensive
        logger.debug("VIX lookup failed: %s", exc)

    # 3) Last-hour move on the intended ticker.
    try:
        if _ticker_moved_more_than(ticker, BIG_MOVE_PCT_1H, now):
            return "big_move_1h"
    except Exception as exc:  # pragma: no cover — defensive
        logger.debug("price-move lookup failed for %s: %s", ticker, exc)

    return None


# ── Optional market hooks ────────────────────────────────────────────
# Each of these is wrapped so the friction layer can run in tests +
# offline dev without the live data services being wired.

def _fomc_window_active(now: datetime) -> bool:
    """True iff the FOMC announcement is within ±30 min of `now`.

    Looks for an optional `services.market_status.next_fomc_dt` (UTC).
    Absent ⇒ returns False — the trigger silently disables.
    """
    try:
        from services import market_status  # type: ignore
    except Exception:
        return False
    fn = getattr(market_status, "next_fomc_dt", None)
    if fn is None:
        return False
    try:
        next_dt = fn(now)
    except Exception:
        return False
    if next_dt is None:
        return False
    delta = abs((next_dt - now).total_seconds())
    return delta <= FOMC_WINDOW_SECONDS


def _read_vix(now: datetime) -> float | None:
    """Best-effort VIX read.

    Tries (in order):
      1. ``services.realtime_service.get_vix()``
      2. ``services.cache_service.get_vix()``
    Returns ``None`` on any failure / absence.
    """
    try:
        from services.data import realtime as rt  # type: ignore
        fn = getattr(rt, "get_vix", None)
        if callable(fn):
            v = fn()
            if v is not None:
                return float(v)
    except Exception:
        logger.debug("silent-fallback: _read_vix", exc_info=True)
        pass
    try:
        from services import cache_service as cs  # type: ignore
        fn = getattr(cs, "get_vix", None)
        if callable(fn):
            v = fn()
            if v is not None:
                return float(v)
    except Exception:
        logger.debug("silent-fallback: _read_vix", exc_info=True)
        pass
    return None


def _ticker_moved_more_than(ticker: str, pct: float, now: datetime) -> bool:
    """True iff the ticker moved more than ``pct`` in the last hour.

    Looks for ``services.realtime_service.last_hour_pct_change(ticker)``.
    Absent ⇒ returns False — disables the trigger silently rather than
    raising into the user's reflection start path.
    """
    try:
        from services.data import realtime as rt  # type: ignore
    except Exception:
        return False
    fn = getattr(rt, "last_hour_pct_change", None)
    if not callable(fn):
        return False
    try:
        change = fn(ticker)
    except Exception:
        return False
    if change is None:
        return False
    return abs(float(change)) > float(pct)


# ── Internal helpers ─────────────────────────────────────────────────

def _utc_now() -> datetime:
    """Naive-UTC, matches the rest of the codebase."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def storage_proof(reflection_id: int, user_id: int) -> dict[str, Any]:
    """Trust artifact — return the user's own free-text in *both* forms: the
    plaintext they typed, and the exact ciphertext stored on disk.

    "Show, don't tell": instead of a policy page asserting "your notes are
    encrypted", the user witnesses it on their own data. Ownership is enforced
    (``LookupError`` on miss / wrong owner). The raw column is read with
    textual SQL so it bypasses the ``EncryptedText`` decoder — we hand back the
    literal bytes-on-disk.

    Honest about the tier: the key is server-held, so the server *can* decrypt
    (that is how the plaintext below is produced). This defeats a DB leak, not
    a malicious operator — a user-held-key / end-to-end stage is separate. See
    ``services.crypto_service.EncryptedText``.
    """
    row = _load_owned(reflection_id, user_id)
    stored = db.session.execute(
        text("SELECT rationale FROM pre_trade_reflections WHERE id = :id"),
        {"id": int(reflection_id)},
    ).scalar()
    return {
        "reflection_id": int(reflection_id),
        "rationale_plaintext": row.rationale,
        "rationale_stored": stored,
        "encrypted": is_encrypted_value(stored),
        "cipher": "AES-256-GCM" if backend_name() == "aesgcm" else "dev-fallback",
        "note_kr": (
            "이것이 데이터베이스에 저장된 당신 메모의 실제 형태입니다. "
            "데이터베이스가 통째로 유출되어도 공격자는 이 암호문만 보게 됩니다. "
            "지금은 복호화 키를 서버가 보관합니다 — 화면에 보여드리기 위해 서버는 "
            "복호화할 수 있습니다. ‘우리도 못 읽는’ 종단간 암호화는 다음 단계입니다."
        ),
        "note_en": (
            "This is exactly how your note is stored in our database. A full "
            "database leak would expose only this ciphertext. The decryption "
            "key is currently held server-side — so the server can decrypt to "
            "show you the text above. A 'we cannot read it' end-to-end stage "
            "is next."
        ),
    }


def _load_owned(
    reflection_id: int, user_id: int, *, for_update: bool = False
) -> PreTradeReflection:
    # ``for_update`` takes a row lock so concurrent /proceed + /cancel calls
    # serialize on the same reflection. Without it, two double-submitted POSTs
    # both read null terminal flags, both pass the guard, and both stamp —
    # duplicate journal write, or a row that ends up both proceeded AND
    # cancelled. The rest of the portfolio layer uses with_for_update() for
    # exactly this class; SQLite (dev/test) treats the lock as a no-op.
    if for_update:
        row = (
            db.session.query(PreTradeReflection)
            .filter(PreTradeReflection.id == int(reflection_id))
            .with_for_update()
            .one_or_none()
        )
    else:
        row = db.session.get(PreTradeReflection, int(reflection_id))
    if row is None or int(row.user_id) != int(user_id):
        # Same error for "not found" vs. "wrong owner" — we don't want
        # to leak existence to a different user (timing-safe-ish).
        raise LookupError("reflection not found")
    return row


def _normalise_side(side: Any) -> str | None:
    if side is None:
        return None
    s = str(side).strip().upper()
    if s in ("BUY", "SELL"):
        return s
    return None


def _sane_volatility(v: Any) -> float | None:
    """Drop a non-finite / out-of-range volatility snapshot to ``None``.

    ``market_volatility`` is optional telemetry; a crafted inf / NaN / huge
    value must not break the user's reflection write (it lands in
    ``Numeric(8,4)`` which raises on Postgres). We silently drop it.
    """
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f) or f < 0 or f > _MAX_VOLATILITY:
        return None
    return f


def _to_decimal(v: Any) -> Decimal | None:
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except Exception:
        logger.debug("silent-fallback: _to_decimal", exc_info=True)
        return None
