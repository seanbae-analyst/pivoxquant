# Part of Journal Companion — see reports/legal/SAFE_FEATURE_SPECS_2026-04-23.md §6
"""Data bridge — real DB rows → pseudonymized AgentContext payloads.

Wave B
------
The Journal Companion is the only legal-safe scope: Remember · Mirror ·
Question · Refuse. Every piece of data passed to the LLM must be
pseudonymized so that if the upstream LLM provider retains or leaks
input, no real user position / ticker / monetary amount is exposed.

Privacy invariants (enforced here)
----------------------------------
- Ticker symbols NEVER leave this module. Sectors only.
- Real monetary amounts NEVER leave this module. Coarse KRW bins only.
- Prices, broker account ids, real names, emails — NEVER.
- Raw journal text IS included verbatim — the user wrote it about
  themselves, and mirroring their own words is the core product. Legal
  is OK with this (it's user-generated content, not advice).

Every return value is JSON-safe (``datetime.isoformat``,
``Decimal → float``, ``None`` preserved) so it can be serialized straight
into the Claude messages payload with ``json.dumps``.

Failure semantics
-----------------
Missing tables or rows → empty list. Never raise. The system prompt
handles empty context by returning T5 (Refusal to proceed without
data), which is the safe default.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)


# ── JSON-safety helpers ──────────────────────────────────────────────────────


def _iso(value: Any) -> Optional[str]:
    """Normalize dates/datetimes to ISO8601 strings. ``None``-safe."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    # Defensive: string-like already
    return str(value)


def _to_float(value: Any) -> Optional[float]:
    """Coerce Decimal/int/float → float. ``None``-safe."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ── Journal entries ──────────────────────────────────────────────────────────


def load_journal_entries(user_id: int, limit: int = 20) -> list[dict[str, Any]]:
    """Return the user's last ``limit`` journal entries, newest first.

    The ``portfolio_journal`` table may not exist yet on every deploy.
    When the model import fails we return an empty list — the companion
    handles that via T5.

    Each entry contains only ``{date, topic, text}`` — no ticker, no
    price. The ``text`` is verbatim user content (mirroring their own
    words is the product).
    """
    try:
        # Lazy import: the Journal feature lands in a later wave; its
        # model may not exist in every branch.
        from extensions import db

        try:
            from models.portfolio_journal import PortfolioJournal  # type: ignore
        except ImportError:
            logger.info(
                "agent.data_bridge.journal_table_missing user_id=%s", user_id
            )
            return []

        rows: Iterable[Any] = (
            db.session.query(PortfolioJournal)
            .filter(PortfolioJournal.user_id == user_id)
            .order_by(PortfolioJournal.created_at.desc())
            .limit(max(1, min(int(limit), 100)))
            .all()
        )

        out: list[dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "date": _iso(
                        getattr(r, "entry_date", None)
                        or getattr(r, "created_at", None)
                    ),
                    "topic": (getattr(r, "topic", "") or "")[:80],
                    # Verbatim user text — capped to keep the prompt budget
                    # predictable. 2000 chars ≈ 400 tokens per entry.
                    "text": (getattr(r, "text", "") or "")[:2000],
                }
            )
        return out
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "agent.data_bridge.journal_load_failed user_id=%s err=%s",
            user_id,
            exc,
        )
        return []


# ── IPS (Investment Policy Statements) ───────────────────────────────────────


def load_ips_statements(user_id: int) -> list[dict[str, Any]]:
    """Return the user's standing IPS clauses.

    IPS model not yet present — returns empty. Empty IPS is a valid,
    common state (free users never write one).
    """
    try:
        from extensions import db

        try:
            from models.ips_statement import IpsStatement  # type: ignore
        except ImportError:
            return []

        rows = (
            db.session.query(IpsStatement)
            .filter(IpsStatement.user_id == user_id)
            .order_by(IpsStatement.created_at.desc())
            .all()
        )
        return [
            {
                "date": _iso(getattr(r, "created_at", None)),
                "clause_text": (getattr(r, "clause_text", "") or "")[:800],
            }
            for r in rows
        ]
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "agent.data_bridge.ips_load_failed user_id=%s err=%s",
            user_id,
            exc,
        )
        return []


# ── Trade history proxy (pseudonymized) ──────────────────────────────────────

# Sector buckets — coarse by design. Maps through a small heuristic so a
# single prompt update can't leak granular sector data. Unknown tickers
# bucket to "Other" (safe default).
_SECTOR_BUCKET_MAP = {
    # Technology
    "AAPL": "Technology", "MSFT": "Technology", "GOOGL": "Technology",
    "GOOG": "Technology", "META": "Technology", "NVDA": "Technology",
    "AMD": "Technology", "INTC": "Technology", "TSM": "Technology",
    "ORCL": "Technology", "ADBE": "Technology", "CRM": "Technology",
    "NFLX": "Technology", "AMZN": "Technology", "TSLA": "Technology",
    # Financial
    "JPM": "Financial", "BAC": "Financial", "WFC": "Financial",
    "GS": "Financial", "MS": "Financial", "C": "Financial",
    "V": "Financial", "MA": "Financial", "BRK.B": "Financial",
    # Healthcare
    "JNJ": "Healthcare", "PFE": "Healthcare", "UNH": "Healthcare",
    "LLY": "Healthcare", "MRK": "Healthcare", "ABBV": "Healthcare",
    # Energy
    "XOM": "Energy", "CVX": "Energy", "COP": "Energy", "SLB": "Energy",
}


def _sector_bucket(ticker: Optional[str]) -> str:
    """Coarse sector bucket. Always one of 5 buckets; never the raw ticker."""
    if not ticker:
        return "Other"
    t = ticker.upper().strip()
    # Korean tickers: suffix-based heuristic only — we don't ship a per-
    # ticker KR sector map (too much surface area). Everything falls into
    # "Other" which is still useful for pattern recognition ("all your
    # trades are in 'Other' — maybe add diversification notes").
    if t.endswith((".KS", ".KQ")):
        return "Other"
    return _SECTOR_BUCKET_MAP.get(t, "Other")


def _amount_bin_krw(amount_krw: Optional[float]) -> str:
    """Coarse KRW magnitude bucket — 4 bins.

    ``0-1M`` / ``1-10M`` / ``10-100M`` / ``100M+``. Preserves signal
    ("you're a 1-10M per-trade investor") without leaking the exact
    position size.
    """
    if amount_krw is None or amount_krw <= 0:
        return "0-1M"
    if amount_krw < 1_000_000:
        return "0-1M"
    if amount_krw < 10_000_000:
        return "1-10M"
    if amount_krw < 100_000_000:
        return "10-100M"
    return "100M+"


def _amount_to_krw(
    *,
    total_value: Optional[float],
    currency: Optional[str],
    buy_fx_rate: Optional[float],
) -> Optional[float]:
    """Rough USD→KRW conversion for bucketing only.

    We deliberately use a crude FX value (the user's stored ``buy_fx_rate``
    if present, else a generous 1400 KRW/USD default). The bucket is so
    coarse that precision doesn't matter — it just keeps USD trades from
    collapsing into the 0-1M bin.
    """
    value = _to_float(total_value)
    if value is None:
        return None
    cur = (currency or "USD").upper()
    if cur == "KRW":
        return value
    fx = _to_float(buy_fx_rate) or 1400.0
    if fx <= 0:
        fx = 1400.0
    return value * fx


def load_trade_history_proxy(
    user_id: int, days: int = 90
) -> list[dict[str, Any]]:
    """Pseudonymized view of the user's last ``days`` of trades.

    Output per row:
        {
          "date":          ISO date string,
          "sector_bucket": one of 5 buckets,
          "amount_bin":    one of 4 KRW magnitude bins,
          "hold_days":     int (0 if unknown),
          "journaled":     bool — journal references this ticker?
        }

    Hard privacy invariants (enforced at row build time):
      - No ticker string in the output dict
      - No raw amount / price / pnl / shares
      - No broker account id, user name, email

    Empty list on any error. Never raises.
    """
    try:
        from extensions import db

        from models.position import Position
        from models.trade_history import TradeHistory
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "agent.data_bridge.trade_proxy_import_failed err=%s", exc
        )
        return []

    try:
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
            days=max(1, min(int(days), 365))
        )

        trades: list[Any] = (
            db.session.query(TradeHistory)
            .filter(TradeHistory.user_id == user_id)
            .filter(TradeHistory.traded_at >= cutoff)
            .order_by(TradeHistory.traded_at.asc())
            .all()
        )

        # Positions, keyed by ticker, used to estimate hold_days for the
        # open positions case (trade row may have no matching close).
        positions_by_ticker: dict[str, Any] = {
            (getattr(p, "ticker", "") or "").upper(): p
            for p in db.session.query(Position)
            .filter(Position.user_id == user_id)
            .all()
        }

        # Journal lookup set — which tickers has the user written about?
        # Case-insensitive substring match against journal text/topic.
        journaled_tickers: set[str] = _journaled_tickers_for(user_id)

        out: list[dict[str, Any]] = []
        for t in trades:
            ticker_raw = (getattr(t, "ticker", "") or "").upper()

            amount_krw = _amount_to_krw(
                total_value=getattr(t, "total_value", None),
                currency=getattr(t, "currency", None),
                buy_fx_rate=None,  # TradeHistory has no fx — use default
            )

            hold_days = _estimate_hold_days(t, positions_by_ticker.get(ticker_raw))

            out.append(
                {
                    "date": _iso(getattr(t, "traded_at", None)),
                    "sector_bucket": _sector_bucket(ticker_raw),
                    "amount_bin": _amount_bin_krw(amount_krw),
                    "hold_days": int(hold_days),
                    "journaled": ticker_raw in journaled_tickers,
                }
            )
        return out
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "agent.data_bridge.trade_proxy_failed user_id=%s err=%s",
            user_id,
            exc,
        )
        return []


def _estimate_hold_days(trade: Any, position: Any) -> int:
    """Best-effort hold duration in days.

    For a BUY with no matching close → days since the buy. For a SELL, we
    estimate from the oldest still-held position of that ticker (if any);
    otherwise 0. Never negative.
    """
    try:
        traded_at = getattr(trade, "traded_at", None)
        if traded_at is None:
            return 0
        reference: Optional[datetime]
        action = (getattr(trade, "action", "") or "").upper()
        if action == "BUY":
            reference = datetime.now(timezone.utc).replace(tzinfo=None)
        else:
            # SELL — prefer the position opening date if we still have it.
            reference = traded_at
            if position is not None:
                added = getattr(position, "added_at", None)
                if added is not None:
                    traded_at = added
        delta = (reference - traded_at).days if reference else 0
        return max(0, int(delta))
    except Exception:  # noqa: BLE001 — hold_days is best-effort
        return 0


def _journaled_tickers_for(user_id: int) -> set[str]:
    """Set of uppercase tickers that appear in the user's journal entries.

    Heuristic: scan journal topic+text for A-Z 2-5 char tokens that look
    like tickers. This is intentionally cheap — false positives are fine
    (the downstream signal is just a boolean "did you write about this?").
    """
    import re

    try:
        from extensions import db

        try:
            from models.portfolio_journal import PortfolioJournal  # type: ignore
        except ImportError:
            return set()

        rows = (
            db.session.query(PortfolioJournal)
            .filter(PortfolioJournal.user_id == user_id)
            .all()
        )
        pattern = re.compile(r"\b([A-Z]{2,5})\b")
        seen: set[str] = set()
        for r in rows:
            blob = f"{getattr(r, 'topic', '') or ''} {getattr(r, 'text', '') or ''}"
            for match in pattern.findall(blob):
                seen.add(match)
        return seen
    except Exception as exc:  # noqa: BLE001
        logger.debug("agent.data_bridge.journaled_scan_failed err=%s", exc)
        return set()
