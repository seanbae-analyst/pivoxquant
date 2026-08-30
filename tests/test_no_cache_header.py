"""The global ``no_cache`` after_request hook must no-store everything.

This file was ``test_no_cache_share_exempt.py``. It guarded a narrow
allowlist added on 2026-05-22: the blanket ``no_cache`` hook was clobbering
``Cache-Control: public, max-age=...`` on the public OG / brag-card share
image routes, which broke crawler and CDN caching of unfurl previews.

Those routes were removed with services/artifacts on 2026-08-30, so the
allowlist matched nothing and went with them — an exemption that matches
no live path is a hole waiting for a future path to fall into it. What
survives is the property the allowlist was carved out of: every response
carries no-store. That is the part worth freezing, so the three
exemption-shaped tests are gone and the two that assert the default
remain, now stated positively rather than as "everything else".

The *real* hook is driven directly (conftest's minimal app does not
register it) by pulling it out of ``create_app()``'s after_request_funcs
and invoking it in a request context — no rendering, DB, or auth needed.
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


def _run_hook(real_app, no_cache_hook, path, headers=None):
    """Invoke the hook for ``path`` against a response carrying ``headers``."""
    with real_app.test_request_context(path):
        resp = Response(b"x")
        for k, v in (headers or {}).items():
            resp.headers[k] = v
        return no_cache_hook(resp)


@pytest.mark.parametrize("path", [
    "/api/portfolio",
    "/api/watchlist",
    "/api/auth/me",
    "/api/behavior/turnover-mirror",
    "/some/unknown/path",
    "/",
])
def test_every_path_gets_no_store(real_app, no_cache_hook, path):
    out = _run_hook(real_app, no_cache_hook, path)
    assert "no-store" in out.headers["Cache-Control"]
    assert out.headers["Pragma"] == "no-cache"


def test_a_public_header_does_not_win(real_app, no_cache_hook):
    """A route setting its own public cache header is still overridden.

    The removed allowlist was the only way to opt out. Without it, a route
    that sets `public, max-age=...` — by habit or by mistake — must not
    thereby publish an authenticated response to a CDN.
    """
    out = _run_hook(
        real_app, no_cache_hook, "/api/portfolio",
        {"Cache-Control": "public, max-age=3600"},
    )
    assert "no-store" in out.headers["Cache-Control"]
    assert "public" not in out.headers["Cache-Control"]
