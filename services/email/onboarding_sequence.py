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


# ── Stage-1 (paid plans) flag ────────────────────────────────────────────────

# The D+7 ``d7_pro_nudge`` step describes the Free / Pro / Premium paid
# subscription tiers + Stripe billing. Those tiers are ⬛Superseded in
# DECISIONS.md for the free launch (Stage 0): ``/pricing`` 307-redirects
# to ``/home``, billing entry points are removed, every feature is free
# behind ``LAUNCH_FREE_ALL_TIERS``. Sending the d7 nudge at Stage 0 would
# advertise non-existent paid plans (표시광고 risk) and link to a broken
# redirect. So d7 is gated behind this Stage-1 flag and is EXCLUDED from
# the active SEQUENCE while it is off (default off = current free launch).
#
# This mirrors the "Stage 1 deferral + code preservation" pattern used
# for the billing code: the _Step definition (``_D7_STEP``) and both
# template files (d7_pro_nudge.html/.txt) are preserved verbatim so the
# paid-plan revival is a single env flip + no code change once the paid
# tiers come back.
_STAGE1_FLAG_ENV = "PIVOX_PAID_PLANS_ENABLED"


def paid_plans_enabled() -> bool:
    """Return True iff the Stage-1 paid-plan steps (d7 nudge) are active.

    Default false — the free launch (Stage 0) ships without paid tiers.
    Flip to true only when Free/Pro/Premium + Stripe billing are revived
    (Stage 1). Read on every call so the flip needs no redeploy, matching
    ``onboarding_enabled``.
    """
    val = os.environ.get(_STAGE1_FLAG_ENV, "false").strip().lower()
    return val in ("true", "1", "yes", "on")


# ── sequence definition ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class _Step:
    slug: str
    offset: timedelta
    category: str  # matches EmailCategory.value
    subject: str
    template_basename: str  # e.g. "welcome" → onboarding/welcome.{html,txt}


# Stage-0 (free launch) base sequence. Adding a step here is sufficient
# — the model accepts any slug; the dispatcher iterates whatever's
# queued. No migration needed for a D+14 / D+30 follow-on in a future
# wave.
_BASE_SEQUENCE: tuple[_Step, ...] = (
    _Step(
        slug="welcome",
        offset=timedelta(days=0),
        category="transactional",
        subject="PivoxQuant 가입을 환영합니다",
        template_basename="welcome",
    ),
    # 2026-09-10 — reclassified 정보성 → 광고성 (CEO), on the same reasoning
    # that moved the inactive nudge in f70bc8b4. This mail goes out on day 3
    # regardless of whether the reader has recorded anything, and it states no
    # fact about them: it explains the three screens and then says "아직 안
    # 해보셨다면 1. 2. 3." with a dashboard CTA. That is a message asking
    # someone to come back — 광고성 정보 under 정통망법 §50 ①. Containing
    # instructions does not make it 정보성; the nudge's docstring says the
    # same thing, and leaving these two classified differently was the
    # inconsistency this fixes.
    #
    # The régime that follows from it: MARKETING consent (not INFORMATION),
    # the literal "(광고)" in subject and body head (시행령 §62 ②), the
    # 21:00–08:00 KST night ban (시행령 §61의2) and the sender-identity block
    # (시행령 §62 ①).
    _Step(
        slug="d3_guide",
        offset=timedelta(days=3),
        category="marketing",
        subject="(광고) PivoxQuant 3일차 — 사용 가이드",
        template_basename="d3_guide",
    ),
)

# Stage-1 (paid plans) only. PRESERVED for revival — do NOT delete.
# Appended to SEQUENCE only when ``paid_plans_enabled()`` is true. The
# template files services/email/templates/onboarding/d7_pro_nudge.{html,txt}
# are likewise preserved verbatim. See ``paid_plans_enabled`` above for the
# Stage-0/표시광고 rationale.
_D7_STEP: _Step = _Step(
    slug="d7_pro_nudge",
    offset=timedelta(days=7),
    category="information",
    subject="PivoxQuant 플랜 안내",
    template_basename="d7_pro_nudge",
)


def active_sequence() -> tuple[_Step, ...]:
    """Return the steps that should actually be scheduled/dispatched now.

    Stage 0 (free launch, default): welcome + d3_guide only.
    Stage 1 (``PIVOX_PAID_PLANS_ENABLED`` on): + d7_pro_nudge.

    Read through ``paid_plans_enabled()`` on every call so a runtime flip
    is honoured without a redeploy.
    """
    if paid_plans_enabled():
        return _BASE_SEQUENCE + (_D7_STEP,)
    return _BASE_SEQUENCE


# Backwards-compatible module-level snapshot. Reflects the flag at import
# time; the canonical runtime source is ``active_sequence()`` (used by
# ``schedule_onboarding`` / ``dispatch_due`` so a runtime flip applies
# without redeploy). Tests assert against this to catch accidental copy
# edits.
SEQUENCE: tuple[_Step, ...] = active_sequence()


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
    """Single source: :func:`services.email.format_helpers.utc_naive`.

    Kept as a thin alias so the call site below reads unchanged. The two email
    sequence modules held byte-identical copies of this until 2026-09-10.
    """
    from services.email.format_helpers import utc_naive
    return utc_naive(dt)


def _dashboard_url() -> str:
    """Single source: :mod:`services.email.urls`. Kept as a thin alias so the
    call sites below read unchanged — see that module for why the old local
    copy pointed at the deleted ``/home``."""
    from services.email.urls import dashboard_url
    return dashboard_url()


def _pricing_url() -> str:
    """Single source: :mod:`services.email.urls`."""
    from services.email.urls import pricing_url
    return pricing_url()


_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates" / "onboarding"


def _format_consent_kr(dt: Any) -> str:
    """Single source: :func:`services.email.retention_sequence._format_consent_kr`.

    Thin alias so the 시행령 §62 ① consent timestamp is formatted identically
    in both queues — two formatters would drift, and this one appears in a
    legally mandated block.
    """
    from services.email.retention_sequence import _format_consent_kr as _f
    return _f(dt)


def _render(
    basename: str,
    *,
    user: Any,
    unsubscribe_url: str = "",
) -> tuple[str, str]:
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
    # 2026-09-10: d3_guide became 광고성, so it needs the 시행령 §62 ① block.
    # These slots are filled for EVERY onboarding template, not only the
    # marketing one — an unfilled `{{ ... }}` ships to the reader as literal
    # braces, and tests/test_email_links_are_live.py fails on exactly that.
    # `unsubscribe_url` is passed IN rather than built here — same contract as
    # retention_sequence._render. Building it needs a Flask app context
    # (it signs an HMAC with SECRET_KEY), and _render must stay callable from a
    # plain unit test; tests/test_email_links_are_live.py renders all five
    # shipping mails with no app at all. The caller supplies the real token;
    # EmailSender's idempotent footer injection covers the empty case.
    ctx = {
        "{{ name }}": name,
        "{{ dashboard_url }}": _dashboard_url(),
        "{{ pricing_url }}": _pricing_url(),
        "{{ unsubscribe_url }}": unsubscribe_url,
        "{{ consent_at_kr }}": _format_consent_kr(
            getattr(user, "marketing_consent_marketing_at", None)
        ),
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

    for step in active_sequence():
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
    # Resolve against the full known set (base + Stage-1) so a row queued
    # while paid plans were on still renders correctly if the flag later
    # flips off — the dispatcher's active-slug filter (below) decides what
    # to *send*, this only resolves template/subject metadata.
    for s in _BASE_SEQUENCE + (_D7_STEP,):
        if s.slug == slug:
            return s
    return None


# Provider-outage retry window. When every email transport is down, a queued
# onboarding row is left pending so a later tick re-sends it once a provider
# recovers (the designed SendGrid→Brevo failover). There is no attempts column,
# so the retry is bounded by TIME: once a row has been overdue longer than this,
# the dispatcher gives up (marks it skipped) rather than looping forever on a
# permanently undeliverable address.
_PROVIDER_RETRY_WINDOW = timedelta(days=3)


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

    # Transient (non-persisted) marker telling the dispatcher WHY a False was
    # returned. Default = permanent skip (bad config / missing user) — every
    # early return below leaves it None. Only a provider-cascade exhaustion
    # overwrites it to "provider_unavailable" (→ dispatcher retries later).
    row._send_failure_reason = None

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
        from services.email_token import build_unsubscribe_url
        html_body, _txt_body = _render(
            step.template_basename,
            user=user,
            unsubscribe_url=build_unsubscribe_url(user.id),
        )
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

    sender = EmailSender()
    ok = sender.send(
        user,
        subject=step.subject,
        html_body=html_body,
        from_env_var="ONBOARDING_FROM_EMAIL",
        from_default="reports@pivoxquant.com",
        email_category=category,
    )
    if not ok:
        # "provider_unavailable" → all transports down (retryable); anything
        # else (consent/opt-out/preference) stays None → permanent skip.
        row._send_failure_reason = sender.last_failure_reason
    return ok


def dispatch_due(now: datetime | None = None) -> dict[str, int]:
    """Drain one tick of the queue. Returns a stats dict.

    Stats keys:
      - ``due``                : rows pulled by ``pending_due``
      - ``sent``               : provider accepted
      - ``skipped_flag_off``   : feature flag off — row stamped + closed
      - ``skipped_no_user``    : user gone or missing email
      - ``skipped_no_consent`` : EmailSender refused (opt-out / consent)
      - ``skipped_error``      : exception inside ``_send_one``
      - ``skipped_lock``       : another drain held the tick lock (W2-P2)

    Concurrency: the per-row commits inside the drain release the
    ``pending_due`` FOR UPDATE row locks, so an overlapping tick (in-process
    APScheduler racing the crontab fallback) could re-send later rows. The
    advisory drain lock serializes whole ticks across processes — the loser
    skips, it never double-sends.
    """
    from services.drain_lock import DRAIN_ONBOARDING, drain_lock

    with drain_lock(DRAIN_ONBOARDING) as acquired:
        if not acquired:
            logger.info("onboarding dispatch skipped — another drain holds the lock")
            return {"due": 0, "skipped_lock": 1}
        return _dispatch_due_locked(now)


def _dispatch_due_locked(now: datetime | None = None) -> dict[str, int]:
    from extensions import db
    from models import ScheduledEmail

    stats = {
        "due": 0,
        "sent": 0,
        "skipped_flag_off": 0,
        "skipped_no_user": 0,
        "skipped_no_consent": 0,
        "skipped_error": 0,
        # Provider-outage handling (silent-drop fix). ``deferred_provider`` =
        # rows left pending for a later retry; ``skipped_provider_expired`` =
        # rows still undeliverable past the retry window, closed permanently.
        # 광고성 rows held back by the §61의2 night ban. Left PENDING,
        # not skipped — the next tick after 08:00 KST sends them.
        "deferred_night": 0,
        "deferred_provider": 0,
        "skipped_provider_expired": 0,
    }

    # Naive-UTC "now" for the overdue calc below — mirrors pending_due's
    # coercion so the comparison against the naive ``scheduled_send_at`` column
    # is apples-to-apples.
    if now is None:
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    elif now.tzinfo is not None:
        now_naive = now.astimezone(timezone.utc).replace(tzinfo=None)
    else:
        now_naive = now

    # Type-filter: dispatch_due owns ONLY the onboarding SEQUENCE slugs.
    # Other queues (retention_sequence's retention_d7 / retention_d30,
    # Wave G C-R1) share the same scheduled_emails table; without this
    # filter ``_send_one`` would log "unknown email_type" and stamp the
    # row ``no_consent_or_provider`` — silently consuming retention rows.
    onboarding_slugs = {s.slug for s in active_sequence()}
    rows = [
        r for r in ScheduledEmail.pending_due(now=now, limit=200)
        if r.email_type in onboarding_slugs
    ]
    stats["due"] = len(rows)
    if not rows:
        return stats

    flag_on = onboarding_enabled()

    # 시행령 §61의2 night ban, for 광고성 steps only. Evaluated at DISPATCH
    # time and implemented by leaving the row pending — exactly how
    # retention_sequence handles it, and for the same reason: this queue is
    # re-scanned every 15 minutes, so a row that comes due at 23:00 is simply
    # picked up after 08:00 rather than being refused and lost. (The nudge had
    # to widen its window instead, because it has no queue to wait in.)
    from services.email.retention_sequence import is_night_kst
    night = is_night_kst(now)
    marketing_slugs = {s.slug for s in active_sequence() if s.category == "marketing"}

    for row in rows:
        try:
            if not flag_on:
                row.mark_skipped("feature_flag_off")
                db.session.commit()
                stats["skipped_flag_off"] += 1
                continue

            if night and row.email_type in marketing_slugs:
                # Left pending on purpose — no mark_skipped, no commit.
                stats["deferred_night"] += 1
                continue

            ok = _send_one(row)
            reason = getattr(row, "_send_failure_reason", None)
            if ok:
                row.mark_sent()
                stats["sent"] += 1
            elif reason == "provider_unavailable":
                # Every transport was down — transient, NOT a consent refusal.
                # Leave the row pending (sent_at + skipped_reason both NULL) so
                # the next tick re-sends it once a provider recovers. This is
                # the designed SendGrid→Brevo failover that was previously
                # silently dropped. Bounded by time so a permanently
                # undeliverable row can't loop forever.
                if (now_naive - row.scheduled_send_at) <= _PROVIDER_RETRY_WINDOW:
                    stats["deferred_provider"] += 1
                else:
                    row.mark_skipped("provider_unavailable_expired")
                    stats["skipped_provider_expired"] += 1
            else:
                # Permanent: no user / no email / opt-out / consent missing.
                # Never retried — 정통망법 §50 default-deny + opt-out must not be
                # re-attempted. Cheap re-check splits no_user vs consent so ops
                # can distinguish without re-running.
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
    "active_sequence",
    "BANNED_MARKETING_PHRASES",
    "onboarding_enabled",
    "paid_plans_enabled",
    "schedule_onboarding",
    "dispatch_due",
]
