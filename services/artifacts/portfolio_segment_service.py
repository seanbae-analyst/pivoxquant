"""Portfolio Segment Report — quarterly 4-page PDF (Premium).

Cadence
-------
Fires quarter +7 days (1/7, 4/7, 7/7, 10/7) at 10:00 KST.

Sections (4 pages)
------------------
    P1  Sector   — GICS 11 weighted return + PnL per sector
    P2  Region   — US / KR / Other
    P3  Style    — Growth / Value / Dividend / Tech / Cyclical
    P4  Best/Worst + disclaimer

Segmentation basis
------------------
- Sector is resolved through `fetcher.get_stock_snapshot(ticker)` and
  normalised into the GICS 11 set (unknown → "Unknown").
- Region is inferred from the ticker suffix: `.KS`/`.KQ` → KR,
  everything else → US (crypto/ETFs also land under US; tightening
  is an explicit non-goal of the MVP).
- Style comes from SignalCache.data_json["style"] when present; else
  falls back to a sector-based rule (Tech sector → Tech, Consumer
  Discretionary → Cyclical, Utilities/REITs → Dividend, etc).

Algorithmic only — no AI. Prose is deterministic best/worst sentences.
The disclaimer partial is included on page 4.
"""
from __future__ import annotations

import logging
import math
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from extensions import db
from models import Artifact, Position, User
from services.legal_filter import detect_prohibited, safe_scrub

logger = logging.getLogger(__name__)


_TEMPLATE_DIR = Path(__file__).parent / "templates"
_DEFAULT_STORAGE_DIR = (
    Path(__file__).resolve().parents[2] / "artifacts" / "portfolio_segment"
)
# Shared set so premium_plus / founding_lifetime are never silently dropped.
from ._tiers import PAID_TIERS_PREMIUM_AND_UP as _PAID_TIERS  # noqa: E402
from services.artifacts._i18n import localize_ctx, resolve_locale  # Wave F i18n


# GICS 11 (canonical).
_GICS_11 = {
    "Energy", "Materials", "Industrials", "Consumer Discretionary",
    "Consumer Staples", "Health Care", "Financials", "Information Technology",
    "Communication Services", "Utilities", "Real Estate",
}

# Common vendor aliases → GICS label.
_SECTOR_ALIAS = {
    "Technology":                 "Information Technology",
    "Tech":                       "Information Technology",
    "IT":                         "Information Technology",
    "Financial Services":         "Financials",
    "Healthcare":                 "Health Care",
    "Consumer Cyclical":          "Consumer Discretionary",
    "Consumer Defensive":         "Consumer Staples",
    "Basic Materials":            "Materials",
    "Communication":              "Communication Services",
    "Telecom":                    "Communication Services",
}


def _canon_sector(raw: Optional[str]) -> str:
    if not raw:
        return "Unknown"
    r = str(raw).strip()
    if r in _GICS_11:
        return r
    if r in _SECTOR_ALIAS:
        return _SECTOR_ALIAS[r]
    return r or "Unknown"


def _region_from_ticker(ticker: str) -> str:
    t = (ticker or "").upper()
    if t.endswith(".KS") or t.endswith(".KQ"):
        return "KR"
    if t.endswith(".T") or t.endswith(".HK") or t.endswith(".L"):
        return "Other"
    # Plain ticker — US.
    return "US"


_STYLE_SECTOR_MAP = {
    "Information Technology":   "Tech",
    "Communication Services":   "Tech",
    "Consumer Discretionary":   "Cyclical",
    "Industrials":              "Cyclical",
    "Energy":                   "Cyclical",
    "Materials":                "Cyclical",
    "Financials":               "Value",
    "Utilities":                "Dividend",
    "Real Estate":              "Dividend",
    "Consumer Staples":         "Dividend",
    "Health Care":              "Growth",
}


def _style_from_signal_or_sector(ticker: str, sector_canon: str) -> str:
    """SignalCache.data_json['style'] if present, else sector fallback."""
    try:
        from models import SignalCache  # type: ignore
        row = SignalCache.query.filter_by(ticker=ticker).first()
        if row and row.data_json:
            st = row.data_json.get("style") if isinstance(row.data_json, dict) else None
            if isinstance(st, str) and st.strip():
                return st.strip()
    except Exception:
        logger.debug("silent-fallback: _style_from_signal_or_sector", exc_info=True)
        pass
    return _STYLE_SECTOR_MAP.get(sector_canon, "Growth")


# ── lazy deps ────────────────────────────────────────────────────────────────

def _try_import_weasyprint():
    try:
        from weasyprint import HTML  # type: ignore
        return HTML
    except Exception as exc:  # pragma: no cover
        logger.info("WeasyPrint unavailable (%s); skipping PDF.", exc)
        return None


def _try_import_jinja():
    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape
        return Environment, FileSystemLoader, select_autoescape
    except Exception as exc:  # pragma: no cover
        logger.warning("Jinja2 unavailable (%s).", exc)
        return None, None, None


def _fx_rate() -> float:
    """Spot USD/KRW with a safe fallback when the service is unavailable.

    Mirrors `dividend_income_service._fx_rate` so multi-currency books are
    normalised identically across artefacts.
    """
    # Single SoT: services.fx_service.spot_usdkrw (live rate when sane >=900,
    # else FALLBACK_USDKRW). Was a copy-pasted >=900/1380 block in 7 artifacts.
    from services import fx_service
    return fx_service.spot_usdkrw()


def _normalize_mv(native_mv: float, ticker: str, report_ccy: str,
                  fx: float) -> float:
    """Convert a position's native market value into the report currency.

    Native MV is KRW for `.KS/.KQ` tickers and USD otherwise. `fx` is
    USD→KRW (>= 900). Without this, summing raw native values over-weights
    KRW holdings ~1000x in a mixed book — distorting weights, weighted
    returns, and best/worst-segment ranking.
    """
    is_kr = ticker.upper().endswith((".KS", ".KQ"))
    if report_ccy == "USD":
        return native_mv / fx if is_kr else native_mv
    # report_ccy == "KRW"
    return native_mv if is_kr else native_mv * fx


def _storage_dir() -> Path:
    override = os.environ.get("PORTFOLIO_SEGMENT_STORAGE_DIR")
    d = Path(override) if override else _DEFAULT_STORAGE_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_snapshot(ticker: str) -> dict[str, Any] | None:
    try:
        from services.container import fetcher
        return fetcher.get_stock_snapshot(ticker)
    except Exception as exc:
        logger.debug("snapshot failed for %s: %s", ticker, exc)
        return None


def _safe_price_at(ticker: str, period_start: date) -> tuple[Optional[float],
                                                             Optional[float]]:
    """Return (start_price, end_price). Falls back to None for either leg
    on any failure. Uses 6mo history which comfortably brackets a single
    quarter plus fetch latency."""
    try:
        from services.container import fetcher
        hist = fetcher.get_price_history(ticker, period="6mo")
        if hist is None or "Close" not in hist or len(hist["Close"]) < 2:
            return None, None
        closes = hist["Close"]
        end_px = float(closes.iloc[-1])
        # Index the closest available date to period_start.
        try:
            target = datetime.combine(period_start, datetime.min.time())
            idx = closes.index.get_indexer([target], method="nearest")[0]
            if idx < 0 or idx >= len(closes):
                start_px = float(closes.iloc[0])
            else:
                start_px = float(closes.iloc[idx])
        except Exception:
            start_px = float(closes.iloc[0])
        start_px = start_px if math.isfinite(start_px) else None
        end_px = end_px if math.isfinite(end_px) else None
        return start_px, end_px
    except Exception as exc:
        logger.debug("price window failed for %s: %s", ticker, exc)
        return None, None


# ── quarter helpers (mirrors self_audit_service) ─────────────────────────────

def _quarter_bounds(anchor: date) -> tuple[date, date, str]:
    """Return (start, end, label) for the quarter that was just closed.

    If `anchor` lands on the first week (day ≤ 7) of Jan/Apr/Jul/Oct we
    look at the *previous* quarter — this matches the cron cadence
    (q+7 days). Otherwise we use the quarter containing `anchor`.
    """
    month = anchor.month
    q_start_month = 3 * ((month - 1) // 3) + 1
    if anchor.day <= 7 and anchor.month in (1, 4, 7, 10):
        prev_end_month = q_start_month - 1
        prev_end_year = anchor.year
        if prev_end_month <= 0:
            prev_end_month = 12
            prev_end_year -= 1
        start_month = prev_end_month - 2
        start_year = prev_end_year
        if start_month <= 0:
            start_month += 12
            start_year -= 1
        start = date(start_year, start_month, 1)
        if prev_end_month == 12:
            end = date(prev_end_year, 12, 31)
        else:
            end = date(prev_end_year, prev_end_month + 1, 1) - timedelta(days=1)
    else:
        start = date(anchor.year, q_start_month, 1)
        end_month = q_start_month + 2
        if end_month >= 12:
            end = date(anchor.year, 12, 31)
        else:
            end = date(anchor.year, end_month + 1, 1) - timedelta(days=1)
    q_num = (start.month - 1) // 3 + 1
    label = f"{start.year} Q{q_num}"
    return start, end, label


# ── data ─────────────────────────────────────────────────────────────────────

@dataclass
class SegmentRow:
    label:     str
    weight_pct: float
    return_pct: Optional[float]
    pnl:       Optional[float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "label":      self.label,
            "weight_pct": round(self.weight_pct, 2),
            "return_pct": (round(self.return_pct, 2)
                           if self.return_pct is not None else None),
            "pnl":        (round(self.pnl, 2)
                           if self.pnl is not None else None),
        }


@dataclass
class SegmentContext:
    user_id:         int
    user_name:       str
    quarter_label:   str
    period_start:    date
    period_end:      date
    generated_at:    datetime
    portfolio_ccy:   str
    portfolio_value: Optional[float]
    sector_rows:     list[dict[str, Any]]
    region_rows:     list[dict[str, Any]]
    style_rows:      list[dict[str, Any]]
    best_segments:   list[dict[str, Any]]   # top 3 across (sector/region/style)
    worst_segments:  list[dict[str, Any]]   # bottom 3
    narrative:       str
    disclaimer:      str
    # Wave 6 — colophon provenance via `resolve_user_data_lineage`.
    data_sources:    list[dict[str, str]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id":         self.user_id,
            "user_name":       self.user_name,
            "quarter_label":   self.quarter_label,
            "period_start":    self.period_start.isoformat(),
            "period_end":      self.period_end.isoformat(),
            "generated_at":    self.generated_at.isoformat() + "Z",
            "portfolio_ccy":   self.portfolio_ccy,
            "portfolio_value": self.portfolio_value,
            "sector_rows":     self.sector_rows,
            "region_rows":     self.region_rows,
            "style_rows":      self.style_rows,
            "best_segments":   self.best_segments,
            "worst_segments":  self.worst_segments,
            "narrative":       self.narrative,
            "disclaimer":      self.disclaimer,
            "data_sources":    self.data_sources,
        }


# ── computation ──────────────────────────────────────────────────────────────

def _group_rows(entries: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    """Given per-position records, weight-average returns and sum PnL by `key`."""
    buckets: dict[str, dict[str, float]] = {}
    total_mv = sum(e["mv"] for e in entries) or 1.0
    for e in entries:
        k = e.get(key) or "Unknown"
        b = buckets.setdefault(k, {"mv": 0.0, "pnl": 0.0, "mv_rated": 0.0,
                                   "ret_mv": 0.0})
        b["mv"] += e["mv"]
        if e.get("pnl") is not None:
            b["pnl"] += float(e["pnl"])
        if e.get("return_pct") is not None:
            b["mv_rated"] += e["mv"]
            b["ret_mv"] += e["mv"] * float(e["return_pct"])

    rows: list[dict[str, Any]] = []
    for label, b in buckets.items():
        weight_pct = (b["mv"] / total_mv) * 100 if total_mv > 0 else 0.0
        ret_pct = (b["ret_mv"] / b["mv_rated"]) if b["mv_rated"] > 0 else None
        pnl = b["pnl"] if b["mv_rated"] > 0 else None
        rows.append(SegmentRow(
            label=label,
            weight_pct=weight_pct,
            return_pct=ret_pct,
            pnl=pnl,
        ).to_dict())
    rows.sort(key=lambda r: -r["weight_pct"])
    return rows


def _narrative(best: list[dict[str, Any]],
               worst: list[dict[str, Any]]) -> str:
    """Deterministic best/worst sentence. No AI — purely descriptive."""
    if not best and not worst:
        return ("이번 분기에 수익률이 관찰된 세그먼트 데이터가 부족했습니다. "
                "거래 이력이 쌓이면 다음 분기 리포트에서 더 자세한 breakdown이 "
                "제공됩니다.")
    best_line = ""
    worst_line = ""
    if best:
        b = best[0]
        ret = b.get("return_pct")
        ret_s = f"{ret:+.2f}%" if ret is not None else "—"
        best_line = (f"수익률 기준 상위 세그먼트는 {b['label']}이며 "
                     f"평균 {ret_s}가 관찰되었습니다.")
    if worst:
        w = worst[0]
        ret = w.get("return_pct")
        ret_s = f"{ret:+.2f}%" if ret is not None else "—"
        worst_line = (f"수익률 기준 하위 세그먼트는 {w['label']}로 "
                      f"평균 {ret_s}가 관찰되었습니다.")
    return (f"{best_line} {worst_line} 본 관찰은 해당 분기 보유 포지션의 "
            f"사실 기록일 뿐, 매매 판단이나 향후 전망을 포함하지 않습니다.")


# ── service ──────────────────────────────────────────────────────────────────

class PortfolioSegmentService:
    """Quarterly 4-page segment breakdown PDF (Premium)."""

    def generate_for_user(self, user_id: int,
                          quarter_end: date | None = None) -> dict[str, Any]:
        user = db.session.get(User, user_id)
        if not user:
            raise ValueError(f"user {user_id} not found")

        quarter_end = quarter_end or date.today()
        start, end, label = _quarter_bounds(quarter_end)
        positions = Position.query.filter_by(user_id=user_id).all()

        ccy = "USD"
        if positions and all(p.ticker.endswith((".KS", ".KQ")) for p in positions):
            ccy = "KRW"

        # Multi-currency normalization (CRITICAL). _safe_price_at returns
        # native prices (KRW for .KS/.KQ, USD otherwise). Every downstream
        # figure — weight_pct, weighted return, summed PnL, best/worst
        # ranking, portfolio_value — is driven by `mv`. Summing raw native
        # values over-weights KRW holdings ~1000x in a mixed book. Convert
        # each position into the report currency before aggregating.
        fx = _fx_rate()  # USD → KRW
        entries: list[dict[str, Any]] = []
        total_mv = 0.0
        for p in positions[:40]:  # cap to protect data budget
            start_px, end_px = _safe_price_at(p.ticker, start)
            snap = _safe_snapshot(p.ticker) or {}
            sector = _canon_sector(snap.get("sector"))
            region = _region_from_ticker(p.ticker)
            style = _style_from_signal_or_sector(p.ticker, sector)
            shares = float(p.shares or 0)
            native_mv = (end_px or float(p.avg_cost or 0)) * shares
            end_mv = _normalize_mv(native_mv, p.ticker, ccy, fx)
            total_mv += end_mv
            ret_pct: Optional[float] = None
            pnl: Optional[float] = None
            if start_px and end_px and start_px > 0 and shares > 0:
                ret_pct = (end_px / start_px - 1.0) * 100.0
                native_pnl = (end_px - start_px) * shares
                pnl = _normalize_mv(native_pnl, p.ticker, ccy, fx)
            entries.append({
                "ticker":     p.ticker,
                "sector":     sector,
                "region":     region,
                "style":      style,
                "mv":         end_mv,
                "return_pct": ret_pct,
                "pnl":        pnl,
            })

        sector_rows = _group_rows(entries, "sector")
        region_rows = _group_rows(entries, "region")
        style_rows  = _group_rows(entries, "style")

        def _tag(rows: list[dict[str, Any]], dim: str) -> list[dict[str, Any]]:
            return [dict(r, dim=dim) for r in rows if r.get("return_pct") is not None]

        rated_all = _tag(sector_rows, "Sector") + _tag(region_rows, "Region") \
                    + _tag(style_rows, "Style")
        best = sorted(rated_all, key=lambda r: -r["return_pct"])[:3]
        worst = sorted(rated_all, key=lambda r: r["return_pct"])[:3]
        narrative = _narrative(best, worst)

        # Wave 6 — colophon data lineage. Populates only broker
        # connections the user actually has. Empty list renders a
        # neutral "Data sources not specified" line in the template.
        try:
            from services.artifacts.data_source_resolver import (
                resolve_user_data_lineage,
            )
            data_sources = resolve_user_data_lineage(user_id)
        except Exception as exc:
            logger.debug("portfolio_segment lineage resolve failed for user %s: %s",
                         user_id, exc)
            data_sources = []

        ctx = SegmentContext(
            user_id=user_id,
            user_name=user.name or user.email.split("@")[0],
            quarter_label=label,
            period_start=start,
            period_end=end,
            generated_at=datetime.now(timezone.utc).replace(tzinfo=None),
            portfolio_ccy=ccy,
            portfolio_value=round(total_mv, 2) if total_mv > 0 else None,
            sector_rows=sector_rows,
            region_rows=region_rows,
            style_rows=style_rows,
            best_segments=best,
            worst_segments=worst,
            narrative=narrative,
            disclaimer="정보 제공 목적이며 투자 권유가 아닙니다. 투자 판단은 본인 책임입니다.",
            data_sources=data_sources,
        )
        return ctx.to_dict()

    # ── v3 design shape (CEO redesign 2026-04-30) ──────────────────────────

    def _to_v3_shape(self, data: dict[str, Any]) -> dict[str, Any]:
        """Map generate_for_user(...) onto the v3 2-page Pro design shape
        used by templates/portfolio_segment.html. Mirrors the React component.

        Missing fields fall back to em-dash. No directive vocabulary.
        """
        sectors_raw = data.get("sector_rows") or []
        regions_raw = data.get("region_rows") or []
        styles_raw  = data.get("style_rows") or []
        ccy = (data.get("portfolio_ccy") or "USD").upper()
        nav = data.get("portfolio_value")
        narrative = data.get("narrative") or ""
        label = data.get("quarter_label") or "—"

        def _money(v: Any) -> str:
            try:
                n = float(v)
            except (TypeError, ValueError):
                return "—"
            if n >= 1_000_000_000:
                return f"${n/1_000_000_000:.2f}B"
            if n >= 1_000_000:
                return f"${n/1_000_000:.2f}M"
            if n >= 1_000:
                return f"${n/1_000:.0f}k"
            return f"${n:,.0f}"

        holdings_count = sum(int(r.get("count") or 0) for r in sectors_raw) or len(sectors_raw)
        avg_pos = (100.0 / holdings_count) if holdings_count else 0
        kpi = {
            "nav":          {"value": _money(nav), "delta": ""},
            "holdings":     {"value": str(holdings_count) if holdings_count else "—",
                              "delta": "보유 종목 수"},
            "avg_pos":      {"value": f"{avg_pos:.1f}%" if avg_pos else "—",
                              "delta": "균등 분배 기준"},
            "active_share": {"value": "—", "delta": "vs 벤치마크"},
        }

        def _alloc_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
            if not rows:
                return []
            max_pct = max((float(r.get("weight_pct") or 0) for r in rows), default=0)
            out = []
            for r in rows[:8]:
                pct = float(r.get("weight_pct") or 0)
                bar = (pct / max_pct * 100.0) if max_pct > 0 else 0
                out.append({
                    "name":        r.get("name") or r.get("label") or "—",
                    "pct":         round(bar, 1),
                    "pct_display": f"{pct:.1f}%",
                    "tone":        None,
                    "flat":        bar < 35,
                })
            return out

        sectors = _alloc_rows(sectors_raw)
        for s_view, s_raw in zip(sectors, sectors_raw):
            try:
                w = float(s_raw.get("weight_pct") or 0)
                if w > 35.0:
                    s_view["tone"] = "neg"
                    s_view["pct_display"] = f"{w:.1f}% / 35% lim"
            except (TypeError, ValueError):
                logger.debug("silent-fallback: _alloc_rows", exc_info=True)
                pass

        geography = _alloc_rows(regions_raw)

        usd_pct = krw_pct = 0.0
        for r in regions_raw:
            name = (r.get("name") or "").lower()
            try:
                pct = float(r.get("weight_pct") or 0)
            except (TypeError, ValueError):
                pct = 0.0
            if "kr" in name or "korea" in name:
                krw_pct += pct
            else:
                usd_pct += pct
        if usd_pct or krw_pct:
            fx = [
                {"ccy": "USD", "pct": f"{usd_pct:.0f}%"},
                {"ccy": "KRW", "pct": f"{krw_pct:.0f}%"},
            ]
        else:
            fx = [{"ccy": ccy, "pct": "100%"}]

        factors: list[dict[str, Any]] = []
        for r in styles_raw[:6]:
            ret = r.get("return_pct")
            tone = "pos" if (ret or 0) > 0 else ("neg" if (ret or 0) < 0 else "neutral")
            factors.append({
                "factor":         r.get("name") or "—",
                "exposure":       f"{float(r.get('weight_pct') or 0):.2f}",
                "vs_bench":       "—",
                "vs_bench_tone":  "neutral",
                "mtd":            f"{ret:+.2f}%" if ret is not None else "—",
                "mtd_tone":       tone,
                "ytd":            "—",
                "ytd_tone":       "neutral",
            })

        return {
            "as_of_label":   label,
            "report_tag":    f"PS-{label.replace(' ', '-')}",
            "nav":           kpi["nav"],
            "holdings":      kpi["holdings"],
            "avg_pos":       kpi["avg_pos"],
            "active_share":  kpi["active_share"],
            "sectors":       sectors,
            "geography":     geography,
            "fx":            fx,
            "fx_note":       "환노출 분포 관찰. 헤지 결정은 별도 항목.",
            "factors":       factors,
            "top_bottom":    [],
            "cfo_note":      narrative or "포트폴리오 분해 결과를 별도 검토.",
        }

    # ── render ──────────────────────────────────────────────────────────────

    def _resolve_persona(self, data: dict[str, Any]) -> str:
        """Same persona contract as weekly_memo / quarterly_self_report."""
        if "persona" in data and data["persona"]:
            try:
                from services.artifacts.persona_resolver import resolve_persona_from_code
                return resolve_persona_from_code(data["persona"])
            except Exception:
                return "balanced"
        user_id = data.get("user_id")
        if user_id is None:
            return "balanced"
        try:
            from services.artifacts.persona_resolver import (
                DEFAULT_PERSONA, resolve_persona,
            )
            from models import InvestmentProfile
            profile = InvestmentProfile.query.filter_by(user_id=user_id).first()
            return resolve_persona(profile) if profile else DEFAULT_PERSONA
        except Exception as exc:
            logger.debug("portfolio_segment persona resolution failed: %s", exc)
            return "balanced"

    def render_pdf_html(self, data: dict[str, Any]) -> str:
        env = self._jinja_env()
        if env is None:
            html = self._fallback_html(data)
        else:
            try:
                ctx = dict(data)
                from services.artifacts._name_enrich import enrich_v3_names
                ctx["v3"] = enrich_v3_names(self._to_v3_shape(data))
                ctx["persona"] = self._resolve_persona(data)
                tpl = env.get_template("portfolio_segment.html")
                ctx = localize_ctx(ctx, resolve_locale(user_id=ctx.get('user_id'), data=data))
                html = tpl.render(**ctx)
            except Exception as exc:
                logger.warning("portfolio_segment v3 render failed: %s", exc)
                html = self._fallback_html(data)
        scrubbed = safe_scrub(html, context="portfolio_segment") or html
        _prohibited = detect_prohibited(scrubbed)
        if _prohibited:
            logger.warning("legal_filter fail: portfolio_segment (%s)", _prohibited)
        return scrubbed

    def render_html(self, data: dict[str, Any]) -> str:
        return self.render_pdf_html(data)

    def render_pdf(self, data: dict[str, Any]) -> Optional[bytes]:
        HTML = _try_import_weasyprint()
        if HTML is None:
            return None
        html_str = self.render_pdf_html(data)
        try:
            return HTML(string=html_str).write_pdf()
        except Exception as exc:  # pragma: no cover
            logger.error("WeasyPrint portfolio_segment failed: %s", exc)
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
<h1>Portfolio Segment — {escape(data.get('quarter_label',''))}</h1>
<p>{escape(data.get('narrative',''))}</p>
<p><em>{escape(data.get('disclaimer',''))}</em></p>
</body></html>"""

    # ── send ────────────────────────────────────────────────────────────────

    def send_email(self, user: User, pdf_bytes: Optional[bytes],
                   html_body: str, subject: str) -> bool:
        """Phase 7 — delegate to :class:`EmailSender`."""
        from services.email import EmailSender, EmailCategory

        sender = EmailSender()
        ok = sender.send(
            user,
            email_category=EmailCategory.INFORMATION,
            subject=subject,
            html_body=html_body,
            from_env_var="WEEKLY_MEMO_FROM_EMAIL",
            from_default="reports@pivoxquant.com",
            pdf_bytes=pdf_bytes,
            pdf_filename=f"portfolio_segment_{user.id}.pdf",
        )
        # Stash the SendGrid X-Message-Id so _persist can write it onto the
        # Artifact row (webhook bounce/open mapping — 정통망법 §50).
        self._last_message_id = getattr(sender, "last_message_id", None)
        return ok

    # ── persist + orchestrate ───────────────────────────────────────────────

    def _persist(self, user_id: int, data: dict[str, Any],
                 pdf_bytes: Optional[bytes], sent: bool) -> Artifact:
        title = f"Portfolio Segment — {data['quarter_label']}"
        pdf_path: Optional[str] = None
        if pdf_bytes:
            try:
                base = _storage_dir() / str(user_id)
                base.mkdir(parents=True, exist_ok=True)
                fname = re.sub(r"[^A-Za-z0-9_-]+", "_", data["quarter_label"])
                path = base / f"{fname}.pdf"
                path.write_bytes(pdf_bytes)
                pdf_path = str(path)
            except Exception as exc:
                logger.warning("segment PDF write failed for user %s: %s",
                               user_id, exc)

        artefact = (
            Artifact.query
            .filter_by(user_id=user_id, type="portfolio_segment", title=title)
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
                type="portfolio_segment",
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
        positions = Position.query.filter_by(user_id=user.id).count()
        if positions == 0:
            logger.info("skipping portfolio_segment for user %s — empty", user.id)
            return None

        data = self.generate_for_user(user.id, quarter_end=quarter_end)
        pdf_bytes = self.render_pdf(data)
        html_body = self.render_html(data)

        subject = f"PivoxQuant Portfolio Segment — {data['quarter_label']}"

        sent = False
        if send:
            try:
                sent = self.send_email(user, pdf_bytes, html_body, subject)
            except Exception as exc:
                logger.error("portfolio_segment send raised for user %s: %s",
                             user.id, exc)
                sent = False
        return self._persist(user.id, data, pdf_bytes, sent)

    def run_quarterly(self, quarter_end: date | None = None) -> dict[str, Any]:
        """Cron target — 1/7, 4/7, 7/7, 10/7 10:00 KST. Premium only."""
        from services.artifacts import iter_users_chunked

        quarter_end = quarter_end or date.today()
        users = (
            User.query
            .filter(User.subscription_tier.in_(list(_PAID_TIERS)))
            .all()
        )

        successes = failures = skipped = 0
        for user in iter_users_chunked(users, label="portfolio_segment.quarterly"):
            try:
                result = self.run_for_user(user, quarter_end=quarter_end)
                if result is None:
                    skipped += 1
                else:
                    successes += 1
            except Exception as exc:
                db.session.rollback()
                failures += 1
                logger.error("portfolio_segment failed for user %s: %s",
                             user.id, exc)

        summary = {
            "quarter_end": quarter_end.isoformat(),
            "attempted":   len(users),
            "success":     successes,
            "failed":      failures,
            "skipped":     skipped,
        }
        logger.info("portfolio_segment quarterly run: %s", summary)
        return summary
