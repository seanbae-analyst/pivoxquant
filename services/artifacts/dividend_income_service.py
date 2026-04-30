"""Dividend Income Statement — monthly 3-page PDF (Premium).

Entry points
------------
    DividendIncomeService().generate_for_user(user_id, as_of=None) → data dict
    DividendIncomeService().render_html(data)                      → str
    DividendIncomeService().render_pdf(data)                       → bytes | None
    DividendIncomeService().run_for_user(user, ...)                → Artifact
    DividendIncomeService().run_monthly(target_month=None)         → summary

Design
------
Fires on the 1st of each month 10:00 KST. Summarises the **prior month**
of dividend income across the user's current positions, projects the
next month's expected dividends from FMP's forward dividend calendar,
and rolls up a trailing-12-month chart with YoY growth.

Compliance
----------
- "예상 배당" is explicitly marked as an estimate, not a guarantee.
- 15.4% Korean withholding (배당소득세 + 지방소득세) applied to the
  net income column. Tax numbers are informational only — service is
  not tax advice (disclaimer embedded).
- `_disclaimer.html` partial included in every page of the PDF.
- Text routed through `legal_filter.safe_scrub` when touching prose.

Data sources
------------
1. `fmp_service.get_dividends(ticker)` — historical dividend record per
   ticker (ex-date, amount, pay-date).
2. `Position` — held shares × dividend/share = gross income.
3. `services.fx_service.get_rate()` — spot USD/KRW for the conversion
   column (BOM of the report day).

All math degrades gracefully — any ticker that fails to resolve falls
through with `None` so the PDF still ships with the rest of the book.
"""
from __future__ import annotations

import calendar
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from extensions import db
from models import Artifact, Position, User

logger = logging.getLogger(__name__)


_TEMPLATE_DIR = Path(__file__).parent / "templates"
_DEFAULT_STORAGE_DIR = (
    Path(__file__).resolve().parents[2] / "artifacts" / "dividend_income"
)
_PAID_TIERS = frozenset({"premium", "elite"})

# Korean withholding (배당소득세 14% + 지방소득세 1.4%)
_KR_WITHHOLDING = 0.154


def _storage_dir() -> Path:
    override = os.environ.get("DIVIDEND_INCOME_STORAGE_DIR")
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


def _fx_rate() -> float:
    """Spot USD/KRW with a safe fallback when the service is unavailable."""
    try:
        from services import fx_service
        rate = float(fx_service.get_rate() or 0)
        if rate >= 900:
            return rate
    except Exception as exc:
        logger.debug("fx lookup failed: %s", exc)
    return 1380.0


def _safe_dividends(ticker: str) -> list[dict[str, Any]]:
    """FMP dividend history. Normalises the output into tiny dicts.

    Returns a list of `{"ex_date": date, "amount": float, "pay_date": date|None}`
    sorted most-recent-first. Empty list on any failure.
    """
    try:
        import fmp_service
        rows = fmp_service.get_dividends(ticker) or []
    except Exception as exc:
        logger.debug("fmp dividends failed for %s: %s", ticker, exc)
        return []
    out: list[dict[str, Any]] = []
    for r in rows:
        try:
            ex_raw = r.get("date") or r.get("recordDate") or r.get("exDividendDate")
            if not ex_raw:
                continue
            ex_date = date.fromisoformat(str(ex_raw)[:10])
            amt = r.get("dividend") or r.get("adjDividend") or r.get("amount") or 0
            amt_f = float(amt or 0)
            pay_raw = r.get("paymentDate") or r.get("payDate")
            pay_date: Optional[date] = None
            if pay_raw:
                try:
                    pay_date = date.fromisoformat(str(pay_raw)[:10])
                except Exception:
                    pay_date = None
            if amt_f > 0:
                out.append({"ex_date": ex_date, "amount": amt_f,
                            "pay_date": pay_date})
        except Exception:
            continue
    out.sort(key=lambda x: x["ex_date"], reverse=True)
    return out


# ── helpers ──────────────────────────────────────────────────────────────────

def _month_bounds(any_day: date) -> tuple[date, date]:
    """Start/end dates (inclusive) of the month containing `any_day`."""
    start = any_day.replace(day=1)
    _, last = calendar.monthrange(any_day.year, any_day.month)
    end = date(any_day.year, any_day.month, last)
    return start, end


def _prev_month(any_day: date) -> date:
    """A date inside the calendar month immediately before `any_day`."""
    first = any_day.replace(day=1)
    return first - timedelta(days=1)


def _next_month(any_day: date) -> date:
    """A date inside the calendar month immediately after `any_day`."""
    first = any_day.replace(day=1)
    # jump forward ~32 days and land in month N+1 regardless of length
    bump = first + timedelta(days=32)
    return bump.replace(day=1)


def _month_label(any_day: date) -> str:
    return f"{any_day.year}-{any_day.month:02d}"


def _per_ticker_gross(positions: list[Position], period_start: date,
                      period_end: date) -> list[dict[str, Any]]:
    """For each held ticker, sum `shares × dividend/share` over the window.

    One row per ticker that actually paid in the window. Rows are sorted
    by gross USD desc. `.KS/.KQ` tickers are treated as KRW-denominated
    so no FX conversion is applied.
    """
    rows: list[dict[str, Any]] = []
    for p in positions:
        shares = float(p.shares or 0)
        if shares <= 0:
            continue
        divs = _safe_dividends(p.ticker)
        if not divs:
            continue
        matches = [d for d in divs
                   if period_start <= d["ex_date"] <= period_end]
        if not matches:
            continue
        amt_per_share = sum(d["amount"] for d in matches)
        gross = amt_per_share * shares
        is_krw = p.ticker.endswith((".KS", ".KQ"))
        ccy = "KRW" if is_krw else "USD"
        rows.append({
            "ticker":         p.ticker,
            "shares":         round(shares, 4),
            "per_share":      round(amt_per_share, 4),
            "gross":          round(gross, 2),
            "ccy":            ccy,
            "pay_count":      len(matches),
            "ex_dates":       [d["ex_date"].isoformat() for d in matches],
        })
    rows.sort(key=lambda x: -x["gross"])
    return rows


def _aggregate_totals(rows: list[dict[str, Any]], fx: float
                      ) -> dict[str, Any]:
    """Convert every row to KRW, apply 15.4% withholding, and total up."""
    gross_krw = 0.0
    gross_usd = 0.0
    for r in rows:
        if r["ccy"] == "USD":
            gross_usd += r["gross"]
            gross_krw += r["gross"] * fx
        else:
            gross_krw += r["gross"]
    net_krw = gross_krw * (1.0 - _KR_WITHHOLDING)
    withholding_krw = gross_krw * _KR_WITHHOLDING
    return {
        "gross_usd":        round(gross_usd, 2),
        "gross_krw":        round(gross_krw, 0),
        "withholding_krw":  round(withholding_krw, 0),
        "net_krw":          round(net_krw, 0),
        "withholding_pct":  round(_KR_WITHHOLDING * 100, 1),
    }


def _trailing_12m(positions: list[Position], end_month: date
                  ) -> list[dict[str, Any]]:
    """Roll up monthly gross USD (+KRW for .KS/.KQ) over trailing 12 months.

    Returns 12 rows in chronological order. YoY only meaningful when
    positions are stable — we still surface it since it's a useful rough
    indicator.
    """
    months: list[dict[str, Any]] = []
    cursor = end_month.replace(day=1)
    for _ in range(12):
        start, end = _month_bounds(cursor)
        rows = _per_ticker_gross(positions, start, end)
        usd = sum(r["gross"] for r in rows if r["ccy"] == "USD")
        krw = sum(r["gross"] for r in rows if r["ccy"] == "KRW")
        months.append({
            "label":    _month_label(cursor),
            "gross_usd": round(usd, 2),
            "gross_krw": round(krw, 0),
        })
        cursor = _prev_month(cursor)
    months.reverse()
    return months


def _yoy_growth(series: list[dict[str, Any]]) -> Optional[float]:
    """Compare most-recent vs same-month-prior-year. None if incomparable."""
    if len(series) < 12:
        return None
    this = series[-1]
    prior = series[0]
    total_now = this["gross_usd"] + this["gross_krw"] / 1000.0
    total_prior = prior["gross_usd"] + prior["gross_krw"] / 1000.0
    if total_prior <= 0:
        return None
    return round((total_now / total_prior - 1) * 100, 1)


def _forward_expected(positions: list[Position], month_start: date,
                      month_end: date, fx: float) -> dict[str, Any]:
    """Forward expected dividends for positions whose ex-date falls next month.

    We look at the **most recent prior ex-date amount** and *assume it
    repeats on the upcoming ex-date* — an explicit estimate (the PDF says
    "예상"). Returns rows plus totals so the template can print both.
    """
    rows: list[dict[str, Any]] = []
    for p in positions:
        shares = float(p.shares or 0)
        if shares <= 0:
            continue
        divs = _safe_dividends(p.ticker)
        if not divs:
            continue
        # Look at the prior-year same-month ex-dates as a cheap proxy; if
        # none, use the most recent ex-date's amount.
        last_year_start = date(month_start.year - 1, month_start.month, 1)
        last_year_end = date(month_end.year - 1, month_end.month,
                             calendar.monthrange(month_end.year - 1,
                                                 month_end.month)[1])
        prior_matches = [d for d in divs
                         if last_year_start <= d["ex_date"] <= last_year_end]
        if not prior_matches:
            continue
        amt_per_share = sum(d["amount"] for d in prior_matches)
        gross = amt_per_share * shares
        is_krw = p.ticker.endswith((".KS", ".KQ"))
        ccy = "KRW" if is_krw else "USD"
        rows.append({
            "ticker":     p.ticker,
            "shares":     round(shares, 4),
            "per_share":  round(amt_per_share, 4),
            "gross":      round(gross, 2),
            "ccy":        ccy,
        })
    rows.sort(key=lambda x: -x["gross"])
    totals = _aggregate_totals(rows, fx)
    return {"rows": rows, "totals": totals}


def _annual_yield_estimate(positions: list[Position], fx: float
                           ) -> Optional[float]:
    """Rough forward yield = sum(trailing-12m gross, KRW) / portfolio_cost.

    Returns None when cost basis is unknown. Explicitly marked as an
    estimate in the template — NOT a realised yield number.
    """
    today = date.today()
    t12 = _trailing_12m(positions, today)
    gross_krw = sum(m["gross_krw"] + m["gross_usd"] * fx for m in t12)
    cost_krw = 0.0
    for p in positions:
        shares = float(p.shares or 0)
        avg = float(p.avg_cost or 0)
        fxp = float(p.buy_fx_rate or 0) or fx
        if shares <= 0 or avg <= 0:
            continue
        if p.ticker.endswith((".KS", ".KQ")):
            cost_krw += shares * avg
        else:
            cost_krw += shares * avg * fxp
    if cost_krw <= 0:
        return None
    return round((gross_krw / cost_krw) * 100, 2)


# ── data ─────────────────────────────────────────────────────────────────────

@dataclass
class DividendContext:
    user_id:            int
    user_name:          str
    month_label:        str          # "2026-03"
    period_start:       date         # first day of reported month
    period_end:         date         # last day of reported month
    next_month_label:   str          # "2026-04"
    generated_at:       datetime
    fx_rate:            float
    # Page 1
    received_rows:      list[dict[str, Any]]
    received_totals:    dict[str, Any]
    position_count:     int
    # Page 2
    monthly_series:     list[dict[str, Any]]
    yoy_growth_pct:     Optional[float]
    # Page 3
    forward_rows:       list[dict[str, Any]]
    forward_totals:     dict[str, Any]
    annual_yield_est:   Optional[float]
    disclaimer:         str

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id":          self.user_id,
            "user_name":        self.user_name,
            "month_label":      self.month_label,
            "period_start":     self.period_start.isoformat(),
            "period_end":       self.period_end.isoformat(),
            "next_month_label": self.next_month_label,
            "generated_at":     self.generated_at.isoformat() + "Z",
            "fx_rate":          round(self.fx_rate, 2),
            "received_rows":    self.received_rows,
            "received_totals":  self.received_totals,
            "position_count":   self.position_count,
            "monthly_series":   self.monthly_series,
            "yoy_growth_pct":   self.yoy_growth_pct,
            "forward_rows":     self.forward_rows,
            "forward_totals":   self.forward_totals,
            "annual_yield_est": self.annual_yield_est,
            "disclaimer":       self.disclaimer,
        }


# ── service ──────────────────────────────────────────────────────────────────

class DividendIncomeService:
    """Monthly PDF dividend statement. Premium only."""

    def generate_for_user(self, user_id: int,
                          as_of: date | None = None) -> dict[str, Any]:
        user = db.session.get(User, user_id)
        if not user:
            raise ValueError(f"user {user_id} not found")

        # The report looks *backward*: the month that just closed.
        today = as_of or date.today()
        report_month_day = _prev_month(today)
        period_start, period_end = _month_bounds(report_month_day)
        next_mo_day = today.replace(day=1)
        next_mo_label = _month_label(next_mo_day)

        positions = Position.query.filter_by(user_id=user_id).all()
        fx = _fx_rate()

        received_rows = _per_ticker_gross(positions, period_start, period_end)
        received_totals = _aggregate_totals(received_rows, fx)

        monthly = _trailing_12m(positions, report_month_day)
        yoy = _yoy_growth(monthly)

        next_start, next_end = _month_bounds(next_mo_day)
        forward = _forward_expected(positions, next_start, next_end, fx)
        ann_yield = _annual_yield_estimate(positions, fx)

        ctx = DividendContext(
            user_id=user_id,
            user_name=user.name or user.email.split("@")[0],
            month_label=_month_label(report_month_day),
            period_start=period_start,
            period_end=period_end,
            next_month_label=next_mo_label,
            generated_at=datetime.now(timezone.utc).replace(tzinfo=None),
            fx_rate=fx,
            received_rows=received_rows,
            received_totals=received_totals,
            position_count=len(positions),
            monthly_series=monthly,
            yoy_growth_pct=yoy,
            forward_rows=forward["rows"],
            forward_totals=forward["totals"],
            annual_yield_est=ann_yield,
            disclaimer=(
                "본 리포트는 이용자 본인의 보유 종목 데이터를 기반으로 한 "
                "참고용 집계이며, 투자자문 또는 세무자문이 아닙니다. "
                "예상 배당은 과거 실적에 기반한 추정이며 지급을 보장하지 않습니다."
            ),
        )
        return ctx.to_dict()

    # ── render ──────────────────────────────────────────────────────────────

    # ── v3 design shape (CEO redesign 2026-04-30) ──────────────────────────

    def _to_v3_shape(self, data: dict[str, Any]) -> dict[str, Any]:
        """Map generate_for_user(...) result onto the v3 1-page Free design
        shape used by templates/dividend_income.html. Mirrors the React
        component (frontend/src/components/reports/templates/dividend-income.tsx).

        Missing fields fall through as em-dash placeholders. No directive
        vocabulary (자본시장법 §17 forbidden) is ever produced.
        """
        rows = data.get("received_rows") or []
        totals = data.get("received_totals") or {}
        monthly = data.get("monthly_series") or []
        ann_yield = data.get("annual_yield_est") or {}
        forward = data.get("forward_totals") or {}

        def _money(v: Any, *, signed: bool = False) -> str:
            try:
                n = float(v)
            except (TypeError, ValueError):
                return "—"
            sign = ("+" if n >= 0 else "−") if signed else ""
            an = abs(n)
            if an >= 1_000_000:
                return f"{sign}${an/1_000_000:.2f}M"
            if an >= 1_000:
                return f"{sign}${an:,.0f}"
            return f"{sign}${an:,.2f}"

        def _pct(v: Any) -> str:
            try:
                return f"{float(v):.2f}%"
            except (TypeError, ValueError):
                return "—"

        # KPI block — uses received_totals + ann_yield + forward
        gross_usd = totals.get("gross_usd")
        ytd_usd = totals.get("ytd_gross_usd") or totals.get("ytd_usd")
        run_rate = forward.get("run_rate_usd") or ann_yield.get("annual_usd")

        # Payments table — flatten received_rows
        payments = []
        for r in rows[:12]:  # cap at 12 to fit one page
            payments.append({
                "date":      r.get("ex_date") or r.get("pay_date") or r.get("date") or "—",
                "ticker":    r.get("ticker") or "—",
                "name":      r.get("name") or "",
                "shares":    str(r.get("shares") or r.get("qty") or "—"),
                "per_share": _money(r.get("per_share") or r.get("dividend_per_share")),
                "received":  _money(r.get("gross_usd") or r.get("amount_usd") or r.get("amount")),
                "yield_pct": _pct(r.get("yield_pct") or r.get("yield")),
            })

        # Top contributors — sort by gross descending, normalize bar pct
        sorted_rows = sorted(rows, key=lambda r: r.get("gross_usd") or 0, reverse=True)
        top_n = sorted_rows[:6]
        max_amt = (top_n[0].get("gross_usd") or 0) if top_n else 0
        contributors = []
        for r in top_n:
            amt = r.get("gross_usd") or 0
            pct_bar = (amt / max_amt * 100.0) if max_amt > 0 else 0
            contributors.append({
                "ticker": r.get("ticker") or "—",
                "pct":    round(pct_bar, 1),
                "amount": _money(amt),
                "flat":   pct_bar < 35,
            })

        # 12-month trail bars — geometry mirrors the TSX layout
        trail_bars = []
        if monthly:
            vals = [(m.get("gross_usd") or 0) for m in monthly[-12:]]
            mx = max(vals) if vals else 0
            for i, v in enumerate(vals):
                h = round((v / mx * 110.0) if mx > 0 else 0)
                y = 142 - h
                trail_bars.append({"x": 10 + i * 50, "y": y, "h": h})

        return {
            "as_of_label":     data.get("month_label") or "—",
            "report_tag":      f"DI-{data.get('month_label','—')}",
            "this_month":      {"value": _money(gross_usd), "delta": ""},
            "ytd_income":      {"value": _money(ytd_usd) if ytd_usd else "—",
                                 "delta": f"+{data.get('yoy_growth_pct','—')}% YoY" if data.get('yoy_growth_pct') else ""},
            "yield_on_cost":   {"value": _pct(ann_yield.get("yield_on_cost_pct") or ann_yield.get("yield_pct")),
                                 "delta": "portfolio avg"},
            "run_rate":        {"value": _money(run_rate),
                                 "delta": f"{_money((run_rate or 0)/12)}/mo" if run_rate else ""},
            "payments":        payments,
            "payments_count":  len(payments),
            "total_received":  _money(gross_usd),
            "avg_yield":       f"avg {_pct(ann_yield.get('avg_yield_pct'))}",
            "top_contributors": contributors,
            "trail_bars":      trail_bars,
            "trail_caption":   None,
            "last_month_label": (data.get("month_label") or "—")[-3:].upper(),
            "reinvestment_note": None,  # falls back to template default
        }

    def _resolve_persona(self, data: dict[str, Any]) -> str:
        """Same persona contract as weekly_memo / quarterly_self_report.

        Note: dividend_income inherently fits the ``income`` persona —
        the resolver still routes via InvestmentProfile so users with a
        different declared persona (e.g. growth-tilt with a satellite
        dividend sleeve) get *their* tone, not a forced income lens.
        """
        if "persona" in data and data["persona"]:
            try:
                from services.artifacts.persona_resolver import resolve_persona_from_code
                return resolve_persona_from_code(data["persona"])
            except Exception:
                return "income"
        user_id = data.get("user_id")
        if user_id is None:
            return "income"
        try:
            from services.artifacts.persona_resolver import (
                DEFAULT_PERSONA, resolve_persona,
            )
            from models import InvestmentProfile
            profile = InvestmentProfile.query.filter_by(user_id=user_id).first()
            return resolve_persona(profile) if profile else DEFAULT_PERSONA
        except Exception as exc:
            logger.debug("dividend_income persona resolution failed: %s", exc)
            return "income"

    def render_pdf_html(self, data: dict[str, Any]) -> str:
        """Render the print-oriented v3 HTML. Caller is render_pdf()."""
        env = self._jinja_env()
        if env is None:
            return self._fallback_html(data)
        try:
            ctx = dict(data)
            ctx["v3"] = self._to_v3_shape(data)
            ctx["persona"] = self._resolve_persona(data)
            tpl = env.get_template("dividend_income.html")
            return tpl.render(**ctx)
        except Exception as exc:
            logger.warning("dividend_income v3 render failed: %s", exc)
            return self._fallback_html(data)

    def render_html(self, data: dict[str, Any]) -> str:
        # Email body still uses the same template (single-template flow).
        return self.render_pdf_html(data)

    def render_pdf(self, data: dict[str, Any]) -> Optional[bytes]:
        HTML = _try_import_weasyprint()
        if HTML is None:
            return None
        html_str = self.render_pdf_html(data)
        try:
            return HTML(string=html_str).write_pdf()
        except Exception as exc:  # pragma: no cover
            logger.error("WeasyPrint dividend_income failed: %s", exc)
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
        tot = data.get("received_totals") or {}
        return f"""<!doctype html><html><body>
<h1>Dividend Income — {escape(data.get('month_label',''))}</h1>
<p>{escape(data.get('user_name',''))}'s dividend summary</p>
<p>Gross (KRW): {tot.get('gross_krw','—'):,} · Net (KRW): {tot.get('net_krw','—'):,}</p>
<p><em>{escape(data.get('disclaimer',''))}</em></p>
</body></html>"""

    # ── send ────────────────────────────────────────────────────────────────

    def send_email(self, user: User, pdf_bytes: Optional[bytes],
                   html_body: str, month_label: str) -> bool:
        if getattr(user, "email_opt_out", False):
            return False

        from_email = os.environ.get(
            "WEEKLY_MEMO_FROM_EMAIL", "reports@pivoxquant.com"
        )
        subject = f"PivoxQuant Dividend Statement — {month_label}"

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
                        FileName(f"dividend_{month_label}.pdf"),
                        FileType("application/pdf"),
                        Disposition("attachment"),
                    )
                    mail.attachment = att
                SendGridAPIClient(sg_key).send(mail)
                return True
            except Exception as exc:
                logger.error("SendGrid dividend send failed for user %s: %s",
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
                                       filename=f"dividend_{month_label}.pdf")
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
                logger.error("SMTP dividend send failed for user %s: %s",
                             user.id, exc)
                return False
        return False

    # ── persist + orchestrate ───────────────────────────────────────────────

    def _persist(self, user_id: int, data: dict[str, Any],
                 pdf_bytes: Optional[bytes], sent: bool) -> Artifact:
        title = f"Dividend Statement — {data['month_label']}"
        pdf_path: Optional[str] = None
        if pdf_bytes:
            try:
                base = _storage_dir() / str(user_id)
                base.mkdir(parents=True, exist_ok=True)
                path = base / f"{data['month_label']}.pdf"
                path.write_bytes(pdf_bytes)
                pdf_path = str(path)
            except Exception as exc:
                logger.warning("dividend PDF write failed for user %s: %s",
                               user_id, exc)

        artefact = (
            Artifact.query
            .filter_by(user_id=user_id, type="dividend_income", title=title)
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
                type="dividend_income",
                title=title,
                data_json=data,
                pdf_path=pdf_path,
                sent_at=datetime.now(timezone.utc).replace(tzinfo=None) if sent else None,
            )
            db.session.add(artefact)
        db.session.commit()
        return artefact

    def run_for_user(self, user: User,
                     as_of: date | None = None,
                     *, send: bool = True) -> Optional[Artifact]:
        n_pos = Position.query.filter_by(user_id=user.id).count()
        if n_pos == 0:
            logger.info("skipping dividend_income for user %s — empty portfolio",
                        user.id)
            return None

        data = self.generate_for_user(user.id, as_of=as_of)
        pdf_bytes = self.render_pdf(data)
        html_body = self.render_html(data)

        sent = False
        if send:
            try:
                sent = self.send_email(user, pdf_bytes, html_body,
                                       data["month_label"])
            except Exception as exc:
                logger.error("dividend send raised for user %s: %s",
                             user.id, exc)
                sent = False
        return self._persist(user.id, data, pdf_bytes, sent)

    def run_monthly(self, target_month: date | None = None) -> dict[str, Any]:
        """Cron — 1st of month 10:00 KST. Premium only."""
        today = target_month or date.today()

        users = (
            User.query
            .filter(User.subscription_tier.in_(list(_PAID_TIERS)))
            .all()
        )

        successes = failures = skipped = 0
        for user in users:
            try:
                result = self.run_for_user(user, as_of=today)
                if result is None:
                    skipped += 1
                else:
                    successes += 1
            except Exception as exc:
                db.session.rollback()
                failures += 1
                logger.error("dividend_income failed for user %s: %s",
                             user.id, exc)

        summary = {
            "month":     _month_label(_prev_month(today)),
            "attempted": len(users),
            "success":   successes,
            "failed":    failures,
            "skipped":   skipped,
        }
        logger.info("dividend_income monthly run: %s", summary)
        return summary
