"""
services/email/retention_sequence.py — 7d/30d retention emails (MARKETING).

Wave G C-R1 (2026-05-19).

Sends two retention nudges (D+7 and D+30 after signup) to users who
explicitly opted in to the **광고성 수신** consent column
(``marketing_consent_marketing_at`` from C-S1, migration 037). Unlike
the S5 onboarding sequence (TRANSACTIONAL + INFORMATION), retention is
MARKETING category — every legal guardrail under 정통망법 §50 ① must
apply.

Hard guardrails (정통망법 §50 ① / 시행령 §61의2 / 시행령 §62)
--------------------------------------------------------------
1. **Night-time block** — 21:00 ~ 08:00 KST 발송 금지 (시행령 §61의2).
   ``is_night_kst`` is evaluated at *dispatch* time. A row that becomes
   due during night hours is left ``sent_at IS NULL`` so the next
   15-min tick after 08:00 KST picks it up — no row is silently lost.
2. **"(광고)" 표제** — 시행령 §62 ② requires the literal "(광고)" marker
   in both the subject line *and* the first line of the body. We hard-
   assert both at render time; ``SUBJECT_*`` constants in this module
   are the source of truth and the template test verifies the bodies.
3. **Sender footer 4 elements** — 시행령 §62 ① mandates four pieces of
   information in every 광고성 메일: 사업자명, 연락처, 수신거부 수단,
   동의 일시 + 출처. The templates render all four; ``test_footer_has_4_elements``
   confirms.
4. **Feature flag default OFF** — ``PIVOX_RETENTION_ENABLED`` defaults
   to ``"false"``. The whole pipeline (schedule + dispatch) is dormant
   until the lawyer's Q-S1 answer lands. Mirrors the C-S1 / C-M1 / C-S2 /
   S5 pattern.
5. **Legal-safe vocabulary** — every rendered subject + body passes
   :func:`services.legal.assert_legal_safe`. Catches accidental drift
   into "추천 / 매수 / 매도 / 조언 / coach" vocabulary that would re-
   classify a marketing nudge as 투자권유 under 자본시장법 §49.
6. **Dispatch-time consent re-check** — even though we only enqueue when
   ``marketing_consent_marketing`` was effective, a user may revoke
   between enqueue and dispatch. ``EmailSender.send(email_category=
   EmailCategory.MARKETING)`` re-evaluates the consent gate live; we
   also keep the explicit guard in ``_send_one`` so a revoke takes
   effect without depending on the EmailSender flag being on.
7. **Schedule gate** — we only enqueue when the user *already* has
   ``marketing_consent_marketing_at`` set + not revoked. Avoids growing
   the queue with rows that would always skip.

Public surface
--------------
* ``schedule_retention(user, now=None)`` — call from signup callbacks.
  Idempotent (``ScheduledEmail.enqueue`` keys off ``"u{id}:{slug}"``).
  Feature-flag-aware (no rows when off). Consent-aware (no rows for
  users without effective MARKETING consent).
* ``dispatch_retention(now=None)`` — called by
  ``scripts/nightly/email_scheduler_dispatcher.py`` every 15 min.
  Filters the queue to ``retention_*`` slugs only, runs the night gate,
  re-checks consent, renders + sends, stamps ``sent_at`` / ``skipped_reason``.
* ``retention_enabled()`` — feature-flag read. Exposed for tests + the
  dispatcher's outer short-circuit.
* ``is_night_kst(dt=None)`` — KST 21:00–08:00 predicate. Pure function,
  testable, no Flask dependency.
* ``SEQUENCE`` — canonical D+7 / D+30 spec.

Cost
----
- DB: ~2 INSERT per signup (only when consent on + flag on) + ~1 SELECT
  per 15-min tick. Zero marginal cost.
- SendGrid 100/day free + Brevo 300/day free fallback.
- 추가 비용 0원.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


# ── feature flag ─────────────────────────────────────────────────────────────


_FLAG_ENV = "PIVOX_RETENTION_ENABLED"


def retention_enabled() -> bool:
    """Return True iff the D+7/D+30 retention pipeline should run.

    Default false (variance-flag pattern). Read live on every call so
    a runtime env flip is honoured without a redeploy.
    """
    val = os.environ.get(_FLAG_ENV, "false").strip().lower()
    return val in ("true", "1", "yes", "on")


# ── KST night-time gate (정통망법 시행령 §61의2) ─────────────────────────────


KST = ZoneInfo("Asia/Seoul")

# 21:00 inclusive ─ 08:00 exclusive (KST). 시행령 §61의2 wording:
# "오후 9시부터 그 다음 날 오전 8시까지" — i.e. 21:00 is blocked, 08:00
# is the first sendable minute. The range edges below match exactly.
_NIGHT_START_HOUR = 21
_NIGHT_END_HOUR = 8


def is_night_kst(dt: datetime | None = None) -> bool:
    """Return True iff ``dt`` falls in the §61의2 night window (KST).

    ``dt`` may be naive (assumed UTC, project convention) or tz-aware.
    Coerced to KST before checking the hour. Pure function — easy to
    unit-test the edge cases at 07:59 / 08:00 / 20:59 / 21:00 KST.
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    kst_dt = dt.astimezone(KST)
    h = kst_dt.hour
    return h >= _NIGHT_START_HOUR or h < _NIGHT_END_HOUR


# ── sequence definition ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class _Step:
    slug: str
    offset: timedelta
    subject: str
    template_basename: str  # e.g. "d7_summary" → retention/d7_summary.{html,txt}


# Subjects MUST start with "(광고)" per 시행령 §62 ②. Tests assert this
# at the SEQUENCE level so accidental copy edits surface immediately.
SEQUENCE: tuple[_Step, ...] = (
    _Step(
        slug="retention_d7",
        offset=timedelta(days=7),
        subject="(광고) PivoxQuant 7일 요약 — 대시보드 다시 둘러보기",
        template_basename="d7_summary",
    ),
    _Step(
        slug="retention_d30",
        offset=timedelta(days=30),
        subject="(광고) PivoxQuant 30일 요약 — 한 달간 사용해 보셨다면",
        template_basename="d30_summary",
    ),
)


# Allowed slug set — used by the dispatcher's type filter so onboarding's
# dispatch_due cannot accidentally consume our rows (and vice versa).
RETENTION_SLUGS: frozenset[str] = frozenset(s.slug for s in SEQUENCE)


# ── consent helpers ──────────────────────────────────────────────────────────


def _has_marketing_consent(user: Any) -> bool:
    """Return True iff the user has effective MARKETING consent.

    Mirrors the predicate used by ``services.email.sender._has_category_consent``
    and ``routes/consents.py`` so all three sides agree exactly.
    """
    consent_at = getattr(user, "marketing_consent_marketing_at", None)
    if consent_at is None:
        return False
    revoked_at = getattr(user, "marketing_consent_marketing_revoked_at", None)
    return revoked_at is None or revoked_at < consent_at


# ── path / URL helpers ───────────────────────────────────────────────────────


_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates" / "retention"


def _utc_naive(dt: datetime | None) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc).replace(tzinfo=None)
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _dashboard_url() -> str:
    frontend = os.environ.get("FRONTEND_URL", "https://pivoxquant.com").rstrip("/")
    return os.environ.get("PIVOX_DASHBOARD_URL", f"{frontend}/home")


def _format_consent_kr(consent_at: datetime | None) -> str:
    """Render the user's consent timestamp in KST locale for the footer."""
    if consent_at is None:
        return "(시점 미상)"
    dt = consent_at
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(KST).strftime("%Y-%m-%d %H:%M KST")


def _render(
    basename: str,
    *,
    user: Any,
    unsubscribe_url: str,
) -> tuple[str, str]:
    """Read + substitute the .html and .txt templates.

    Hand-rolled ``str.replace`` (matches the onboarding_sequence pattern)
    so the module does not depend on a Flask Jinja env. Placeholders:

    * ``{{ name }}``           — display name, falls back to email-local-part
    * ``{{ dashboard_url }}``  — env-driven, defaults to ``$FRONTEND_URL/home``
    * ``{{ unsubscribe_url }}``— pre-built HMAC token from
      :func:`services.email_token.build_unsubscribe_url`
    * ``{{ consent_at_kr }}``  — KST-localised MARKETING consent timestamp
    * ``{{ consent_source }}`` — short string identifying where consent
      was captured. Hard-coded to "회원가입 시 동의" for now; future
      sources (settings page re-opt-in) can be threaded through later.
    """
    name = (
        (getattr(user, "name", None) or "").strip()
        or (getattr(user, "email", "") or "").split("@")[0]
        or "고객"
    )
    consent_at = getattr(user, "marketing_consent_marketing_at", None)
    ctx = {
        "{{ name }}": name,
        "{{ dashboard_url }}": _dashboard_url(),
        "{{ unsubscribe_url }}": unsubscribe_url,
        "{{ consent_at_kr }}": _format_consent_kr(consent_at),
        "{{ consent_source }}": "회원가입 시 동의",
    }
    html_path = _TEMPLATE_DIR / f"{basename}.html"
    txt_path = _TEMPLATE_DIR / f"{basename}.txt"

    html_body = html_path.read_text(encoding="utf-8")
    txt_body = txt_path.read_text(encoding="utf-8")
    for k, v in ctx.items():
        html_body = html_body.replace(k, v)
        txt_body = txt_body.replace(k, v)
    return html_body, txt_body


# ── render-time hard assertions (시행령 §62 ② + §49 자본시장법) ──────────────


_AD_MARKER = "(광고)"


def _assert_ad_marker(subject: str, body: str, *, where: str) -> None:
    """Belt-and-braces: subject + body first line must include '(광고)'.

    Two layers (constants in SEQUENCE *and* template content) so a
    refactor that swaps subjects or edits a template body cannot quietly
    drop the marker.
    """
    if _AD_MARKER not in subject:
        raise ValueError(
            f"'(광고)' marker missing from subject at {where!r}: {subject!r}"
        )
    first_line = body.lstrip().splitlines()[0] if body.strip() else ""
    # For HTML bodies the first visible text line is near the top but
    # wrapped in <p>; scan the first 400 chars to be tolerant.
    head = body[:400]
    if _AD_MARKER not in head:
        raise ValueError(
            f"'(광고)' marker missing from body head at {where!r}: "
            f"first_line={first_line!r}"
        )


def _assert_legal_safe(text: str, *, where: str) -> None:
    """Wrap services.legal.assert_legal_safe with a stable import site."""
    from services.legal import assert_legal_safe
    assert_legal_safe(text, where)


# ── public: schedule at signup ──────────────────────────────────────────────


def schedule_retention(
    user: Any,
    *,
    now: datetime | None = None,
) -> dict[str, int]:
    """Enqueue the D+7/D+30 retention rows for ``user``.

    Skips enqueue when:
      * Feature flag off (``flag_off=1``)
      * User has no effective MARKETING consent (``no_consent=1``)
      * ``user.id`` missing (defensive — pre-commit signup race)

    Caller commits. Returns a stats dict for logging.
    """
    from extensions import db
    from models import ScheduledEmail

    stats = {
        "enqueued": 0,
        "existed": 0,
        "flag_off": 0,
        "no_consent": 0,
    }

    if not retention_enabled():
        stats["flag_off"] = 1
        return stats

    user_id = getattr(user, "id", None)
    if not user_id:
        logger.warning("schedule_retention called with user.id missing — skip")
        return stats

    if not _has_marketing_consent(user):
        stats["no_consent"] = 1
        return stats

    base = _utc_naive(now)
    for step in SEQUENCE:
        row = ScheduledEmail.enqueue(
            user_id=user_id,
            email_type=step.slug,
            email_category="marketing",
            scheduled_send_at=base + step.offset,
        )
        if row is None:
            stats["existed"] += 1
        else:
            stats["enqueued"] += 1

    # Flush so an enqueue race surfaces immediately (matches the
    # onboarding_sequence + CheckoutExpiration pattern).
    try:
        db.session.flush()
    except Exception:
        logger.exception(
            "schedule_retention flush failed for user_id=%s", user_id,
        )
        db.session.rollback()
        return {"enqueued": 0, "existed": 0, "flag_off": 0, "no_consent": 0}

    return stats


# ── public: dispatch due rows ───────────────────────────────────────────────


def _step_for(slug: str) -> _Step | None:
    for s in SEQUENCE:
        if s.slug == slug:
            return s
    return None


def _pending_retention_rows(now: datetime | None, limit: int = 200) -> list[Any]:
    """Type-filtered pending_due — only ``retention_*`` slugs."""
    from models import ScheduledEmail

    if now is None:
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    elif now.tzinfo is not None:
        now_naive = now.astimezone(timezone.utc).replace(tzinfo=None)
    else:
        now_naive = now

    return (
        ScheduledEmail.query
        .filter(ScheduledEmail.email_type.in_(RETENTION_SLUGS))
        .filter(ScheduledEmail.scheduled_send_at <= now_naive)
        .filter(ScheduledEmail.sent_at.is_(None))
        .filter(ScheduledEmail.skipped_reason.is_(None))
        .order_by(ScheduledEmail.scheduled_send_at.asc())
        .limit(limit)
        .all()
    )


def _send_one(row: Any) -> bool:
    """Render + send one queued retention email. Returns True on accept.

    All hard guardrails (§50 / §49 / §62) fire here so a future caller
    that bypasses ``dispatch_retention`` still cannot ship a non-compliant
    email.
    """
    from services.email import EmailSender
    from services.email.sender import EmailCategory
    from services.email_token import build_unsubscribe_url
    from extensions import db
    from models import User

    step = _step_for(row.email_type)
    if step is None:
        logger.warning(
            "retention row id=%s has unknown email_type=%r",
            row.id, row.email_type,
        )
        return False

    user = db.session.get(User, row.user_id)
    if user is None or not getattr(user, "email", None):
        return False

    # Dispatch-time consent re-check (guardrail #6). A revoke between
    # enqueue and dispatch must short-circuit even when the EmailSender's
    # CS1 flag is off.
    if not _has_marketing_consent(user):
        return False

    unsubscribe_url = build_unsubscribe_url(user.id, kind="all")

    try:
        html_body, txt_body = _render(
            step.template_basename, user=user, unsubscribe_url=unsubscribe_url,
        )
    except FileNotFoundError as exc:
        logger.exception("retention template missing for %s: %s", step.slug, exc)
        return False

    # Render-time hard assertions — kill switches (guardrails #2 + #5).
    _assert_ad_marker(step.subject, html_body, where=f"retention/{step.slug}/html")
    _assert_ad_marker(step.subject, txt_body,  where=f"retention/{step.slug}/txt")
    _assert_legal_safe(step.subject, where=f"retention/{step.slug}/subject")
    _assert_legal_safe(html_body,    where=f"retention/{step.slug}/html")
    _assert_legal_safe(txt_body,     where=f"retention/{step.slug}/txt")

    return EmailSender().send(
        user,
        subject=step.subject,
        html_body=html_body,
        from_env_var="RETENTION_FROM_EMAIL",
        from_default="reports@pivoxquant.com",
        email_category=EmailCategory.MARKETING,
    )


def dispatch_retention(now: datetime | None = None) -> dict[str, int]:
    """Drain one tick of the retention queue. Returns a stats dict.

    Stats keys:
      - ``due``                : retention rows whose scheduled_send_at <= now
      - ``sent``               : provider accepted
      - ``skipped_flag_off``   : feature flag off — row stamped + closed
      - ``skipped_night``      : §61의2 night window — row LEFT pending
                                 (the only path that does *not* close the row)
      - ``skipped_no_user``    : user gone or missing email
      - ``skipped_no_consent`` : MARKETING consent missing / revoked / provider
                                 refused — row stamped + closed
      - ``skipped_error``      : exception inside ``_send_one``
    """
    from extensions import db

    stats = {
        "due": 0,
        "sent": 0,
        "skipped_flag_off": 0,
        "skipped_night": 0,
        "skipped_no_user": 0,
        "skipped_no_consent": 0,
        "skipped_error": 0,
    }

    rows = _pending_retention_rows(now=now)
    stats["due"] = len(rows)
    if not rows:
        return stats

    flag_on = retention_enabled()
    night = is_night_kst(now)

    for row in rows:
        try:
            if not flag_on:
                row.mark_skipped("feature_flag_off")
                db.session.commit()
                stats["skipped_flag_off"] += 1
                continue

            if night:
                # 시행령 §61의2 — DO NOT close the row. The next tick
                # after 08:00 KST picks it up. We commit nothing for
                # this row so its (sent_at, skipped_reason) stay NULL.
                stats["skipped_night"] += 1
                continue

            ok = _send_one(row)
            if ok:
                row.mark_sent()
                stats["sent"] += 1
            else:
                from models import User
                user = db.session.get(User, row.user_id)
                if user is None or not getattr(user, "email", None):
                    row.mark_skipped("no_user_or_email")
                    stats["skipped_no_user"] += 1
                else:
                    row.mark_skipped("no_consent_or_provider")
                    stats["skipped_no_consent"] += 1
            db.session.commit()
        except Exception as exc:  # noqa: BLE001
            db.session.rollback()
            logger.exception(
                "retention dispatch failed (id=%s type=%s): %s",
                row.id, row.email_type, exc,
            )
            stats["skipped_error"] += 1

    return stats


__all__ = [
    "SEQUENCE",
    "RETENTION_SLUGS",
    "retention_enabled",
    "is_night_kst",
    "schedule_retention",
    "dispatch_retention",
]
