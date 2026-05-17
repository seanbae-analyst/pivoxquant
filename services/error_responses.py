"""Centralized JSON error response factory.

Why this module exists
----------------------
A wave 13 structure audit of routes/*.py found 393 sites calling
``jsonify({"error": ...})`` but only 1 also carrying the ``error_kr``
field (PR #419 swept routes/ai.py). Korean users on every other
endpoint saw raw English error strings — a 정통망법 + UX consistency
gap that grew quietly as the surface expanded.

The fix is structural: instead of asking every author to remember
the {error, error_kr, code} triple by hand, route callers through
``api_error()`` and the shape is enforced.

Contract
--------
Every error response returned by the SPA-facing API SHOULD be
constructed via this helper. The Flask test client + frontend
``apiFetch`` both rely on the same three top-level keys:

    {
        "error":      "<English message, dev-readable>",
        "error_kr":   "<Korean message, user-facing toast>",
        "code":       "<MACHINE_READABLE_STABLE_KEY>",
    }

``code`` lets the frontend pattern-match without parsing copy
strings (the failure mode PR #416 / #423 surfaced for tier responses).

Status codes are passed through as a tuple so callers preserve
existing semantics — 400 / 401 / 403 / 404 / 409 / 413 / 422 / 429
/ 500 / 503 are all valid.

Migration strategy
------------------
The helper is additive. Existing ``jsonify({"error": ...})`` sites
continue to work; routes get migrated one file at a time per the
``feedback_pr_workflow`` ">30 files split" rule. Each migration PR
also adds ``error_kr`` + ``code`` for free since the helper requires
them.

A regression test (``tests/test_error_responses.py``) pins the
contract so any future helper drift is caught immediately.

2026-05-17 wave 13 — PR #435.
"""
from __future__ import annotations

from typing import Tuple

from flask import jsonify
from flask.wrappers import Response


# Sentinel for "no machine-readable code" — historical responses that
# don't have a stable code yet. New code SHOULD pass a code explicitly.
DEFAULT_CODE = "INTERNAL_ERROR"


def api_error(
    *,
    en: str,
    kr: str,
    code: str = DEFAULT_CODE,
    status: int = 500,
    **extra: object,
) -> Tuple[Response, int]:
    """Build a JSON error response with the canonical three-key shape.

    Example::

        from services.error_responses import api_error

        @bp.route("/foo")
        def foo():
            if not allowed:
                return api_error(
                    en="Account is suspended.",
                    kr="계정이 정지되었습니다.",
                    code="ACCOUNT_SUSPENDED",
                    status=403,
                )

    Extra keyword arguments are merged into the response body so callers
    can attach context like ``retry_after`` / ``detail`` without
    bypassing the helper::

        return api_error(
            en="Stripe webhook missing signature",
            kr="Stripe 웹훅 서명이 누락되었습니다.",
            code="STRIPE_WEBHOOK_MISSING_SIGNATURE",
            status=400,
            detail=str(exc),
        )

    Returns the Flask ``(response, status)`` tuple so callers can simply
    ``return api_error(...)`` from any view function.
    """
    body: dict = {"error": en, "error_kr": kr, "code": code}
    # Reserved keys never overridden by callers — guards against typos
    # like ``api_error(en=..., error_kr="...")`` (the ``kr`` slot is
    # the canonical name).
    for reserved in ("error", "error_kr", "code"):
        extra.pop(reserved, None)
    body.update(extra)
    return jsonify(body), status
