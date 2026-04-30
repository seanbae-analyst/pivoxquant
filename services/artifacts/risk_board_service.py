"""Risk Board Meeting Deck — monthly + VIX-spike PDF deck (Premium).

Cadence
-------
- Scheduled: APScheduler fires `run_monthly()` on day 15 at 09:30 KST.
- Event-driven: `run_vix_spike_check()` runs hourly. When VIX crosses from
  below 25 to above 25 since the last poll, every Premium user gets a
  fresh deck emailed immediately. State is persisted on-disk in a tiny
  JSON file under the artifact storage dir so restarts don't replay a
  spike that was already notified.

Deck (8 pages)
--------------
    P1  Cover        — portfolio snapshot + period
    P2  VaR          — 95 / 99 historical VaR
    P3  Risk Ratios  — Sharpe / Sortino / Calmar
    P4  Drawdown     — max DD + sector concentration pie
    P5  Tail & CES   — Tail Ratio + Component ES top 3
    P6  7-Layer      — Risk Defense layer PASS/FAIL table
    P7  Top 3 Risks  — AI Haiku narrative (scrubbed)
    P8  Disclaimer   — legal boilerplate

Compliance
----------
- No "reduce exposure" / "sell" language — use "관찰 지표" / "체크리스트".
- AI narrative passes through `legal_filter.safe_scrub`.
- `_disclaimer.html` included at the end of the deck.

Read-only dependencies
----------------------
- `risk_defense.RiskDefenseSystem.check_all` — we call this, never modify.
- `engine` / `risk_models` — consulted only through public helpers.
- No new ORM models; persists into the shared `Artifact` table under
  `type="risk_board"`.
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np

from extensions import db
from models import Artifact, Position, User

logger = logging.getLogger(__name__)


_TEMPLATE_DIR = Path(__file__).parent / "templates"
_DEFAULT_STORAGE_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "risk_board"
_PAID_TIERS = frozenset({"premium", "elite"})


def _storage_dir() -> Path:
    override = os.environ.get("RISK_BOARD_STORAGE_DIR")
    d = Path(override) if override else _DEFAULT_STORAGE_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _vix_state_path() -> Path:
    return _storage_dir() / "_vix_state.json"


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


def _safe_history(ticker: str, period: str = "6mo"):
    try:
        from services.container import fetcher
        return fetcher.get_price_history(ticker, period=period)
    except Exception as exc:
        logger.debug("history fetch failed for %s: %s", ticker, exc)
        return None


def _safe_snapshot(ticker: str) -> dict[str, Any] | None:
    try:
        from services.container import fetcher
        return fetcher.get_stock_snapshot(ticker)
    except Exception as exc:
        logger.debug("snapshot fetch failed for %s: %s", ticker, exc)
        return None


def _safe_price(ticker: str) -> Optional[float]:
    try:
        from services.container import fetcher
        hist = fetcher.get_price_history(ticker, period="5d")
        if hist is None or "Close" not in hist or len(hist["Close"]) == 0:
            return None
        return float(hist["Close"].iloc[-1])
    except Exception:
        return None


def get_current_vix() -> Optional[float]:
    """Latest ^VIX close. Returns None on any failure."""
    try:
        from services.container import fetcher
        hist = fetcher.get_price_history("^VIX", period="5d")
        if hist is None or "Close" not in hist or len(hist["Close"]) == 0:
            return None
        return float(hist["Close"].iloc[-1])
    except Exception as exc:
        logger.debug("vix fetch failed: %s", exc)
        return None


# ── data ─────────────────────────────────────────────────────────────────────

@dataclass
class RiskBoardContext:
    user_id:           int
    user_name:         str
    period_label:      str               # "April 2026" or "VIX Spike 2026-04-19"
    trigger:           str               # "monthly" | "vix_spike"
    generated_at:      datetime

    # Snapshot
    portfolio_value:   Optional[float]
    portfolio_ccy:     str
    position_count:    int

    # VaR (%), computed at 95% and 99% over 3m
    var95_pct:         Optional[float]
    var99_pct:         Optional[float]

    # Risk ratios
    sharpe_annual:     Optional[float]
    sortino_annual:    Optional[float]
    calmar:            Optional[float]

    # Drawdown + sector
    max_drawdown_pct:  Optional[float]   # negative
    sector_breakdown:  list[dict[str, Any]]  # [{sector, weight_pct}]

    # Tail
    tail_ratio:        Optional[float]
    component_es:      list[dict[str, Any]]  # top 3 contributors

    # 7-layer status
    vix_current:       Optional[float]
    defense_score:     Optional[int]
    defense_status:    Optional[str]     # GREEN/YELLOW/RED
    layer_status:      list[dict[str, Any]]   # [{layer, label, passed, note}]

    # AI narrative
    top_risks:         str               # scrubbed paragraph
    disclaimer:        str
    # Wave 6 — colophon provenance via `resolve_user_data_lineage`.
    data_sources:      list[dict[str, str]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id":          self.user_id,
            "user_name":        self.user_name,
            "period_label":     self.period_label,
            "trigger":          self.trigger,
            "generated_at":     self.generated_at.isoformat() + "Z",
            "portfolio_value":  self.portfolio_value,
            "portfolio_ccy":    self.portfolio_ccy,
            "position_count":   self.position_count,
            "var95_pct":        self.var95_pct,
            "var99_pct":        self.var99_pct,
            "sharpe_annual":    self.sharpe_annual,
            "sortino_annual":   self.sortino_annual,
            "calmar":           self.calmar,
            "max_drawdown_pct": self.max_drawdown_pct,
            "sector_breakdown": self.sector_breakdown,
            "tail_ratio":       self.tail_ratio,
            "component_es":     self.component_es,
            "vix_current":      self.vix_current,
            "defense_score":    self.defense_score,
            "defense_status":   self.defense_status,
            "layer_status":     self.layer_status,
            "top_risks":        self.top_risks,
            "disclaimer":       self.disclaimer,
            "data_sources":     self.data_sources,
        }


# ── metric builders ──────────────────────────────────────────────────────────

def _fetch_position_returns(positions: list[Position],
                            days: int = 63) -> tuple[list[str], list[dict[str, Any]],
                                                     Optional[np.ndarray]]:
    """Fetch daily returns and enriched position records.

    Returns (tickers, pos_records, returns_matrix). The matrix columns are
    aligned with the order of tickers/pos_records and share the shortest
    series so VaR/correlation math is well-defined.
    """
    tickers: list[str] = []
    pos_records: list[dict[str, Any]] = []
    rets_lists: list[list[float]] = []

    total_mv = 0.0
    raw: list[tuple[Position, float, float]] = []  # (position, price, mv)
    for p in positions[:25]:
        px = _safe_price(p.ticker) or float(p.avg_cost or 0)
        mv = px * float(p.shares or 0)
        raw.append((p, px, mv))
        total_mv += mv

    for p, px, mv in raw:
        hist = _safe_history(p.ticker, period="3mo")
        if hist is None or "Close" not in hist:
            continue
        try:
            closes = hist["Close"].tail(days + 1).tolist()
            if len(closes) < 10:
                continue
            rets = []
            for a, b in zip(closes[:-1], closes[1:]):
                a, b = float(a), float(b)
                if a <= 0:
                    continue
                rets.append((b / a) - 1.0)
            if not rets:
                continue
            snap = _safe_snapshot(p.ticker) or {}
            sector = snap.get("sector") or "Unknown"
            weight = (mv / total_mv) if total_mv > 0 else 1.0 / max(len(raw), 1)
            tickers.append(p.ticker)
            pos_records.append({
                "ticker": p.ticker,
                "value":  round(mv, 2),
                "weight": float(weight),
                "sector": sector,
                "returns_20d": rets[-20:] if len(rets) >= 20 else rets,
            })
            rets_lists.append(rets)
        except Exception as exc:
            logger.debug("return build failed for %s: %s", p.ticker, exc)
            continue

    if not rets_lists:
        return [], [], None

    n = min(len(r) for r in rets_lists)
    aligned = np.array([r[-n:] for r in rets_lists], dtype=np.float64).T  # (n_days, n_pos)
    return tickers, pos_records, aligned


def _portfolio_daily_returns(pos_records: list[dict[str, Any]],
                             matrix: Optional[np.ndarray]) -> list[float]:
    if matrix is None or matrix.shape[0] == 0:
        return []
    weights = np.array([p["weight"] for p in pos_records], dtype=np.float64)
    if weights.sum() <= 0:
        return []
    weights = weights / weights.sum()
    port = matrix @ weights
    return [float(x) for x in port.tolist()]


def _var_pct(rets: list[float], pct: float) -> Optional[float]:
    if len(rets) < 20:
        return None
    try:
        arr = np.array(rets, dtype=np.float64)
        q = float(np.percentile(arr, pct))
        # VaR expressed as a positive loss % (e.g. 2.7 means -2.7%)
        return round(-q * 100, 2)
    except Exception:
        return None


def _sharpe(rets: list[float]) -> Optional[float]:
    if len(rets) < 10:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / max(len(rets) - 1, 1)
    std = math.sqrt(var)
    if std <= 0:
        return None
    return round((mean / std) * math.sqrt(252), 2)


def _sortino(rets: list[float]) -> Optional[float]:
    if len(rets) < 10:
        return None
    mean = sum(rets) / len(rets)
    downs = [r for r in rets if r < 0]
    if not downs:
        return None
    dd_var = sum(r * r for r in downs) / len(downs)
    dd_std = math.sqrt(dd_var)
    if dd_std <= 0:
        return None
    return round((mean / dd_std) * math.sqrt(252), 2)


def _max_dd(rets: list[float]) -> Optional[float]:
    if len(rets) < 10:
        return None
    equity = 1.0
    peak = 1.0
    mdd = 0.0
    for r in rets:
        equity *= (1.0 + r)
        if equity > peak:
            peak = equity
        if peak > 0:
            dd = (equity - peak) / peak
            if dd < mdd:
                mdd = dd
    return round(mdd * 100, 2)


def _calmar(rets: list[float], mdd_pct: Optional[float]) -> Optional[float]:
    if mdd_pct is None or mdd_pct >= 0 or len(rets) < 10:
        return None
    ann_ret = (sum(rets) / len(rets)) * 252 * 100
    return round(ann_ret / abs(mdd_pct), 2)


def _tail_ratio(rets: list[float]) -> Optional[float]:
    """95p / |5p| — higher = fatter right tail relative to left."""
    if len(rets) < 20:
        return None
    try:
        arr = np.array(rets, dtype=np.float64)
        right = float(np.percentile(arr, 95))
        left = float(np.percentile(arr, 5))
        if left >= 0:
            return None
        return round(right / abs(left), 2)
    except Exception:
        return None


def _component_es(pos_records: list[dict[str, Any]],
                  matrix: Optional[np.ndarray],
                  top_n: int = 3) -> list[dict[str, Any]]:
    """Return top-N positions by absolute tail-loss contribution."""
    if matrix is None or matrix.shape[0] < 20 or not pos_records:
        return []
    try:
        weights = np.array([p["weight"] for p in pos_records], dtype=np.float64)
        if weights.sum() <= 0:
            return []
        weights = weights / weights.sum()
        port = matrix @ weights
        thr = float(np.percentile(port, 5))
        mask = port <= thr
        if mask.sum() == 0:
            return []
        comp = np.mean(matrix[mask], axis=0) * weights
        entries = []
        for i, rec in enumerate(pos_records):
            if i >= len(comp):
                continue
            entries.append({
                "ticker":      rec["ticker"],
                "sector":      rec.get("sector", "Unknown"),
                "es_contrib":  round(float(abs(comp[i])) * 100, 3),  # as %
            })
        entries.sort(key=lambda x: -x["es_contrib"])
        return entries[:top_n]
    except Exception as exc:
        logger.debug("component es failed: %s", exc)
        return []


def _sector_breakdown(pos_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, float] = {}
    total = sum(float(p.get("weight", 0)) for p in pos_records) or 1.0
    for p in pos_records:
        sec = p.get("sector") or "Unknown"
        buckets[sec] = buckets.get(sec, 0.0) + float(p.get("weight", 0))
    rows = [{"sector": k, "weight_pct": round(v / total * 100, 1)}
            for k, v in buckets.items()]
    rows.sort(key=lambda r: -r["weight_pct"])
    return rows


def _run_defense_layers(pos_records: list[dict[str, Any]],
                        matrix: Optional[np.ndarray],
                        port_value: float,
                        port_rets: list[float],
                        vix: Optional[float]) -> dict[str, Any]:
    """Call risk_defense.check_all (read-only) and turn its output into a
    per-layer PASS/FAIL table.
    """
    default = {
        "defense_score": None, "status": None, "layers_triggered": [],
        "warnings": [],
    }
    try:
        from risk_defense import RiskDefenseSystem
    except Exception as exc:
        logger.debug("risk_defense import failed: %s", exc)
        return default

    try:
        sys = RiskDefenseSystem()
        state = {
            "positions":      pos_records,
            "portfolio_value": float(port_value or 0),
            "daily_return":   (port_rets[-1] * 100) if port_rets else 0.0,
            "vix":            vix,
            "regime":         "TRANSITION",
            "returns_matrix": matrix,
        }
        res = sys.check_all(state)
        return res
    except Exception as exc:
        logger.warning("risk_defense.check_all failed: %s", exc)
        return default


_LAYER_LABELS = [
    ("L1_VAR",                "Layer 1 · VaR"),
    ("L2_CORRELATION",        "Layer 2 · Correlation"),
    ("L3_VIX_CAUTION",        "Layer 3 · VIX"),
    ("L4_TAIL_RISK",          "Layer 4 · Tail Risk"),
    ("L5_DAILY_LOSS",         "Layer 5 · Daily Loss"),
    ("L6_SECTOR_CONCENTRATION", "Layer 6 · Sector Concentration"),
    ("L7_REGIME",             "Layer 7 · Cash Management"),
]


def _layer_table(defense_result: dict[str, Any]) -> list[dict[str, Any]]:
    triggered = set(defense_result.get("layers_triggered") or [])
    # Merge VIX panic into VIX caution bucket for display purposes
    if "L3_VIX_PANIC" in triggered:
        triggered.add("L3_VIX_CAUTION")
    rows: list[dict[str, Any]] = []
    for code, label in _LAYER_LABELS:
        fired = code in triggered
        rows.append({
            "code":   code,
            "label":  label,
            # "passed" = layer did NOT fire = clean. Fired = attention.
            "passed": not fired,
            "note":   "관찰 지표 감지" if fired else "정상 범위",
        })
    return rows


def _top_risks_narrative(defense_result: dict[str, Any],
                         ces: list[dict[str, Any]],
                         vix: Optional[float],
                         sectors: list[dict[str, Any]]) -> str:
    """One paragraph describing the top-3 risk observations.

    - Pulls seed facts from the 7-layer triggers and component ES.
    - Optional Haiku pass for prose; falls back to a deterministic sentence
      on any failure.
    - Output runs through `legal_filter.safe_scrub` and a banned-word
      replacement pass. Hard cap 600 chars.
    """
    try:
        from services.legal_filter import safe_scrub
    except Exception:
        def safe_scrub(t: str, context: str = "") -> str: return t

    warnings_ = defense_result.get("warnings") or []
    sector_top = sectors[0] if sectors else None
    ces_top = ces[0] if ces else None

    # Deterministic fallback prose (always safe).
    parts: list[str] = []
    if vix is not None:
        parts.append(f"VIX {vix:.1f} 관찰")
    if sector_top:
        parts.append(
            f"{sector_top['sector']} 섹터 비중 {sector_top['weight_pct']:.0f}% "
            f"집중도 체크리스트 항목"
        )
    if ces_top:
        parts.append(
            f"{ces_top['ticker']} 종목의 꼬리 손실 기여도 상위 관찰"
        )
    if warnings_:
        parts.append(str(warnings_[0]))
    fallback = ("이번 리스크 보드 기간 동안 주요 관찰 지표는 " +
                ", ".join(parts) + " 입니다. 본 문서는 정보 제공 목적의 "
                "관찰 체크리스트이며 매매 판단을 포함하지 않습니다."
                if parts else
                "이번 리스크 보드 기간 동안 7-레이어 방어선의 경고 트리거는 "
                "관찰되지 않았습니다. 본 문서는 정보 제공 목적의 관찰 "
                "체크리스트이며 매매 판단을 포함하지 않습니다.")

    # Haiku narrative (optional)
    try:
        import ai_service  # type: ignore
        svc_ = getattr(ai_service, "ai_service", None) or ai_service.AIService()
        if not getattr(svc_, "available", False):
            return safe_scrub(fallback, context="risk_board.fallback") or fallback
        seed_lines = []
        if vix is not None:
            seed_lines.append(f"- VIX current: {vix:.1f}")
        if sector_top:
            seed_lines.append(
                f"- Top sector weight: {sector_top['sector']} "
                f"{sector_top['weight_pct']:.1f}%"
            )
        for c in ces[:3]:
            seed_lines.append(
                f"- CES contributor: {c['ticker']} "
                f"{c.get('sector','')} es={c['es_contrib']}"
            )
        for w in warnings_[:3]:
            seed_lines.append(f"- Layer warning: {w}")
        seed = "\n".join(seed_lines) or "- (관찰 지표 없음)"
        prompt = (
            "다음은 한 투자자 포트폴리오의 리스크 관찰 지표다. "
            "이 지표들을 바탕으로 상위 3가지 '관찰 포인트'를 한국어 1 문단 "
            "(3-4문장)으로 중립적으로 서술하라.\n"
            "금지 단어: 추천, 조언, 매수, 매도, 비중 축소, 손절, 익절, "
            "buy, sell, recommend, advice, reduce. 대신 '관찰 지표', "
            "'체크리스트', '모니터링'을 사용하라.\n\n"
            f"{seed}"
        )
        resp = svc_.client.messages.create(
            model=ai_service.MODEL,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            getattr(b, "text", "") for b in (resp.content or [])
            if getattr(b, "type", "") == "text"
        ).strip()
        # Defensive banned-word substitution.
        banned = [
            (r"비중\s*축소", "비중 모니터링"),
            (r"추천", "관찰"),
            (r"조언", "정보 고지"),
            (r"매수", "진입 관찰"),
            (r"매도", "청산 관찰"),
            (r"손절", "SL 레벨 관찰"),
            (r"익절", "TP 레벨 관찰"),
            (r"\breduce\b", "monitor"),
            (r"\brecommend(ation|ed)?\b", "observation"),
            (r"\badvice\b", "information"),
        ]
        for pat, repl in banned:
            text = re.sub(pat, repl, text, flags=re.IGNORECASE)
        if not text:
            return safe_scrub(fallback, context="risk_board.empty") or fallback
        scrubbed = safe_scrub(text, context="risk_board.ai") or text
        return scrubbed[:600]
    except Exception as exc:
        logger.debug("risk board narrative AI failed: %s", exc)
        return safe_scrub(fallback, context="risk_board.err") or fallback


# ── service ──────────────────────────────────────────────────────────────────

class RiskBoardService:
    """Monthly + VIX-spike Risk Board deck (Premium)."""

    # ── data ────────────────────────────────────────────────────────────────

    def generate_for_user(self, user_id: int,
                          trigger: str = "monthly",
                          now: datetime | None = None) -> dict[str, Any]:
        user = db.session.get(User, user_id)
        if not user:
            raise ValueError(f"user {user_id} not found")

        now = now or datetime.now(timezone.utc).replace(tzinfo=None)
        positions = Position.query.filter_by(user_id=user_id).all()

        # Portfolio snapshot
        total_mv = 0.0
        ccy = "USD"
        if positions and all(p.ticker.endswith((".KS", ".KQ")) for p in positions):
            ccy = "KRW"
        for p in positions:
            px = _safe_price(p.ticker) or float(p.avg_cost or 0)
            total_mv += px * float(p.shares or 0)

        tickers, pos_records, matrix = _fetch_position_returns(positions)
        port_rets = _portfolio_daily_returns(pos_records, matrix)

        var95 = _var_pct(port_rets, 5)
        var99 = _var_pct(port_rets, 1)
        sharpe = _sharpe(port_rets)
        sortino = _sortino(port_rets)
        mdd = _max_dd(port_rets)
        calmar = _calmar(port_rets, mdd)
        tail_r = _tail_ratio(port_rets)
        ces = _component_es(pos_records, matrix)
        sectors = _sector_breakdown(pos_records)

        vix = get_current_vix()
        defense = _run_defense_layers(pos_records, matrix, total_mv,
                                      port_rets, vix)
        layer_status = _layer_table(defense)
        narrative = _top_risks_narrative(defense, ces, vix, sectors)

        if trigger == "vix_spike":
            period_label = f"VIX Spike · {now.date().isoformat()}"
        else:
            period_label = now.strftime("%B %Y")

        # Wave 6 — colophon data lineage.
        try:
            from services.artifacts.data_source_resolver import (
                resolve_user_data_lineage,
            )
            data_sources = resolve_user_data_lineage(user_id)
        except Exception as exc:
            logger.debug("risk_board lineage resolve failed for user %s: %s",
                         user_id, exc)
            data_sources = []

        ctx = RiskBoardContext(
            user_id=user_id,
            user_name=user.name or user.email.split("@")[0],
            period_label=period_label,
            trigger=trigger,
            generated_at=now,
            portfolio_value=round(total_mv, 2) if total_mv > 0 else None,
            portfolio_ccy=ccy,
            position_count=len(positions),
            var95_pct=var95,
            var99_pct=var99,
            sharpe_annual=sharpe,
            sortino_annual=sortino,
            calmar=calmar,
            max_drawdown_pct=mdd,
            sector_breakdown=sectors,
            tail_ratio=tail_r,
            component_es=ces,
            vix_current=round(vix, 2) if vix is not None else None,
            defense_score=defense.get("defense_score"),
            defense_status=defense.get("status"),
            layer_status=layer_status,
            top_risks=narrative,
            disclaimer="정보 제공 목적이며 투자 권유가 아닙니다. 투자 판단은 본인 책임입니다.",
            data_sources=data_sources,
        )
        return ctx.to_dict()

    # ── render ──────────────────────────────────────────────────────────────

    def render_html(self, data: dict[str, Any]) -> str:
        """Render the email/HTML body (also used as the PDF source).

        Note: PDF rendering goes through `render_pdf_html` which injects the
        v3 shape; `render_html` is kept for email/legacy callers and now
        also injects v3 so the same template fills correctly. If a caller
        needs the bare data without v3 augmentation, they can pass an
        already-shaped dict.
        """
        env = self._jinja_env()
        if env is None:
            return self._fallback_html(data)
        try:
            tpl = env.get_template("risk_board.html")
            ctx = dict(data)
            if "v3" not in ctx:
                from services.artifacts._name_enrich import enrich_v3_names
                ctx["v3"] = enrich_v3_names(self._to_v3_shape(data))
            if "persona" not in ctx:
                ctx["persona"] = self._resolve_persona(data)
            return tpl.render(**ctx)
        except Exception as exc:
            logger.warning("risk_board render failed: %s", exc)
            return self._fallback_html(data)

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
            logger.debug("risk_board persona resolution failed: %s", exc)
            return "balanced"

    def render_pdf_html(self, data: dict[str, Any]) -> str:
        """Render the 2-page Pro Risk Board PDF HTML (CEO design v3)."""
        env = self._jinja_env()
        if env is None:
            return self._fallback_html(data)
        try:
            tpl = env.get_template("risk_board.html")
            ctx = dict(data)
            ctx["v3"] = self._to_v3_shape(data)
            ctx["persona"] = self._resolve_persona(data)
            return tpl.render(**ctx)
        except Exception as exc:
            logger.warning("risk_board pdf template render failed: %s", exc)
            return self._fallback_html(data)

    def render_pdf(self, data: dict[str, Any]) -> Optional[bytes]:
        HTML = _try_import_weasyprint()
        if HTML is None:
            return None
        html_str = self.render_pdf_html(data)
        try:
            return HTML(string=html_str).write_pdf()
        except Exception as exc:  # pragma: no cover
            logger.error("WeasyPrint risk_board failed: %s", exc)
            return None

    # ── v3 shape mapping (CEO design 2026-04-29) ────────────────────────────

    def _to_v3_shape(self, data: dict[str, Any]) -> dict[str, Any]:
        """Map generate_for_user() result → the 2-page Pro Risk Board v3
        data shape consumed by services/artifacts/templates/risk_board.html.

        Source of truth for the design:
          frontend/src/components/reports/templates/risk-board.tsx
          (interface RiskBoardData, 2026-04-29).

        Mapping summary
        ---------------
          as_of           ← period_label
          week_tag        ← "RB-{trigger-token}-{period}"
          status_tone     ← derived from defense_status (GREEN/AMBER/RED)
          status_label    ← derived from defense_status
          status_text     ← Korean prose summary of defense layers fired
          headline_risk   ← top sector concentration prose
          stress_worst    ← VaR99-derived stress-worst prose
          this_week       ← VaR/Sharpe/MDD digest line
          action_p1       ← layer-fired derived observation, neutral verbs
          kpis (4)        ← VaR(95%) / Sharpe / MaxDD / VIX
          limits (5)      ← sector concentration / VIX / tail / sharpe / vol
          scenarios (5)   ← stress impact rows derived from VaR / MDD
          corr            ← pairwise correlation gauge (mean of OFF-diag)
          actions         ← observed rebalance notes — neutral language

        Every output is observation-only — BREACH / OVER / OK labels, not
        매수/매도/보유 directives. No banned vocab from 자본시장법 §6.
        Resilient to missing data: every field falls back to a neutral
        default("—") so the template renders even on empty portfolios.
        """
        # ── 1. as_of / week_tag ─────────────────────────────────────────────
        as_of = data.get("period_label") or "—"
        period_token = re.sub(r"[^A-Za-z0-9]+", "", str(as_of))[:12] or "current"
        trigger_token = "S" if data.get("trigger") == "vix_spike" else "M"
        week_tag = f"RB-{trigger_token}-{period_token}"

        # ── 2. Status (Defense layer summary) ───────────────────────────────
        defense_status = (data.get("defense_status") or "").upper()
        if defense_status == "RED":
            status_tone, status_label = "severe", "RED"
        elif defense_status == "YELLOW":
            status_tone, status_label = "moderate", "AMBER"
        elif defense_status == "GREEN":
            status_tone, status_label = "low", "GREEN"
        else:
            status_tone, status_label = "moderate", "관찰"

        layers = data.get("layer_status") or []
        fired_layers = [L for L in layers if isinstance(L, dict) and not L.get("passed")]
        if fired_layers:
            n_fired = len(fired_layers)
            status_text = (
                f"{n_fired}개 관찰 지표 트리거됨. 다음 리밸런스에서 점검 항목 확인."
            )
        else:
            status_text = "한도 트리거 없음. 모든 관찰 지표 정상 범위."

        # ── 3. Headline Risk / Stress Worst / This Week / Action P1 ─────────
        sectors = data.get("sector_breakdown") or []
        sector_top = sectors[0] if sectors else None
        if sector_top:
            headline_risk = (
                f"<strong>섹터 집중</strong> — {sector_top.get('sector','—')} "
                f"섹터 비중 {sector_top.get('weight_pct','—')}%. "
                f"분산 효과 모니터링 항목."
            )
        else:
            headline_risk = "섹터 분포 데이터가 충분하지 않아 관찰 보류."

        var99 = data.get("var99_pct")
        port_value = data.get("portfolio_value") or 0
        if var99 is not None and port_value:
            est_loss = float(var99) / 100.0 * float(port_value)
            stress_worst = (
                f"<strong>99% 신뢰구간 1일 VaR — 약 ${abs(est_loss):,.0f} "
                f"({-abs(float(var99)):.1f}% NAV).</strong> "
                f"5개 시나리오 관찰."
            )
        else:
            stress_worst = "스트레스 관찰 데이터가 충분하지 않습니다."

        var95 = data.get("var95_pct")
        sharpe = data.get("sharpe_annual")
        mdd = data.get("max_drawdown_pct")
        this_week_parts = []
        if var95 is not None:
            this_week_parts.append(f"VaR(95%) <strong>{-abs(float(var95)):.1f}%</strong>")
        if sharpe is not None:
            this_week_parts.append(f"Sharpe <strong>{float(sharpe):.2f}</strong>")
        if mdd is not None:
            this_week_parts.append(f"MaxDD <strong>{-abs(float(mdd)):.1f}%</strong>")
        this_week = " · ".join(this_week_parts) if this_week_parts else "주간 관찰 지표 산출 보류."

        if fired_layers:
            first_label = fired_layers[0].get("label", "관찰 지표")
            action_p1 = (
                f"다음 리밸런스 시 {first_label} 항목 점검. "
                f"한도 복귀 여부 모니터링."
            )
        else:
            action_p1 = "정기 모니터링 유지. 추가 조치 항목 없음."

        # ── 4. KPIs (4-up) ──────────────────────────────────────────────────
        def _heat_for_var(v):
            if v is None: return ("green", "OK")
            av = abs(float(v))
            if av < 2.0: return ("green", "OK")
            if av < 3.5: return ("amber", "WATCH")
            return ("red", "OVER")

        def _heat_for_sharpe(s):
            if s is None: return ("green", "OK")
            if s >= 1.0: return ("green", "OK")
            if s >= 0.5: return ("amber", "WATCH")
            return ("red", "LOW")

        def _heat_for_mdd(m):
            if m is None: return ("green", "OK")
            am = abs(float(m))
            if am < 10.0: return ("green", "OK")
            if am < 20.0: return ("amber", "WATCH")
            return ("red", "OVER")

        def _heat_for_vix(v):
            if v is None: return ("green", "OK")
            if v < 20.0: return ("green", "OK")
            if v < 25.0: return ("amber", "WATCH")
            return ("red", "SPIKE")

        var_heat = _heat_for_var(var95)
        sharpe_heat = _heat_for_sharpe(sharpe)
        mdd_heat = _heat_for_mdd(mdd)
        vix = data.get("vix_current")
        vix_heat = _heat_for_vix(vix)

        kpis = [
            {
                "label": "VaR · 95% 1d",
                "value": f"{-abs(float(var95)):.1f}%" if var95 is not None else "—",
                "delta": "Historical · 3M",
                "delta_tone": "neg" if var95 is not None else "",
                "heat_tone": var_heat[0],
                "heat_text": var_heat[1],
            },
            {
                "label": "Sharpe · Annual",
                "value": f"{float(sharpe):.2f}" if sharpe is not None else "—",
                "delta": "Risk-adj. return",
                "delta_tone": "pos" if sharpe is not None and sharpe >= 1.0 else "",
                "heat_tone": sharpe_heat[0],
                "heat_text": sharpe_heat[1],
            },
            {
                "label": "Max Drawdown",
                "value": f"{-abs(float(mdd)):.1f}%" if mdd is not None else "—",
                "delta": "Peak-to-trough",
                "delta_tone": "neg" if mdd is not None else "",
                "heat_tone": mdd_heat[0],
                "heat_text": mdd_heat[1],
            },
            {
                "label": "VIX · Current",
                "value": f"{float(vix):.1f}" if vix is not None else "—",
                "delta": "Volatility regime",
                "delta_tone": "warn" if vix is not None and vix >= 25 else "",
                "heat_tone": vix_heat[0],
                "heat_text": vix_heat[1],
            },
        ]

        # ── 5. Risk Limits (gauge bars) ─────────────────────────────────────
        limits: list[dict[str, Any]] = []

        # Sector concentration — soft cap 35%
        if sector_top:
            sec_w = float(sector_top.get("weight_pct") or 0)
            cap = 35.0
            fill_pct = min(100.0, (sec_w / cap) * 70.0) if cap > 0 else 0
            cap_pct = 70.0  # cap-marker position (70% of bar = 100% of cap)
            if sec_w > cap:
                fill_state, status_t, status_x = "breach", "severe", "BREACH"
            elif sec_w > cap * 0.85:
                fill_state, status_t, status_x = "warn", "moderate", "OVER"
            else:
                fill_state, status_t, status_x = "", "low", "OK"
            limits.append({
                "name": "Sector concentration",
                "detail": str(sector_top.get("sector") or "—"),
                "fill_pct": round(fill_pct, 1),
                "cap_pct": cap_pct,
                "value_label": f"{sec_w:.0f}% / {cap:.0f}%",
                "fill_state": fill_state,
                "status_tone": status_t,
                "status_text": status_x,
            })

        # VIX — soft cap 25
        if vix is not None:
            cap = 25.0
            fill_pct = min(100.0, (float(vix) / cap) * 70.0)
            if vix > cap:
                fill_state, status_t, status_x = "breach", "severe", "SPIKE"
            elif vix > cap * 0.85:
                fill_state, status_t, status_x = "warn", "moderate", "OVER"
            else:
                fill_state, status_t, status_x = "", "low", "OK"
            limits.append({
                "name": "Volatility regime",
                "detail": "VIX index",
                "fill_pct": round(fill_pct, 1),
                "cap_pct": 70.0,
                "value_label": f"{float(vix):.1f} / {cap:.0f}",
                "fill_state": fill_state,
                "status_tone": status_t,
                "status_text": status_x,
            })

        # Tail Ratio — neutral around 1.0; below 0.7 = warning
        tail = data.get("tail_ratio")
        if tail is not None:
            t = float(tail)
            cap_show = 1.0
            fill_pct = min(100.0, (t / cap_show) * 70.0) if cap_show > 0 else 0
            if t < 0.7:
                fill_state, status_t, status_x = "warn", "moderate", "OVER"
            elif t < 0.5:
                fill_state, status_t, status_x = "breach", "severe", "BREACH"
            else:
                fill_state, status_t, status_x = "", "low", "OK"
            limits.append({
                "name": "Tail ratio",
                "detail": "Right / |left| 5p",
                "fill_pct": round(fill_pct, 1),
                "cap_pct": 70.0,
                "value_label": f"{t:.2f} / {cap_show:.2f}",
                "fill_state": fill_state,
                "status_tone": status_t,
                "status_text": status_x,
            })

        # MaxDD — soft cap 12%
        if mdd is not None:
            am = abs(float(mdd))
            cap = 12.0
            fill_pct = min(100.0, (am / cap) * 70.0) if cap > 0 else 0
            if am > cap:
                fill_state, status_t, status_x = "breach", "severe", "BREACH"
            elif am > cap * 0.85:
                fill_state, status_t, status_x = "warn", "moderate", "OVER"
            else:
                fill_state, status_t, status_x = "", "low", "OK"
            limits.append({
                "name": "Max drawdown",
                "detail": "limit −12%",
                "fill_pct": round(fill_pct, 1),
                "cap_pct": 70.0,
                "value_label": f"{-am:.1f}% / -{cap:.0f}%",
                "fill_state": fill_state,
                "status_tone": status_t,
                "status_text": status_x,
            })

        # Position count — soft cap 30 names
        n_pos = data.get("position_count") or 0
        if n_pos:
            cap = 30.0
            fill_pct = min(100.0, (float(n_pos) / cap) * 70.0)
            limits.append({
                "name": "Position count",
                "detail": "names held",
                "fill_pct": round(fill_pct, 1),
                "cap_pct": 70.0,
                "value_label": f"{n_pos} / {int(cap)}",
                "fill_state": "",
                "status_tone": "low",
                "status_text": "OK",
            })

        # ── 6. Scenarios (waterfall + table) ────────────────────────────────
        # Use VaR99 as the worst single shock if available; else fall back.
        worst_pct = abs(float(var99)) if var99 is not None else (
            abs(float(var95)) * 1.6 if var95 is not None else 8.0
        )
        # Scaling band so bars are visually progressive (90% / 65% / 40% / 25% / 15%)
        bands = [
            ("Replay shock",        "−40% equity / +200bp credit", 0.90),
            ("Tech crash",          "Tech basket −33% / 12mo",     0.65),
            ("Geopolitical",        "Oil +50% / VIX > 40",          0.45),
            ("USD −10%",            "DXY 104 → 94",                 0.28),
            ("Rates +100bp",        "10Y 4.2 → 5.2",                0.18),
        ]
        scenarios: list[dict[str, Any]] = []
        (
            float(port_value) * (worst_pct / 100.0) if port_value else None
        )
        for label, detail, mult in bands:
            pct_loss = worst_pct * mult
            dollar_loss = (
                float(port_value) * (pct_loss / 100.0) if port_value else None
            )
            nav_after = (
                float(port_value) - dollar_loss if dollar_loss is not None else None
            )
            recovery = (
                f"~{int(round(pct_loss * 1.2))} mo" if pct_loss > 0 else "—"
            )
            if mult >= 0.85:
                v_tone, v_text = "severe", "SEVERE"
            elif mult >= 0.55:
                v_tone, v_text = "high", "HIGH"
            else:
                v_tone, v_text = "moderate", "MODERATE"

            scenarios.append({
                "label": label,
                "detail": detail,
                "left_pct": round(90.0 - mult * 90.0, 1),
                "width_pct": round(mult * 90.0, 1),
                "axis_pct": 90.0,
                "value": (
                    f"-${dollar_loss:,.0f}" if dollar_loss is not None
                    else f"-{pct_loss:.1f}%"
                ),
                "value_tone": "neg",
                "pnl_pct": f"-{pct_loss:.1f}%",
                "nav_after": (
                    f"${nav_after:,.0f}" if nav_after is not None else "—"
                ),
                "recovery": recovery,
                "verdict_tone": v_tone,
                "verdict_text": v_text,
            })

        # ── 7. Correlation gauge ────────────────────────────────────────────
        # The service doesn't expose pairwise correlation in the v2 context,
        # but we can derive a coarse proxy from sector concentration.
        # When >1 sector exists, lower diversity → higher avg correlation.
        if sectors:
            top_w = float(sectors[0].get("weight_pct") or 0) / 100.0
            # Heuristic mapping: 0.30 → 0.30 corr · 0.45 → 0.55 · 0.60 → 0.75
            corr_value = max(0.0, min(0.95, 0.10 + top_w * 1.10))
        else:
            corr_value = None

        if corr_value is None:
            corr = {
                "value": "—",
                "gauge_pct": 0,
                "badge_tone": "low",
                "badge_text": "—",
                "verdict": "분산 관찰을 위해 더 많은 데이터가 필요합니다.",
            }
        else:
            gauge_pct = round(corr_value * 100.0, 1)
            if corr_value >= 0.65:
                btone, btext = "severe", "CONCENTRATED"
            elif corr_value >= 0.45:
                btone, btext = "moderate", "ELEVATED"
            else:
                btone, btext = "low", "DIVERSIFIED"
            corr = {
                "value": f"{corr_value:.2f}",
                "gauge_pct": gauge_pct,
                "badge_tone": btone,
                "badge_text": btext,
                "verdict": (
                    "상위 섹터 비중이 평균 페어와이즈 상관에 영향을 미치는 "
                    "관찰 지표입니다. 분산 효과 모니터링 항목."
                ),
            }

        # ── 8. Rebalance Notes (observed checklist) ─────────────────────────
        actions: list[dict[str, Any]] = []
        # Generate from layers fired + ces (component ES top contributors)
        ces = data.get("component_es") or []
        priority = 1
        for L in fired_layers[:2]:
            actions.append({
                "body": f"<strong>P{priority}</strong> · {L.get('label','관찰')} 항목 모니터링",
                "meta": "다음 리밸런스",
            })
            priority += 1
        for c in ces[:2]:
            if priority > 4:
                break
            actions.append({
                "body": (
                    f"<strong>P{priority}</strong> · {c.get('ticker','—')} "
                    f"꼬리 손실 기여도 관찰"
                ),
                "meta": "월간",
            })
            priority += 1
        if not actions:
            actions.append({
                "body": "<strong>P1</strong> · 정기 한도 점검 항목 모니터링",
                "meta": "주간",
            })

        return {
            "as_of": as_of,
            "as_of_stamp": data.get("generated_at") or as_of,
            "week_tag": week_tag,
            "status_tone": status_tone,
            "status_label": status_label,
            "status_text": status_text,
            "headline_risk": headline_risk,
            "stress_worst": stress_worst,
            "this_week": this_week,
            "action_p1": action_p1,
            "kpis": kpis,
            "limits": limits,
            "scenarios": scenarios,
            "corr": corr,
            "actions": actions,
        }

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
<h1>Risk Board — {escape(data.get('period_label',''))}</h1>
<p>Portfolio: {data.get('portfolio_ccy','USD')} {data.get('portfolio_value') or '—'}</p>
<p>VaR95: {data.get('var95_pct')}% · VaR99: {data.get('var99_pct')}%</p>
<p>Sharpe: {data.get('sharpe_annual')} · Sortino: {data.get('sortino_annual')} · Calmar: {data.get('calmar')}</p>
<p>Max DD: {data.get('max_drawdown_pct')}%</p>
<p>VIX: {data.get('vix_current')} · Defense: {data.get('defense_status')} ({data.get('defense_score')})</p>
<p>{escape(data.get('top_risks',''))}</p>
<p><em>{escape(data.get('disclaimer',''))}</em></p>
</body></html>"""

    # ── send ────────────────────────────────────────────────────────────────

    def send_email(self, user: User, pdf_bytes: Optional[bytes],
                   html_body: str, subject: str) -> bool:
        if getattr(user, "email_opt_out", False):
            return False

        from_email = os.environ.get(
            "WEEKLY_MEMO_FROM_EMAIL", "reports@pivoxquant.com"
        )

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
                        FileName(f"risk_board_{user.id}.pdf"),
                        FileType("application/pdf"),
                        Disposition("attachment"),
                    )
                    mail.attachment = att
                SendGridAPIClient(sg_key).send(mail)
                return True
            except Exception as exc:
                logger.error("SendGrid risk_board send failed for user %s: %s",
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
                                       filename=f"risk_board_{user.id}.pdf")
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
                logger.error("SMTP risk_board send failed for user %s: %s",
                             user.id, exc)
                return False

        return False

    # ── persist + orchestrate ───────────────────────────────────────────────

    def _persist(self, user_id: int, data: dict[str, Any],
                 pdf_bytes: Optional[bytes], sent: bool) -> Artifact:
        title = f"Risk Board — {data['period_label']}"
        pdf_path: Optional[str] = None
        if pdf_bytes:
            try:
                base = _storage_dir() / str(user_id)
                base.mkdir(parents=True, exist_ok=True)
                fname = re.sub(r"[^A-Za-z0-9_-]+", "_", data["period_label"])
                path = base / f"{fname}.pdf"
                path.write_bytes(pdf_bytes)
                pdf_path = str(path)
            except Exception as exc:
                logger.warning("risk_board PDF write failed for user %s: %s",
                               user_id, exc)

        artefact = (
            Artifact.query
            .filter_by(user_id=user_id, type="risk_board", title=title)
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
                type="risk_board",
                title=title,
                data_json=data,
                pdf_path=pdf_path,
                sent_at=datetime.now(timezone.utc).replace(tzinfo=None) if sent else None,
            )
            db.session.add(artefact)
        db.session.commit()
        return artefact

    def run_for_user(self, user: User, *, trigger: str = "monthly",
                     send: bool = True, now: datetime | None = None
                     ) -> Optional[Artifact]:
        positions = Position.query.filter_by(user_id=user.id).count()
        if positions == 0:
            logger.info("skipping risk_board for user %s — empty portfolio", user.id)
            return None

        data = self.generate_for_user(user.id, trigger=trigger, now=now)
        pdf_bytes = self.render_pdf(data)
        html_body = self.render_html(data)

        subject_label = ("VIX Spike" if trigger == "vix_spike"
                         else data.get("period_label", "Monthly"))
        subject = f"PivoxQuant Risk Board — {subject_label}"

        sent = False
        if send:
            try:
                sent = self.send_email(user, pdf_bytes, html_body, subject)
            except Exception as exc:
                logger.error("risk_board send raised for user %s: %s",
                             user.id, exc)
                sent = False
        return self._persist(user.id, data, pdf_bytes, sent)

    def run_monthly(self, now: datetime | None = None) -> dict[str, Any]:
        """Cron — day 15 09:30 KST. Premium only."""
        users = (
            User.query
            .filter(User.subscription_tier.in_(list(_PAID_TIERS)))
            .all()
        )

        successes = failures = skipped = 0
        for user in users:
            try:
                result = self.run_for_user(user, trigger="monthly", now=now)
                if result is None:
                    skipped += 1
                else:
                    successes += 1
            except Exception as exc:
                db.session.rollback()
                failures += 1
                logger.error("risk_board monthly failed for user %s: %s",
                             user.id, exc)

        summary = {
            "trigger":   "monthly",
            "attempted": len(users),
            "success":   successes,
            "failed":    failures,
            "skipped":   skipped,
        }
        logger.info("risk_board monthly run: %s", summary)
        return summary

    # ── VIX spike monitor ───────────────────────────────────────────────────

    def run_vix_spike_check(self, now: datetime | None = None
                            ) -> dict[str, Any]:
        """Hourly job — dispatch a deck to all Premium users when VIX newly
        crosses above 25.

        State is a tiny JSON file: `{"last_vix": float, "last_notified_at": iso}`.
        The trigger fires exactly once per "crossing event" — we require
        the previous observed value to be < threshold AND the current
        value to be >= threshold. Subsequent hourly polls while VIX stays
        elevated are no-ops.
        """
        now = now or datetime.now(timezone.utc).replace(tzinfo=None)
        threshold = float(os.environ.get("RISK_BOARD_VIX_THRESHOLD", "25"))
        vix = get_current_vix()
        state_path = _vix_state_path()
        prev: dict[str, Any] = {}
        try:
            if state_path.exists():
                prev = json.loads(state_path.read_text() or "{}")
        except Exception as exc:
            logger.debug("vix state read failed: %s", exc)
            prev = {}

        result: dict[str, Any] = {
            "vix":         vix,
            "threshold":   threshold,
            "prev_vix":    prev.get("last_vix"),
            "triggered":   False,
            "notified":    0,
        }
        if vix is None:
            # Don't touch state — a failed fetch shouldn't wipe history.
            return result

        prev_vix = prev.get("last_vix")
        crossed = (
            (prev_vix is None or float(prev_vix) < threshold)
            and vix >= threshold
        )
        # Always persist the latest observation.
        try:
            state_path.write_text(json.dumps({
                "last_vix":         vix,
                "last_observed_at": now.isoformat(),
                "last_notified_at": prev.get("last_notified_at"),
            }))
        except Exception as exc:
            logger.debug("vix state write failed: %s", exc)

        if not crossed:
            return result

        result["triggered"] = True
        users = (
            User.query
            .filter(User.subscription_tier.in_(list(_PAID_TIERS)))
            .all()
        )
        notified = 0
        for user in users:
            try:
                r = self.run_for_user(user, trigger="vix_spike", now=now)
                if r is not None:
                    notified += 1
            except Exception as exc:
                db.session.rollback()
                logger.error("risk_board spike failed for user %s: %s",
                             user.id, exc)
        result["notified"] = notified

        try:
            state_path.write_text(json.dumps({
                "last_vix":         vix,
                "last_observed_at": now.isoformat(),
                "last_notified_at": now.isoformat(),
            }))
        except Exception:
            pass

        logger.info("risk_board vix_spike run: %s", result)
        return result
