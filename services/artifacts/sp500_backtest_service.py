"""SP500 Backtest Observation — Premium 2-page admin-debug PDF.

Purpose
-------
Renders the published `docs/BACKTEST_RESULTS.md` observation window
(2021-12-01 → 2026-04-17, Strategy C: TSMOM + MeanReversion) as a
v3 Premium PDF. This is **not** a per-user artifact — there is no
cron, no email pipeline, no `_ARTIFACT_DISPATCH` integration.

Surfaces
--------
- Admin preview only (`routes/admin_preview.py` -> sp500_backtest entry)
- Historical observation; no claim about future performance

Legal posture
-------------
- All numbers are descriptive records of the historical observation
  window. The artifact says "관찰" / "기록" everywhere it would
  otherwise say "수익률" / "성과".
- No buy/sell/추천/조언 vocabulary; legal_filter scrubs all prose.
- Disclaimer partial mandatory.

Entry points
------------
    SP500BacktestService().render_pdf_html(data) → str
    SP500BacktestService().render_html(data)     → str  (alias)
    SP500BacktestService().render_pdf(data)      → bytes | None
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from services.legal_filter import is_compliant, safe_scrub

logger = logging.getLogger(__name__)


_TEMPLATE_DIR = Path(__file__).parent / "templates"


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


# ── service ──────────────────────────────────────────────────────────────────

class SP500BacktestService:
    """Premium 2-page SP500 backtest observation PDF (admin-debug only)."""

    _NOT_CLAIMED: list[str] = [
        "본 결과는 과거 관찰 구간의 통계 기록이며, 향후 수익률을 보장하지 않습니다.",
        "어떠한 매매 전략도 권유·추천하지 않습니다.",
        "사용자 본인 거래 결과와는 별개의 백테스트 시뮬레이션입니다.",
        "투자자문 또는 일임 서비스가 아닙니다.",
        "관찰 구간 외 시점의 동일 결과를 보장하지 않습니다.",
    ]

    _PULLQUOTE_DEFAULT = (
        "백테스트는 미래의 약속이 아니라 과거의 기록입니다 — "
        "시장은 같은 강을 두 번 흐르지 않습니다."
    )

    def _to_v3_shape(self, data: dict[str, Any]) -> dict[str, Any]:
        """Map sample/published backtest data onto v3 2-page Premium shape."""
        period_start = data.get("period_start") or "—"
        period_end = data.get("period_end") or "—"
        as_of = data.get("generated_at") or period_end

        def _pct(v: Any, signed: bool = True) -> str:
            try:
                n = float(v)
            except (TypeError, ValueError):
                return "—"
            return f"{n:+.2f}%" if signed else f"{n:.2f}%"

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

        annual_rows = []
        for r in (data.get("annual_rows") or [])[:12]:
            annual_rows.append({
                "year":     str(r.get("year") or "—"),
                "strategy": _pct(r.get("strategy")),
                "strategy_tone": _tone(r.get("strategy")),
                "spy":      _pct(r.get("spy")),
                "spy_tone": _tone(r.get("spy")),
                "alpha":    _pct(r.get("alpha")),
                "alpha_tone": _tone(r.get("alpha")),
                "mdd":      _pct(r.get("mdd")),
                "sharpe":   (f"{float(r.get('sharpe')):.2f}"
                             if r.get("sharpe") is not None else "—"),
            })

        return {
            "doc":             f"SP500 Backtest · {period_start[:7]}~{period_end[:7]}",
            "doc_short":       f"{period_start[:7]} ~ {period_end[:7]}",
            "issued":          f"Issued · {str(as_of)[:10]}",
            "kpi_cagr":        _pct(data.get("hero_cagr")),
            "kpi_cagr_tone":   _tone(data.get("hero_cagr")),
            "kpi_sharpe":      (f"{float(data.get('hero_sharpe')):.2f}"
                                if data.get("hero_sharpe") is not None else "—"),
            "kpi_alpha":       _pct(data.get("hero_alpha")),
            "kpi_alpha_tone":  _tone(data.get("hero_alpha")),
            "kpi_2022":        _pct(data.get("hero_2022_spread")),
            "kpi_2022_tone":   _tone(data.get("hero_2022_spread")),
            "period_start":    period_start,
            "period_end":      period_end,
            "annual_rows":     annual_rows,
            "pullquote":       self._PULLQUOTE_DEFAULT,
            "not_claimed":     list(self._NOT_CLAIMED),
        }

    def _resolve_persona(self, data: dict[str, Any]) -> str:
        """Same persona contract as weekly_memo / quarterly_self_report.

        Note: sp500_backtest is admin-debug only with universal data —
        persona only colours the eyebrow label (no body branching).
        """
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
            logger.debug("sp500_backtest persona resolution failed: %s", exc)
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
                tpl = env.get_template("sp500_backtest.html")
                html = tpl.render(**ctx)
            except Exception as exc:
                logger.warning("sp500_backtest render failed: %s", exc)
                html = self._fallback_html(data)
        scrubbed = safe_scrub(html, context="sp500_backtest") or html
        if not is_compliant(scrubbed):
            logger.warning("legal_filter fail: sp500_backtest")
        return scrubbed

    def render_html(self, data: dict[str, Any]) -> str:
        return self.render_pdf_html(data)

    def render_pdf(self, data: dict[str, Any]) -> Optional[bytes]:
        HTML = _try_import_weasyprint()
        if HTML is None:
            return None
        try:
            return HTML(string=self.render_pdf_html(data)).write_pdf()
        except Exception as exc:  # pragma: no cover
            logger.error("WeasyPrint sp500_backtest render failed: %s", exc)
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
<h1>SP500 Backtest — {escape(str(data.get('period_start',''))[:10])} ~ {escape(str(data.get('period_end',''))[:10])}</h1>
<p>관찰 구간 백테스트 결과 (admin-debug only).</p>
</body></html>"""
