"""해외주식 양도소득세 (overseas-equity capital gains) — pure estimator.

Computes, from a user's own ``TradeHistory``, the realised-gain detail and the
per-attribution-year tax estimate for **US (overseas) equities only**. Korean
regular stocks are surfaced as non-taxable (대주주 제외, 2026) with a zero tax
contribution, never silently dropped.

Design contract — why this module is pure
------------------------------------------
* No DB query, no live network call, no Flask context. It consumes already
  FIFO-matched pairs (:func:`services.profile.fifo_util.fifo_match_closed_trades`)
  and an injectable ``fx_resolver``. That makes every branch — FX miss, KR
  carve-out, 250만원 공제, 손익통산 with negative lots — unit-testable with a
  deterministic mock rate and no live FMP dependency.
* FX honesty (표시광고법): the resolver MUST return ``None`` when no genuine
  historical rate exists. We never substitute the spot rate or ``0``. A lot
  whose buy-date OR sell-date FX is missing has its KRW columns left ``None``
  and is excluded from the KRW year aggregate, with an explicit note. USD
  figures are always shown because they are raw stored facts.
* Record/calculation only: no advice, no 절세 전략, no filing. The disclaimer
  constant makes the "참고용 추정 / 신고는 본인·세무사" framing explicit.

Tax model (Korea, 2026 — single source of truth via shared constants)
---------------------------------------------------------------------
* 과세 대상 = 미국(해외) 상장 주식의 실현손익. ``.KS`` / ``.KQ`` = 한국 일반
  주식 → 비과세(대주주 제외) → tax contribution 0.
* 귀속연도 = 양도일(SELL)의 연도.
* 실현손익_KRW = (양도가 USD × 양도일환율) − (취득가 USD × 취득일환율).
* 연 손익통산: 한 귀속연도의 모든 과세 lot 실현손익을 합산(음수 포함).
* 과세표준 = max(0, 합산 − 2,500,000)   (기본공제 250만원).
* 예상세액 = 과세표준 × 0.22            (양도세 20% + 지방소득세 2%).
"""
from __future__ import annotations

from typing import Callable, Iterable, NamedTuple

# Shared SoT with services/artifacts/burn_rate_service.py so the headline CGT
# rate can never drift between the burn-rate card and the tax CSV.
from services.artifacts.burn_rate_service import _US_CGT_RATE as US_CGT_RATE

# 기본공제: 해외주식 양도소득 기본공제 250만원/년 (소득세법 §103).
ANNUAL_BASIC_DEDUCTION_KRW: float = 2_500_000.0


def _is_kr_ticker(ticker: str | None) -> bool:
    """True for KR-listed symbols (``.KS`` / ``.KQ``) — a property of the
    symbol itself, so it stays inside the raw-fact boundary."""
    return bool(ticker) and str(ticker).upper().endswith((".KS", ".KQ"))


class CapitalGainLot(NamedTuple):
    """One realised (FIFO-matched) lot with both USD facts and KRW estimates.

    KRW fields are ``None`` when either leg's FX rate is unavailable — never
    fabricated. ``taxable`` is False for KR regular stock (비과세). ``note``
    carries the human-readable reason (KR 비과세 / 환율 확인 불가) in Korean.
    """
    attribution_year: int
    ticker: str
    name: str
    quantity: float
    buy_date: str          # ISO YYYY-MM-DD
    sell_date: str         # ISO YYYY-MM-DD
    buy_price_usd: float
    sell_price_usd: float
    buy_fx: float | None   # 취득일환율 (None = 확인 불가)
    sell_fx: float | None  # 양도일환율 (None = 확인 불가)
    buy_cost_krw: float | None
    sell_proceeds_krw: float | None
    realized_pnl_krw: float | None
    taxable: bool
    note: str


class CapitalGainYear(NamedTuple):
    """Per-attribution-year aggregate over taxable (US) lots only.

    ``trade_count`` counts taxable lots whose realised KRW P&L could be
    computed (FX present on both legs); ``fx_missing_count`` records taxable
    lots excluded from the aggregate because an FX rate was unavailable, so
    the summary is honest about partial coverage.
    """
    attribution_year: int
    trade_count: int
    fx_missing_count: int
    total_realized_pnl_krw: float
    basic_deduction_krw: float
    taxable_base_krw: float
    estimated_tax_krw: float


# Note labels (Korean). Kept as constants so the CSV and any future surface
# stay consistent and a copy change is one edit.
_NOTE_KR_EXEMPT = "한국 일반주식 비과세(대주주 제외)"
_NOTE_FX_MISSING = "환율 확인 불가(주말·공휴일·데이터 결손) — KRW 환산 제외"
_NOTE_FX_MISSING_PARTIAL = "환율 일부 확인 불가 — KRW 환산 제외"

# Confirmed disclaimer wording — legal-kr-fintech 2026-05-31 (§5-B). Vetted
# against 세무사법 §2/§20③ (삼쩜삼 선례 = pure-calculator, 면허 불요) +
# 표시광고법 §3 (추정 명기 + FMP 환율 비공식성 + 대주주 면책 + 홈택스 확인).
# Kept a module constant so any future legal revision is a single-line swap.
DISCLAIMER_KR: str = (
    "본 내역은 이용자 본인의 체결 데이터를 기반으로 참고용으로 계산한 추정 "
    "수치이며, 세무대리·세무자문이 아닙니다. 예상세액은 FIFO 원가 매칭과 "
    "단순화된 22% 세율(양도세 20% + 지방세 2%)을 적용한 것으로, 실제 신고 "
    "납부액과 다를 수 있습니다. 환율은 FMP 종가 기준이며, 국세청 신고 시 "
    "적용되는 서울외국환중개 고시 매매기준율과 미세한 차이가 있을 수 있습니다. "
    "한국 일반주식(코스피·코스닥)은 2026년 소액주주 비과세 기준에 따라 0원으로 "
    "표시되며 대주주 해당 여부는 본인이 확인해야 합니다. 실제 세금 신고는 "
    "홈택스(hometax.go.kr) 또는 공인 세무사를 통해 직접 진행하시기 바랍니다. "
    "신고 책임은 전적으로 이용자 본인에게 있습니다."
)


def _safe_year(sell_time) -> int | None:
    try:
        return int(sell_time.year)
    except (AttributeError, TypeError, ValueError):
        return None


def _iso_date(dt) -> str:
    try:
        return dt.date().isoformat()
    except (AttributeError, TypeError):
        try:
            return dt.isoformat()[:10]
        except (AttributeError, TypeError):
            return ""


def compute_capital_gain_lots(
    matched_pairs: Iterable,
    fx_resolver: Callable[[object], float | None],
    name_resolver: Callable[[str], str] | None = None,
) -> list[CapitalGainLot]:
    """Build per-lot capital-gain detail from FIFO-matched pairs.

    Parameters
    ----------
    matched_pairs
        Iterable of ``MatchedPair`` (ticker / quantity / buy_time / sell_time
        / buy_price / sell_price / ...). Typically the output of
        :func:`services.profile.fifo_util.fifo_match_closed_trades`.
    fx_resolver
        ``date -> float | None``. MUST return ``None`` when no genuine
        historical rate exists (e.g. :func:`services.fx_service.get_rate_at_strict`).
        Injected so tests pin deterministic rates without a live fetch.
    name_resolver
        Optional ``ticker -> display name``. Pure local lookup only; a miss
        or absence falls back to the ticker. Never raises through this fn.

    Returns
    -------
    list[CapitalGainLot]
        One entry per matched lot, in input order. Deterministic for fixed
        inputs and a fixed ``fx_resolver``.
    """
    lots: list[CapitalGainLot] = []

    for pair in matched_pairs:
        ticker = (getattr(pair, "ticker", "") or "").upper()
        try:
            name = (name_resolver(ticker) if name_resolver else None) or ticker
        except Exception:
            name = ticker

        quantity = float(getattr(pair, "quantity", 0.0) or 0.0)
        buy_price = float(getattr(pair, "buy_price", 0.0) or 0.0)
        sell_price = float(getattr(pair, "sell_price", 0.0) or 0.0)
        buy_time = getattr(pair, "buy_time", None)
        sell_time = getattr(pair, "sell_time", None)

        year = _safe_year(sell_time) or 0
        buy_date = _iso_date(buy_time)
        sell_date = _iso_date(sell_time)

        is_kr = _is_kr_ticker(ticker)

        if is_kr:
            # Korean regular stock → 비과세. Surfaced explicitly (never
            # silently dropped) with USD/KRW left uncomputed and a clear note.
            lots.append(CapitalGainLot(
                attribution_year=year,
                ticker=ticker,
                name=name,
                quantity=quantity,
                buy_date=buy_date,
                sell_date=sell_date,
                buy_price_usd=buy_price,
                sell_price_usd=sell_price,
                buy_fx=None,
                sell_fx=None,
                buy_cost_krw=None,
                sell_proceeds_krw=None,
                realized_pnl_krw=None,
                taxable=False,
                note=_NOTE_KR_EXEMPT,
            ))
            continue

        # US (overseas) equity → taxable. Resolve trade-date FX strictly.
        buy_fx = _resolve_fx(fx_resolver, buy_time)
        sell_fx = _resolve_fx(fx_resolver, sell_time)

        if buy_fx is None or sell_fx is None:
            # FX missing on at least one leg → never fabricate a rate or use
            # spot. Leave KRW blank; USD facts still shown.
            lots.append(CapitalGainLot(
                attribution_year=year,
                ticker=ticker,
                name=name,
                quantity=quantity,
                buy_date=buy_date,
                sell_date=sell_date,
                buy_price_usd=buy_price,
                sell_price_usd=sell_price,
                buy_fx=buy_fx,
                sell_fx=sell_fx,
                buy_cost_krw=None,
                sell_proceeds_krw=None,
                realized_pnl_krw=None,
                taxable=True,
                note=_NOTE_FX_MISSING,
            ))
            continue

        buy_cost_krw = buy_price * quantity * buy_fx
        sell_proceeds_krw = sell_price * quantity * sell_fx
        realized_pnl_krw = sell_proceeds_krw - buy_cost_krw

        lots.append(CapitalGainLot(
            attribution_year=year,
            ticker=ticker,
            name=name,
            quantity=quantity,
            buy_date=buy_date,
            sell_date=sell_date,
            buy_price_usd=buy_price,
            sell_price_usd=sell_price,
            buy_fx=buy_fx,
            sell_fx=sell_fx,
            buy_cost_krw=buy_cost_krw,
            sell_proceeds_krw=sell_proceeds_krw,
            realized_pnl_krw=realized_pnl_krw,
            taxable=True,
            note="",
        ))

    return lots


def _resolve_fx(fx_resolver, when) -> float | None:
    """Call the injected resolver on the lot's date, swallowing failures.

    A resolver exception (or a non-positive rate) is treated as a miss
    (``None``) — never a fabricated value.
    """
    if when is None:
        return None
    try:
        rate = fx_resolver(when.date() if hasattr(when, "date") else when)
    except Exception:
        return None
    if rate is None:
        return None
    try:
        rate = float(rate)
    except (TypeError, ValueError):
        return None
    return rate if rate > 0 else None


def summarize_by_year(lots: Iterable[CapitalGainLot]) -> list[CapitalGainYear]:
    """Aggregate taxable (US) lots per attribution year — 손익통산 + 공제 + 세액.

    Only lots with ``taxable=True`` and a computed ``realized_pnl_krw`` enter
    the 손익통산 sum (FX-missing taxable lots are counted separately so the
    summary discloses partial coverage). KR 비과세 lots never affect tax.

    Returns one row per year with a positive *or* negative aggregate (a
    net-loss year shows taxable_base 0 / tax 0 but is still listed so the
    user sees the loss-carry context). Sorted by year ascending.
    """
    by_year: dict[int, dict] = {}

    for lot in lots:
        if not lot.taxable:
            continue
        year = lot.attribution_year
        bucket = by_year.setdefault(
            year, {"sum": 0.0, "count": 0, "fx_missing": 0}
        )
        if lot.realized_pnl_krw is None:
            bucket["fx_missing"] += 1
            continue
        bucket["sum"] += float(lot.realized_pnl_krw)
        bucket["count"] += 1

    out: list[CapitalGainYear] = []
    for year in sorted(by_year):
        bucket = by_year[year]
        total = bucket["sum"]
        # 과세표준 = max(0, 합산 − 250만). A net loss → base 0, tax 0.
        taxable_base = max(0.0, total - ANNUAL_BASIC_DEDUCTION_KRW)
        estimated_tax = taxable_base * US_CGT_RATE
        out.append(CapitalGainYear(
            attribution_year=year,
            trade_count=bucket["count"],
            fx_missing_count=bucket["fx_missing"],
            total_realized_pnl_krw=total,
            basic_deduction_krw=ANNUAL_BASIC_DEDUCTION_KRW,
            taxable_base_krw=taxable_base,
            estimated_tax_krw=estimated_tax,
        ))
    return out
