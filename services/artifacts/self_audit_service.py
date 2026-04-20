"""Self Audit Report — quarterly 4-page PDF of decision-quality (Premium).

MVP (2026-04-19)
----------------
Aggregates the user's own TradeHistory over the last quarter and grades
each *closed* position by comparing buy-date price to a 3-month-forward
price (or the sell price, whichever came first). The output is an
*observation* of past decisions — never a recommendation.

Algorithmic only — no AI judgement for the scoring. A *single* Haiku
call (≤3K tokens) produces a one-paragraph pattern summary from the
top/bottom winners and losers, purely descriptive language.

Entry points
------------
    SelfAuditService().generate_for_user(user_id, quarter_end=None) → data dict
    SelfAuditService().render_html(data)                             → str
    SelfAuditService().render_pdf(data)                              → bytes | None
    SelfAuditService().run_for_user(user, ...)                       → Artifact
    SelfAuditService().run_quarterly(quarter_end=None)               → summary

Compliance
----------
- All prose routed through `morning_brief_service.is_compliant` regex.
- AI prompt forbids 매수/매도/추천/조언 words.
- `_disclaimer.html` is included inside the PDF/HTML template.
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
from models import Artifact, Position, TradeHistory, User

logger = logging.getLogger(__name__)


_TEMPLATE_DIR = Path(__file__).parent / "templates"
_DEFAULT_STORAGE_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "self_audit"
_PAID_TIERS = frozenset({"premium", "elite"})


def _storage_dir() -> Path:
    override = os.environ.get("SELF_AUDIT_STORAGE_DIR")
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


def _safe_history(ticker: str, period: str = "6mo"):
    try:
        from services.container import fetcher
        return fetcher.get_price_history(ticker, period=period)
    except Exception as exc:
        logger.debug("history fetch failed for %s: %s", ticker, exc)
        return None


# ── data ─────────────────────────────────────────────────────────────────────

@dataclass
class AuditContext:
    user_id:              int
    user_name:            str
    quarter_label:        str      # "2026 Q1"
    period_start:         date
    period_end:           date
    generated_at:         datetime
    # Aggregates
    trades_total:         int
    wins:                 int
    losses:               int
    win_rate_pct:         Optional[float]
    avg_return_pct:       Optional[float]
    best_decisions:       list[dict[str, Any]]   # top 3
    worst_decisions:      list[dict[str, Any]]   # top 3
    pattern_summary:      str      # AI-generated 1-paragraph observation
    disclaimer:           str

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id":         self.user_id,
            "user_name":       self.user_name,
            "quarter_label":   self.quarter_label,
            "period_start":    self.period_start.isoformat(),
            "period_end":      self.period_end.isoformat(),
            "generated_at":    self.generated_at.isoformat() + "Z",
            "trades_total":    self.trades_total,
            "wins":             self.wins,
            "losses":           self.losses,
            "win_rate_pct":    self.win_rate_pct,
            "avg_return_pct":  self.avg_return_pct,
            "best_decisions":  self.best_decisions,
            "worst_decisions": self.worst_decisions,
            "pattern_summary": self.pattern_summary,
            "disclaimer":      self.disclaimer,
        }


# ── helpers ──────────────────────────────────────────────────────────────────

def _quarter_bounds(quarter_end: date) -> tuple[date, date, str]:
    """Return (period_start, period_end, label) for the quarter that ended
    on-or-just-before `quarter_end`. We treat "quarter_end" as the inclusive
    last day of a review-worthy quarter — this matches the 1/7, 4/7, 7/7,
    10/7 cron firings (7 days into the next quarter = look back at the
    previous quarter).
    """
    # Anchor to the start of the month `quarter_end` sits in, then walk
    # back to the start of that quarter.
    month = quarter_end.month
    q_start_month = 3 * ((month - 1) // 3) + 1  # 1,4,7,10
    # But if `quarter_end` is day 7 of Jan/Apr/Jul/Oct, we look at the *previous*
    # quarter. Detect this: if day <= 7, quarter_end points at the quarter
    # just *after* the one we want to audit.
    if quarter_end.day <= 7 and quarter_end.month in (1, 4, 7, 10):
        # Previous quarter
        prev_end_month = q_start_month - 1
        prev_end_year = quarter_end.year
        if prev_end_month <= 0:
            prev_end_month = 12
            prev_end_year -= 1
        start_month = prev_end_month - 2
        start_year = prev_end_year
        if start_month <= 0:
            start_month += 12
            start_year -= 1
        start = date(start_year, start_month, 1)
        # End = last day of prev_end_month
        if prev_end_month == 12:
            end = date(prev_end_year, 12, 31)
        else:
            end = date(prev_end_year, prev_end_month + 1, 1) - timedelta(days=1)
    else:
        start = date(quarter_end.year, q_start_month, 1)
        end_month = q_start_month + 2
        if end_month >= 12:
            end = date(quarter_end.year, 12, 31)
        else:
            end = date(quarter_end.year, end_month + 1, 1) - timedelta(days=1)

    q_num = (start.month - 1) // 3 + 1
    label = f"{start.year} Q{q_num}"
    return start, end, label


def _buy_outcome_return(tr: TradeHistory, sell_price: Optional[float]
                        ) -> Optional[float]:
    """% return: sell_price / buy_price - 1 (or 3-month forward price if
    no matching sell). Returns None on any failure."""
    buy_price = float(tr.price_per_share or 0)
    if buy_price <= 0:
        return None
    if sell_price and sell_price > 0:
        return round((sell_price / buy_price - 1) * 100, 2)
    # Fallback: 3-month forward price from the fetcher
    hist = _safe_history(tr.ticker, period="6mo")
    if hist is None or "Close" not in hist:
        return None
    try:
        # Find the index closest to `traded_at + 90d`
        target_dt = (tr.traded_at or datetime.now(timezone.utc).replace(tzinfo=None)) + timedelta(days=90)
        closes = hist["Close"]
        if len(closes) < 2:
            return None
        # Best-effort: use the last close as the forward proxy when
        # `target_dt` is in the future.
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if target_dt > now:
            fwd = float(closes.iloc[-1])
        else:
            # pandas DatetimeIndex — fall back to nearest via indexer
            try:
                idx = closes.index.get_indexer([target_dt], method="nearest")[0]
                if idx < 0 or idx >= len(closes):
                    return None
                fwd = float(closes.iloc[idx])
            except Exception:
                fwd = float(closes.iloc[-1])
        if fwd <= 0:
            return None
        return round((fwd / buy_price - 1) * 100, 2)
    except Exception as exc:
        logger.debug("forward price calc failed for %s: %s", tr.ticker, exc)
        return None


def _score_trades(user_id: int, period_start: date, period_end: date
                  ) -> list[dict[str, Any]]:
    """Return a list of scored trade decisions in the audit window.

    One entry per BUY within [period_start, period_end]. Matched to the
    earliest SELL (same ticker, same user) after the buy if any; else
    a 3-month forward price from market data.
    """
    ps_dt = datetime.combine(period_start, datetime.min.time())
    pe_dt = datetime.combine(period_end, datetime.max.time())
    try:
        all_trades = (
            TradeHistory.query
            .filter(TradeHistory.user_id == user_id)
            .order_by(TradeHistory.traded_at.asc())
            .all()
        )
    except Exception as exc:
        logger.debug("trade history query failed for user %s: %s", user_id, exc)
        return []

    buys = [t for t in all_trades
            if (t.action or "").upper() == "BUY"
            and t.traded_at
            and ps_dt <= t.traded_at <= pe_dt]
    # Index sells by ticker → sorted list of (ts, price)
    sells_by_ticker: dict[str, list[tuple[datetime, float]]] = {}
    for t in all_trades:
        if (t.action or "").upper() == "SELL" and t.traded_at:
            sells_by_ticker.setdefault(t.ticker, []).append(
                (t.traded_at, float(t.price_per_share or 0))
            )
    for lst in sells_by_ticker.values():
        lst.sort(key=lambda x: x[0])

    scored: list[dict[str, Any]] = []
    for b in buys:
        # Earliest sell after the buy
        sell_price = None
        for ts, px in sells_by_ticker.get(b.ticker, []):
            if ts >= b.traded_at and px > 0:
                sell_price = px
                break
        ret = _buy_outcome_return(b, sell_price)
        scored.append({
            "ticker":       b.ticker,
            "name":         b.name or b.ticker,
            "buy_date":     b.traded_at.date().isoformat() if b.traded_at else None,
            "buy_price":    round(float(b.price_per_share or 0), 2),
            "shares":       float(b.shares or 0),
            "sell_price":   round(sell_price, 2) if sell_price else None,
            "outcome":      "closed" if sell_price else "open",
            "return_pct":   ret,
        })
    return scored


def _pattern_summary(scored: list[dict[str, Any]],
                     win_rate: Optional[float],
                     avg_ret: Optional[float]) -> str:
    """One-paragraph descriptive summary. Tries Haiku; falls back to a
    deterministic rule-based sentence if AI is unavailable.

    Compliance: the prompt forbids recommendation language; output is
    additionally filtered through `is_compliant` and clipped to 500
    chars to guarantee the email stays short."""
    try:
        from services.morning_brief_service import is_compliant
    except Exception:
        def is_compliant(_: str) -> bool: return True  # pragma: no cover

    # Fallback prose (always safe)
    if not scored:
        return "이번 분기에 기록된 매수 거래가 없어 패턴 분석을 생략합니다."
    top_sectors: dict[str, int] = {}
    for s in scored:
        top_sectors[s["ticker"]] = top_sectors.get(s["ticker"], 0) + 1
    most_traded = max(top_sectors.items(), key=lambda x: x[1])[0] if top_sectors else ""

    wr_str = f"{win_rate:.0f}%" if win_rate is not None else "—"
    ar_str = f"{avg_ret:+.1f}%" if avg_ret is not None else "—"
    fallback = (
        f"분기 내 총 {len(scored)}건의 매수 결정 중 승률 {wr_str}, "
        f"평균 수익률 {ar_str}가 관찰되었습니다. "
        f"가장 자주 거래된 종목은 {most_traded} 였으며, "
        f"반복 매매 패턴이 기록되었습니다."
    )

    # Try Haiku
    try:
        import ai_service  # type: ignore
        svc_ = getattr(ai_service, "ai_service", None) or ai_service.AIService()
        if not getattr(svc_, "available", False):
            return fallback if is_compliant(fallback) else fallback[:500]
        # Compact the scored list for the prompt to stay within 3K tokens.
        sample = scored[:15]
        lines = []
        for s in sample:
            ret = s.get("return_pct")
            ret_str = f"{ret:+.1f}%" if ret is not None else "n/a"
            lines.append(
                f"- {s['ticker']} bought {s['buy_date']} @ {s['buy_price']} "
                f"outcome={s['outcome']} return={ret_str}"
            )
        ctx = "\n".join(lines)
        prompt = (
            "아래는 한 투자자가 최근 한 분기에 실행한 매수 결정과 결과다. "
            "반복 패턴(집중 거래 종목, 승률 분포, 평균 수익/손실)을 중립적으로 "
            "1 문단(3-4문장, 한국어)으로 요약하라.\n"
            "절대 '추천' / '매수' / '매도' / '조언' 같은 단어를 쓰지 말 것.\n"
            "데이터는 사실만 서술하고, 판단이나 조언은 금지.\n\n"
            f"{ctx}"
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
        # Strip any residual forbidden words defensively.
        banned = ["추천", "매수", "매도", "조언", "buy", "sell", "recommend"]
        for w in banned:
            text = re.sub(w, "관찰", text, flags=re.IGNORECASE)
        if not text or not is_compliant(text):
            return fallback
        return text[:500]
    except Exception as exc:
        logger.debug("self-audit pattern AI failed: %s", exc)
        return fallback


# ── service ──────────────────────────────────────────────────────────────────

class SelfAuditService:
    """Quarterly PDF. Premium only."""

    def generate_for_user(self, user_id: int,
                          quarter_end: date | None = None) -> dict[str, Any]:
        user = db.session.get(User, user_id)
        if not user:
            raise ValueError(f"user {user_id} not found")

        quarter_end = quarter_end or date.today()
        start, end, label = _quarter_bounds(quarter_end)
        scored = _score_trades(user_id, start, end)

        # Only trades with a computable return contribute to aggregates.
        rated = [s for s in scored if s["return_pct"] is not None]
        wins = sum(1 for s in rated if s["return_pct"] > 0)
        losses = sum(1 for s in rated if s["return_pct"] <= 0)
        win_rate = round(wins / len(rated) * 100, 1) if rated else None
        avg_ret = round(sum(s["return_pct"] for s in rated) / len(rated), 2) if rated else None

        best = sorted(rated, key=lambda s: -s["return_pct"])[:3]
        worst = sorted(rated, key=lambda s: s["return_pct"])[:3]

        pattern = _pattern_summary(scored, win_rate, avg_ret)

        ctx = AuditContext(
            user_id=user_id,
            user_name=user.name or user.email.split("@")[0],
            quarter_label=label,
            period_start=start,
            period_end=end,
            generated_at=datetime.now(timezone.utc).replace(tzinfo=None),
            trades_total=len(scored),
            wins=wins,
            losses=losses,
            win_rate_pct=win_rate,
            avg_return_pct=avg_ret,
            best_decisions=best,
            worst_decisions=worst,
            pattern_summary=pattern,
            disclaimer="정보 제공 목적이며 투자 권유가 아닙니다. 투자 판단은 본인 책임입니다.",
        )
        return ctx.to_dict()

    # ── render ──────────────────────────────────────────────────────────────

    def render_html(self, data: dict[str, Any]) -> str:
        env = self._jinja_env()
        if env is None:
            return self._fallback_html(data)
        try:
            tpl = env.get_template("self_audit.html")
            return tpl.render(**data)
        except Exception as exc:
            logger.warning("self_audit template render failed: %s", exc)
            return self._fallback_html(data)

    def render_pdf(self, data: dict[str, Any]) -> Optional[bytes]:
        HTML = _try_import_weasyprint()
        if HTML is None:
            return None
        html_str = self.render_html(data)
        try:
            return HTML(string=html_str).write_pdf()
        except Exception as exc:  # pragma: no cover
            logger.error("WeasyPrint self_audit render failed: %s", exc)
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
<h1>Self Audit — {escape(data.get('quarter_label',''))} — {escape(data.get('user_name',''))}</h1>
<p>Trades: {data.get('trades_total',0)} · Wins: {data.get('wins',0)} · Losses: {data.get('losses',0)}</p>
<p>{escape(data.get('pattern_summary',''))}</p>
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
        subject = f"PivoxQuant Self Audit — Q review"

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
                        FileName(f"self_audit_{user.id}.pdf"),
                        FileType("application/pdf"),
                        Disposition("attachment"),
                    )
                    mail.attachment = att
                SendGridAPIClient(sg_key).send(mail)
                return True
            except Exception as exc:
                logger.error("SendGrid self_audit send failed for user %s: %s",
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
                                       filename=f"self_audit_{user.id}.pdf")
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
                logger.error("SMTP self_audit send failed for user %s: %s",
                             user.id, exc)
                return False

        return False

    # ── persist + orchestrate ───────────────────────────────────────────────

    def _persist(self, user_id: int, data: dict[str, Any],
                 pdf_bytes: Optional[bytes], sent: bool) -> Artifact:
        title = f"Self Audit — {data['quarter_label']}"
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
                logger.warning("self_audit PDF write failed for user %s: %s",
                               user_id, exc)

        artefact = (
            Artifact.query
            .filter_by(user_id=user_id, type="self_audit", title=title)
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
                type="self_audit",
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
            logger.info("skipping self_audit for user %s — no trades", user.id)
            return None

        data = self.generate_for_user(user.id, quarter_end=quarter_end)
        pdf_bytes = self.render_pdf(data)
        html_body = self.render_html(data)

        sent = False
        if send:
            try:
                sent = self.send_email(user, pdf_bytes, html_body)
            except Exception as exc:
                logger.error("self_audit send raised for user %s: %s",
                             user.id, exc)
                sent = False
        return self._persist(user.id, data, pdf_bytes, sent)

    def run_quarterly(self, quarter_end: date | None = None) -> dict[str, Any]:
        """Cron — quarter +7 days 08:00 KST. Premium only."""
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
                logger.error("self_audit failed for user %s: %s", user.id, exc)

        summary = {
            "quarter_end": quarter_end.isoformat(),
            "attempted":   len(users),
            "success":     successes,
            "failed":      failures,
            "skipped":     skipped,
        }
        logger.info("self_audit quarterly run: %s", summary)
        return summary
