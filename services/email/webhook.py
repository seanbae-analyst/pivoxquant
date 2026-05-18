"""SendGrid Event Webhook handler.

Listens at ``POST /webhooks/sendgrid`` for SendGrid event notifications
(open / bounce / unsubscribe / group_unsubscribe) and updates the
matching :class:`models.Artifact` row's tracking columns.

Security
--------
SendGrid signs every request with ECDSA P-256 (SHA-256) when the
"Signed Event Webhook Requests" feature is enabled. We verify the
signature via the public key configured at
``SENDGRID_WEBHOOK_PUBLIC_KEY`` (PEM). When the env var is unset we
skip verification — useful for local smoke tests, but the production
deployment must always have it set.

CSRF
----
Webhook endpoints are CSRF-exempt (see ``security._CSRF_EXEMPT_PREFIXES``).
The signature check above is the auth layer for this route.

Idempotency
-----------
``open`` events only set ``opened_at`` once (first-open wins) so retried
deliveries from SendGrid don't clobber the original timestamp. ``bounce``
and ``unsubscribe`` overwrite — these are terminal states and the most
recent timestamp is the most useful one.

Reference: https://docs.sendgrid.com/for-developers/tracking-events/getting-started-event-webhook-security-features
"""
from __future__ import annotations

import base64
import logging
import os
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

logger = logging.getLogger(__name__)

sendgrid_webhook_bp = Blueprint("sendgrid_webhook", __name__)


def _verify_signature(
    public_key_pem: str,
    signature: str | None,
    timestamp: str | None,
    body: bytes,
) -> bool:
    """Verify SendGrid Event Webhook ECDSA P-256 signature.

    SendGrid signs ``timestamp + raw_body`` with SHA-256 ECDSA. The
    signature header is base64-encoded.
    """
    if not (signature and timestamp and body):
        return False
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec

        pubkey = serialization.load_pem_public_key(public_key_pem.encode())
        signed_payload = (timestamp.encode("utf-8") + body)
        sig_bytes = base64.b64decode(signature)

        pubkey.verify(sig_bytes, signed_payload, ec.ECDSA(hashes.SHA256()))
        return True
    except Exception as exc:  # pragma: no cover — exercised via tests
        logger.warning("SendGrid signature verification failed: %s", exc)
        return False


def _extract_message_id(raw: str) -> str:
    """Strip SendGrid's ``.<filter-id>`` suffix to get the base message id.

    SendGrid's ``sg_message_id`` looks like ``abcDEF123.filterserver-1``;
    the part before the first dot matches the ``X-Message-Id`` header
    SendGrid returns at send time.
    """
    if not raw:
        return ""
    return raw.split(".", 1)[0]


def _auto_opt_out(user_id, reason: str) -> None:
    """Force-flip ``User.email_opt_out=True`` after a terminal email event.

    Triggered from the SendGrid webhook on bounce / spamreport /
    unsubscribe. The flag is treated as one-way (False → True only);
    the user can re-enable manually through the settings page if the
    event was wrong (e.g. transient bounce mis-classified).

    Silent on missing user / DB error — the artifact row update has
    already happened and is the primary signal; opt-out flip is the
    defensive secondary signal. Logging keeps an audit trail.
    """
    if not user_id:
        return
    try:
        from extensions import db
        from models import User
        user = db.session.get(User, int(user_id))
        if user is None:
            return
        if bool(getattr(user, "email_opt_out", False)):
            return  # already opted-out, no-op
        user.email_opt_out = True
        # Wave G-1 Bug #6 (2026-05-18): bounce / spamreport / hosted-unsubscribe
        # 는 implicit revocation 으로 취급. consent audit trail 일관성을 위해
        # marketing_consent_revoked_at 도 함께 기록한다 (정통망법 §50 ① 증빙).
        # 이미 revoke 이력이 있으면 가장 오래된 stamp 유지 — 첫 revoke 시점이
        # 법적으로 유의미하므로 덮어쓰지 않는다.
        if not getattr(user, "marketing_consent_revoked_at", None):
            user.marketing_consent_revoked_at = (
                datetime.now(timezone.utc).replace(tzinfo=None)
            )
        # 정통망법 §50 evidentiary record — caller commits the
        # surrounding artifact update; relying on that commit so we
        # don't fragment the transaction.
        logger.info(
            "email auto opt-out flipped: user_id=%s reason=%s", user_id, reason
        )
    except Exception:
        logger.exception(
            "auto-opt-out failed user_id=%s reason=%s", user_id, reason
        )


@sendgrid_webhook_bp.route("/webhooks/sendgrid", methods=["POST"])
def sendgrid_event():
    """Receive SendGrid event notifications and update tracking columns."""
    raw_body = request.get_data()

    public_key = os.environ.get("SENDGRID_WEBHOOK_PUBLIC_KEY")
    if not public_key:
        # In production, refuse to accept unsigned webhooks. SendGrid will
        # retry on 5xx, so a missing key surfaces as a deploy-time alarm
        # instead of silently allowing forged events into the DB.
        if os.environ.get("FLASK_ENV") == "production":
            logger.error(
                "SENDGRID_WEBHOOK_PUBLIC_KEY missing in production — refusing webhook"
            )
            return jsonify({"error": "webhook key not configured"}), 503
    else:
        signature = request.headers.get("X-Twilio-Email-Event-Webhook-Signature")
        timestamp = request.headers.get("X-Twilio-Email-Event-Webhook-Timestamp")
        if not _verify_signature(public_key, signature, timestamp, raw_body):
            return jsonify({"error": "invalid signature"}), 403

    events = request.get_json(silent=True)
    if not isinstance(events, list):
        return jsonify({"error": "invalid payload"}), 400

    # Lazy imports — keeps this module importable in environments where
    # the ORM hasn't initialised yet (e.g. ``ast.parse`` syntax checks).
    from extensions import db
    from models import Artifact

    processed = 0
    for event in events:
        if not isinstance(event, dict):
            continue

        msg_id = _extract_message_id(event.get("sg_message_id", "") or "")
        if not msg_id:
            continue

        artifact = Artifact.query.filter_by(sg_message_id=msg_id).first()
        if not artifact:
            # Not every SendGrid send corresponds to an Artifact row
            # (transactional auth emails, dev test sends, etc.). Silent
            # skip is correct here.
            continue

        ts_raw = event.get("timestamp")
        if ts_raw in (None, ""):
            # SendGrid always sends a timestamp on real events; treat its
            # absence as a malformed entry rather than silently coercing
            # to epoch 0 (1970-01-01).
            continue
        try:
            ts = datetime.fromtimestamp(int(ts_raw), tz=timezone.utc)
        except (TypeError, ValueError):
            continue
        # Strip tzinfo to match the model's naive-UTC convention
        # (every other ``datetime`` column on Artifact is stored naive).
        ts_naive = ts.replace(tzinfo=None)

        evt_type = event.get("event")
        if evt_type == "open" and not artifact.opened_at:
            artifact.opened_at = ts_naive
            processed += 1
        elif evt_type == "bounce":
            artifact.bounced_at = ts_naive
            processed += 1
            # 2026-05-17 wave 13 P1 (PR #439): hard bounces +
            # spam reports must auto-flip the user's
            # ``email_opt_out`` flag so the daily artifact cron
            # doesn't re-send to the same broken / hostile
            # address tomorrow. Continuing to mail a bounced or
            # complained recipient is a 정통망법 §50 + SendGrid
            # sender-reputation risk. We honour the flag as a
            # one-way toggle (False → True only); opt-in flow
            # already exists for the user to re-enable manually.
            _auto_opt_out(artifact.user_id, reason="bounce")
        elif evt_type == "spamreport":
            # Pre-fix: spamreport was silently ignored. SendGrid
            # treats spam complaints as the strongest deliverability
            # signal; we must stop sending to this address NOW.
            artifact.bounced_at = artifact.bounced_at or ts_naive
            processed += 1
            _auto_opt_out(artifact.user_id, reason="spamreport")
        elif evt_type in ("unsubscribe", "group_unsubscribe"):
            artifact.unsubscribed_at = ts_naive
            processed += 1
            # Unsubscribe events from SendGrid's hosted page (separate
            # from our /api/email/unsubscribe path) should also flip
            # the opt-out flag so the next artifact cron skips this
            # user. Symmetric to the bounce path above.
            _auto_opt_out(artifact.user_id, reason=evt_type)
        # Other event types (delivered, processed, dropped, deferred,
        # click) are intentionally ignored — we don't currently surface
        # those in the product.

    if processed:
        db.session.commit()

    return jsonify({"processed": processed}), 200


__all__ = ["sendgrid_webhook_bp"]
