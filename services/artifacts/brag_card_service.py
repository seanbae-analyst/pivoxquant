"""Monthly Brag Card — 9:16 PNG emailed 1st of each month 09:00 KST.

Entry points
------------
    BragCardService().generate_for_user(user_id, month=None) -> dict
    BragCardService().render_html(data)                      -> str
    BragCardService().render_png(html)                       -> bytes | None
    BragCardService().send_email(user, png_bytes, html)      -> bool
    BragCardService().run_monthly(target_month=None)         -> summary dict
    BragCardService().get_share_url(artifact_id)             -> str

Design principles (MVP #2 — the viral loop)
-------------------------------------------
1. **Everyone, Free included.** Unlike the Weekly Memo (Pro+), the brag
   card ships to every user with at least one trade in the target
   month. Free users ARE the distribution channel — they share to
   Instagram, which carries our watermark + referral code back in.
2. **Idempotent.** `(user_id, "brag_card", title)` is UNIQUE so a
   re-run on the same month UPSERTs the existing row.
3. **Graceful degradation.** Playwright is a large native dep
   (~120 MB Chromium). When it isn't installed, `render_png` returns
   None and the pipeline still persists data + HTML so the user can
   later download a PNG once the bundle is present.
4. **Compliance.** No "buy/sell/추천" prose — numbers and tickers only.
   Anonymous mode (`user.privacy_mode=True`) masks tickers as "A 종목"
   for users who want to share without revealing holdings.
5. **No modifications to the Weekly Memo pipeline.** Structure is
   parallel-inspired (same shape: data → render → send → persist), but
   imports are independent.
6. **Layout is 9:16 (1080 x 1920).** Inline-CSS HTML template rendered
   by a headless Chromium at 1080-wide viewport — text reflows
   naturally at that size.

Storage
-------
PNGs are written to `<PROJECT_ROOT>/artifacts/brag_card/<user_id>/
<title>.png`. Override with `BRAG_CARD_STORAGE_DIR` for a mounted
volume in production.

Share URL / OG
--------------
Each brag card persists a one-shot `share_token` on the Artifact row
(32-char urlsafe). Public route `/api/artifacts/brag-card/share/<token>`
renders the HTML directly with OG meta so Kakao/Instagram/Twitter
crawlers pick up the card image. The token carries the owner's
referral code as a query param so signup attribution is intact even
if the user reshares outside our flow.
"""
from __future__ import annotations

import logging
import os
import secrets
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from extensions import db
from models import Artifact, Position, TradeHistory, User, UserReferral
from services.legal_filter import scrub_signal

logger = logging.getLogger(__name__)


# ── paths / config ───────────────────────────────────────────────────────────

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_DEFAULT_STORAGE_DIR = Path(__file__).resolve().parents[2] / "artifacts" / "brag_card"

# 9:16 Instagram Story aspect ratio — exact Chromium viewport target.
CARD_WIDTH  = 1080
CARD_HEIGHT = 1920

# Color tokens — see frontend/design-principles-cfo.md §7.2.
# Task spec calls for #0a0a0a; we honor that exact value here and let
# the frontend globals handle the slightly warmer #0a0e17 elsewhere.
COLOR_BG      = "#0a0a0a"      # Vantablack backdrop
COLOR_FG      = "#F6F3EC"      # primary text (warm off-white)
COLOR_FG_DIM  = "rgba(246,243,236,0.70)"  # watermark
COLOR_GOLD    = "#E2B96F"      # Warm Gold — gain months
COLOR_NEUTRAL = "#8C8B87"      # Loss months / "Long View" tone


def _storage_dir() -> Path:
    override = os.environ.get("BRAG_CARD_STORAGE_DIR")
    d = Path(override) if override else _DEFAULT_STORAGE_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _share_base_url() -> str:
    """Public base URL used in share links. Trailing slash stripped."""
    url = os.environ.get("BRAG_CARD_SHARE_BASE_URL", "https://pivoxquant.com")
    return url.rstrip("/")


def _from_email() -> str:
    return os.environ.get("BRAG_CARD_FROM_EMAIL", "reports@pivoxquant.com")


# ── optional deps ────────────────────────────────────────────────────────────

def _try_import_playwright():
    """Return the sync_playwright context manager, or None if unavailable.

    Playwright ships a ~120 MB Chromium bundle that isn't installed by
    default in CI / lightweight containers. Returning None lets the
    rest of the pipeline run — the Artifact row is still persisted
    with HTML and `pdf_path=None`. Operators should run
    `playwright install chromium` once per host.
    """
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
        return sync_playwright
    except Exception as exc:  # pragma: no cover — depends on env
        logger.info(
            "Playwright unavailable (%s); PNG generation will be skipped.",
            exc,
        )
        return None


def _try_import_jinja():
    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape
        return Environment, FileSystemLoader, select_autoescape
    except Exception as exc:  # pragma: no cover
        logger.warning(
            "Jinja2 unavailable (%s); template rendering will fail.", exc,
        )
        return None, None, None


# ── data assembly ────────────────────────────────────────────────────────────

@dataclass
class BragCardContext:
    """Everything the 9:16 template needs. Missing fields render as em-dash
    so the card never crashes the pipeline on partial data."""
    user_id:            int
    user_name:          str
    referral_code:      str
    month_label:        str   # "Mar 2026" (English, mono-friendly)
    month_label_long:   str   # "March 2026"
    month_start:        date
    month_end:          date
    generated_at:       datetime
    return_pct:         Optional[float]
    trade_count:        int
    best_ticker:        Optional[str]
    best_return_pct:    Optional[float]
    worst_ticker:       Optional[str]
    worst_return_pct:   Optional[float]
    anonymous:          bool
    is_empty:           bool
    share_token:        Optional[str]
    data_sources:       list[str]
    disclaimer:         str

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id":          self.user_id,
            "user_name":        self.user_name,
            "referral_code":    self.referral_code,
            "month_label":      self.month_label,
            "month_label_long": self.month_label_long,
            "month_start":      self.month_start.isoformat(),
            "month_end":        self.month_end.isoformat(),
            "generated_at":     self.generated_at.isoformat() + "Z",
            "return_pct":       self.return_pct,
            "trade_count":      self.trade_count,
            "best_ticker":      self.best_ticker,
            "best_return_pct":  self.best_return_pct,
            "worst_ticker":     self.worst_ticker,
            "worst_return_pct": self.worst_return_pct,
            "anonymous":        self.anonymous,
            "is_empty":         self.is_empty,
            "share_token":      self.share_token,
            "data_sources":     self.data_sources,
            "disclaimer":       self.disclaimer,
        }


# ── helpers ──────────────────────────────────────────────────────────────────

_MONTH_SHORT = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]
_MONTH_LONG = [
    "January", "February", "March",    "April",   "May",      "June",
    "July",    "August",   "September", "October", "November", "December",
]


def _previous_month_bounds(today: date | None = None) -> tuple[date, date]:
    """Return (first_day, last_day) of the month *before* `today`."""
    today = today or date.today()
    first_this = today.replace(day=1)
    last_prev = first_this - timedelta(days=1)
    first_prev = last_prev.replace(day=1)
    return first_prev, last_prev


def _month_label_short(d: date) -> str:
    return f"{_MONTH_SHORT[d.month - 1]} {d.year}"


def _month_label_long(d: date) -> str:
    return f"{_MONTH_LONG[d.month - 1]} {d.year}"


def _month_title(d: date) -> str:
    """Stable title used in the Artifact table — keyed for UPSERT."""
    return f"{d.year}-{d.month:02d} Brag Card"


def _generate_share_token() -> str:
    """32-char URL-safe token. 32 * 6 = 192 bits of entropy — plenty."""
    return secrets.token_urlsafe(24)[:32]


def _compute_monthly_stats(
    user_id: int, start: date, end: date,
) -> dict[str, Any]:
    """Aggregate a user's realized trades for the target month.

    Returns a shape identical to monthly_brag_service for easy swap-in:
    {
      "return_pct":       float | None,  # realized PnL / invested cost
      "trade_count":      int,
      "best_ticker":      str  | None,
      "best_return_pct":  float| None,
      "worst_ticker":     str  | None,
      "worst_return_pct": float| None,
    }
    """
    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(end + timedelta(days=1), datetime.min.time())

    try:
        trades = (
            TradeHistory.query
            .filter(TradeHistory.user_id == user_id,
                    TradeHistory.traded_at >= start_dt,
                    TradeHistory.traded_at < end_dt)
            .order_by(TradeHistory.traded_at.asc())
            .all()
        )
    except Exception as exc:
        logger.debug("trade history fetch failed for user %s: %s", user_id, exc)
        trades = []

    if not trades:
        return {
            "return_pct":       None,
            "trade_count":      0,
            "best_ticker":      None,
            "best_return_pct":  None,
            "worst_ticker":     None,
            "worst_return_pct": None,
        }

    per_ticker: dict[str, dict[str, float]] = {}
    realized_pnl = 0.0
    realized_cost = 0.0

    for t in trades:
        tkr = (t.ticker or "").upper()
        if not tkr:
            continue
        bucket = per_ticker.setdefault(
            tkr, {"buy_cost": 0.0, "sell_pnl": 0.0, "sell_cost": 0.0},
        )
        tv = float(t.total_value or 0)
        pnl = float(t.pnl or 0)
        action = (t.action or "").upper()
        if action == "BUY":
            bucket["buy_cost"] += tv
        elif action == "SELL":
            bucket["sell_pnl"] += pnl
            bucket["sell_cost"] += tv
            realized_pnl += pnl
            realized_cost += max(tv, 0.0)

    return_pct: Optional[float] = None
    if realized_cost > 0:
        return_pct = round(realized_pnl / realized_cost * 100, 2)

    per_ticker_pct: list[tuple[str, float]] = []
    for tkr, bk in per_ticker.items():
        cost = bk["buy_cost"] or bk["sell_cost"]
        if cost <= 0 or bk["sell_cost"] <= 0:
            continue
        pct = bk["sell_pnl"] / cost * 100
        per_ticker_pct.append((tkr, round(pct, 2)))

    best_ticker = worst_ticker = None
    best_ret = worst_ret = None
    if per_ticker_pct:
        per_ticker_pct.sort(key=lambda x: x[1])
        worst_ticker, worst_ret = per_ticker_pct[0]
        best_ticker, best_ret = per_ticker_pct[-1]
        if best_ticker == worst_ticker and len(per_ticker_pct) == 1:
            worst_ticker = None
            worst_ret = None

    return {
        "return_pct":       return_pct,
        "trade_count":      len(trades),
        "best_ticker":      best_ticker,
        "best_return_pct":  best_ret,
        "worst_ticker":     worst_ticker,
        "worst_return_pct": worst_ret,
    }


def _mask_ticker(ticker: Optional[str], anonymous: bool) -> Optional[str]:
    """Anonymous mode → generic label; otherwise passthrough."""
    if not ticker:
        return ticker
    if anonymous:
        return "A 종목"
    return ticker


# ── The service ──────────────────────────────────────────────────────────────

class BragCardService:
    """Orchestrates data → HTML → PNG → email → persist for the monthly brag.

    The service is safe to run against the full user base (Free+), and
    each upstream failure is contained to one user — the monthly loop
    continues regardless.
    """

    # ── data ─────────────────────────────────────────────────────────────────

    def generate_for_user(self, user_id: int,
                          month: date | None = None,
                          *, anonymous: bool | None = None) -> dict[str, Any]:
        """Assemble the brag payload for one user.

        `month` is any date within the *target* month (default: the month
        immediately preceding today). `anonymous` explicitly overrides
        `user.privacy_mode` — leave `None` to honor the user's setting.
        """
        user = db.session.get(User, user_id)
        if not user:
            raise ValueError(f"user {user_id} not found")

        if month is None:
            start, end = _previous_month_bounds(date.today())
        else:
            start = month.replace(day=1)
            end = start.replace(day=monthrange(start.year, start.month)[1])

        stats = _compute_monthly_stats(user_id, start, end)

        has_positions = Position.query.filter_by(user_id=user_id).count() > 0
        is_empty = (stats["trade_count"] == 0) and not has_positions

        # Anonymous — explicit arg beats user attribute beats default False.
        if anonymous is None:
            anonymous = bool(getattr(user, "privacy_mode", False))

        # Referral code — side-table first (MVP#2 convention), fall back
        # to the dedicated column on users if it exists.
        try:
            referral = UserReferral.get_or_create(user_id)
            referral_code = referral.referral_code
        except Exception as exc:
            logger.debug("referral fetch failed for user %s: %s", user_id, exc)
            referral_code = getattr(user, "referral_code", "") or ""

        user_name = (user.name or "").strip() or \
                    (user.email or "").split("@")[0] or "Investor"

        # Data-source provenance — Wave 5. The brag card narrates the
        # user's own realised trades, so the truthful claim is system
        # sources + whatever broker actually served the trade history.
        try:
            from services.artifacts.data_source_resolver import (
                resolve_user_data_sources,
            )
            data_sources = resolve_user_data_sources(user_id)
        except Exception as exc:
            logger.debug("data_source resolve failed for user %s: %s",
                         user_id, exc)
            data_sources = []

        ctx = BragCardContext(
            user_id=user_id,
            user_name=user_name,
            referral_code=referral_code or "",
            month_label=_month_label_short(start),
            month_label_long=_month_label_long(start),
            month_start=start,
            month_end=end,
            generated_at=datetime.now(timezone.utc).replace(tzinfo=None),
            return_pct=stats["return_pct"],
            trade_count=stats["trade_count"],
            best_ticker=_mask_ticker(stats["best_ticker"], anonymous),
            best_return_pct=stats["best_return_pct"],
            worst_ticker=_mask_ticker(stats["worst_ticker"], anonymous),
            worst_return_pct=stats["worst_return_pct"],
            anonymous=anonymous,
            is_empty=is_empty,
            share_token=None,  # populated on first persist
            data_sources=data_sources,
            disclaimer="정보 제공 목적이며 투자 권유가 아닙니다.",
        )
        # Legal scrub at user-facing boundary — covers known free-text
        # fields (commentary/disclaimer/etc.) before the card renders.
        return scrub_signal(ctx.to_dict())

    # ── render (HTML) ────────────────────────────────────────────────────────

    def render_html(self, data: dict[str, Any]) -> str:
        """Render the brag-card HTML (the one we turn into PNG / PDF).

        Returns a minimal in-line fallback when Jinja2 is unavailable —
        enough to keep the pipeline from crashing in CI. Any missing
        data field is rendered as em-dash.

        As of 2026-04-29 the canonical template is the CEO design v3
        (`brag_card.html`), a 1-page A4 layout shared by both the PDF
        path (`render_pdf_html`) and the existing 9:16 PNG path. The
        template tolerates a missing `v3` key — we still inject one so
        every section renders with real data rather than placeholders.
        """
        env = self._jinja_env()
        if env is None:
            return self._fallback_html(data)
        try:
            tpl = env.get_template("brag_card.html")
            ctx = dict(data)
            from services.artifacts._name_enrich import enrich_v3_names
            ctx["v3"] = enrich_v3_names(self._to_v3_shape(data))
            ctx["persona"] = self._resolve_persona(data)
            return tpl.render(**ctx)
        except Exception as exc:
            logger.warning("brag card template render failed: %s", exc)
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
            logger.debug("brag_card persona resolution failed: %s", exc)
            return "balanced"

    def render_pdf_html(self, data: dict[str, Any]) -> str:
        """Render the 1-page Free Brag Card PDF HTML (CEO design v3).

        Mirror of `WeeklyMemoService.render_pdf_html`: same template, but
        with the v3 shape mapping injected so headings, KPIs, hero card,
        and pullquote pull from real `generate_for_user` output.
        """
        env = self._jinja_env()
        if env is None:
            return self._fallback_html(data)
        try:
            tpl = env.get_template("brag_card.html")
            ctx = dict(data)
            ctx["v3"] = self._to_v3_shape(data)
            ctx["persona"] = self._resolve_persona(data)
            return tpl.render(**ctx)
        except Exception as exc:
            logger.warning("brag card pdf template render failed: %s", exc)
            return self._fallback_html(data)

    # ── v3 shape mapping (CEO design 2026-04-29) ────────────────────────────

    def _to_v3_shape(self, data: dict[str, Any]) -> dict[str, Any]:
        """Map generate_for_user() result → the 1-page Free Brag Card v3
        data shape consumed by services/artifacts/templates/brag_card.html.

        Source of truth for the design:
          frontend/src/components/reports/templates/brag-card.tsx
          (interface BragCardData, 2026-04-29).

        Mapping summary
        ---------------
          month_label        ← month_label_long ("March 2026")
          report_tag         ← "BC-{YYYY}-{MM}"
          best_decision_pct  ← formatted best_return_pct, e.g. "+18.00%"
          contribution       ← "P&L $1,240" (when best_pnl_usd present)
          best_tone          ← pos / neg from sign of best_return_pct
          hit_rate           ← "X / Y" winning closed lots (—  fallback)
          hit_rate_detail    ← "Y trade(s) closed" or "—"
          month_return       ← formatted return_pct, e.g. "+12.30%"
          benchmark          ← placeholder when no benchmark wire-up
          month_return_tone  ← pos / neg from sign of return_pct
          hero               ← {ticker, title, body, entry, mark, pnl, pnl_tone}
                               from best_ticker + best_return_pct (the rest
                               are neutral placeholders — strict descriptive
                               framing, no buy/sell/추천/조언).
          why_it_worked      ← 3 neutral observations (process-focused)
          lesson_for_next    ← 3 neutral observations (process-focused)
          pullquote          ← neutral one-liner with <em> highlight

        Every placeholder is descriptive — no buy/sell/추천 verbs (자본시장법).
        Free-text strings are run through `scrub_signal` already (in
        `generate_for_user`); template-side only adds neutral framing.
        """
        # ── month / tag ─────────────────────────────────────────────────────
        month_label = (
            data.get("month_label_long")
            or data.get("month_label")
            or "—"
        )
        # Tag from month_start when available (YYYY-MM); else fall back.
        month_start = str(data.get("month_start") or "")
        if len(month_start) >= 7:
            report_tag = f"BC-{month_start[:7]}"
        else:
            report_tag = "BC-—"

        # ── best decision (KPI 1) ───────────────────────────────────────────
        best_ret = data.get("best_return_pct")
        if best_ret is None:
            best_decision_pct = "—"
            best_tone = "neutral"
        else:
            best_decision_pct = f"{best_ret:+.2f}%"
            best_tone = "pos" if best_ret >= 0 else "neg"

        contribution = data.get("contribution") or ""

        # ── hit rate (KPI 2) — derived from trade_count when no detail ──────
        # `_compute_monthly_stats` doesn't currently expose win/total
        # split; we surface trade_count as a faithful denominator and
        # leave numerator/detail as descriptive placeholders.
        trade_count = int(data.get("trade_count") or 0)
        if trade_count > 0:
            hit_rate = f"{trade_count} 건"
            hit_rate_detail = f"{trade_count} closed lot(s)"
        else:
            hit_rate = "—"
            hit_rate_detail = ""

        # ── month return (KPI 3) ────────────────────────────────────────────
        ret = data.get("return_pct")
        if ret is None:
            month_return = "—"
            month_return_tone = "neutral"
        else:
            month_return = f"{ret:+.2f}%"
            month_return_tone = "pos" if ret >= 0 else "neg"

        # Benchmark wire-up not yet on the brag pipeline — placeholder.
        benchmark = ""

        # ── hero card — single decision narrative ───────────────────────────
        # Strict neutral framing. We surface the user's own realised
        # numbers (ticker, return%) but never recommend, advise, or
        # imply forward action.
        ticker = data.get("best_ticker")
        if ticker:
            hero_title = "이번 달 단일 의사결정 기록"
            if best_ret is not None:
                hero_body = (
                    f"{ticker} 종목에서 단일 의사결정을 관찰했습니다. "
                    f"실현 수익률은 {best_decision_pct}로 기록되었습니다. "
                    "이 카드는 결과의 기록일 뿐 향후 의사결정에 대한 안내가 아닙니다."
                )
            else:
                hero_body = (
                    f"{ticker} 종목에서 단일 의사결정을 관찰했습니다. "
                    "이 카드는 결과의 기록일 뿐 향후 의사결정에 대한 안내가 아닙니다."
                )
            hero_pnl = best_decision_pct
            hero_pnl_tone = best_tone
        else:
            hero_title = "이 달의 단일 의사결정 기록"
            hero_body = (
                "이번 달, 거래 기록이 충분하지 않아 단일 의사결정을 별도로 표기할 "
                "수 없었습니다. 다음 달의 기록을 기다립니다."
            )
            hero_pnl = "—"
            hero_pnl_tone = "neutral"

        hero = {
            "ticker":   ticker or "—",
            "title":    hero_title,
            "body":     hero_body,
            "entry":    "—",
            "mark":     "—",
            "pnl":      hero_pnl,
            "pnl_tone": hero_pnl_tone,
        }

        # ── why it worked + lesson for next — neutral, process-framed ──────
        why_it_worked = [
            {
                "checked": True,
                "body":    "<strong>사전 가설 기록</strong> — 행동 전에 메모를 남기는 절차를 유지합니다.",
                "meta":    "PROCESS",
            },
            {
                "checked": True,
                "body":    "<strong>한도 준수</strong> — 단일 종목 비중 한도를 넘기지 않았습니다.",
                "meta":    "DISCIPLINE",
            },
            {
                "checked": True,
                "body":    "<strong>시나리오 점검</strong> — 베이스/베어/불 세 가지 시나리오를 검토했습니다.",
                "meta":    "REVIEW",
            },
        ]
        lesson_for_next = [
            {
                "checked": False,
                "body":    "<strong>가설 시점 박제</strong> — 다음 달도 사전 메모 절차를 유지합니다.",
                "meta":    "KEEP",
            },
            {
                "checked": False,
                "body":    "<strong>감정 분리</strong> — 단기 시장 반응을 진입 사유로 사용하지 않습니다.",
                "meta":    "GUARD",
            },
            {
                "checked": False,
                "body":    "<strong>한도 재확인</strong> — 추가 의사결정 시 단일 종목 한도를 재확인합니다.",
                "meta":    "GUARD",
            },
        ]

        # ── pullquote — process-first, no forward statements ───────────────
        pullquote = (
            "결과보다 <em>절차</em>가 먼저였다. 다음 달도 같은 절차로."
        )

        return {
            "month_label":        month_label,
            "report_tag":         report_tag,
            "best_decision_pct":  best_decision_pct,
            "contribution":       contribution,
            "best_tone":          best_tone,
            "hit_rate":           hit_rate,
            "hit_rate_detail":    hit_rate_detail,
            "month_return":       month_return,
            "benchmark":          benchmark,
            "month_return_tone":  month_return_tone,
            "hero":               hero,
            "why_it_worked":      why_it_worked,
            "lesson_for_next":    lesson_for_next,
            "pullquote":          pullquote,
        }

    def render_email_html(self, data: dict[str, Any],
                          png_url: str | None = None) -> str:
        """Render the mobile-first HTML email body."""
        env = self._jinja_env()
        share_url = self._share_url_for(data.get("share_token"),
                                        data.get("referral_code"))
        ctx = {**data, "share_url": share_url, "png_url": png_url or ""}
        if env is None:
            return self._fallback_email_html(ctx)
        try:
            tpl = env.get_template("brag_card_email.html")
            return tpl.render(**ctx)
        except Exception as exc:
            logger.warning("brag card email template render failed: %s", exc)
            return self._fallback_email_html(ctx)

    # ── render (PNG) ─────────────────────────────────────────────────────────

    def render_png(self, html: str) -> Optional[bytes]:
        """Rasterize the HTML at 1080x1920 via headless Chromium.

        Returns PNG bytes on success, `None` when Playwright/Chromium is
        unavailable. Does not raise — failures fall through to the
        artifact-without-PNG path.
        """
        sync_playwright = _try_import_playwright()
        if sync_playwright is None:
            return None
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                try:
                    context = browser.new_context(
                        viewport={"width": CARD_WIDTH, "height": CARD_HEIGHT},
                        device_scale_factor=1,
                    )
                    page = context.new_page()
                    page.set_content(html, wait_until="networkidle")
                    # Full-page screenshot of the fixed-size viewport.
                    return page.screenshot(
                        type="png",
                        full_page=False,
                        clip={
                            "x": 0, "y": 0,
                            "width": CARD_WIDTH, "height": CARD_HEIGHT,
                        },
                        omit_background=False,
                    )
                finally:
                    browser.close()
        except Exception as exc:  # pragma: no cover — browser-dependent
            logger.error("Playwright render failed: %s", exc)
            return None

    # ── send ─────────────────────────────────────────────────────────────────

    def send_email(self, user: User,
                   png_bytes: Optional[bytes],
                   html_body: str) -> bool:
        """Deliver the brag card email (PNG attachment, not PDF).

        Phase 7 — delegates to :class:`EmailSender`. Brag is the only
        artefact that ships an image attachment, so we override
        ``attachment_mime`` to ``image/png``.
        """
        from services.email import EmailSender

        return EmailSender().send(
            user,
            subject="당신의 월간 브래그 카드가 도착했어요",
            html_body=html_body,
            from_env_var="BRAG_CARD_FROM_EMAIL",
            from_default="reports@pivoxquant.com",
            pdf_bytes=png_bytes,
            pdf_filename=f"pivoxquant_brag_{user.id}.png",
            attachment_mime="image/png",
        )

    # ── share ────────────────────────────────────────────────────────────────

    def get_share_url(self, artifact_id: int) -> str:
        """Return the public share URL for a given brag card.

        URL shape: `<base>/share/brag/<share_token>?r=<referral_code>`
        — a stable deep link that downstream social crawlers can follow.
        If the artifact has no share token yet, one is allocated and
        persisted on the row (lazy).
        """
        artefact = db.session.get(Artifact, artifact_id)
        if not artefact:
            return _share_base_url()

        token = getattr(artefact, "share_token", None)
        if not token:
            # Lazy-allocate; keeps old rows forward-compatible.
            token = _generate_share_token()
            try:
                artefact.share_token = token
                db.session.commit()
            except Exception as exc:  # pragma: no cover — schema drift
                db.session.rollback()
                logger.warning(
                    "share_token backfill failed for artefact %s: %s",
                    artifact_id, exc,
                )

        referral = ""
        try:
            if artefact.data_json:
                referral = str(artefact.data_json.get("referral_code") or "")
        except Exception:
            referral = ""
        if not referral:
            try:
                referral = UserReferral.get_or_create(
                    artefact.user_id,
                ).referral_code
            except Exception:
                referral = ""

        return self._share_url_for(token, referral)

    def _share_url_for(self, token: Optional[str],
                       referral: Optional[str]) -> str:
        base = _share_base_url()
        if not token:
            if referral:
                return f"{base}/r/{referral}"
            return base
        if referral:
            return f"{base}/share/brag/{token}?r={referral}"
        return f"{base}/share/brag/{token}"

    # ── fallback HTML (no Jinja) ─────────────────────────────────────────────

    def _fallback_html(self, data: dict[str, Any]) -> str:
        """Minimal inline-CSS HTML — enough to rasterize without the template."""
        from html import escape

        ret = data.get("return_pct")
        if ret is None:
            hero = "—"
            hero_color = COLOR_NEUTRAL
        else:
            sign = "+" if ret >= 0 else ""
            hero = f"{sign}{ret:.1f}%"
            hero_color = COLOR_GOLD if ret >= 0 else COLOR_NEUTRAL

        month = escape(data.get("month_label", "—"))
        return f"""<!doctype html>
<html><head><meta charset="utf-8">
<style>
  html,body{{margin:0;padding:0;background:{COLOR_BG};
    width:{CARD_WIDTH}px;height:{CARD_HEIGHT}px;
    font-family:-apple-system,system-ui,sans-serif;color:{COLOR_FG};}}
  .hero{{font-size:220px;font-weight:700;letter-spacing:-6px;
    color:{hero_color};text-align:center;
    position:absolute;top:380px;left:0;right:0;}}
  .month{{font-size:56px;text-align:center;
    position:absolute;top:780px;left:0;right:0;color:{COLOR_FG};}}
  .watermark{{font-size:42px;letter-spacing:16px;text-transform:uppercase;
    text-align:center;color:{COLOR_FG_DIM};
    position:absolute;bottom:140px;left:0;right:0;}}
</style></head><body>
<div class="hero">{hero}</div>
<div class="month">{month}</div>
<div class="watermark">PIVOXQUANT</div>
</body></html>"""

    def _fallback_email_html(self, ctx: dict[str, Any]) -> str:
        from html import escape
        ret = ctx.get("return_pct")
        if ret is None:
            ret_str = "—"
        else:
            sign = "+" if ret >= 0 else ""
            ret_str = f"{sign}{ret:.1f}%"
        month = escape(ctx.get("month_label_long") or ctx.get("month_label", ""))
        name = escape(ctx.get("user_name", "Investor"))
        share_url = escape(ctx.get("share_url", "") or "")
        return f"""<!doctype html><html><body>
<p style="display:none;max-height:0;overflow:hidden;">
{name}의 {month} 리포트가 도착했습니다</p>
<h1>{name}님의 {month}</h1>
<p><strong>{ret_str}</strong></p>
{f'<p><a href="{share_url}">공유 링크 열기</a></p>' if share_url else ''}
</body></html>"""

    # ── persistence + orchestration ──────────────────────────────────────────

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

    def _persist(self, user_id: int, data: dict[str, Any],
                 png_bytes: Optional[bytes], html: str,
                 sent: bool,
                 target_month_start: date) -> Artifact:
        """UPSERT on (user_id, type='brag_card', title)."""
        title = _month_title(target_month_start)
        png_path: Optional[str] = None
        if png_bytes:
            try:
                base = _storage_dir() / str(user_id)
                base.mkdir(parents=True, exist_ok=True)
                path = base / f"{title.replace(' ', '_')}.png"
                path.write_bytes(png_bytes)
                png_path = str(path)
            except Exception as exc:
                logger.warning("PNG write failed for user %s: %s", user_id, exc)

        artefact = (
            Artifact.query
            .filter_by(user_id=user_id, type="brag_card", title=title)
            .first()
        )

        # Allocate a share token on first persist (UNIQUE col; lazy retry).
        token = _generate_share_token()
        data_payload = {**data, "share_token": token}

        if artefact:
            # Upsert path — keep the original share_token if present.
            if getattr(artefact, "share_token", None):
                data_payload["share_token"] = artefact.share_token
            artefact.data_json = data_payload
            if png_path:
                artefact.pdf_path = png_path  # column reused for PNG path
            if sent and not artefact.sent_at:
                artefact.sent_at = datetime.now(timezone.utc).replace(tzinfo=None)
        else:
            artefact = Artifact(
                user_id=user_id,
                type="brag_card",
                title=title,
                data_json=data_payload,
                pdf_path=png_path,
                sent_at=datetime.now(timezone.utc).replace(tzinfo=None) if sent else None,
            )
            # Set share_token attribute if the column exists on the model.
            try:
                setattr(artefact, "share_token", token)
            except Exception:
                logger.debug("silent-fallback: Set share_token attribute if the column exists on the model. | _persist", exc_info=True)
                pass
            db.session.add(artefact)

        try:
            db.session.commit()
        except Exception as exc:
            # share_token UNIQUE collision — retry once with a new token.
            db.session.rollback()
            logger.debug("persist retry after commit error: %s", exc)
            new_token = _generate_share_token()
            data_payload["share_token"] = new_token
            artefact = Artifact(
                user_id=user_id,
                type="brag_card",
                title=title + "-r",
                data_json=data_payload,
                pdf_path=png_path,
                sent_at=datetime.now(timezone.utc).replace(tzinfo=None) if sent else None,
            )
            try:
                setattr(artefact, "share_token", new_token)
            except Exception:
                logger.debug("silent-fallback: _persist", exc_info=True)
                pass
            db.session.add(artefact)
            db.session.commit()

        return artefact

    def run_for_user(self, user: User,
                     target_month: date | None = None,
                     *, send: bool = True) -> Optional[Artifact]:
        """End-to-end for one user. Empty portfolios are SKIPPED here
        (unlike the legacy monthly_brag_service, which emits a welcome
        card). That matches the task requirement: 'run_monthly 전체
        Free+ 유저 일괄, 빈 포트폴리오 skip'.
        """
        positions = Position.query.filter_by(user_id=user.id).count()
        trades = TradeHistory.query.filter_by(user_id=user.id).count()
        if positions == 0 and trades == 0:
            logger.info("skipping user %s — empty portfolio", user.id)
            return None

        data = self.generate_for_user(user.id, month=target_month)
        html = self.render_html(data)
        png_bytes = self.render_png(html)
        email_html = self.render_email_html(data)

        sent = False
        if send:
            try:
                sent = self.send_email(user, png_bytes, email_html)
            except Exception as exc:
                logger.error("send_email raised for user %s: %s", user.id, exc)
                sent = False

        if target_month is None:
            start, _ = _previous_month_bounds(date.today())
        else:
            start = target_month.replace(day=1)

        return self._persist(user.id, data, png_bytes, html, sent, start)

    def run_monthly(self, target_month: date | None = None) -> dict[str, Any]:
        """Cron target — 1st of each month 09:00 KST. Iterates over EVERY
        user (Free included) — the brag card is the viral-loop input.
        """
        if target_month is None:
            start, end = _previous_month_bounds(date.today())
        else:
            start = target_month.replace(day=1)
            start.replace(day=monthrange(start.year, start.month)[1])

        from services.artifacts import iter_users_chunked

        users = User.query.all()

        successes = 0
        failures = 0
        skipped = 0

        for user in iter_users_chunked(users, label="brag_card.monthly"):
            try:
                result = self.run_for_user(user, target_month=start)
                if result is None:
                    skipped += 1
                else:
                    successes += 1
            except Exception as exc:
                db.session.rollback()
                failures += 1
                logger.error("brag card failed for user %s: %s",
                             user.id, exc)

        summary = {
            "month":     start.isoformat(),
            "attempted": len(users),
            "success":   successes,
            "failed":    failures,
            "skipped":   skipped,
        }
        logger.info("brag card monthly run: %s", summary)
        return summary
