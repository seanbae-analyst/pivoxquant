"""tests/test_csrf_exempt_prefixes.py — no CSRF exemption for routes that don't exist.

2026-10-09: ``security._CSRF_EXEMPT_PREFIXES`` still exempted
``/api/auth/sim-onboard`` although the route was deleted with CAUS
(2026-09-01, ``tests/test_deleted_modules_stay_deleted.py``). A dead prefix is
a pre-authorised CSRF hole for whatever route next lands under that path.
"""
from __future__ import annotations

from security import _CSRF_EXEMPT_PREFIXES


def test_sim_onboard_is_not_csrf_exempt():
    assert not any(p.startswith("/api/auth/sim-onboard") for p in _CSRF_EXEMPT_PREFIXES)


def test_sim_onboard_route_does_not_exist(app):
    rules = [r.rule for r in app.url_map.iter_rules()]
    assert not [r for r in rules if r.startswith("/api/auth/sim-onboard")]
