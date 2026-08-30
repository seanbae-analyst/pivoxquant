"""Regression guard — the admin secret must not bypass user-data endpoints.

Background (commit 7cc7185, reverted at the time):

    `api_auth` once allowed an X-Admin-Secret bypass so production cron
    triggers could reach admin-gated endpoints without a user session. The
    bypass leaked to EVERY `@api_auth` route, including user-data endpoints
    that dereference `current_user.id` — an admin-secret call arrived as an
    Anonymous user and 500'd on the first attribute access.

Fix, frozen here:

    - `api_auth` is user-only. No admin bypass, ever.

2026-08-30: the original vehicles for these tests were the artefact
endpoints (`/api/artifacts/list`, `/api/artifacts/<id>/preview`, the
`*_trigger` cron routes). That tree is gone, so the user-data half is
repointed at `/api/watchlist` — a surviving `@api_auth` route that reads
`current_user.id` on its first line, which is exactly the shape the
original bug crashed on.

The cron-trigger half is NOT repointed. `_check_cron_admin_secret()` and
every `*_trigger` route lived in routes/artifacts.py and went with it, so
there is nothing left to assert about them. Rewriting those tests against
a substitute would have them pass while guarding nothing. If cron triggers
return, the invariant returns with them — the AST guard below still holds
the important half in the meantime, since it constrains `api_auth` itself
rather than any particular caller.
"""
from __future__ import annotations

import ast


# ─── 1. a user-data endpoint must reject X-Admin-Secret ──────────────────

def test_admin_secret_does_not_reach_user_endpoint(client, monkeypatch):
    """`/api/watchlist` reads `current_user.id`, so an admin secret must not
    authenticate the request — it would arrive Anonymous and crash.
    """
    monkeypatch.setenv("ADMIN_SECRET", "test-admin-secret")

    resp = client.get(
        "/api/watchlist",
        headers={"X-Admin-Secret": "test-admin-secret"},
    )

    # 401 is the point. A 500 would mean the bypass is back and the handler
    # dereferenced current_user.id on an Anonymous user.
    assert resp.status_code == 401, (
        f"admin secret reached a user-data endpoint (got {resp.status_code}) — "
        "the api_auth admin bypass has returned"
    )


def test_admin_secret_does_not_reach_user_write_endpoint(client, monkeypatch):
    """Same guard on a write path — POST carries more damage than a read."""
    monkeypatch.setenv("ADMIN_SECRET", "test-admin-secret")

    resp = client.post(
        "/api/watchlist",
        headers={"X-Admin-Secret": "test-admin-secret"},
        json={"ticker": "005930"},
    )

    assert resp.status_code == 401, (
        f"admin secret reached a user write endpoint (got {resp.status_code})"
    )


# ─── 2. api_auth itself must contain no bypass ───────────────────────────

def test_api_auth_decorator_has_no_admin_bypass():
    """AST guard: api_auth's executable code must not reference admin-bypass
    tokens. Source-level rather than behavioural so it fails even if no
    route happens to exercise the path.
    """
    with open("routes/decorators.py") as f:
        tree = ast.parse(f.read())

    api_auth_fn = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "api_auth"
    )

    # Docstrings are stripped — the decorator's own docstring describes the
    # bypass it must never contain, and counting that as a reference would
    # make the guard fire on its own explanation.
    body = api_auth_fn.body
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        body = body[1:]

    code_strings: list[str] = []
    for node in body:
        for sub in ast.walk(node):
            if isinstance(sub, ast.FunctionDef):
                inner = sub.body
                if (inner and isinstance(inner[0], ast.Expr)
                        and isinstance(inner[0].value, ast.Constant)
                        and isinstance(inner[0].value.value, str)):
                    inner = inner[1:]
                for n in inner:
                    for s2 in ast.walk(n):
                        if isinstance(s2, ast.Constant) and isinstance(s2.value, str):
                            code_strings.append(s2.value)
            elif isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                code_strings.append(sub.value)

    forbidden = ("X-Admin-Secret", "ARTIFACT_TRIGGER_SECRET", "DEV_LOGIN_SECRET")
    for token in forbidden:
        assert not any(token in s for s in code_strings), (
            f"api_auth executable code references {token!r} — admin bypass "
            "must never be reintroduced into the user-auth decorator"
        )
