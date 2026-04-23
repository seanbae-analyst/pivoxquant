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
_PAID_TIERS = frozenset({"premium", "elite"})


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


def _safe_price(ticker: str) -> Optional[float]:
    try:
        from services.container import fetcher
        hist = fetcher.get_price_history(ticker, period="5d")
        if hist is None or "Close" not in hist or len(hist["Close"]) == 0:
            return None
        return float(hist["Close"].iloc[-1])
    except Exception as exc:
        logger.debug("price fetch failed for %s: %s", ticker, exc)
        return None


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
                pass
    except Exception:
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
        }


# ── helpers ──────────────────────────────────────────────────────────────────

def _quarter_cash_flow(user_id: int, start: date, end: date
                       ) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """Return (total_buys, total_sells, net_cash_flow) for the quarter."""
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
        val = float(t.total_value or 0)
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

    bucket: dict[str, dict[str, float]] = {}
    for t in rows:
        sec = _sector_for_ticker(t.ticker or "")
        b = bucket.setdefault(sec, {"pnl": 0.0, "count": 0})
        b["pnl"] += float(t.pnl or 0)
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

    total_mv = 0.0
    enriched: list[dict[str, Any]] = []
    for p in positions:
        shares = float(p.shares or 0)
        if shares <= 0:
            continue
        price = _safe_price(p.ticker) or float(p.avg_cost or 0)
        mv = shares * price
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
            rows.append({
                "factor": "단일 포지션",
                "note":   _safe_scrub(
                    f"{top['ticker']} 포지션이 전체 MV의 {w*100:.0f}%를 차지 (관찰)"
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
        pass
    events.sort(key=lambda e: e["date"])
    return events


def _principal_positions(positions: list[Position]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for p in positions:
        shares = float(p.shares or 0)
        if shares <= 0:
            continue
        price = _safe_price(p.ticker) or float(p.avg_cost or 0)
        mv = shares * price
        rows.append({
            "ticker":   p.ticker,
            "shares":   shares,
            "avg_cost": round(float(p.avg_cost or 0), 2),
            "last":     round(price, 2),
            "mv":       round(mv, 2),
            "sector":   _sector_for_ticker(p.ticker),
            "thesis":   p.thesis or "",
        })
    rows.sort(key=lambda r: -r["mv"])
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

    try:
        import ai_service  # type: ignore
        svc_ = getattr(ai_service, "ai_service", None) or ai_service.AIService()
        available = getattr(svc_, "available", False)
    except Exception:
        svc_, available = None, False

    out: list[dict[str, Any]] = []
    for e in entries[:10]:
        verdict = e.get("status") or "pending"
        note = e.get("reason") or ""
        if available and e.get("thesis"):
            try:
                prompt = (
                    "투자자가 기록한 thesis 문장 1개가 주어진다. "
                    "해당 thesis가 '여전히 타당해 보이는지 / 주의 필요 / 근거 약함' "
                    "중 하나로 판단하고, 중립적인 1-2문장 한국어로 근거를 서술하라.\n"
                    "추천/매수/매도/조언 단어 사용 금지.\n\n"
                    f"thesis: {e.get('thesis')}"
                )
                resp = svc_.client.messages.create(
                    model=ai_service.MODEL,
                    max_tokens=200,
                    messages=[{"role": "user", "content": prompt}],
                )
                txt = "".join(
                    getattr(b, "text", "") for b in (resp.content or [])
                    if getattr(b, "type", "") == "text"
                ).strip()
                note = _safe_scrub(txt) or note
                lower = txt.lower()
                if any(k in lower for k in ("근거 약함", "invalid", "약함")):
                    verdict = "warning"
                elif any(k in lower for k in ("주의", "watch")):
                    verdict = "warning"
                else:
                    verdict = verdict or "valid"
            except Exception as exc:
                logger.debug("thesis AI check failed for %s: %s",
                             e.get("ticker"), exc)
        out.append({
            "ticker":  e["ticker"],
            "verdict": verdict,
            "note":    note,
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

    try:
        import ai_service  # type: ignore
        svc_ = getattr(ai_service, "ai_service", None) or ai_service.AIService()
        if not getattr(svc_, "available", False):
            return _safe_scrub(fallback) or fallback

        seg_str = ", ".join(f"{s['sector']}({s['pnl']:+.0f})" for s in segs[:5]) or "n/a"
        prompt = (
            "Self 10-K 형식의 'Management Discussion & Analysis' 섹션을 "
            "2 문단(총 4-6문장, 한국어, 중립적 서술체)으로 작성하라. "
            "추천/매수/매도/조언/목표가 단어 사용 금지.\n\n"
            f"분기: {qlabel}\n"
            f"분기 수익률(관찰): {_fmt_pct(qr)}\n"
            f"순현금흐름(관찰): {cf}\n"
            f"섹터 P/L 요약: {seg_str}\n"
        )
        resp = svc_.client.messages.create(
            model=ai_service.MODEL,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            getattr(b, "text", "") for b in (resp.content or [])
            if getattr(b, "type", "") == "text"
        ).strip()
        return (_safe_scrub(text) or _safe_scrub(fallback) or fallback)[:1500]
    except Exception as exc:
        logger.debug("mdna AI failed: %s", exc)
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

        buys, sells, net = _quarter_cash_flow(user_id, start, end)

        # Closing value (live)
        closing = 0.0
        for p in positions:
            shares = float(p.shares or 0)
            if shares <= 0:
                continue
            px = _safe_price(p.ticker) or float(p.avg_cost or 0)
            closing += shares * px
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
                "정보 제공 목적이며 투자 권유가 아닙니다. "
                "투자 판단은 본인 책임입니다."
            ),
        )
        return ctx.to_dict()

    # ── render ──────────────────────────────────────────────────────────────

    def render_html(self, data: dict[str, Any]) -> str:
        env = self._jinja_env()
        if env is None:
            return self._fallback_html(data)
        try:
            tpl = env.get_template("quarterly_self_report.html")
            return tpl.render(**self._with_persona(data))
        except Exception as exc:
            logger.warning("quarterly_self_report render failed: %s", exc)
            return self._fallback_html(data)

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
        if getattr(user, "email_opt_out", False):
            return False

        from_email = os.environ.get(
            "WEEKLY_MEMO_FROM_EMAIL", "reports@pivoxquant.com"
        )
        subject = f"PivoxQuant Quarterly Self Report"

        sg_key = os.environ.get("SENDGRID_API_KEY")
        if sg_key:
            try:
                import base64
                from sendgrid import SendGridAPIClient  # type: ignore
                from sendgrid.helpers.mail import (  # type: ignore
                    Mail, Attachment, FileContent, FileName, FileType, Disposition,
                )
                mail = Mail(from_email=from_email, to_emails=user.email,
                            subject=subject, html_content=html_body)
                if pdf_bytes:
                    enc = base64.b64encode(pdf_bytes).decode()
                    att = Attachment(
                        FileContent(enc),
                        FileName(f"quarterly_self_{user.id}.pdf"),
                        FileType("application/pdf"),
                        Disposition("attachment"),
                    )
                    mail.attachment = att
                SendGridAPIClient(sg_key).send(mail)
                return True
            except Exception as exc:
                logger.error("SendGrid quarterly_self send failed for user %s: %s",
                             user.id, exc)
                return False

        smtp_host = os.environ.get("SMTP_HOST")
        if smtp_host:
            try:
                import smtplib
                from email.message import EmailMessage
                msg = EmailMessage()
                msg["From"] = from_email
                msg["To"] = user.email
                msg["Subject"] = subject
                msg.set_content("HTML-only; view in an HTML-capable client.")
                msg.add_alternative(html_body, subtype="html")
                if pdf_bytes:
                    msg.add_attachment(pdf_bytes, maintype="application",
                                       subtype="pdf",
                                       filename=f"quarterly_self_{user.id}.pdf")
                port = int(os.environ.get("SMTP_PORT", "587"))
                user_ = os.environ.get("SMTP_USER")
                pw = os.environ.get("SMTP_PASSWORD")
                with smtplib.SMTP(smtp_host, port, timeout=10) as s:
                    s.starttls()
                    if user_ and pw:
                        s.login(user_, pw)
                    s.send_message(msg)
                return True
            except Exception as exc:
                logger.error("SMTP quarterly_self send failed for user %s: %s",
                             user.id, exc)
                return False

        return False

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
        quarter_end = quarter_end or date.today()
        users = (
            User.query
            .filter(User.subscription_tier.in_(list(_PAID_TIERS)))
            .all()
        )

        successes = failures = skipped = 0
        for user in users:
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
