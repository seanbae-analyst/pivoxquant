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
- All prose routed through `legal_filter.is_compliant` regex.
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
from models import Artifact, TradeHistory, User

logger = logging.getLogger(__name__)


_TEMPLATE_DIR = Path(__file__).parent / "templates"
_DEFAULT_STORAGE_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "self_audit"
# Shared set so premium_plus / founding_lifetime are never silently dropped.
from ._tiers import PAID_TIERS_PREMIUM_AND_UP as _PAID_TIERS  # noqa: E402
from services.artifacts._i18n import localize_ctx, resolve_locale  # Wave F i18n


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
    data_sources:         list[str]
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
            "data_sources":    self.data_sources,
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
        from services.legal_filter import is_compliant, safe_scrub
    except Exception:
        def is_compliant(_: str) -> bool: return True  # pragma: no cover
        def safe_scrub(t: str | None, context: str = "") -> str | None:  # pragma: no cover
            return t

    # Fallback prose (always safe)
    if not scored:
        return "이번 분기에 기록된 매수 거래가 없어 패턴 분석을 생략합니다."
    top_sectors: dict[str, int] = {}
    for s in scored:
        top_sectors[s["ticker"]] = top_sectors.get(s["ticker"], 0) + 1
    most_traded = max(top_sectors.items(), key=lambda x: x[1])[0] if top_sectors else ""
    # feedback_ticker_display: KR ticker → hangul name in prose (US stays as ticker).
    if most_traded:
        from services.name_resolver import kr_display_name
        most_traded = kr_display_name(most_traded)

    wr_str = f"{win_rate:.0f}%" if win_rate is not None else "—"
    ar_str = f"{avg_ret:+.1f}%" if avg_ret is not None else "—"
    fallback = (
        f"분기 내 총 {len(scored)}건의 거래 결정 중 승률 {wr_str}, "
        f"평균 수익률 {ar_str}가 관찰되었습니다. "
        f"가장 자주 거래된 종목은 {most_traded} 였으며, "
        f"반복 매매 패턴이 기록되었습니다."
    )

    # AI pattern-summary retired (2026-06-03 legal re-audit): this was an
    # orphaned `import ai_service` (the module moved to services.ai.service in
    # the services/ reorg) that always raised ModuleNotFoundError and fell
    # back. The deterministic, is_compliant-safe fallback above is the actual
    # product output. To revive AI here, fix the import + route output through
    # safe_scrub + a hard-reject gate, and run a compliance pass first.
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

        # Data-source provenance — Wave 5. The quarterly self-audit
        # narrates the user's own decisions, so in addition to the
        # always-truthful system sources we surface the observation
        # journal (which reflects the user's reflective notes) and
        # any broker actually connected.
        try:
            from services.artifacts.data_source_resolver import (
                resolve_user_data_sources,
            )
            data_sources = resolve_user_data_sources(
                user_id, include_journal=True,
            )
        except Exception as exc:
            logger.debug("data_source resolve failed for user %s: %s",
                         user_id, exc)
            data_sources = []

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
            data_sources=data_sources,
            disclaimer="정보 제공 목적이며 투자 권유가 아닙니다. 투자 판단은 본인 책임입니다.",
        )
        return ctx.to_dict()

    # ── v3 design shape (CEO redesign 2026-04-30) ──────────────────────────

    _NOT_CLAIMED: list[str] = [
        "본 리포트는 매수·매도 권유가 아닙니다.",
        "과거 거래 결과는 미래 수익률을 보장하지 않습니다.",
        "관찰 기준 (3개월 forward 또는 exit 가격) 외 다른 척도는 사용하지 않습니다.",
        "투자자문 또는 일임 서비스가 아닙니다.",
        "세무·법률 자문이 아닙니다.",
    ]

    _PULLQUOTE_DEFAULT = (
        "Self-review is the small hinge on which large habits turn — "
        "기록은 판결이 아니라 습관의 작은 경첩입니다."
    )

    def _to_v3_shape(self, data: dict[str, Any]) -> dict[str, Any]:
        """Map generate_for_user(...) onto the v3 2-page Premium shape."""
        quarter_label = data.get("quarter_label") or "—"
        as_of = data.get("generated_at") or data.get("period_end") or "—"
        as_of_label = str(as_of).split("T")[0] if as_of else "—"

        def _pct(v: Any, signed: bool = True) -> str:
            try:
                n = float(v)
            except (TypeError, ValueError):
                return "—"
            return f"{n:+.2f}%" if signed else f"{n:.1f}%"

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

        def _decision_rows(rows: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
            out = []
            for r in (rows or [])[:3]:
                ret = r.get("return_pct")
                out.append({
                    "ticker":   r.get("ticker") or "—",
                    "name":     r.get("name") or r.get("ticker") or "—",
                    "buy_date": r.get("buy_date") or "—",
                    "outcome":  r.get("outcome") or "—",
                    "return":   _pct(ret),
                    "tone":     _tone(ret),
                })
            return out

        win_rate = data.get("win_rate_pct")
        avg_ret = data.get("avg_return_pct")

        return {
            "doc":             f"Self Audit · {quarter_label}",
            "doc_short":       quarter_label,
            "issued":          f"Issued · {as_of_label}",
            "kpi_trades":      str(data.get("trades_total") or 0),
            "kpi_winrate":     (_pct(win_rate, signed=False)
                                if win_rate is not None else "—"),
            "kpi_avgret":      _pct(avg_ret),
            "kpi_avgret_tone": _tone(avg_ret),
            "kpi_wl":          f"{data.get('wins') or 0} / {data.get('losses') or 0}",
            "pattern_summary": data.get("pattern_summary") or "",
            "best_decisions":  _decision_rows(data.get("best_decisions")),
            "worst_decisions": _decision_rows(data.get("worst_decisions")),
            "pullquote":       self._PULLQUOTE_DEFAULT,
            "not_claimed":     list(self._NOT_CLAIMED),
            "data_sources":    data.get("data_sources") or [],
        }

    # ── render ──────────────────────────────────────────────────────────────

    def _resolve_persona(self, data: dict[str, Any]) -> str:
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
            logger.debug("self_audit persona resolution failed: %s", exc)
            return "balanced"

    def render_pdf_html(self, data: dict[str, Any]) -> str:
        env = self._jinja_env()
        if env is None:
            return self._fallback_html(data)
        try:
            ctx = dict(data)
            from services.artifacts._name_enrich import enrich_v3_names
            ctx["v3"] = enrich_v3_names(self._to_v3_shape(data))
            ctx["persona"] = self._resolve_persona(data)
            tpl = env.get_template("self_audit.html")
            ctx = localize_ctx(ctx, resolve_locale(user_id=ctx.get('user_id'), data=data))
            return tpl.render(**ctx)
        except Exception as exc:
            logger.warning("self_audit template render failed: %s", exc)
            return self._fallback_html(data)

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
        """Phase 7 — delegate to :class:`EmailSender`."""
        from services.email import EmailSender, EmailCategory

        sender = EmailSender()
        ok = sender.send(
            user,
            email_category=EmailCategory.INFORMATION,
            subject="PivoxQuant Self Audit — Q review",
            html_body=html_body,
            from_env_var="WEEKLY_MEMO_FROM_EMAIL",
            from_default="reports@pivoxquant.com",
            pdf_bytes=pdf_bytes,
            pdf_filename=f"self_audit_{user.id}.pdf",
        )
        # Stash the SendGrid X-Message-Id so _persist can write it onto the
        # Artifact row (webhook bounce/open mapping — 정통망법 §50).
        self._last_message_id = getattr(sender, "last_message_id", None)
        return ok

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
        from services.artifacts import iter_users_chunked

        quarter_end = quarter_end or date.today()

        users = (
            User.query
            .filter(User.subscription_tier.in_(list(_PAID_TIERS)))
            .all()
        )

        successes = failures = skipped = 0
        for user in iter_users_chunked(users, label="self_audit.quarterly"):
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
