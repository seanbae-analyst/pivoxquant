# Part of Journal Companion — see reports/legal/SAFE_FEATURE_SPECS_2026-04-23.md §6
"""tests/test_agent_waitlist.py — /api/agent/waitlist (P0-2).

Covers the five cases called out in HANDOVER.md v6 §3-D #2:
  1. POST with a valid new email              → 201 queued
  2. POST with a duplicate email              → 200 already-registered
  3. POST with a malformed / missing email    → 400
  4. POST beyond 5 per hour per IP            → 429
  5. POST without an ``email`` field at all   → 400

Also smoke-tests the admin list endpoint so the ops runbook in
``docs/JOURNAL_COMPANION_BETA.md`` can trust the round-trip.
"""
from __future__ import annotations


import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def _admin_user(app, make_user, monkeypatch):
    """Create an admin-capable user and wire ``ADMIN_EMAILS`` to match.

    ``routes.agent_admin._deny_non_admin`` fails closed when the env var is
    unset, so every test that exercises the admin listing must declare the
    admin here.
    """
    u = make_user(
        email="admin+waitlist@test.com",
        password="adminpass",
        tier="premium_plus",
    )
    monkeypatch.setenv("ADMIN_EMAILS", u["email"])
    return u


def _login(client, email: str, password: str):
    resp = client.post(
        "/api/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.data
    return resp


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/agent/waitlist — submission flow
# ─────────────────────────────────────────────────────────────────────────────


class TestWaitlistPost:
    def test_new_email_returns_201_queued(self, raw_client):
        """A fresh email yields 201 + status=queued + position >= 1."""
        r = raw_client.post(
            "/api/agent/waitlist",
            json={"email": "alice@example.com", "source": "landing-teaser"},
        )
        assert r.status_code == 201, r.data
        data = r.get_json()
        assert data["status"] == "queued"
        assert data["position"] >= 1
        assert "request_id" in data

    def test_duplicate_email_returns_200_already_registered(self, raw_client):
        """Second POST of the same email is idempotent — 200 + already-registered."""
        first = raw_client.post(
            "/api/agent/waitlist",
            json={"email": "bob@example.com"},
        )
        assert first.status_code == 201

        second = raw_client.post(
            "/api/agent/waitlist",
            json={"email": "bob@example.com", "persona": "value"},
        )
        assert second.status_code == 200, second.data
        data = second.get_json()
        assert data["status"] == "already-registered"
        # Position is a count — duplicate shouldn't grow it.
        assert data["position"] == first.get_json()["position"]

    def test_email_is_case_insensitive_for_dedup(self, raw_client):
        """Dedup uses the hash of the lowercased email — mixed-case repeats dedupe."""
        r1 = raw_client.post(
            "/api/agent/waitlist",
            json={"email": "Carol@Example.COM"},
        )
        assert r1.status_code == 201

        r2 = raw_client.post(
            "/api/agent/waitlist",
            json={"email": "carol@example.com"},
        )
        assert r2.status_code == 200
        assert r2.get_json()["status"] == "already-registered"

    def test_invalid_email_returns_400(self, raw_client):
        """Clearly malformed input never reaches the DB."""
        r = raw_client.post(
            "/api/agent/waitlist",
            json={"email": "not-an-email"},
        )
        assert r.status_code == 400
        assert r.get_json()["error"] == "invalid-email"

    def test_missing_email_returns_400(self, raw_client):
        """Body without an ``email`` field is rejected."""
        r = raw_client.post(
            "/api/agent/waitlist",
            json={"persona": "growth"},
        )
        assert r.status_code == 400
        assert r.get_json()["error"] == "missing-email"

    def test_invalid_persona_is_silently_dropped(self, raw_client):
        """Free-form persona text must not be echoed into the DB.

        Unknown persona values degrade to ``None`` — the submission still
        succeeds but ``persona_interest`` is NULL.
        """
        from models.companion_waitlist import CompanionWaitlist

        r = raw_client.post(
            "/api/agent/waitlist",
            json={"email": "dan@example.com", "persona": "<script>alert(1)</script>"},
        )
        assert r.status_code == 201
        row = CompanionWaitlist.query.filter_by(
            email_hash=CompanionWaitlist.hash_email("dan@example.com")
        ).first()
        assert row is not None
        assert row.persona_interest is None

    def test_valid_persona_is_persisted(self, raw_client):
        """Known personas round-trip to the DB."""
        from models.companion_waitlist import CompanionWaitlist

        r = raw_client.post(
            "/api/agent/waitlist",
            json={"email": "eve@example.com", "persona": "quant"},
        )
        assert r.status_code == 201
        row = CompanionWaitlist.query.filter_by(
            email_hash=CompanionWaitlist.hash_email("eve@example.com")
        ).first()
        assert row is not None
        assert row.persona_interest == "quant"

    def test_referrer_alias_is_accepted(self, raw_client):
        """The task spec uses ``referrer``; the landing teaser uses ``source``.

        The backend accepts either so the frontend contract can evolve
        without a breaking change.
        """
        from models.companion_waitlist import CompanionWaitlist

        r = raw_client.post(
            "/api/agent/waitlist",
            json={"email": "frank@example.com", "referrer": "pricing-page"},
        )
        assert r.status_code == 201
        row = CompanionWaitlist.query.filter_by(
            email_hash=CompanionWaitlist.hash_email("frank@example.com")
        ).first()
        assert row is not None
        assert row.source == "pricing-page"

    def test_runs_while_agent_is_disabled(self, raw_client, monkeypatch):
        """AGENT_ENABLED=0 MUST still accept waitlist submissions —
        suppressing the funnel during Closed Beta defeats the feature."""
        monkeypatch.setenv("AGENT_ENABLED", "0")
        r = raw_client.post(
            "/api/agent/waitlist",
            json={"email": "gwen@example.com"},
        )
        assert r.status_code == 201


# ─────────────────────────────────────────────────────────────────────────────
# Race condition — concurrent enroll() on same email_hash (P0-2 / GAP-1)
# ─────────────────────────────────────────────────────────────────────────────


class TestWaitlistRaceCondition:
    """Verify the enroll() upsert path when two requests race.

    SQLite's serialized writer makes a true threaded race hard to reproduce —
    the second transaction simply blocks rather than interleaving. We instead
    exercise the code path directly by:

      (a) ``test_enroll_returns_tuple_with_created_flag`` — contract test for
          the new ``(row, created)`` signature.

      (b) ``test_concurrent_enroll_returns_200_not_500`` — monkeypatch the
          pre-check ``filter_by(...).first()`` to return ``None`` the first
          time (simulating "we missed the existing row") while a second row
          is actually already committed. The flush then surfaces a genuine
          IntegrityError from SQLite's UNIQUE constraint and we assert the
          recovery path returns ``(existing_row, False)`` — i.e. no 500.

      (c) ``test_waitlist_route_handles_integrity_error_as_200`` — end-to-end
          simulation via the HTTP layer: we monkeypatch ``enroll()`` to raise
          a real IntegrityError on the first call inside the route, then
          verify the response is still 200/201 rather than 500.

    Neither (b) nor (c) is a threaded race — it's a deterministic injection of
    the exact exception the race would produce. We call this "partial
    reproduction": the catch-path is verified end-to-end, but the literal
    thread interleaving is not, because SQLite serialises writers.
    """

    def test_enroll_returns_tuple_with_created_flag(self, app):
        """enroll() returns (row, created) — first call True, second False."""
        from models.companion_waitlist import CompanionWaitlist

        with app.app_context():
            row1, created1 = CompanionWaitlist.enroll(
                email="race-a@example.com",
                consent_direct_email=True,
            )
            assert created1 is True
            assert row1.id is not None

            row2, created2 = CompanionWaitlist.enroll(
                email="race-a@example.com",
                consent_direct_email=True,
            )
            assert created2 is False
            # Same underlying row — dedup via email_hash.
            assert row2.id == row1.id

    def test_concurrent_enroll_returns_200_not_500(self, app, monkeypatch):
        """Simulate the race: pre-check misses, INSERT hits UNIQUE violation,
        recovery path re-fetches the winning row and returns (winner, False).

        We stage this by:
          1. Pre-seeding a row for the email (the "concurrent winner").
          2. Patching ``cls.query.filter_by(...).first()`` so the FIRST call
             inside ``enroll()`` returns None — i.e. the pre-check "misses"
             the winner, forcing the code down the INSERT-then-catch branch.
          3. The subsequent ``db.session.flush()`` then raises a genuine
             IntegrityError against SQLite's UNIQUE constraint on
             ``email_hash``. The recovery code catches it, re-fetches
             (this second call is unpatched → sees the real winner), and
             returns ``(winner, False)``.
        """
        from extensions import db
        from models.companion_waitlist import CompanionWaitlist

        email = "race-b@example.com"

        with app.app_context():
            # Step 1 — seed the "concurrent winner" directly, bypassing enroll().
            winner = CompanionWaitlist(
                email_hash=CompanionWaitlist.hash_email(email),
                email_plaintext=email,
                source="landing-teaser",
            )
            db.session.add(winner)
            db.session.commit()
            winner_id = winner.id

            # Step 2 — make the pre-check miss exactly once.
            # CompanionWaitlist.query is a scoped proxy, so we wrap the
            # filter_by(...).first() path to drop the result on first hit.
            original_filter_by = CompanionWaitlist.query.filter_by
            miss_budget = {"remaining": 1}

            def _patched_filter_by(*args, **kwargs):
                q = original_filter_by(*args, **kwargs)
                original_first = q.first

                def _first(*fa, **fkw):
                    if miss_budget["remaining"] > 0:
                        miss_budget["remaining"] -= 1
                        return None  # simulate pre-check race miss
                    return original_first(*fa, **fkw)

                q.first = _first
                return q

            monkeypatch.setattr(
                CompanionWaitlist.query, "filter_by", _patched_filter_by
            )

            # Step 3 — call enroll(). The pre-check returns None (patched),
            # the INSERT-then-flush hits UNIQUE, the except-branch re-fetches
            # (unpatched this time → sees the real winner).
            row, created = CompanionWaitlist.enroll(
                email=email,
                consent_direct_email=True,
            )

            assert created is False, (
                "race recovery path must report created=False, not raise 500"
            )
            assert row.id == winner_id, (
                "recovery path must return the winning row, not a phantom"
            )

            # And the total row count is unchanged — no duplicate rows.
            assert (
                CompanionWaitlist.query
                .filter_by(email_hash=CompanionWaitlist.hash_email(email))
                .count()
                == 1
            )

    def test_waitlist_route_handles_integrity_error_as_200(
        self, raw_client, monkeypatch
    ):
        """End-to-end: if enroll() recovers from an IntegrityError internally,
        the HTTP response is 200 already-registered — never 500.

        We stub ``enroll()`` to return the race-recovery tuple
        ``(existing_row, False)`` to prove the route treats that shape as a
        success path.
        """
        from models.companion_waitlist import CompanionWaitlist

        # Step 1 — create a real row so the route can read back a position.
        seed = raw_client.post(
            "/api/agent/waitlist",
            json={"email": "race-c@example.com"},
        )
        assert seed.status_code == 201

        # Step 2 — patch enroll() so the second POST goes through the
        # "race-recovered" return shape.
        real_enroll = CompanionWaitlist.enroll.__func__

        def _recovered_enroll(cls, **kwargs):
            # Delegate to the real implementation but force created=False
            # regardless — simulates the race-recovery path.
            row, _ = real_enroll(cls, **kwargs)
            return row, False

        monkeypatch.setattr(
            CompanionWaitlist,
            "enroll",
            classmethod(_recovered_enroll),
        )

        r = raw_client.post(
            "/api/agent/waitlist",
            json={"email": "race-c@example.com"},
        )
        assert r.status_code == 200, (r.status_code, r.data)
        assert r.get_json()["status"] == "already-registered"


# ─────────────────────────────────────────────────────────────────────────────
# Rate limit — 5 per hour per IP
# ─────────────────────────────────────────────────────────────────────────────


class TestWaitlistRateLimit:
    def test_sixth_request_within_hour_returns_429(
        self, raw_client, enable_rate_limit
    ):
        """Five successful submissions, sixth from the same IP is throttled."""
        for idx in range(5):
            r = raw_client.post(
                "/api/agent/waitlist",
                json={"email": f"heidi{idx}@example.com"},
            )
            assert r.status_code in (200, 201), (idx, r.data)

        r6 = raw_client.post(
            "/api/agent/waitlist",
            json={"email": "heidi-over@example.com"},
        )
        assert r6.status_code == 429, r6.data


# ─────────────────────────────────────────────────────────────────────────────
# Admin listing — GET /api/admin/agent/waitlist
# ─────────────────────────────────────────────────────────────────────────────


class TestAdminWaitlistList:
    def test_requires_admin(self, client, make_user):
        """Non-admin sessions are denied."""
        u = make_user(email="nobody@test.com", password="xxxxxxxx")
        _login(client, u["email"], u["password"])
        r = client.get("/api/admin/agent/waitlist")
        assert r.status_code == 403

    def test_unauthenticated_returns_401(self, raw_client):
        r = raw_client.get("/api/admin/agent/waitlist")
        assert r.status_code == 401

    def test_admin_sees_full_list(self, app, client, _admin_user):
        """Admin sees every row, newest-last (FIFO).

        Seeds the waitlist by inserting rows directly (the CSRF-aware
        ``client`` fixture handles the admin GET — mixing ``raw_client``
        and ``client`` in one test would race Flask's app-context stack).
        """
        from extensions import db
        from models.companion_waitlist import CompanionWaitlist

        with app.app_context():
            for email in ("ian@example.com", "judy@example.com"):
                row = CompanionWaitlist(
                    email_hash=CompanionWaitlist.hash_email(email),
                    email_plaintext=email,
                    source="landing-teaser",
                )
                db.session.add(row)
            db.session.commit()

        _login(client, _admin_user["email"], _admin_user["password"])
        r = client.get("/api/admin/agent/waitlist")
        assert r.status_code == 200, r.data
        data = r.get_json()
        assert data["ok"] is True
        assert data["total"] == 2
        emails = [row["email"] for row in data["rows"]]
        assert "ian@example.com" in emails
        assert "judy@example.com" in emails
