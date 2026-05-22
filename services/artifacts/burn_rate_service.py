"""Burn Rate Report — monthly 1-page PDF of trading cost + expected tax (Pro+).

Entry points
------------
    BurnRateService().generate_for_user(user_id, target_month=None) → data dict
    BurnRateService().render_html(data)                              → str
    BurnRateService().render_pdf(data)                               → bytes | None
    BurnRateService().run_for_user(user, ...)                        → Artifact
    BurnRateService().run_monthly(target_month=None)                 → summary

Scope
-----
Aggregates the user's own TradeHistory rows traded in the *previous* calendar
month and computes:

    * Commission      — 한국 0.015% per side, US $0 (Alpaca).
    * Transaction tax — 한국 매도 시 0.20% (정규 시장), US $0.
    * Expected CGT    — US 매도 실현이익의 22%. 한국 일반주식 0원 (2026년 양도세
                         유예 기준; 명시적으로 '예상 세금' 문구만 사용).
    * FX spread       — .KS/.KQ → USD 환전 추정 (0.2% 왕복 가정).
    * Slippage est.   — |매매 price − 월 평균 가격| / 평균 × notional.
    * Total burn      — 합계 / 포트폴리오 추정가치 %.

Compliance
----------
*   "세무 상담이 아닙니다" 면책 문구 (`_disclaimer.html` include).
*   모든 세금 수치는 "예상" 표현만. 실제 납부액과 다를 수 있음.
*   AI 호출 없음 — 순수 계산.
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
from services.legal_filter import is_compliant, safe_scrub

logger = logging.getLogger(__name__)


_TEMPLATE_DIR = Path(__file__).parent / "templates"
_DEFAULT_STORAGE_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "burn_rate"
# Shared set so premium_plus / founding_lifetime are never silently dropped.
from ._tiers import PAID_TIERS_PRO_AND_UP as _PAID_TIERS  # noqa: E402

# Rate constants (as of 2026; tweak centrally without touching calculations).
_KR_COMMISSION = 0.00015       # 0.015% per side (브로커 수수료)
_KR_TX_TAX_SELL = 0.0020       # 0.20% (증권거래세 — 매도 시)
_US_COMMISSION = 0.0           # Alpaca free
_US_CGT_RATE = 0.22            # 미국 주식 양도세 — 예상(지방세 포함 단순화)
_FX_SPREAD_RT = 0.002          # 0.2% FX 왕복 스프레드 추정
_SLIPPAGE_APPROX = 0.0005      # 0.05% fallback slippage when no month avg


def _storage_dir() -> Path:
    override = os.environ.get("BURN_RATE_STORAGE_DIR")
    d = Path(override) if override else _DEFAULT_STORAGE_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


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


def _safe_history(ticker: str, period: str = "3mo"):
    try:
        from services.container import fetcher
        return fetcher.get_price_history(ticker, period=period)
    except Exception as exc:
        logger.debug("price history fetch failed for %s: %s", ticker, exc)
        return None


def _prev_month_bounds(today: date) -> tuple[date, date, str]:
    """Return (first_day, last_day, label) for the calendar month preceding
    `today`. When called on the 1st of a month that's the prior month.
    """
    first_of_this = date(today.year, today.month, 1)
    last_of_prev = first_of_this - timedelta(days=1)
    first_of_prev = date(last_of_prev.year, last_of_prev.month, 1)
    label = f"{first_of_prev.year}-{first_of_prev.month:02d}"
    return first_of_prev, last_of_prev, label


def _is_kr(ticker: str) -> bool:
    t = (ticker or "").upper()
    return t.endswith(".KS") or t.endswith(".KQ")


# ── data ─────────────────────────────────────────────────────────────────────

@dataclass
class BurnContext:
    user_id:          int
    user_name:        str
    period_label:     str           # "2026-03"
    period_start:     date
    period_end:       date
    generated_at:     datetime
    # Aggregates (all in USD-equivalent for mixed portfolios; falls back to
    # raw currency when only KR trades exist)
    trades_total:     int
    notional_total:   float
    commission_total: float
    tx_tax_total:     float
    cgt_est_total:    float
    fx_spread_total:  float
    slippage_total:   float
    burn_total:       float
    portfolio_value:  Optional[float]
    burn_pct:         Optional[float]   # burn_total / portfolio_value
    by_market:        list[dict[str, Any]]  # [{market, trades, burn}]
    data_sources:     list[str]
    disclaimer:       str

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id":           self.user_id,
            "user_name":         self.user_name,
            "period_label":      self.period_label,
            "period_start":      self.period_start.isoformat(),
            "period_end":        self.period_end.isoformat(),
            "generated_at":      self.generated_at.isoformat() + "Z",
            "trades_total":      self.trades_total,
            "notional_total":    round(self.notional_total, 2),
            "commission_total":  round(self.commission_total, 2),
            "tx_tax_total":      round(self.tx_tax_total, 2),
            "cgt_est_total":     round(self.cgt_est_total, 2),
            "fx_spread_total":   round(self.fx_spread_total, 2),
            "slippage_total":    round(self.slippage_total, 2),
            "burn_total":        round(self.burn_total, 2),
            "portfolio_value":   round(self.portfolio_value, 2) if self.portfolio_value else None,
            "burn_pct":          round(self.burn_pct, 3) if self.burn_pct is not None else None,
            "by_market":         self.by_market,
            "data_sources":      self.data_sources,
            "disclaimer":        self.disclaimer,
        }


# ── calculation helpers ──────────────────────────────────────────────────────

def _month_avg_price(ticker: str, period_start: date, period_end: date
                     ) -> Optional[float]:
    hist = _safe_history(ticker, period="3mo")
    if hist is None or "Close" not in hist:
        return None
    try:
        closes = hist["Close"]
        if len(closes) == 0:
            return None
        # Best-effort: slice by index if pandas DatetimeIndex available.
        try:
            sliced = closes.loc[str(period_start):str(period_end)]
            if len(sliced) >= 3:
                return float(sum(sliced) / len(sliced))
        except Exception:
            logger.debug("silent-fallback: Best-effort: slice by index if pandas DatetimeIndex availabl | _month_avg_price", exc_info=True)
            pass
        # Fallback — the tail ~21 points (approx one month of trading days).
        tail = closes.tail(21)
        if len(tail) == 0:
            return None
        return float(sum(tail) / len(tail))
    except Exception as exc:
        logger.debug("month avg calc failed for %s: %s", ticker, exc)
        return None


def _per_trade_components(tr: TradeHistory,
                          period_start: date, period_end: date,
                          sell_match_buys: dict[tuple[int, str], list[TradeHistory]]
                          ) -> dict[str, float]:
    """Compute the six burn components for a single trade row. Returns all
    values in whatever currency the trade recorded — we aggregate per market
    upstream, and convert for the summary line if needed.
    """
    action = (tr.action or "").upper()
    notional = float(tr.total_value or 0.0)
    if notional <= 0:
        px = float(tr.price_per_share or 0)
        sh = float(tr.shares or 0)
        notional = max(px * sh, 0.0)

    is_kr = _is_kr(tr.ticker)
    commission = notional * (_KR_COMMISSION if is_kr else _US_COMMISSION)

    tx_tax = 0.0
    if is_kr and action == "SELL":
        tx_tax = notional * _KR_TX_TAX_SELL

    # Expected CGT — US realized gain only. For Korean regular stocks we
    # flag 0 (2026 유예) and surface the assumption in the template.
    cgt = 0.0
    if (not is_kr) and action == "SELL":
        # Realized gain = SELL notional - matched BUY cost basis (FIFO).
        key = (tr.user_id, tr.ticker)
        remaining_shares = float(tr.shares or 0)
        cost_basis = 0.0
        for buy in sell_match_buys.get(key, []):
            if remaining_shares <= 0:
                break
            avail = float(getattr(buy, "_remaining", 0) or 0)
            if avail <= 0:
                continue
            take = min(avail, remaining_shares)
            cost_basis += take * float(buy.price_per_share or 0)
            buy._remaining = avail - take   # type: ignore[attr-defined]
            remaining_shares -= take
        realized = notional - cost_basis
        if realized > 0:
            cgt = realized * _US_CGT_RATE

    # FX spread — every KR trade implicitly consumed a USD→KRW conversion at
    # some point in its lifecycle; charge half the roundtrip so a buy+sell
    # pair amortises to the full _FX_SPREAD_RT rate once.
    fx = 0.0
    if is_kr:
        fx = notional * (_FX_SPREAD_RT / 2.0)

    # Slippage estimate — |trade_px − month_avg_px| / month_avg × notional
    slippage = notional * _SLIPPAGE_APPROX  # conservative fallback
    try:
        avg = _month_avg_price(tr.ticker, period_start, period_end)
        px = float(tr.price_per_share or 0)
        if avg and avg > 0 and px > 0:
            diff = abs(px - avg) / avg
            slippage = notional * diff
    except Exception:
        logger.debug("silent-fallback: _per_trade_components", exc_info=True)
        pass

    return {
        "notional":   notional,
        "commission": commission,
        "tx_tax":     tx_tax,
        "cgt":        cgt,
        "fx":         fx,
        "slippage":   slippage,
    }


def _portfolio_value_estimate(user_id: int) -> Optional[float]:
    """Best-effort portfolio value — sum(shares × avg_cost). Uses cost basis
    because this report is about *cumulative* burn; using live marks would
    noise the denominator."""
    try:
        positions = Position.query.filter_by(user_id=user_id).all()
    except Exception:
        logger.debug("silent-fallback: _portfolio_value_estimate", exc_info=True)
        return None
    if not positions:
        return None
    total = 0.0
    for p in positions:
        try:
            total += float(p.shares or 0) * float(p.avg_cost or 0)
        except Exception:
            logger.debug("silent-fallback: _portfolio_value_estimate", exc_info=True)
            continue
    return total if total > 0 else None


# ── service ──────────────────────────────────────────────────────────────────

class BurnRateService:
    """Monthly burn-rate PDF. Pro+ only."""

    def generate_for_user(self, user_id: int,
                          target_month: date | None = None) -> dict[str, Any]:
        user = db.session.get(User, user_id)
        if not user:
            raise ValueError(f"user {user_id} not found")

        today = target_month or date.today()
        period_start, period_end, label = _prev_month_bounds(today)

        ps_dt = datetime.combine(period_start, datetime.min.time())
        pe_dt = datetime.combine(period_end, datetime.max.time())

        try:
            trades = (
                TradeHistory.query
                .filter(TradeHistory.user_id == user_id,
                        TradeHistory.traded_at >= ps_dt,
                        TradeHistory.traded_at <= pe_dt)
                .order_by(TradeHistory.traded_at.asc())
                .all()
            )
        except Exception as exc:
            logger.error("burn_rate trade query failed for user %s: %s", user_id, exc)
            trades = []

        # FIFO lots for CGT matching — only US (non-KR) BUYs count because
        # Korean general-stock capital gains are exempt in 2026.
        sell_match_buys: dict[tuple[int, str], list[TradeHistory]] = {}
        try:
            all_buys = (
                TradeHistory.query
                .filter(TradeHistory.user_id == user_id,
                        TradeHistory.action == "BUY")
                .order_by(TradeHistory.traded_at.asc())
                .all()
            )
            for b in all_buys:
                if _is_kr(b.ticker):
                    continue
                b._remaining = float(b.shares or 0)  # type: ignore[attr-defined]
                sell_match_buys.setdefault((b.user_id, b.ticker), []).append(b)
        except Exception as exc:
            logger.debug("burn_rate buy-index failed for user %s: %s", user_id, exc)

        # Aggregate
        totals = {"notional": 0.0, "commission": 0.0, "tx_tax": 0.0,
                  "cgt": 0.0, "fx": 0.0, "slippage": 0.0}
        by_market_acc: dict[str, dict[str, float]] = {}
        for tr in trades:
            comp = _per_trade_components(tr, period_start, period_end,
                                         sell_match_buys)
            for k in totals:
                totals[k] += comp[k]

            market = "한국" if _is_kr(tr.ticker) else "미국"
            row = by_market_acc.setdefault(
                market, {"trades": 0, "burn": 0.0, "notional": 0.0}
            )
            row["trades"] += 1
            row["notional"] += comp["notional"]
            row["burn"] += (comp["commission"] + comp["tx_tax"] +
                            comp["cgt"] + comp["fx"] + comp["slippage"])

        burn_total = (totals["commission"] + totals["tx_tax"] + totals["cgt"]
                      + totals["fx"] + totals["slippage"])
        pv = _portfolio_value_estimate(user_id)
        burn_pct: Optional[float] = None
        if pv and pv > 0:
            burn_pct = round((burn_total / pv) * 100, 3)

        by_market = [
            {
                "market":   m,
                "trades":   int(row["trades"]),
                "notional": round(row["notional"], 2),
                "burn":     round(row["burn"], 2),
            }
            for m, row in sorted(by_market_acc.items())
        ]

        # Data-source provenance — Wave 5. Burn-rate is computed from the
        # user's own TradeHistory rows (which originate from either a
        # broker sync OR the user's manual entry). We claim system
        # sources for the tax-rate constants + the ledger flag, and only
        # name brokers that are actually connected.
        try:
            from services.artifacts.data_source_resolver import (
                resolve_user_data_sources,
            )
            data_sources = resolve_user_data_sources(
                user_id, include_manual_ledger=True,
            )
        except Exception as exc:
            logger.debug("data_source resolve failed for user %s: %s",
                         user_id, exc)
            data_sources = []

        ctx = BurnContext(
            user_id=user_id,
            user_name=user.name or user.email.split("@")[0],
            period_label=label,
            period_start=period_start,
            period_end=period_end,
            generated_at=datetime.now(timezone.utc).replace(tzinfo=None),
            trades_total=len(trades),
            notional_total=totals["notional"],
            commission_total=totals["commission"],
            tx_tax_total=totals["tx_tax"],
            cgt_est_total=totals["cgt"],
            fx_spread_total=totals["fx"],
            slippage_total=totals["slippage"],
            burn_total=burn_total,
            portfolio_value=pv,
            burn_pct=burn_pct,
            by_market=by_market,
            data_sources=data_sources,
            disclaimer=("본 리포트는 세무 상담이 아니며 예상 세금·비용을 정보 "
                        "제공 목적으로 추정한 것입니다. 실제 납부액은 중개사/"
                        "과세당국 산정과 다를 수 있습니다."),
        )
        return ctx.to_dict()

    # ── v3 design shape (CEO redesign 2026-04-30) ──────────────────────────

    def _to_v3_shape(self, data: dict[str, Any]) -> dict[str, Any]:
        """Map BurnContext (trading cost burn) onto v3 1-page Pro shape.

        Backend semantics: user trading cost burn (commission / tx_tax /
        cgt / fx_spread / slippage). Frontend tsx covers growth-co cash
        runway — different concept; v3 layout adapted to backend.
        """
        burn_total = data.get("burn_total") or 0
        commission = data.get("commission_total") or 0
        tx_tax = data.get("tx_tax_total") or 0
        cgt = data.get("cgt_est_total") or 0
        fx = data.get("fx_spread_total") or 0
        slippage = data.get("slippage_total") or 0
        notional = data.get("notional_total") or 0
        trades = data.get("trades_total") or 0
        burn_pct = data.get("burn_pct")
        period_label = data.get("period_label") or "—"

        def _money(v, *, signed: bool = False) -> str:
            try:
                n = float(v)
            except (TypeError, ValueError):
                return "—"
            sign = ("−" if n > 0 and signed else "")
            an = abs(n)
            if an >= 1_000_000:
                return f"{sign}${an/1_000_000:.2f}M"
            if an >= 1_000:
                return f"{sign}${an/1_000:.1f}k"
            return f"{sign}${an:,.2f}"

        def _pct_of(part: float, total: float) -> str:
            if not total:
                return "—"
            return f"{(part/total)*100:.1f}%"

        cost_rows = []
        for label, amount, note in [
            ("Commission", commission, "거래 수수료"),
            ("Tax (Tx)", tx_tax, "거래세"),
            ("Tax (CGT est)", cgt, "양도세 추정"),
            ("FX Spread", fx, "환전 스프레드"),
            ("Slippage", slippage, "체결가 차이"),
        ]:
            try:
                amt_f = float(amount or 0)
            except (TypeError, ValueError):
                amt_f = 0
            if amt_f or burn_total:
                cost_rows.append({
                    "category": label,
                    "amount":   _money(amt_f, signed=True),
                    "pct":      _pct_of(amt_f, burn_total),
                    "detail":   note,
                })

        # by_market: service.generate_for_user produces a *list* of
        # {market, trades, burn} rows; sample_data sometimes ships a *dict*
        # ({"us": {...}, "kr": {...}}). Normalise both shapes here so the
        # v3 cron path renders, not just the preview path.
        bm_raw = data.get("by_market") or []
        if isinstance(bm_raw, dict):
            bm_pairs = [(k, v) for k, v in bm_raw.items()]
        elif isinstance(bm_raw, list):
            bm_pairs = [(r.get("market") or "—", r) for r in bm_raw if isinstance(r, dict)]
        else:
            bm_pairs = []

        by_market = []
        if bm_pairs:
            try:
                tot = sum(float((v or {}).get("burn") or 0) for _, v in bm_pairs)
            except Exception:
                tot = 0
            for name, info in bm_pairs:
                try:
                    val = float((info or {}).get("burn") or 0)
                except (TypeError, ValueError):
                    val = 0
                pct = (val / tot * 100) if tot > 0 else 0
                by_market.append({
                    "name":        str(name).upper(),
                    "pct":         round(pct, 1),
                    "pct_display": f"{pct:.1f}%",
                    "flat":        pct < 35,
                })

        avg_cost = (burn_total / trades) if trades > 0 else 0

        return {
            "month_label": period_label,
            "report_tag":  f"BR-{str(period_label).replace(' ', '-')[:20]}",
            "this_month":  {"value": _money(burn_total, signed=True),
                             "detail": "이번 달 누계"},
            "trades":      {"value": str(trades) if trades else "—",
                             "detail": f"notional {_money(notional)}" if notional else ""},
            "burn_pct":    {"value": f"{burn_pct:.2f}%" if burn_pct is not None else "—",
                             "detail": "vs NAV"},
            "avg_cost":    {"value": _money(avg_cost, signed=True) if avg_cost else "—",
                             "detail": "거래당"},
            "cost_rows":   cost_rows,
            "by_market":   by_market,
            "cfo_note":    None,
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
            logger.debug("burn_rate persona resolution failed: %s", exc)
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
                tpl = env.get_template("burn_rate.html")
                html = tpl.render(**ctx)
            except Exception as exc:
                logger.warning("burn_rate v3 render failed: %s", exc)
                html = self._fallback_html(data)
        scrubbed = safe_scrub(html, context="burn_rate") or html
        if not is_compliant(scrubbed):
            logger.warning("legal_filter fail: burn_rate")
        return scrubbed

    def render_html(self, data: dict[str, Any]) -> str:
        return self.render_pdf_html(data)

    def render_pdf(self, data: dict[str, Any]) -> Optional[bytes]:
        HTML = _try_import_weasyprint()
        if HTML is None:
            return None
        html_str = self.render_html(data)
        try:
            return HTML(string=html_str).write_pdf()
        except Exception as exc:  # pragma: no cover
            logger.error("WeasyPrint burn_rate render failed: %s", exc)
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
<h1>Burn Rate — {escape(data.get('period_label',''))} — {escape(data.get('user_name',''))}</h1>
<p>Trades: {data.get('trades_total',0)} · Total burn: {data.get('burn_total',0)}</p>
<p><em>{escape(data.get('disclaimer',''))}</em></p>
</body></html>"""

    # ── send ────────────────────────────────────────────────────────────────

    def send_email(self, user: User, pdf_bytes: Optional[bytes],
                   html_body: str, period_label: str) -> bool:
        """Phase 7 — delegate to :class:`EmailSender`. Subject + filename
        keyed off ``period_label``; opt-out + transport handling lives
        in the consolidated sender.
        """
        from services.email import EmailSender

        return EmailSender().send(
            user,
            subject=f"PivoxQuant Burn Rate — {period_label}",
            html_body=html_body,
            from_env_var="WEEKLY_MEMO_FROM_EMAIL",
            from_default="reports@pivoxquant.com",
            pdf_bytes=pdf_bytes,
            pdf_filename=f"burn_rate_{period_label}.pdf",
        )

    # ── persist + orchestrate ───────────────────────────────────────────────

    def _persist(self, user_id: int, data: dict[str, Any],
                 pdf_bytes: Optional[bytes], sent: bool) -> Artifact:
        title = f"Burn Rate — {data['period_label']}"
        pdf_path: Optional[str] = None
        if pdf_bytes:
            try:
                base = _storage_dir() / str(user_id)
                base.mkdir(parents=True, exist_ok=True)
                fname = data["period_label"].replace(" ", "_")
                path = base / f"{fname}.pdf"
                path.write_bytes(pdf_bytes)
                pdf_path = str(path)
            except Exception as exc:
                logger.warning("burn_rate PDF write failed for user %s: %s",
                               user_id, exc)

        artefact = (
            Artifact.query
            .filter_by(user_id=user_id, type="burn_rate", title=title)
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
                type="burn_rate",
                title=title,
                data_json=data,
                pdf_path=pdf_path,
                sent_at=datetime.now(timezone.utc).replace(tzinfo=None) if sent else None,
            )
            db.session.add(artefact)
        db.session.commit()
        return artefact

    def run_for_user(self, user: User,
                     target_month: date | None = None,
                     *, send: bool = True) -> Optional[Artifact]:
        data = self.generate_for_user(user.id, target_month=target_month)
        if data["trades_total"] == 0:
            logger.info("skipping burn_rate for user %s — no trades in period", user.id)
            return None

        pdf_bytes = self.render_pdf(data)
        html_body = self.render_html(data)

        sent = False
        if send:
            try:
                sent = self.send_email(user, pdf_bytes, html_body,
                                       data["period_label"])
            except Exception as exc:
                logger.error("burn_rate send raised for user %s: %s",
                             user.id, exc)
                sent = False
        return self._persist(user.id, data, pdf_bytes, sent)

    def run_monthly(self, target_month: date | None = None) -> dict[str, Any]:
        """Cron — 1st of each month 09:00 KST. Pro+ only."""
        from services.artifacts import iter_users_chunked

        today = target_month or date.today()

        users = (
            User.query
            .filter(User.subscription_tier.in_(list(_PAID_TIERS)))
            .all()
        )

        successes = failures = skipped = 0
        for user in iter_users_chunked(users, label="burn_rate.monthly"):
            try:
                result = self.run_for_user(user, target_month=today)
                if result is None:
                    skipped += 1
                else:
                    successes += 1
            except Exception as exc:
                db.session.rollback()
                failures += 1
                logger.error("burn_rate failed for user %s: %s", user.id, exc)

        summary = {
            "run_date":   today.isoformat(),
            "attempted":  len(users),
            "success":    successes,
            "failed":     failures,
            "skipped":    skipped,
        }
        logger.info("burn_rate monthly run: %s", summary)
        return summary
