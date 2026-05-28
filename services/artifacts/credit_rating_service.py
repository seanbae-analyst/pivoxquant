"""Credit Rating Self-Assessment — monthly 1-page HTML email (Pro+).

Entry points
------------
    CreditRatingService().generate_for_user(user_id, as_of=None) → data dict
    CreditRatingService().render_html(data)                      → str
    CreditRatingService().run_for_user(user, ...)                → Artifact
    CreditRatingService().run_monthly(as_of=None)                → summary

Scope
-----
Scores the user's portfolio on five deterministic factors (0–100 each),
then weighted-averages → letter grade (AAA–B). Compares to the previous
month to surface upgrade/downgrade.

Factors & weights
-----------------
    Diversification      — 25%  (sector/ticker count, top-weight penalty)
    Liquidity            — 20%  (avg daily $volume, size-weighted)
    Risk-adjusted Return — 25%  (Sharpe 3m)
    Drawdown Discipline  — 20%  (Max DD, 3m)
    Cash Buffer          — 10%  (cash / total assets)

Grade mapping
-------------
    90+ AAA   80–89 AA   70–79 A   60–69 BBB   50–59 BB   <50 B

Compliance
----------
*   "자체 신용등급"이라는 표현만 사용 (S&P/Moody's 등 공식 기관 평가 아님).
*   모든 팩터는 사실 기반 계산 — AI 호출/판단 없음.
*   `_disclaimer.html` include.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

from extensions import db
from models import Artifact, Position, User
from services.legal_filter import detect_prohibited, safe_scrub

logger = logging.getLogger(__name__)


_TEMPLATE_DIR = Path(__file__).parent / "templates"
# Shared set so premium_plus / founding_lifetime are never silently dropped.
from ._tiers import PAID_TIERS_PRO_AND_UP as _PAID_TIERS  # noqa: E402
from services.artifacts._i18n import localize_ctx, resolve_locale  # Wave F i18n

_GRADE_THRESHOLDS: list[tuple[int, str]] = [
    (90, "AAA"),
    (80, "AA"),
    (70, "A"),
    (60, "BBB"),
    (50, "BB"),
    (0,  "B"),
]

_FACTOR_WEIGHTS = {
    "diversification":       0.25,
    "liquidity":             0.20,
    "risk_adjusted_return":  0.25,
    "drawdown_discipline":   0.20,
    "cash_buffer":           0.10,
}


# ── lazy deps ────────────────────────────────────────────────────────────────

def _try_import_jinja():
    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape
        return Environment, FileSystemLoader, select_autoescape
    except Exception as exc:  # pragma: no cover
        logger.warning("Jinja2 unavailable (%s).", exc)
        return None, None, None


def _safe_history(ticker: str, period: str = "3mo"):
    try:
        from services.container import fetcher
        return fetcher.get_price_history(ticker, period=period)
    except Exception as exc:
        logger.debug("history fetch failed for %s: %s", ticker, exc)
        return None


def _grade_from_score(score: float) -> str:
    for threshold, letter in _GRADE_THRESHOLDS:
        if score >= threshold:
            return letter
    return "B"


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


# ── data ─────────────────────────────────────────────────────────────────────

@dataclass
class RatingContext:
    user_id:              int
    user_name:            str
    as_of:                date
    generated_at:         datetime
    # Factor scores 0–100
    diversification:      Optional[float]
    liquidity:            Optional[float]
    risk_adjusted_return: Optional[float]
    drawdown_discipline:  Optional[float]
    cash_buffer:          Optional[float]
    # Aggregate
    composite_score:      Optional[float]
    grade:                str
    prev_grade:           Optional[str]     # previous month, if any
    change:               str               # "upgrade" / "downgrade" / "same" / "new"
    factor_details:       list[dict[str, Any]]
    position_count:       int
    disclaimer:           str

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id":              self.user_id,
            "user_name":            self.user_name,
            "as_of":                self.as_of.isoformat(),
            "generated_at":         self.generated_at.isoformat() + "Z",
            "diversification":      self.diversification,
            "liquidity":            self.liquidity,
            "risk_adjusted_return": self.risk_adjusted_return,
            "drawdown_discipline":  self.drawdown_discipline,
            "cash_buffer":          self.cash_buffer,
            "composite_score":      self.composite_score,
            "grade":                self.grade,
            "prev_grade":           self.prev_grade,
            "change":               self.change,
            "factor_details":       self.factor_details,
            "position_count":       self.position_count,
            "disclaimer":           self.disclaimer,
        }


# ── factor calculators ───────────────────────────────────────────────────────

def _diversification_score(positions: list[Position]) -> Optional[float]:
    """Scores: (a) unique ticker count (cap at 15 → 100), (b) top-1 weight
    (capped at 40%+ → 0, 10% → 100). Equal weight of the two."""
    if not positions:
        return None
    n = len(positions)
    count_score = _clamp((n / 15.0) * 100.0)
    # Top-1 weight by notional cost basis
    weights = []
    total = 0.0
    for p in positions:
        w = float(p.shares or 0) * float(p.avg_cost or 0)
        weights.append(w)
        total += w
    if total <= 0:
        return round(count_score, 1)
    top_w = max(weights) / total if weights else 0.0
    # 10%→100, 40%→0 linear
    conc_score = _clamp(100.0 - ((top_w - 0.10) / 0.30) * 100.0)
    return round((count_score + conc_score) / 2.0, 1)


def _liquidity_score(positions: list[Position]) -> Optional[float]:
    """Avg daily $volume across held tickers, size-weighted.

    >= $50M → 100; <= $500K → 0. Log-scaled between.
    """
    if not positions:
        return None
    scores: list[tuple[float, float]] = []
    for p in positions[:20]:
        hist = _safe_history(p.ticker, period="1mo")
        if hist is None:
            continue
        try:
            volumes = hist.get("Volume") if hasattr(hist, "get") else None
            closes = hist["Close"]
            if volumes is None or len(volumes) == 0 or len(closes) == 0:
                continue
            avg_dollar_vol = float(sum(v * c for v, c in zip(volumes, closes))
                                   / max(len(volumes), 1))
            if avg_dollar_vol <= 0:
                continue
            # log scale: 500K → 0, 50M → 100
            lo, hi = math.log(5e5), math.log(5e7)
            lv = math.log(avg_dollar_vol)
            s = _clamp((lv - lo) / (hi - lo) * 100.0)
            weight = float(p.shares or 0) * float(p.avg_cost or 0)
            scores.append((s, max(weight, 1.0)))
        except Exception:
            logger.debug("silent-fallback: _liquidity_score", exc_info=True)
            continue
    if not scores:
        return None
    wsum = sum(s * w for s, w in scores)
    wtot = sum(w for _, w in scores)
    return round(wsum / wtot, 1) if wtot > 0 else None


def _sharpe_and_dd(positions: list[Position]) -> tuple[Optional[float], Optional[float]]:
    """Equal-weight daily-return series over 3m; return (Sharpe, MaxDD%)."""
    if not positions:
        return None, None
    ticker_rets: list[list[float]] = []
    for p in positions[:20]:
        hist = _safe_history(p.ticker, period="3mo")
        if hist is None or "Close" not in hist:
            continue
        try:
            closes = hist["Close"].tolist()
            if len(closes) < 10:
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
            logger.debug("silent-fallback: _sharpe_and_dd", exc_info=True)
            continue
    if not ticker_rets:
        return None, None
    n = min(len(r) for r in ticker_rets)
    aligned = [r[-n:] for r in ticker_rets]
    port = [sum(r[i] for r in aligned) / len(aligned) for i in range(n)]

    if len(port) < 10:
        return None, None
    mean = sum(port) / len(port)
    var = sum((r - mean) ** 2 for r in port) / max(len(port) - 1, 1)
    std = math.sqrt(var)
    sharpe = (mean / std) * math.sqrt(252) if std > 0 else None

    # Max DD
    equity = 1.0
    peak = 1.0
    mdd = 0.0
    for r in port:
        equity *= (1.0 + r)
        if equity > peak:
            peak = equity
        dd = (equity - peak) / peak if peak > 0 else 0.0
        if dd < mdd:
            mdd = dd
    mdd_pct = mdd * 100.0

    return sharpe, mdd_pct


def _risk_adjusted_return_score(sharpe: Optional[float]) -> Optional[float]:
    """Sharpe 2+ → 100, Sharpe 0 → 50, Sharpe ≤-1 → 0. Linear clamp."""
    if sharpe is None:
        return None
    # map -1 → 0, 0 → 50, 2 → 100  (linear piecewise)
    if sharpe <= -1:
        return 0.0
    if sharpe >= 2:
        return 100.0
    if sharpe < 0:
        return round(50.0 * (sharpe + 1), 1)   # -1→0, 0→50
    return round(50.0 + 25.0 * sharpe, 1)      # 0→50, 2→100


def _drawdown_discipline_score(mdd_pct: Optional[float]) -> Optional[float]:
    """0% DD → 100; -30% or worse → 0."""
    if mdd_pct is None:
        return None
    # mdd_pct is negative
    return round(_clamp(100.0 + (mdd_pct / 30.0) * 100.0), 1)


def _cash_buffer_score(user: User, positions_mv: float) -> Optional[float]:
    cash_usd = float(getattr(user, "available_capital", 0) or 0)
    cash_krw = float(getattr(user, "available_capital_krw", 0) or 0)
    cash = cash_usd if cash_usd > 0 else cash_krw
    total = cash + (positions_mv or 0)
    if total <= 0:
        return None
    pct = cash / total
    # 0% → 40, 10% → 80, 25%+ → 100.
    if pct <= 0:
        return 40.0
    if pct >= 0.25:
        return 100.0
    if pct < 0.10:
        return round(40.0 + (pct / 0.10) * 40.0, 1)
    return round(80.0 + ((pct - 0.10) / 0.15) * 20.0, 1)


def _positions_mv(positions: list[Position]) -> float:
    total = 0.0
    for p in positions:
        try:
            total += float(p.shares or 0) * float(p.avg_cost or 0)
        except Exception:
            logger.debug("silent-fallback: _positions_mv", exc_info=True)
            continue
    return total


def _previous_grade(user_id: int, as_of: date) -> Optional[str]:
    """Most recent prior credit_rating artifact (≠ current month)."""
    current_label = f"{as_of.year}-{as_of.month:02d}"
    prev = (
        Artifact.query
        .filter(Artifact.user_id == user_id,
                Artifact.type == "credit_rating")
        .order_by(Artifact.created_at.desc())
        .limit(5)
        .all()
    )
    for a in prev:
        data = a.data_json or {}
        # Skip today's row if it exists
        if (data.get("as_of") or "").startswith(current_label):
            continue
        g = data.get("grade")
        if g:
            return str(g)
    return None


def _grade_rank(letter: str) -> int:
    order = ["B", "BB", "BBB", "A", "AA", "AAA"]
    try:
        return order.index(letter)
    except ValueError:
        return -1


# ── service ──────────────────────────────────────────────────────────────────

class CreditRatingService:
    """Monthly 1-page email — portfolio self-rating (Pro+)."""

    def generate_for_user(self, user_id: int,
                          as_of: date | None = None) -> dict[str, Any]:
        """Compute portfolio self-rating for the user.

        Legal posture (자본시장법 §101 회피, 2026-04-29):
            **사용자 보유 포트폴리오 자체에 대한 자기 신용평가 도구**다.
            보유 종목이 0 개면 ``is_empty=True`` 페이로드를 즉시 반환해
            EmptyState 로 전환된다. 계산식은 모두 사용자 보유 데이터
            기반(Position × FMP 정량 재무 지표) — 외부 종목 평가 서비스
            아님. 헤더 disclaimer 가 본 사실을 명시한다.
        """
        user = db.session.get(User, user_id)
        if not user:
            raise ValueError(f"user {user_id} not found")

        as_of = as_of or date.today()
        positions = Position.query.filter_by(user_id=user_id).all()

        # ── §101 가드: 보유 종목 0 → empty payload ────────────────────────
        if not positions:
            return {
                "is_empty":     True,
                "empty_reason": "no_positions",
                "user_id":      user_id,
                "as_of":        as_of.isoformat(),
                "message":      "보유 종목이 없습니다 — 자기 신용등급 계산 불가",
            }

        div = _diversification_score(positions)
        liq = _liquidity_score(positions)
        sharpe, mdd_pct = _sharpe_and_dd(positions)
        rar = _risk_adjusted_return_score(sharpe)
        ddd = _drawdown_discipline_score(mdd_pct)
        pmv = _positions_mv(positions)
        cash_s = _cash_buffer_score(user, pmv)

        # Composite — skip missing factors and renormalise.
        factors = {
            "diversification":       div,
            "liquidity":             liq,
            "risk_adjusted_return":  rar,
            "drawdown_discipline":   ddd,
            "cash_buffer":           cash_s,
        }
        total_w = 0.0
        score_sum = 0.0
        for name, val in factors.items():
            if val is None:
                continue
            w = _FACTOR_WEIGHTS[name]
            total_w += w
            score_sum += val * w
        composite: Optional[float] = None
        if total_w > 0:
            composite = round(score_sum / total_w, 1)

        grade = _grade_from_score(composite) if composite is not None else "B"
        prev_grade = _previous_grade(user_id, as_of)
        if prev_grade is None:
            change = "new"
        else:
            cur_rank = _grade_rank(grade)
            prev_rank = _grade_rank(prev_grade)
            if cur_rank > prev_rank:
                change = "upgrade"
            elif cur_rank < prev_rank:
                change = "downgrade"
            else:
                change = "same"

        factor_details = [
            {"name": "Diversification",      "key": "diversification",
             "score": div, "weight": _FACTOR_WEIGHTS["diversification"]},
            {"name": "Liquidity",            "key": "liquidity",
             "score": liq, "weight": _FACTOR_WEIGHTS["liquidity"]},
            {"name": "Risk-adjusted Return", "key": "risk_adjusted_return",
             "score": rar, "weight": _FACTOR_WEIGHTS["risk_adjusted_return"]},
            {"name": "Drawdown Discipline",  "key": "drawdown_discipline",
             "score": ddd, "weight": _FACTOR_WEIGHTS["drawdown_discipline"]},
            {"name": "Cash Buffer",          "key": "cash_buffer",
             "score": cash_s, "weight": _FACTOR_WEIGHTS["cash_buffer"]},
        ]

        ctx = RatingContext(
            user_id=user_id,
            user_name=user.name or user.email.split("@")[0],
            as_of=as_of,
            generated_at=datetime.now(timezone.utc).replace(tzinfo=None),
            diversification=div,
            liquidity=liq,
            risk_adjusted_return=rar,
            drawdown_discipline=ddd,
            cash_buffer=cash_s,
            composite_score=composite,
            grade=grade,
            prev_grade=prev_grade,
            change=change,
            factor_details=factor_details,
            position_count=len(positions),
            disclaimer=(
                "본 스냅샷은 사용자 본인 보유 포트폴리오에 대한 자기 점검 "
                "참고 자료이며, **신용평가가 아닙니다**. PivoxQuant 는 "
                "자본시장법상 신용평가회사가 아니며, 본 자료는 S&P · Moody's · "
                "Fitch 등 공인 신용평가기관의 등급과 무관합니다. FMP 정량 "
                "재무 데이터를 PivoxQuant 내부 점검 공식에 투입해 산출한 "
                "사용자 본인 데이터 기반 자가 점검 결과로, 본인 외 종목에 "
                "대한 평가 / 추천 / 조언이 아닙니다."
            ),
        )
        return ctx.to_dict()

    # ── v3 design shape (CEO redesign 2026-04-30) ──────────────────────────

    def _to_v3_shape(self, data: dict[str, Any]) -> dict[str, Any]:
        """Map portfolio credit *snapshot* onto v3 3-page Premium shape.

        Mirrors frontend/src/components/reports/templates/credit-rating.tsx.

        §335 회피 (2026-05-08): 본 service 는 **공인 신용평가기관이 아니다**.
        외부 agency rating(S&P / Moody's / Fitch) 공급 전까지는 자체 산정
        등급(letter grade) 을 PDF 노출 페이로드에 절대 포함하지 않는다.
        v3 shape 은 quarter label / counts / empty-state placeholder 만
        반환하며, agency rating 공급 후 별도 sprint 에서 외부 등급 노출을
        구현한다. 이전 self-rating 계산 결과는 사용자 본인 자가 점검
        용도로만 internal payload 에 남기고, PDF/HTML 노출은 차단한다.
        """
        as_of = data.get("as_of")
        as_of_label = str(as_of) if as_of else "—"
        mo = getattr(as_of, "month", 0)
        yr = getattr(as_of, "year", "—")
        quarter_label = f"Q{(mo - 1) // 3 + 1} {yr}" if mo else as_of_label[:7]

        return {
            "doc":             f"{quarter_label} · CR",
            "doc_short":       quarter_label,
            "cover_title":     quarter_label,
            "reviewed":        str(data.get("position_count") or "—"),
            "upgrades":        "—",
            "downgrades":      "—",
            "on_watch":        "—",
            "issued":          f"Issued · {as_of_label}",
            "pullquote":       "“주식이 환상을 팔 때, 채권은 진실을 말한다.” — 분기 신용 점검의 한 줄.",
            "distribution":    [],
            "changes":         [],
            "watch_primary":   None,
            "watch_secondary": [],
            "cds":             [],
            "cfo_note":        None,
        }

    # ── render ──────────────────────────────────────────────────────────────

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
            logger.debug("credit_rating persona resolution failed: %s", exc)
            return "balanced"

    def render_pdf_html(self, data: dict[str, Any]) -> str:
        env = self._jinja_env()
        if env is None:
            html = self._fallback_html(data)
        else:
            try:
                ctx = dict(data)
                from services.artifacts._name_enrich import enrich_v3_names
                ctx["v3"] = enrich_v3_names(self._to_v3_shape(data))
                ctx["persona"] = self._resolve_persona(data)
                tpl = env.get_template("credit_rating.html")
                ctx = localize_ctx(ctx, resolve_locale(user_id=ctx.get('user_id'), data=data))
                html = tpl.render(**ctx)
            except Exception as exc:
                logger.warning("credit_rating v3 render failed: %s", exc)
                html = self._fallback_html(data)
        scrubbed = safe_scrub(html, context="credit_rating") or html
        _prohibited = detect_prohibited(scrubbed)
        if _prohibited:
            logger.warning("legal_filter fail: credit_rating (%s)", _prohibited)
        return scrubbed

    def render_html(self, data: dict[str, Any]) -> str:
        return self.render_pdf_html(data)

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
        score = data.get("composite_score")
        score_str = f"{score:.1f}" if score is not None else "—"
        return f"""<!doctype html><html><body>
<h1>Credit Rating — {escape(data.get('user_name',''))}</h1>
<p>Grade: <strong>{escape(data.get('grade','—'))}</strong> ({score_str}/100)</p>
<p>Change: {escape(data.get('change','—'))}</p>
<p><em>{escape(data.get('disclaimer',''))}</em></p>
</body></html>"""

    # ── send ────────────────────────────────────────────────────────────────

    def send_email(self, user: User, html_body: str, grade: str) -> bool:
        """Phase 7 — delegate to :class:`EmailSender`. No PDF attachment;
        the credit rating is HTML-only.
        """
        from services.email import EmailSender

        sender = EmailSender()
        ok = sender.send(
            user,
            subject=f"PivoxQuant Credit Rating — {grade}",
            html_body=html_body,
            from_env_var="WEEKLY_MEMO_FROM_EMAIL",
            from_default="reports@pivoxquant.com",
        )
        # Stash the SendGrid X-Message-Id so _persist can write it onto the
        # Artifact row (webhook bounce/open mapping — 정통망법 §50).
        self._last_message_id = getattr(sender, "last_message_id", None)
        return ok

    # ── persist + orchestrate ───────────────────────────────────────────────

    def _persist(self, user_id: int, data: dict[str, Any], sent: bool) -> Artifact:
        title = f"Credit Rating — {data['as_of']}"
        artefact = (
            Artifact.query
            .filter_by(user_id=user_id, type="credit_rating", title=title)
            .first()
        )
        if artefact:
            artefact.data_json = data
            if sent and not artefact.sent_at:
                artefact.sent_at = datetime.now(timezone.utc).replace(tzinfo=None)
        else:
            artefact = Artifact(
                user_id=user_id,
                type="credit_rating",
                title=title,
                data_json=data,
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

    def run_for_user(self, user: User, as_of: date | None = None,
                     *, send: bool = True) -> Optional[Artifact]:
        # Skip empty portfolios — no positions → nothing to rate.
        if Position.query.filter_by(user_id=user.id).count() == 0:
            logger.info("skipping credit_rating for user %s — empty portfolio",
                        user.id)
            return None

        data = self.generate_for_user(user.id, as_of=as_of)
        html_body = self.render_html(data)

        sent = False
        if send:
            try:
                sent = self.send_email(user, html_body, data.get("grade", "B"))
            except Exception as exc:
                logger.error("credit_rating send raised for user %s: %s",
                             user.id, exc)
                sent = False
        return self._persist(user.id, data, sent)

    def run_monthly(self, as_of: date | None = None) -> dict[str, Any]:
        """Cron — 15th of each month 09:00 KST. Pro+ only."""
        from services.artifacts import iter_users_chunked

        as_of = as_of or date.today()

        users = (
            User.query
            .filter(User.subscription_tier.in_(list(_PAID_TIERS)))
            .all()
        )

        successes = failures = skipped = 0
        for user in iter_users_chunked(users, label="credit_rating.monthly"):
            try:
                result = self.run_for_user(user, as_of=as_of)
                if result is None:
                    skipped += 1
                else:
                    successes += 1
            except Exception as exc:
                db.session.rollback()
                failures += 1
                logger.error("credit_rating failed for user %s: %s", user.id, exc)

        summary = {
            "as_of":     as_of.isoformat(),
            "attempted": len(users),
            "success":   successes,
            "failed":    failures,
            "skipped":   skipped,
        }
        logger.info("credit_rating monthly run: %s", summary)
        return summary
