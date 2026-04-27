"""Morning Brief — daily personalized brief generation.

Entry points:
    generate_brief(user)      — generate + persist a brief for one user
    run_daily_briefs()        — generate for all onboarded users (cron target)

Design principles
-----------------
1. Legality first. Korean capital-markets law forbids individualised
   investment recommendations. Every piece of text we emit is run through
   _is_compliant() which rejects the forbidden action vocabulary
   ("추천", "매수", "매도", "사세요", "파세요", "오를 것", ...). AI insight
   that fails validation is dropped and replaced with a rule-based one.
2. Idempotent. `(user_id, brief_date)` is unique. Re-running the job the
   same morning updates the existing row instead of erroring.
3. Cost bounded. A module-level daily counter caps Claude Haiku calls at
   AI_DAILY_LIMIT; above that, every brief is generated with a rule-based
   insight and the AI call is skipped.
4. Graceful degradation. Any per-section failure is swallowed and the
   section is simply omitted; one broken upstream doesn't take down the
   whole brief.
"""
from __future__ import annotations

import logging
import os
import re
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from extensions import db
from models import MorningBrief, Position, SignalCache, User, Watchlist
from services.container import ai as ai_service
from services.container import fetcher
from services.legal_filter import safe_scrub, scrub_signal, ensure_disclaimer
from services.name_resolver import (
    lookup_name_from_signal_cache,
    resolve_stock_name,
)

logger = logging.getLogger(__name__)

# Shared templates directory (Morning Brief Plus + KPI Dashboard + other
# artefacts all live here so the _disclaimer.html partial is reachable via
# one loader). Morning Brief historically shipped as a JSON API only — with
# the Morning Brief Plus integration we start rendering the same content as
# an HTML email at 06:00 KST.
_TEMPLATE_DIR = (
    Path(__file__).parent / "artifacts" / "templates"
)
_PAID_TIERS = frozenset({"pro", "premium", "elite"})


# ── Compliance: forbidden vocabulary (regex) ─────────────────────────────────
# These words never appear in any text we persist. They'd trip the
# 자본시장법 투자자문업 line even in a "neutral" analyst context.
_FORBIDDEN_PATTERNS = [
    r"추천", r"조언", r"권(?:고|유|장)",
    r"매수", r"매도",
    r"사세요", r"파세요", r"사라", r"팔아",
    r"오를\s*것", r"내릴\s*것", r"오른다", r"내린다",
    r"\b(?:buy|sell|recommend|advice|advise)\b",
]
_FORBIDDEN_RE = re.compile("|".join(_FORBIDDEN_PATTERNS), re.IGNORECASE)


def _is_compliant(text: str) -> bool:
    """True iff `text` contains no forbidden vocabulary."""
    if not text:
        return True
    return _FORBIDDEN_RE.search(text) is None


# Public aliases for reuse by other modules (e.g. ai_service.py).
# Keep the private names above for backwards compatibility.
def is_compliant(text: str) -> bool:
    """Public wrapper around the compliance vocabulary check.

    Returns True when `text` contains none of the forbidden
    investment-advisory words ('추천', '매수', '매도', 'recommend', 'buy',
    'sell', ...). Callers should drop or redact non-compliant AI output
    before returning it to users (자본시장법 §6 미등록 투자자문업 방지).
    """
    return _is_compliant(text)


FORBIDDEN_RE = _FORBIDDEN_RE


# ── Cost guard: daily AI call budget ─────────────────────────────────────────
# Reset at UTC day boundary. Keeps the whole cohort under ~$3/month on
# Claude Haiku even if active users spike.
AI_DAILY_LIMIT = 100
_ai_usage = {"day": None, "count": 0}
_ai_lock = threading.Lock()


def _ai_budget_available() -> bool:
    """True if we still have budget to call Claude Haiku today."""
    today_utc = datetime.now(timezone.utc).replace(tzinfo=None).date()
    with _ai_lock:
        if _ai_usage["day"] != today_utc:
            _ai_usage["day"] = today_utc
            _ai_usage["count"] = 0
        return _ai_usage["count"] < AI_DAILY_LIMIT


def _ai_budget_consume() -> None:
    today_utc = datetime.now(timezone.utc).replace(tzinfo=None).date()
    with _ai_lock:
        if _ai_usage["day"] != today_utc:
            _ai_usage["day"] = today_utc
            _ai_usage["count"] = 0
        _ai_usage["count"] += 1


def ai_usage_snapshot() -> dict:
    """Diagnostic — exposed via a route for ops visibility."""
    with _ai_lock:
        return {
            "day": _ai_usage["day"].isoformat() if _ai_usage["day"] else None,
            "count": _ai_usage["count"],
            "limit": AI_DAILY_LIMIT,
        }


# ── Data helpers ─────────────────────────────────────────────────────────────

def _signal_data(ticker: str) -> dict:
    """Read the signal cache entry for a ticker as a plain dict."""
    import json
    cached = db.session.get(SignalCache, ticker)
    if not cached or not cached.data_json:
        return {}
    try:
        return json.loads(cached.data_json)
    except Exception:
        return {}


def _yesterday_change(ticker: str) -> float | None:
    """Best-effort yesterday-over-previous-close % change from SignalCache."""
    sd = _signal_data(ticker)
    for key in ("change_pct", "pct_change", "day_change_pct"):
        v = sd.get(key)
        if isinstance(v, (int, float)):
            return round(float(v), 2)
    return None


def _market_summary(macro: dict) -> dict:
    """Extract the four headline indices + VIX from the enhanced-macro dict."""
    def _pick(key):
        v = macro.get(key) if isinstance(macro, dict) else None
        if not isinstance(v, dict):
            return None
        out = {}
        if isinstance(v.get("price"), (int, float)):
            out["price"] = round(v["price"], 2)
        if isinstance(v.get("change_pct"), (int, float)):
            out["change_pct"] = round(v["change_pct"], 2)
        return out or None

    return {
        "sp500":  _pick("sp500"),
        "nasdaq": _pick("nasdaq"),
        "dow":    _pick("dow"),
        "kospi":  _pick("kospi"),
        "kosdaq": _pick("kosdaq"),
        "vix":    _pick("vix"),
    }


def _portfolio_changes(positions: list[Position]) -> list[dict]:
    """Per-position yesterday change; skips rows with no cached data.

    Name resolution: SignalCache first (broker-fresh), then the static
    US/KR registry, then ticker as last-resort fallback. The name is
    guaranteed to be a non-empty string so the frontend can render it.
    """
    out: list[dict] = []
    for p in positions:
        change = _yesterday_change(p.ticker)
        if change is None:
            continue
        cached_name = _signal_data(p.ticker).get("name")
        name = (
            cached_name
            or resolve_stock_name(p.ticker)
            or p.ticker
        )
        out.append({
            "ticker":     p.ticker,
            "name":       name,
            "change_pct": change,
            "direction":  "up" if change > 0 else ("down" if change < 0 else "flat"),
        })
    return out


def _today_events(tickers: list[str]) -> list[dict]:
    """Upcoming events for the given tickers. Today + tomorrow window.

    Pulls from FMP earnings-calendar. No tickers => empty list (avoids the
    full-market variant, which is huge and expensive).

    Each event carries a `name` field (company name, falls back to ticker)
    so the frontend can render the name prominently without a second lookup.
    """
    if not tickers:
        return []

    try:
        import fmp_service as fmp
    except Exception:
        return []

    today = date.today()
    tomorrow = today + timedelta(days=1)
    targets = {today.isoformat(), tomorrow.isoformat()}

    events: list[dict] = []
    for ticker in tickers[:10]:  # cap to protect the FMP budget
        try:
            rows = fmp.get_earnings_calendar(ticker=ticker, days_ahead=2) or []
        except Exception as e:
            logger.debug(f"Earnings fetch failed for {ticker}: {e}")
            continue
        # Prefer the broker-fresh cache, then static registry. Resolved
        # once per ticker even if multiple rows match.
        name = (
            lookup_name_from_signal_cache(ticker)
            or resolve_stock_name(ticker)
            or ticker
        )
        for r in rows:
            if not isinstance(r, dict):
                continue
            d = str(r.get("date", ""))[:10]
            if d not in targets:
                continue
            events.append({
                "ticker":      ticker,
                "name":        name,
                "event_type":  "earnings",
                "date":        d,
                "description": f"{name} 실적 발표",
                "event_time":  r.get("time") or "",
            })
            if len(events) >= 5:
                return events
    return events


# ── Insight generation (AI + rule-based fallback) ────────────────────────────

def _rule_based_insight(portfolio_changes: list[dict],
                        market_summary: dict,
                        events: list[dict]) -> str:
    """Deterministic compliant one-liner when AI is unavailable/over-budget.

    Purely descriptive statistics — no directional claims about the future.
    """
    vix = ((market_summary or {}).get("vix") or {}).get("price")
    if events:
        tickers = ", ".join(e["ticker"] for e in events[:2])
        return f"보유 종목 중 {tickers} 관련 일정 관찰됨"
    if isinstance(vix, (int, float)) and vix >= 25:
        return f"VIX {vix:.1f} 변동성 확대 구간 관찰됨"
    if portfolio_changes:
        up = sum(1 for c in portfolio_changes if c["direction"] == "up")
        down = sum(1 for c in portfolio_changes if c["direction"] == "down")
        return f"포트폴리오 상승 {up}종목, 하락 {down}종목 기록"
    return "오늘 주요 일정 없음, 시장 상황 주목"


def _generate_insight(portfolio_changes, market_summary, events) -> str:
    """Try Claude Haiku; fall back to rule-based on failure/over-budget/non-compliant."""
    fallback = _rule_based_insight(portfolio_changes, market_summary, events)

    if not _ai_budget_available():
        logger.info("Morning brief: AI daily budget exhausted, using rule-based insight")
        return fallback

    _ai_budget_consume()
    try:
        ai_text = ai_service.generate_brief_insight(
            portfolio_changes=portfolio_changes,
            market_summary=market_summary,
            events=events,
        )
    except Exception as e:
        logger.error(f"Morning brief: AI insight call failed: {e}")
        ai_text = None

    if not ai_text:
        return fallback

    ai_text = ai_text.strip().strip('"').strip("'")
    # Trim to 60 chars to guarantee "one line" on mobile
    if len(ai_text) > 60:
        ai_text = ai_text[:60].rstrip()

    if not _is_compliant(ai_text):
        logger.warning(f"Morning brief: AI insight rejected by compliance filter: {ai_text!r}")
        return fallback

    return ai_text


# ── Public API ───────────────────────────────────────────────────────────────

def generate_brief(user: User, for_date: date | None = None) -> MorningBrief:
    """Generate, upsert and return a MorningBrief for `user`."""
    brief_date = for_date or date.today()

    positions = Position.query.filter_by(user_id=user.id).all()
    watch_rows = Watchlist.query.filter_by(user_id=user.id).all()

    # 1. Yesterday's US close + KR overnight snapshot
    try:
        macro = fetcher.get_enhanced_macro() or {}
    except Exception as e:
        logger.error(f"Morning brief: macro fetch failed for user {user.id}: {e}")
        macro = {}
    market_summary = _market_summary(macro)

    # 2. Portfolio movement
    portfolio_changes = _portfolio_changes(positions)

    # 3. Today's relevant events (portfolio + watchlist intersection)
    tracked = [p.ticker for p in positions] + [w.ticker for w in watch_rows]
    events = _today_events(list(dict.fromkeys(tracked)))  # dedupe, preserve order

    # 4. AI one-liner (compliance-filtered)
    insight = _generate_insight(portfolio_changes, market_summary, events)

    # 5. KPI snapshot (Morning Brief Plus — replaces the stand-alone daily
    #    KPI Dashboard email). Best-effort; an empty/failed KPI block
    #    degrades gracefully to an empty dict and the template renders "—".
    kpis: dict = {}
    try:
        from services.artifacts.kpi_dashboard_service import (
            compute_kpis_for_user,
        )
        kpis = compute_kpis_for_user(user.id, target_date=brief_date)
    except Exception as e:
        logger.warning(f"Morning brief KPI computation failed for user {user.id}: {e}")
        kpis = {}

    content = {
        "kpis":              kpis,
        "market_summary":    market_summary,
        "portfolio_changes": portfolio_changes,
        "events":            events,
        "insight":           insight,
        "disclaimer":        "정보 제공 목적, 투자 판단은 본인 책임",
        "generated_at":      datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z",
    }

    # Legal scrub at user-facing boundary — `insight` is the AI-generated
    # one-liner; scrub_signal walks known free-text fields (insight,
    # disclaimer, message, etc.) before persistence + email render.
    content = scrub_signal(content)

    # 6. Upsert — idempotent re-runs on the same date
    existing = MorningBrief.query.filter_by(
        user_id=user.id, brief_date=brief_date
    ).first()
    if existing:
        existing.content = content
        existing.created_at = datetime.now(timezone.utc).replace(tzinfo=None)
        brief = existing
    else:
        brief = MorningBrief(
            user_id=user.id,
            brief_date=brief_date,
            content=content,
        )
        db.session.add(brief)

    db.session.commit()
    return brief


def run_daily_briefs() -> dict:
    """Generate briefs for every onboarded user. Cron target.

    With the Morning Brief Plus integration this also *emails* the brief to
    Pro+ subscribers — the stand-alone `kpi_dashboard_daily` scheduler job
    has been retired; its five KPIs are now embedded at the top of the
    Morning Brief email. Free users still get the JSON brief via `/api/brief/today`
    but no email is sent.

    Returns a summary dict for logging / monitoring.
    """
    # Onboarded users are the closest proxy we have to "active".
    users = User.query.filter_by(onboarding_completed=True).all()

    successes = 0
    failures = 0
    skipped  = 0
    emailed  = 0

    for user in users:
        try:
            # Users with no positions and no watchlist — skip (nothing to
            # personalise). Keeps generic briefs out of the archive.
            has_positions = Position.query.filter_by(user_id=user.id).count() > 0
            has_watch = Watchlist.query.filter_by(user_id=user.id).count() > 0
            if not has_positions and not has_watch:
                skipped += 1
                continue

            brief = generate_brief(user)
            successes += 1

            # Pro+ users get the Morning Brief Plus email (KPI cards + brief).
            # Free users still see the in-app /api/brief/today payload but no email.
            if (getattr(user, "subscription_tier", "free") or "free").lower() in _PAID_TIERS:
                try:
                    html_body = render_brief_email(brief.content or {},
                                                   user=user)
                    if send_brief_email(user, html_body):
                        emailed += 1
                except Exception as e:
                    logger.error(f"Morning brief email failed for user {user.id}: {e}")
        except Exception as e:
            db.session.rollback()
            failures += 1
            logger.error(f"Morning brief failed for user {user.id}: {e}")

    summary = {
        "date":      date.today().isoformat(),
        "attempted": len(users),
        "success":   successes,
        "emailed":   emailed,
        "failed":    failures,
        "skipped":   skipped,
        "ai_usage":  ai_usage_snapshot(),
    }
    logger.info(f"Morning brief daily run: {summary}")
    return summary


# ── Email rendering + delivery (Morning Brief Plus) ──────────────────────────

def _jinja_env():
    """Lazy Jinja environment pointed at the shared artifacts templates dir.

    Kept inside the function so a missing Jinja install doesn't break the
    JSON-only API — the email path is allowed to fail independently.
    """
    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape
        return Environment(
            loader=FileSystemLoader(str(_TEMPLATE_DIR)),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("Morning brief: Jinja env build failed: %s", exc)
        return None


def render_brief_email(content: dict, *, user: User | None = None) -> str:
    """Render the Morning Brief Plus HTML email.

    `content` is the dict produced by `generate_brief()` (has `kpis`,
    `market_summary`, `portfolio_changes`, `events`, `insight`,
    `disclaimer`, `generated_at`). A missing `kpis` key degrades cleanly —
    the template hides the KPI grid rather than erroring.
    """
    env = _jinja_env()
    context = {
        "content":   content,
        "kpis":      content.get("kpis") or {},
        "user_name": (user.name if user and user.name
                      else (user.email.split("@")[0] if user and user.email else "")),
        "as_of":     (content.get("kpis") or {}).get("as_of")
                     or date.today().isoformat(),
    }
    # Wave 6 — colophon provenance scalars. Only claim Alpaca for
    # Alpaca-connected users; otherwise the template elides the section
    # rather than claiming Alpaca Market Data / Alpaca FX as theirs
    # (표시광고법 §3 기만표시 방어선).
    try:
        from services.artifacts.data_source_resolver import _has_active_alpaca
        uid = getattr(user, "id", None) if user is not None else None
        alpaca_on = _has_active_alpaca(uid) if uid else False
    except Exception as exc:
        logger.debug("morning_brief lineage check failed: %s", exc)
        alpaca_on = False
    context["equities_source"] = (
        "Alpaca Market Data (IEX consolidated) · Polygon futures."
        if alpaca_on else None
    )
    context["currencies_source"] = (
        "FX rate observation via Alpaca FX." if alpaca_on else None
    )
    # Persona injection — resolve from the user's InvestmentProfile, if any.
    # Resolver is lazy-imported and never raises; unknown → "balanced".
    try:
        from services.artifacts.persona_resolver import (
            DEFAULT_PERSONA, resolve_persona,
        )
        profile = None
        if user is not None and getattr(user, "id", None):
            try:
                from models import InvestmentProfile
                profile = (
                    InvestmentProfile.query
                    .filter_by(user_id=user.id)
                    .first()
                )
            except Exception:
                profile = None
        context["persona"] = resolve_persona(profile) if profile else DEFAULT_PERSONA
    except Exception as exc:
        logger.debug("persona resolution failed: %s", exc)
        context["persona"] = "balanced"

    if env is None:
        return _fallback_brief_email(context)
    try:
        tpl = env.get_template("morning_brief_plus.html")
        return tpl.render(**context)
    except Exception as exc:
        logger.warning("Morning brief template render failed: %s", exc)
        return _fallback_brief_email(context)


def _fallback_brief_email(ctx: dict) -> str:
    """Minimal HTML used if Jinja/template is unavailable."""
    from html import escape
    content = ctx.get("content") or {}
    insight = escape(str(content.get("insight", "") or ""))
    disclaimer = escape(str(content.get("disclaimer", "") or ""))
    return (
        "<!doctype html><html><body>"
        f"<h1>PivoxQuant Morning Brief — {escape(ctx.get('as_of',''))}</h1>"
        f"<p>{insight}</p>"
        f"<p><em>{disclaimer}</em></p>"
        "</body></html>"
    )


def send_brief_email(user: User, html_body: str) -> bool:
    """Deliver Morning Brief Plus via SendGrid → SMTP → skip.

    Mirrors the KPI Dashboard / Weekly Memo sender contract so operators
    can reuse the same env vars (`SENDGRID_API_KEY`, `SMTP_*`,
    `WEEKLY_MEMO_FROM_EMAIL`). Honours `user.email_opt_out`.
    """
    if getattr(user, "email_opt_out", False):
        return False
    if not getattr(user, "email", None):
        return False

    from_email = os.environ.get(
        "WEEKLY_MEMO_FROM_EMAIL", "reports@pivoxquant.com"
    )
    subject = f"PivoxQuant Morning Brief — {date.today().isoformat()}"

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
            logger.error("SendGrid morning-brief send failed for user %s: %s",
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
            logger.error("SMTP morning-brief send failed for user %s: %s",
                         user.id, exc)
            return False

    logger.info("no email provider — skip morning-brief send for user %s", user.id)
    return False
