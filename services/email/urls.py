"""Outbound link targets for the transactional / retention mails.

Why this module exists
----------------------
``_dashboard_url()`` was implemented three times — in
``onboarding_sequence``, ``retention_sequence`` and
``customer/inactive_nudge`` — and by 2026-09-07 the copies had already
diverged: the first two derived the host from ``FRONTEND_URL`` while the
nudge hard-coded the apex, which costs an extra 307 hop before the reader
reaches anything. CLAUDE.md §10 records the general lesson from the legal
scrubber: two implementations of one rule always drift. This is the same
shape, so there is now one.

The route was wrong in all three
--------------------------------
All three defaulted to ``/home``. That page was deleted; the frontend
answers it with a 308 to ``/mirror``. Measured 2026-09-07 from the nudge's
own default: ``pivoxquant.com/home`` → 307 → ``www`` → 308 → ``/mirror``,
two hops to reach a screen we could have named directly. It worked, which
is why nobody noticed — but every one of the five mails that actually ship
put a deleted route in its primary call to action, and CLAUDE.md's own rule
is "삭제된 표면을 가리키는 링크·문구를 만들지 마라".

The fallback host is ``www`` rather than the apex for the same reason: the
apex only 307s to it, and ``render.yaml`` sets ``FRONTEND_URL`` to the www
host anyway, so the fallback now agrees with production instead of costing
a redirect whenever it is used.
"""

from __future__ import annotations

import os

# The reader-facing home screen — 거울. `/home` was its old address and is
# now only a redirect; never point a mail at it again.
_DASHBOARD_PATH = "/mirror"
_PRICING_PATH = "/pricing"

_DEFAULT_FRONTEND = "https://www.pivoxquant.com"


def _frontend() -> str:
    return os.environ.get("FRONTEND_URL", _DEFAULT_FRONTEND).rstrip("/")


def dashboard_url() -> str:
    """Where a mail's primary CTA sends the reader.

    ``PIVOX_DASHBOARD_URL`` still overrides, so an operator can repoint every
    mail at once without a deploy.
    """
    return os.environ.get("PIVOX_DASHBOARD_URL", f"{_frontend()}{_DASHBOARD_PATH}")


def pricing_url() -> str:
    """Plans page.

    ⚠️ Only the Stage-1 ``d7_pro_nudge`` links here, and that step is
    excluded from ``active_sequence()`` unless ``PIVOX_PAID_PLANS_ENABLED``
    is on. While the beta is free ``/pricing`` 307s away, so a mail that
    linked here would be advertising a page that redirects — the shape
    표시광고법 §3 cares about.
    """
    return os.environ.get("PIVOX_PRICING_URL", f"{_frontend()}{_PRICING_PATH}")
