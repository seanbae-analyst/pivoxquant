"""Rebuy Mirror — retrospective factual record of, after the user **sold**
a name, whether they **bought the same name again** within a fixed window,
and where that later price sat relative to the price they sold at.

What this is (and is NOT)
-------------------------
This is a **retrospective factual mirror** of the user's own sell → later
buy pairs: "지난 기록에서 판 종목을 90일 안에 다시 산 것이 N건, 그중 판
가격보다 높게 다시 산 것이 P건 · 낮게 다시 산 것이 Q건." It answers, from
the user's own fills only, the question a price-history backtest would ask
of a sale — "what did the name cost when I came back to it?" — without a
single vendor price.

It is deliberately **not**:

* A *score* / *grade* / *index* / *label* / *percentile* / "health"
  number. Counts, a median gap in days, and a median price change between
  the two fills of the same name — nothing else. (DECISIONS.md — AI 점수화
  폐기.)
* A verdict. Rebuying higher is not called a mistake and rebuying lower is
  not called a skill. The module never says either outcome is good or bad
  and never asserts a cause. The interpretation is the user's.
  (research_cbt_bias_model.md — 사실만 비추고 재구성은 사용자.)
* A market-data feature. **No live price, no historical price, no FX
  call, no network.** Both prices in every pair are the user's own recorded
  fills of the *same ticker*, which carry the same currency — so no
  conversion is ever needed. Same discipline as the other behaviour mirrors
  (``averaging_down_mirror`` — "no live price / FX call"), and the reason
  this mirror can be shown while vendor-price display stays behind
  ``MARKET_DATA_DISPLAY_ENABLED`` (CLAUDE.md — FMP 약관 §2.2.2).

Pairing rule
------------
Per ticker, walking the user's fills in chronological order:

* A recorded 매도 that **leaves no shares** becomes the ticker's *pending
  sale* (a later one replaces it — the comparison is always with the **most
  recent** exit before the buy). A partial 매도 is a trim, not leaving the
  name: the buy that follows it is an add, not a return (2026-10-22 — same
  running position as ``averaging_down_mirror``). A 매도 with no recorded
  holding before it (history that starts after the buy) counts as an exit —
  there is nothing to say it was partial.
* Fills of one name under ``.KS`` / ``.KQ`` / the bare code are one ticker
  (``friction_outcome.ticker_key``), and a sale pairs only with a buy in the
  same currency.
* Order is by KST day, then by instant within the day — except that a
  date-only fill (stored as its KST date at 00:00) has no instant. On such a
  day a date-only 매수 goes **before** every timed fill of that day and a
  date-only 매도 **after** them: where the order is unknown, buys precede
  sells, so an ambiguous day never manufactures a same-day "sold, then
  bought back" pair. (2026-10-22, CEO "재매수 버그도 고쳐": the earlier
  end-of-day rule read a date-only buy + timed sale on one day — a day
  trade, or a manual entry of the morning's buy — as a sale and a rebuy
  0.4 days later. A sale larger than the recorded holding also says the buy
  came first.) A timed sale and a timed buy on one day still pair as
  recorded. Gaps are measured with a date-only fill at the end of its day.
* The first recorded 매수 after a pending sale closes the pair **if** it
  lands within :data:`REBUY_WINDOW_DAYS` of that sale. A 매수 after the
  window does not pair (it reads as a new decision, not a return to the
  name) and clears the pending sale. Either way one sale pairs with at most
  one buy.
* Holding-registration rows are not fills: a ``holding_seed`` 매수 never
  closes a pair, a ``holding_adjust`` 매도 never opens one (both still move
  the running share count)
  (:func:`services.profile.fifo_util.is_registration_row`).
* Rows with a non-positive share count or price are ignored entirely — they
  neither open nor close a pair.

The walk always runs over the **full** history; ``period_days`` only decides
which pairs are counted (by the 매수's ``traded_at``), so a sale just before
the window still pairs with a buy inside it (2026-09-29 lesson from
``averaging_down_mirror``).

Statistics
----------
* ``median_gap_days`` — days from the sale to the later buy.
* ``median_price_change_pct`` — ``(buy_price - sell_price) / sell_price``
  per pair, in percent. **Median only**: like realised returns, these are
  long-tailed and one pair should not move the headline.
* Below :data:`_DEFAULT_MIN_PAIRS` pairs in the window we refuse to report
  numbers (``sufficient_data=False``, every number ``None``) — a handful of
  pairs is noise, not a reflection.

Public API
----------
:func:`compute_rebuy_mirror` — pure function over a list of ``TradeHistory``
    rows. No DB access, no network, no ORM mutation.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from statistics import median
from typing import Iterable, NamedTuple

from models import TradeHistory
from services.imports import is_date_only
from services.pre_trade.friction_outcome import ticker_key
from services.profile.fifo_util import is_registration_row


# ── tunables ─────────────────────────────────────────────────────────

# A 매수 more than this many days after the sale is not paired with it.
# Echoed in the payload as ``rebuy_window_days`` so the UI states the rule
# instead of hiding it.
REBUY_WINDOW_DAYS: int = 90

# Below this many pairs in the window the mirror reports no numbers.
# Same gate as ``averaging_down_mirror._DEFAULT_MIN_FOLLOW_ON``.
_DEFAULT_MIN_PAIRS: int = 3

# A rebuy within this of the sale price is bucketed ``flat`` so float drift
# never mislabels a buy that was effectively at the sale price.
_PRICE_EPSILON: float = 1e-9

# How many tickers to surface in the neutral per-ticker breakdown.
_MAX_TICKERS: int = 5

# A position at or below this share count is closed. Matches
# services.profile.fifo_util._SHARE_EPSILON.
_SHARE_EPSILON: float = 1e-9

_KST = timedelta(hours=9)


def _order_at(traded_at: datetime) -> datetime:
    """The instant a pair's gap and window are measured from — a date-only
    fill (its KST date at 00:00) at the end of that KST day, a timed fill at
    its own instant."""
    if is_date_only(traded_at):
        return traded_at + timedelta(days=1) - _KST
    return traded_at


def _walk_key(t: TradeHistory) -> tuple:
    """Walk order: KST day, then within the day date-only 매수 (0) → timed
    fills by instant (1) → date-only 매도 (2), then id. See the module
    docstring's pairing rule."""
    at = t.traded_at
    if is_date_only(at):
        bucket = 2 if (t.action or "").upper() == "SELL" else 0  # // legal-ok — trade.action value, compared only
        return (at.date(), bucket, at, t.id or 0)
    return ((at + _KST).date(), 1, at, t.id or 0)


class _Pair(NamedTuple):
    """One sale and the later buy of the same ticker that it paired with."""

    ticker: str
    sell_at: datetime
    sell_price: float
    buy_at: datetime
    buy_price: float

    @property
    def gap_days(self) -> float:
        return max(0.0, (self.buy_at - self.sell_at).total_seconds() / 86400.0)

    @property
    def price_change_pct(self) -> float:
        return (self.buy_price - self.sell_price) / self.sell_price * 100.0


def _pair_rebuys(
    trades: list[TradeHistory],
    *,
    window_days: int,
) -> tuple[list[_Pair], dict[str, tuple[str | None, str]]]:
    """Walk every ticker's fills and return ``(pairs, names)``.

    ``names`` maps ticker key → (freshest non-empty display name, latest
    ticker spelling). The walk is deterministic: fills are sorted by
    :func:`_walk_key` so out-of-order ingestion (backfill) and same-day
    date-grain fills give one answer.
    """
    ordered = sorted(
        (t for t in trades if t.traded_at and t.ticker),
        key=_walk_key,
    )
    window = timedelta(days=window_days)

    held: dict[str, float] = {}
    pending: dict[str, tuple[datetime, float, str]] = {}
    names: dict[str, str] = {}
    shown: dict[str, str] = {}
    pairs: list[_Pair] = []

    for t in ordered:
        key = ticker_key(t.ticker)
        shown[key] = t.ticker.upper()
        name = (t.name or "").strip()
        if name:
            names[key] = name

        shares = float(t.shares or 0.0)
        price = float(t.price_per_share or 0.0)
        action = (t.action or "").upper()
        before = held.get(key, 0.0)

        if is_registration_row(t):
            # Not a fill — but the shares it seeds or adjusts are held.
            if shares > 0 and action == "BUY":
                held[key] = before + shares
            elif shares > 0 and action == "SELL":
                held[key] = max(0.0, before - shares)
            continue
        if shares <= 0 or price <= 0:
            continue

        at = _order_at(t.traded_at)
        currency = (t.currency or "").upper()
        if action == "SELL":
            left = before - shares
            held[key] = max(0.0, left)
            if before <= _SHARE_EPSILON or left <= _SHARE_EPSILON:
                pending[key] = (at, price, currency)
        elif action == "BUY":
            held[key] = before + shares
            sale = pending.pop(key, None)
            if sale is None:
                continue
            sell_at, sell_price, sell_currency = sale
            if sell_currency != currency:
                continue
            if at - sell_at <= window:
                pairs.append(_Pair(key, sell_at, sell_price, at, price))
        # Unknown action types are ignored entirely.

    # One display spelling per name: the latest one the user's fills used.
    return pairs, {k: (names.get(k), shown[k]) for k in shown}


def _bucket(pair: _Pair) -> str:
    if pair.buy_price > pair.sell_price + _PRICE_EPSILON:
        return "higher"
    if pair.buy_price < pair.sell_price - _PRICE_EPSILON:
        return "lower"
    return "flat"


def _by_ticker(pairs: list[_Pair], names: dict[str, tuple[str | None, str]]) -> list[dict]:
    """Neutral per-ticker breakdown — top ``_MAX_TICKERS`` by pair count.

    Each entry: ``{ticker, name, rebuy_count, higher_count, lower_count}``,
    ordered by descending pair count, ties broken by ticker code.
    """
    tally: dict[str, dict[str, int]] = {}
    for p in pairs:
        rec = tally.setdefault(p.ticker, {"rebuy": 0, "higher": 0, "lower": 0, "flat": 0})
        rec["rebuy"] += 1
        rec[_bucket(p)] += 1
    ordered = sorted(tally.items(), key=lambda kv: (-kv[1]["rebuy"], kv[0]))
    return [
        {
            "ticker": names[ticker][1],
            "name": names[ticker][0],
            "rebuy_count": rec["rebuy"],
            "higher_count": rec["higher"],
            "lower_count": rec["lower"],
        }
        for ticker, rec in ordered[:_MAX_TICKERS]
    ]


def compute_rebuy_mirror(
    trades: Iterable[TradeHistory],
    *,
    period_days: int | None = None,
    min_pairs: int = _DEFAULT_MIN_PAIRS,
    window_days: int = REBUY_WINDOW_DAYS,
    now: datetime | None = None,
) -> dict:
    """Compute the retrospective sell → later-buy mirror for one user.

    Parameters
    ----------
    trades : Iterable[TradeHistory]
        All trade rows for a single user (full history; order-independent).
    period_days : int | None
        When set, only pairs whose 매수 falls within the last ``period_days``
        days are counted — relative to ``now`` when given (the route), else
        to the latest recorded fill in the input. ``None`` → all history.
    min_pairs : int
        Minimum pairs in the window before numbers are reported.
    window_days : int
        Maximum days from a sale to the buy that pairs with it.
    now : datetime | None
        Naive-UTC anchor for ``period_days``. Anchored to the latest fill,
        one unrelated later buy moved the window off every pair (2026-10-22).

    Returns
    -------
    dict
        ``{sufficient_data, period_days, rebuy_window_days, rebuy_count,
        higher_count, lower_count, flat_count, median_gap_days,
        median_price_change_pct, by_ticker}``. **No score / grade / index /
        label field is ever included.** When ``sufficient_data`` is
        ``False`` every number is ``None`` and ``by_ticker`` is ``[]``.
    """
    materialised = [t for t in trades if t is not None]

    cutoff: datetime | None = None
    if period_days is not None and period_days > 0:
        # 창의 기준점은 마지막 *체결* — 보유 등록 시드·조정은 체결이 아니다.
        dated = [t for t in materialised if t.traded_at and not is_registration_row(t)]
        if now is not None:
            cutoff = now - timedelta(days=period_days)
        elif dated:
            cutoff = max(t.traded_at for t in dated) - timedelta(days=period_days)
        else:
            materialised = []

    pairs, names = _pair_rebuys(materialised, window_days=window_days)
    if cutoff is not None:
        pairs = [p for p in pairs if p.buy_at >= cutoff]

    if len(pairs) < max(0, min_pairs) or not pairs:
        return {
            "sufficient_data": False,
            "period_days": period_days,
            "rebuy_window_days": window_days,
            "rebuy_count": None,
            "higher_count": None,
            "lower_count": None,
            "flat_count": None,
            "median_gap_days": None,
            "median_price_change_pct": None,
            "by_ticker": [],
        }

    buckets = [_bucket(p) for p in pairs]
    return {
        "sufficient_data": True,
        "period_days": period_days,
        "rebuy_window_days": window_days,
        "rebuy_count": len(pairs),
        "higher_count": buckets.count("higher"),
        "lower_count": buckets.count("lower"),
        "flat_count": buckets.count("flat"),
        "median_gap_days": round(median(p.gap_days for p in pairs), 1),
        "median_price_change_pct": round(median(p.price_change_pct for p in pairs), 2),
        "by_ticker": _by_ticker(pairs, names),
    }


__all__ = ["REBUY_WINDOW_DAYS", "compute_rebuy_mirror"]
