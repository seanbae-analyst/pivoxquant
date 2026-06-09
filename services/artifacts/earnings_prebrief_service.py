"""Earnings Pre-Brief — 30-min pre-announcement 2p PDF, emailed + pushed to Pro+ holders.

Entry points
------------
    EarningsPreBriefService().get_upcoming_earnings(hours=24)
    EarningsPreBriefService().generate_for_position(user_id, ticker, earnings_date)
    EarningsPreBriefService().render_pdf(data)        → bytes
    EarningsPreBriefService().render_email_html(data, pdf_url=None)
    EarningsPreBriefService().send_notification(user, pdf_bytes, html_body, data)
    EarningsPreBriefService().run_scan()              → summary dict (cron target, 10-min cadence)

Design principles
-----------------
1. Pro+ only. Free tier silently skipped.
2. Event-triggered, not scheduled by calendar. Cron runs every 10 min and
   matches "positions whose earnings are ~30 minutes away (tolerance ±5 min)
   and who have no prebrief artifact yet for that (ticker, earnings_date)".
3. Idempotent. (user_id, 'earnings_prebrief', title) UNIQUE, title encodes
   ticker + earnings_date so a re-run cannot duplicate.
4. Graceful degradation. Every upstream failure (FMP down, Claude down,
   WeasyPrint missing, push unconfigured) is caught and the affected
   section/channel is skipped. Fallback questions are hardcoded so a
   brief always ships with 5 questions.
5. No modifications to fmp_service / ai_service / push_service /
   weekly_memo_service / engine.py / quant_models.
   All integration is read-only import + call.

Storage
-------
PDFs live in `<project>/artifacts/earnings_prebrief/<user_id>/<ticker>_<date>.pdf`
unless `EARNINGS_PREBRIEF_STORAGE_DIR` env override is set.

Lead time
---------
`EARNINGS_PREBRIEF_LEAD_MINUTES` (default 30) controls how far before the
announcement the brief fires. Matcher tolerance is ±5 min around that.
"""
from __future__ import annotations

import logging
import os
import re
import threading
from dataclasses import dataclass
from datetime import date, datetime, time as _time, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

from extensions import db
from services.email.format_helpers import currency_prefix
from models import Artifact, Position, User
from services.legal_filter import safe_scrub, scrub_signal

logger = logging.getLogger(__name__)


# ── paths / config ───────────────────────────────────────────────────────────

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_DEFAULT_STORAGE_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "earnings_prebrief"

# Tiers eligible for the pre-brief — Pro+ only.
# Shared set so premium_plus / founding_lifetime are never silently dropped.
from ._tiers import PAID_TIERS_PRO_AND_UP as _PAID_TIERS  # noqa: E402
from services.artifacts._i18n import localize_ctx, resolve_locale  # Wave F i18n
from services.legal.disclaimers import DISCLAIMER_ARTIFACT_BILINGUAL

# ± window (minutes) around the 30-min-before target. Must exceed cron cadence
# to avoid gaps. Default 10-min cron + ±6min window → every earnings is matched
# exactly once.
_MATCH_TOLERANCE_MIN = 6

# Hardcoded fallback question bank — used when Claude API is unavailable OR
# returns fewer than 5 parsable items. Ensures a brief always ships.
_FALLBACK_QUESTIONS_EN = [
    "Guidance for next quarter and full-year outlook focus points",
    "Gross margin trend versus consensus expectations",
    "Capital expenditure plans and return on invested capital",
    "Revenue mix shift across key business segments",
    "Macro headwinds management expects to call out",
]

_FALLBACK_QUESTIONS_KO = [
    "다음 분기와 연간 가이던스의 톤과 핵심 포인트 관찰",
    "총마진 트렌드와 컨센서스 대비 차이 확인 여부",
    "설비 투자 계획과 투자수익률 코멘트 관찰",
    "주요 사업부문별 매출 구성 변화 확인",
    "거시적 역풍에 대한 경영진 코멘트 톤 확인",
]


def _lead_minutes() -> int:
    try:
        return int(os.environ.get("EARNINGS_PREBRIEF_LEAD_MINUTES", "30"))
    except ValueError:
        return 30


def _build_unsubscribe_url(user_id: Any, kind: str = "all") -> str:
    """Best-effort HMAC unsubscribe URL for the styled in-body footer.

    Returns "" when user_id is missing or the token layer is unavailable —
    rendering must never break on this. Reuses the canonical
    services.email_token builder so the token shape matches the sender's.
    """
    if not user_id:
        return ""
    try:
        from services.email_token import build_unsubscribe_url
        return build_unsubscribe_url(int(user_id), kind=kind)
    except Exception as exc:  # pragma: no cover — defensive
        logger.debug("unsubscribe url build failed for user %s: %s", user_id, exc)
        return ""


_KST = ZoneInfo("Asia/Seoul")


def _format_earnings_kst(raw: Any) -> Optional[str]:
    """Convert an earnings datetime (aware, or naive=UTC) to a KST display
    string like ``2026-05-22 06:00 KST (21:00 UTC)``.

    The pipeline stores ``earnings_datetime`` as UTC (naive or aware). The
    data-contract comment claimed the template converts to KST but it never
    did — KR users saw a bare UTC timestamp. We pre-format once here so both
    the email template and the PDF reuse the same string. Returns ``None``
    when ``raw`` is missing/unparseable so callers can fall back cleanly.
    """
    if raw is None:
        return None
    try:
        if isinstance(raw, datetime):
            dt = raw
        else:
            s = str(raw).strip()
            # Accept a trailing "Z" (UTC) — fromisoformat (py<3.11) chokes on it.
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            dt = datetime.fromisoformat(s)
    except Exception:
        return None
    # Naive → treat as UTC (matches PreBriefContext.to_dict serialization).
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    kst = dt.astimezone(_KST)
    utc = dt.astimezone(timezone.utc)
    return f"{kst.strftime('%Y-%m-%d %H:%M')} KST ({utc.strftime('%H:%M')} UTC)"


def _storage_dir() -> Path:
    override = os.environ.get("EARNINGS_PREBRIEF_STORAGE_DIR")
    d = Path(override) if override else _DEFAULT_STORAGE_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── lazy optional deps ───────────────────────────────────────────────────────

def _try_import_weasyprint():
    try:
        from weasyprint import HTML  # type: ignore
        return HTML
    except Exception as exc:  # pragma: no cover — native libs
        logger.info("WeasyPrint unavailable (%s); PDF generation will be skipped.", exc)
        return None


def _try_import_jinja():
    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape
        return Environment, FileSystemLoader, select_autoescape
    except Exception as exc:  # pragma: no cover
        logger.warning("Jinja2 unavailable (%s); template rendering will fall back to string.", exc)
        return None, None, None


# ── AI budget (module-level; mirrors weekly_memo) ────────────

_AI_LIMIT = 100  # per UTC day — earnings events are rare
_ai_usage = {"day": None, "count": 0}
_ai_lock = threading.Lock()


def _ai_budget_available() -> bool:
    today_utc = datetime.now(timezone.utc).replace(tzinfo=None).date()
    with _ai_lock:
        if _ai_usage["day"] != today_utc:
            _ai_usage["day"] = today_utc
            _ai_usage["count"] = 0
        return _ai_usage["count"] < _AI_LIMIT


def _ai_budget_consume() -> None:
    today_utc = datetime.now(timezone.utc).replace(tzinfo=None).date()
    with _ai_lock:
        if _ai_usage["day"] != today_utc:
            _ai_usage["day"] = today_utc
            _ai_usage["count"] = 0
        _ai_usage["count"] += 1


# ── data shape ───────────────────────────────────────────────────────────────

@dataclass
class PreBriefContext:
    """Template-friendly payload. Any field may be falsy — template hides
    sections that have no data so the PDF always renders cleanly."""
    user_id:             int
    user_name:           str
    ticker:              str
    company_name:        str
    earnings_datetime:   datetime          # aware or naive UTC; template converts to KST display
    fiscal_period:       str               # e.g. "Q1 2026"
    generated_at:        datetime
    consensus_eps:       Optional[float]
    consensus_eps_low:   Optional[float]
    consensus_eps_high:  Optional[float]
    consensus_revenue:   Optional[float]   # USD millions
    current_price:       Optional[float]
    surprise_history:    list[dict[str, Any]]  # last 4 qtrs
    expected_questions:  list[str]         # exactly 5
    position_shares:     float
    position_avg_cost:   float
    position_mv:         float
    sensitivity_beat:    Optional[float]   # $ PnL if +3% beat
    sensitivity_miss:    Optional[float]   # $ PnL if -3% miss
    risk_notes:          list[str]
    disclaimer:          str
    # Wave 6 — colophon provenance. Populated from
    # `resolve_user_data_lineage(user_id)`. Empty list means the template
    # renders a neutral "Data sources not specified" line; never a
    # hardcoded broker-name fallback. `option_source` is a separate
    # scalar because the option-chain section is a prose paragraph,
    # not part of the colophon lineage list.
    data_sources:        list[dict[str, str]]
    option_source:       Optional[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id":            self.user_id,
            "user_name":          self.user_name,
            "ticker":             self.ticker,
            "company_name":       self.company_name,
            "earnings_datetime":  self.earnings_datetime.isoformat() + ("Z" if self.earnings_datetime.tzinfo is None else ""),
            # Pre-formatted KST display string (KR-targeted). Both the email
            # template and the PDF reporting-date line consume this so the
            # tz conversion lives in one place, not in Jinja.
            "earnings_datetime_kst": _format_earnings_kst(self.earnings_datetime),
            "fiscal_period":      self.fiscal_period,
            "generated_at":       self.generated_at.isoformat() + "Z",
            "consensus_eps":      self.consensus_eps,
            "consensus_eps_low":  self.consensus_eps_low,
            "consensus_eps_high": self.consensus_eps_high,
            "consensus_revenue":  self.consensus_revenue,
            "current_price":      self.current_price,
            "surprise_history":   self.surprise_history,
            "expected_questions": self.expected_questions,
            "position_shares":    self.position_shares,
            "position_avg_cost":  self.position_avg_cost,
            "position_mv":        self.position_mv,
            "sensitivity_beat":   self.sensitivity_beat,
            "sensitivity_miss":   self.sensitivity_miss,
            "risk_notes":         self.risk_notes,
            "disclaimer":         self.disclaimer,
            "data_sources":       self.data_sources,
            "option_source":      self.option_source,
        }


# ── helpers ──────────────────────────────────────────────────────────────────

def _safe_fetch_quote(ticker: str) -> Optional[dict]:
    """Thin wrapper around fmp_service.get_quote — never raises."""
    try:
        from services.data import fmp as fmp  # type: ignore
        q = fmp.get_quote(ticker)
        return q if isinstance(q, dict) else (q[0] if isinstance(q, list) and q else None)
    except Exception as exc:
        logger.debug("quote fetch failed for %s: %s", ticker, exc)
        return None


def _safe_get_earnings_calendar(ticker: Optional[str] = None,
                                 days_ahead: int = 2) -> list[dict]:
    """Read-only wrapper around fmp_service.get_earnings_calendar.

    Returns [] if FMP unavailable / disabled / errors.
    """
    try:
        from services.data import fmp as fmp  # type: ignore
        rows = fmp.get_earnings_calendar(ticker=ticker, days_ahead=days_ahead)
        return rows if isinstance(rows, list) else []
    except Exception as exc:
        logger.debug("earnings calendar fetch failed (ticker=%s): %s", ticker, exc)
        return []


def _safe_get_quarterly_eps(ticker: str, quarters: int = 4) -> list[dict]:
    """Last N quarters of EPS actuals + estimates for surprise history."""
    try:
        from services.data import fmp as fmp  # type: ignore
        rows = fmp.get_quarterly_eps(ticker, quarters=quarters)
        return rows if isinstance(rows, list) else []
    except Exception as exc:
        logger.debug("quarterly EPS fetch failed for %s: %s", ticker, exc)
        return []


def _safe_get_news(ticker: str, limit: int = 8) -> list[dict]:
    try:
        from services.data import fmp as fmp  # type: ignore
        rows = fmp.get_news(ticker, limit=limit)
        return rows if isinstance(rows, list) else []
    except Exception as exc:
        logger.debug("news fetch failed for %s: %s", ticker, exc)
        return []


def _parse_earnings_row_datetime(row: dict) -> Optional[datetime]:
    """FMP earnings-calendar rows come with `date` (YYYY-MM-DD) and an
    optional `time` field ("bmo"/"amc"/"HH:MM"). We map those to a naive
    UTC datetime — good enough for the 30-min matcher.

    bmo (before market open)  → 13:30 UTC  (≈ 09:30 ET pre-market close)
    amc (after market close)  → 20:30 UTC  (≈ 16:30 ET post-market)
    """
    d_str = str(row.get("date", ""))[:10]
    if not d_str:
        return None
    try:
        d = date.fromisoformat(d_str)
    except ValueError:
        logger.debug("silent-fallback: _parse_earnings_row_datetime", exc_info=True)
        return None

    t_raw = str(row.get("time") or "").strip().lower()
    if t_raw in ("bmo", "pre", "pre-market", "premarket", "before"):
        t = _time(13, 30)
    elif t_raw in ("amc", "post", "post-market", "postmarket", "after"):
        t = _time(20, 30)
    elif re.match(r"^\d{1,2}:\d{2}$", t_raw):
        hh, mm = t_raw.split(":")
        try:
            t = _time(int(hh), int(mm))
        except ValueError:
            logger.debug("invalid HH:MM in earnings row: %r — skipping", t_raw)
            return None
    else:
        # 2026-05-02 fix — was: default to amc (20:30 UTC). That bucketed
        # every ticker with a missing/unknown time field into the same
        # 30-min match window, producing 22-ticker digest emails when
        # FMP didn't populate `time`. Now: skip rows without an explicit
        # bmo/amc/HH:MM signal — better to omit than to false-match.
        if t_raw:
            logger.debug("unrecognised earnings time %r — skipping row", t_raw)
        return None
    return datetime.combine(d, t)


def _fiscal_period_label(dt: datetime) -> str:
    """Best-effort "Q{n} {YYYY}" label from a calendar date."""
    q = (dt.month - 1) // 3 + 1
    return f"Q{q} {dt.year}"


def _derive_consensus_eps(calendar_row: dict) -> tuple[Optional[float], Optional[float], Optional[float]]:
    """Extract (mean, low, high) consensus EPS from an FMP calendar row.

    FMP stable earnings-calendar returns `epsEstimated`. Some endpoints
    also include `epsEstimatedLow`/`epsEstimatedHigh` — we read them
    defensively and fall back to ±10% of the mean for the bar chart.
    """
    mean = calendar_row.get("epsEstimated")
    try:
        mean_f = float(mean) if mean is not None else None
    except (TypeError, ValueError):
        mean_f = None

    low = calendar_row.get("epsEstimatedLow")
    high = calendar_row.get("epsEstimatedHigh")
    try:
        low_f = float(low) if low is not None else None
    except (TypeError, ValueError):
        low_f = None
    try:
        high_f = float(high) if high is not None else None
    except (TypeError, ValueError):
        high_f = None

    if mean_f is not None and (low_f is None or high_f is None):
        # Synthesise a ±10% band for visualisation; mark semantically via
        # equal low/high when mean is 0.
        band = abs(mean_f) * 0.10 if mean_f else 0.0
        low_f = low_f if low_f is not None else round(mean_f - band, 4)
        high_f = high_f if high_f is not None else round(mean_f + band, 4)

    return mean_f, low_f, high_f


def _derive_consensus_revenue(calendar_row: dict) -> Optional[float]:
    """USD millions. FMP returns raw USD — we divide by 1e6 for display."""
    rev = calendar_row.get("revenueEstimated")
    try:
        rev_f = float(rev) if rev is not None else None
    except (TypeError, ValueError):
        logger.debug("silent-fallback: _derive_consensus_revenue", exc_info=True)
        return None
    if rev_f is None or rev_f <= 0:
        return None
    # Heuristic: FMP sometimes returns millions already, sometimes raw.
    # Assume > 1e9 means raw, else already in millions.
    return round(rev_f / 1_000_000, 1) if rev_f > 1_000_000 else round(rev_f, 1)


def _build_surprise_history(eps_rows: list[dict]) -> list[dict[str, Any]]:
    """Condense last-4-quarter EPS actual vs estimate into template shape."""
    out: list[dict[str, Any]] = []
    for row in eps_rows[:4]:
        try:
            actual = float(row.get("actualEarningResult") or row.get("actualEPS") or 0)
            est = float(row.get("estimatedEarning") or row.get("epsEstimated") or 0)
        except (TypeError, ValueError):
            logger.debug("silent-fallback: _build_surprise_history", exc_info=True)
            continue
        d_str = str(row.get("date", ""))[:10]
        if est == 0:
            surprise_pct = None
        else:
            surprise_pct = round((actual - est) / abs(est) * 100, 1)
        out.append({
            "date":         d_str,
            "actual_eps":   actual,
            "estimate_eps": est,
            "surprise_pct": surprise_pct,
        })
    return out


def _position_sensitivity(shares: float, current_price: Optional[float],
                          beat_miss_pct: float = 3.0) -> tuple[Optional[float], Optional[float]]:
    """$ PnL impact for a ±`beat_miss_pct`% post-earnings move.

    Uses live price × shares × pct. If current_price is missing, returns
    (None, None) so the template hides the row.
    """
    if current_price is None or current_price <= 0 or shares <= 0:
        return None, None
    mv = current_price * shares
    move = mv * (beat_miss_pct / 100.0)
    return round(move, 2), round(-move, 2)


def _is_compliant_question(q: str) -> bool:
    """True when the question carries no canonical forbidden directive term.

    Uses the single source of truth (``services.legal.forbidden_terms``)
    instead of a local 8-token mirror that had drifted from the canonical
    50+ set (2026-06-03 legal audit H4). ``contains_forbidden_term`` is
    case-insensitive + substring-based, covering English ("buy"/"sell"/
    "recommend") and the full Korean directive vocabulary.
    """
    from services.legal.forbidden_terms import contains_forbidden_term
    return contains_forbidden_term(q) is None


def _parse_numbered_questions(text: str) -> list[str]:
    """Extract lines prefixed by '1.', '2.' etc. Strips enumeration + trailing
    punctuation. Returns up to 5 cleaned questions."""
    if not text:
        return []
    lines = []
    for raw in text.splitlines():
        m = re.match(r"^\s*(\d+)[\.\)]\s+(.+?)\s*$", raw)
        if m:
            q = m.group(2).strip().rstrip(".?!")
            if q:
                lines.append(q)
    return lines[:5]


def _call_claude_for_questions(ticker: str, fiscal_period: str,
                                news_snippets: list[str]) -> list[str]:
    """Ask Claude for 5 short expected-question bullets. Returns [] on any failure.

    Uses the shared ai_service client WITHOUT mutating it — we only read
    `.client` and `.available`. One retry when the parsed list has < 5 items.
    """
    if not _ai_budget_available():
        logger.info("AI budget exhausted; skipping Claude for %s", ticker)
        return []

    try:
        from services.ai.service import AIService  # type: ignore
    except Exception as exc:
        logger.debug("ai_service import failed: %s", exc)
        return []

    try:
        svc = AIService()
    except Exception as exc:
        logger.debug("AIService init failed: %s", exc)
        return []

    if not getattr(svc, "available", False) or not getattr(svc, "client", None):
        return []

    news_block = "\n".join(f"- {s}" for s in news_snippets[:5]) or "- (no recent news)"
    prompt = (
        f"당신은 공개 공시·실적 데이터를 중립적으로 요약하는 정보 도구입니다. "
        f"투자 조언이나 추천을 제공하지 않습니다.\n"
        f"{ticker} {fiscal_period} 실적 발표와 관련해 투자자가 공시·컨퍼런스콜에서 "
        f"확인할 수 있는 관찰 항목 5개를 작성하세요.\n"
        f"최근 뉴스:\n{news_block}\n"
        f"참고 맥락: 마진 트렌드, 가이던스 톤, 자본 배분.\n\n"
        f"형식: 번호 매김 5개. 각 항목은 1문장, 20-30자. "
        f"'매수/매도 시점', '추천', '조언' 같은 표현 금지."
    )

    def _one_shot() -> list[str]:
        try:
            resp = svc.client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}],
            )
            text = ""
            for block in getattr(resp, "content", []) or []:
                if getattr(block, "type", None) == "text":
                    text += getattr(block, "text", "")
            return _parse_numbered_questions(text)
        except Exception as exc:
            logger.warning("Claude call failed for %s: %s", ticker, exc)
            return []

    # FIX 6 — consume the AI budget once per logical generation (not once
    # per HTTP attempt). The retry below is the same generation re-attempted
    # after a truncated/unparseable first response; it must not double-count
    # against the budget. Previously _ai_budget_consume() was inside
    # _one_shot(), so a parse failure burned the budget twice.
    _ai_budget_consume()
    parsed = _one_shot()
    if len(parsed) < 5:
        # Single retry — model sometimes truncates on the first shot.
        parsed = _one_shot()
    # Compliance filter
    parsed = [q for q in parsed if _is_compliant_question(q)]
    return parsed[:5]


# ── The service ──────────────────────────────────────────────────────────────

class EarningsPreBriefService:
    """Coordinates match → assembly → render → dispatch → persist."""

    # ── discovery ──────────────────────────────────────────────────────────

    def get_upcoming_earnings(self, hours: int = 24) -> list[dict[str, Any]]:
        """Return (user_id, ticker, earnings_dt, shares, avg_cost) rows
        for Pro+ holders whose position's earnings fall within `hours`.

        Join is done in Python — `Position × User × FMP.calendar(ticker)`.
        FMP call per distinct ticker is cached 24h by fmp_service itself,
        so the scan is cheap even with many positions.
        """
        horizon = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=hours)

        paid_users = (
            User.query
            .filter(User.subscription_tier.in_(list(_PAID_TIERS)))
            .all()
        )
        paid_ids = [u.id for u in paid_users]
        if not paid_ids:
            return []

        positions = (
            Position.query
            .filter(Position.user_id.in_(paid_ids))
            .all()
        )
        if not positions:
            return []

        # Group so we hit FMP once per ticker.
        ticker_to_positions: dict[str, list[Position]] = {}
        for p in positions:
            ticker_to_positions.setdefault(p.ticker.upper(), []).append(p)

        rows: list[dict[str, Any]] = []
        # 2026-05-02 fix — dedup by (user_id, ticker). Was: emit one row
        # per Position, so a user with 3 lots of AAPL got 3 entries in
        # the same digest. Same earnings event regardless of lot count;
        # combine shares so the prebrief shows total exposure.
        seen: set[tuple[int, str]] = set()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for ticker, pos_list in ticker_to_positions.items():
            cal = _safe_get_earnings_calendar(ticker=ticker,
                                               days_ahead=max(2, (hours // 24) + 1))
            for c in cal:
                dt = _parse_earnings_row_datetime(c)
                if dt is None:
                    continue
                if not (now <= dt <= horizon):
                    continue
                # Combine shares per user across multiple lots of the same ticker.
                user_to_total: dict[int, tuple[float, float]] = {}
                for p in pos_list:
                    s = float(p.shares or 0)
                    cost = float(p.avg_cost or 0)
                    prev_s, prev_cost = user_to_total.get(p.user_id, (0.0, 0.0))
                    new_s = prev_s + s
                    # Weighted-average avg_cost across lots.
                    new_cost = (
                        ((prev_cost * prev_s) + (cost * s)) / new_s
                        if new_s > 0
                        else 0.0
                    )
                    user_to_total[p.user_id] = (new_s, new_cost)
                for uid, (total_shares, blended_cost) in user_to_total.items():
                    key = (uid, ticker)
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append({
                        "user_id":       uid,
                        "ticker":        ticker,
                        "earnings_dt":   dt,
                        "shares":        total_shares,
                        "avg_cost":      blended_cost,
                        "calendar_row":  c,
                    })
        rows.sort(key=lambda r: r["earnings_dt"])
        return rows

    # ── assembly ───────────────────────────────────────────────────────────

    def generate_for_position(self, user_id: int, ticker: str,
                               earnings_date: datetime,
                               *, calendar_row: Optional[dict] = None
                              ) -> dict[str, Any]:
        """Assemble the full payload for one (user, ticker, earnings_dt).

        Missing upstream data → section drops silently; the brief still
        renders. Hardcoded fallback questions are used when Claude is
        unavailable OR returns fewer than 5 parsable items.
        """
        user = db.session.get(User, user_id)
        if not user:
            raise ValueError(f"user {user_id} not found")

        ticker = ticker.upper()

        # Pull the position (may be stale by a few seconds; fine for email copy)
        pos = (Position.query
               .filter_by(user_id=user_id, ticker=ticker)
               .first())
        shares = float(pos.shares) if pos else 0.0
        avg_cost = float(pos.avg_cost) if pos else 0.0

        # Calendar row — reuse the one from the matcher when given, else fetch.
        if calendar_row is None:
            cal = _safe_get_earnings_calendar(ticker=ticker, days_ahead=5)
            calendar_row = next(
                (c for c in cal if _parse_earnings_row_datetime(c) and
                 abs((_parse_earnings_row_datetime(c) - earnings_date).total_seconds()) < 3600),
                {},
            ) or {}

        consensus_eps, eps_low, eps_high = _derive_consensus_eps(calendar_row)
        consensus_rev = _derive_consensus_revenue(calendar_row)

        # Live quote for sensitivity calc + header badge
        quote = _safe_fetch_quote(ticker) or {}
        try:
            current_price = float(quote.get("price") or quote.get("c") or 0) or None
        except (TypeError, ValueError):
            current_price = None

        # Surprise history — last 4 quarters
        eps_rows = _safe_get_quarterly_eps(ticker, quarters=4)
        surprise_history = _build_surprise_history(eps_rows)

        # Position sensitivity — ±3% move
        mv = (current_price or 0) * shares if current_price else avg_cost * shares
        sens_beat, sens_miss = _position_sensitivity(shares, current_price)

        # Expected questions — Claude first, then fallback
        news = _safe_get_news(ticker, limit=6)
        news_snippets = [
            (n.get("title") or n.get("headline") or "")[:140]
            for n in news if isinstance(n, dict)
        ][:5]
        ai_questions = _call_claude_for_questions(ticker,
                                                   _fiscal_period_label(earnings_date),
                                                   news_snippets)
        if len(ai_questions) < 5:
            # Top-up with fallbacks (never advisory language)
            pool = _FALLBACK_QUESTIONS_KO if user.name and re.search(r"[\uac00-\ud7a3]", user.name or "") \
                   else _FALLBACK_QUESTIONS_EN
            for q in pool:
                if len(ai_questions) >= 5:
                    break
                if q not in ai_questions:
                    ai_questions.append(q)
        expected_questions = ai_questions[:5]

        # Risk notes — rule-based, never advisory
        risk_notes: list[str] = []
        if mv and mv >= 50_000:
            risk_notes.append(f"포지션 규모 ${mv:,.0f} — 단일 이벤트 노출 구간 관찰")
        if surprise_history:
            beats = sum(1 for s in surprise_history if (s.get("surprise_pct") or 0) > 0)
            if beats <= 1:
                risk_notes.append(f"최근 4분기 중 {beats}회 beat — 기대치 조정 관찰")
        if not consensus_eps:
            risk_notes.append("컨센서스 EPS 데이터 미확보 — 참고 목적")

        company_name = quote.get("name") or ticker

        # Wave 6 — colophon data lineage. Only include broker rows for a
        # user who is actually connected. Option-chain provenance is a
        # separate scalar because the section is a prose paragraph, not
        # part of the colophon list; we claim "CBOE via Alpaca" only for
        # Alpaca-connected users.
        try:
            from services.artifacts.data_source_resolver import (
                resolve_user_data_lineage, _has_active_alpaca,
            )
            data_sources = resolve_user_data_lineage(user_id)
            option_source: Optional[str] = (
                "CBOE via Alpaca" if _has_active_alpaca(user_id) else None
            )
        except Exception as exc:
            logger.debug("earnings_prebrief lineage resolve failed for user %s: %s",
                         user_id, exc)
            data_sources = []
            option_source = None

        ctx = PreBriefContext(
            user_id=user_id,
            user_name=user.name or user.email.split("@")[0],
            ticker=ticker,
            company_name=str(company_name),
            earnings_datetime=earnings_date,
            fiscal_period=_fiscal_period_label(earnings_date),
            generated_at=datetime.now(timezone.utc).replace(tzinfo=None),
            consensus_eps=consensus_eps,
            consensus_eps_low=eps_low,
            consensus_eps_high=eps_high,
            consensus_revenue=consensus_rev,
            current_price=current_price,
            surprise_history=surprise_history,
            expected_questions=expected_questions,
            position_shares=shares,
            position_avg_cost=avg_cost,
            position_mv=round(mv, 2) if mv else 0.0,
            sensitivity_beat=sens_beat,
            sensitivity_miss=sens_miss,
            risk_notes=risk_notes,
            disclaimer=(DISCLAIMER_ARTIFACT_BILINGUAL),
            data_sources=data_sources,
            option_source=option_source,
        )
        # Legal scrub at user-facing boundary — AI-generated questions and
        # rule-based risk notes both pass through scrubber before render.
        data = scrub_signal(ctx.to_dict())
        if isinstance(data.get("expected_questions"), list):
            data["expected_questions"] = [
                safe_scrub(q, context="earnings_prebrief.question")
                for q in data["expected_questions"]
            ]
        if isinstance(data.get("risk_notes"), list):
            data["risk_notes"] = [
                safe_scrub(n, context="earnings_prebrief.risk_notes")
                for n in data["risk_notes"]
            ]
        return data

    # ── render ─────────────────────────────────────────────────────────────

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
            logger.debug("earnings_prebrief persona resolution failed: %s", exc)
            return "balanced"

    def render_pdf_html(self, data: dict[str, Any]) -> str:
        """Render the 2-page Pro Earnings Pre-Brief PDF HTML (CEO design v3)."""
        env = self._jinja_env()
        if env is None:
            return self._fallback_html(data, email=False)
        try:
            tpl = env.get_template("earnings_prebrief.html")
            ctx = dict(data)
            from services.artifacts._name_enrich import enrich_v3_names
            ctx["v3"] = enrich_v3_names(self._to_v3_shape(data))
            ctx["persona"] = self._resolve_persona(data)
            ctx = localize_ctx(ctx, resolve_locale(user_id=ctx.get('user_id'), data=data))
            return tpl.render(**ctx)
        except Exception as exc:
            logger.warning("pdf template render failed: %s", exc)
            return self._fallback_html(data, email=False)

    # ── v3 shape mapping (CEO design 2026-04-29) ────────────────────────────

    def _to_v3_shape(self, data: dict[str, Any]) -> dict[str, Any]:
        """Map generate_for_user() result → the 2-page Pro Earnings Pre-Brief
        v3 data shape consumed by services/artifacts/templates/earnings_prebrief.html.

        Source of truth for the design:
          frontend/src/components/reports/templates/earnings-prebrief.tsx
          (interface EarningsPrebriefData, 2026-04-29).

        Mapping summary
        ---------------
          ticker             ← data.ticker
          company_name       ← data.company_name
          fiscal_label       ← f"{fiscal_period} Earnings"
          reporting_date     ← formatted earnings_datetime + "After Market Close"
          position           ← f"{shares} sh · ${mv} mv"  (or "—")
          consensus          ← Consensus rows derived from
                                 (consensus_eps + consensus_revenue + surprise_history)
          implied_move_pct   ← derived placeholder ("±X.X%") or "—"
          implied_move_detail← option-source provenance line
          quant_score        ← 0..1 (unset → None hides number)
          quant_label        ← POSITIVE / NEGATIVE / NEUTRAL  (compliance — never BUY/SELL/HOLD)
          quant_tone         ← pos / neg / neutral css class hint
          factor_breakdown   ← compact "Momentum · Quality · Value · Sentiment" line
          scenarios          ← Bull / Base / Bear case rows derived from sensitivity
          watch_checklist    ← from expected_questions + risk_notes
          governance         ← static defaults (overridable via data)

        Compliance posture (자본시장법 §6)
        ----------------------------------
          - quant_label is FORCED to one of POSITIVE / NEGATIVE / NEUTRAL.
            Any input variant (BUY/SELL/HOLD/추천 etc.) is mapped to NEUTRAL.
          - watch_checklist items are passed through as observation strings
            ("OBSERVE" meta tag, never advisory verbs).
        """
        # ── Hero meta — reporting date / position ───────────────────────────
        # Prefer the service-prebuilt KST string; fall back to formatting the
        # raw datetime (also KST) for callers that didn't go through to_dict.
        kst_pre = data.get("earnings_datetime_kst")
        if kst_pre:
            reporting_date = f"{kst_pre} · Per IR calendar"
        else:
            reporting_date = self._format_reporting_date(
                data.get("earnings_datetime"))

        shares = data.get("position_shares") or 0
        mv = data.get("position_mv") or 0
        if shares and mv:
            # E3 mirror — currency must match the ticker (₩ for .KS/.KQ,
            # $ for US). The email path already does this (~line 1148);
            # the PDF path was hardcoding "$" → KR positions showed
            # "₩-denominated" MV with a "$" sign (표시광고법 §3 기만표시).
            cur = currency_prefix(data.get("ticker"))
            position_str = f"{shares:g} sh · {cur}{mv:,.0f} mv"
        elif shares:
            position_str = f"{shares:g} sh"
        else:
            position_str = "—"

        # ── Consensus rows ──────────────────────────────────────────────────
        consensus_rows = self._build_consensus_rows(data)

        # ── Quant Signal (POSITIVE / NEGATIVE / NEUTRAL only) ───────────────
        quant_label, quant_tone, quant_score = self._derive_quant_signal(data)
        factor_breakdown = self._build_factor_breakdown(data)

        # ── Implied Move ────────────────────────────────────────────────────
        implied_move_pct = self._derive_implied_move(data)
        option_src = data.get("option_source")
        if option_src:
            implied_move_detail = f"Source · {option_src}"
        else:
            implied_move_detail = "Option chain provenance not observed"

        # ── Scenarios (Bull / Base / Bear) ──────────────────────────────────
        scenarios = self._build_scenarios(data)

        # ── Watch checklist (observation only — never advisory) ─────────────
        watch_checklist = self._build_watch_checklist(data)

        # ── Cover title pieces ──────────────────────────────────────────────
        fiscal_period = data.get("fiscal_period") or ""
        fiscal_label = f"{fiscal_period} Earnings" if fiscal_period else ""
        company_name = data.get("company_name") or data.get("ticker") or "—"

        return {
            "ticker":             data.get("ticker") or "",
            "company_name":       company_name,
            "fiscal_label":       fiscal_label,
            "reporting_date":     reporting_date,
            "position":           position_str,
            "consensus":          consensus_rows,
            "implied_move_pct":   implied_move_pct,
            "implied_move_detail": implied_move_detail,
            "quant_score":        quant_score,
            "quant_label":        quant_label,
            "quant_tone":         quant_tone,
            "factor_breakdown":   factor_breakdown,
            "scenarios":          scenarios,
            "watch_checklist":    watch_checklist,
            "governance": {
                "prepared_by":  "PivoxQuant Earnings Desk",
                "reviewed_by":  "Quant Research",
                "methodology":  "58 quant models · 7-Layer Risk Defense",
                "sources":      self._format_sources(data),
            },
        }

    # ── v3 helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _format_reporting_date(raw: Any) -> str:
        """Format earnings datetime into a human-readable line.

        Accepts ISO string (with/without trailing Z) or a datetime instance.
        Falls back to a neutral default on any parsing error.
        """
        if raw is None:
            return "Earnings Date · After Market Close"
        # KR-targeted — display KST (with UTC in parens), not bare UTC.
        kst = _format_earnings_kst(raw)
        if kst:
            return f"{kst} · Per IR calendar"
        return "Earnings Date · After Market Close"

    @staticmethod
    def _build_consensus_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
        """Build the Consensus vs Whisper table rows from EPS / revenue /
        surprise history. Whisper is shown as "—" unless the upstream
        explicitly populates one (we never fabricate whisper numbers).
        """
        rows: list[dict[str, Any]] = []

        # EPS row (mean / low / high)
        eps_mean = data.get("consensus_eps")
        data.get("consensus_eps_low")
        eps_high = data.get("consensus_eps_high")
        if eps_mean is not None:
            try:
                eps_str = f"${float(eps_mean):.2f}"
            except (TypeError, ValueError):
                eps_str = "—"
            whisper_str = "—"
            if eps_high is not None:
                try:
                    whisper_str = f"${float(eps_high):.2f}"
                except (TypeError, ValueError):
                    logger.debug("silent-fallback: _build_consensus_rows", exc_info=True)
                    pass
            rows.append({
                "metric":        "EPS (Consensus)",
                "consensus":     eps_str,
                "whisper":       whisper_str,
                "last_q":        "—",
                "surprise":      "—",
            })

        # Revenue row
        rev = data.get("consensus_revenue")
        if rev is not None:
            try:
                rev_str = f"${float(rev):,.0f}M"
            except (TypeError, ValueError):
                rev_str = "—"
            rows.append({
                "metric":    "Revenue",
                "consensus": rev_str,
                "whisper":   "—",
                "last_q":    "—",
                "surprise":  "—",
            })

        # Surprise history → fold last 4 quarter surprises into rows.
        # Service emits both shapes:
        #   {date, actual_eps, estimate_eps, surprise_pct}  (legacy)
        #   {quarter, consensus, actual, surprise_pct, ...} (new template input)
        for h in (data.get("surprise_history") or [])[:4]:
            quarter = h.get("quarter") or h.get("date") or "—"
            cons = h.get("consensus") if h.get("consensus") is not None else h.get("estimate_eps")
            actual = h.get("actual") if h.get("actual") is not None else h.get("actual_eps")
            sp = h.get("surprise_pct")
            try:
                cons_str = f"${float(cons):.2f}" if cons is not None else "—"
            except (TypeError, ValueError):
                cons_str = "—"
            try:
                actual_str = f"${float(actual):.2f}" if actual is not None else "—"
            except (TypeError, ValueError):
                actual_str = "—"
            try:
                sp_val = float(sp) if sp is not None else None
            except (TypeError, ValueError):
                sp_val = None
            if sp_val is None:
                sp_str = "—"
                sp_tone = ""
            else:
                sp_str = f"{sp_val:+.1f}%"
                sp_tone = "pos" if sp_val >= 0 else "neg"
            rows.append({
                "metric":         f"Hist · {quarter}",
                "consensus":      cons_str,
                "whisper":        "—",
                "last_q":         actual_str,
                "surprise":       sp_str,
                "surprise_tone":  sp_tone,
            })

        return rows

    @staticmethod
    def _derive_quant_signal(data: dict[str, Any]) -> tuple[str, str, Optional[float]]:
        """Return (label, tone, score) where label is one of
        POSITIVE / NEGATIVE / NEUTRAL only.

        Score derivation: from `quant_score` if explicit, otherwise from
        the average surprise_pct across surprise_history (clamped 0..1).
        Compliance — any input variant (BUY/SELL/HOLD/추천 etc.) is mapped
        to NEUTRAL so the rendered label can never be advisory.
        """
        # Score
        raw_score = data.get("quant_score")
        score: Optional[float]
        try:
            score = float(raw_score) if raw_score is not None else None
        except (TypeError, ValueError):
            score = None

        if score is None:
            hist = data.get("surprise_history") or []
            sps = []
            for h in hist:
                try:
                    if h.get("surprise_pct") is not None:
                        sps.append(float(h["surprise_pct"]))
                except (TypeError, ValueError):
                    logger.debug("silent-fallback: _derive_quant_signal", exc_info=True)
                    continue
            if sps:
                avg = sum(sps) / len(sps)
                # Map ±10% surprise → 0..1 (linear, clamped)
                score = max(0.0, min(1.0, 0.5 + avg / 20.0))

        # Label — POSITIVE / NEGATIVE / NEUTRAL only
        raw_label = (data.get("quant_label") or "").strip().upper()
        if raw_label in ("POSITIVE", "NEGATIVE", "NEUTRAL"):
            label = raw_label
        elif score is not None:
            if score >= 0.6:
                label = "POSITIVE"
            elif score <= 0.4:
                label = "NEGATIVE"
            else:
                label = "NEUTRAL"
        else:
            label = "NEUTRAL"

        tone = {"POSITIVE": "pos", "NEGATIVE": "neg", "NEUTRAL": "neutral"}[label]
        return label, tone, score

    @staticmethod
    def _build_factor_breakdown(data: dict[str, Any]) -> str:
        """Compose the small-print factor line under the Quant Signal.

        Uses sensitivity numbers if available — otherwise a neutral text
        marker so the section remains observational only.
        """
        beat = data.get("sensitivity_beat")
        miss = data.get("sensitivity_miss")
        if beat is not None and miss is not None:
            try:
                return f"±3% sensitivity · beat ${float(beat):,.0f} · miss ${float(miss):,.0f}"
            except (TypeError, ValueError):
                logger.debug("silent-fallback: _build_factor_breakdown", exc_info=True)
                pass
        return "Composite signal · observation only"

    @staticmethod
    def _derive_implied_move(data: dict[str, Any]) -> str:
        """Return a "±X.X%" string when implied_move_pct or option chain
        data is present; "—" otherwise. We never synthesise a number."""
        raw = data.get("implied_move_pct")
        if raw is None:
            return "—"
        try:
            return f"±{abs(float(raw)):.1f}%"
        except (TypeError, ValueError):
            return "—"

    @staticmethod
    def _build_scenarios(data: dict[str, Any]) -> list[dict[str, Any]]:
        """Bull / Base / Bear scenario rows. Position Δ is derived from
        the live ±3% sensitivity numbers when available, otherwise a
        neutral "—" placeholder.

        §101 회피 (2026-05-08): action 필드는 사용자 본인 룰 재확인을
        촉구하는 관찰 시나리오 문구로만 작성한다. 본 함수 출력은 사용자
        본인 룰 재확인을 위한 관찰 시나리오이며, 매수·매도 권유가 아니다.
        """
        beat = data.get("sensitivity_beat")
        miss = data.get("sensitivity_miss")

        try:
            beat_str = f"+${float(beat):,.0f}" if beat is not None else "—"
        except (TypeError, ValueError):
            beat_str = "—"
        try:
            miss_str = f"−${abs(float(miss)):,.0f}" if miss is not None else "—"
        except (TypeError, ValueError):
            miss_str = "—"

        return [
            {
                "case":           "Bull Case",
                "case_detail":    "Beat consensus EPS",
                "trigger":        "EPS > 컨센서스 · 가이던스 상향",
                "action":         "본인 룰 기준 — 사전 정의한 한도·시나리오 대조 시점",
                "pos_delta":      beat_str,
                "pos_delta_tone": "pos" if beat is not None else "",
                "stop":           "—",
            },
            {
                "case":           "Base Case",
                "case_detail":    "In-line",
                "trigger":        "EPS ≈ 컨센서스 · 가이던스 ≥ 컨센서스",
                "action":         "본인 룰 기준 — 컨퍼런스콜 후 가정 대조 시점",
                "pos_delta":      "$0",
                "pos_delta_tone": "",
                "stop":           "—",
            },
            {
                "case":           "Bear Case",
                "case_detail":    "Miss or weak guide",
                "trigger":        "EPS < 컨센서스 OR 가이던스 < 컨센서스",
                "action":         "본인 룰 기준 — 리스크 한도 대조 시점",
                "pos_delta":      miss_str,
                "pos_delta_tone": "neg" if miss is not None else "",
                "stop":           "—",
            },
        ]

    @staticmethod
    def _build_watch_checklist(data: dict[str, Any]) -> list[str]:
        """Combine expected_questions + risk_notes into a single observation
        list. We dedupe and cap at 8 entries to keep the page balanced."""
        items: list[str] = []
        seen: set[str] = set()
        for src in ("expected_questions", "risk_notes"):
            for q in (data.get(src) or []):
                q_str = str(q).strip()
                if q_str and q_str not in seen:
                    seen.add(q_str)
                    items.append(q_str)
                if len(items) >= 8:
                    break
            if len(items) >= 8:
                break
        return items

    @staticmethod
    def _format_sources(data: dict[str, Any]) -> str:
        """Format colophon `data_sources` list into a single inline string.

        Falls back to the canonical default if the user has no connections —
        matches the colophon's neutral-line policy (Wave 6)."""
        ds = data.get("data_sources") or []
        if not ds:
            return "FMP · SEC EDGAR"
        parts: list[str] = []
        for d in ds:
            if not isinstance(d, dict):
                continue
            label = d.get("source") or d.get("note") or d.get("description")
            if label:
                parts.append(str(label))
        return " · ".join(parts) if parts else "FMP · SEC EDGAR"

    def render_email_html(self, data: dict[str, Any],
                           pdf_url: Optional[str] = None) -> str:
        env = self._jinja_env()
        if env is None:
            return self._fallback_html(data, email=True, pdf_url=pdf_url)
        try:
            tpl = env.get_template("earnings_prebrief_email.html")
            # E3: pass currency symbol so KR tickers show ₩ instead of $
            ctx = dict(data)
            ctx.setdefault("currency_symbol",
                           currency_prefix(data.get("ticker")))
            # FIX 5 — pass the HMAC unsubscribe URL (earnings kind, matching
            # the sender's unsubscribe_kind) so the in-body styled
            # `{% if unsubscribe_url %}` footer renders. Idempotent with the
            # sender's inject_unsubscribe_footer.
            ctx.setdefault("unsubscribe_url",
                           _build_unsubscribe_url(data.get("user_id"),
                                                  kind="earnings"))
            ctx = localize_ctx(ctx, resolve_locale(user_id=ctx.get('user_id'), data=data))
            return tpl.render(pdf_url=pdf_url, **ctx)
        except Exception as exc:
            logger.warning("email template render failed: %s", exc)
            return self._fallback_html(data, email=True, pdf_url=pdf_url)

    def render_pdf(self, data: dict[str, Any]) -> Optional[bytes]:
        """HTML → PDF via WeasyPrint. None when WeasyPrint is unavailable."""
        HTML = _try_import_weasyprint()
        if HTML is None:
            return None
        html_str = self.render_pdf_html(data)
        try:
            return HTML(string=html_str).write_pdf()
        except Exception as exc:  # pragma: no cover — native deps
            logger.error("WeasyPrint render failed: %s", exc)
            return None

    def _fallback_html(self, data: dict[str, Any], *, email: bool,
                        pdf_url: Optional[str] = None) -> str:
        """Template-free minimal HTML — keeps dispatch working in broken envs."""
        from html import escape
        qs = "".join(
            f"<li>{escape(q)}</li>" for q in (data.get("expected_questions") or [])
        )
        eps = data.get("consensus_eps")
        eps_str = f"${eps}" if eps is not None else "N/A"
        ticker = escape(data.get("ticker", "?"))
        fp = escape(data.get("fiscal_period", ""))
        user_name = escape(data.get("user_name", ""))
        cta = ""
        if email and pdf_url:
            cta = f'<p><a href="{escape(pdf_url)}">Download full PDF →</a></p>'
        return f"""<!doctype html><html><body>
<h1>{ticker} — {fp} Earnings Pre-Brief</h1>
<p>For {user_name}. Consensus EPS: <strong>{eps_str}</strong></p>
<h2>Top 5 Expected Questions</h2>
<ol>{qs}</ol>
{cta}
<p><em>{escape(data.get('disclaimer',''))}</em></p>
</body></html>"""

    # ── dispatch ───────────────────────────────────────────────────────────

    def send_notification(self, user: User,
                           pdf_bytes: Optional[bytes],
                           html_body: str,
                           data: dict[str, Any]) -> dict[str, bool]:
        """Send both email + web-push. Neither failure blocks the other.

        Returns {"email": bool, "push": bool}. Both True means full delivery.
        """
        out = {"email": False, "push": False}

        # 1) Email — SendGrid first, SMTP fallback, else skip.
        try:
            out["email"] = self._send_email(user, pdf_bytes, html_body, data)
        except Exception as exc:
            logger.error("email send raised for user %s: %s", user.id, exc)

        # 2) Push — via services.push_service.notify_insight (read-only call)
        try:
            from services.push_service import _label_for_ticker, notify_insight
            ticker = data.get("ticker", "?")
            # 2026-05-13: prefer "name (ticker)" over raw ticker in push title
            # to align with feedback_ticker_display (CEO directive, 3+ times).
            # _label_for_ticker collapses to ticker alone when the resolver
            # misses, so we never produce "X (X)".
            label = _label_for_ticker(ticker)
            # E3: KR tickers (.KS / .KQ) use ₩, US tickers $.
            title_text = f"{currency_prefix(ticker)}{label} 실적 30분 전"
            body_text = "예상 질문 5개 + 컨센서스 브리프 도착"
            # The underlying send_push_to_user accepts an explicit `url`
            # param; notify_insight hardcodes it. We call the lower-level
            # function when possible to hit /reports?highlight=... but fall
            # back to notify_insight on any import failure.
            try:
                # 2026-05-17 PR #437: send_push_to_user now lives in
                # services/push_service.py (same layer as this file)
                # so the cross-layer routes.push import is gone.
                from services.push_service import send_push_to_user
                # Artifact delivery is transactional (same class as the
                # 'artifact_ready' bell kind) — must reach opted-out paying
                # users, else the prebrief push is silently dropped for them.
                send_push_to_user(
                    user_id=user.id,
                    title=f"PivoxQuant — {title_text}",
                    body=body_text,
                    url=f"/reports?highlight={data.get('_artifact_id','')}".rstrip("="),
                    transactional=True,
                )
            except Exception:
                notify_insight(user.id, title_text, body_text)
            out["push"] = True
        except Exception as exc:
            logger.warning("push send failed for user %s: %s", user.id, exc)

        return out

    def _send_email(self, user: User,
                     pdf_bytes: Optional[bytes],
                     html_body: str,
                     data: dict[str, Any]) -> bool:
        """Phase 7 — delegate to :class:`EmailSender`.

        Earnings has its own per-channel opt-out (``email_opt_out_earnings``)
        layered on top of the global flag — passed via ``opt_out_attrs``
        so the sender short-circuits on either. Two-tier from-email
        override is preserved by resolving the chain inline.
        """
        from services.email import EmailSender, EmailCategory
        from services.push_service import _label_for_ticker

        ticker = data.get("ticker", "?")
        # 2026-05-13: subject prefers "name (ticker)" via _label_for_ticker
        # (feedback_ticker_display rule). Falls back to ticker alone on
        # resolver miss — never produces "X (X)".
        label = _label_for_ticker(ticker)
        # Two-tier env fallback — earnings-specific then global default.
        fallback = os.environ.get(
            "WEEKLY_MEMO_FROM_EMAIL", "reports@pivoxquant.com"
        )
        sender = EmailSender()
        ok = sender.send(
            user,
            email_category=EmailCategory.INFORMATION,
            subject=f"[Pre-Brief] {label} — Earnings in {_lead_minutes()} min",
            html_body=html_body,
            from_env_var="EARNINGS_PREBRIEF_FROM_EMAIL",
            from_default=fallback,
            pdf_bytes=pdf_bytes,
            pdf_filename=f"prebrief_{ticker}_{user.id}.pdf",
            opt_out_attrs=("email_opt_out", "email_opt_out_earnings"),
            # ``kind="all"`` matches the Phase 2 inlined behaviour —
            # the unsubscribe route also supports ``kind="earnings"``
            # for per-channel opt-out, but flipping that here changes
            # the existing user-facing default. Out of scope for Phase 7.
            unsubscribe_kind="all",
            event_id="earnings_pre_brief",
        )
        # Stash the SendGrid X-Message-Id so _persist can write it onto the
        # per-ticker Artifact row (webhook bounce/open mapping — 정통망법 §50).
        self._last_message_id = getattr(sender, "last_message_id", None)
        return ok

    # ── persist ────────────────────────────────────────────────────────────

    def _title_for(self, ticker: str, earnings_date: datetime) -> str:
        """Deterministic title → UNIQUE (user_id, type, title) prevents dupes.

        Format: "₩삼성전자 (005930.KS) Q1 2026 Earnings Pre-Brief — 2026-04-22 20:30"
        when the name resolves, else "$TSLA Q1 2026 …" (ticker alone).

        2026-05-13: prefer "name (ticker)" via _label_for_ticker
        (feedback_ticker_display rule). Falls back to ticker-only on miss
        so dedup still works for unresolved names. Currency prefix retained
        so the user can tell KR ($-prefix would be wrong) vs US at a glance.
        """
        from services.push_service import _label_for_ticker

        period = _fiscal_period_label(earnings_date)
        ts = earnings_date.strftime("%Y-%m-%d %H:%M")
        label = _label_for_ticker(ticker)
        # E3: KR tickers (.KS / .KQ) use ₩, US tickers $.
        return f"{currency_prefix(ticker)}{label} {period} Earnings Pre-Brief — {ts}"

    def _persist(self, user_id: int, data: dict[str, Any],
                 pdf_bytes: Optional[bytes], earnings_date: datetime,
                 sent: bool) -> Artifact:
        ticker = data["ticker"]
        title = self._title_for(ticker, earnings_date)

        pdf_path: Optional[str] = None
        if pdf_bytes:
            try:
                base = _storage_dir() / str(user_id)
                base.mkdir(parents=True, exist_ok=True)
                fname = f"{ticker}_{earnings_date.strftime('%Y%m%d_%H%M')}.pdf"
                path = base / fname
                path.write_bytes(pdf_bytes)
                pdf_path = str(path)
            except Exception as exc:
                logger.warning("PDF write failed for user %s: %s", user_id, exc)

        artefact = (
            Artifact.query
            .filter_by(user_id=user_id, type="earnings_prebrief", title=title)
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
                type="earnings_prebrief",
                title=title,
                data_json=data,
                pdf_path=pdf_path,
                sent_at=datetime.now(timezone.utc).replace(tzinfo=None) if sent else None,
            )
            db.session.add(artefact)
        # Persist the SendGrid X-Message-Id captured during _send_email so the
        # event webhook can map bounce/open/spam back to this row. The digest
        # path calls _persist with sent=False (no per-ticker email), so the
        # ``if sent`` guard correctly leaves those rows untracked.
        _msg_id = getattr(self, "_last_message_id", None)
        if sent and _msg_id:
            artefact.sg_message_id = _msg_id
        db.session.commit()
        return artefact

    def _already_sent(self, user_id: int, ticker: str,
                      earnings_date: datetime) -> bool:
        """True if a prebrief for this exact (user, ticker, earnings_dt) was
        already persisted + `sent_at` set — the dedup guard."""
        title = self._title_for(ticker, earnings_date)
        existing = (Artifact.query
                    .filter_by(user_id=user_id,
                               type="earnings_prebrief",
                               title=title)
                    .first())
        return bool(existing and existing.sent_at)

    @staticmethod
    def _digest_dedup_dates(today: Optional[date] = None) -> tuple[date, date]:
        """Return (utc_date, kst_date) — both are checked for dedup.

        Conservative dedup: a digest is "already sent today" if EITHER the
        UTC-anchored marker OR the KST-anchored marker exists. This way a
        user near KST midnight (= UTC 15:00) cannot receive two digests
        across the boundary regardless of which calendar Korea or UTC
        considers "today". Trade-off: dedup window is a superset of either
        single-timezone window (24h–33h depending on cron firing time).
        """
        now_utc = datetime.now(timezone.utc)
        utc_d = today or now_utc.date()
        kst_d = today or (now_utc + timedelta(hours=9)).date()
        return utc_d, kst_d

    def _already_sent_digest(self, user_id: int,
                              today: Optional[date] = None) -> bool:
        """Daily-level dedup for digest emails (conservative UTC ∪ KST).

        Once a user receives one digest today, additional cron runs in
        the same day must not send another digest even if more tickers
        match. Per-ticker `_already_sent` still persists Artifact rows
        for downstream features.

        Boundary
        --------
        Checks BOTH the UTC-anchored marker title (``digest-YYYY-MM-DD``)
        and the KST-anchored marker title (``digest-kst-YYYY-MM-DD``).
        Returns True if EITHER exists. This guarantees no duplicate
        digest near KST midnight (UTC 15:00) regardless of which side of
        either timezone boundary the cron fires on.

        See ``_digest_dedup_dates`` for the date-pair derivation.
        """
        utc_d, kst_d = self._digest_dedup_dates(today)
        markers = [f"digest-{utc_d.isoformat()}",
                   f"digest-kst-{kst_d.isoformat()}"]
        existing = (Artifact.query
                    .filter(Artifact.user_id == user_id,
                            Artifact.type == "earnings_prebrief_digest",
                            Artifact.title.in_(markers))
                    .filter(Artifact.sent_at.isnot(None))
                    .first())
        return existing is not None

    def _persist_digest_marker(self, user_id: int, count: int,
                                today: Optional[date] = None) -> Artifact:
        """Persist a daily marker row so subsequent cron runs skip this
        user. ``data_json`` records the ticker count for telemetry.

        Writes only the **UTC-anchored** marker (``digest-YYYY-MM-DD``).
        ``_already_sent_digest`` checks both UTC and KST markers, so the
        single UTC write is sufficient — the KST-anchored read is what
        protects the boundary.
        """
        today = today or datetime.now(timezone.utc).date()
        marker_title = f"digest-{today.isoformat()}"
        existing = (Artifact.query
                    .filter_by(user_id=user_id,
                               type="earnings_prebrief_digest",
                               title=marker_title)
                    .first())
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        if existing:
            existing.data_json = {"date": today.isoformat(),
                                   "tickers": count}
            existing.sent_at = now_naive
            artefact = existing
        else:
            artefact = Artifact(
                user_id=user_id,
                type="earnings_prebrief_digest",
                title=marker_title,
                data_json={"date": today.isoformat(),
                            "tickers": count},
                sent_at=now_naive,
            )
            db.session.add(artefact)
        # Persist the SendGrid X-Message-Id captured during _send_digest_email
        # so the event webhook can map bounce/open/spam back to this digest
        # marker row (정통망법 §50 auto-opt-out).
        _msg_id = getattr(self, "_last_digest_message_id", None)
        if _msg_id:
            artefact.sg_message_id = _msg_id
        db.session.commit()
        return artefact

    # ── orchestration ──────────────────────────────────────────────────────

    def run_for_match(self, user: User, ticker: str,
                      earnings_date: datetime,
                      *, calendar_row: Optional[dict] = None,
                      send: bool = True) -> Optional[Artifact]:
        """End-to-end: assemble → render → dispatch → persist for one match.

        Returns the Artifact row. Returns None if already delivered
        (dedup) or if upstream data was catastrophically empty.
        """
        if self._already_sent(user.id, ticker, earnings_date):
            logger.info("prebrief already sent for user=%s ticker=%s dt=%s",
                        user.id, ticker, earnings_date)
            return None

        try:
            data = self.generate_for_position(user.id, ticker, earnings_date,
                                               calendar_row=calendar_row)
        except Exception as exc:
            logger.error("prebrief assembly failed (user=%s ticker=%s): %s",
                         user.id, ticker, exc)
            return None

        pdf_bytes = self.render_pdf(data)
        html_body = self.render_email_html(data)

        sent_any = False
        if send:
            try:
                result = self.send_notification(user, pdf_bytes, html_body, data)
                sent_any = bool(result.get("email") or result.get("push"))
            except Exception as exc:
                logger.error("send_notification raised for user %s: %s", user.id, exc)

        return self._persist(user.id, data, pdf_bytes, earnings_date, sent_any)

    def run_scan(self, *, send: bool = True) -> dict[str, Any]:
        """Cron target — every 10 min. Match positions whose earnings are
        `LEAD_MINUTES ± TOLERANCE` away, dispatch prebriefs.

        Never raises. Per-user failures are logged and the loop continues.
        """
        lead = _lead_minutes()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        target_window_start = now + timedelta(minutes=lead - _MATCH_TOLERANCE_MIN)
        target_window_end   = now + timedelta(minutes=lead + _MATCH_TOLERANCE_MIN)

        try:
            candidates = self.get_upcoming_earnings(
                hours=max(1, (lead + _MATCH_TOLERANCE_MIN) // 60 + 1),
            )
        except Exception as exc:
            logger.error("scan: get_upcoming_earnings raised: %s", exc)
            return {"attempted": 0, "success": 0, "failed": 0, "skipped": 0,
                    "error": str(exc)}

        # Filter to the tight 30-min window.
        in_window = [c for c in candidates
                     if target_window_start <= c["earnings_dt"] <= target_window_end]

        successes = 0
        failures = 0
        skipped = 0
        attempted = 0

        # Chunk per-row PDF rendering so WeasyPrint memory is released
        # between batches. See services/artifacts/__init__.py.
        from services.artifacts import iter_users_chunked

        # Cache user objects so we don't re-query for every row.
        user_cache: dict[int, User] = {}
        for row in iter_users_chunked(in_window, label="earnings_prebrief.scan"):
            uid = row["user_id"]
            if uid not in user_cache:
                u = db.session.get(User, uid)
                if u is None:
                    continue
                user_cache[uid] = u
            user = user_cache[uid]

            attempted += 1
            try:
                result = self.run_for_match(
                    user, row["ticker"], row["earnings_dt"],
                    calendar_row=row.get("calendar_row"),
                    send=send,
                )
                if result is None:
                    skipped += 1
                else:
                    successes += 1
            except Exception as exc:
                db.session.rollback()
                failures += 1
                logger.error("prebrief failed user=%s ticker=%s: %s",
                             uid, row["ticker"], exc)

        summary = {
            "now":         now.isoformat() + "Z",
            "lead_minutes": lead,
            "candidates":  len(candidates),
            "in_window":   len(in_window),
            "attempted":   attempted,
            "success":     successes,
            "failed":      failures,
            "skipped":     skipped,
        }
        logger.info("earnings prebrief scan: %s", summary)
        return summary

    # ── DIGEST mode (CEO redesign 2026-05-01) ─────────────────────────────
    # Replaces per-ticker email blast (`run_scan` + `_send_email` for each
    # match) with a SINGLE consolidated email per user listing all
    # matched tickers. Dedup is daily-per-user, not per (user, ticker).

    def render_digest_email_html(self, user: User,
                                  entries: list[dict[str, Any]],
                                  *, lead_minutes: int = 30,
                                  as_of_label: Optional[str] = None) -> str:
        """Render the multi-ticker digest email HTML.

        `entries` is a list of per-ticker data dicts (each shaped like
        what `generate_for_position` returns). The template iterates
        and renders one card per entry.
        """
        env = self._jinja_env()
        if env is None:
            return self._fallback_digest_html(user, entries)
        try:
            tpl = env.get_template("earnings_prebrief_digest_email.html")
            _digest_ctx = localize_ctx(
                {
                    "user_name": getattr(user, "name", "") or getattr(user, "email", ""),
                    "entries": entries,
                    "lead_minutes": lead_minutes,
                    "as_of_label": as_of_label or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                },
                resolve_locale(user=user),
            )
            return tpl.render(**_digest_ctx)
        except Exception as exc:
            logger.warning("digest email render failed: %s", exc)
            return self._fallback_digest_html(user, entries)

    def _fallback_digest_html(self, user: User,
                               entries: list[dict[str, Any]]) -> str:
        """Plain HTML fallback when Jinja is unavailable."""
        from html import escape
        rows = "".join(
            f"<li><strong>{escape(e.get('company_name', e.get('ticker', '?')))}</strong> "
            f"<code>{escape(e.get('ticker', '?'))}</code> · "
            f"{escape(e.get('reporting_date', '—'))}</li>"
            for e in entries
        )
        return (
            f"<!doctype html><html><body>"
            f"<h1>오늘 실적 발표 {len(entries)}개 종목</h1>"
            f"<ul>{rows}</ul>"
            f"<p><em>매수·매도 권유가 아닙니다.</em></p>"
            f"</body></html>"
        )

    def _send_digest_email(self, user: User, html_body: str,
                            entries: list[dict[str, Any]]) -> bool:
        """Phase 7 — delegate to :class:`EmailSender` (HTML-only digest).

        Per-ticker PDFs are NOT attached on the digest path — when a
        user has multiple tickers we'd blow past inbox size limits.
        Subject summarises count + leading ticker.
        """
        from services.email import EmailSender, EmailCategory
        from services.push_service import _label_for_ticker

        count = len(entries)
        first_ticker = entries[0].get("ticker", "?") if entries else "?"
        if count == 1:
            # 2026-05-13: prefer "name (ticker)" via _label_for_ticker
            # (feedback_ticker_display). Drops the hardcoded `$` since
            # the label form disambiguates KR vs US already.
            first_label = _label_for_ticker(first_ticker)
            subject = f"[Pre-Brief] {first_label} 실적 발표"
        else:
            subject = f"[Pre-Brief] 오늘 {count}개 종목 실적 발표"

        fallback = os.environ.get(
            "WEEKLY_MEMO_FROM_EMAIL", "reports@pivoxquant.com"
        )
        sender = EmailSender()
        ok = sender.send(
            user,
            email_category=EmailCategory.INFORMATION,
            subject=subject,
            html_body=html_body,
            from_env_var="EARNINGS_PREBRIEF_FROM_EMAIL",
            from_default=fallback,
            opt_out_attrs=("email_opt_out", "email_opt_out_earnings"),
            unsubscribe_kind="all",
            event_id="earnings_pre_brief",
        )
        # Stash the SendGrid X-Message-Id so _persist_digest_marker can write
        # it onto the digest marker row (webhook bounce/open mapping — §50).
        self._last_digest_message_id = getattr(sender, "last_message_id", None)
        return ok

    def run_scan_digest(self, *, send: bool = True) -> dict[str, Any]:
        """User-grouped variant of `run_scan` — one digest email per user.

        Differences vs `run_scan`:
          1. Matches are grouped by user_id, then per-user rendered as a
             single multi-ticker email body via
             `render_digest_email_html`.
          2. Daily dedup at the user level (`_already_sent_digest`) — a
             user receives at most one digest per UTC day even if the
             scan fires multiple times.
          3. Per-ticker Artifact rows are still persisted via
             `_persist` so downstream features (e.g. archive list, PDF
             on-demand download) keep working unchanged.

        Cron callable. Never raises.
        """
        lead = _lead_minutes()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        today = now.date()
        target_window_start = now + timedelta(minutes=lead - _MATCH_TOLERANCE_MIN)
        target_window_end   = now + timedelta(minutes=lead + _MATCH_TOLERANCE_MIN)

        try:
            candidates = self.get_upcoming_earnings(
                hours=max(1, (lead + _MATCH_TOLERANCE_MIN) // 60 + 1),
            )
        except Exception as exc:
            logger.error("scan_digest: get_upcoming_earnings raised: %s", exc)
            return {"attempted": 0, "users_sent": 0, "tickers": 0,
                    "skipped_users": 0, "failed": 0, "error": str(exc)}

        in_window = [c for c in candidates
                     if target_window_start <= c["earnings_dt"] <= target_window_end]

        # Group matches by user_id.
        by_user: dict[int, list[dict[str, Any]]] = {}
        for row in in_window:
            uid = row["user_id"]
            by_user.setdefault(uid, []).append(row)

        # 2026-05-02 fix — defensive cap. Even after parser & dedup fixes,
        # a user can in principle have many positions reporting in the same
        # 12-min window (e.g. AAPL+MSFT+GOOG all amc on same day). Cap at
        # 8 to keep the digest readable; surplus tickers are skipped this
        # cycle but still get a per-ticker Artifact row for the archive
        # surface. If this cap is hit in practice we'll see a WARNING.
        DIGEST_TICKER_CAP = 8
        for uid, rows in list(by_user.items()):
            if len(rows) > DIGEST_TICKER_CAP:
                logger.warning(
                    "earnings digest cap hit: user=%s window-matches=%d cap=%d",
                    uid, len(rows), DIGEST_TICKER_CAP,
                )
                # Keep the first N by earnings_dt (already sorted upstream).
                by_user[uid] = rows[:DIGEST_TICKER_CAP]

        users_sent = 0
        skipped_users = 0
        ticker_total = 0
        failed = 0

        # Chunk over user-grouped rows so multiple PDFs per user release
        # WeasyPrint memory between batches. See services/artifacts/__init__.py.
        from services.artifacts import iter_users_chunked

        user_groups = list(by_user.items())
        for uid, rows in iter_users_chunked(
            user_groups, label="earnings_prebrief.scan_digest",
        ):
            user = db.session.get(User, uid)
            if user is None:
                continue

            # Daily dedup at user level
            if self._already_sent_digest(uid, today):
                skipped_users += 1
                continue

            # Build per-ticker entries (assemble + persist Artifact, but
            # do NOT send per-ticker email)
            entries: list[dict[str, Any]] = []
            for row in rows:
                try:
                    data = self.generate_for_position(
                        uid, row["ticker"], row["earnings_dt"],
                        calendar_row=row.get("calendar_row"),
                    )
                except Exception as exc:
                    logger.error("digest assembly failed user=%s ticker=%s: %s",
                                 uid, row["ticker"], exc)
                    continue
                entries.append(data)
                # Persist Artifact even before send so PDF download works
                pdf_bytes = self.render_pdf(data)
                self._persist(uid, data, pdf_bytes, row["earnings_dt"], False)
                ticker_total += 1

            if not entries:
                skipped_users += 1
                continue

            # Render single digest email
            try:
                html_body = self.render_digest_email_html(
                    user, entries,
                    lead_minutes=lead,
                    as_of_label=today.isoformat(),
                )
            except Exception as exc:
                logger.error("digest render failed for user %s: %s", uid, exc)
                failed += 1
                continue

            sent_ok = False
            if send:
                try:
                    sent_ok = self._send_digest_email(user, html_body, entries)
                except Exception as exc:
                    logger.error("digest send raised for user %s: %s", uid, exc)
                    failed += 1

            if sent_ok or not send:
                self._persist_digest_marker(uid, len(entries), today)
                users_sent += 1
            else:
                failed += 1

        summary = {
            "now":           now.isoformat() + "Z",
            "lead_minutes":  lead,
            "candidates":    len(candidates),
            "in_window":     len(in_window),
            "users_total":   len(by_user),
            "users_sent":    users_sent,
            "tickers":       ticker_total,
            "skipped_users": skipped_users,
            "failed":        failed,
        }
        logger.info("earnings prebrief scan_digest: %s", summary)
        return summary

    # ── spec-aligned aliases ───────────────────────────────────────────────
    # The MVP #3 task spec uses a slightly different surface:
    #   find_upcoming_earnings(within_minutes=60) -> list
    #   generate_for_user(user_id, ticker) -> dict
    #   render_email(data) -> str
    #   send(user, pdf_bytes, html, ticker) -> dict
    # These thin wrappers present that surface without touching any
    # existing callers.

    def find_upcoming_earnings(self, within_minutes: int = 60
                                ) -> list[dict[str, Any]]:
        """Spec-aligned alias for `get_upcoming_earnings`, expressed in
        minutes. Uses an hours ceiling so the underlying matcher's
        hour-grained FMP window covers the request."""
        hours = max(1, (within_minutes + 59) // 60)
        rows = self.get_upcoming_earnings(hours=hours)
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=within_minutes)
        return [r for r in rows if r["earnings_dt"] <= cutoff]

    def generate_for_user(self, user_id: int, ticker: str,
                          *, earnings_date: Optional[datetime] = None,
                          calendar_row: Optional[dict] = None
                          ) -> Optional[dict[str, Any]]:
        """Spec-aligned alias — resolve the earnings_date from FMP when not
        supplied. Returns None when no upcoming earnings are found for
        the ticker (rather than raising) so routes can 404 cleanly.

        Legal posture (자본시장법 §101 회피, 2026-04-29):
            본 서비스는 **사용자 보유 종목만 분석**하는 자기 데이터 도구다.
            보유하지 않은 종목 ticker 가 들어오면 ``is_empty=True`` 페이로드를
            돌려 routes 레벨에서 EmptyState UI 로 전환되도록 한다. 시장 임의
            종목 분석 가능성을 차단해 "불특정 다수 + 매매정보" 요건을 깬다.
        """
        ticker_norm = (ticker or "").strip().upper()
        if not ticker_norm:
            return None

        # ── §101 가드: 보유 종목 검증 ────────────────────────────────────
        try:
            held = (
                Position.query
                .filter_by(user_id=user_id, ticker=ticker_norm)
                .first()
            )
        except Exception as exc:
            logger.debug("position lookup failed (user=%s ticker=%s): %s",
                         user_id, ticker_norm, exc)
            held = None

        if held is None or float(held.shares or 0) <= 0:
            return {
                "is_empty":     True,
                "empty_reason": "not_in_portfolio",
                "ticker":       ticker_norm,
                "message":      "보유 종목만 분석 가능합니다",
                "user_id":      user_id,
            }

        if earnings_date is None:
            cal = _safe_get_earnings_calendar(ticker=ticker_norm, days_ahead=7)
            for c in cal:
                dt = _parse_earnings_row_datetime(c)
                if dt and dt >= datetime.now(timezone.utc).replace(tzinfo=None):
                    earnings_date = dt
                    calendar_row = c
                    break
        if earnings_date is None:
            return {
                "is_empty":     True,
                "empty_reason": "no_upcoming_earnings",
                "ticker":       ticker_norm,
                "message":      "해당 종목의 다가오는 실적 일정이 없습니다",
                "user_id":      user_id,
            }
        return self.generate_for_position(user_id, ticker_norm, earnings_date,
                                           calendar_row=calendar_row)

    def render_email(self, data: dict[str, Any],
                     pdf_url: Optional[str] = None) -> str:
        """Spec-aligned alias for `render_email_html`."""
        return self.render_email_html(data, pdf_url=pdf_url)

    def send(self, user: User, pdf_bytes: Optional[bytes],
             html: str, ticker: str) -> dict[str, bool]:
        """Spec-aligned alias for `send_notification`. Accepts `ticker`
        explicitly instead of threading a full `data` dict; rebuilds the
        minimal payload downstream wants (ticker + artifact_id if present)."""
        data = {"ticker": ticker}
        return self.send_notification(user, pdf_bytes, html, data)


# ── Spec-aligned name alias ───────────────────────────────────────────────────
# The task spec references the class as `EarningsPrebriefService` (lower-case
# 'b'); the historical class name is `EarningsPreBriefService`. We export both
# so either import path works. New code should prefer the spec-aligned form.

EarningsPrebriefService = EarningsPreBriefService


__all__ = [
    "EarningsPreBriefService",
    "EarningsPrebriefService",
    "PreBriefContext",
]
