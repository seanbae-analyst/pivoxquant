"""Regression — global ``no_cache`` after_request hook must NOT clobber the
``Cache-Control: public, max-age=...`` header that public OG / social-share
image routes set (routes/artifacts.py).

Bug (2026-05-22): the blanket ``no_cache`` hook in ``app.create_app`` forced
``no-store`` on every response, including the PUBLIC OG image / brag-card
share endpoints. That broke crawler (Kakao / Twitter / Instagram) and CDN
caching of unfurl preview images — degrading the viral share loop.

Fix: a narrow allowlist of explicitly-public share-image / share-HTML paths
preserves the route's own ``public`` header; every other path keeps the
strict no-store policy.

We drive the *real* ``no_cache`` hook (conftest's minimal app does not
register it) by pulling it out of ``create_app()``'s after_request_funcs and
invoking it inside a request context for each target path. This exercises the
exact branch logic — path allowlist + ``public`` guard — without rendering,
DB, Pillow, or auth, and without colliding with the live artifacts routes.
"""
import pytest
from flask import Response

# conftest import sets DATABASE_URL / SECRET_KEY / etc. before this runs.
import tests.conftest  # noqa: F401
from app import create_app


@pytest.fixture(scope="module")
def real_app():
    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture(scope="module")
def no_cache_hook(real_app):
    """The live ``no_cache`` after_request function from ``create_app()``."""
    funcs = real_app.after_request_funcs.get(None, [])
    for f in funcs:
        if getattr(f, "__name__", "") == "no_cache":
            return f
    raise AssertionError("no_cache after_request hook not found")


def _run_hook(real_app, no_cache_hook, path, headers):
    """Invoke the hook for ``path`` against a response carrying ``headers``."""
    with real_app.test_request_context(path):
        resp = Response(b"x")
        for k, v in headers.items():
            resp.headers[k] = v
        return no_cache_hook(resp)


# ── Exempt share paths preserve the route's public cache header ──────────
@pytest.mark.parametrize(
    "path",
    [
        "/api/artifacts/monthly-brag/og-image/42",
        "/api/artifacts/brag-card/share/abcdef0123456789xyz/image",
        "/api/artifacts/brag-card/share/abcdef0123456789xyz",
    ],
)
def test_share_image_paths_preserve_public_cache(real_app, no_cache_hook, path):
    out = _run_hook(
        real_app, no_cache_hook, path,
        {"Cache-Control": "public, max-age=86400"},
    )
    cc = out.headers.get("Cache-Control", "")
    assert "public" in cc, f"{path} lost its public Cache-Control: {cc!r}"
    assert "max-age=86400" in cc
    assert "no-store" not in cc
    assert "Pragma" not in out.headers


# ── Sensitive / regular API always gets strict no-store ──────────────────
def test_sensitive_api_still_no_store(real_app, no_cache_hook):
    # Even if a non-allowlisted route mistakenly set ``public``, the hook
    # must override it with no-store — only allowlisted paths are exempt.
    out = _run_hook(
        real_app, no_cache_hook, "/api/portfolio/positions",
        {"Cache-Control": "public, max-age=86400"},
    )
    cc = out.headers.get("Cache-Control", "")
    assert "no-store" in cc, f"sensitive API was not no-store: {cc!r}"
    assert "no-cache" in cc
    assert out.headers.get("Pragma") == "no-cache"
    assert "public" not in cc


def test_unknown_path_no_store(real_app, no_cache_hook):
    out = _run_hook(real_app, no_cache_hook, "/", {})
    cc = out.headers.get("Cache-Control", "")
    assert "no-store" in cc
    assert out.headers.get("Pragma") == "no-cache"


# ── A share path WITHOUT a public header is still locked down ────────────
def test_share_path_without_public_header_gets_no_store(real_app, no_cache_hook):
    # Error responses on share paths (e.g. 404 with no public header) must
    # still be no-store — the ``public`` guard prevents leaking the exemption.
    out = _run_hook(
        real_app, no_cache_hook, "/api/artifacts/monthly-brag/og-image/42",
        {},  # route returned an error, never set public
    )
    cc = out.headers.get("Cache-Control", "")
    assert "no-store" in cc, f"share error response was cached: {cc!r}"


def test_unanchored_share_ish_path_not_exempt(real_app, no_cache_hook):
    # Regex is anchored ($) — a longer path under the share prefix must not
    # match and must receive no-store even if it carries a public header.
    out = _run_hook(
        real_app, no_cache_hook,
        "/api/artifacts/monthly-brag/og-image/42/extra",
        {"Cache-Control": "public, max-age=86400"},
    )
    cc = out.headers.get("Cache-Control", "")
    assert "no-store" in cc, f"unanchored path leaked exemption: {cc!r}"
