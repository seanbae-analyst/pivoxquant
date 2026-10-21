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

* A recorded 매도 becomes the ticker's *pending sale* (a later 매도 replaces
  it — the comparison is always with the **most recent** sale before the
  buy).
* The first recorded 매수 after a pending sale closes the pair **if** it
  lands within :data:`REBUY_WINDOW_DAYS` of that sale. A 매수 after the
  window does not pair (it reads as a new decision, not a return to the
  name) and clears the pending sale. Either way one sale pairs with at most
  one buy.
* Holding-registration rows are not fills: a ``holding_seed`` 매수 never
  closes a pair, a ``holding_adjust`` 매도 never opens one
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
) -> tuple[list[_Pair], dict[str, str]]:
    """Walk every ticker's fills and return ``(pairs, names)``.

    ``names`` maps ticker → freshest non-empty display name seen. The walk is
    deterministic: fills are sorted by ``(traded_at, id)`` so out-of-order
    ingestion (backfill) and same-day date-grain fills give one answer.
    """
    ordered = sorted(
        (t for t in trades if t.traded_at and t.ticker),
        key=lambda t: (t.traded_at, t.id or 0),
    )
    window = timedelta(days=window_days)

    pending: dict[str, tuple[datetime, float]] = {}
    names: dict[str, str] = {}
    pairs: list[_Pair] = []

    for t in ordered:
        key = t.ticker.upper()
        name = (t.name or "").strip()
        if name:
            names[key] = name

        if is_registration_row(t):
            continue
        shares = float(t.shares or 0.0)
        price = float(t.price_per_share or 0.0)
        if shares <= 0 or price <= 0:
            continue

        action = (t.action or "").upper()
        if action == "SELL":
            pending[key] = (t.traded_at, price)
        elif action == "BUY":
            sale = pending.pop(key, None)
            if sale is None:
                continue
            sell_at, sell_price = sale
            if t.traded_at - sell_at <= window:
                pairs.append(_Pair(key, sell_at, sell_price, t.traded_at, price))
        # Unknown action types are ignored entirely.

    return pairs, names


def _bucket(pair: _Pair) -> str:
    if pair.buy_price > pair.sell_price + _PRICE_EPSILON:
        return "higher"
    if pair.buy_price < pair.sell_price - _PRICE_EPSILON:
        return "lower"
    return "flat"


def _by_ticker(pairs: list[_Pair], names: dict[str, str]) -> list[dict]:
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
            "ticker": ticker,
            "name": names.get(ticker),
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
) -> dict:
    """Compute the retrospective sell → later-buy mirror for one user.

    Parameters
    ----------
    trades : Iterable[TradeHistory]
        All trade rows for a single user (full history; order-independent).
    period_days : int | None
        When set, only pairs whose 매수 falls within the last ``period_days``
        days (relative to the latest recorded fill in the input, for
        determinism) are counted. ``None`` → all history.
    min_pairs : int
        Minimum pairs in the window before numbers are reported.
    window_days : int
        Maximum days from a sale to the buy that pairs with it.

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
        if dated:
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
