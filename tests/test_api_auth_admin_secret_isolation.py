"""Regression guard — admin secret must not bypass user-data endpoints.

Background (commit 7cc7185, reverted in this session):

    `api_auth` previously allowed an X-Admin-Secret bypass so production cron
    triggers (GitHub Actions → /api/artifacts/weekly-memo/trigger) could call
    admin-gated endpoints without a user session. The bypass leaked to ALL
    `@api_auth`-decorated routes — including user-data endpoints like
    `/api/artifacts/list` that dereference `current_user.id`. With the bypass
    active, an admin-secret call hit those routes as an Anonymous user and
    crashed with 500 on the first `current_user.id` access.

Fix:

    - `api_auth` is user-only (no admin bypass).
    - Cron triggers do NOT use `@api_auth`; they call
      `_check_cron_admin_secret()` inside the function body instead.

These tests freeze the post-fix invariants so the regression cannot
re-emerge silently.
"""
from __future__ import annotations

import os


# ─── 1. user-data endpoint must reject X-Admin-Secret ────────────────────

def test_admin_secret_does_not_reach_user_endpoint_list(client, monkeypatch):
    """`/api/artifacts/list` reads `current_user.id` — admin secret must NOT
    let an unauthenticated request through. Expect 401, never 500.
    """
    monkeypatch.setenv("ARTIFACT_TRIGGER_SECRET", "test-secret-12345")
    resp = client.get(
        "/api/artifacts/list",
        headers={"X-Admin-Secret": "test-secret-12345"},
    )
    assert resp.status_code == 401, (
        f"admin secret bypassed user endpoint (status={resp.status_code}). "
        f"Pre-fix bug: api_auth let admin secret through, then "
        f"current_user.id raised AttributeError → 500."
    )


def test_admin_secret_does_not_reach_user_endpoint_preview(client, monkeypatch):
    """Same guard for `/api/artifacts/<id>/preview`."""
    monkeypatch.setenv("ARTIFACT_TRIGGER_SECRET", "test-secret-12345")
    resp = client.get(
        "/api/artifacts/1/preview",
        headers={"X-Admin-Secret": "test-secret-12345"},
    )
    assert resp.status_code == 401


# ─── 2. cron trigger still works with admin secret ───────────────────────

def test_cron_trigger_accepts_admin_secret(client, monkeypatch):
    """Cron endpoint reachable with valid admin secret (no user session).

    The trigger may return 4xx/5xx for downstream reasons (no users to
    notify, mocked services), but it must NOT return 401 — that would
    mean the admin secret path is broken again.
    """
    monkeypatch.setenv("ARTIFACT_TRIGGER_SECRET", "test-secret-12345")
    resp = client.post(
        "/api/artifacts/weekly-memo/trigger",
        headers={"X-Admin-Secret": "test-secret-12345"},
        json={},
    )
    assert resp.status_code != 401, (
        f"cron trigger rejected valid admin secret (status={resp.status_code}). "
        f"Production cron will fail."
    )


def test_cron_trigger_rejects_wrong_admin_secret(client, monkeypatch):
    """Wrong admin secret → 403 (not 401, not 200)."""
    monkeypatch.setenv("ARTIFACT_TRIGGER_SECRET", "test-secret-12345")
    resp = client.post(
        "/api/artifacts/weekly-memo/trigger",
        headers={"X-Admin-Secret": "WRONG"},
        json={},
    )
    assert resp.status_code == 403


def test_cron_trigger_rejects_no_secret_at_all(client, monkeypatch):
    """No admin secret → 403 (endpoint internal check)."""
    monkeypatch.setenv("ARTIFACT_TRIGGER_SECRET", "test-secret-12345")
    monkeypatch.delenv("DEV_LOGIN_SECRET", raising=False)
    resp = client.post("/api/artifacts/weekly-memo/trigger", json={})
    # Either 403 (wrong secret) or 401 (no auth) — both are correct rejections.
    # The key invariant: NOT 200.
    assert resp.status_code in (401, 403), (
        f"trigger reachable without secret OR auth (status={resp.status_code})"
    )


# ─── 3. structural guard — decorator stack invariant ─────────────────────

def test_api_auth_decorator_has_no_admin_bypass():
    """AST guard: api_auth's executable code must not reference admin-bypass
    string constants. Docstrings are excluded — they may describe history.

    If someone re-introduces the bypass, this test fails immediately —
    long before a production 500 caused by current_user.id on Anonymous.
    """
    import ast

    tree = ast.parse(open("routes/decorators.py").read())
    api_auth_fn = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "api_auth"
    )

    # Strip the leading docstring expression — only inspect executable code.
    body = api_auth_fn.body
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        body = body[1:]

    code_strings = []
    for node in body:
        for sub in ast.walk(node):
            # Constants in executable code (not docstrings) — skip the
            # docstrings of any nested defs too.
            if isinstance(sub, ast.FunctionDef):
                inner = sub.body
                if (inner and isinstance(inner[0], ast.Expr)
                        and isinstance(inner[0].value, ast.Constant)
                        and isinstance(inner[0].value.value, str)):
                    inner = inner[1:]
                for n in inner:
                    for s in ast.walk(n):
                        if isinstance(s, ast.Constant) and isinstance(s.value, str):
                            code_strings.append(s.value)
            elif isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                code_strings.append(sub.value)

    forbidden = ("X-Admin-Secret", "ARTIFACT_TRIGGER_SECRET", "DEV_LOGIN_SECRET")
    for token in forbidden:
        assert not any(token in s for s in code_strings), (
            f"api_auth executable code references {token!r} — admin bypass "
            f"must live in _check_cron_admin_secret(), not the user-auth "
            f"decorator."
        )


def test_cron_triggers_have_no_api_auth_decorator():
    """Source-level guard: every `*_trigger` route in artifacts.py must NOT
    be wrapped in @api_auth (which would gate cron behind user auth and
    break production cron blast).
    """
    import re

    with open("routes/artifacts.py") as f:
        lines = f.readlines()

    trigger_funcs = []
    for i, line in enumerate(lines):
        m = re.match(r"def\s+(\w+_trigger)\s*\(", line)
        if m:
            # Walk backwards over decorator stack.
            j = i - 1
            decorators = []
            while j >= 0 and lines[j].lstrip().startswith("@"):
                decorators.append(lines[j].strip())
                j -= 1
            trigger_funcs.append((m.group(1), decorators))

    assert trigger_funcs, "no *_trigger functions found — test mis-targeted"

    offenders = [name for name, decs in trigger_funcs if "@api_auth" in decs]
    assert not offenders, (
        f"these cron triggers still have @api_auth (would 401 production cron): "
        f"{offenders}"
    )
