"""Due-Diligence Checklist — T+3 post-entry safety email (Pro+).

Why T+3, not T+0?
-----------------
Delivering a *checklist* at the moment of purchase creates legal risk
(자본시장법 §6): a checklist at point-of-trade implicitly suggests
"did you consider X before buying?" — which a regulator can frame as
advising a buy/sell decision. PivoxQuant instead waits 3 trading days
*after* the user has already entered the position, then prompts a
self-recorded Y/N review. No AI judgement is persisted — the artefact
records only what the user confirms they checked.

Entry points
------------
    DDChecklistService().pending_for_user(user_id)         → list[dict]
    DDChecklistService().submit(user_id, position_id, ...) → PositionDDCheck
    DDChecklistService().generate_email_for_user(user_id)  → list[dict]
    DDChecklistService().render_html(data)                 → str
    DDChecklistService().run_daily()                       → summary dict

Scheduler semantics
-------------------
- Daily at 08:00 KST (same cron hour as KPI; different job id).
- For every Pro+ user, find positions whose `added_at` was EXACTLY 3
  calendar days ago (window [T-3d, T-2d)) AND have no `PositionDDCheck`
  row yet. Email a single-shot prompt per position.
- Idempotency is guaranteed by the (one-row-per-position) DDCheck table:
  a second firing will simply find a row and skip.
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from extensions import db
from models import Artifact, Position, PositionDDCheck, User
from services.legal_filter import detect_prohibited, safe_scrub

logger = logging.getLogger(__name__)


_TEMPLATE_DIR = Path(__file__).parent / "templates"
# Shared set so premium_plus / founding_lifetime are never silently dropped.
from ._tiers import PAID_TIERS_PRO_AND_UP as _PAID_TIERS  # noqa: E402
from services.artifacts._i18n import localize_ctx, resolve_locale  # Wave F i18n
# Pending window: `added_at` in [now - (N+1)d, now - Nd)
_PENDING_LAG_DAYS = 3


# ── lazy deps ────────────────────────────────────────────────────────────────

def _try_import_jinja():
    try:
        from jinja2 import Environment, FileSystemLoader, select_autoescape
        return Environment, FileSystemLoader, select_autoescape
    except Exception as exc:  # pragma: no cover
        logger.warning("Jinja2 unavailable (%s).", exc)
        return None, None, None


# ── service ──────────────────────────────────────────────────────────────────

class DDChecklistService:
    """Post-entry T+3 Y/N checklist. No recommendation surface."""

    # ── queries ─────────────────────────────────────────────────────────────

    def pending_for_user(self, user_id: int) -> list[dict[str, Any]]:
        """Positions that are T+3 or older and still unchecked.

        Used both by the email trigger path (`run_daily`) and by the
        in-app `/pending` endpoint so the user can see the checklist in
        the web UI as well as via email.
        """
        cutoff_new = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=_PENDING_LAG_DAYS)
        try:
            positions = (
                Position.query
                .filter(Position.user_id == user_id,
                        Position.added_at <= cutoff_new)
                .all()
            )
        except Exception as exc:
            logger.debug("pending positions query failed for user %s: %s",
                         user_id, exc)
            return []

        if not positions:
            return []

        pos_ids = [p.id for p in positions]
        try:
            existing_rows = (
                PositionDDCheck.query
                .filter(PositionDDCheck.position_id.in_(pos_ids))
                .all()
            )
        except Exception:
            existing_rows = []
        done_pos_ids = {r.position_id for r in existing_rows}

        pending: list[dict[str, Any]] = []
        for p in positions:
            if p.id in done_pos_ids:
                continue
            pending.append({
                "position_id":  p.id,
                "ticker":       p.ticker,
                "shares":       float(p.shares or 0),
                "avg_cost":     float(p.avg_cost or 0),
                "added_at":     p.added_at.isoformat() + "Z" if p.added_at else None,
                "days_since":   (datetime.now(timezone.utc).replace(tzinfo=None)
                                 - p.added_at).days if p.added_at else None,
            })
        return pending

    def submit(self, user_id: int, position_id: int, *,
               financials: bool, moat: bool, management: bool,
               valuation: bool, risks: bool,
               note: str | None = None) -> PositionDDCheck:
        """UPSERT a DDCheck row. Returns the persisted model.

        Verifies the position belongs to the caller before writing —
        otherwise raises PermissionError so the route returns 403.
        """
        position = db.session.get(Position, position_id)
        if not position:
            raise LookupError(f"position {position_id} not found")
        if position.user_id != user_id:
            raise PermissionError("position does not belong to user")

        row = (
            PositionDDCheck.query
            .filter_by(position_id=position_id)
            .first()
        )
        if row is None:
            row = PositionDDCheck(
                user_id=user_id,
                position_id=position_id,
            )
            db.session.add(row)

        row.financials_checked = bool(financials)
        row.moat_checked = bool(moat)
        row.management_checked = bool(management)
        row.valuation_checked = bool(valuation)
        row.risks_checked = bool(risks)
        if note is not None:
            row.note = str(note)[:500]

        db.session.commit()
        return row

    # ── v3 design shape (CEO redesign 2026-04-30) ──────────────────────────

    _SELF_REVIEW_QUESTIONS: list[dict[str, str]] = [
        {"key": "financials",  "label": "재무 상태",
         "prompt": "최근 분기 손익·현금흐름·부채 구조를 직접 확인했는가?"},
        {"key": "moat",        "label": "경제적 해자",
         "prompt": "이 회사가 경쟁사 대비 가지는 지속 가능한 강점을 한 줄로 적을 수 있는가?"},
        {"key": "management",  "label": "경영진",
         "prompt": "CEO/CFO 최근 12개월 행적과 자본 배치 결정을 확인했는가?"},
        {"key": "valuation",   "label": "밸류에이션",
         "prompt": "현재 가격이 적정한지 본인 기준 (PER/PSR/FCF 멀티플 등)으로 검증했는가?"},
        {"key": "risks",       "label": "리스크",
         "prompt": "투자 thesis가 깨지는 시나리오 3가지를 미리 적어두었는가?"},
    ]

    _NOT_CLAIMED: list[str] = [
        "본 체크리스트는 매수·매도 권유가 아닙니다.",
        "본 문서는 자동 생성된 자기 점검 프롬프트이며, 종목 분석이 아닙니다.",
        "5개 질문은 가이드일 뿐 종목별 깊이 있는 DD를 대체하지 않습니다.",
        "제공된 가격·수량은 본인이 입력한 데이터를 그대로 표시한 것입니다.",
    ]

    def _ai_reflection(self, pending: list[dict[str, Any]]) -> str:
        """One-paragraph Buffett-tone self-review reflection.

        Descriptive only — no recommendations. Falls back to a deterministic
        sentence when Claude Haiku is unavailable. Routed through legal_filter.
        """
        n = len(pending)
        tickers = ", ".join((p.get("ticker") or "—") for p in pending[:5])
        days_max = max((p.get("days_since") or 0 for p in pending), default=0)

        fallback = (
            f"이번 점검에는 {n}개 포지션이 올라와 있습니다. "
            f"가장 오래된 항목은 매수 후 {days_max}일이 지났습니다. "
            "체크리스트는 수익을 보장하지 않습니다 — "
            "다만 매수 직후의 흥분이 잦아든 시점에서 본인의 thesis를 다시 읽는 것은 "
            "기록을 남기는 가장 단순한 방법입니다. 답이 'No' 인 항목은 thesis가 약해진 "
            "지점입니다. 결정의 주체는 귀하 본인입니다."
        )

        try:
            import ai_service  # type: ignore
            svc_ = getattr(ai_service, "ai_service", None) or ai_service.AIService()
            if not getattr(svc_, "available", False):
                return safe_scrub(fallback, context="dd_checklist") or fallback
            prompt = (
                "아래는 한 투자자가 매수한 지 3일 이상 지난 본인 포지션 목록이다. "
                "Warren Buffett 의 주주 서한 톤(겸손·장기·절제)으로 1 문단(3-4 문장, "
                "한국어)의 '체크리스트 자기 점검 권유 글' 을 작성하라.\n"
                "\n"
                "**자본시장법 §6 / §101 회피 규칙**\n"
                "- 시장 전망/의견/예측 금지. 종목에 대한 견해 일절 금지.\n"
                "- 사용자 본인 매수 기록만 회고. 다른 종목 언급 금지.\n"
                "- 추천/매수/매도/조언/목표가/예측/유망/주목 같은 단어 금지.\n"
                "- '귀하' 또는 '당신'으로 독자를 지칭.\n"
                "- 5가지 질문 (재무/해자/경영진/밸류에이션/리스크) 자체에 대한 답은 하지 말 것 — "
                "  사용자가 직접 답하도록 권유만.\n"
                "\n"
                f"점검 대상 포지션: {tickers}\n"
                f"포지션 수: {n}, 가장 오래된 매수 후 일수: {days_max}\n"
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
            scrubbed = safe_scrub(text, context="dd_checklist") or text
            return (scrubbed[:1200] if scrubbed else fallback) or fallback
        except Exception as exc:
            logger.debug("dd_checklist AI reflection failed: %s", exc)
            return safe_scrub(fallback, context="dd_checklist") or fallback

    def _to_v3_shape(self, data: dict[str, Any]) -> dict[str, Any]:
        """Map run_for_user(...) onto the v3 2-page Pro design shape.

        Service produces a multi-position T+3 pending list (matches
        DDCheck table semantics). v3 shape: cover KPIs + positions table +
        5-question self-review grid + AI reflection + watch / colophon.

        Empty fields fall back to em-dash. No directive vocabulary.
        """
        pending = data.get("pending") or []
        as_of = data.get("as_of") or "—"
        positions: list[dict[str, Any]] = []
        for p in pending[:12]:
            shares = p.get("shares") or 0
            avg = p.get("avg_cost") or 0
            try:
                cost = float(shares) * float(avg)
            except (TypeError, ValueError):
                cost = 0.0
            positions.append({
                "ticker":     p.get("ticker") or "—",
                "shares":     f"{float(shares):.2f}" if shares else "—",
                "avg_cost":   f"{float(avg):.2f}" if avg else "—",
                "cost_basis": f"${cost:,.0f}" if cost > 0 else "—",
                "added_at":   (p.get("added_at") or "—").split("T")[0],
                "days_since": p.get("days_since") if p.get("days_since") is not None else "—",
            })

        days_max = max((p.get("days_since") or 0 for p in pending), default=0)
        days_avg_int = (
            round(sum((p.get("days_since") or 0) for p in pending) / len(pending))
            if pending else 0
        )

        return {
            "doc":           f"DD Checklist · {as_of}",
            "doc_short":     f"DD · {as_of}",
            "issued":        f"Issued · {as_of}",
            "kpi_pending":   str(len(pending)) if pending else "—",
            "kpi_oldest":    f"{days_max}일" if days_max else "—",
            "kpi_avg_age":   f"{days_avg_int}일" if days_avg_int else "—",
            "kpi_questions": "5",
            "positions":     positions,
            "questions":     list(self._SELF_REVIEW_QUESTIONS),
            "reflection":    self._ai_reflection(pending),
            "pullquote":     "체크리스트는 수익을 보장하지 않습니다. 다만 매수 직후의 흥분이 잦아든 시점에서 본인의 thesis를 다시 읽도록 권유합니다.",
            "not_claimed":   list(self._NOT_CLAIMED),
        }

    # ── render / email ──────────────────────────────────────────────────────

    def _resolve_persona(self, data: dict[str, Any]) -> str:
        """Same persona contract as weekly_memo / year_end_letter."""
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
            logger.debug("dd_checklist persona resolution failed: %s", exc)
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
                tpl = env.get_template("dd_checklist.html")
                ctx = localize_ctx(ctx, resolve_locale(user_id=ctx.get('user_id'), data=data))
                html = tpl.render(**ctx)
            except Exception as exc:
                logger.warning("dd_checklist template render failed: %s", exc)
                html = self._fallback_html(data)
        scrubbed = safe_scrub(html, context="dd_checklist") or html
        _prohibited = detect_prohibited(scrubbed)
        if _prohibited:
            logger.warning("legal_filter fail: dd_checklist (%s)", _prohibited)
        return scrubbed

    def render_html(self, data: dict[str, Any]) -> str:
        return self.render_pdf_html(data)

    def render_email_html(self, data: dict[str, Any]) -> str:
        """Render the email-specific body — separate from the PDF template.

        2026-05-02: the PDF template references @font-face with file:///app
        absolute paths (WeasyPrint convention). When that html was reused
        as the email body the fonts failed to resolve in mail clients and
        the result rendered with browser defaults — users described it as
        "코드처럼 날아옴". The email template uses inline styles + a
        system font stack only so every client renders correctly, and
        links back into the in-app preview shell rather than embedding
        the full layout.
        """
        env = self._jinja_env()
        view_url = (
            os.environ.get("FRONTEND_URL", "https://www.pivoxquant.com").rstrip("/")
            + "/reports/preview/dd-checklist"
        )
        ctx = dict(data)
        ctx["view_url"] = view_url
        ctx["subject"] = f"오늘 점검할 {len(data.get('pending', []))}개 종목 — DD Checklist"
        if env is not None:
            try:
                tpl = env.get_template("dd_checklist_email.html")
                ctx = localize_ctx(ctx, resolve_locale(user_id=ctx.get('user_id'), data=data))
                html = tpl.render(**ctx)
                return safe_scrub(html, context="dd_checklist_email") or html
            except Exception as exc:
                logger.warning("dd_checklist email template render failed: %s", exc)
        # Plain fallback — still readable in any client.
        from html import escape
        rows = "".join(
            f"<tr><td style='padding:8px 0;font-family:monospace;color:#B8956A;'>"
            f"{escape(p['ticker'])}</td>"
            f"<td style='padding:8px 0;'>{p['shares']} shares</td>"
            f"<td style='padding:8px 0;text-align:right;color:#888;'>"
            f"+{p['days_since']}d</td></tr>"
            for p in data.get("pending", [])[:8]
        )
        return f"""<!doctype html>
<html><body style="font-family:-apple-system,Segoe UI,sans-serif;background:#0A0A0A;color:#F5F0E8;padding:24px;">
<h2 style="font-family:Georgia,serif;color:#B8956A;">오늘 점검할 {len(data.get('pending', []))}개 종목</h2>
<table style="width:100%;border-collapse:collapse;">{rows}</table>
<p style="margin-top:24px;"><a href="{escape(view_url)}" style="color:#B8956A;">앱에서 자세히 보기 ›</a></p>
<p style="font-size:11px;color:#666;margin-top:24px;">{escape(data.get('disclaimer',''))}</p>
</body></html>"""

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
        items = "".join(
            f"<li>{escape(p['ticker'])} — added {escape(p.get('added_at','') or '')}</li>"
            for p in data.get("pending", [])
        )
        return f"""<!doctype html><html><body>
<h1>Due-Diligence Checklist — {escape(data.get('user_name',''))}</h1>
<p>최근 추가 후 3일이 지난 포지션 {len(data.get('pending', []))}건:</p>
<ul>{items}</ul>
<p><em>{escape(data.get('disclaimer',''))}</em></p>
</body></html>"""

    def send_email(self, user: User, html_body: str, pending_count: int) -> bool:
        """Phase 7 — delegate to :class:`EmailSender`. Pre-flight gates
        ``pending_count <= 0`` (no checklist items → no email) and the
        sender then handles opt-out + transport.
        """
        if pending_count <= 0:
            return False

        from services.email import EmailSender, EmailCategory

        sender = EmailSender()
        ok = sender.send(
            user,
            email_category=EmailCategory.INFORMATION,
            subject=f"PivoxQuant DD Checklist — {pending_count}개 포지션 점검",
            html_body=html_body,
            from_env_var="WEEKLY_MEMO_FROM_EMAIL",
            from_default="reports@pivoxquant.com",
        )
        # Stash the SendGrid X-Message-Id so _persist_artefact can write it
        # onto the Artifact row (webhook bounce/open mapping — 정통망법 §50).
        self._last_message_id = getattr(sender, "last_message_id", None)
        return ok

    # ── persist + orchestrate ───────────────────────────────────────────────

    def _persist_artefact(self, user_id: int, data: dict[str, Any],
                          sent: bool) -> Artifact:
        title = f"DD Checklist — {data['as_of']}"
        artefact = (
            Artifact.query
            .filter_by(user_id=user_id, type="dd_checklist", title=title)
            .first()
        )
        if artefact:
            artefact.data_json = data
            if sent and not artefact.sent_at:
                artefact.sent_at = datetime.now(timezone.utc).replace(tzinfo=None)
        else:
            artefact = Artifact(
                user_id=user_id,
                type="dd_checklist",
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

    def run_for_user(self, user: User, *, send: bool = True
                     ) -> Optional[Artifact]:
        pending = self.pending_for_user(user.id)
        if not pending:
            return None
        data = {
            "user_id":     user.id,
            "user_name":   user.name or user.email.split("@")[0],
            "as_of":       date.today().isoformat(),
            "generated_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + "Z",
            "pending":     pending,
            "disclaimer":  "정보 제공 목적이며 투자 권유가 아닙니다. 투자 판단은 본인 책임입니다.",
        }
        # 2026-05-02: use the email-specific template (inline styles +
        # system font stack + CTA link). The PDF body keeps the heavy
        # WeasyPrint @font-face setup; emails deserve their own minimal
        # body or they render as plain code in Gmail/Outlook.
        email_html = self.render_email_html(data)
        sent = False
        if send:
            try:
                sent = self.send_email(user, email_html, len(pending))
            except Exception as exc:
                logger.error("dd send raised for user %s: %s", user.id, exc)
                sent = False
        return self._persist_artefact(user.id, data, sent)

    def run_daily(self) -> dict[str, Any]:
        """Cron — 08:00 KST daily. Pro+ only."""
        from services.artifacts import iter_users_chunked

        users = (
            User.query
            .filter(User.subscription_tier.in_(list(_PAID_TIERS)))
            .all()
        )

        successes = failures = skipped = 0
        for user in iter_users_chunked(users, label="dd_checklist.daily"):
            try:
                result = self.run_for_user(user)
                if result is None:
                    skipped += 1
                else:
                    successes += 1
            except Exception as exc:
                db.session.rollback()
                failures += 1
                logger.error("dd_checklist failed for user %s: %s", user.id, exc)

        summary = {
            "date":      date.today().isoformat(),
            "attempted": len(users),
            "success":   successes,
            "failed":    failures,
            "skipped":   skipped,
        }
        logger.info("dd checklist daily run: %s", summary)
        return summary
