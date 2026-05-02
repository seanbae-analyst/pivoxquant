"""Year-End Investor Letter — Premium annual 6-page PDF (2026-04-19).

Cadence
-------
Cron fires every 31 December 10:00 KST (see `app.py ::
_scheduled_year_end_letter` / `id="year_end_letter_annual"`). The
service resolves the closed year from `target_year` (or "today().year"
by default) and aggregates that calendar year's trading history for
every Premium (+Elite) user.

Legal posture — **share-safe** design
-------------------------------------
By explicit product decision (2026-04-19) this artefact has:

- **NO share link / no public landing / no social OG**.
- **Download for the owner only** (PDF email + in-app download).
- Dollar / Won amounts are allowed in the user's *own* copy because
  they are reading their own book; the renderer must not surface
  absolute amounts to any shared surface. Percent-only KPIs are used
  wherever the data could leak via aggregate surfaces.
- Every prose field routes through `services.legal_filter.safe_scrub`.
- Disclaimer partial `_disclaimer.html` is always included.
- Engine / risk_defense / autotrader are **never** touched — this
  service is read-only.

Entry points
------------
    YearEndLetterService().generate_for_user(user_id, target_year=None) → dict
    YearEndLetterService().render_html(data)                            → str
    YearEndLetterService().render_pdf(data)                             → bytes | None
    YearEndLetterService().run_for_user(user, target_year=None)         → Artifact | None
    YearEndLetterService().run_annual(target_year=None)                 → summary dict

Storage
-------
PDFs land at `<PROJECT_ROOT>/artifacts/year_end_letter/<user_id>/<year>.pdf`
by default. Override with `YEAR_END_LETTER_STORAGE_DIR`.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

from extensions import db
from models import Artifact, InvestmentProfile, Position, TradeHistory, User

logger = logging.getLogger(__name__)


_TEMPLATE_DIR = Path(__file__).parent / "templates"
_DEFAULT_STORAGE_DIR = (
    Path(__file__).resolve().parents[2] / "artifacts" / "year_end_letter"
)
_PAID_TIERS = frozenset({"premium", "elite"})


def _storage_dir() -> Path:
    override = os.environ.get("YEAR_END_LETTER_STORAGE_DIR")
    d = Path(override) if override else _DEFAULT_STORAGE_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── lazy optional deps ───────────────────────────────────────────────────────

def _try_import_weasyprint():
    try:
        from weasyprint import HTML  # type: ignore
        return HTML
    except Exception as exc:  # pragma: no cover — depends on env
        logger.info("WeasyPrint unavailable (%s); PDF will be skipped.", exc)
        return None


def _try_import_jinja():
    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape
        return Environment, FileSystemLoader, select_autoescape
    except Exception as exc:  # pragma: no cover
        logger.warning("Jinja2 unavailable (%s).", exc)
        return None, None, None


def _safe_scrub(text: str | None) -> str:
    if not text:
        return text or ""
    try:
        from services.legal_filter import safe_scrub
        scrubbed = safe_scrub(text, context="year_end_letter")
        return scrubbed or text
    except Exception:
        return text


def _safe_price(ticker: str) -> Optional[float]:
    try:
        from services.container import fetcher
        hist = fetcher.get_price_history(ticker, period="5d")
        if hist is None or "Close" not in hist or len(hist["Close"]) == 0:
            return None
        return float(hist["Close"].iloc[-1])
    except Exception as exc:
        logger.debug("price fetch failed for %s: %s", ticker, exc)
        return None


def _sector_for_ticker(ticker: str) -> str:
    """Best-effort sector lookup — SignalCache first, unknown otherwise."""
    try:
        from models import SignalCache
        import json
        row = db.session.get(SignalCache, ticker)
        if row and row.data_json:
            try:
                payload = json.loads(row.data_json)
                sector = payload.get("sector")
                if sector:
                    return str(sector)
            except Exception:
                logger.debug("silent-fallback: _sector_for_ticker", exc_info=True)
                pass
    except Exception:
        logger.debug("silent-fallback: _sector_for_ticker", exc_info=True)
        pass
    return "Unknown"


# ── data ─────────────────────────────────────────────────────────────────────

@dataclass
class YearEndContext:
    user_id:            int
    user_name:          str
    year:               int
    period_start:       date
    period_end:         date
    generated_at:       datetime
    # P1 / P2 — annual summary
    opening_value:      Optional[float]
    closing_value:      Optional[float]
    ytd_return_pct:     Optional[float]
    benchmark_pct:      Optional[float]
    alpha_pct:          Optional[float]
    total_trades:       int
    win_rate_pct:       Optional[float]
    sector_contribution: list[dict[str, Any]]
    # P3 / P4
    best_decisions:     list[dict[str, Any]]
    worst_decisions:    list[dict[str, Any]]
    # P5
    risk_profile:       Optional[str]       # onboarding risk_profile
    realized_style:     Optional[str]       # observed style
    consistency_score:  Optional[int]       # 0-100
    consistency_notes:  str
    # P6
    watch_items:        list[dict[str, Any]]
    # Narrative
    shareholder_letter: str                 # Buffett-tone AI paragraph
    disclaimer:         str

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id":            self.user_id,
            "user_name":          self.user_name,
            "year":               self.year,
            "period_start":       self.period_start.isoformat(),
            "period_end":         self.period_end.isoformat(),
            "generated_at":       self.generated_at.isoformat() + "Z",
            "opening_value":      self.opening_value,
            "closing_value":      self.closing_value,
            "ytd_return_pct":     self.ytd_return_pct,
            "benchmark_pct":      self.benchmark_pct,
            "alpha_pct":          self.alpha_pct,
            "total_trades":       self.total_trades,
            "win_rate_pct":       self.win_rate_pct,
            "sector_contribution": self.sector_contribution,
            "best_decisions":     self.best_decisions,
            "worst_decisions":    self.worst_decisions,
            "risk_profile":       self.risk_profile,
            "realized_style":     self.realized_style,
            "consistency_score":  self.consistency_score,
            "consistency_notes":  self.consistency_notes,
            "watch_items":        self.watch_items,
            "shareholder_letter": self.shareholder_letter,
            # CRITICAL: Template reads `letter_paragraphs` (list), service generates
            # `shareholder_letter` (str). Without this bridge the AI-generated
            # Buffett-tone letter never reaches the PDF — every Premium user
            # receives the same hardcoded default fiction letter.
            # See: reports/product/PDF_CONTENT_AUDIT_2026-04-23.md §Year-End.
            "letter_paragraphs":  [p.strip() for p in (self.shareholder_letter or "").split("\n\n") if p.strip()],
            "disclaimer":         self.disclaimer,
        }


# ── helpers ──────────────────────────────────────────────────────────────────

def _year_bounds(target_year: int) -> tuple[date, date]:
    return date(target_year, 1, 1), date(target_year, 12, 31)


def _benchmark_ytd_pct(year: int) -> Optional[float]:
    """Rough proxy: SPY YTD using Jan-2 and Dec-31 closes — reasonable
    enough for the letter's alpha line; falls back to None on any
    failure so the template hides the row."""
    try:
        from services.container import fetcher
        hist = fetcher.get_price_history("SPY", period="1y")
        if hist is None or "Close" not in hist:
            return None
        closes = hist["Close"]
        if len(closes) < 30:
            return None
        first = float(closes.iloc[0])
        last = float(closes.iloc[-1])
        if first <= 0:
            return None
        return round((last / first - 1) * 100, 2)
    except Exception as exc:
        logger.debug("benchmark ytd failed: %s", exc)
        return None


def _score_year_trades(user_id: int, year_start: date, year_end: date
                       ) -> list[dict[str, Any]]:
    """List each BUY in the year with its realised outcome (earliest
    matching SELL) or a 3-month forward close. Same semantics as
    `self_audit_service._score_trades`, duplicated here intentionally to
    avoid coupling across services. Returns ticker-level records."""
    ps_dt = datetime.combine(year_start, datetime.min.time())
    pe_dt = datetime.combine(year_end, datetime.max.time())
    try:
        all_trades = (
            TradeHistory.query
            .filter(TradeHistory.user_id == user_id)
            .order_by(TradeHistory.traded_at.asc())
            .all()
        )
    except Exception as exc:
        logger.debug("history query failed for user %s: %s", user_id, exc)
        return []

    buys = [t for t in all_trades
            if (t.action or "").upper() == "BUY"
            and t.traded_at
            and ps_dt <= t.traded_at <= pe_dt]
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
        buy_price = float(b.price_per_share or 0)
        if buy_price <= 0:
            continue
        sell_price = None
        for ts, px in sells_by_ticker.get(b.ticker, []):
            if ts >= b.traded_at and px > 0:
                sell_price = px
                break
        # Forward price fallback
        if sell_price is None:
            fwd = _safe_price(b.ticker)
            sell_price = fwd if (fwd and fwd > 0) else None
        ret = None
        if sell_price and sell_price > 0:
            ret = round((sell_price / buy_price - 1) * 100, 2)
        scored.append({
            "ticker":     b.ticker,
            "name":       b.name or b.ticker,
            "buy_date":   b.traded_at.date().isoformat() if b.traded_at else None,
            "buy_price":  round(buy_price, 2),
            "shares":     float(b.shares or 0),
            "sell_price": round(sell_price, 2) if sell_price else None,
            "outcome":    "closed" if sell_price else "open",
            "return_pct": ret,
        })
    return scored


def _sector_contribution(scored: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Average return % per sector, weighted equally across trades. Keeps
    the letter percent-only — no notional amounts on this page."""
    buckets: dict[str, list[float]] = {}
    for s in scored:
        if s["return_pct"] is None:
            continue
        sec = _sector_for_ticker(s["ticker"])
        buckets.setdefault(sec, []).append(s["return_pct"])
    rows: list[dict[str, Any]] = []
    for sec, vals in buckets.items():
        if not vals:
            continue
        avg = sum(vals) / len(vals)
        rows.append({
            "sector":        sec,
            "trade_count":   len(vals),
            "avg_return_pct": round(avg, 2),
        })
    rows.sort(key=lambda r: -r["avg_return_pct"])
    return rows


def _consistency(profile: InvestmentProfile | None,
                 scored: list[dict[str, Any]]
                 ) -> tuple[Optional[str], Optional[str], Optional[int], str]:
    """Compare onboarding risk_profile vs realised trading intensity.

    Returns: (risk_profile, realized_style, score_0_100, descriptive_notes).
    Purely descriptive — never prescriptive. All prose scrubbed.
    """
    if profile is None:
        return None, None, None, ""

    risk_profile = profile.profile_type or "balanced"
    trade_count = len(scored)
    # Realised style: trade frequency + realised volatility proxy.
    rets = [s["return_pct"] for s in scored if s["return_pct"] is not None]
    if rets:
        abs_vol = sum(abs(r) for r in rets) / len(rets)
    else:
        abs_vol = 0.0

    if trade_count <= 10 and abs_vol < 8:
        realized = "conservative"
    elif trade_count <= 30 and abs_vol < 15:
        realized = "balanced"
    elif trade_count <= 80 and abs_vol < 25:
        realized = "growth"
    else:
        realized = "aggressive"

    # Score: distance between ordinal ranks.
    order = ["conservative", "balanced", "growth", "aggressive"]
    try:
        diff = abs(order.index(risk_profile) - order.index(realized))
    except ValueError:
        diff = 0
    score = max(0, 100 - diff * 25)

    note = (
        f"온보딩 성향 '{risk_profile}' 대비 실제 거래 패턴은 '{realized}' 로 기록되었습니다. "
        f"연간 거래 {trade_count}건, 평균 변동 폭 {abs_vol:.1f}%가 관찰되었습니다."
    )
    return risk_profile, realized, score, _safe_scrub(note) or note


def _watch_items(year: int) -> list[dict[str, Any]]:
    """Calendar-only watch items for the coming year. Dates are public
    policy events — the list is identical for every user and explicitly
    **not** a recommendation. Template framing says 'Watch' not 'Act'."""
    yr = year + 1
    return [
        {"date": f"{yr}-01-31", "label": "연초 FOMC 정례 회의"},
        {"date": f"{yr}-03-15", "label": "1분기 어닝 시즌 개시 (테크 large cap)"},
        {"date": f"{yr}-04-15", "label": "미국 세금 마감일 (자본이득세 신고)"},
        {"date": f"{yr}-07-05", "label": "2분기 어닝 시즌 개시"},
        {"date": f"{yr}-09-18", "label": "연준 9월 회의 — 점도표 갱신"},
        {"date": f"{yr}-12-15", "label": "연말 tax-loss harvesting 관찰 구간"},
    ]


def _shareholder_letter(ctx_partial: dict[str, Any]) -> str:
    """One-paragraph Buffett-tone narrative. Descriptive only — no
    recommendations. Scrubbed. Falls back to a deterministic sentence
    when Claude Haiku is unavailable."""
    ytd = ctx_partial.get("ytd_return_pct")
    bench = ctx_partial.get("benchmark_pct")
    best = ctx_partial.get("best_decisions") or []
    worst = ctx_partial.get("worst_decisions") or []
    year = ctx_partial.get("year")

    best_s = best[0]["ticker"] if best else None
    worst_s = worst[0]["ticker"] if worst else None

    def _fmt_pct(v): return f"{v:+.2f}%" if isinstance(v, (int, float)) else "—"

    # Fallback (always safe)
    lines = [
        f"{year}년은 귀하의 포트폴리오가 연간 {_fmt_pct(ytd)}의 결과를 기록한 해였습니다.",
    ]
    if bench is not None:
        lines.append(f"동기간 시장 벤치마크는 {_fmt_pct(bench)}를 나타냈습니다.")
    if best_s:
        lines.append(f"올해 가장 큰 수익을 낸 결정은 {best_s} 포지션으로 관찰되었습니다.")
    if worst_s:
        lines.append(f"가장 큰 손실은 {worst_s}에서 기록되었으며, 동일 패턴이 다음 해에 "
                     f"재현되는지 관찰할 만합니다.")
    lines.append("본 서한은 판단이 아닌 기록이며, 모든 결정의 주체는 귀하 본인입니다.")
    fallback = " ".join(lines)

    # Try Haiku
    try:
        import ai_service  # type: ignore
        svc_ = getattr(ai_service, "ai_service", None) or ai_service.AIService()
        if not getattr(svc_, "available", False):
            return _safe_scrub(fallback) or fallback

        best_lines = "; ".join(
            f"{b['ticker']} {_fmt_pct(b.get('return_pct'))}" for b in best[:3]
        ) or "n/a"
        worst_lines = "; ".join(
            f"{w['ticker']} {_fmt_pct(w.get('return_pct'))}" for w in worst[:3]
        ) or "n/a"
        prompt = (
            "아래는 한 투자자의 **본인 연간 거래 기록**이다. "
            "Warren Buffett 의 주주 서한 톤(겸손·장기·절제)으로 2 문단(총 5-7문장, "
            "한국어)의 '연말 자기 거래 회고 서한' 을 작성하라.\n"
            "\n"
            "**자본시장법 §101 회피 규칙 (2026-04-29 강화)**\n"
            "- 시장 전망/의견/예측 금지. 거시 경제·섹터·종목에 대한 견해 일절 금지.\n"
            "- 시장 데이터는 **객관 통계 수치**만 사실로 인용 (예: 'S&P 500 YTD +12%').\n"
            "  벤치마크 대비 비교는 **숫자 대조까지만**, 그 의미 해석 금지.\n"
            "- 사용자 본인 거래 기록만 회고. **본인이 거래한 종목 외 다른 종목 언급 금지**.\n"
            "- 추천/매수/매도/조언/목표가/예측/전망/유망/주목 같은 단어 금지.\n"
            "- '귀하' 또는 '당신'으로 독자를 지칭.\n"
            "- 수치는 %만 인용 (금액 언급 금지).\n"
            "- 본인의 실수와 교훈을 정직하게 서술 (blame 없이, 다만 자기 결정 한정).\n"
            "\n"
            f"연도: {year}\n"
            f"본인 YTD: {_fmt_pct(ytd)} / 시장 벤치마크 통계: {_fmt_pct(bench)}\n"
            f"본인 베스트 거래: {best_lines}\n"
            f"본인 워스트 거래: {worst_lines}\n"
        )
        resp = svc_.client.messages.create(
            model=ai_service.MODEL,
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(
            getattr(b, "text", "") for b in (resp.content or [])
            if getattr(b, "type", "") == "text"
        ).strip()
        scrubbed = _safe_scrub(text) or text
        if not scrubbed:
            return _safe_scrub(fallback) or fallback
        return scrubbed[:1500]
    except Exception as exc:
        logger.debug("year-end letter AI failed: %s", exc)
        return _safe_scrub(fallback) or fallback


# ── service ──────────────────────────────────────────────────────────────────

class YearEndLetterService:
    """Annual Premium PDF. Owner-download only — no share surface."""

    def generate_for_user(self, user_id: int,
                          target_year: int | None = None) -> dict[str, Any]:
        user = db.session.get(User, user_id)
        if not user:
            raise ValueError(f"user {user_id} not found")

        today = date.today()
        # Default: the year that just closed. If called mid-year via the
        # admin trigger, honour the override.
        target_year = target_year or (today.year if today.month >= 12 else today.year - 1)
        start, end = _year_bounds(target_year)

        scored = _score_year_trades(user_id, start, end)
        rated = [s for s in scored if s["return_pct"] is not None]
        wins = sum(1 for s in rated if s["return_pct"] > 0)
        win_rate = round(wins / len(rated) * 100, 1) if rated else None

        # YTD portfolio return — equal-weighted mean of realised trade returns.
        # Prefer this over % of market-value to stay share-safe (no absolute
        # $-amounts leak in case the caller ever renders to an aggregate).
        if rated:
            ytd = round(sum(s["return_pct"] for s in rated) / len(rated), 2)
        else:
            ytd = None

        bench = _benchmark_ytd_pct(target_year)
        alpha = None
        if ytd is not None and bench is not None:
            alpha = round(ytd - bench, 2)

        # Current book MV — shown only to the owner in the PDF.
        positions = Position.query.filter_by(user_id=user_id).all()
        closing_value = 0.0
        for p in positions:
            shares = float(p.shares or 0)
            if shares <= 0:
                continue
            px = _safe_price(p.ticker) or float(p.avg_cost or 0)
            closing_value += shares * px
        closing_value = round(closing_value, 2) if closing_value > 0 else None

        # Opening value — approximate from first Position.added_at or from
        # the prior year's aggregate trade flow. Best-effort; the template
        # hides the row when None.
        opening_value = None
        try:
            total_buys = 0.0
            total_sells = 0.0
            for t in (TradeHistory.query
                      .filter(TradeHistory.user_id == user_id)
                      .all()):
                if not t.traded_at or t.traded_at.date() >= start:
                    continue
                val = float(t.total_value or 0)
                if (t.action or "").upper() == "BUY":
                    total_buys += val
                elif (t.action or "").upper() == "SELL":
                    total_sells += val
            approx = total_buys - total_sells
            if approx > 0:
                opening_value = round(approx, 2)
        except Exception as exc:
            logger.debug("opening-value approx failed: %s", exc)

        sectors = _sector_contribution(scored)
        best = sorted(rated, key=lambda s: -s["return_pct"])[:3]
        worst = sorted(rated, key=lambda s: s["return_pct"])[:3]

        profile = (
            InvestmentProfile.query.filter_by(user_id=user_id).first()
        )
        risk_p, realized, score, notes = _consistency(profile, scored)

        partial = {
            "year": target_year,
            "ytd_return_pct": ytd,
            "benchmark_pct": bench,
            "best_decisions": best,
            "worst_decisions": worst,
        }
        letter = _shareholder_letter(partial)

        ctx = YearEndContext(
            user_id=user_id,
            user_name=user.name or user.email.split("@")[0],
            year=target_year,
            period_start=start,
            period_end=end,
            generated_at=datetime.now(timezone.utc).replace(tzinfo=None),
            opening_value=opening_value,
            closing_value=closing_value,
            ytd_return_pct=ytd,
            benchmark_pct=bench,
            alpha_pct=alpha,
            total_trades=len(scored),
            win_rate_pct=win_rate,
            sector_contribution=sectors,
            best_decisions=best,
            worst_decisions=worst,
            risk_profile=risk_p,
            realized_style=realized,
            consistency_score=score,
            consistency_notes=notes,
            watch_items=_watch_items(target_year),
            shareholder_letter=letter,
            disclaimer=(
                "정보 제공 목적이며 투자 권유가 아닙니다. "
                "투자 판단은 본인 책임입니다."
            ),
        )
        return ctx.to_dict()

    # ── v3 design shape (CEO redesign 2026-04-30) ──────────────────────────

    _NOT_CLAIMED_DEFAULT: list[str] = [
        "다음 해 시장 전망 또는 종목 전망.",
        "복제 가능한 청사진 또는 매매 전략.",
        "투자자문 또는 일임 서비스.",
        "관찰 품질의 미래 보장.",
        "세무 또는 법률 자문.",
    ]

    _PULLQUOTE_DEFAULT = (
        "한 해는 도래한 것이 아니라 작은 결정들로 만들어졌습니다. "
        "대부분 평범했고, 몇 개는 후회되었으며, 어떤 것도 예측되지 않았습니다."
    )

    def _to_v3_shape(self, data: dict[str, Any]) -> dict[str, Any]:
        """Map generate_for_user(...) onto the v3 4-page Premium shape.

        Mirrors the editorial Buffett-letter cadence used elsewhere in v3 set
        (cover · letter · year recap · watch + colophon). Empty fields fall
        back to em-dash; service stays observational only — no directives.
        """
        year = data.get("year") or "—"
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

        ytd = data.get("ytd_return_pct")
        bench = data.get("benchmark_pct")
        alpha = data.get("alpha_pct")
        win = data.get("win_rate_pct")
        trades = data.get("total_trades")

        sectors_raw = data.get("sector_contribution") or []
        sector_rows: list[dict[str, Any]] = []
        for s in sectors_raw[:8]:
            avg = s.get("avg_return_pct")
            sector_rows.append({
                "sector":      s.get("sector") or "—",
                "trades":      s.get("trade_count") or 0,
                "avg_return":  _pct(avg),
                "tone":        _tone(avg),
            })

        def _decision_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
            out = []
            for r in rows[:3]:
                ret = r.get("return_pct")
                out.append({
                    "ticker":    r.get("ticker") or "—",
                    "name":      r.get("name") or r.get("ticker") or "—",
                    "buy_date":  r.get("buy_date") or "—",
                    "shares":    r.get("shares") or 0,
                    "buy_price": r.get("buy_price"),
                    "sell_price": r.get("sell_price"),
                    "outcome":   r.get("outcome") or "—",
                    "return":    _pct(ret),
                    "tone":      _tone(ret),
                })
            return out

        watch_items = []
        for w in (data.get("watch_items") or [])[:6]:
            watch_items.append({
                "date":  w.get("date") or "—",
                "label": w.get("label") or "—",
            })

        letter_paragraphs = data.get("letter_paragraphs") or []
        if not letter_paragraphs and data.get("shareholder_letter"):
            letter_paragraphs = [
                p.strip() for p in str(data["shareholder_letter"]).split("\n\n")
                if p.strip()
            ]

        risk_p = data.get("risk_profile") or "—"
        realized = data.get("realized_style") or "—"
        score = data.get("consistency_score")
        consistency_label = (
            f"{score}/100" if isinstance(score, (int, float)) else "—"
        )

        return {
            "doc":             f"Year-End · {year}",
            "doc_short":       f"Year-End · {year}",
            "cover_year":      str(year),
            "cover_title":     f"{year}년",
            "issued":          f"Issued · {as_of_label}",
            "kpi_pnl_label":   "Return · YTD",
            "kpi_pnl_value":   _pct(ytd),
            "kpi_pnl_tone":    _tone(ytd),
            "kpi_bench_label": "Benchmark · YTD",
            "kpi_bench_value": _pct(bench),
            "kpi_bench_tone":  _tone(bench),
            "kpi_alpha_label": "Alpha",
            "kpi_alpha_value": _pct(alpha),
            "kpi_alpha_tone":  _tone(alpha),
            "kpi_winrate_label": "Win Rate",
            "kpi_winrate_value": _pct(win, signed=False) if win is not None else "—",
            "kpi_winrate_tone":  "neutral",
            "trades_total":      trades if trades is not None else "—",
            "pullquote":         self._PULLQUOTE_DEFAULT,
            "letter_paragraphs": letter_paragraphs,
            "sector_rows":       sector_rows,
            "best_decisions":    _decision_rows(data.get("best_decisions") or []),
            "worst_decisions":   _decision_rows(data.get("worst_decisions") or []),
            "consistency_notes": data.get("consistency_notes") or "",
            "risk_profile":      risk_p,
            "realized_style":    realized,
            "consistency_label": consistency_label,
            "watch_items":       watch_items,
            "not_claimed":       list(self._NOT_CLAIMED_DEFAULT),
        }

    # ── render ──────────────────────────────────────────────────────────────

    def _resolve_persona(self, data: dict[str, Any]) -> str:
        """Resolve persona for the year-end letter — same contract as
        weekly_memo / quarterly_self_report. Falls back to balanced when
        the user has no InvestmentProfile or experience_level=beginner
        gates the persona to beginner."""
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
            profile = InvestmentProfile.query.filter_by(user_id=user_id).first()
            return resolve_persona(profile) if profile else DEFAULT_PERSONA
        except Exception as exc:
            logger.debug("year_end_letter persona resolution failed: %s", exc)
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
            tpl = env.get_template("year_end_letter.html")
            html = tpl.render(**ctx)
        except Exception as exc:
            logger.warning("year_end_letter template render failed: %s", exc)
            return self._fallback_html(data)
        scrubbed = _safe_scrub(html) or html
        return scrubbed

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
            logger.error("WeasyPrint year_end_letter render failed: %s", exc)
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
<h1>{escape(str(data.get('year','')))} Year-End Letter — {escape(data.get('user_name',''))}</h1>
<p>{escape(data.get('shareholder_letter',''))}</p>
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
        subject = "PivoxQuant Year-End Investor Letter — for you only"

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
                        FileName(f"year_end_letter_{user.id}.pdf"),
                        FileType("application/pdf"),
                        Disposition("attachment"),
                    )
                    mail.attachment = att
                SendGridAPIClient(sg_key).send(mail)
                return True
            except Exception as exc:
                logger.error("SendGrid year_end_letter send failed for user %s: %s",
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
                                       filename=f"year_end_letter_{user.id}.pdf")
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
                logger.error("SMTP year_end_letter send failed for user %s: %s",
                             user.id, exc)
                return False

        return False

    # ── persist + orchestrate ───────────────────────────────────────────────

    def _persist(self, user_id: int, data: dict[str, Any],
                 pdf_bytes: Optional[bytes], sent: bool) -> Artifact:
        title = f"Year-End Letter — {data['year']}"
        pdf_path: Optional[str] = None
        if pdf_bytes:
            try:
                base = _storage_dir() / str(user_id)
                base.mkdir(parents=True, exist_ok=True)
                path = base / f"{data['year']}.pdf"
                path.write_bytes(pdf_bytes)
                pdf_path = str(path)
            except Exception as exc:
                logger.warning("year_end_letter PDF write failed for user %s: %s",
                               user_id, exc)

        artefact = (
            Artifact.query
            .filter_by(user_id=user_id, type="year_end_letter", title=title)
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
                type="year_end_letter",
                title=title,
                data_json=data,
                pdf_path=pdf_path,
                sent_at=datetime.now(timezone.utc).replace(tzinfo=None) if sent else None,
            )
            db.session.add(artefact)
        db.session.commit()
        return artefact

    def run_for_user(self, user: User,
                     target_year: int | None = None,
                     *, send: bool = True) -> Optional[Artifact]:
        trades = TradeHistory.query.filter_by(user_id=user.id).count()
        if trades == 0:
            logger.info("skipping year_end_letter for user %s — no trades", user.id)
            return None

        data = self.generate_for_user(user.id, target_year=target_year)
        pdf_bytes = self.render_pdf(data)
        html_body = self.render_html(data)

        sent = False
        if send:
            try:
                sent = self.send_email(user, pdf_bytes, html_body)
            except Exception as exc:
                logger.error("year_end_letter send raised for user %s: %s",
                             user.id, exc)
                sent = False
        return self._persist(user.id, data, pdf_bytes, sent)

    def run_annual(self, target_year: int | None = None) -> dict[str, Any]:
        """Cron target — 12/31 10:00 KST. Premium users only."""
        users = (
            User.query
            .filter(User.subscription_tier.in_(list(_PAID_TIERS)))
            .all()
        )

        successes = failures = skipped = 0
        for user in users:
            try:
                result = self.run_for_user(user, target_year=target_year)
                if result is None:
                    skipped += 1
                else:
                    successes += 1
            except Exception as exc:
                db.session.rollback()
                failures += 1
                logger.error("year_end_letter failed for user %s: %s",
                             user.id, exc)

        summary = {
            "target_year": target_year or (date.today().year),
            "attempted":   len(users),
            "success":     successes,
            "failed":      failures,
            "skipped":     skipped,
        }
        logger.info("year_end_letter annual run: %s", summary)
        return summary
