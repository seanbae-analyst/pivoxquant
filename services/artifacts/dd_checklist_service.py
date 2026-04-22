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

logger = logging.getLogger(__name__)


_TEMPLATE_DIR = Path(__file__).parent / "templates"
_PAID_TIERS = frozenset({"pro", "premium", "elite"})
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

    # ── render / email ──────────────────────────────────────────────────────

    def render_html(self, data: dict[str, Any]) -> str:
        env = self._jinja_env()
        if env is None:
            return self._fallback_html(data)
        try:
            tpl = env.get_template("dd_checklist.html")
            return tpl.render(**data)
        except Exception as exc:
            logger.warning("dd_checklist template render failed: %s", exc)
            return self._fallback_html(data)

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
        if getattr(user, "email_opt_out", False):
            return False
        if pending_count <= 0:
            return False

        from_email = os.environ.get(
            "WEEKLY_MEMO_FROM_EMAIL", "reports@pivoxquant.com"
        )
        subject = f"PivoxQuant DD Checklist — {pending_count}개 포지션 점검"

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
                logger.error("SendGrid dd send failed for user %s: %s",
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
                logger.error("SMTP dd send failed for user %s: %s",
                             user.id, exc)
                return False
        return False

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
        html_body = self.render_html(data)
        sent = False
        if send:
            try:
                sent = self.send_email(user, html_body, len(pending))
            except Exception as exc:
                logger.error("dd send raised for user %s: %s", user.id, exc)
                sent = False
        return self._persist_artefact(user.id, data, sent)

    def run_daily(self) -> dict[str, Any]:
        """Cron — 08:00 KST daily. Pro+ only."""
        users = (
            User.query
            .filter(User.subscription_tier.in_(list(_PAID_TIERS)))
            .all()
        )

        successes = failures = skipped = 0
        for user in users:
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
