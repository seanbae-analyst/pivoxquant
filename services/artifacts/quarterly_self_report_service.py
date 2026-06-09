"""Quarterly Self Report — Premium 15-page Self 10-K PDF (2026-04-19).

Cadence
-------
Cron fires on the 7th day of Jan / Apr / Jul / Oct at 10:00 KST and
aggregates the calendar quarter that just closed. Wraps and **absorbs**
the old Self Audit pipeline (`self_audit_service.py`) as Part 2 of the
report — no data duplication, no new models.

Legal posture
-------------
- Tier gate: `@require_tier("premium")` on the routes.
- Download-only surface; no share, no OG, no landing.
- All AI prose → `services.legal_filter.safe_scrub`.
- Disclaimer partial included on every page footer + dedicated page.

Structure (15p)
---------------
Part 1 — Self 10-K (P1-P7)
    P1  Quarterly Financial Summary (portfolio value delta, cash flow)
    P2  MD&A (AI narrative)
    P3  Segment Performance (sector P/L)
    P4  Risk Factors (concentration, top position risk)
    P5  Internal Controls (risk_defense.py 7-layer status snapshot)
    P6  Legal Matters (quarterly events log — *not* legal issues)
    P7  Principal Positions Detail

Part 2 — Thesis Reality Check (P8-P11) · absorbed Self Audit
    P8  Quarter-opening thesis (Position.thesis recorded)
    P9  Thesis validity check (AI, scrubbed)
    P10 Buy decision-quality score (Self Audit re-used)
    P11 Thesis change checklist (Y/N)

P12-P15
    P12 Best decisions
    P13 Worst decisions
    P14 Next-quarter watch items
    P15 Disclaimer

Entry points
------------
    QuarterlySelfReportService().generate_for_user(user_id, quarter_end=None)
    QuarterlySelfReportService().render_html(data)
    QuarterlySelfReportService().render_pdf(data)  → bytes | None
    QuarterlySelfReportService().run_for_user(user, quarter_end=None)
    QuarterlySelfReportService().run_quarterly(quarter_end=None)
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from extensions import db
from models import Artifact, Position, TradeHistory, User
from services import fx_service

# Re-use the Self Audit aggregator — we wrap, not duplicate.
from services.artifacts.self_audit_service import (
    SelfAuditService,
    _quarter_bounds,
)

logger = logging.getLogger(__name__)


_TEMPLATE_DIR = Path(__file__).parent / "templates"
_DEFAULT_STORAGE_DIR = (
    Path(__file__).resolve().parents[2] / "artifacts" / "quarterly_self_report"
)
# Shared set so premium_plus / founding_lifetime are never silently dropped.
from ._tiers import PAID_TIERS_PREMIUM_AND_UP as _PAID_TIERS  # noqa: E402
from services.artifacts._i18n import localize_ctx, resolve_locale  # Wave F i18n
from services.legal.disclaimers import DISCLAIMER_ARTIFACT_KR
from services.artifacts._pricing import safe_last_price as _safe_price


def _storage_dir() -> Path:
    override = os.environ.get("QUARTERLY_SELF_STORAGE_DIR")
    d = Path(override) if override else _DEFAULT_STORAGE_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _try_import_weasyprint():
    try:
        from weasyprint import HTML  # type: ignore
        return HTML
    except Exception as exc:  # pragma: no cover
        logger.info("WeasyPrint unavailable (%s); PDF skipped.", exc)
        return None


def _try_import_jinja():
    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape
        return Environment, FileSystemLoader, select_autoescape
    except Exception as exc:  # pragma: no cover
        logger.warning("Jinja2 unavailable (%s).", exc)
        return None, None, None


def _safe_scrub(text: str | None) -> str:
    if not text:
        return text or ""
    try:
        from services.legal_filter import safe_scrub
        return safe_scrub(text, context="quarterly_self_report") or text
    except Exception:
        return text



def _fx_rate() -> float:
    """Spot USD/KRW with a safe fallback (mirrors dividend_income)."""
    # Single SoT: services.fx_service.spot_usdkrw (live rate when sane >=900,
    # else FALLBACK_USDKRW). Was a copy-pasted >=900/1380 block in 7 artifacts.
    from services import fx_service
    return fx_service.spot_usdkrw()


def _mv_usd(price: float, shares: float, ticker: str, fx: float) -> float:
    """Position market value normalised to USD.

    The report formats every figure with `$`, so KR (.KS/.KQ) native KRW
    values must be divided by the USD→KRW rate before they are summed with
    US positions. Without this, KR holdings over-weight US ones ~1000x in
    concentration weights, position ranking, and closing/opening value.
    """
    native = price * shares
    if ticker.upper().endswith((".KS", ".KQ")):
        return native / fx
    return native


def _amount_usd(amount: float, currency: Optional[str],
                ticker: Optional[str], fx: float) -> float:
    """Normalise a bare TradeHistory amount (`total_value` / `pnl`) to USD.

    The quarterly report's numeraire is USD (every figure rendered with `$`,
    `closing_val`/`opening_val` summed via `_mv_usd`). A KR trade's
    `total_value` is native KRW, so summing it raw with a US trade's USD
    value over-weights KR ~1000x — the Pattern-7 ₩+$ corruption. Defers the
    KRW/USD decision to `fx_service.is_krw_currency` (explicit `currency`
    column wins, else `.KS`/`.KQ` suffix) so the convention cannot drift from
    the canonical primitive, then divides KRW → USD to match the report.
    """
    amt = float(amount or 0.0)
    if fx_service.is_krw_currency(currency, ticker):
        return amt / fx if fx > 0 else 0.0
    return amt


def _sector_for_ticker(ticker: str) -> str:
    try:
        from models import SignalCache
        import json
        row = db.session.get(SignalCache, ticker)
        if row and row.data_json:
            try:
                payload = json.loads(row.data_json)
                sector = payload.get("sector")
                if sector:
                    return str(sector)
            except Exception:
                logger.debug("silent-fallback: _sector_for_ticker", exc_info=True)
                pass
    except Exception:
        logger.debug("silent-fallback: _sector_for_ticker", exc_info=True)
        pass
    return "Unknown"


# ── data ─────────────────────────────────────────────────────────────────────

@dataclass
class QuarterlyContext:
    user_id:             int
    user_name:           str
    quarter_label:       str                    # "2026 Q1"
    period_start:        date
    period_end:          date
    generated_at:        datetime
    # Part 1 — Self 10-K
    opening_value:       Optional[float]
    closing_value:       Optional[float]
    net_cash_flow:       Optional[float]        # buys - sells in quarter
    quarterly_return_pct: Optional[float]
    mdna:                str                    # AI MD&A paragraph
    segments:            list[dict[str, Any]]
    risk_factors:        list[dict[str, Any]]   # top position + concentration
    internal_controls:   list[dict[str, Any]]   # 7-layer snapshot
    legal_matters:       list[dict[str, Any]]   # quarter events log
    principal_positions: list[dict[str, Any]]
    # Part 2 — Thesis Reality Check
    thesis_entries:      list[dict[str, Any]]   # per-position thesis
    thesis_checks:       list[dict[str, Any]]   # AI validity per thesis
    decision_quality:    dict[str, Any]         # Self Audit payload (wins, avg, best, worst)
    thesis_checklist:    list[dict[str, Any]]   # Y/N
    # P12 / P13 already inside decision_quality
    watch_items:         list[dict[str, Any]]
    disclaimer:          str
    # Wave 6 — colophon provenance. Populated from
    # `resolve_user_data_lineage` with include_journal=True (the
    # quarterly self-report narrates the user's own decisions and
    # journal notes).
    data_sources:        list[dict[str, str]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id":             self.user_id,
            "user_name":           self.user_name,
            "quarter_label":       self.quarter_label,
            "period_start":        self.period_start.isoformat(),
            "period_end":          self.period_end.isoformat(),
            "generated_at":        self.generated_at.isoformat() + "Z",
            "opening_value":       self.opening_value,
            "closing_value":       self.closing_value,
            "net_cash_flow":       self.net_cash_flow,
            "quarterly_return_pct": self.quarterly_return_pct,
            "mdna":                self.mdna,
            "segments":            self.segments,
            "risk_factors":        self.risk_factors,
            "internal_controls":   self.internal_controls,
            "legal_matters":       self.legal_matters,
            "principal_positions": self.principal_positions,
            "thesis_entries":      self.thesis_entries,
            "thesis_checks":       self.thesis_checks,
            "decision_quality":    self.decision_quality,
            "thesis_checklist":    self.thesis_checklist,
            "watch_items":         self.watch_items,
            "disclaimer":          self.disclaimer,
            "data_sources":        self.data_sources,
        }


# ── helpers ──────────────────────────────────────────────────────────────────

def _quarter_cash_flow(user_id: int, start: date, end: date, fx: float
                       ) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """Return (total_buys, total_sells, net_cash_flow) for the quarter, in USD.

    Each trade's `total_value` is native (KRW for `.KS`/`.KQ`, USD otherwise),
    so it is normalised to the report's USD numeraire via `_amount_usd` before
    summing — without this a mixed KR(₩)+US($) book over-weights KR ~1000x
    (Pattern-7) and the downstream `opening_val = closing_val - net` subtracts
    a ₩+$ mixture from a USD figure. `fx` is the USD→KRW spot, fetched once by
    the caller and reused.
    """
    ps_dt = datetime.combine(start, datetime.min.time())
    pe_dt = datetime.combine(end, datetime.max.time())
    try:
        rows = (
            TradeHistory.query
            .filter(TradeHistory.user_id == user_id,
                    TradeHistory.traded_at >= ps_dt,
                    TradeHistory.traded_at <= pe_dt)
            .all()
        )
    except Exception as exc:
        logger.debug("quarter trades query failed: %s", exc)
        return None, None, None

    buys = 0.0
    sells = 0.0
    for t in rows:
        val = _amount_usd(t.total_value, t.currency, t.ticker, fx)
        if (t.action or "").upper() == "BUY":
            buys += val
        elif (t.action or "").upper() == "SELL":
            sells += val
    return round(buys, 2), round(sells, 2), round(sells - buys, 2)


def _segments(user_id: int, start: date, end: date) -> list[dict[str, Any]]:
    """Sector-level P/L — uses realised returns from within the quarter."""
    ps_dt = datetime.combine(start, datetime.min.time())
    pe_dt = datetime.combine(end, datetime.max.time())
    try:
        rows = (
            TradeHistory.query
            .filter(TradeHistory.user_id == user_id,
                    TradeHistory.traded_at >= ps_dt,
                    TradeHistory.traded_at <= pe_dt)
            .all()
        )
    except Exception:
        return []

    # Sector buckets can mix KR(₩) and US($) tickers (e.g. 005930.KS + AAPL
    # both map to Technology), so each pnl is normalised to USD — the report
    # numeraire ($-rendered, ranked) — before bucketing. Raw ₩+$ would
    # over-weight KR ~1000x and corrupt the best-sector ranking (Pattern-7).
    fx = _fx_rate()  # USD → KRW
    bucket: dict[str, dict[str, float]] = {}
    for t in rows:
        sec = _sector_for_ticker(t.ticker or "")
        b = bucket.setdefault(sec, {"pnl": 0.0, "count": 0})
        b["pnl"] += _amount_usd(t.pnl, t.currency, t.ticker, fx)
        b["count"] += 1
    out: list[dict[str, Any]] = []
    for sec, v in bucket.items():
        out.append({
            "sector":      sec,
            "trade_count": int(v["count"]),
            "pnl":         round(v["pnl"], 2),
        })
    out.sort(key=lambda r: -r["pnl"])
    return out


def _risk_factors(user_id: int, positions: list[Position]
                  ) -> list[dict[str, Any]]:
    """Descriptive concentration + top position risks — never prescriptive."""
    if not positions:
        return []

    fx = _fx_rate()  # USD → KRW
    total_mv = 0.0
    enriched: list[dict[str, Any]] = []
    for p in positions:
        shares = float(p.shares or 0)
        if shares <= 0:
            continue
        price = _safe_price(p.ticker) or float(p.avg_cost or 0)
        mv = _mv_usd(price, shares, p.ticker, fx)
        total_mv += mv
        enriched.append({"ticker": p.ticker, "mv": mv,
                         "sector": _sector_for_ticker(p.ticker)})

    rows: list[dict[str, Any]] = []
    if total_mv > 0:
        # Sector concentration
        sec: dict[str, float] = {}
        for e in enriched:
            sec[e["sector"]] = sec.get(e["sector"], 0) + e["mv"]
        top_sec = max(sec.items(), key=lambda kv: kv[1]) if sec else None
        if top_sec and (top_sec[1] / total_mv) >= 0.40:
            rows.append({
                "factor": "섹터 집중",
                "note":   _safe_scrub(
                    f"{top_sec[0]} 섹터 비중 {top_sec[1]/total_mv*100:.0f}% 관찰"
                ) or "",
            })
        # Top single position
        enriched.sort(key=lambda e: -e["mv"])
        top = enriched[0]
        w = top["mv"] / total_mv
        if w >= 0.20:
            # feedback_ticker_display: KR ticker → hangul name (US stays as ticker).
            from services.name_resolver import kr_display_name
            _top_name = kr_display_name(top["ticker"])
            rows.append({
                "factor": "단일 포지션",
                "note":   _safe_scrub(
                    f"{_top_name} 포지션이 전체 MV의 {w*100:.0f}%를 차지 (관찰)"
                ) or "",
            })
    if len(enriched) < 5:
        rows.append({
            "factor": "분산",
            "note":   f"보유 종목 {len(enriched)}개 — 분산 부족 구간 관찰",
        })
    return rows


def _internal_controls() -> list[dict[str, Any]]:
    """Read-only snapshot of the 7-layer Risk Defense state. We do NOT
    import risk_defense.py's runtime here (per the constraint); we surface
    the layer names as a descriptive control list with a 'present' flag
    that flips to False only when the module is physically unimportable."""
    layers = [
        ("L1", "VaR / CVaR"),
        ("L2", "Correlation Cluster"),
        ("L3", "VIX Regime"),
        ("L4", "Tail / Kurtosis"),
        ("L5", "Daily Loss Limit"),
        ("L6", "Sector Concentration"),
        ("L7", "Cash Reserve Floor"),
    ]
    try:
        import importlib
        importlib.import_module("risk_defense")
        module_ok = True
    except Exception:
        module_ok = False

    return [
        {"layer": code, "label": label,
         "status": "active" if module_ok else "unavailable"}
        for code, label in layers
    ]


def _legal_matters(user_id: int, start: date, end: date) -> list[dict[str, Any]]:
    """Quarter events log — filings, broker connects, major actions. This
    is a record, *not* a legal-issue register; framing is explicit in the
    template to prevent misreading."""
    events: list[dict[str, Any]] = []
    ps_dt = datetime.combine(start, datetime.min.time())
    pe_dt = datetime.combine(end, datetime.max.time())

    try:
        tc = (TradeHistory.query
              .filter(TradeHistory.user_id == user_id,
                      TradeHistory.traded_at >= ps_dt,
                      TradeHistory.traded_at <= pe_dt)
              .count())
        events.append({
            "date":  end.isoformat(),
            "label": f"분기 내 거래 총 {tc}건 기록",
        })
    except Exception:
        logger.debug("silent-fallback: _legal_matters", exc_info=True)
        pass

    # Broker connect rows (descriptive)
    try:
        from models import BrokerConnection
        conns = (
            BrokerConnection.query
            .filter_by(user_id=user_id).all()
        )
        for c in conns:
            created = getattr(c, "created_at", None)
            if created and start <= created.date() <= end:
                events.append({
                    "date":  created.date().isoformat(),
                    "label": f"증권사 연결: {getattr(c,'broker','unknown')}",
                })
    except Exception:
        logger.debug("silent-fallback: Broker connect rows (descriptive) | _legal_matters", exc_info=True)
        pass
    events.sort(key=lambda e: e["date"])
    return events


def _principal_positions(positions: list[Position]) -> list[dict[str, Any]]:
    fx = _fx_rate()  # USD → KRW
    rows: list[dict[str, Any]] = []
    for p in positions:
        shares = float(p.shares or 0)
        if shares <= 0:
            continue
        price = _safe_price(p.ticker) or float(p.avg_cost or 0)
        # Per-row mv is shown alongside native `last`/`avg_cost`, so it stays
        # in the position's native currency for internal row consistency.
        # `_mv_usd` is the cross-currency-comparable value used only to rank
        # so KR holdings don't always sort first regardless of true size.
        mv = shares * price
        rows.append({
            "ticker":   p.ticker,
            "shares":   shares,
            "avg_cost": round(float(p.avg_cost or 0), 2),
            "last":     round(price, 2),
            "mv":       round(mv, 2),
            "_mv_usd":  _mv_usd(price, shares, p.ticker, fx),
            "sector":   _sector_for_ticker(p.ticker),
            "thesis":   p.thesis or "",
        })
    rows.sort(key=lambda r: -r["_mv_usd"])
    for r in rows:
        r.pop("_mv_usd", None)
    return rows[:20]


def _thesis_entries(positions: list[Position]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for p in positions:
        if not p.thesis:
            continue
        rows.append({
            "ticker":      p.ticker,
            "thesis":      _safe_scrub(p.thesis or "") or (p.thesis or ""),
            "created_at":  p.thesis_created_at.isoformat()
                           if p.thesis_created_at else None,
            "status":      p.thesis_status or "pending",
            "reason":      _safe_scrub(p.thesis_reason or "")
                           or (p.thesis_reason or ""),
        })
    return rows


def _thesis_checks(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """AI validity check — single Haiku per thesis, scrubbed. Falls back
    to the stored `thesis_status` label when AI unavailable."""
    if not entries:
        return []

    # AI thesis-validity check retired (2026-06-03 legal re-audit): orphaned
    # `import ai_service` (services/ reorg → services.ai.service) always raised
    # ModuleNotFoundError and fell back to the stored thesis_status. We surface
    # that stored label directly — no AI-derived verdict. This also resolves
    # the §101 ④ concern of an AI setting a "warning" verdict on a held
    # position (see legal_question_queue Q-G1).
    out: list[dict[str, Any]] = []
    for e in entries[:10]:
        out.append({
            "ticker":  e["ticker"],
            "verdict": e.get("status") or "pending",
            "note":    e.get("reason") or "",
        })
    return out


def _thesis_checklist(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Y/N checklist — AI-free. User fills these mentally; we only surface
    the question text for each open thesis."""
    out: list[dict[str, Any]] = []
    for e in entries[:15]:
        out.append({
            "ticker":   e["ticker"],
            "question": "이 thesis가 여전히 유효합니까?",
            "answer":   "",  # intentionally blank — user input space
        })
    return out


def _watch_items(quarter_end: date) -> list[dict[str, Any]]:
    next_q_start = quarter_end + timedelta(days=1)
    return [
        {"date": next_q_start.isoformat(),
         "label": "신규 분기 시작 — 포지션 재점검 구간"},
        {"date": (next_q_start + timedelta(days=45)).isoformat(),
         "label": "주요 종목 어닝 리포트 관찰 구간"},
        {"date": (next_q_start + timedelta(days=75)).isoformat(),
         "label": "FOMC / 매크로 이벤트 관찰"},
    ]


def _mdna(ctx_partial: dict[str, Any]) -> str:
    """Management Discussion & Analysis — Haiku narrative, scrubbed.
    Falls back to rule-based prose when AI unavailable."""
    qlabel = ctx_partial.get("quarter_label")
    qr = ctx_partial.get("quarterly_return_pct")
    cf = ctx_partial.get("net_cash_flow")
    segs = ctx_partial.get("segments") or []

    def _fmt_pct(v): return f"{v:+.2f}%" if isinstance(v, (int, float)) else "—"

    top_seg = segs[0]["sector"] if segs else None
    lines = [f"{qlabel} 분기 요약 관찰 보고서입니다."]
    if qr is not None:
        lines.append(f"관찰된 분기 평균 수익률은 {_fmt_pct(qr)}이며, ")
    if cf is not None:
        direction = "유입" if cf >= 0 else "유출"
        lines.append(f"분기 중 자금 {direction}이 관찰되었습니다 ({cf:+,.0f}). ")
    if top_seg:
        lines.append(f"수익 기여가 가장 컸던 섹터는 {top_seg}였습니다.")
    lines.append("본 서술은 사실 관찰이며 매매 권유가 아닙니다.")
    fallback = " ".join(lines)

    # AI MD&A narrative retired (2026-06-03 legal re-audit): orphaned
    # `import ai_service` (services/ reorg → services.ai.service) always raised
    # ModuleNotFoundError and fell back. The deterministic, scrubbed fallback
    # above is the actual product output.
    return _safe_scrub(fallback) or fallback


# ── service ──────────────────────────────────────────────────────────────────

class QuarterlySelfReportService:
    """Premium quarterly 15-page PDF. Absorbs Self Audit as Part 2."""

    def __init__(self) -> None:
        # We do NOT schedule self_audit any more; we just reuse its
        # generator to hydrate Part 2's decision-quality section.
        self._audit = SelfAuditService()

    # ── data ────────────────────────────────────────────────────────────────

    def generate_for_user(self, user_id: int,
                          quarter_end: date | None = None
                          ) -> dict[str, Any]:
        user = db.session.get(User, user_id)
        if not user:
            raise ValueError(f"user {user_id} not found")

        quarter_end = quarter_end or date.today()
        start, end, label = _quarter_bounds(quarter_end)

        positions = Position.query.filter_by(user_id=user_id).all()

        # USD→KRW spot, fetched once and reused for every currency
        # normalisation in this report (cash flow + closing/opening value).
        fx = _fx_rate()  # USD → KRW

        # Cash flow normalised to USD ($) — the report numeraire — so the
        # opening-value identity below stays currency-coherent.
        buys, sells, net = _quarter_cash_flow(user_id, start, end, fx)

        # Closing value (live) — normalised to USD ($), the report numeraire.
        closing = 0.0
        for p in positions:
            shares = float(p.shares or 0)
            if shares <= 0:
                continue
            px = _safe_price(p.ticker) or float(p.avg_cost or 0)
            closing += _mv_usd(px, shares, p.ticker, fx)
        closing_val = round(closing, 2) if closing > 0 else None

        # Opening value approx = closing - net_cash_flow (within quarter
        # only; this is a first-order approximation, good enough for the
        # quarterly 10-K summary since the PDF is owner-only).
        opening_val = None
        if closing_val is not None and net is not None:
            opening_val = round(closing_val - net, 2)

        # Decision quality — reuse Self Audit payload
        audit_data = self._audit.generate_for_user(user_id, quarter_end=quarter_end)
        rated = [s for s in (audit_data.get("best_decisions") or [])
                 + (audit_data.get("worst_decisions") or [])
                 if s.get("return_pct") is not None]
        # Quarterly return = mean of rated — same convention as self_audit
        qr = None
        if rated:
            qr = round(sum(s["return_pct"] for s in rated) / len(rated), 2)

        segments = _segments(user_id, start, end)
        risk_factors = _risk_factors(user_id, positions)
        internal_controls = _internal_controls()
        legal_matters = _legal_matters(user_id, start, end)
        principal = _principal_positions(positions)
        thesis_entries = _thesis_entries(positions)
        thesis_checks = _thesis_checks(thesis_entries)
        thesis_checklist = _thesis_checklist(thesis_entries)

        mdna_text = _mdna({
            "quarter_label":        label,
            "quarterly_return_pct": qr,
            "net_cash_flow":        net,
            "segments":             segments,
        })

        # Wave 6 — colophon data lineage. Include observation-journal
        # row because the quarterly self-report is explicitly a
        # reflection on the user's own decisions.
        try:
            from services.artifacts.data_source_resolver import (
                resolve_user_data_lineage,
            )
            data_sources = resolve_user_data_lineage(
                user_id, include_journal=True,
            )
        except Exception as exc:
            logger.debug("quarterly_self_report lineage resolve failed for user %s: %s",
                         user_id, exc)
            data_sources = []

        ctx = QuarterlyContext(
            user_id=user_id,
            user_name=user.name or user.email.split("@")[0],
            quarter_label=label,
            period_start=start,
            period_end=end,
            generated_at=datetime.now(timezone.utc).replace(tzinfo=None),
            opening_value=opening_val,
            closing_value=closing_val,
            net_cash_flow=net,
            quarterly_return_pct=qr,
            mdna=mdna_text,
            segments=segments,
            risk_factors=risk_factors,
            internal_controls=internal_controls,
            legal_matters=legal_matters,
            principal_positions=principal,
            thesis_entries=thesis_entries,
            thesis_checks=thesis_checks,
            decision_quality={
                "trades_total":    audit_data.get("trades_total"),
                "wins":            audit_data.get("wins"),
                "losses":          audit_data.get("losses"),
                "win_rate_pct":    audit_data.get("win_rate_pct"),
                "avg_return_pct":  audit_data.get("avg_return_pct"),
                "best_decisions":  audit_data.get("best_decisions") or [],
                "worst_decisions": audit_data.get("worst_decisions") or [],
                "pattern_summary": audit_data.get("pattern_summary") or "",
            },
            thesis_checklist=thesis_checklist,
            watch_items=_watch_items(end),
            disclaimer=(
                DISCLAIMER_ARTIFACT_KR
            ),
            data_sources=data_sources,
        )
        return ctx.to_dict()

    # ── v3 design shape (CEO redesign 2026-04-30) ──────────────────────────

    _NOT_CLAIMED: list[str] = [
        "다음 분기 시장 전망 또는 종목 전망.",
        "복제 가능한 청사진 또는 매매 전략.",
        "투자자문 또는 일임 서비스.",
        "관찰 품질의 미래 보장.",
        "세무 또는 법률 자문.",
    ]

    _PULLQUOTE_DEFAULT = (
        "분기는 도래한 것이 아니라 작은 결정들로 만들어졌습니다. "
        "본 보고서는 그 결정들을 정직하게 기록한 것이며, 다음 분기를 예측하지 않습니다."
    )

    def _to_v3_shape(self, data: dict[str, Any]) -> dict[str, Any]:
        """Map generate_for_user(...) onto the v3 5-page Premium shape.

        Persona macro (pm.persona_opener) is rendered directly in the template
        on Page 2 — `data['persona']` is already injected by `_with_persona()`.
        Empty fields fall back to em-dash. No directive vocabulary.
        """
        quarter_label = data.get("quarter_label") or "—"
        as_of = data.get("generated_at") or data.get("period_end") or "—"
        as_of_label = str(as_of).split("T")[0] if as_of else "—"

        def _pct(v: Any, signed: bool = True) -> str:
            try:
                n = float(v)
            except (TypeError, ValueError):
                return "—"
            return f"{n:+.2f}%" if signed else f"{n:.1f}%"

        def _money(v: Any) -> str:
            try:
                n = float(v)
            except (TypeError, ValueError):
                return "—"
            if abs(n) >= 1_000_000:
                return f"${n/1_000_000:.2f}M"
            if abs(n) >= 1_000:
                return f"${n/1_000:.0f}k"
            return f"${n:,.0f}"

        def _tone(v: Any) -> str:
            try:
                n = float(v)
            except (TypeError, ValueError):
                return "neutral"
            if n > 0:
                return "pos"
            if n < 0:
                return "neg"
            return "neutral"

        qrn = data.get("quarterly_return_pct")
        net_cf = data.get("net_cash_flow")
        opening = data.get("opening_value")
        closing = data.get("closing_value")

        segments = []
        for s in (data.get("segments") or [])[:8]:
            segments.append({
                "sector": s.get("sector") or "—",
                "trades": s.get("trade_count") or 0,
                "pnl":    _money(s.get("pnl")),
                "tone":   _tone(s.get("pnl")),
            })

        risk_factors = []
        for r in (data.get("risk_factors") or [])[:6]:
            risk_factors.append({
                "factor": r.get("factor") or "—",
                "note":   r.get("note") or "—",
            })

        controls = []
        for c in (data.get("internal_controls") or []):
            controls.append({
                "code":    c.get("code") or "—",
                "name":    c.get("name") or "—",
                "present": bool(c.get("present", True)),
            })

        dq = data.get("decision_quality") or {}
        def _decision_rows(rows: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
            out = []
            for r in (rows or [])[:3]:
                ret = r.get("return_pct")
                out.append({
                    "ticker":    r.get("ticker") or "—",
                    "name":      r.get("name") or r.get("ticker") or "—",
                    "buy_date":  r.get("buy_date") or "—",
                    "outcome":   r.get("outcome") or "—",
                    "return":    _pct(ret),
                    "tone":      _tone(ret),
                })
            return out

        thesis_checks = []
        for t in (data.get("thesis_checks") or [])[:8]:
            verdict = (t.get("verdict") or "pending").lower()
            verdict_tone = "pos" if verdict in ("valid", "ok") else (
                "warn" if verdict == "warning" else "neutral"
            )
            thesis_checks.append({
                "ticker":  t.get("ticker") or "—",
                "verdict": verdict,
                "verdict_label": {"valid": "유효", "warning": "주의", "ok": "유효",
                                  "pending": "대기"}.get(verdict, verdict),
                "verdict_tone":  verdict_tone,
                "note":    t.get("note") or "—",
            })

        thesis_checklist = []
        for t in (data.get("thesis_checklist") or [])[:10]:
            thesis_checklist.append({
                "ticker":   t.get("ticker") or "—",
                "question": t.get("question") or "이 thesis가 여전히 유효합니까?",
            })

        watch_items = []
        for w in (data.get("watch_items") or [])[:6]:
            watch_items.append({
                "date":  w.get("date") or "—",
                "label": w.get("label") or "—",
            })

        win_rate = dq.get("win_rate_pct")

        return {
            "doc":             f"Quarterly Self Report · {quarter_label}",
            "doc_short":       quarter_label,
            "issued":          f"Issued · {as_of_label}",
            "kpi_qrn_label":   "Quarterly Return",
            "kpi_qrn_value":   _pct(qrn),
            "kpi_qrn_tone":    _tone(qrn),
            "kpi_winrate_label": "Win Rate",
            "kpi_winrate_value": _pct(win_rate, signed=False) if win_rate is not None else "—",
            "kpi_netcf_label": "Net Cash Flow",
            "kpi_netcf_value": _money(net_cf),
            "kpi_netcf_tone":  _tone(net_cf),
            "kpi_closing_label": "Closing Value",
            "kpi_closing_value": _money(closing),
            "opening_value_str": _money(opening),
            "trades_total":      dq.get("trades_total") or 0,
            "wins":              dq.get("wins") or 0,
            "losses":            dq.get("losses") or 0,
            "pattern_summary":   dq.get("pattern_summary") or "",
            "mdna":              data.get("mdna") or "",
            "pullquote":         self._PULLQUOTE_DEFAULT,
            "segments":          segments,
            "risk_factors":      risk_factors,
            "controls":          controls,
            "best_decisions":    _decision_rows(dq.get("best_decisions")),
            "worst_decisions":   _decision_rows(dq.get("worst_decisions")),
            "thesis_checks":     thesis_checks,
            "thesis_checklist":  thesis_checklist,
            "watch_items":       watch_items,
            "not_claimed":       list(self._NOT_CLAIMED),
        }

    # ── render ──────────────────────────────────────────────────────────────

    def render_pdf_html(self, data: dict[str, Any]) -> str:
        env = self._jinja_env()
        if env is None:
            return self._fallback_html(data)
        try:
            ctx = self._with_persona(data)
            from services.artifacts._name_enrich import enrich_v3_names
            ctx["v3"] = enrich_v3_names(self._to_v3_shape(data))
            tpl = env.get_template("quarterly_self_report.html")
            ctx = localize_ctx(ctx, resolve_locale(user_id=ctx.get('user_id'), data=data))
            return tpl.render(**ctx)
        except Exception as exc:
            logger.warning("quarterly_self_report render failed: %s", exc)
            return self._fallback_html(data)

    def render_html(self, data: dict[str, Any]) -> str:
        return self.render_pdf_html(data)

    def _with_persona(self, data: dict[str, Any]) -> dict[str, Any]:
        """Inject the `persona` context variable. See weekly_memo_service
        for the full rationale; this mirrors the same contract."""
        ctx = dict(data)
        try:
            from services.artifacts.persona_resolver import (
                DEFAULT_PERSONA, resolve_persona, resolve_persona_from_code,
            )
            if "persona" in ctx:
                ctx["persona"] = resolve_persona_from_code(ctx.get("persona"))
                return ctx
            user_id = ctx.get("user_id")
            profile = None
            if user_id is not None:
                try:
                    from models import InvestmentProfile
                    profile = (
                        InvestmentProfile.query
                        .filter_by(user_id=user_id)
                        .first()
                    )
                except Exception:
                    profile = None
            ctx["persona"] = resolve_persona(profile) if profile else DEFAULT_PERSONA
        except Exception as exc:
            logger.debug("persona resolution failed: %s", exc)
            ctx["persona"] = "balanced"
        return ctx

    def render_pdf(self, data: dict[str, Any]) -> Optional[bytes]:
        HTML = _try_import_weasyprint()
        if HTML is None:
            return None
        html_str = self.render_html(data)
        try:
            return HTML(string=html_str).write_pdf()
        except Exception as exc:  # pragma: no cover
            logger.error("WeasyPrint quarterly_self render failed: %s", exc)
            return None

    def _jinja_env(self):
        Environment, FileSystemLoader, select_autoescape = _try_import_jinja()
        if Environment is None:
            return None
        try:
            return Environment(
                loader=FileSystemLoader(str(_TEMPLATE_DIR)),
                autoescape=select_autoescape(["html", "xml"]),
                trim_blocks=True,
                lstrip_blocks=True,
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("Jinja env build failed: %s", exc)
            return None

    def _fallback_html(self, data: dict[str, Any]) -> str:
        from html import escape
        return f"""<!doctype html><html><body>
<h1>Quarterly Self Report — {escape(data.get('quarter_label',''))} — {escape(data.get('user_name',''))}</h1>
<p>{escape(data.get('mdna',''))}</p>
<p><em>{escape(data.get('disclaimer',''))}</em></p>
</body></html>"""

    # ── send ────────────────────────────────────────────────────────────────

    def send_email(self, user: User, pdf_bytes: Optional[bytes],
                   html_body: str) -> bool:
        """Phase 7 — delegate to :class:`EmailSender`."""
        from services.email import EmailSender, EmailCategory

        sender = EmailSender()
        ok = sender.send(
            user,
            email_category=EmailCategory.INFORMATION,
            subject="PivoxQuant Quarterly Self Report",
            html_body=html_body,
            from_env_var="WEEKLY_MEMO_FROM_EMAIL",
            from_default="reports@pivoxquant.com",
            pdf_bytes=pdf_bytes,
            pdf_filename=f"quarterly_self_{user.id}.pdf",
        )
        # Stash the SendGrid X-Message-Id so _persist can write it onto the
        # Artifact row (webhook bounce/open mapping — 정통망법 §50).
        self._last_message_id = getattr(sender, "last_message_id", None)
        return ok

    # ── persist + orchestrate ───────────────────────────────────────────────

    def _persist(self, user_id: int, data: dict[str, Any],
                 pdf_bytes: Optional[bytes], sent: bool) -> Artifact:
        title = f"Quarterly Self Report — {data['quarter_label']}"
        pdf_path: Optional[str] = None
        if pdf_bytes:
            try:
                base = _storage_dir() / str(user_id)
                base.mkdir(parents=True, exist_ok=True)
                fname = data["quarter_label"].replace(" ", "_")
                path = base / f"{fname}.pdf"
                path.write_bytes(pdf_bytes)
                pdf_path = str(path)
            except Exception as exc:
                logger.warning("quarterly_self PDF write failed for user %s: %s",
                               user_id, exc)

        artefact = (
            Artifact.query
            .filter_by(user_id=user_id, type="quarterly_self_report",
                       title=title)
            .first()
        )
        if artefact:
            artefact.data_json = data
            if pdf_path:
                artefact.pdf_path = pdf_path
            if sent and not artefact.sent_at:
                artefact.sent_at = datetime.now(timezone.utc).replace(tzinfo=None)
        else:
            artefact = Artifact(
                user_id=user_id,
                type="quarterly_self_report",
                title=title,
                data_json=data,
                pdf_path=pdf_path,
                sent_at=datetime.now(timezone.utc).replace(tzinfo=None) if sent else None,
            )
            db.session.add(artefact)
        # Persist the SendGrid X-Message-Id captured during send_email so the
        # event webhook can map bounce/open/spam back to this row.
        _msg_id = getattr(self, "_last_message_id", None)
        if sent and _msg_id:
            artefact.sg_message_id = _msg_id
        db.session.commit()
        return artefact

    def run_for_user(self, user: User,
                     quarter_end: date | None = None,
                     *, send: bool = True) -> Optional[Artifact]:
        trades = TradeHistory.query.filter_by(user_id=user.id).count()
        if trades == 0:
            logger.info("skipping quarterly_self for user %s — no trades",
                        user.id)
            return None

        data = self.generate_for_user(user.id, quarter_end=quarter_end)
        pdf_bytes = self.render_pdf(data)
        html_body = self.render_html(data)

        sent = False
        if send:
            try:
                sent = self.send_email(user, pdf_bytes, html_body)
            except Exception as exc:
                logger.error("quarterly_self send raised for user %s: %s",
                             user.id, exc)
                sent = False
        return self._persist(user.id, data, pdf_bytes, sent)

    def run_quarterly(self, quarter_end: date | None = None) -> dict[str, Any]:
        """Cron — quarter +7 days 10:00 KST. Premium only."""
        from services.artifacts import iter_users_chunked

        quarter_end = quarter_end or date.today()
        users = (
            User.query
            .filter(User.subscription_tier.in_(list(_PAID_TIERS)))
            .all()
        )

        successes = failures = skipped = 0
        for user in iter_users_chunked(users, label="quarterly_self_report.quarterly"):
            try:
                result = self.run_for_user(user, quarter_end=quarter_end)
                if result is None:
                    skipped += 1
                else:
                    successes += 1
            except Exception as exc:
                db.session.rollback()
                failures += 1
                logger.error("quarterly_self failed for user %s: %s",
                             user.id, exc)

        summary = {
            "quarter_end": quarter_end.isoformat(),
            "attempted":   len(users),
            "success":     successes,
            "failed":      failures,
            "skipped":     skipped,
        }
        logger.info("quarterly_self_report run: %s", summary)
        return summary
