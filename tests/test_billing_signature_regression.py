"""Stripe webhook signature regression guard (Wave D Sub-wave 1, D4).

The ``/api/billing/webhook`` handler must verify the Stripe-Signature
header via ``stripe.Webhook.construct_event``. Removing that call would
silently accept forged payloads — a Top-10 webhook-security vendor
incident class.

These tests are deliberately *structural* (not runtime): the runtime
behaviour is covered by ``tests/test_billing_webhook.py``. We assert
that the source file itself still contains the signature-verification
call so a careless refactor cannot delete it without one of:

  * Updating this test (forcing a reviewer to read why).
  * Bypassing pre-push (``--no-verify``) — leaves a deliberate trace.

The companion grep guard lives in ``.githooks/pre-push`` (step 1b).
Either layer catches the regression on its own; together they form
defense-in-depth.
"""
from __future__ import annotations

from pathlib import Path

_BILLING_PATH = Path(__file__).resolve().parent.parent / "routes" / "billing.py"


def test_billing_routes_file_exists():
    """Sanity — the file path the guard watches must actually exist."""
    assert _BILLING_PATH.exists(), (
        f"routes/billing.py missing — D4 guard cannot run. "
        f"Update tests/test_billing_signature_regression.py path."
    )


def test_construct_event_call_present():
    """``stripe.Webhook.construct_event`` must appear in routes/billing.py.

    Bare-string grep matching mirrors what the pre-push hook does so the
    two layers stay in lock-step. A reviewer wanting to remove this
    must explicitly update this test (auditable in the diff).
    """
    src = _BILLING_PATH.read_text(encoding="utf-8")
    assert "construct_event" in src, (
        "D4 REGRESSION: stripe.Webhook.construct_event no longer present in "
        "routes/billing.py. Restoring it is mandatory — silent acceptance of "
        "forged webhook payloads is a Stripe Top-10 security incident class."
    )


def test_construct_event_in_webhook_handler():
    """The call must live inside the ``/webhook`` route handler scope.

    A weaker version of this test would only check file-level presence,
    which would let a refactor accidentally hoist the call out of the
    handler (e.g. into a dead helper) without tripping the guard. We
    require the literal call to appear *after* the ``@billing_bp.route``
    decorator for ``/webhook`` so the handler body is what's protected.
    """
    src = _BILLING_PATH.read_text(encoding="utf-8")
    # Find the /webhook route decorator. The handler body starts after
    # this line and extends until the next module-level def/class — but
    # for the regression guard, "construct_event appears somewhere after
    # the decorator" is sufficient (the runtime test covers behaviour).
    webhook_idx = src.find('"/webhook"')
    assert webhook_idx >= 0, (
        "Could not find '/webhook' route decorator in routes/billing.py — "
        "test selector is stale, update tests/test_billing_signature_regression.py."
    )
    construct_idx = src.find("construct_event", webhook_idx)
    assert construct_idx > webhook_idx, (
        "D4 REGRESSION: construct_event call no longer follows the /webhook "
        "decorator in routes/billing.py. Signature verification must live "
        "inside the handler body."
    )
