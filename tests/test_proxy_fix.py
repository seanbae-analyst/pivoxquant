"""W5.2 — ProxyFix regression tests.

Verifies that when a Flask app is wrapped with ``werkzeug.middleware.proxy_fix.ProxyFix``
matching the production configuration in ``app.create_app``:

  * ``X-Forwarded-For`` rewrites ``request.remote_addr`` to the **client** IP
    (so flask-limiter's ``get_remote_address`` no longer collapses every
    visitor onto the proxy's internal IP).
  * ``X-Forwarded-Proto: https`` rewrites ``request.scheme`` so external URL
    builders emit ``https://`` (OAuth redirect, email unsubscribe links).
  * ``X-Forwarded-Host`` is honoured for host-aware logic.
  * Without ProxyFix wrapping (the test conftest's default factory) the
    forwarded headers are ignored — confirms the fix is the load-bearing
    piece, not coincidental Flask behaviour.
  * Multi-hop spoofing is blocked: with ``x_for=1`` only the **right-most**
    forwarded hop (the trusted proxy's record) is honoured. An attacker
    that injects ``X-Forwarded-For: evil, real-client`` cannot poison
    ``remote_addr`` to ``evil``.

The production factory in ``app.py`` gates ProxyFix on
``FLASK_ENV=production`` — these tests build their own minimal Flask app and
apply ProxyFix unconditionally so the assertions are environment-independent.
"""
from __future__ import annotations

from flask import Flask, jsonify, request
from werkzeug.middleware.proxy_fix import ProxyFix


def _build_app(*, with_proxy_fix: bool) -> Flask:
    """Minimal Flask app exposing a probe endpoint that echoes IP / scheme / host.

    When ``with_proxy_fix`` is True the WSGI app is wrapped with the same
    1-hop ProxyFix configuration used in ``app.create_app`` for production.
    """
    app = Flask(__name__)
    app.config["TESTING"] = True

    if with_proxy_fix:
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=1,
            x_proto=1,
            x_host=1,
            x_prefix=1,
        )

    @app.route("/_probe")
    def probe():
        return jsonify({
            "remote_addr": request.remote_addr,
            "scheme": request.scheme,
            "host": request.host,
            "url": request.url,
        })

    return app


# ── With ProxyFix (matches production) ──────────────────────────────────────


def test_x_forwarded_for_rewrites_remote_addr() -> None:
    app = _build_app(with_proxy_fix=True)
    client = app.test_client()

    resp = client.get(
        "/_probe",
        headers={"X-Forwarded-For": "203.0.113.42"},
        environ_overrides={"REMOTE_ADDR": "10.0.0.1"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["remote_addr"] == "203.0.113.42", (
        "ProxyFix x_for=1 must rewrite remote_addr to the X-Forwarded-For "
        f"client value; got {body['remote_addr']!r}"
    )


def test_x_forwarded_proto_rewrites_scheme_to_https() -> None:
    app = _build_app(with_proxy_fix=True)
    client = app.test_client()

    resp = client.get(
        "/_probe",
        headers={
            "X-Forwarded-For": "203.0.113.42",
            "X-Forwarded-Proto": "https",
        },
        environ_overrides={"REMOTE_ADDR": "10.0.0.1", "wsgi.url_scheme": "http"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["scheme"] == "https", (
        f"ProxyFix x_proto=1 must rewrite request.scheme; got {body['scheme']!r}"
    )
    assert body["url"].startswith("https://"), (
        f"request.url must inherit the rewritten scheme; got {body['url']!r}"
    )


def test_x_forwarded_host_rewrites_host() -> None:
    app = _build_app(with_proxy_fix=True)
    client = app.test_client()

    resp = client.get(
        "/_probe",
        headers={
            "X-Forwarded-For": "203.0.113.42",
            "X-Forwarded-Host": "pivoxquant.com",
            "X-Forwarded-Proto": "https",
        },
        environ_overrides={"REMOTE_ADDR": "10.0.0.1"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["host"] == "pivoxquant.com", (
        f"ProxyFix x_host=1 must rewrite request.host; got {body['host']!r}"
    )


def test_multi_hop_spoof_attempt_blocked() -> None:
    """With x_for=1, only the *right-most* X-Forwarded-For value is trusted.

    Werkzeug's ProxyFix peels exactly ``x_for`` entries off the right side
    of the comma-separated header. An attacker injecting an extra hop on the
    left ("evil") therefore cannot poison ``request.remote_addr`` — the
    last-hop value remains the one the trusted proxy added.
    """
    app = _build_app(with_proxy_fix=True)
    client = app.test_client()

    # Attacker supplies an extra hop on the left; the trusted proxy appended
    # the real client (203.0.113.42) on the right. With x_for=1, ProxyFix
    # peels exactly one value off the right and ignores the spoofed hop.
    resp = client.get(
        "/_probe",
        headers={"X-Forwarded-For": "198.51.100.7, 203.0.113.42"},
        environ_overrides={"REMOTE_ADDR": "10.0.0.1"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["remote_addr"] == "203.0.113.42", (
        "Spoofing protection broken: x_for=1 must trust only the right-most "
        f"X-Forwarded-For hop; got {body['remote_addr']!r}"
    )
    assert body["remote_addr"] != "198.51.100.7", (
        "Attacker's left-side spoofed hop must NOT win over the trusted "
        "proxy's appended client value"
    )


# ── Without ProxyFix (control / test conftest behaviour) ────────────────────


def test_without_proxyfix_forwarded_headers_are_ignored() -> None:
    """Control test — confirms ProxyFix is the load-bearing piece.

    Without ProxyFix wrapping, ``request.remote_addr`` falls back to the
    raw WSGI ``REMOTE_ADDR`` (the proxy IP). This is the pre-fix behaviour
    that allowed every visitor to collapse onto the same flask-limiter
    bucket in production.
    """
    app = _build_app(with_proxy_fix=False)
    client = app.test_client()

    resp = client.get(
        "/_probe",
        headers={
            "X-Forwarded-For": "203.0.113.42",
            "X-Forwarded-Proto": "https",
        },
        environ_overrides={"REMOTE_ADDR": "10.0.0.1"},
    )
    assert resp.status_code == 200
    body = resp.get_json()
    # Pre-fix: proxy IP wins.
    assert body["remote_addr"] == "10.0.0.1"
    assert body["scheme"] == "http"


# ── Production factory wiring sanity check ──────────────────────────────────


def test_create_app_wires_proxy_fix() -> None:
    """Source-level sanity: ``app.py`` imports ProxyFix and wraps wsgi_app.

    A regression that drops the import or the wrap call would silently
    leave production unprotected. We grep the source text rather than
    booting ``create_app()`` (which spins up scheduler / OAuth / cache
    warmup — out of scope for this unit test) so the assertion is
    Python-version-independent (the project still has files using
    PEP 604 ``X | None`` syntax that Python 3.9 cannot parse at runtime).
    """
    import os

    app_py = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "app.py",
    )
    with open(app_py, encoding="utf-8") as f:
        src = f.read()

    assert "from werkzeug.middleware.proxy_fix import ProxyFix" in src, (
        "app.py must import ProxyFix from werkzeug.middleware.proxy_fix"
    )
    assert "app.wsgi_app = ProxyFix(" in src, (
        "app.create_app() must wrap app.wsgi_app with ProxyFix(...)"
    )
    assert "x_for=1" in src and "x_proto=1" in src, (
        "ProxyFix wrap must trust exactly 1 hop for x_for and x_proto"
    )
    assert "x_host=1" in src and "x_prefix=1" in src, (
        "ProxyFix wrap must trust 1 hop for x_host and x_prefix as well"
    )
    # Production gate — must NOT apply ProxyFix in dev/test where there is
    # no proxy, otherwise an attacker could spoof X-Forwarded-For locally.
    assert 'FLASK_ENV' in src and 'production' in src, (
        "ProxyFix wrap must be gated on FLASK_ENV=production"
    )
