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
import re
import threading
from datetime import date, datetime, timedelta, timezone

from extensions import db
from models import MorningBrief, Position, SignalCache, User, Watchlist
from services.container import ai as ai_service
from services.container import fetcher

logger = logging.getLogger(__name__)


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
    """Per-position yesterday change; skips rows with no cached data."""
    out: list[dict] = []
    for p in positions:
        change = _yesterday_change(p.ticker)
        if change is None:
            continue
        out.append({
            "ticker":     p.ticker,
            "name":       _signal_data(p.ticker).get("name", p.ticker),
            "change_pct": change,
            "direction":  "up" if change > 0 else ("down" if change < 0 else "flat"),
        })
    return out


def _today_events(tickers: list[str]) -> list[dict]:
    """Upcoming events for the given tickers. Today + tomorrow window.

    Pulls from FMP earnings-calendar. No tickers => empty list (avoids the
    full-market variant, which is huge and expensive).
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
        for r in rows:
            if not isinstance(r, dict):
                continue
            d = str(r.get("date", ""))[:10]
            if d not in targets:
                continue
            events.append({
                "ticker":      ticker,
                "event_type":  "earnings",
                "date":        d,
                "description": f"{ticker} 실적 발표",
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

    content = {
        "market_summary":    market_summary,
        "portfolio_changes": portfolio_changes,
        "events":            events,
        "insight":           insight,
        "disclaimer":        "정보 제공 목적, 투자 판단은 본인 책임",
        "generated_at":      datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z",
    }

    # 5. Upsert — idempotent re-runs on the same date
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

    Returns a summary dict for logging / monitoring.
    """
    # Onboarded users are the closest proxy we have to "active".
    users = User.query.filter_by(onboarding_completed=True).all()

    successes = 0
    failures = 0
    skipped  = 0

    for user in users:
        try:
            # Users with no positions and no watchlist — skip (nothing to
            # personalise). Keeps generic briefs out of the archive.
            has_positions = Position.query.filter_by(user_id=user.id).count() > 0
            has_watch = Watchlist.query.filter_by(user_id=user.id).count() > 0
            if not has_positions and not has_watch:
                skipped += 1
                continue

            generate_brief(user)
            successes += 1
        except Exception as e:
            db.session.rollback()
            failures += 1
            logger.error(f"Morning brief failed for user {user.id}: {e}")

    summary = {
        "date":      date.today().isoformat(),
        "attempted": len(users),
        "success":   successes,
        "failed":    failures,
        "skipped":   skipped,
        "ai_usage":  ai_usage_snapshot(),
    }
    logger.info(f"Morning brief daily run: {summary}")
    return summary
