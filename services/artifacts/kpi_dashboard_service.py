"""KPI Dashboard Email — daily 08:00 KST 5-metric portfolio snapshot.

Entry points
------------
    KPIDashboardService().generate_for_user(user_id)  → data dict
    KPIDashboardService().render_html(data)           → str
    KPIDashboardService().send_email(user, html)      → bool
    KPIDashboardService().run_daily(target_date=None) → summary dict

Design
------
Shipped as a *short* HTML email (no PDF). The user opens Gmail, sees five
numbers, closes the tab. 80% of the value of a daily report for <5% of
the clutter. Pro + Premium only — Free is silently skipped.

Five KPIs
---------
1. Portfolio Value + YTD %        — sum(shares × cost × fx) with YTD return.
2. Sharpe (annualised)            — mean(daily_ret) / std(daily_ret) * √252,
                                    computed on the equal-weight daily return
                                    series derived from position history.
3. Max Drawdown (3-month)          — worst peak-to-trough of the equal-weight
                                    equity curve over the last ~63 trading days.
4. Turnover Ratio (30d)           — Σ|trade notional| / portfolio value,
                                    using TradeHistory rows < 30 days old.
5. Cash %                          — available_capital / (positions_mv + cash).

Degradation
-----------
Every metric is computed in a try/except and returns None on failure. The
template renders "—" for missing values so the email still ships with
whatever metrics are available. This mirrors the weekly_memo contract.

Compliance
----------
All text is descriptive. `_disclaimer.html` is included so each email
carries the 자본시장법 §6 disclaimer. Numbers only — no opinion, no
"should buy/sell" language.
"""
from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from extensions import db
from models import Artifact, Position, TradeHistory, User

logger = logging.getLogger(__name__)


_TEMPLATE_DIR = Path(__file__).parent / "templates"
_PAID_TIERS = frozenset({"pro", "premium", "elite"})


# ── lazy imports ─────────────────────────────────────────────────────────────

def _try_import_jinja():
    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape
        return Environment, FileSystemLoader, select_autoescape
    except Exception as exc:  # pragma: no cover
        logger.warning("Jinja2 unavailable (%s); template rendering will fail.", exc)
        return None, None, None


def _safe_price(ticker: str) -> Optional[float]:
    """Latest close via the shared fetcher. Never raises."""
    try:
        from services.container import fetcher
        hist = fetcher.get_price_history(ticker, period="5d")
        if hist is None or "Close" not in hist or len(hist["Close"]) == 0:
            return None
        return float(hist["Close"].iloc[-1])
    except Exception as exc:
        logger.debug("price fetch failed for %s: %s", ticker, exc)
        return None


def _safe_history(ticker: str, period: str = "3mo"):
    """Close-series DataFrame for a ticker. None on any failure."""
    try:
        from services.container import fetcher
        return fetcher.get_price_history(ticker, period=period)
    except Exception as exc:
        logger.debug("price history fetch failed for %s: %s", ticker, exc)
        return None


# ── data ─────────────────────────────────────────────────────────────────────

@dataclass
class KPIContext:
    user_id:          int
    user_name:        str
    as_of:            date
    generated_at:     datetime
    # Metric 1
    portfolio_value:  Optional[float]
    portfolio_ccy:    str                 # "USD" / "KRW"
    ytd_return_pct:   Optional[float]
    # Metric 2
    sharpe_annual:    Optional[float]
    # Metric 3
    max_drawdown_pct: Optional[float]     # negative number (e.g. -12.3)
    # Metric 4
    turnover_ratio:   Optional[float]     # 0.35 = 35%
    # Metric 5
    cash_pct:         Optional[float]     # 0.20 = 20%
    # Narrative
    position_count:   int
    disclaimer:       str
    # Wave 6 — colophon provenance. Populated from
    # `resolve_user_data_lineage`. Empty list renders a neutral line in
    # the colophon rather than a hardcoded broker name.
    data_sources:     list[dict[str, str]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id":          self.user_id,
            "user_name":        self.user_name,
            "as_of":            self.as_of.isoformat(),
            "generated_at":     self.generated_at.isoformat() + "Z",
            "portfolio_value":  self.portfolio_value,
            "portfolio_ccy":    self.portfolio_ccy,
            "ytd_return_pct":   self.ytd_return_pct,
            "sharpe_annual":    self.sharpe_annual,
            "max_drawdown_pct": self.max_drawdown_pct,
            "turnover_ratio":   self.turnover_ratio,
            "cash_pct":         self.cash_pct,
            "position_count":   self.position_count,
            "disclaimer":       self.disclaimer,
            "data_sources":     self.data_sources,
        }


# ── metric computation ───────────────────────────────────────────────────────

def _portfolio_value(positions: list[Position]) -> tuple[Optional[float], str]:
    """Market value using latest close × shares. Falls back to cost basis."""
    if not positions:
        return 0.0, "USD"
    total = 0.0
    any_krw = all(p.ticker.endswith((".KS", ".KQ")) for p in positions)
    ccy = "KRW" if any_krw else "USD"
    for p in positions:
        price = _safe_price(p.ticker) or float(p.avg_cost or 0)
        total += price * float(p.shares or 0)
    return (round(total, 2) if total > 0 else None, ccy)


def _ytd_return(positions: list[Position]) -> Optional[float]:
    """Equal-weight mean YTD return across held tickers.

    For each ticker we take `(last_close / first_close_of_year - 1) × 100`
    and average. Returns None if no ticker produces a valid pair.
    """
    if not positions:
        return None
    # Fetch max 1y history so we always cover Jan 1.
    rets: list[float] = []
    for p in positions[:25]:  # cap to protect budget
        hist = _safe_history(p.ticker, period="1y")
        if hist is None or "Close" not in hist:
            continue
        try:
            closes = hist["Close"]
            if len(closes) < 2:
                continue
            first = float(closes.iloc[0])
            last = float(closes.iloc[-1])
            if first <= 0:
                continue
            rets.append((last / first - 1) * 100)
        except Exception:
            continue
    if not rets:
        return None
    return round(sum(rets) / len(rets), 2)


def _equal_weight_daily_returns(positions: list[Position],
                                days: int = 63) -> list[float]:
    """Build an equal-weight daily-return series across held tickers.

    Returns a list of ~`days` daily % returns, missing days dropped. Used
    as the input for Sharpe and max-drawdown calculations so both metrics
    share the same basis.
    """
    if not positions:
        return []
    ticker_rets: list[list[float]] = []
    for p in positions[:25]:
        hist = _safe_history(p.ticker, period="3mo")
        if hist is None or "Close" not in hist:
            continue
        try:
            closes = hist["Close"].tail(days + 1).tolist()
            if len(closes) < 5:
                continue
            rets = []
            for a, b in zip(closes[:-1], closes[1:]):
                a, b = float(a), float(b)
                if a <= 0:
                    continue
                rets.append((b / a) - 1.0)
            if rets:
                ticker_rets.append(rets)
        except Exception:
            continue
    if not ticker_rets:
        return []
    # Align to shortest series, then equal-weight average.
    n = min(len(r) for r in ticker_rets)
    aligned = [r[-n:] for r in ticker_rets]
    port_rets: list[float] = []
    for i in range(n):
        vals = [r[i] for r in aligned]
        port_rets.append(sum(vals) / len(vals))
    return port_rets


def _sharpe_annual(daily_rets: list[float]) -> Optional[float]:
    """Annualised Sharpe assuming Rf=0. None if <10 data points."""
    if len(daily_rets) < 10:
        return None
    mean = sum(daily_rets) / len(daily_rets)
    var = sum((r - mean) ** 2 for r in daily_rets) / max(len(daily_rets) - 1, 1)
    std = math.sqrt(var)
    if std <= 0:
        return None
    return round((mean / std) * math.sqrt(252), 2)


def _max_drawdown_pct(daily_rets: list[float]) -> Optional[float]:
    """Max peak-to-trough drawdown on the compounded equity curve.

    Returns a negative number (e.g. -12.3 = -12.3%). None if <10 points.
    """
    if len(daily_rets) < 10:
        return None
    equity = 1.0
    peak = 1.0
    mdd = 0.0
    for r in daily_rets:
        equity *= (1.0 + r)
        if equity > peak:
            peak = equity
        if peak > 0:
            dd = (equity - peak) / peak
            if dd < mdd:
                mdd = dd
    return round(mdd * 100, 2)


def _turnover_ratio(user_id: int, portfolio_value: Optional[float]
                    ) -> Optional[float]:
    """Σ|trade_notional| over last 30d / portfolio_value.

    Returns None if portfolio_value is missing/zero or there are no trades.
    Can exceed 1.0 (>100% turnover) — consistent with standard definition.
    """
    if not portfolio_value or portfolio_value <= 0:
        return None
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30)
    try:
        rows = (
            TradeHistory.query
            .filter(TradeHistory.user_id == user_id,
                    TradeHistory.traded_at >= cutoff)
            .all()
        )
    except Exception as exc:
        logger.debug("turnover query failed for user %s: %s", user_id, exc)
        return None
    if not rows:
        return 0.0
    total = 0.0
    for r in rows:
        try:
            total += abs(float(r.total_value or 0))
        except Exception:
            continue
    return round(total / portfolio_value, 3)


def _cash_pct(user: User, portfolio_value: Optional[float]) -> Optional[float]:
    """cash / (cash + positions_mv). None if both are zero/unknown."""
    cash_usd = float(getattr(user, "available_capital", 0) or 0)
    cash_krw = float(getattr(user, "available_capital_krw", 0) or 0)
    # Normalize KRW to USD via a rough divisor as a best-effort fallback. We
    # prefer the stored USD number first; when it's zero but KRW is set we
    # treat KRW as already in report ccy.
    cash = cash_usd if cash_usd > 0 else cash_krw
    pv = portfolio_value or 0.0
    total = cash + pv
    if total <= 0:
        return None
    return round(cash / total, 3)


# ── public reusable helper ────────────────────────────────────────────────────
#
# `compute_kpis_for_user` is the canonical entry for any caller that wants the
# 5-metric KPI snapshot without the email/artifact plumbing. Keep this free
# function — services that need the raw metrics should NOT have to
# instantiate KPIDashboardService.

def compute_kpis_for_user(user_id: int,
                          target_date: date | None = None) -> dict[str, Any]:
    """Compute the 5-metric KPI snapshot for a user.

    Returns a dict shaped like `KPIContext.to_dict()` — safe to merge into
    the Morning Brief content payload and pass straight to a Jinja template.
    Every metric is individually best-effort; missing values come back as
    `None` (template renders "—"). Never raises for empty portfolios; the
    numeric fields are `None` / `0.0` and `position_count == 0`.
    """
    user = db.session.get(User, user_id)
    if not user:
        raise ValueError(f"user {user_id} not found")

    as_of = target_date or date.today()
    positions = Position.query.filter_by(user_id=user_id).all()

    pv, ccy = _portfolio_value(positions)
    ytd = _ytd_return(positions) if positions else None
    daily_rets = _equal_weight_daily_returns(positions) if positions else []
    sharpe = _sharpe_annual(daily_rets)
    mdd = _max_drawdown_pct(daily_rets)
    turnover = _turnover_ratio(user_id, pv)
    cash = _cash_pct(user, pv)

    # Wave 6 — colophon data lineage. Only include broker rows for a
    # user who is actually connected (표시광고법 §3 기만표시 방어선).
    try:
        from services.artifacts.data_source_resolver import (
            resolve_user_data_lineage,
        )
        data_sources = resolve_user_data_lineage(user_id)
    except Exception as exc:
        logger.debug("kpi dashboard lineage resolve failed for user %s: %s",
                     user_id, exc)
        data_sources = []

    ctx = KPIContext(
        user_id=user_id,
        user_name=user.name or user.email.split("@")[0],
        as_of=as_of,
        generated_at=datetime.now(timezone.utc).replace(tzinfo=None),
        portfolio_value=pv,
        portfolio_ccy=ccy,
        ytd_return_pct=ytd,
        sharpe_annual=sharpe,
        max_drawdown_pct=mdd,
        turnover_ratio=turnover,
        cash_pct=cash,
        position_count=len(positions),
        disclaimer="정보 제공 목적이며 투자 권유가 아닙니다. 투자 판단은 본인 책임입니다.",
        data_sources=data_sources,
    )
    return ctx.to_dict()


# ── service ──────────────────────────────────────────────────────────────────

class KPIDashboardService:
    """Daily 5-KPI email. Pro + Premium only."""

    # ── data ────────────────────────────────────────────────────────────────

    def generate_for_user(self, user_id: int,
                          target_date: date | None = None) -> dict[str, Any]:
        # Thin wrapper — the canonical implementation is the module-level
        # `compute_kpis_for_user` so both the stand-alone dashboard preview
        # and the Morning Brief Plus integration share one code path.
        return compute_kpis_for_user(user_id, target_date=target_date)

    # ── render ──────────────────────────────────────────────────────────────

    def render_html(self, data: dict[str, Any]) -> str:
        env = self._jinja_env()
        if env is None:
            return self._fallback_html(data)
        try:
            tpl = env.get_template("kpi_dashboard.html")
            return tpl.render(**data)
        except Exception as exc:
            logger.warning("kpi dashboard template render failed: %s", exc)
            return self._fallback_html(data)

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
        pv = data.get("portfolio_value")
        pv_str = f"{data.get('portfolio_ccy','USD')} {pv:,.0f}" if pv else "—"
        ytd = data.get("ytd_return_pct")
        ytd_str = f"{ytd:+.2f}%" if ytd is not None else "—"
        sharpe = data.get("sharpe_annual")
        mdd = data.get("max_drawdown_pct")
        tover = data.get("turnover_ratio")
        cash = data.get("cash_pct")
        return f"""<!doctype html><html><body>
<h1>{escape(data.get('user_name',''))}'s Daily KPIs — {data.get('as_of','')}</h1>
<ul>
<li>Portfolio: {pv_str} (YTD {ytd_str})</li>
<li>Sharpe (annual): {sharpe if sharpe is not None else '—'}</li>
<li>Max Drawdown (3mo): {f'{mdd:.2f}%' if mdd is not None else '—'}</li>
<li>Turnover (30d): {f'{tover*100:.1f}%' if tover is not None else '—'}</li>
<li>Cash: {f'{cash*100:.1f}%' if cash is not None else '—'}</li>
</ul>
<p><em>{escape(data.get('disclaimer',''))}</em></p>
</body></html>"""

    # ── send ────────────────────────────────────────────────────────────────

    def send_email(self, user: User, html_body: str) -> bool:
        """Deliver. SendGrid → SMTP → skip. Same pattern as weekly_memo."""
        if getattr(user, "email_opt_out", False):
            return False

        from_email = os.environ.get(
            "WEEKLY_MEMO_FROM_EMAIL", "reports@pivoxquant.com"
        )
        subject = f"PivoxQuant KPIs — {date.today().isoformat()}"

        sg_key = os.environ.get("SENDGRID_API_KEY")
        if sg_key:
            try:
                from sendgrid import SendGridAPIClient  # type: ignore
                from sendgrid.helpers.mail import Mail  # type: ignore
                mail = Mail(from_email=from_email, to_emails=user.email,
                            subject=subject, html_content=html_body)
                SendGridAPIClient(sg_key).send(mail)
                return True
            except Exception as exc:
                logger.error("SendGrid kpi send failed for user %s: %s", user.id, exc)
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
                logger.error("SMTP kpi send failed for user %s: %s", user.id, exc)
                return False

        logger.info("no email provider — skip kpi send for user %s", user.id)
        return False

    # ── persist + orchestrate ───────────────────────────────────────────────

    def _persist(self, user_id: int, data: dict[str, Any], sent: bool) -> Artifact:
        title = f"KPI Dashboard — {data['as_of']}"
        artefact = (
            Artifact.query
            .filter_by(user_id=user_id, type="kpi_dashboard", title=title)
            .first()
        )
        if artefact:
            artefact.data_json = data
            if sent and not artefact.sent_at:
                artefact.sent_at = datetime.now(timezone.utc).replace(tzinfo=None)
        else:
            artefact = Artifact(
                user_id=user_id,
                type="kpi_dashboard",
                title=title,
                data_json=data,
                sent_at=datetime.now(timezone.utc).replace(tzinfo=None) if sent else None,
            )
            db.session.add(artefact)
        db.session.commit()
        return artefact

    def run_for_user(self, user: User,
                     target_date: date | None = None,
                     *, send: bool = True) -> Optional[Artifact]:
        positions = Position.query.filter_by(user_id=user.id).count()
        if positions == 0:
            logger.info("skipping kpi for user %s — empty portfolio", user.id)
            return None

        data = self.generate_for_user(user.id, target_date=target_date)
        html_body = self.render_html(data)

        sent = False
        if send:
            try:
                sent = self.send_email(user, html_body)
            except Exception as exc:
                logger.error("kpi send_email raised for user %s: %s", user.id, exc)
                sent = False

        return self._persist(user.id, data, sent)

    def run_daily(self, target_date: date | None = None) -> dict[str, Any]:
        """Cron target — 08:00 KST daily. Pro+ only."""
        target_date = target_date or date.today()

        paid_users = (
            User.query
            .filter(User.subscription_tier.in_(list(_PAID_TIERS)))
            .all()
        )

        successes = failures = skipped = 0
        for user in paid_users:
            try:
                result = self.run_for_user(user, target_date=target_date)
                if result is None:
                    skipped += 1
                else:
                    successes += 1
            except Exception as exc:
                db.session.rollback()
                failures += 1
                logger.error("kpi daily failed for user %s: %s", user.id, exc)

        summary = {
            "date":      target_date.isoformat(),
            "attempted": len(paid_users),
            "success":   successes,
            "failed":    failures,
            "skipped":   skipped,
        }
        logger.info("kpi dashboard daily run: %s", summary)
        return summary
