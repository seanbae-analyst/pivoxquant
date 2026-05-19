"""
services/email/onboarding_sequence.py — D+0 / D+3 / D+7 onboarding emails.

Wave G S5. Wraps the ``scheduled_emails`` queue (``models.ScheduledEmail``)
with the actual sequence definition + per-row send logic.

Public surface
--------------
* ``schedule_onboarding(user, now=None)`` — call from signup callbacks
  (password ``/register``, OAuth finalize). Idempotent: re-running for
  the same user is a no-op because every row keys off
  ``"u{user_id}:{email_type}"``. Feature-flag-aware: when
  ``PIVOX_ONBOARDING_SEQUENCE_ENABLED=false`` (default) returns
  immediately without writing any rows.
* ``dispatch_due(now=None)`` — called by
  ``scripts/nightly/email_scheduler_dispatcher.py`` every 15 min. Walks
  ``ScheduledEmail.pending_due()`` and renders + sends each one,
  marking ``sent_at`` on success and ``skipped_reason`` on permanent
  failure. Feature-flag-aware: when the flag is off, stamps every due
  row with ``skipped_reason="feature_flag_off"`` so the table doesn't
  grow unbounded while we wait for the variance-flag flip.
* ``onboarding_enabled()`` — feature-flag read. Exposed for tests +
  the dispatcher's short-circuit.
* ``SEQUENCE`` — the canonical D+0 / D+3 / D+7 spec. Tests assert
  against this to catch accidental copy edits.

§50 classification
------------------
``welcome`` is TRANSACTIONAL — §50 ③ 면제 (가입 절차의 일부 통지).
``d3_guide`` and ``d7_pro_nudge`` are INFORMATION — §50 ① 분리 동의
필수. The send path passes ``email_category`` to ``EmailSender.send``
which (with ``PIVOX_CS1_CONSENT_ENABLED=true``) enforces the
per-category consent column. With the C-S1 flag off, sends fall back
to the legacy ``marketing_consent_at`` + ``email_opt_out`` gate.

광고 카피 금지
-------------
The d7 template uses sachlich, factual plan description ("Pro 는
무제한 분석을 제공합니다") — no discount / scarcity / urgency
language. ``BANNED_MARKETING_PHRASES`` below is enforced by the test
suite for both HTML and text bodies, mirroring the
``services/billing_followup`` ban list pattern.

Cost
----
- DB: ~3 INSERT per signup + ~1 SELECT per 15-min tick (96/day). Zero
  marginal cost.
- SendGrid 100/day free + Brevo 300/day free fallback.
- 추가 비용 0원.

Schedule shape (table top-of-mind)
----------------------------------

  | slug          | offset | category      | template family    |
  |---------------|--------|---------------|--------------------|
  | welcome       | +0d    | transactional | onboarding/welcome |
  | d3_guide      | +3d    | information   | onboarding/d3_guide|
  | d7_pro_nudge  | +7d    | information   | onboarding/d7_pro… |
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ── feature flag ─────────────────────────────────────────────────────────────


_FLAG_ENV = "PIVOX_ONBOARDING_SEQUENCE_ENABLED"


def onboarding_enabled() -> bool:
    """Return True iff the D+0/D+3/D+7 pipeline should run.

    Default false — matches the C-S1 / C-M1 / C-S2 pattern. The schema
    + dispatcher + signup hooks all deploy, but the user-visible
    side-effect is gated behind a single env flip. Variance-flag flip
    after the lawyer's Q-S1 answer arrives.

    Read on every call so a runtime env flip is honoured without
    needing a redeploy (matches EmailSender's stateless dispatch
    contract).
    """
    val = os.environ.get(_FLAG_ENV, "false").strip().lower()
    return val in ("true", "1", "yes", "on")


# ── sequence definition ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class _Step:
    slug: str
    offset: timedelta
    category: str  # matches EmailCategory.value
    subject: str
    template_basename: str  # e.g. "welcome" → onboarding/welcome.{html,txt}


# Canonical sequence. Adding a step here is sufficient — the model
# accepts any slug; the dispatcher iterates whatever's queued. No
# migration needed for a D+14 / D+30 follow-on in a future wave.
SEQUENCE: tuple[_Step, ...] = (
    _Step(
        slug="welcome",
        offset=timedelta(days=0),
        category="transactional",
        subject="PivoxQuant 가입을 환영합니다",
        template_basename="welcome",
    ),
    _Step(
        slug="d3_guide",
        offset=timedelta(days=3),
        category="information",
        subject="PivoxQuant 3일차 — 사용 가이드",
        template_basename="d3_guide",
    ),
    _Step(
        slug="d7_pro_nudge",
        offset=timedelta(days=7),
        category="information",
        subject="PivoxQuant 플랜 안내",
        template_basename="d7_pro_nudge",
    ),
)


# ── marketing-copy ban-list (enforced by tests for INFORMATION steps) ───────

# We intentionally avoid any phrase that would re-classify the email
# as 광고성 정보 under 정통망법 §50 ①. The d7 step is the load-bearing
# one — Pro plan info is allowed, but discount / urgency / scarcity
# framing would tip it into 광고 territory.
BANNED_MARKETING_PHRASES: tuple[str, ...] = (
    "할인", "특가", "혜택", "프로모션", "이벤트", "쿠폰",
    "지금만", "한정", "오늘만", "특별 가격", "런칭 기념",
    "discount", "promo", "promotion", "limited", "offer", "deal",
    "save now", "today only", "exclusive",
)


# ── helpers ──────────────────────────────────────────────────────────────────


def _utc_naive(dt: datetime | None) -> datetime:
    if dt is None:
        return datetime.now(timezone.utc).replace(tzinfo=None)
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _dashboard_url() -> str:
    frontend = os.environ.get("FRONTEND_URL", "https://pivoxquant.com").rstrip("/")
    return os.environ.get("PIVOX_DASHBOARD_URL", f"{frontend}/home")


def _pricing_url() -> str:
    frontend = os.environ.get("FRONTEND_URL", "https://pivoxquant.com").rstrip("/")
    return os.environ.get("PIVOX_PRICING_URL", f"{frontend}/pricing")


_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates" / "onboarding"


def _render(basename: str, *, user: Any) -> tuple[str, str]:
    """Read the .html + .txt templates and substitute placeholders.

    Intentionally not pulling Flask's Jinja env in — these templates
    are small, the placeholder set is fixed, and a hand-rolled
    ``str.replace`` keeps the dispatcher independent of an app context
    setup beyond the model layer. The trade-off: any new placeholder
    needs an explicit branch here.
    """
    name = (
        (getattr(user, "name", None) or "").strip()
        or (getattr(user, "email", "") or "").split("@")[0]
        or "고객"
    )
    ctx = {
        "{{ name }}": name,
        "{{ dashboard_url }}": _dashboard_url(),
        "{{ pricing_url }}": _pricing_url(),
    }
    html_path = _TEMPLATE_DIR / f"{basename}.html"
    txt_path = _TEMPLATE_DIR / f"{basename}.txt"

    html_body = html_path.read_text(encoding="utf-8")
    txt_body = txt_path.read_text(encoding="utf-8")

    for k, v in ctx.items():
        html_body = html_body.replace(k, v)
        txt_body = txt_body.replace(k, v)
    return html_body, txt_body


# ── public: schedule at signup ──────────────────────────────────────────────


def schedule_onboarding(
    user: Any,
    *,
    now: datetime | None = None,
) -> dict[str, int]:
    """Enqueue the D+0/D+3/D+7 sequence rows for ``user``.

    Called from signup hooks (password ``/register``, OAuth finalize).
    Caller is responsible for the surrounding commit — this helper
    only ``add`` + ``flush`` so it can run inside the existing signup
    transaction (matches ``CheckoutExpiration.enqueue``).

    Returns a small stats dict for logging:
      - ``enqueued`` : new rows inserted
      - ``existed``  : rows whose idempotency_key already existed
      - ``flag_off`` : 1 if the feature flag was off (no work done)
    """
    from extensions import db
    from models import ScheduledEmail

    stats = {"enqueued": 0, "existed": 0, "flag_off": 0}

    if not onboarding_enabled():
        stats["flag_off"] = 1
        return stats

    base = _utc_naive(now)
    user_id = getattr(user, "id", None)
    if not user_id:
        logger.warning("schedule_onboarding called with user.id missing — skip")
        return stats

    for step in SEQUENCE:
        row = ScheduledEmail.enqueue(
            user_id=user_id,
            email_type=step.slug,
            email_category=step.category,
            scheduled_send_at=base + step.offset,
        )
        if row is None:
            stats["existed"] += 1
        else:
            stats["enqueued"] += 1

    # We do NOT commit here — the signup transaction commits us. But
    # we *do* flush so an enqueue race surfaces immediately rather
    # than at the outer commit (matches CheckoutExpiration.enqueue).
    try:
        db.session.flush()
    except Exception:
        logger.exception("schedule_onboarding flush failed for user_id=%s", user_id)
        db.session.rollback()
        # Reset stats — nothing actually got through.
        return {"enqueued": 0, "existed": 0, "flag_off": 0}

    return stats


# ── public: dispatch due rows ───────────────────────────────────────────────


def _step_for(slug: str) -> _Step | None:
    for s in SEQUENCE:
        if s.slug == slug:
            return s
    return None


def _send_one(row: Any) -> bool:
    """Render + send one queued email. Returns True on provider accept.

    Lazily imports the EmailSender + EmailCategory so the model layer
    doesn't depend on the email machinery (mirrors the
    ``billing_followup`` pattern). ``EmailSender.send`` itself owns
    the SendGrid → Brevo → SMTP cascade + opt-out gate + List-Unsubscribe
    headers + unsubscribe footer injection.
    """
    from services.email import EmailSender
    from services.email.sender import EmailCategory

    step = _step_for(row.email_type)
    if step is None:
        logger.warning(
            "scheduled_email row id=%s has unknown email_type=%r",
            row.id, row.email_type,
        )
        return False

    # Re-resolve user fresh — the row may have been queued days ago.
    from models import User
    from extensions import db
    user = db.session.get(User, row.user_id)
    if user is None or not getattr(user, "email", None):
        return False

    try:
        html_body, _txt_body = _render(step.template_basename, user=user)
    except FileNotFoundError as exc:
        logger.exception("template missing for %s: %s", step.slug, exc)
        return False

    # Category enum coerced from the persisted string so the §50 gate
    # uses the same enum the EmailSender's _has_category_consent check
    # expects.
    try:
        category = EmailCategory(row.email_category)
    except ValueError:
        logger.warning(
            "scheduled_email id=%s has unknown email_category=%r — "
            "defaulting to INFORMATION",
            row.id, row.email_category,
        )
        category = EmailCategory.INFORMATION

    return EmailSender().send(
        user,
        subject=step.subject,
        html_body=html_body,
        from_env_var="ONBOARDING_FROM_EMAIL",
        from_default="reports@pivoxquant.com",
        email_category=category,
    )


def dispatch_due(now: datetime | None = None) -> dict[str, int]:
    """Drain one tick of the queue. Returns a stats dict.

    Stats keys:
      - ``due``                : rows pulled by ``pending_due``
      - ``sent``               : provider accepted
      - ``skipped_flag_off``   : feature flag off — row stamped + closed
      - ``skipped_no_user``    : user gone or missing email
      - ``skipped_no_consent`` : EmailSender refused (opt-out / consent)
      - ``skipped_error``      : exception inside ``_send_one``
    """
    from extensions import db
    from models import ScheduledEmail

    stats = {
        "due": 0,
        "sent": 0,
        "skipped_flag_off": 0,
        "skipped_no_user": 0,
        "skipped_no_consent": 0,
        "skipped_error": 0,
    }

    # Type-filter: dispatch_due owns ONLY the onboarding SEQUENCE slugs.
    # Other queues (retention_sequence's retention_d7 / retention_d30,
    # Wave G C-R1) share the same scheduled_emails table; without this
    # filter ``_send_one`` would log "unknown email_type" and stamp the
    # row ``no_consent_or_provider`` — silently consuming retention rows.
    onboarding_slugs = {s.slug for s in SEQUENCE}
    rows = [
        r for r in ScheduledEmail.pending_due(now=now, limit=200)
        if r.email_type in onboarding_slugs
    ]
    stats["due"] = len(rows)
    if not rows:
        return stats

    flag_on = onboarding_enabled()

    for row in rows:
        try:
            if not flag_on:
                row.mark_skipped("feature_flag_off")
                db.session.commit()
                stats["skipped_flag_off"] += 1
                continue

            ok = _send_one(row)
            if ok:
                row.mark_sent()
                stats["sent"] += 1
            else:
                # ``_send_one`` returns False for any non-success path
                # (no user, no email, opt-out, consent missing, provider
                # exhausted). We collapse all into ``no_consent`` /
                # ``no_user`` based on a cheap re-check so ops can
                # distinguish without re-running.
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
                "scheduled_email dispatch failed (id=%s type=%s): %s",
                row.id, row.email_type, exc,
            )
            stats["skipped_error"] += 1

    return stats


__all__ = [
    "SEQUENCE",
    "BANNED_MARKETING_PHRASES",
    "onboarding_enabled",
    "schedule_onboarding",
    "dispatch_due",
]
