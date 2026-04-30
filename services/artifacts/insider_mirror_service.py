"""Insider Transaction Mirror — weekly 3-page PDF (Premium).

Legal posture (2026-04-19 redesign)
-----------------------------------
This report is a **factual event feed only**. We do not compute
"hit rate", rank insiders, imply any insider is worth following,
or give any buy/sell judgement. The document is three pages:

  P1  Weekly summary — count of filings related to holdings.
  P2  Event feed     — chronological rows (date / ticker / insider /
                       direction / shares / amount / filing link).
  P3  12-week trend  — bar chart of filings/week + disclaimer.

Data sources
------------
- US tickers: ``services.data.sec_edgar_service.SECEdgarService`` —
  existing Form 4 fetcher.
- KR tickers: ``services.data.dart_insider`` — optional (DART_API_KEY).
  When the key is absent we skip the KR section entirely. We never
  raise; downstream callers continue to function with partial data.

Cache TTL is 24 h (matches the filing cadence — SEC Form 4 is T+2,
DART filings are same-day).

Cadence
-------
APScheduler ``day_of_week=mon, hour=9, minute=0`` KST. Empty holdings
are skipped. Per-user failures never block the rest of the run.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from extensions import db
from models import Artifact, Position, User
from services.legal_filter import is_compliant, safe_scrub

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_DEFAULT_STORAGE_DIR = (
    Path(__file__).resolve().parents[2] / "artifacts" / "insider_mirror"
)
_PAID_TIERS = frozenset({"premium", "elite"})
_LOOKBACK_DAYS = 7
_TREND_WEEKS = 12
_MAX_EVENTS_PER_PDF = 40


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


def _storage_dir() -> Path:
    override = os.environ.get("INSIDER_MIRROR_STORAGE_DIR")
    d = Path(override) if override else _DEFAULT_STORAGE_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _region(ticker: str) -> str:
    t = (ticker or "").upper()
    if t.endswith((".KS", ".KQ")):
        return "KR"
    return "US"


def _accession_url(accession: str) -> str:
    """SEC canonical filing URL from a raw accession number."""
    if not accession:
        return ""
    compact = accession.replace("-", "")
    if not compact.isdigit() or len(compact) < 18:
        return ""
    return (
        f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&"
        f"filenum={accession}"
    )


# ── context dataclasses ──────────────────────────────────────────────────────

@dataclass
class EventRow:
    transaction_date: str
    ticker:           str
    company:          str
    insider:          str
    relationship:     str
    direction:        str          # "buy" / "sell" / "other"
    transaction_code: str          # Form 4 code or "" (KR has none)
    shares:           int
    price:            Optional[float]
    value:            Optional[float]
    currency:         str          # "USD" / "KRW"
    region:           str          # "US" / "KR"
    source:           str          # "SEC" / "DART"
    disclosure_url:   str

    def to_dict(self) -> dict[str, Any]:
        return {
            "transaction_date": self.transaction_date,
            "ticker":           self.ticker,
            "company":          self.company,
            "insider":          self.insider,
            "relationship":     self.relationship,
            "direction":        self.direction,
            "transaction_code": self.transaction_code,
            "shares":           self.shares,
            "price":            self.price,
            "value":            self.value,
            "currency":         self.currency,
            "region":           self.region,
            "source":           self.source,
            "disclosure_url":   self.disclosure_url,
        }


@dataclass
class MirrorContext:
    user_id:        int
    user_name:      str
    period_label:   str
    period_start:   date
    period_end:     date
    generated_at:   datetime
    tickers:        list[str]
    us_tickers:     list[str]
    kr_tickers:     list[str]
    events:         list[dict[str, Any]]
    total_events:   int
    dart_configured: bool
    trend_rows:     list[dict[str, Any]]  # 12-week weekly counts
    disclaimer:     str

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id":         self.user_id,
            "user_name":       self.user_name,
            "period_label":    self.period_label,
            "period_start":    self.period_start.isoformat(),
            "period_end":      self.period_end.isoformat(),
            "generated_at":    self.generated_at.isoformat() + "Z",
            "tickers":         self.tickers,
            "us_tickers":      self.us_tickers,
            "kr_tickers":      self.kr_tickers,
            "events":          self.events,
            "total_events":    self.total_events,
            "dart_configured": self.dart_configured,
            "trend_rows":      self.trend_rows,
            "disclaimer":      self.disclaimer,
        }


# ── ingestion helpers ────────────────────────────────────────────────────────

def _fetch_us_events(tickers: list[str], days: int) -> list[EventRow]:
    """SEC Form 4 per ticker → flattened EventRow list."""
    rows: list[EventRow] = []
    if not tickers:
        return rows
    try:
        from services.data.sec_edgar_service import SECEdgarService
    except Exception as exc:
        logger.warning("SEC service import failed: %s", exc)
        return rows

    for t in tickers:
        try:
            trades = SECEdgarService.get_form4_insider_trades(t, days=days) or []
        except Exception as exc:
            logger.debug("SEC form4 fetch failed %s: %s", t, exc)
            continue
        for tr in trades:
            code = (tr.get("transaction_code") or "").upper()
            acquired = bool(tr.get("acquired"))
            if code == "P" or acquired:
                direction = "buy"
            elif code == "S" or (acquired is False and code):
                direction = "sell"
            else:
                direction = "other"
            try:
                shares = int(float(tr.get("shares") or 0))
            except (TypeError, ValueError):
                shares = 0
            try:
                price = float(tr.get("price") or 0.0) or None
            except (TypeError, ValueError):
                price = None
            try:
                value = float(tr.get("value_usd") or 0.0) or None
            except (TypeError, ValueError):
                value = None
            rows.append(EventRow(
                transaction_date=str(tr.get("transaction_date") or tr.get("filing_date") or ""),
                ticker=t.upper(),
                company="",
                insider=str(tr.get("insider") or ""),
                relationship=str(tr.get("relationship") or ""),
                direction=direction,
                transaction_code=code,
                shares=shares,
                price=price,
                value=value,
                currency="USD",
                region="US",
                source="SEC",
                disclosure_url=_accession_url(str(tr.get("accession") or "")),
            ))
    return rows


def _fetch_kr_events(tickers: list[str], days: int) -> tuple[list[EventRow], bool]:
    """DART per-ticker → flattened EventRow list. Returns (rows, configured)."""
    rows: list[EventRow] = []
    if not tickers:
        return rows, False
    try:
        from services.data import dart_insider
    except Exception as exc:
        logger.debug("DART service import failed: %s", exc)
        return rows, False

    configured = dart_insider.is_configured()
    if not configured:
        return rows, False

    for t in tickers:
        corp_code = dart_insider.ticker_to_corp_code(t)
        if not corp_code:
            # Unlisted symbol or CORPCODE.xml download failed — skip
            # silently. Rest of the report still renders with the US
            # section + an empty-KR note on the PDF.
            continue
        try:
            trades = dart_insider.get_insider_trades(corp_code, days=days) or []
        except Exception as exc:
            logger.debug("DART insider fetch failed %s: %s", t, exc)
            continue
        for tr in trades:
            try:
                shares = int(tr.get("shares") or 0)
            except (TypeError, ValueError):
                shares = 0
            rows.append(EventRow(
                transaction_date=str(tr.get("transaction_date") or ""),
                ticker=t.upper(),
                company=str(tr.get("company") or ""),
                insider=str(tr.get("insider") or ""),
                relationship=str(tr.get("relationship") or ""),
                direction=str(tr.get("direction") or "other"),
                transaction_code=str(tr.get("transaction_code") or ""),
                shares=shares,
                price=None,
                value=None,
                currency="KRW",
                region="KR",
                source="DART",
                disclosure_url=str(tr.get("disclosure_url") or ""),
            ))
    return rows, configured


def _week_label(d: date) -> str:
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _trend_bucket(events: list[EventRow], weeks: int) -> list[dict[str, Any]]:
    """Bucket events into the last `weeks` ISO weeks, counting per week.

    Returned rows are sorted oldest → newest and include zero-count weeks
    so the chart renders a continuous 12-bar trend.
    """
    today = datetime.now(timezone.utc).date()
    buckets: dict[str, dict[str, int]] = {}
    for i in range(weeks):
        d = today - timedelta(days=i * 7)
        buckets[_week_label(d)] = {"count": 0, "buys": 0, "sells": 0}
    for ev in events:
        try:
            d = date.fromisoformat(ev.transaction_date)
        except (ValueError, TypeError):
            continue
        label = _week_label(d)
        if label in buckets:
            buckets[label]["count"] += 1
            if ev.direction == "buy":
                buckets[label]["buys"] += 1
            elif ev.direction == "sell":
                buckets[label]["sells"] += 1
    # Sort oldest → newest for the bar chart.
    sorted_labels = sorted(buckets.keys())
    return [dict(week=w, **buckets[w]) for w in sorted_labels]


# ── service ──────────────────────────────────────────────────────────────────

class InsiderMirrorService:
    """Weekly 3-page Insider Event Feed (Premium)."""

    # ---------- main pipeline ----------------------------------------------

    def generate_for_user(self, user_id: int,
                          anchor: date | None = None) -> dict[str, Any]:
        """Insider Form 4 mirror restricted to the user's holdings.

        Legal posture (자본시장법 §101 회피, 2026-04-29):
            **사용자 보유 종목의 SEC Form 4 / DART 공시 알림** 도구다.
            보유하지 않은 종목의 내부자 거래는 표시하지 않는다 — 보유 0 종목
            이면 ``is_empty=True`` 페이로드 반환. 사실 그대로의 공시 미러링
            만 제공하며, "내부자 거래의 의미" 또는 "타사 종목 매매 정보" 는
            제공하지 않는다.
        """
        user = db.session.get(User, user_id)
        if not user:
            raise ValueError(f"user {user_id} not found")

        anchor = anchor or datetime.now(timezone.utc).date()
        start = anchor - timedelta(days=_LOOKBACK_DAYS - 1)

        positions = Position.query.filter_by(user_id=user_id).all()
        tickers = sorted({(p.ticker or "").upper() for p in positions
                           if p.ticker})

        # ── §101 가드: 보유 종목 0 → empty payload ────────────────────────
        if not tickers:
            return {
                "is_empty":     True,
                "empty_reason": "no_positions",
                "user_id":      user_id,
                "period_label": f"{start} → {anchor}",
                "message":      "보유 종목이 없습니다 — Insider Mirror 는 보유 종목 한정 공시 알림 도구입니다",
            }
        us = [t for t in tickers if _region(t) == "US"]
        kr = [t for t in tickers if _region(t) == "KR"]

        us_rows = _fetch_us_events(us, days=_LOOKBACK_DAYS)
        kr_rows, dart_ok = _fetch_kr_events(kr, days=_LOOKBACK_DAYS)

        # For the 12-week trend chart we pull a wider SEC window. DART
        # wider-window is skipped if the key is unset — zeros are fine.
        trend_us = _fetch_us_events(us, days=_TREND_WEEKS * 7) if us else []
        trend_kr = (_fetch_kr_events(kr, days=_TREND_WEEKS * 7)[0]
                    if dart_ok and kr else [])
        trend_rows = _trend_bucket(trend_us + trend_kr, weeks=_TREND_WEEKS)

        # Week-1 event list = newest first, capped for PDF.
        all_week = sorted(
            us_rows + kr_rows,
            key=lambda e: e.transaction_date or "",
            reverse=True,
        )[:_MAX_EVENTS_PER_PDF]

        period_label = (
            f"{start.strftime('%b %-d')} → {anchor.strftime('%b %-d, %Y')}"
            if hasattr(start, "strftime") else f"{start} → {anchor}"
        )

        ctx = MirrorContext(
            user_id=user_id,
            user_name=user.name or user.email.split("@")[0],
            period_label=period_label,
            period_start=start,
            period_end=anchor,
            generated_at=datetime.now(timezone.utc).replace(tzinfo=None),
            tickers=tickers,
            us_tickers=us,
            kr_tickers=kr,
            events=[e.to_dict() for e in all_week],
            total_events=len(us_rows) + len(kr_rows),
            dart_configured=dart_ok,
            trend_rows=trend_rows,
            disclaimer=(
                "본 리포트는 사용자 본인 보유 종목에 한정해 공개된 SEC Form 4 "
                "및 DART 공시 자료를 사실 그대로 나열한 자기 데이터 알림 "
                "도구입니다. 특정 매매를 권유·추천하지 않으며, 보유 종목 외 "
                "타 종목의 내부자 거래 정보는 제공하지 않습니다. PivoxQuant 은 "
                "내부자 거래의 의미나 투자 적합성에 대해 어떠한 판단도 "
                "제공하지 않습니다."
            ),
        )
        return ctx.to_dict()

    # ---------- v3 design shape (CEO redesign 2026-04-30) -------------------

    def _to_v3_shape(self, data: dict[str, Any]) -> dict[str, Any]:
        """Map generate_for_user(...) onto v3 2-page Pro shape.

        Mirrors frontend/src/components/reports/templates/insider-mirror.tsx.
        Missing fields fall back to em-dash. No directive vocabulary.
        """
        events = data.get("events") or []

        def _is_buy(e):
            t = (e.get("transaction_type") or e.get("type") or "").lower()
            return "buy" in t or "purchase" in t or "p" == t.strip()

        def _amt(e) -> float:
            try:
                return float(e.get("usd_value") or e.get("amount_usd") or e.get("value") or 0)
            except (TypeError, ValueError):
                return 0.0

        def _money(v: float, *, signed: bool = True) -> str:
            sign = ("+" if v >= 0 else "−")
            an = abs(v)
            if an >= 1_000_000:
                return f"{sign if signed else ''}${an/1_000_000:.1f}M"
            if an >= 1_000:
                return f"{sign if signed else ''}${an/1_000:.0f}k"
            return f"{sign if signed else ''}${an:,.0f}"

        buy_events = sorted([e for e in events if _is_buy(e)], key=_amt, reverse=True)
        sell_events = sorted([e for e in events if not _is_buy(e)], key=_amt, reverse=True)

        buys: list[dict[str, Any]] = []
        for e in buy_events[:5]:
            amt = _amt(e)
            buys.append({
                "ticker":      e.get("ticker") or "—",
                "insider":     e.get("insider_name") or e.get("name") or "—",
                "role":        e.get("title") or e.get("role") or "—",
                "amount":      _money(amt),
                "date":        (e.get("date") or e.get("filing_date") or "—")[-5:] if e.get("date") else "—",
                "signal":      e.get("signal_label") or "—",
                "signal_tone": e.get("signal_tone") or "neutral",
            })

        sells: list[dict[str, Any]] = []
        for e in sell_events[:5]:
            amt = -_amt(e)
            is_10b5 = bool(e.get("is_10b5_1") or "10b5" in (e.get("plan") or "").lower())
            sells.append({
                "ticker":   e.get("ticker") or "—",
                "insider":  e.get("insider_name") or e.get("name") or "—",
                "role":     e.get("title") or e.get("role") or "—",
                "amount":   _money(amt),
                "plan":     "10b5-1" if is_10b5 else "discretionary",
                "flag":     "routine" if is_10b5 else "⚠ NON-10b5-1",
                "flag_tone": "neutral" if is_10b5 else "neg",
            })

        cluster_count = sum(1 for e in events if "cluster" in (e.get("signal_label") or "").lower())
        ceo_cfo_pair = sum(1 for e in events if "CEO" in (e.get("title") or "") or "CFO" in (e.get("title") or ""))
        non_plan_sells = sum(1 for e in sell_events if not bool(e.get("is_10b5_1")))

        period_label = data.get("period_label") or "—"

        return {
            "as_of_label":    period_label,
            "report_tag":     f"IM-{period_label.replace(' ', '-')[:20]}",
            "cluster_buys":   {"value": str(cluster_count) if cluster_count else "—",
                                "detail": "5+ insiders, 30d"},
            "ceo_cfo_pair":   {"value": str(ceo_cfo_pair) if ceo_cfo_pair else "—",
                                "detail": "강한 신호"},
            "non_plan_sells": {"value": str(non_plan_sells) if non_plan_sells else "—",
                                "detail": "주의 list"},
            "hit_rate":       {"value": "—", "detail": "백테스트 누적 후 표시"},
            "buys":           buys,
            "sells":          sells,
            "featured":       buys[0] if buys else None,
            "has_backtest":   False,  # backtest 데이터 미구축
            "mirror_path":    "",
            "benchmark_path": "",
            "mirror_24m":     {"value": "—", "delta": ""},
            "win_rate":       {"value": "—", "detail": ""},
            "avg_hold":       {"value": "—", "detail": ""},
            "how_to_use":     "시그널은 시그널일 뿐. 90일 후 자동 점검, 가설 깨지면 청산. 미러는 출발점.",
        }

    # ---------- rendering ---------------------------------------------------

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
            logger.debug("insider_mirror persona resolution failed: %s", exc)
            return "balanced"

    def render_pdf_html(self, data: dict[str, Any]) -> str:
        env = self._jinja_env()
        if env is None:
            html = self._fallback_html(data)
        else:
            try:
                ctx = dict(data)
                ctx["v3"] = self._to_v3_shape(data)
                ctx["persona"] = self._resolve_persona(data)
                tpl = env.get_template("insider_mirror.html")
                html = tpl.render(**ctx)
            except Exception as exc:
                logger.warning("insider_mirror v3 render failed: %s", exc)
                html = self._fallback_html(data)
        scrubbed = safe_scrub(html, context="insider_mirror") or html
        if not is_compliant(scrubbed):
            logger.warning("legal_filter fail: insider_mirror")
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
            logger.error("WeasyPrint insider_mirror failed: %s", exc)
            return None

    def _jinja_env(self):
        Environment, FileSystemLoader, select_autoescape = _try_import_jinja()
        if Environment is None:
            return None
        try:
            return Environment(
                loader=FileSystemLoader(str(_TEMPLATE_DIR)),
                autoescape=select_autoescape(["html", "xml"]),
                trim_blocks=True, lstrip_blocks=True,
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("Jinja env build failed: %s", exc)
            return None

    def _fallback_html(self, data: dict[str, Any]) -> str:
        from html import escape
        return (
            f"<!doctype html><html><body>"
            f"<h1>Insider Transaction Mirror — {escape(data.get('period_label',''))}</h1>"
            f"<p>Events: {data.get('total_events', 0)}</p>"
            f"<p><em>{escape(data.get('disclaimer',''))}</em></p>"
            f"</body></html>"
        )

    # ---------- email ------------------------------------------------------

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
                    Mail, Attachment, FileContent, FileName, FileType,
                    Disposition,
                )
                mail = Mail(from_email=from_email, to_emails=user.email,
                            subject=subject, html_content=html_body)
                if pdf_bytes:
                    enc = base64.b64encode(pdf_bytes).decode()
                    att = Attachment(
                        FileContent(enc),
                        FileName(f"insider_mirror_{user.id}.pdf"),
                        FileType("application/pdf"),
                        Disposition("attachment"),
                    )
                    mail.attachment = att
                SendGridAPIClient(sg_key).send(mail)
                return True
            except Exception as exc:
                logger.error("SendGrid insider_mirror send failed for user %s: %s",
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
                                       filename=f"insider_mirror_{user.id}.pdf")
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
                logger.error("SMTP insider_mirror send failed for user %s: %s",
                             user.id, exc)
                return False

        return False

    # ---------- persist + orchestrate --------------------------------------

    def _persist(self, user_id: int, data: dict[str, Any],
                 pdf_bytes: Optional[bytes], sent: bool) -> Artifact:
        title = f"Insider Mirror — {data['period_label']}"

        pdf_path: Optional[str] = None
        if pdf_bytes:
            try:
                base = _storage_dir() / str(user_id)
                base.mkdir(parents=True, exist_ok=True)
                safe = re.sub(r"[^A-Za-z0-9_-]+", "_", data["period_label"])
                path = base / f"{safe}.pdf"
                path.write_bytes(pdf_bytes)
                pdf_path = str(path)
            except Exception as exc:
                logger.warning("insider_mirror PDF write failed for user %s: %s",
                               user_id, exc)

        artefact = (
            Artifact.query
            .filter_by(user_id=user_id, type="insider_mirror", title=title)
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
                type="insider_mirror",
                title=title,
                data_json=data,
                pdf_path=pdf_path,
                sent_at=datetime.now(timezone.utc).replace(tzinfo=None) if sent else None,
            )
            db.session.add(artefact)
        db.session.commit()
        return artefact

    def run_for_user(self, user: User,
                     anchor: date | None = None,
                     *, send: bool = True) -> Optional[Artifact]:
        n_positions = Position.query.filter_by(user_id=user.id).count()
        if n_positions == 0:
            logger.info("skipping insider_mirror for user %s — empty portfolio",
                        user.id)
            return None

        data = self.generate_for_user(user.id, anchor=anchor)
        pdf_bytes = self.render_pdf(data)
        html_body = self.render_html(data)
        subject = f"PivoxQuant Insider Mirror — {data['period_label']}"

        sent = False
        if send:
            try:
                sent = self.send_email(user, pdf_bytes, html_body, subject)
            except Exception as exc:
                logger.error("insider_mirror send raised for user %s: %s",
                             user.id, exc)
                sent = False
        return self._persist(user.id, data, pdf_bytes, sent)

    def run_weekly(self, anchor: date | None = None) -> dict[str, Any]:
        """Cron target — Mon 09:00 KST. Premium users only."""
        anchor = anchor or datetime.now(timezone.utc).date()
        users = (
            User.query
            .filter(User.subscription_tier.in_(list(_PAID_TIERS)))
            .all()
        )
        successes = failures = skipped = 0
        for user in users:
            try:
                result = self.run_for_user(user, anchor=anchor)
                if result is None:
                    skipped += 1
                else:
                    successes += 1
            except Exception as exc:
                db.session.rollback()
                failures += 1
                logger.error("insider_mirror failed for user %s: %s",
                             user.id, exc)

        summary = {
            "anchor":    anchor.isoformat(),
            "attempted": len(users),
            "success":   successes,
            "failed":    failures,
            "skipped":   skipped,
        }
        logger.info("insider_mirror weekly run: %s", summary)
        return summary
