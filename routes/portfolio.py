"""Portfolio routes: positions CRUD, buy/sell, capital, analytics."""
import logging
import math
import threading
from datetime import datetime, timezone
from flask import Blueprint, current_app, request, jsonify
from flask_login import current_user
from sqlalchemy.exc import IntegrityError

from extensions import db
from models import Position, SignalCache, TradeHistory
from security import trade_rate_limit
from services import fx_service, cache_service
from services.error_responses import api_error
from services.market_display import (
    MARKET_DATA_DISPLAY_FIELD,
    PRICE_SOURCE_DISABLED,
    market_data_display_enabled,
)
from services.name_resolver import resolve_stock_name, canonical_display_name
from services.container import fetcher, realtime  # noqa: F401 — realtime: tests patch routes.portfolio.realtime (conftest mock_realtime)
from services.price_overlay import overlay_prices, parse_price_display
from services.ticker_normalizer import normalize_ticker
from .decorators import api_auth, legal_scrub_response

logger = logging.getLogger(__name__)

portfolio_bp = Blueprint("portfolio", __name__, url_prefix="/api/portfolio")

# Bug API#5 (2026-05-26): upper bound for any user-supplied shares/price/quantity
# amount. Without a finite + bounded guard, a value like 1e308 (or inf/nan from a
# crafted payload) flows into ``shares * price`` → Infinity → JSON Infinity →
# frontend JSON.parse crash. 1e9 is well above any plausible real trade
# (₩1B shares or $1B price per unit) while keeping every product of two amounts
# safely below float64's ~1.8e308 ceiling.
_MAX_AMOUNT = 1e9


def _validate_amount(v):
    """Return True iff ``v`` is a finite, positive, in-range trade amount.

    Used for shares/price/quantity after float() conversion. Rejects nan, inf,
    -inf, <= 0, and anything above _MAX_AMOUNT (which would risk Infinity
    products downstream).
    """
    return math.isfinite(v) and 0 < v <= _MAX_AMOUNT


def _cache_ticker_async(app, ticker: str, capital: float):
    """Warm the SignalCache for a newly-added ticker without blocking the
    HTTP response. The warm is a quote lookup rather than the old
    engine.analyze() run, so it is fast now, but it still hits FMP/KIS and
    can stall on a 402 fallback. Running it in a background thread keeps
    POST /positions snappy and idempotent — the cache miss on the next
    GET /positions call will simply fall back to stored avg_cost defaults,
    exactly as cache_service already handles."""
    def _run():
        with app.app_context():
            try:
                cache_service.cache_ticker(ticker)
            except Exception as e:
                logger.error("Background cache_ticker failed %s: %s", ticker, e)

    threading.Thread(target=_run, daemon=True).start()


# ── avg_cost plausibility guard (Bug #4, 2026-05-14) ────────────────────────
# A test/typo position (AAPL avg_cost=$30 — AAPL last traded at $30 in 2013)
# drove the portfolio equity curve to +593,259%. The position-write paths
# had no sanity check on avg_cost against a realistic price floor.
#
# Guard policy: reject avg_cost that is below 50% of the ticker's trailing
# 52-week low. This catches stale/typo cost-basis entries (an order of
# magnitude off) while still allowing legitimate deep-discount holdings —
# a real long-term holder who bought near a multi-year low is still well
# within 50% of the *52-week* low.
#
# FAIL-OPEN: if the 52-week low cannot be fetched (FMP plan-gated symbol,
# provider outage, KR ticker without FMP coverage), the guard returns None
# and the write proceeds. A data outage must never block a legitimate add.
_AVG_COST_FLOOR_RATIO = 0.5


def _avg_cost_implausible(ticker: str, avg_cost: float) -> str | None:
    """Return a human error string if ``avg_cost`` is implausibly low for
    ``ticker``, else None. Fails open on any data-fetch failure."""
    try:
        if avg_cost <= 0:
            return None  # zero/negative already rejected upstream
        from services.data import fmp as _fmp
        quote = _fmp.get_quote(ticker)
        if not quote:
            return None  # fail-open: no quote → cannot validate
        raw_low = quote.get("yearLow")
        if raw_low in (None, ""):
            return None  # fail-open: provider omitted the field
        year_low = float(raw_low)
        if year_low <= 0:
            return None  # fail-open: unusable field
        floor = year_low * _AVG_COST_FLOOR_RATIO
        if avg_cost < floor:
            logger.warning(
                "avg_cost guard: %s avg_cost=%.2f below floor=%.2f "
                "(52w low=%.2f x %.2f) — rejecting",
                ticker, avg_cost, floor, year_low, _AVG_COST_FLOOR_RATIO,
            )
            # The guard itself keeps running with the display gate shut — it
            # protects data integrity and the quote never leaves the server.
            # Only the *message* is scrubbed: quoting the vendor's 52-week low
            # back to the user would be a display of that data.
            if not market_data_display_enabled():
                return (
                    f"Average cost {avg_cost:,.2f} is implausibly low for "
                    f"{ticker} compared with its recent trading range. "
                    "Please re-check the cost basis."
                )
            return (
                f"Average cost {avg_cost:,.2f} is implausibly low for "
                f"{ticker} (below 50% of its 52-week low of "
                f"{year_low:,.2f}). Please re-check the cost basis."
            )
        return None
    except Exception as e:  # pragma: no cover - defensive, always fail-open
        logger.debug("avg_cost guard fail-open for %s: %s", ticker, e)
        return None


# ── Frontend-friendly aliases (added 2026-04-22) ──────────────────────────────
# These endpoints expose the schema the /portfolio page + modals use.
# 2026-09-29: the deprecated singular write routes (/position, /position/<id>,
# /position/<id>/buy|sell, /position/buy-new), DELETE /positions/<id> and
# PUT /capital were removed — none had a frontend consumer (endpoints.ts
# symbols checked). Seed capital is set via POST /api/profile/capital.
# 2026-09-29: GET "" (the legacy full list, API.portfolio.list) was removed
# too — its only reader, RealtimeProvider, now reads GET /positions.


def _sector_for(sd):
    return sd.get("sector") or "Other"


def _position_display_name(p, sd):
    # KR 종목은 레지스트리 한글명이 항상 이긴다 — 옛 SignalCache 행의 영문명이
    # /portfolio 에만 남고 거래 내역·알림은 한글로 나오던 불일치를 없앤다.
    cached_name = sd.get("name")
    if cached_name and cached_name.upper() == p.ticker.upper():
        cached_name = None
    return canonical_display_name(cached_name, p.ticker) or p.ticker


def _build_positions_list():
    threading.Thread(target=fx_service.refresh, daemon=True).start()
    positions = Position.query.filter_by(user_id=current_user.id).all()
    tickers = [p.ticker for p in positions]
    cache_map = {
        c.ticker: c
        for c in SignalCache.query.filter(SignalCache.ticker.in_(tickers)).all()
    } if tickers else {}
    # MARKET_DATA_DISPLAY_ENABLED (config.py) — see module config comment.
    display_on = market_data_display_enabled()
    # Freshness overlay: realtime (Alpaca/KIS) first, then non-stale cache.
    # Ensures "current" never shows a price older than the SignalCache TTL.
    overlay = overlay_prices(tickers) if display_on else {}

    out = []
    for p in positions:
        cached = cache_map.get(p.ticker)
        sd = cache_service.safe_cache_blob(cached)
        is_kr = p.ticker.upper().endswith(".KS") or p.ticker.upper().endswith(".KQ")
        o = overlay.get(p.ticker) or {}
        if not display_on:
            cur_px = None
            price_source = PRICE_SOURCE_DISABLED
            observed_at = None
            change_pct = None
        elif o.get("price"):
            cur_px = float(o["price"])
            price_source = o.get("source") or "realtime"
            observed_at = o.get("observed_at")
            change_pct = float(o.get("change_pct") or 0)
        else:
            # Bug C (2026-04-24): before falling back to avg_cost, attempt a
            # price_display parse. /api/portfolio/positions used to emit
            # LAST=avg_cost (rendered as "•-" stale chip) whenever the overlay
            # was empty, even when SignalCache had a legible "$402.91".
            parsed_fallback = parse_price_display(sd.get("price_display"))
            if parsed_fallback:
                cur_px = parsed_fallback
                price_source = "stale_display"
                observed_at = None
                change_pct = 0.0
            else:
                # Overlay has no fresh price — fall back to avg_cost (never stale cache).
                cur_px = float(p.avg_cost or 0)
                price_source = "stale"
                observed_at = None
                change_pct = 0.0
        currency = sd.get("currency", "KRW" if is_kr else "USD")
        name = _position_display_name(p, sd)
        opened_at = p.added_at.isoformat() if p.added_at else None

        out.append({
            "id": str(p.id),
            # 2026-05-02: emit both `symbol` (frontend-shape rename used
            # by /portfolio v2) and `ticker` (legacy key still read by
            # /detail access guard, /home v1 holding tables, /signals
            # widgets, /risk concentration aggregator). Single source of
            # truth on the backend, all consumers keep working.
            "symbol": p.ticker,
            "ticker": p.ticker,
            "name": name,
            "side": "Long",  # short positions not represented in DB
            "shares": p.shares,
            "avgCost": round(p.avg_cost, 4),
            "current": round(cur_px, 4) if display_on else None,
            "change_pct": round(change_pct, 4) if display_on else None,
            "observed_at": observed_at,
            "price_source": price_source,
            # Cost basis normalised to KRW by the shared fx_service helper —
            # the weight denominator the /risk aggregators fall back to when
            # market_value is withheld. Same helper as the journal
            # concentration mirror, so the two can never drift (Pattern 7).
            "cost_basis_krw": fx_service.cost_basis_krw(p),
            # Native-currency market value — required by the /risk weight
            # aggregators (useConcentration / useSectorExposure). Its absence
            # made every concentration weight render 0% (CEO 2026-05-24).
            "market_value": round(cur_px * p.shares, 2) if display_on else None,
            "sector": _sector_for(sd),
            "purchaseDate": opened_at[:10] if opened_at else "",
            "notes": p.thesis or "",
            "currency": currency,
            # 2026-05-08 (isKorean sweep): emit BOTH camelCase (v2 page-v2)
            # AND snake_case (lib/hooks.ts RawPosition, signal-card,
            # detail/[ticker], search-command, …). The frontend snake_case
            # is_korean is used in 10+ places — emitting both keeps every
            # consumer working without coordinated frontend rewrites.
            "isKorean":  is_kr,
            "is_korean": is_kr,
        })
    return out


@portfolio_bp.route("/positions", methods=["GET"])
@api_auth
# 2026-09-29 — the scrub contract moves here from the removed legacy GET ""
# (this list replaced it as the RealtimeProvider/portfolio read). `notes` is
# the user's own thesis text and is returned verbatim, like observation notes.
@legal_scrub_response(skip_keys=("notes",))
def list_positions_alias():
    """Simpler positions list tailored to the new frontend shape."""
    try:
        positions = _build_positions_list()
        # Portfolio totals — the /risk weight aggregators divide each holding's
        # market value by these. Omitting them made `denom = 0` → every
        # concentration/sector weight rendered 0% (CEO 2026-05-24).
        #
        # 2026-06-10 (wave-3 P1): bucket on the suffix-derived `is_korean`
        # flag, NOT the cache-blob `currency` string — the same Pattern-7
        # poisoned-cache bug fixed in get_portfolio (2610c824) lived on here,
        # and THIS is the endpoint the v2 frontend actually polls (feeds
        # useConcentration/useSectorExposure weights). `is_korean` is computed
        # from the .KS/.KQ suffix in _build_positions_list; the per-row
        # `currency` display field stays cache-echoed (unchanged).
        rate = fx_service.get_rate() or 0
        display_on = market_data_display_enabled()
        # Cost-basis denominator — always present, so the weight aggregators
        # have a legal fallback while market values are withheld.
        cost_basis_all_krw = round(
            sum(p["cost_basis_krw"] or 0 for p in positions)
        )
        if not display_on:
            return jsonify({
                "positions": positions,
                "total_value_usd": None,
                "total_value_krw": None,
                "total_value_all_krw": None,
                "cost_basis_all_krw": cost_basis_all_krw,
                "fx_rate": rate,
                MARKET_DATA_DISPLAY_FIELD: False,
            })
        total_usd = sum(
            p["market_value"] for p in positions if not p.get("is_korean")
        )
        total_krw = sum(
            p["market_value"] for p in positions if p.get("is_korean")
        )
        total_all_krw = round(total_usd * rate + total_krw)
        return jsonify({
            "positions": positions,
            "total_value_usd": round(total_usd, 2),
            "total_value_krw": round(total_krw, 0),
            "total_value_all_krw": total_all_krw,
            "cost_basis_all_krw": cost_basis_all_krw,
            "fx_rate": rate,
            MARKET_DATA_DISPLAY_FIELD: True,
        })
    except Exception:
        logger.exception("list_positions_alias failed")
        return api_error(
            en="Failed to load positions", kr="포지션 목록을 불러오지 못했습니다.",
            code="POSITIONS_LOAD_FAILED", status=500,
        )


@portfolio_bp.route("/summary", methods=["GET"])
@api_auth
def portfolio_summary_alias():
    """KPI summary: NAV, today's P&L, unrealized, realized YTD."""
    try:
        threading.Thread(target=fx_service.refresh, daemon=True).start()
        rate = fx_service.get_rate() or 0
        positions = Position.query.filter_by(user_id=current_user.id).all()
        tickers = [p.ticker for p in positions]
        cache_map = {
            c.ticker: c
            for c in SignalCache.query.filter(SignalCache.ticker.in_(tickers)).all()
        } if tickers else {}

        # MARKET_DATA_DISPLAY_ENABLED (config.py) — every KPI below except the
        # realized-P&L block is a market-value derivative, so with the gate
        # shut we skip the quote overlay entirely and null them out.
        display_on = market_data_display_enabled()
        # Freshness overlay — ensures NAV/P&L use the latest price, not stale cache.
        overlay = overlay_prices([p.ticker for p in positions]) if display_on else {}

        total_nav_usd = 0.0
        unrealized_usd = 0.0
        today_pnl_usd = 0.0
        # Native-currency subtotals so /home can show US holdings in USD and
        # KR holdings in KRW separately (CEO: don't unify everything to USD).
        nav_us_usd = 0.0   # US positions, native USD market value
        nav_kr_krw = 0.0   # KR positions, native KRW market value
        # Per-currency P&L (native) so the hero KPIs (Today / Unrealized /
        # Realized) show KR figures in KRW, not only a USD-unified number
        # (CEO 2026-05-24: "today 부분은 여전히 usd만").
        today_pnl_us_usd = 0.0
        today_pnl_kr_krw = 0.0
        unrealized_us_usd = 0.0
        unrealized_kr_krw = 0.0

        # Cost basis (avg_cost x shares) — the user's own data, accumulated in
        # BOTH flag states. Native subtotals mirror navUsd / navKrw; the
        # KRW-normalised total mirrors totalNav and reuses
        # fx_service.cost_basis_krw (same helper as the journal concentration
        # mirror — no second implementation, Pattern 7).
        cost_basis_us_usd = 0.0
        cost_basis_kr_krw = 0.0
        cost_basis_total_krw = 0.0

        for p in positions:
            cached = cache_map.get(p.ticker)
            sd = cache_service.safe_cache_blob(cached)
            is_kr = p.ticker.upper().endswith(".KS") or p.ticker.upper().endswith(".KQ")
            o = overlay.get(p.ticker) or {}

            _native_cost = float(p.avg_cost or 0) * float(p.shares or 0)
            if is_kr:
                cost_basis_kr_krw += _native_cost
            else:
                cost_basis_us_usd += _native_cost
            _cb_krw = fx_service.cost_basis_krw(p)
            if _cb_krw:
                cost_basis_total_krw += _cb_krw

            if not display_on:
                continue

            cur_px = float(o.get("price") or p.avg_cost or 0)
            mv = cur_px * p.shares
            cost = p.avg_cost * p.shares

            # Convert KRW positions to USD for a unified NAV figure.
            if is_kr and rate:
                mv_usd = mv / rate
                cost_usd = cost / rate
            else:
                mv_usd = mv
                cost_usd = cost

            total_nav_usd += mv_usd
            unrealized_usd += mv_usd - cost_usd
            if is_kr:
                nav_kr_krw += mv      # native KRW
                unrealized_kr_krw += (mv - cost)
            else:
                nav_us_usd += mv      # native USD
                unrealized_us_usd += (mv - cost)

            # Today's P&L: prefer fresh overlay change_pct, fall back to cache blob.
            chg_pct = (
                o.get("change_pct")
                if o.get("change_pct") is not None
                else (sd.get("change_pct") or sd.get("changePct") or 0)
            )
            try:
                _pct = float(chg_pct) / 100.0
                today_pnl_usd += mv_usd * _pct
                if is_kr:
                    today_pnl_kr_krw += mv * _pct
                else:
                    today_pnl_us_usd += mv * _pct
            except (TypeError, ValueError):
                logger.debug("silent-fallback: portfolio_summary_alias", exc_info=True)
                pass

        today_pnl_pct = (today_pnl_usd / total_nav_usd * 100) if total_nav_usd else 0

        # Realized YTD from TradeHistory (SELL rows only).
        from datetime import datetime
        ytd_start = datetime(datetime.now(timezone.utc).year, 1, 1)
        sells = (TradeHistory.query
                 .filter(TradeHistory.user_id == current_user.id,
                         TradeHistory.action == "SELL",
                         TradeHistory.traded_at >= ytd_start)
                 .all())
        realized_ytd_usd = 0.0
        realized_us_usd = 0.0
        realized_kr_krw = 0.0
        for t in sells:
            raw = t.pnl or 0
            if t.currency == "KRW":
                realized_kr_krw += raw
                realized_ytd_usd += (raw / rate) if rate else 0
            else:
                realized_us_usd += raw
                realized_ytd_usd += raw

        # 2026-05-08 (observed_at sweep): the v2 portfolio page
        # (frontend/src/app/(dashboard)/portfolio/_v2/page-v2.tsx:158)
        # consumes `sumData?.observed_at ?? null` to render the "last
        # reconciled" timestamp chip. Emit it explicitly so the chip
        # stops showing "—" forever. The response IS what we observed.
        observed_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # 2026-05-09 (bug-hunter Bug #5): the PORTFOLIO header renders
        # "Cash buffer at —." forever because this endpoint never emitted
        # the cash percent. Compute it as the idle-cash share of total
        # equity (cash + holdings), unified to USD via the same FX path as
        # totalNav. Defensive: returns 0.0 when capital and NAV are both
        # zero, never a negative or non-finite number.
        cap_usd = float(getattr(current_user, "available_capital", 0.0) or 0.0)
        cap_krw = float(getattr(current_user, "available_capital_krw", 0.0) or 0.0)
        cash_usd_total = cap_usd + (cap_krw / rate if (cap_krw and rate) else 0.0)
        equity_usd = total_nav_usd + cash_usd_total
        if not display_on:
            # Denominator is holdings AT MARKET — no honest cash share exists
            # while the market leg is withheld. Null, never a wrong number.
            cash_pct = None
        elif equity_usd > 0:
            cash_pct = max(0.0, min(100.0, (cash_usd_total / equity_usd) * 100.0))
        else:
            cash_pct = 0.0

        return jsonify({
            "totalNav": round(total_nav_usd, 2) if display_on else None,
            # Native-currency stock subtotals (no FX unification). /home shows
            # US holdings in USD and KR holdings in KRW separately.
            "navUsd": round(nav_us_usd, 2) if display_on else None,
            "navKrw": round(nav_kr_krw, 0) if display_on else None,
            "todayPnl": round(today_pnl_usd, 2) if display_on else None,
            "todayPnlPct": round(today_pnl_pct, 2) if display_on else None,
            "unrealized": round(unrealized_usd, 2) if display_on else None,
            # Realized P&L comes from the user's own recorded executions
            # (TradeHistory), not from a vendor quote — never gated.
            "realizedYtd": round(realized_ytd_usd, 2),
            # Per-currency P&L (native) — hero KPIs show KR figures in KRW.
            "todayPnlUsd": round(today_pnl_us_usd, 2) if display_on else None,
            "todayPnlKrw": round(today_pnl_kr_krw, 0) if display_on else None,
            "unrealizedUsd": round(unrealized_us_usd, 2) if display_on else None,
            "unrealizedKrw": round(unrealized_kr_krw, 0) if display_on else None,
            "realizedUsd": round(realized_us_usd, 2),
            "realizedKrw": round(realized_kr_krw, 0),
            # Cost basis — what the user actually deployed. Always real.
            "costBasisUsd": round(cost_basis_us_usd, 2),
            "costBasisKrw": round(cost_basis_kr_krw, 0),
            "costBasisTotalKrw": round(cost_basis_total_krw, 0),
            "currency": "USD",
            "fxRate": rate,
            "positionCount": len(positions),
            "observed_at": observed_iso,
            # Cash buffer percent of total equity (cash + holdings).
            # Frontend reads `sumData?.cashPct` in
            # frontend/src/app/(dashboard)/portfolio/_v2/page-v2.tsx and
            # renders "Cash buffer at {cashText}." in
            # frontend/src/components/portfolio/v2/portfolio-hero-v2.tsx.
            "cashPct": round(cash_pct, 2) if cash_pct is not None else None,
            MARKET_DATA_DISPLAY_FIELD: display_on,
        })
    except Exception:
        logger.exception("portfolio_summary_alias failed")
        return api_error(
            en="Failed to load summary", kr="요약을 불러오지 못했습니다.",
            code="PORTFOLIO_SUMMARY_FAILED", status=500,
        )


@portfolio_bp.route("/trades", methods=["GET"])
@api_auth
def list_trades_alias():
    """Recent trades, mapped to the frontend Trade shape."""
    try:
        try:
            limit = int(request.args.get("limit", "20"))
        except (TypeError, ValueError):
            limit = 20
        limit = max(1, min(limit, 100))

        rows = (TradeHistory.query
                .filter_by(user_id=current_user.id)
                .order_by(TradeHistory.traded_at.desc())
                .limit(limit).all())
        trades = []
        for t in rows:
            trades.append({
                "id": str(t.id),
                "date": t.traded_at.strftime("%Y-%m-%d") if t.traded_at else "",
                "symbol": t.ticker,
                "name": t.name or t.ticker,
                "side": "Bought" if (t.action or "").upper() == "BUY" else "Sold",
                "qty": t.shares or 0,
                "price": t.price_per_share or 0,
                "total": t.total_value or 0,
                "pnl": t.pnl or 0,
                "pnlPct": t.pnl_pct or 0,
                "currency": t.currency or "USD",
                # 2026-09-29: "holding_seed" = 보유 등록 시드 (체결 아님),
                # None = 체결 기록.
                "source": t.source,
            })
        return jsonify({"trades": trades})
    except Exception:
        logger.exception("list_trades_alias failed")
        return api_error(
            en="Failed to load trades", kr="거래 내역을 불러오지 못했습니다.",
            code="TRADES_LOAD_FAILED", status=500,
        )


def _parse_purchase_date(raw):
    """Parse a user-supplied "YYYY-MM-DD" purchase (open) date.

    Returns a naive-UTC ``datetime`` (midnight) on success, or ``None`` to
    signal "fall back to default now()". Validation is lenient on purpose —
    a malformed value must never 400 / break the add-asset flow (UX), it
    just falls through to the server clock.

    Guards:
      * empty / non-string / unparseable  → None (default now)
      * future date (after today)         → None (default now); a user
        cannot have opened a position in the future
      * implausibly old (before 1900)     → None (default now)
    """
    if not raw or not isinstance(raw, str):
        return None
    s = raw.strip()
    if not s:
        return None
    try:
        parsed = datetime.strptime(s, "%Y-%m-%d")
    except (ValueError, TypeError):
        return None
    parsed = parsed.replace(tzinfo=None)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    # Future date: reject → default now (cannot open a position in the future).
    if parsed.date() > now.date():
        return None
    # Implausibly old: guard against typos / sentinel dates.
    if parsed.year < 1900:
        return None
    return parsed


@portfolio_bp.route("/positions", methods=["POST"])
@api_auth
@trade_rate_limit
def create_position_alias():
    """Accepts the new frontend shape {symbol, side, quantity, price,
    purchase_date, note} and registers (or merges into) a holding.

    ``purchase_date`` (optional, "YYYY-MM-DD") is the date the user opened
    the position. When valid it is stored as ``Position.added_at`` (the
    position open date, serialised as ``opened_at``). Invalid / missing /
    future values fall back to the default server clock — see
    :func:`_parse_purchase_date`. On a merge into an existing position the
    original ``added_at`` is preserved (earliest open date wins).

    ``reflection_id`` (optional, 2026-09-29): sent by the review-mode entry
    ("신규 진입 검토 · 7문항") with the pause it just stamped. Validated by
    ``services/pre_trade/link.py``; the trade row is then an ordinary buy
    linked to that pause instead of a holding seed.
    """
    d = request.get_json() or {}
    raw_symbol = (d.get("symbol") or d.get("ticker") or "").strip().upper()
    # Bug #1 fix (2026-05-13): this is the *production* endpoint hit by
    # the new frontend (POST /api/portfolio/positions). Previously stored
    # bare "005930" → portfolio surfaces rendered "$54,000" / raw ticker /
    # missing name. Funnel every input through normalize_ticker so KR
    # codes always land as canonical .KS / .KQ.
    symbol = normalize_ticker(raw_symbol)
    try:
        quantity = float(d.get("quantity") or d.get("shares") or 0)
        price = float(d.get("price") or d.get("avg_cost") or 0)
    except (TypeError, ValueError):
        return api_error(
            en="Quantity and price must be numbers", kr="수량과 가격은 숫자여야 합니다.",
            code="TRADE_NUMERIC_REQUIRED", status=400,
        )
    if not symbol or quantity <= 0 or price <= 0:
        return api_error(
            en="Symbol, quantity, and price required", kr="종목, 수량, 가격이 필요합니다.",
            code="TRADE_FIELDS_REQUIRED", status=400,
        )
    # Bug API#5 (2026-05-26): reject non-finite / out-of-range amounts so
    # quantity*price can't overflow to Infinity → JSON crash. This is the
    # production add endpoint hit by the frontend (POST /api/portfolio/positions).
    if not _validate_amount(quantity) or not _validate_amount(price):
        return api_error(
            en="Quantity and price out of range", kr="수량 또는 가격이 허용 범위를 벗어났습니다.",
            code="INVALID_AMOUNT", status=400,
        )
    # Position.ticker is db.String(20).
    if len(symbol) > 20:
        return api_error(
            en="Invalid ticker", kr="유효하지 않은 종목입니다.",
            code="INVALID_TICKER", status=400,
        )
    # Bug #4 guard: reject implausibly-low cost basis (test/typo data).
    _implausible = _avg_cost_implausible(symbol, price)
    if _implausible:
        return api_error(
            en=_implausible,
            kr="평균 매입가가 비현실적입니다. 다시 확인해 주세요.",
            code="AVG_COST_IMPLAUSIBLE", status=400,
        )

    # Bug C#2 (2026-05-26): lock the User row FIRST (lock order User→Position,
    # consistent with every buy/sell/add path → deadlock-free), then run the
    # free-plan cap COUNT under that lock so concurrent adds of distinct tickers
    # can't both pass the cap and bypass the limit. Gate logic / message
    # unchanged. SQLite no-ops the lock.
    from services.position_writes import (
        FREE_POSITION_CAP, blocks_new_symbol, lock_user_row, merge_buy_into,
    )
    # Resolved before the User lock (may hit a registry / KIS) — used for the
    # holding seed row and the response.
    resolved_name = resolve_stock_name(symbol)
    lock_user_row(current_user.id)
    # 2026-09-29: the cap limits symbols — adding to an already-held ticker
    # merges and never raises the count (services/position_writes).
    if blocks_new_symbol(current_user, symbol):
        db.session.rollback()
        return api_error(
            en=f"Free plan limited to {FREE_POSITION_CAP} positions. Upgrade to Pro for unlimited.",
            kr=f"무료 플랜은 보유 종목 {FREE_POSITION_CAP}개까지입니다.",
            code="TIER_LIMIT", status=403,
        )

    # 2026-09-29 — review-mode entry ("신규 진입 검토 · 7문항"): the modal sends
    # the pause it just stamped. With a valid link this is a real buy made now,
    # so it is written as an ordinary 매수 row linked to the pause (not a
    # holding seed). Holding-mode registrations send nothing and keep seeding.
    from services.pre_trade.link import ReflectionLinkError, resolve_reflection_link
    try:
        reflection_id = resolve_reflection_link(
            current_user.id, d.get("reflection_id"), ticker=symbol, action="buy")
    except ReflectionLinkError as e:
        db.session.rollback()
        return api_error(en=e.en, kr=e.kr, code=e.code, status=400)

    note = (d.get("note") or d.get("notes") or d.get("thesis") or "").strip()[:500] or None
    # Optional user-supplied open date ("YYYY-MM-DD"). None → default now().
    opened_dt = _parse_purchase_date(d.get("purchase_date"))
    is_kr = symbol.endswith(".KS") or symbol.endswith(".KQ")
    fx_rate = fx_service.get_rate() if not is_kr else 0.0

    # NEW-D (2026-05-09): race-safe upsert. See the
    # uq_positions_user_ticker rationale on Position.__table_args__.
    def _merge_into_alias(ex_row):
        merge_buy_into(ex_row, quantity, price, is_kr=is_kr, fx_rate=fx_rate, note=note)

    # 2026-09-29: registered shares get a holding-seed trade_history row so
    # the FIFO mirrors have a lot for them (services/position_writes).
    # traded_at is the registration time even when purchase_date is given —
    # the seed is excluded from hold-time statistics either way.
    # With a reflection link the row is a recorded buy instead (see above).
    from services.position_writes import add_holding_seed, add_recorded_buy

    def _seed():
        currency = "KRW" if is_kr else "USD"
        if reflection_id is not None:
            add_recorded_buy(current_user.id, symbol, quantity, price, currency,
                             resolved_name or symbol, reflection_id=reflection_id)
            return
        add_holding_seed(current_user.id, symbol, quantity, price,
                         currency, resolved_name or symbol)

    try:
        ex = Position.query.filter_by(user_id=current_user.id, ticker=symbol).first()
        if ex:
            _merge_into_alias(ex)
            new_pos = ex
        else:
            new_pos = Position(
                user_id=current_user.id, ticker=symbol,
                shares=quantity, avg_cost=price, buy_fx_rate=fx_rate,
                thesis=note,
                thesis_created_at=datetime.now(timezone.utc).replace(tzinfo=None) if note else None,
                thesis_status="pending",
            )
            # When the user supplied a valid open date, override the model
            # default (now()). Invalid/missing → leave default. Merge path
            # never reaches here, so an existing position keeps its earliest
            # added_at.
            if opened_dt is not None:
                new_pos.added_at = opened_dt
            db.session.add(new_pos)
        _seed()
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        logger.info("create_position_alias race recovery user=%s ticker=%s",
                    current_user.id, symbol)
        try:
            ex = Position.query.filter_by(
                user_id=current_user.id, ticker=symbol,
            ).first()
            if ex is None:
                return jsonify({
                    "error": "Position add raced; please retry.",
                    "code": "POSITION_RACE",
                }), 409
            _merge_into_alias(ex)
            _seed()
            db.session.commit()
            new_pos = ex
        except Exception:
            db.session.rollback()
            logger.exception("create_position_alias race recovery failed")
            return api_error(
            en="Failed to save position", kr="포지션 저장에 실패했습니다.",
            code="POSITION_SAVE_FAILED", status=500,
        )
    except Exception:
        db.session.rollback()
        logger.exception("create_position_alias commit failed")
        return api_error(
            en="Failed to save position", kr="포지션 저장에 실패했습니다.",
            code="POSITION_SAVE_FAILED", status=500,
        )

    _cache_ticker_async(
        current_app._get_current_object(),
        symbol,
        current_user.available_capital,
    )
    return jsonify({
        "ok": True,
        "id": str(new_pos.id),
        "symbol": symbol,
        "name": resolved_name or symbol,
        # 2026-05-08 (isKorean sweep): dual-emit camelCase + snake_case;
        # see _build_positions_list comment for rationale.
        "isKorean":  is_kr,
        "is_korean": is_kr,
    })


@portfolio_bp.route("/positions/<int:pid>", methods=["PATCH"])
@api_auth
@trade_rate_limit
def patch_position_alias(pid):
    """Partial update: note and/or avg_cost only. Shares untouched."""
    p = Position.query.filter_by(id=pid, user_id=current_user.id).first()
    if not p:
        return api_error(
            en="Position not found", kr="포지션을 찾을 수 없습니다.",
            code="POSITION_NOT_FOUND", status=404,
        )
    d = request.get_json() or {}

    if "avg_cost" in d or "avgCost" in d:
        try:
            new_cost = float(d.get("avg_cost") if "avg_cost" in d else d.get("avgCost"))
        except (TypeError, ValueError):
            return api_error(
            en="avg_cost must be a number", kr="avg_cost 는 숫자여야 합니다.",
            code="AVG_COST_NUMERIC", status=400,
        )
        if new_cost <= 0:
            return api_error(
            en="avg_cost must be positive", kr="avg_cost 는 양수여야 합니다.",
            code="AVG_COST_POSITIVE", status=400,
        )
        # Bug #4 guard: reject implausibly-low cost basis (test/typo data).
        _implausible = _avg_cost_implausible(p.ticker, new_cost)
        if _implausible:
            return api_error(
            en=_implausible,
            kr="평균 매입가가 비현실적입니다. 다시 확인해 주세요.",
            code="AVG_COST_IMPLAUSIBLE", status=400,
        )
        p.avg_cost = new_cost

    if "note" in d or "notes" in d or "thesis" in d:
        note_val = d.get("note") or d.get("notes") or d.get("thesis") or ""
        note_val = (note_val or "").strip()[:500]
        p.thesis = note_val or None
        if note_val and not p.thesis_created_at:
            p.thesis_created_at = datetime.now(timezone.utc).replace(tzinfo=None)
            p.thesis_status = "pending"

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("patch_position_alias failed")
        return api_error(
            en="Failed to update", kr="업데이트에 실패했습니다.",
            code="POSITION_UPDATE_FAILED", status=500,
        )
    return jsonify({"ok": True, "id": str(p.id)})


@portfolio_bp.route("/trades", methods=["POST"])
@api_auth
@trade_rate_limit
def create_trade_alias():
    """Record an executed buy/sell fill on an existing position:
    {position_id, action, quantity, price, date, note}. Seed capital is not
    involved (see the note below the date parse)."""
    d = request.get_json() or {}
    try:
        pid = int(d.get("position_id") or d.get("positionId") or 0)
        quantity = float(d.get("quantity") or d.get("shares") or 0)
        price = float(d.get("price") or 0)
    except (TypeError, ValueError):
        return api_error(
            en="position_id/quantity/price must be numeric", kr="position_id / quantity / price 는 숫자여야 합니다.",
            code="TRADE_NUMERIC_REQUIRED", status=400,
        )
    action = (d.get("action") or "").lower()

    if action not in ("buy", "sell"):
        return api_error(
            en="action must be 'buy' or 'sell'", kr="action 은 'buy' 또는 'sell' 이어야 합니다.",
            code="TRADE_ACTION_INVALID", status=400,
        )
    if pid <= 0 or quantity <= 0 or price <= 0:
        return api_error(
            en="position_id, quantity, and price required", kr="position_id, quantity, price 가 필요합니다.",
            code="TRADE_FIELDS_REQUIRED", status=400,
        )
    # Bug API#5 (2026-05-26): reject non-finite / out-of-range amounts so
    # quantity*price can't overflow to Infinity → JSON crash.
    if not _validate_amount(quantity) or not _validate_amount(price):
        return api_error(
            en="Quantity and price out of range", kr="수량 또는 가격이 허용 범위를 벗어났습니다.",
            code="INVALID_AMOUNT", status=400,
        )

    p = Position.query.filter_by(id=pid, user_id=current_user.id).first()
    if not p:
        return api_error(
            en="Position not found", kr="포지션을 찾을 수 없습니다.",
            code="POSITION_NOT_FOUND", status=404,
        )

    # 2026-09-29 — optional explicit buy ↔ pause link (services/pre_trade/link.py).
    # `reflection_declined: true` = a candidate was shown and unchecked.
    from services.pre_trade.link import ReflectionLinkError, link_declined, resolve_reflection_link
    try:
        reflection_id = resolve_reflection_link(
            current_user.id, d.get("reflection_id"), ticker=p.ticker, action=action)
    except ReflectionLinkError as e:
        return api_error(en=e.en, kr=e.kr, code=e.code, status=400)
    declined = link_declined(d, reflection_id, action=action)

    cached = cache_service.get_signal(p.ticker)
    sd = cache_service.safe_cache_blob(cached)
    is_kr = sd.get("is_korean", p.ticker.upper().endswith(".KS") or p.ticker.upper().endswith(".KQ"))
    name = canonical_display_name(sd.get("name"), p.ticker)
    currency = sd.get("currency", "KRW" if is_kr else "USD")

    # Trade-accuracy fix (2026-05-22): the TradeModalV2 record-mode sends an
    # explicit trade date ("YYYY-MM-DD") for already-executed past trades, but
    # this handler ignored it — TradeHistory.traded_at fell to default now(),
    # so a 2020 trade was stamped today. Parse the optional date and stamp
    # traded_at when valid; None (missing / malformed / future / pre-1900)
    # falls back to the server clock via the column default.
    traded_at_dt = _parse_purchase_date(d.get("date"))

    # 2026-09-29: this endpoint records a fill that already happened at the
    # user's broker. TradeModalV2 sends the same body from both its RECORD
    # ("이미 체결됨 · 기록만") and REVIEW (7문항) modes, and the app never
    # places orders — so every call is a recorded fill. It follows the import
    # ledger (services/imports/ledger.py): seed capital
    # (User.available_capital*) is neither a gate nor a counter here. It used
    # to reject a 매수 with 400 "Insufficient capital" (no code) whenever the
    # seed was short — every new user starts at 0 — and to debit/credit the
    # seed on each fill, so a typed fill moved capital while the same fill
    # imported left it alone.
    #
    # Lock order User→Position, the same on every add/trade path
    # (deadlock-free). The User row is no longer written, but taking it keeps
    # the order uniform with POST /positions. SQLite no-ops the lock.
    from services.position_writes import lock_user_row
    lock_user_row(current_user.id)
    # Bug C#1 (2026-05-26): the initial ``p`` (first() above) was unlocked, so
    # concurrent buy/sell on the same position interleaved their
    # read-modify-write on p.shares/p.avg_cost. Re-load under SELECT FOR UPDATE
    # *after* the User lock. The pre-lock first() still serves the 404 + the
    # display-name lookup above.
    p = (
        db.session.query(Position)
        .filter_by(id=pid, user_id=current_user.id)
        .with_for_update()
        .one_or_none()
    )
    if p is None:
        db.session.rollback()
        return api_error(
            en="Position not found", kr="포지션을 찾을 수 없습니다.",
            code="POSITION_NOT_FOUND", status=404,
        )

    # 2026-09-29: the modal's note used to be dropped. It is kept the way the
    # import ledger keeps an approved thesis — it fills Position.thesis when
    # that is empty (the merge rule of merge_buy_into). A note with nowhere to
    # go on the position (thesis already written, or a 매도 that may close
    # it) becomes an observation note on the ticker — the existing home for
    # free text outside a position (models/observation_note.py).
    note = (d.get("note") or d.get("notes") or d.get("thesis") or "").strip()[:500] or None
    ticker = p.ticker

    if action == "buy":
        cost = quantity * price
        from services.position_writes import merge_buy_into
        thesis_was_empty = not (p.thesis or "").strip()
        merge_buy_into(
            p, quantity, price, is_kr=is_kr,
            fx_rate=0.0 if is_kr else (fx_service.get_rate() or 0.0),
            note=note if thesis_was_empty else None,
        )
        _buy_th = TradeHistory(
            user_id=current_user.id, ticker=ticker, name=name,
            action="BUY", shares=quantity, price_per_share=round(price, 4),  # // legal-ok — trade action data value
            total_value=round(cost, 2), pnl=0, pnl_pct=0, currency=currency,
        )
        if traded_at_dt is not None:
            _buy_th.traded_at = traded_at_dt
        _buy_th.reflection_id = reflection_id
        _buy_th.reflection_declined = True if declined else None
        db.session.add(_buy_th)
        err = _commit_recorded_trade(
            ticker, None if thesis_was_empty else note, "buy",
        )
        if err is not None:
            return err
        return jsonify({
            "ok": True,
            "action": "buy",
            "positionId": str(p.id),
            "newShares": round(p.shares, 6),
            "newAvgCost": round(p.avg_cost, 4),
        })

    # 매도
    if quantity > p.shares:
        db.session.rollback()
        return api_error(
            en=f"Cannot sell {quantity:g}; only {p.shares:g} shares held.",
            kr=f"보유 {p.shares:g}주보다 많은 {quantity:g}주는 매도로 기록할 수 없습니다.",
            code="TRADE_SELL_EXCEEDS_HOLDING", status=400,
        )
    proceeds = quantity * price
    cost_basis = quantity * p.avg_cost
    pnl = proceeds - cost_basis
    pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0
    closed = quantity >= p.shares - 0.0001
    if closed:
        db.session.delete(p)
    else:
        p.shares = round(p.shares - quantity, 6)
    _sell_th = TradeHistory(
        user_id=current_user.id, ticker=ticker, name=name,
        action="SELL", shares=quantity, price_per_share=round(price, 4),  # // legal-ok — trade action data value
        total_value=round(proceeds, 2), pnl=round(pnl, 2),
        pnl_pct=round(pnl_pct, 2), currency=currency,
    )
    if traded_at_dt is not None:
        _sell_th.traded_at = traded_at_dt
    db.session.add(_sell_th)
    err = _commit_recorded_trade(ticker, note, "sell")
    if err is not None:
        return err
    return jsonify({
        "ok": True,
        "action": "sell",
        "positionId": str(pid),
        "proceeds": round(proceeds, 2),
        "pnl": round(pnl, 2),
        "pnlPct": round(pnl_pct, 2),
        "closed": closed,
    })


def _commit_recorded_trade(ticker: str, observation_body: str | None, action: str):
    """Commit the pending trade write. With ``observation_body`` the same
    commit also stores it as an observation note on ``ticker`` —
    ``services.observation_notes.create_note`` commits the session, so the
    trade and its note land together or not at all. Returns an error
    response, or ``None`` on success."""
    try:
        if observation_body:
            from services.observation_notes import create_note
            create_note(current_user.id, observation_body,
                        tickers=[ticker], source="portfolio")
        else:
            db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("create_trade_alias %s failed", action)
        return api_error(
            en="Failed to record trade", kr="거래 기록에 실패했습니다.",
            code="TRADE_RECORD_FAILED", status=500,
        )
    return None


@portfolio_bp.route("/history")
@api_auth
def portfolio_history():
    from datetime import datetime, timezone

    # MARKET_DATA_DISPLAY_ENABLED (config.py): the equity curve IS a series of
    # vendor-priced NAVs and the overlay is a vendor index series, so there is
    # no cost-basis version of this response — it degrades to empty. We also
    # skip record_today_snapshot(): storing a NAV nobody may see would burn a
    # quote call per page load for nothing (the daily path can resume the day
    # the Data Display Agreement lands).
    if not market_data_display_enabled():
        return jsonify({"data": [], MARKET_DATA_DISPLAY_FIELD: False})

    positions = Position.query.filter_by(user_id=current_user.id).all()
    if not positions:
        return jsonify({"data": [], MARKET_DATA_DISPLAY_FIELD: True})
    from services.data import fmp as fmp

    period = request.args.get("period", "5d")
    if period not in ("5d", "1mo", "2mo", "3mo", "6mo", "1y"):
        period = "5d"

    # ── Honest equity curve: plot REAL recorded NAV, never reconstruct. ──────
    # This curve used to apply the CURRENT share count to historical prices,
    # fabricating portfolio value for dates the user never actually held that
    # book (CEO flagged repeatedly as fake data; 표시광고법 fabrication risk).
    # The previous `added_at` clamp was only a band-aid — it moved the start
    # date but still drew a counterfactual "if you'd held today's book back
    # then" line, and for KIS-synced positions `added_at` is our sync time, not
    # the real purchase date. We now plot ONLY NAV we actually observed and
    # stored (services/portfolio/nav_snapshot.py). No backfill — a new account
    # shows a short/empty curve, which is the truth.
    from datetime import date as _d, timedelta as _td

    # Opportunistically record today's NAV on every load, so the curve keeps
    # accumulating from real usage even without the daily cron. Best-effort —
    # must never break the read.
    try:
        from services.portfolio.nav_snapshot import record_today_snapshot
        record_today_snapshot(current_user.id)
    except Exception:
        logger.debug("silent-fallback: nav snapshot record", exc_info=True)

    _win_days = {"5d": 8, "1mo": 35, "2mo": 60, "3mo": 100, "6mo": 200, "1y": 370}.get(period, 8)
    _since = _d.today() - _td(days=_win_days)

    all_values: dict[str, float] = {}
    try:
        from models import PortfolioNavSnapshot
        snap_rows = (
            PortfolioNavSnapshot.query
            .filter(
                PortfolioNavSnapshot.user_id == current_user.id,
                PortfolioNavSnapshot.as_of_date >= _since,
            )
            .order_by(PortfolioNavSnapshot.as_of_date.asc())
            .all()
        )
        for _r in snap_rows:
            all_values[_r.as_of_date.strftime("%Y-%m-%d")] = round(
                float(_r.nav_total_usd), 2
            )
    except Exception:
        # Table may be absent on a lagging deploy — degrade to today-only
        # rather than 500. db.create_all() at boot makes this transient.
        logger.debug("silent-fallback: nav snapshot read", exc_info=True)
        all_values = {}

    # Today's point = the NAV record_today_snapshot just stored (already read
    # above). It used to be overwritten by a re-sum over tickers WITH a
    # realtime quote only, so a holding without one vanished from today and
    # the curve dropped sharply (2026-09-29). compute_current_nav — the same
    # avg_cost-fallback NAV the snapshot stores — fills in only when the row
    # could not be written/read.
    try:
        today = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d")
        if today not in all_values:
            from services.portfolio.nav_snapshot import compute_current_nav
            nav = compute_current_nav(current_user.id)
            if nav and nav["nav_total_usd"] > 0:
                all_values[today] = nav["nav_total_usd"]
    except Exception:
        logger.debug("silent-fallback: portfolio_history", exc_info=True)
        pass

    sorted_dates = sorted(all_values.keys())
    data = [{"date": k, "value": round(all_values[k], 2)} for k in sorted_dates]

    # ── Benchmark overlay (EQUITY CURVE 비교선) ──────────────────────────────
    # Frontend (`EquityPoint.benchmark`) renders an optional comparison line
    # whenever each point carries a `benchmark` field. We emit raw close
    # prices — the frontend handles normalisation so backend changes stay
    # backwards compatible (omit field == old behaviour, no benchmark line).
    #
    # Source policy (메모리 룰: 공식 라이선스만 — yfinance/pykrx 영구 금지):
    #   • KR portfolio (any .KS/.KQ position) → KOSPI 200 via KIS
    #     (`get_index_history("2001")`), with `0001` (KOSPI) as graceful
    #     fallback. KIS already powers `routes/market.py` indices tile via
    #     the same endpoint — same code path, same auth.
    #   • US portfolio → S&P 500 via FMP `SPY` ETF (proven Starter-plan
    #     coverage; `^GSPC` 402-gates on the same plan — see
    #     services/data/fetcher.py:703 fallback table).
    #
    # Graceful degradation: any fetch failure / empty response → benchmark
    # field omitted entirely. Existing equity-curve rendering preserved.
    try:
        is_kr_portfolio = any(
            isinstance(p.ticker, str)
            and (p.ticker.endswith(".KS") or p.ticker.endswith(".KQ"))
            for p in positions
        )
        bench_map: dict[str, float] = {}
        benchmark_label: str | None = (
            "KOSPI 200" if is_kr_portfolio else "S&P 500"
        )

        if is_kr_portfolio:
            # KIS index daily history (FHPUP02120000). 2001 = KOSPI 200,
            # 0001 = KOSPI (broad). Mirror the market.py fallback chain
            # so a degraded 2001 plan still yields a comparison line.
            try:
                from services.kis.service import KISService
                _svc = KISService()
                for _idx_code in ("2001", "0001"):
                    rows = _svc.get_index_history(_idx_code, period=period)
                    if rows:
                        for row in rows:
                            ds = (row.get("date") or "").strip()
                            close = row.get("close")
                            if not ds or len(ds) != 8 or not ds.isdigit():
                                continue
                            try:
                                iso = f"{ds[0:4]}-{ds[4:6]}-{ds[6:8]}"
                                bench_map[iso] = float(close)
                            except (TypeError, ValueError):
                                continue
                        if bench_map:
                            break
            except Exception:
                logger.debug("silent-fallback: portfolio_history KIS bench",
                             exc_info=True)
        else:
            # S&P 500 via SPY ETF (FMP Starter plan covers this; ^GSPC
            # raw index 402-gates — see services/data/fetcher.py:703).
            try:
                bh = fmp.get_history("SPY", period=period)
                if bh is not None and not bh.empty and "Close" in bh.columns:
                    for date, row in bh.iterrows():
                        ds = date.strftime("%Y-%m-%d")
                        try:
                            bench_map[ds] = float(row["Close"])
                        except (TypeError, ValueError):
                            continue
            except Exception:
                logger.debug("silent-fallback: portfolio_history SPY bench",
                             exc_info=True)

        if bench_map:
            # Per-point match by ISO date. Trading-day misalignment
            # (KIS holiday vs FMP holiday vs portfolio compute) means
            # some points may legitimately lack benchmark — frontend
            # tolerates omission per `EquityPoint.benchmark?`.
            for point in data:
                bv = bench_map.get(point["date"])
                if bv is not None:
                    point["benchmark"] = round(bv, 2)
    except Exception:
        # Belt-and-suspenders: never let benchmark logic break the
        # primary equity-curve response. 메모리 룰 [기능 100% 보존].
        logger.debug("silent-fallback: portfolio_history bench wrap",
                     exc_info=True)
        benchmark_label = None

    payload: dict = {"data": data, MARKET_DATA_DISPLAY_FIELD: True}
    if benchmark_label is not None and any("benchmark" in pt for pt in data):
        # Frontend `hooks-v2.ts` BackendEquityResponse already expects
        # `benchmark?: { name?: string }` — emit the label there so the
        # equity-curve legend can render "KOSPI 200" / "S&P 500" dynamically
        # instead of the prior hardcoded "Benchmark · KOSPI200".
        payload["benchmark"] = {"name": benchmark_label}
    return jsonify(payload)


# ── Reconcile (broker sync) — REMOVED 2026-08-31 ───────────────────────────
#
# `POST /api/portfolio/reconcile` used to live here and was deleted with the
# rest of the broker surface in the prune (47a5e8f3). Its ~20-line design note
# was left behind describing the endpoint in the present tense — legal posture,
# response shape, mockup reference — which reads as if the route still exists.
# Removed 2026-09-06; recover the implementation with
#     git show 47a5e8f3^:routes/portfolio.py
#
# The frontend still names the path (`portfolio/page.tsx`), and that is not a
# live 404: the CTA is gated on `reconcileAvailable = brokerData?.kis_connected`
# and `useBrokerConnections()` passes SWR the key `false && ...`, so the request
# never fires. It is dormant, like the rest of `API.broker.*` (CLAUDE.md 함정
# §12) — KIS does not partner with fintech intermediaries, so reviving this
# means solving that first, and the route would have to be rewritten anyway.
