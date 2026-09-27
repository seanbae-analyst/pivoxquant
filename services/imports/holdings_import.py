"""Holdings (잔고·보유종목) screenshot → positions, in one reviewed step.

The screenshot never reaches the server: the browser OCRs the brokerage
holdings screen and the user reviews every row. Only JSON rows arrive here,
through two endpoints (``routes/holdings_import.py``):

``preview``  — resolves read names/codes to tickers, no DB writes. Resolution
               is the fill-screen importer's (``routes.imports`` /image +
               ``ocr_rows``): a 6-digit code counts only if it is in the KRX
               master, a code/name conflict or a fuzzy name match is
               ``needs_confirm``, anything unproven is ``needs_ticker``. One
               addition: a US symbol must also be in the US master
               (``us_stock_registry``), because commit checks it too — preview
               never offers a ticker that commit would refuse.

``commit``   — writes the reviewed rows in one transaction. Every row is
               validated first; any bad row is a 400 naming the row and field
               and nothing is written.

Decisions (and why):

* **Ticker existence.** ``create_position`` only normalises and length-checks
  the symbol. Here the ticker must be in a master list — KRX master for KR
  (canonicalised to the master's .KS/.KQ by the bare code), Alpaca asset
  master for US — because OCR rows are exactly where a plausible-looking
  wrong symbol comes from.
* **Currency is never changed.** A row's currency must equal the ticker's
  (KR → KRW, else USD) or the batch is refused with
  ``IMPORT_CURRENCY_MISMATCH``.
* **Duplicate tickers** — the same (normalised) ticker twice in one request is
  refused (``IMPORT_DUPLICATE_TICKER``) *including skip rows*: two readings of
  one holding in one capture mean the client is confused about which one is
  real; guessing which to honour would be confidently wrong.
* **No avg-cost vendor guard.** ``create_position`` calls FMP per add for the
  52-week-low plausibility check (fail-open). A 200-row import would make 200
  vendor calls inside the user lock; the value is the broker's own average
  shown on the user's screen and reviewed by the user, so only the numeric
  range guard (``_validate_amount`` parity: finite, 0 < x ≤ 1e9) applies.
* **FX.** Inserts store the capture-time rate exactly like ``create_position``.
  ``add`` uses create_position's merge (cost-weighted FX). ``replace`` also
  sets ``buy_fx_rate`` to the capture-time rate for USD rows: the captured
  average is a new cost basis, and pairing it with the old basis's rate would
  mix two bases. KR rows keep their stored rate (unused for KRW).
* **No trade_history.** ``create_position`` (POST /positions), ``edit_position``
  (PUT /position/<id>) and PATCH /positions/<id> write no trade_history rows —
  they record holdings, not fills. This import records holdings too, so it
  writes none for any mode. Side effect mirrored: the SignalCache warm
  (``cache_service.cache_ticker``) for every written ticker, in one background
  thread.
* **Free-plan cap.** Under the same User-row lock as ``create_position``, new
  positions are applied in request order until the cap; the rest are skipped
  with ``TIER_LIMIT`` (the batch does not fail). ``replace``/``add`` on an
  existing, still-held position is never capped; a stored zero-share row
  would re-activate a holding, so it is gated like a new one.
* **Race.** A concurrent insert of the same ticker (unique user+ticker) rolls
  the whole batch back → 409 ``POSITION_RACE``. Retrying the merge silently
  would apply a mode the user chose while the position did not exist yet.
"""
from __future__ import annotations

import functools
import json
import math
import os
import re
from dataclasses import dataclass

from services.imports import mask_sensitive, ticker_ok
from services.imports import ocr_rows
from services.ticker_normalizer import is_korean_ticker, normalize_ticker

MAX_ROWS = 200
MAX_AMOUNT = 1e9  # routes.portfolio._MAX_AMOUNT parity
MODES = ("replace", "add", "skip")
_NUMERIC_STR = re.compile(r"^\s*\d+(?:\.\d+)?\s*$")
_SIX = re.compile(r"^\d{6}$")
_KR_SHAPE = re.compile(r"^\d{6}(?:\.(?:KS|KQ|KRX))?$", re.IGNORECASE)


class HoldingsError(Exception):
    """A request-level 400. ``code`` is the API error code."""

    def __init__(self, en: str, kr: str, code: str = "IMPORT_INVALID_FIELD",
                 row: int | None = None, field: str | None = None):
        super().__init__(en)
        self.en, self.kr, self.code, self.row, self.field = en, kr, code, row, field

    def extra(self) -> dict:
        out = {}
        if self.row is not None:
            out["row"] = self.row
        if self.field is not None:
            out["field"] = self.field
        return out


# ── masters ──────────────────────────────────────────────────────────

def _kr_index() -> dict[str, str]:
    from routes.imports import _kr_name_index
    return _kr_name_index()


_US_KR_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "us_kr_names.json")


@functools.lru_cache(maxsize=1)
def _us_kr_index() -> dict[str, str]:
    """US stocks by the Korean name Korean apps print ("엔비디아" → NVDA).
    Curated (services/us_kr_names.json); every ticker is in the US master."""
    try:
        with open(_US_KR_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _kr_by_bare() -> dict[str, str]:
    """bare 6-digit code → master ticker (.KS / .KQ)."""
    return {t.split(".")[0]: normalize_ticker(t) for t in _kr_index().values()}


def _us_known(ticker: str) -> bool:
    from services.us_stock_registry import US_STOCKS
    return ticker in US_STOCKS or ticker.replace("-", ".") in US_STOCKS


def ticker_currency(ticker: str) -> str:
    return "KRW" if is_korean_ticker(ticker) else "USD"


def canonical_known_ticker(raw) -> str | None:
    """Master-checked canonical ticker, or None when unknown/malformed."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    t = raw.strip().upper()
    if _KR_SHAPE.match(t):
        return _kr_by_bare().get(t.split(".")[0])
    t = normalize_ticker(t)
    if not ticker_ok(t) or is_korean_ticker(t) or not _us_known(t):
        return None
    return t


def _check_rows_list(rows) -> list:
    if not isinstance(rows, list) or not rows:
        raise HoldingsError("rows must be a non-empty list.", "rows 는 비어 있지 않은 배열이어야 합니다.",
                            field="rows")
    if len(rows) > MAX_ROWS:
        raise HoldingsError(f"rows exceeds {MAX_ROWS} entries.", f"rows 가 {MAX_ROWS}건을 넘습니다.",
                            field="rows")
    return rows


# ── preview ──────────────────────────────────────────────────────────

def _opt_str(item: dict, key: str, i: int) -> str:
    v = item.get(key)
    if v is None:
        return ""
    if not isinstance(v, str):
        raise HoldingsError(f"rows[{i}].{key} must be a string or null.",
                            f"rows[{i}].{key} 는 문자열 또는 null 이어야 합니다.", row=i, field=key)
    return v


def resolve_row(name: str, code: str, currency: str | None) -> dict:
    """Same resolution as the fill-screen image import (see module doc)."""
    from routes.imports import resolve_ticker
    index = _kr_index()
    if code and _KR_SHAPE.match(code) and not ocr_rows.known_kr_code(code, index):
        code = ""  # a comma-less price ("372500") has the code's shape
    status = "resolved"
    ticker, display = resolve_ticker(code, name, latin_name_is_symbol=currency == "USD")
    by_name = index.get(re.sub(r"\s+", "", name or ""))
    if ticker and code and by_name and normalize_ticker(code) != normalize_ticker(by_name):
        status = "needs_confirm"
    us_kr = _us_kr_index()
    if ticker is None and name:
        us = us_kr.get(re.sub(r"\s+", "", name))
        if us is not None:
            ticker, display = us, name
    if ticker is None and name and currency != "USD":
        # KRX names first; a US Korean name only where no KRX name is as close.
        hit = ocr_rows.fuzzy_kr_ticker(name, index) or ocr_rows.fuzzy_kr_ticker(name, {**us_kr, **index})
        if hit is not None:
            ticker, display, status = normalize_ticker(hit[0]), hit[1], "needs_confirm"
    if ticker is not None and not is_korean_ticker(ticker) and not _us_known(ticker):
        ticker = None  # commit would refuse a symbol outside the US master
    if ticker is None:
        return {"ticker": None, "name": None, "currency": None, "status": "needs_ticker"}
    return {"ticker": ticker, "name": display or ticker, "currency": ticker_currency(ticker),
            "status": status}


def preview(user_id: int, rows) -> list[dict]:
    from models import Position
    rows = _check_rows_list(rows)
    parsed = []
    for i, item in enumerate(rows):
        if not isinstance(item, dict):
            raise HoldingsError(f"rows[{i}] must be an object.", f"rows[{i}] 은(는) 객체여야 합니다.", row=i)
        name = mask_sensitive(_opt_str(item, "name", i).strip(), limit=100)
        code = _opt_str(item, "code", i).strip()[:20]
        cur = item.get("currency")
        if cur is not None and cur not in ("KRW", "USD"):
            raise HoldingsError(f"rows[{i}].currency must be KRW, USD or null.",
                                f"rows[{i}].currency 는 KRW·USD·null 중 하나여야 합니다.", row=i, field="currency")
        parsed.append((i, name, code, cur))

    out = []
    for i, name, code, cur in parsed:
        res = resolve_row(name, code, cur)
        out.append({"index": i, "read_name": name or None, "read_code": code or None, **res,
                    "currency_mismatch": bool(cur and res["currency"] and cur != res["currency"]),
                    "existing": None})
    tickers = {r["ticker"] for r in out if r["ticker"]}
    if tickers:
        held = {p.ticker: p for p in Position.query.filter(
            Position.user_id == user_id, Position.ticker.in_(tickers))}
        for r in out:
            p = held.get(r["ticker"]) if r["ticker"] else None
            if p is not None:
                r["existing"] = {"id": p.id, "shares": p.shares, "avg_cost": p.avg_cost,
                                 "currency": ticker_currency(p.ticker)}
    return out


# ── commit ───────────────────────────────────────────────────────────

@dataclass
class CommitRow:
    index: int
    ticker: str
    shares: float
    avg_cost: float
    currency: str
    mode: str


def _number(item: dict, key: str, i: int) -> float:
    v = item.get(key)
    if isinstance(v, bool) or v is None:
        f = None
    elif isinstance(v, (int, float)):
        f = float(v)
    elif isinstance(v, str) and _NUMERIC_STR.match(v):
        f = float(v)
    else:
        f = None
    if f is None or not math.isfinite(f) or not (0 < f <= MAX_AMOUNT):
        raise HoldingsError(f"rows[{i}].{key} must be a number above 0 and at most 1e9.",
                            f"rows[{i}].{key} 는 0보다 크고 10억 이하인 숫자여야 합니다.", row=i, field=key)
    return f


def validate_commit_rows(rows) -> list[CommitRow]:
    rows = _check_rows_list(rows)
    out: list[CommitRow] = []
    seen: dict[str, int] = {}
    for i, item in enumerate(rows):
        if not isinstance(item, dict):
            raise HoldingsError(f"rows[{i}] must be an object.", f"rows[{i}] 은(는) 객체여야 합니다.", row=i)
        mode = item.get("mode")
        if mode not in MODES:
            raise HoldingsError(f"rows[{i}].mode must be replace, add or skip.",
                                f"rows[{i}].mode 는 replace·add·skip 중 하나여야 합니다.", row=i, field="mode")
        ticker = canonical_known_ticker(item.get("ticker"))
        if ticker is None:
            raise HoldingsError(f"rows[{i}].ticker is not a known listed ticker.",
                                f"rows[{i}].ticker 가 확인된 상장 종목이 아닙니다.", row=i, field="ticker")
        currency = item.get("currency")
        if currency not in ("KRW", "USD"):
            raise HoldingsError(f"rows[{i}].currency must be KRW or USD.",
                                f"rows[{i}].currency 는 KRW 또는 USD 여야 합니다.", row=i, field="currency")
        if currency != ticker_currency(ticker):
            raise HoldingsError(
                f"rows[{i}]: {ticker} is priced in {ticker_currency(ticker)}, not {currency}.",
                f"rows[{i}]: {ticker} 의 통화는 {ticker_currency(ticker)} 입니다 ({currency} 아님).",
                code="IMPORT_CURRENCY_MISMATCH", row=i, field="currency")
        shares = _number(item, "shares", i)
        if currency == "KRW" and shares != int(shares):
            raise HoldingsError(f"rows[{i}]: KRW shares must be whole.",
                                f"rows[{i}]: 국내 주식 수량은 정수여야 합니다.", row=i, field="shares")
        avg_cost = _number(item, "avg_cost", i)
        if ticker in seen:
            raise HoldingsError(f"rows[{i}]: {ticker} already appears in rows[{seen[ticker]}].",
                                f"rows[{i}]: {ticker} 가 rows[{seen[ticker]}] 에 이미 있습니다.",
                                code="IMPORT_DUPLICATE_TICKER", row=i, field="ticker")
        seen[ticker] = i
        out.append(CommitRow(i, ticker, shares, avg_cost, currency, mode))
    return out


class RaceError(Exception):
    pass


def commit(user, rows: list[CommitRow], fx_rate_fn) -> tuple[dict, list[str]]:
    """Apply validated rows in one transaction. Returns ``(result, written
    tickers)``. Raises ``RaceError`` after rollback on a concurrent insert."""
    from sqlalchemy.exc import IntegrityError

    from extensions import db
    from models import Position
    from services.position_writes import (
        FREE_POSITION_CAP, active_position_count, is_capped_tier, lock_user_row, merge_buy_into,
    )

    result = {"created": [], "replaced": [], "added": [], "skipped": []}
    written: list[str] = []
    try:
        lock_user_row(user.id)
        capped = is_capped_tier(user)
        active = active_position_count(user.id) if capped else 0
        live = [r for r in rows if r.mode != "skip"]
        held = {}
        if live:
            held = {p.ticker: p for p in Position.query.filter(
                Position.user_id == user.id, Position.ticker.in_([r.ticker for r in live]))}
        fx_rate = fx_rate_fn() if any(r.currency == "USD" for r in live) else 0.0

        for r in rows:
            if r.mode == "skip":
                result["skipped"].append({"ticker": r.ticker, "reason": "USER_SKIP"})
                continue
            is_kr = r.currency == "KRW"
            ex = held.get(r.ticker)
            reactivates = ex is None or not (ex.shares and ex.shares > 0)
            if capped and reactivates:
                if active >= FREE_POSITION_CAP:
                    result["skipped"].append({"ticker": r.ticker, "reason": "TIER_LIMIT"})
                    continue
                active += 1
            if ex is None:
                pos = Position(user_id=user.id, ticker=r.ticker, shares=r.shares, avg_cost=r.avg_cost,
                               buy_fx_rate=0.0 if is_kr else fx_rate, thesis=None,
                               thesis_created_at=None, thesis_status="pending")
                db.session.add(pos)
                result["created"].append({"ticker": r.ticker, "shares": r.shares,
                                          "avg_cost": r.avg_cost, "currency": r.currency})
            else:
                prev_shares, prev_avg = ex.shares, ex.avg_cost
                if r.mode == "replace":
                    ex.shares, ex.avg_cost = r.shares, r.avg_cost
                    if not is_kr and fx_rate:
                        ex.buy_fx_rate = fx_rate
                    bucket = "replaced"
                else:
                    merge_buy_into(ex, r.shares, r.avg_cost, is_kr=is_kr, fx_rate=fx_rate)
                    bucket = "added"
                result[bucket].append({"ticker": r.ticker, "shares": ex.shares, "avg_cost": ex.avg_cost,
                                       "currency": r.currency, "prev_shares": prev_shares,
                                       "prev_avg_cost": prev_avg})
            written.append(r.ticker)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise RaceError()
    except Exception:
        db.session.rollback()
        raise
    return result, written
