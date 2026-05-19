"""First-brag-card celebration email (Wave G C-AC1).

When a user generates their *first* brag card, send a one-time
congratulatory email with a share CTA. This is the "Aha moment" hook
for the viral loop — the brag card is MVP #2 and shares are the
distribution channel back into signup.

§50 분류
--------
**TRANSACTIONAL.** The email is triggered by the user's own action
(generating a brag card) and contains no marketing copy ("축하" /
"공유 가능 링크" only — no "할인", "혜택", "특가"). Per
``services.email.sender.EmailCategory`` docstring this is §50 ①
적용 제외 — no marketing consent required.

Idempotency
-----------
The "is this the first one?" check is a single ``COUNT(*)`` over
``Artifact`` filtered on ``user_id`` + ``type='brag_card'``. The caller
hooks this from inside the brag-card service ``_persist`` flow *after*
the new row has been written, so the count is 1 on the very first
card and ≥2 thereafter. We re-read the count instead of trusting a
caller-passed flag so a retry of the hook (e.g. transient SMTP
failure) cannot fire a second celebration.

Feature flag
------------
No flag. TRANSACTIONAL category. The flag-gated path is the C-S2 24h
nudge (information-class) — see ``services/customer/inactive_nudge.py``.

UTM / referral attribution
--------------------------
The share CTA URL carries ``?utm_source=email_brag_celebration`` so
downstream signup attribution can tell viral-loop emails apart from
the existing share-link surface (which uses ``?r={referral_code}``).
Both query params coexist — the referral code is mandatory for
attribution and the utm source disambiguates the email channel.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

from extensions import db
from models import Artifact, User
from services.email import EmailSender
from services.email.sender import EmailCategory

logger = logging.getLogger(__name__)


# ── path / config ────────────────────────────────────────────────────────────

_TEMPLATE_DIR_NAME = "customer"
_TEMPLATE_NAME = "brag_card_celebration.html"


def _share_base_url() -> str:
    """Public base URL used in share links. Trailing slash stripped.

    Matches ``services.artifacts.brag_card_service._share_base_url`` so
    the celebration email's CTA reaches the same surface as the
    in-app share button.
    """
    url = os.environ.get("BRAG_CARD_SHARE_BASE_URL", "https://pivoxquant.com")
    return url.rstrip("/")


# ── public API ───────────────────────────────────────────────────────────────

def is_first_brag_card(user_id: int) -> bool:
    """Return True iff this user has exactly one persisted brag_card row.

    Called *after* the new artefact is committed, so the count is 1 on
    the very first card. The query is intentionally scoped to
    ``type='brag_card'`` so the legacy ``monthly_brag`` rows do not
    skew the result.
    """
    try:
        count = (
            Artifact.query
            .filter_by(user_id=user_id, type="brag_card")
            .count()
        )
    except Exception as exc:  # pragma: no cover — DB schema drift
        logger.warning(
            "brag_card count failed for user %s: %s — skipping celebration",
            user_id, exc,
        )
        return False
    return count == 1


_CELEBRATION_SENT_KEY = "_first_brag_celebration_sent_at"


def _already_celebrated(artifact: Artifact) -> bool:
    """True iff ``data_json[_CELEBRATION_SENT_KEY]`` is set.

    The marker is written on the artefact row itself (no schema
    migration needed — ``Artifact.data_json`` is a JSON column already
    used by every artefact mailer for similar bookkeeping). This makes
    the celebration idempotent across upserts on the same month: the
    second ``run_for_user`` for March-2026 still has ``COUNT == 1`` but
    finds the marker set and skips.
    """
    try:
        return bool(
            artifact.data_json
            and artifact.data_json.get(_CELEBRATION_SENT_KEY)
        )
    except Exception:
        return False


def maybe_send_first_brag_celebration(
    user: User,
    artifact: Artifact,
) -> bool:
    """Send the first-brag celebration email if this is the user's N=1 card.

    Returns ``True`` on dispatch, ``False`` on skip (not first / already
    celebrated / send failed / opt-out gate / no transport). Never
    raises — callers can fire-and-forget without try/except.

    Idempotency
    -----------
    Two layers, both required:
      1. ``COUNT(*) == 1`` over brag_card artefacts — rejects N≥2.
      2. ``data_json[_first_brag_celebration_sent_at]`` flag on the
         artefact — rejects re-runs of the same month-upsert.

    The flag is written only on a successful dispatch so a transient
    send failure (SendGrid 5xx with no fallback configured) leaves the
    marker unset and the next persist retry will re-attempt.
    """
    if user is None or artifact is None:
        return False

    if artifact.type != "brag_card":
        return False

    if _already_celebrated(artifact):
        return False

    if not is_first_brag_card(user.id):
        return False

    share_url = _build_share_url(user, artifact)
    html_body = _render_html(user, artifact, share_url)

    try:
        ok = EmailSender().send(
            user,
            subject="첫 brag-card 완성을 축하드려요",
            html_body=html_body,
            from_env_var="BRAG_CARD_FROM_EMAIL",
            from_default="reports@pivoxquant.com",
            # TRANSACTIONAL — §50 ① 적용 제외. The sender's category
            # gate short-circuits to "allowed" for transactional sends
            # even when PIVOX_CS1_CONSENT_ENABLED is true.
            email_category=EmailCategory.TRANSACTIONAL,
        )
    except Exception as exc:
        logger.exception(
            "first-brag celebration send raised for user %s: %s",
            user.id, exc,
        )
        return False

    if not ok:
        return False

    # Persist the celebrated marker so subsequent UPSERT-on-same-month
    # runs short-circuit. Failure to write the marker is non-fatal — the
    # email already went out and worst-case the user gets a second copy
    # on the next re-run (rare; only triggered by manual reruns).
    try:
        from datetime import datetime, timezone
        payload = dict(artifact.data_json or {})
        payload[_CELEBRATION_SENT_KEY] = (
            datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        )
        artifact.data_json = payload
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.warning(
            "first-brag celebration marker persist failed for user %s: %s",
            user.id, exc,
        )

    logger.info(
        "first-brag celebration sent to user %s (artefact %s)",
        user.id, artifact.id,
    )
    return True


# ── internals ────────────────────────────────────────────────────────────────

def _build_share_url(user: User, artifact: Artifact) -> str:
    """Compose the celebration share URL.

    Layered fallback (in order):
      1. ``artefact.share_token`` + referral code → canonical share path
      2. ``referral_code`` alone → ``/r/{code}`` (still attributable)
      3. base URL only (last-resort — should not happen post-persist)
    """
    base = _share_base_url()
    token = getattr(artifact, "share_token", None)
    referral = ""
    try:
        if artifact.data_json:
            referral = str(artifact.data_json.get("referral_code") or "")
    except Exception:
        referral = ""
    if not referral:
        referral = getattr(user, "referral_code", "") or ""

    utm = "utm_source=email_brag_celebration"
    if token:
        url = f"{base}/share/brag/{token}"
        if referral:
            return f"{url}?r={referral}&{utm}"
        return f"{url}?{utm}"
    if referral:
        return f"{base}/r/{referral}?{utm}"
    return f"{base}?{utm}"


def _render_html(user: User, artifact: Artifact, share_url: str) -> str:
    """Render the celebration HTML.

    Uses Jinja when available (template at
    ``services/email/templates/customer/brag_card_celebration.html``);
    falls back to a minimal inline-CSS body so the pipeline survives
    on machines without Jinja2 installed (parity with the brag-card
    service's own fallback).
    """
    user_name = _resolve_user_name(user)
    month_label = ""
    return_pct = None
    try:
        if artifact.data_json:
            month_label = str(
                artifact.data_json.get("month_label_long")
                or artifact.data_json.get("month_label")
                or ""
            )
            return_pct = artifact.data_json.get("return_pct")
    except Exception:
        pass

    ctx: dict[str, Any] = {
        "user_name": user_name,
        "share_url": share_url,
        "month_label": month_label,
        "return_pct": return_pct,
    }

    env = _try_jinja_env()
    if env is None:
        return _fallback_html(ctx)
    try:
        tpl = env.get_template(f"{_TEMPLATE_DIR_NAME}/{_TEMPLATE_NAME}")
        return tpl.render(**ctx)
    except Exception as exc:
        logger.warning("celebration template render failed: %s", exc)
        return _fallback_html(ctx)


def _resolve_user_name(user: User) -> str:
    name = (getattr(user, "name", "") or "").strip()
    if name:
        return name
    email = getattr(user, "email", "") or ""
    return (email.split("@")[0] if email else "Investor") or "Investor"


def _try_jinja_env():
    """Return a Jinja2 ``Environment`` pointed at ``services/email/templates``.

    Returns ``None`` when Jinja2 is unavailable so the caller can fall
    back to inline HTML.
    """
    try:
        from pathlib import Path

        from jinja2 import Environment, FileSystemLoader, select_autoescape
    except Exception as exc:  # pragma: no cover — depends on env
        logger.debug("Jinja2 unavailable for celebration: %s", exc)
        return None
    try:
        templates_dir = Path(__file__).resolve().parent.parent / "email" / "templates"
        return Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
    except Exception as exc:  # pragma: no cover
        logger.warning("Jinja env build failed for celebration: %s", exc)
        return None


def _fallback_html(ctx: dict[str, Any]) -> str:
    """Inline-CSS fallback used when Jinja2 isn't available.

    Plain neutral copy — no "할인" / "혜택" / "특가" / "광고". Reuses
    the same warm-ivory palette as the brag-card email so the
    celebration feels continuous with the artefact itself.
    """
    from html import escape

    name = escape(ctx.get("user_name", "Investor"))
    share_url = escape(ctx.get("share_url", "") or "")
    month = escape(ctx.get("month_label", "") or "")
    return_pct = ctx.get("return_pct")
    if return_pct is None:
        ret_line = ""
    else:
        sign = "+" if return_pct >= 0 else ""
        ret_line = (
            f"<p style=\"margin:8px 0;color:#5C5550;\">"
            f"이번 달 기록: <strong>{sign}{return_pct:.2f}%</strong></p>"
        )
    month_line = (
        f"<p style=\"margin:8px 0;color:#5C5550;\">{month}</p>"
        if month else ""
    )
    cta = (
        f"<p style=\"margin:24px 0;\">"
        f"<a href=\"{share_url}\" "
        f"style=\"display:inline-block;padding:12px 24px;"
        f"background:#0A0A0A;color:#F6F3EC;text-decoration:none;"
        f"font-family:'Source Serif 4',Georgia,serif;font-size:14px;"
        f"letter-spacing:0.04em;\">친구에게 공유해보세요</a></p>"
        if share_url else ""
    )
    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"/></head>
<body style="margin:0;padding:24px;background:#F6F3EC;
  font-family:'Source Serif 4',Georgia,serif;color:#0A0A0A;">
<div style="max-width:560px;margin:0 auto;">
  <p style="margin:0;font-size:11px;letter-spacing:0.28em;
    text-transform:uppercase;color:#B8956A;">
    PIVOXQUANT &middot; BRAG CARD</p>
  <h1 style="margin:16px 0 8px 0;font-size:22px;line-height:1.3;
    font-weight:600;letter-spacing:-0.01em;">
    {name}님, 첫 brag-card 완성을 축하드려요</h1>
  <p style="margin:12px 0;line-height:1.6;color:#202020;">
    이번 달의 거래 기록을 정리한 첫 brag-card 가 도착했습니다.
    이 카드는 결과의 기록일 뿐, 향후 의사결정에 대한 안내는 아닙니다.</p>
  {month_line}
  {ret_line}
  {cta}
  <p style="margin:24px 0;font-size:12px;color:#6B6B6B;line-height:1.5;">
    공유 링크는 사용자의 referral 코드를 포함합니다. 카카오톡 / 인스타그램 /
    트위터 등에서 카드 이미지가 미리보기로 노출됩니다.</p>
</div>
</body></html>"""


__all__ = ["is_first_brag_card", "maybe_send_first_brag_celebration"]
